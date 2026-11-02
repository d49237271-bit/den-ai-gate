"""Что добавил форк Ден.AI: границы исполнителя, скилл /free, обновление, защита от чужих сайтов."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import FakeResponse
from neurogate import cli, main


class Done:
    returncode = 0
    stdout = ""


@pytest.fixture
def worker(home, tmp_path, monkeypatch):
    """Проект, живой шлюз, перехваченный subprocess. Возвращает список вызовов."""
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setenv("NEUROGATE_CALLER_DIR", str(proj))
    monkeypatch.setattr(cli, "_gateway_alive", lambda base: True)
    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)) or Done())
    return calls


@pytest.fixture
def claude_installed(home, monkeypatch):
    claude = home / ".local/bin/claude"
    claude.parent.mkdir(parents=True, exist_ok=True)
    claude.write_text("#!/bin/sh\n")
    monkeypatch.setattr(cli.shutil, "which", lambda name: str(claude) if name == "claude" else None)
    return claude


def after(cmd, flag):
    """Значения variadic-флага до следующего --флага."""
    i = cmd.index(flag) + 1
    out = []
    while i < len(cmd) and not cmd[i].startswith("--"):
        out.append(cmd[i])
        i += 1
    return out


# ---------------------------------------------------------------- исполнитель

def test_claude_is_default_worker_when_both_installed(worker, claude_installed, monkeypatch):
    monkeypatch.setattr(cli, "_opencode_cli", lambda prefer_app=False: "/bin/opencode")
    cli.main(["delegate", "задача"])
    assert worker[0][0][0] == str(claude_installed)


def test_opencode_only_on_request(worker, claude_installed, monkeypatch):
    monkeypatch.setattr(cli, "_opencode_cli", lambda prefer_app=False: "/bin/opencode")
    cli.main(["delegate", "--worker", "opencode", "задача"])
    assert worker[0][0][0] == "/bin/opencode"


def test_claude_worker_has_no_shell_by_default(worker, claude_installed):
    cli.main(["delegate", "задача"])
    cmd = worker[0][0]
    assert cmd[cmd.index("--tools") + 1] == "Read,Edit,Write,Glob,Grep"
    assert "--allowedTools" not in cmd


def test_claude_worker_keeps_project_boundary(worker, claude_installed):
    """Явный allow для Read/Write открыл бы весь диск: граница держится на acceptEdits и cwd."""
    cli.main(["delegate", "задача"])
    cmd, kw = worker[0]
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert "--allowedTools" not in cmd
    assert kw["cwd"].name == "proj"


def test_claude_worker_never_sees_secrets_or_mcp(worker, claude_installed):
    cli.main(["delegate", "задача"])
    cmd = worker[0][0]
    denied = after(cmd, "--disallowedTools")
    assert "Read(./.env)" in denied and "Read(./**/.env)" in denied and "Read(./**/*.pem)" in denied
    assert "--strict-mcp-config" in cmd


def test_shell_flag_allows_bash_but_blocks_sending_out(worker, claude_installed, capsys):
    cli.main(["delegate", "--shell", "задача"])
    cmd = worker[0][0]
    assert cmd[cmd.index("--tools") + 1].endswith(",Bash")
    assert after(cmd, "--allowedTools") == ["Bash"]
    denied = after(cmd, "--disallowedTools")
    for rule in ("Bash(curl *)", "Bash(git push *)", "Bash(*.env*)", "Bash(sudo *)"):
        assert rule in denied
    assert "без подтверждения" in capsys.readouterr().out


def test_opencode_worker_is_edit_only_by_default(worker, monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    monkeypatch.setattr(cli, "_opencode_cli", lambda prefer_app=False: "/bin/opencode")
    cli.main(["delegate", "задача"])
    perm = json.loads(worker[0][1]["env"]["OPENCODE_PERMISSION"])
    assert perm["bash"] == "deny" and perm["webfetch"] == "deny" and perm["external_directory"] == "deny"
    assert perm["read"]["*.env"] == "deny" and perm["read"]["*.env.example"] == "allow"


def test_opencode_shell_keeps_secret_rules(worker, monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    monkeypatch.setattr(cli, "_opencode_cli", lambda prefer_app=False: "/bin/opencode")
    cli.main(["delegate", "--shell", "задача"])
    perm = json.loads(worker[0][1]["env"]["OPENCODE_PERMISSION"])
    assert perm["bash"]["*"] == "allow" and perm["bash"]["git push*"] == "deny" and perm["bash"]["*.env*"] == "deny"


def test_worker_prompt_is_ascii_for_windows_cmd_shim():
    """claude.cmd пропускает аргументы через cmd.exe: кириллица там ломается."""
    assert cli.WORKER_PROMPT_NO_SHELL.isascii() and cli.WORKER_PROMPT_SHELL.isascii()


# ---------------------------------------------------------------- скилл /free

def test_skill_written_to_personal_skills(home):
    assert cli.main(["connect", "claude-skill"]) == 0
    text = (home / ".claude/skills/free/SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: free\n")
    assert "disable-model-invocation: true" in text, "только по команде /free"
    assert "$ARGUMENTS" in text


def test_skill_preapproves_only_gateway_commands():
    head = cli.CLAUDE_SKILL.split("---")[1]
    line = next(ln for ln in head.splitlines() if ln.startswith("allowed-tools:"))
    assert "Bash(neurogate delegate *)" in line
    assert "Bash(*" not in line and "Edit" not in line and "Write" not in line


def test_doctor_reports_missing_skill(home, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_gateway_alive", lambda base: False)
    cli.main(["doctor"])
    assert "neurogate connect claude-skill" in capsys.readouterr().out
    cli.main(["connect", "claude-skill"])
    capsys.readouterr()
    cli.main(["doctor"])
    assert "Скилл /free установлен" in capsys.readouterr().out


# ---------------------------------------------------------------- список моделей

@pytest.fixture
def install_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("config.yaml.example").write_text("v1\n", encoding="utf-8")
    return tmp_path


def refresh():
    return cli.main(["refresh-config"])


def test_first_install_creates_config(install_dir):
    assert refresh() == 0
    assert Path("config.yaml").read_text(encoding="utf-8") == "v1\n"


def test_untouched_config_gets_new_models(install_dir, capsys):
    refresh()
    Path("config.yaml.example").write_text("v2\n", encoding="utf-8")
    refresh()
    assert Path("config.yaml").read_text(encoding="utf-8") == "v2\n"
    assert "обновлён" in capsys.readouterr().out
    assert not Path("config.yaml.new").exists()


def test_hand_edited_config_survives(install_dir, capsys):
    refresh()
    Path("config.yaml").write_text("моя цепочка\n", encoding="utf-8")
    Path("config.yaml.example").write_text("v2\n", encoding="utf-8")
    refresh()
    assert Path("config.yaml").read_text(encoding="utf-8") == "моя цепочка\n"
    assert Path("config.yaml.new").read_text(encoding="utf-8") == "v2\n"
    assert "не трогаю" in capsys.readouterr().out


def test_update_on_posix_runs_installer_from_install_dir(home, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.os, "name", "posix")
    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or Done())
    assert cli.main(["update"]) == 0
    assert calls == [["bash", str(tmp_path / "install.sh")]]


def test_update_on_windows_reads_installer_as_utf8(tmp_path, monkeypatch):
    """-File в PowerShell 5.1 читает файл без BOM как ANSI: байт 0x94 из «—» становится кавычкой."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.os, "name", "nt")
    seen = {}

    class Proc:
        def __init__(self, cmd, **kw):
            seen.update(cmd=cmd, kw=kw)

    monkeypatch.setattr(cli.subprocess, "Popen", Proc)
    assert cli.cmd_update(None) == 0
    assert "-File" not in seen["cmd"]
    assert "-Encoding UTF8" in seen["cmd"][-1]


