"""Browser onboarding using the same encrypted, single-use keydrops as Telegram."""
import asyncio
import json
import time
from importlib import resources

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from neurogate.cli import load_catalog, ordered_services
from neurogate.keydrop import DEFAULT_DROP_URL, new_code, seal

RAW = "https://raw.githubusercontent.com/NurTechKSA/neurogate/main"
NO_STORE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff"}


def setup_router(store, public_url, check_key):
    router = APIRouter()
    active = 0
    attempts = {}
    services = ordered_services(load_catalog())

    def error(status, message):
        return JSONResponse({"ok": False, "message": message}, status_code=status, headers=NO_STORE)

    @router.get("/start", response_class=HTMLResponse)
    async def start():
        page = resources.files("neurogate").joinpath("static/start.html").read_text(encoding="utf-8")
        return HTMLResponse(page, headers=NO_STORE)

    @router.get("/setup/services")
    async def catalog():
        safe = [{k: s.get(k, "") for k in ("id", "name", "gives", "needs", "key_url", "steps")}
                | {"extra": [e.get("prompt", "Дополнительное значение") for e in s.get("extra_env", [])]}
                for s in services]
        return JSONResponse({"services": safe}, headers=NO_STORE)

    @router.post("/setup/create")
    async def create(request: Request):
        nonlocal active
        # Compare against configured public origin: TLS terminates at the reverse proxy.
        if (request.headers.get("origin") not in (None, public_url)
                or request.headers.get("sec-fetch-site") not in (None, "same-origin", "none")):
            return error(403, "Откройте форму на сайте NeuroGate и повторите попытку.")
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            return error(415, "Нужен запрос JSON.")
        # Bound both concurrency and the client map. Never trust a client-supplied forwarded IP.
        now = time.monotonic()
        for ip, (_, expires) in list(attempts.items()):
            if expires <= now:
                del attempts[ip]
        ip = request.client.host if request.client else "unknown"
        count, expires = attempts.get(ip, (0, now + 60))
        if count >= 10 or (ip not in attempts and len(attempts) >= 1024) or active >= 4:
            return error(429, "Слишком много проверок. Подождите минуту и попробуйте снова.")
        attempts[ip] = count + 1, expires
        active += 1
        try:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 16384:
                    return error(413, "Слишком большой запрос. Вставьте только ключ.")
                body.extend(chunk)
            try:
                data = json.loads(body)
            except (ValueError, UnicodeError):
                return error(400, "Не удалось прочитать запрос. Обновите страницу.")
            if not isinstance(data, dict):
                return error(400, "Не удалось прочитать поля формы.")
            service = next((s for s in services if s["id"] == data.get("id")), None)
            key, extra, system = data.get("key"), data.get("extra", []), data.get("os")
            if (not service or system not in ("mac", "win") or not isinstance(key, str)
                    or not 1 <= len(key.strip()) <= 4096 or not isinstance(extra, list)
                    or len(extra) != len(service.get("extra_env", []))
                    or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 4096 for v in extra)):
                return error(400, "Выберите компьютер и сервис, заполните ключ и дополнительные поля.")
            key = key.strip()
            # Multiline credentials cannot be safely imported into a local .env file.
            if any(c in value for value in [key, *extra] for c in ("\r", "\n", "\x00")):
                return error(400, "Вставьте ключ одной строкой, без переносов.")
            try:
                ok, _ = await asyncio.to_thread(check_key, service, key)
            except Exception:
                ok = None
            if ok is False:
                return error(400, "Сервис отклонил ключ. Скопируйте его целиком и попробуйте снова.")
            values = {service["env"]: key}
            values.update({spec["env"]: value.strip()
                           for spec, value in zip(service.get("extra_env", []), extra)})
            drop_id, secret, code = new_code()
            store.cleanup()
            store.add_drop(drop_id, seal(secret, values))
            if system == "mac":
                drop = "" if public_url == DEFAULT_DROP_URL else f"NEUROGATE_DROP_URL='{public_url}' "
                command = f"curl -fsSL {RAW}/install.sh | {drop}NEUROGATE_CODE={code} bash"
            else:
                drop = "" if public_url == DEFAULT_DROP_URL else f'$env:NEUROGATE_DROP_URL="{public_url}"; '
                command = f'{drop}$env:NEUROGATE_CODE="{code}"; irm {RAW}/install.ps1 | iex'
            message = ("Ключ проверен. Скопируйте команду установки." if ok else
                       "Сервис сейчас не дал проверить ключ. Команда готова, работоспособность ключа пока не подтверждена.")
            return JSONResponse({"ok": True, "message": message, "command": command}, headers=NO_STORE)
        except Exception:
            # Do not send exception text (which might contain submitted credentials) to the client.
            return error(503, "Не удалось подготовить команду. Попробуйте позже.")
        finally:
            active -= 1

    return router
