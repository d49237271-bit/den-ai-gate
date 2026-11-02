"""Фальшивые провайдеры для e2e: /dead отвечает 429, /live ведёт себя как модель с инструментами.

Какой инструмент вызвать, модель берёт из текста задачи: [[TOOL Write file_path={a.py} content={x}]].
Каждый запрос пишется в MOCK_LOG: тест видит всё, что ушло бы настоящему провайдеру.
"""
import json
import os
import re
import sys
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

LOG = os.environ.get("MOCK_LOG", "/tmp/mock.log")
app = FastAPI()

def log(rec):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

@app.post("/dead/v1/chat/completions")
async def dead(req: Request):
    b = await req.json()
    log({"up": "dead", "model": b.get("model")})
    return JSONResponse({"error": {"message": "rate limited", "code": 429}}, status_code=429)

def text_of(m):
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""

def plan(body):
    msgs = body.get("messages", [])
    tools = {t["function"]["name"]: t["function"] for t in body.get("tools") or []}
    last = msgs[-1] if msgs else {}
    joined = "\n".join(text_of(m) for m in msgs if m.get("role") == "user")
    wanted = re.findall(r"\[\[TOOL (\w+) (.*?)\]\]", joined)
    done = sum(1 for m in msgs if m.get("role") == "tool")
    if tools and done < len(wanted):
        name, args = wanted[done]
        real = next((n for n in tools if n.lower() == name.lower()), None)
        if real:
            kv = dict(re.findall(r'(\w+)=\{(.*?)\}', args))
            return {"tool": real, "args": kv}
    if last.get("role") == "tool":
        return {"text": "ГОТОВО. Результат инструмента: " + text_of(last)[:300]}
    return {"text": "Ответ фейковой модели."}

def sse(cid, model, delta, finish=None):
    return "data: " + json.dumps({"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}, ensure_ascii=False) + "\n\n"

@app.post("/live/v1/chat/completions")
async def live(req: Request):
    b = await req.json()
    p = plan(b)
    log({"up": "live", "model": b.get("model"), "stream": bool(b.get("stream")), "tools": [t["function"]["name"] for t in b.get("tools") or []],
         "msgs": len(b.get("messages", [])), "size": len(json.dumps(b)), "plan": p,
         "body": json.dumps(b, ensure_ascii=False)})  # целиком: отрицательные проверки должны видеть всё
    cid = "chatcmpl-" + uuid.uuid4().hex[:8]
    model = b.get("model", "mock")
    if b.get("stream"):
        def gen():
            yield sse(cid, model, {"role": "assistant"})
            if "tool" in p:
                yield sse(cid, model, {"tool_calls": [{"index": 0, "id": "call_" + uuid.uuid4().hex[:8], "type": "function",
                    "function": {"name": p["tool"], "arguments": json.dumps(p["args"], ensure_ascii=False)}}]})
                yield sse(cid, model, {}, "tool_calls")
            else:
                yield sse(cid, model, {"content": p["text"]})
                yield sse(cid, model, {}, "stop")
            yield "data: " + json.dumps({"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model, "choices": [],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}) + "\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    if "tool" in p:
        msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_" + uuid.uuid4().hex[:8], "type": "function",
               "function": {"name": p["tool"], "arguments": json.dumps(p["args"], ensure_ascii=False)}}]}
        fin = "tool_calls"
    else:
        msg = {"role": "assistant", "content": p["text"]}
        fin = "stop"
    return {"id": cid, "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": fin}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

@app.get("/health")
async def h():
    return {"ok": True}

uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