# ---------------------------------------------------------------- ключ и страна

def test_geo_block_does_not_reject_good_key(monkeypatch):
    body = '{"error":{"code":400,"message":"User location is not supported for the API use.","status":"FAILED_PRECONDITION"}}'
    monkeypatch.setattr(cli.httpx, "get", lambda *a, **k: FakeResponse(400, text=body))
    service = {"check": {"url": "https://x", "auth": "query", "param": "key"}}
    ok, why = cli.check_key(service, "AIza")
    assert ok is None and "VPN" in why


def test_real_bad_key_is_still_rejected(monkeypatch):
    monkeypatch.setattr(cli.httpx, "get", lambda *a, **k: FakeResponse(400, text='{"error":"API key not valid"}'))
    ok, _ = cli.check_key({"check": {"url": "https://x", "auth": "query"}}, "bad")
    assert ok is False


# ---------------------------------------------------------------- чужие сайты

@pytest.mark.parametrize("host,origin,allowed", [
    ("127.0.0.1:8765", None, True),
    ("localhost:8765", "http://localhost:8765", True),
    ("127.0.0.1:8765", "http://127.0.0.1:8765", True),
    ("[::1]:8765", None, True),
    (None, None, True),
    ("127.0.0.1:8765", "vscode-webview://abc", True),
    ("127.0.0.1:8765", "app://opencode", True),
    ("evil.example:8765", "http://evil.example:8765", False),
    ("evil.example:8765", None, False),
    ("127.0.0.1:8765", "https://evil.example", False),
    ("127.0.0.1:8765", "http://127.0.0.1.evil.example", False),
])
def test_browser_guard_rules(host, origin, allowed):
    assert main._browser_allowed(host, origin) is allowed


