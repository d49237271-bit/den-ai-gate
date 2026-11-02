"""Границы бесплатного исполнителя на настоящем Claude Code.

Бесплатная модель — чужой код на компьютере подписчика, поэтому проверяем не флаги, а результат:
что реально появилось на диске и что реально ушло провайдеру. Claude Code обновляется сам, и
поведение прав может измениться: запускай этот тест перед каждым переносом main в stable.

Запуск: uv run pytest tests/e2e -q   (нужен `claude` в PATH; к Anthropic запросы не уходят)
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.skipif(shutil.which("claude") is None, reason="нужен Claude Code")

HERE = Path(__file__).parent
BIN = Path(sys.executable).parent
NEUROGATE = BIN / "neurogate"
TIMEOUT = 120

CONFIG = """
providers:
  - {{name: "dead:model", kind: openai, base_url: "http://127.0.0.1:{port}/dead/v1", model: dead, api_key_env: MOCK_KEY, timeout: 30}}
  - {{name: "live:model", kind: openai, base_url: "http://127.0.0.1:{port}/live/v1", model: live, api_key_env: MOCK_KEY, timeout: 30}}
default_chain: chat
chains:
  chat: ["dead:model", "live:model"]
  code: ["dead:model", "live:model"]
  code_fast: ["dead:model", "live:model"]
"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_up(url: str) -> None:
    for _ in range(60):
        try:
            if httpx.get(url, timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"не поднялся {url}")