CONFIG = """
providers:
  - name: fake:coder
    kind: groq
    model: m
    api_key: k
chains:
  chat: [fake:coder]
default_chain: chat
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("NEUROGATE_CONFIG", str(cfg))
    monkeypatch.delenv("NEUROGATE_API_TOKEN", raising=False)
    monkeypatch.delenv("NEUROGATE_HOST", raising=False)
    return TestClient(main.create_app())


def test_dns_rebinding_blocked(client):
    assert client.get("/v1/calls", headers={"Host": "evil.example:8765"}).status_code == 403
    assert client.get("/v1/calls").status_code == 200


def test_foreign_site_cannot_add_key(client):
    r = client.post("/keys/add", headers={"Origin": "https://evil.example"}, json={"id": "groq", "key": "x"})
    assert r.status_code == 403


def test_foreign_site_cannot_spend_quota(client):
    r = client.post("/v1/chat/completions", headers={"Origin": "https://evil.example"},
                    json={"model": "chat", "messages": [{"role": "user", "content": "x"}]})
    assert r.status_code == 403


def test_guard_is_off_on_a_server(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv("NEUROGATE_CONFIG", str(cfg))
    monkeypatch.setenv("NEUROGATE_HOST", "0.0.0.0")
    monkeypatch.delenv("NEUROGATE_API_TOKEN", raising=False)
    c = TestClient(main.create_app())
    assert c.get("/health", headers={"Host": "gate.example.com"}).status_code == 200


# ---------------------------------------------------------------- отказ одного сервиса

@pytest.mark.parametrize("text", [
    "400 FAILED_PRECONDITION. {'error': {'code': 400, 'message': 'User location is not supported for the API use.'}}",
    "401 Unauthorized", "403 Forbidden", "404 No endpoints found for poolside/laguna-s-2.1:free",
])
def test_one_provider_refusal_does_not_stop_chain(text):
    from neurogate.errors import classify
    assert classify(RuntimeError(text)).retryable


def test_bad_request_still_stops_chain():
    from neurogate.errors import ErrorCategory, classify
    assert classify(RuntimeError("400 invalid message format")) is ErrorCategory.OTHER