def clean_env(**extra: str) -> dict[str, str]:
    """Без переменных самого Claude Code: вложенный запуск не должен наследовать чужую сессию."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "CLAUDE", "NEUROGATE_"))}
    env.update(extra)
    return env


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("stack")
    home = tmp / "home"
    home.mkdir()
    mock_port, gate_port = free_port(), free_port()
    (tmp / "config.yaml").write_text(CONFIG.format(port=mock_port), encoding="utf-8")
    log = tmp / "provider.log"
    log.write_text("", encoding="utf-8")
    env = clean_env(HOME=str(home), MOCK_LOG=str(log), MOCK_KEY="x", NEUROGATE_CONFIG=str(tmp / "config.yaml"),
                    NEUROGATE_PORT=str(gate_port), NEUROGATE_STATS_DB=str(tmp / "stats.db"),
                    NEUROGATE_SKIP_LIVENESS="1", NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    procs = [
        subprocess.Popen([sys.executable, "-I", str(HERE / "mock_upstream.py"), str(mock_port)], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        subprocess.Popen([str(NEUROGATE), "serve"], env=env, cwd=tmp,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    ]
    try:
        wait_up(f"http://127.0.0.1:{mock_port}/health")
        wait_up(f"http://127.0.0.1:{gate_port}/health")
        yield {"env": env, "home": home, "log": log, "tmp": tmp, "port": gate_port}
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=10)


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".env").write_text("SECRET=hunter2\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/.env.local").write_text("SECRET=hunter3\n", encoding="utf-8")
    (tmp_path / "server.pem").write_text("hunter4\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def delegate(stack, project: Path, task: str, *flags: str) -> str:
    env = dict(stack["env"], NEUROGATE_CALLER_DIR=str(project))
    r = subprocess.run([str(NEUROGATE), "delegate", *flags, task], env=env, cwd=stack["tmp"],
                       capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    return r.stdout + r.stderr


def provider_saw(stack, needle: str) -> bool:
    return needle in stack["log"].read_text(encoding="utf-8")


def last_tools(stack) -> list[str]:
    lines = [json.loads(ln) for ln in stack["log"].read_text(encoding="utf-8").splitlines()]
    return next(r["tools"] for r in reversed(lines) if r.get("up") == "live" and r.get("tools"))


# ---------------------------------------------------------------- работа

def test_writes_and_edits_inside_project(stack, project):
    delegate(stack, project, f"[[TOOL Write file_path={{{project}/new.py}} content={{print(42)}}]]")
    assert (project / "new.py").read_text(encoding="utf-8") == "print(42)"
    delegate(stack, project, f"[[TOOL Read file_path={{{project}/a.py}}]] "
                             f"[[TOOL Edit file_path={{{project}/a.py}} old_string={{print(1)}} new_string={{print(2)}}]]")
    assert "print(2)" in (project / "a.py").read_text(encoding="utf-8")


def test_gateway_switches_after_rate_limit(stack, project):
    delegate(stack, project, "привет")
    records = [json.loads(ln) for ln in stack["log"].read_text(encoding="utf-8").splitlines()]
    assert any(r.get("up") == "live" for r in records)


def test_provider_log_sees_file_content(stack, project):
    """Контроль самой проверки: без него «провайдер не видел секрет» могло бы значить «лог пуст»."""
    (project / "visible.py").write_text("VISIBLE_MARKER_55\n", encoding="utf-8")
    delegate(stack, project, f"[[TOOL Read file_path={{{project}/visible.py}}]]")
    assert provider_saw(stack, "VISIBLE_MARKER_55")


# ---------------------------------------------------------------- граница проекта

def test_cannot_write_outside_project(stack, project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "x.txt"
    delegate(stack, project, f"[[TOOL Write file_path={{{outside}}} content={{x}}]]")
    assert not outside.exists()


def test_cannot_read_outside_project(stack, project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text("OUTSIDE_VALUE_77\n", encoding="utf-8")
    delegate(stack, project, f"[[TOOL Read file_path={{{outside}}}]]")
    assert not provider_saw(stack, "OUTSIDE_VALUE_77")


def test_cannot_grep_outside_project(stack, project, tmp_path_factory):
    folder = tmp_path_factory.mktemp("outside")
    (folder / "s.txt").write_text("OUTSIDE_VALUE_78\n", encoding="utf-8")
    delegate(stack, project, f"[[TOOL Grep pattern={{OUTSIDE_VALUE}} path={{{folder}}} output_mode={{content}}]]")
    assert not provider_saw(stack, "OUTSIDE_VALUE_78")


# ---------------------------------------------------------------- секреты

@pytest.mark.parametrize("name,value", [(".env", "hunter2"), ("sub/.env.local", "hunter3"), ("server.pem", "hunter4")])
def test_secret_files_never_reach_provider(stack, project, name, value):
    delegate(stack, project, f"[[TOOL Read file_path={{{project}/{name}}}]]")
    assert not provider_saw(stack, value)


# ---------------------------------------------------------------- команды

def test_no_shell_by_default(stack, project):
    delegate(stack, project, "[[TOOL Bash command={echo PWNED > pwned.txt} description={t}]]")
    assert not (project / "pwned.txt").exists()
    assert "Bash" not in last_tools(stack)


def test_shell_flag_runs_commands(stack, project):
    delegate(stack, project, "[[TOOL Bash command={echo OK > shell.txt} description={t}]]", "--shell")
    assert (project / "shell.txt").read_text(encoding="utf-8").strip() == "OK"


@pytest.mark.parametrize("command", ["cat .env", "curl -s https://example.com", "git push origin main", "sudo id"])
def test_shell_flag_keeps_deny_rules(stack, project, command):
    out = delegate(stack, project, f"[[TOOL Bash command={{{command}}} description={{t}}]]", "--shell")
    assert "denied" in out
    assert not provider_saw(stack, "hunter2")


# ---------------------------------------------------------------- скилл /free

def test_free_skill_runs_worker_without_prompt(stack, project):
    """Настоящая цепочка: /free → разрешённый скиллом Bash → вложенный исполнитель → файл."""
    env = dict(stack["env"], NEUROGATE_PORT=str(stack["port"]), PATH=f"{BIN}{os.pathsep}{stack['env']['PATH']}")
    subprocess.run([str(NEUROGATE), "connect", "claude-skill"], env=env, cwd=stack["tmp"], check=True,
                   capture_output=True)
    (project / ".neurogate-task.md").write_text(
        f"[[TOOL Write file_path={{{project}/from_worker.py}} content={{print(42)}}]]\n", encoding="utf-8")
    base = f"http://127.0.0.1:{stack['port']}"
    outer = dict(env, ANTHROPIC_BASE_URL=base, ANTHROPIC_AUTH_TOKEN="neurogate-local", ANTHROPIC_MODEL="code",
                 ANTHROPIC_DEFAULT_HAIKU_MODEL="code_fast", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    subprocess.run(
        ["claude", "-p", "/free [[TOOL Bash command={neurogate delegate --file .neurogate-task.md} description={t}]]",
         "--output-format", "text"],
        env=outer, cwd=project, capture_output=True, text=True, timeout=TIMEOUT * 2, stdin=subprocess.DEVNULL)
    assert (project / "from_worker.py").read_text(encoding="utf-8") == "print(42)"
