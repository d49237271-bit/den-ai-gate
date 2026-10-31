import re

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from neurogate.keybot import Store
from neurogate.keydrop import parse_code, unseal
from neurogate.websetup import setup_router


@pytest.fixture
def setup(tmp_path):
    store = Store(str(tmp_path / "keys.db"), Fernet.generate_key().decode())
    app = FastAPI()
    app.include_router(setup_router(store, "https://neurogate.nurtech.dev",
                                   lambda s, k: (None if k == "unknown" else k == "valid", "")))
    client = TestClient(app)
    services = client.get("/setup/services").json()["services"]
    return client, store, services


def payload(services, **changes):
    data = {"id": services[0]["id"], "os": "mac", "key": "valid",
            "extra": ["test-extra" for _ in services[0]["extra"]]}
    return data | changes


@pytest.mark.parametrize("system,installer", [("mac", "install.sh"), ("win", "install.ps1")])
def test_browser_to_encrypted_single_use_drop(setup, system, installer):
    c, store, services = setup
    r = c.post("/setup/create", json=payload(services, os=system),
               headers={"Origin": "https://neurogate.nurtech.dev", "Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    result = r.json()
    assert installer in result["command"] and "valid" not in result["command"]
    code = re.search(r"NG-[A-Za-z0-9_-]+", result["command"]).group()
    drop_id, secret = parse_code(code)
    blob = store.take_drop(drop_id)
    assert "valid" not in blob
    assert "valid" in unseal(secret, blob).values()
    assert store.take_drop(drop_id) is None
    assert store.db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_catalog_and_page_contain_no_secrets(setup):
    c, _, services = setup
    assert services and all("env" not in s and "has_key" not in s for s in services)
    assert all(isinstance(p, str) for s in services for p in s["extra"])
    r = c.get("/start")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("changes", [{"os": "linux"}, {"key": []}, {"key": ""},
    {"key": "a" * 4097}, {"key": "abc\ndef"}, {"id": "absent"}, {"extra": [123]},
    {"extra": "bad"}, {"os": {"bad": 1}}])
def test_invalid_fields_do_not_store_drop(setup, changes):
    c, store, services = setup
    r = c.post("/setup/create", json=payload(services, **changes))
    assert r.status_code == 400 and r.headers["cache-control"] == "no-store"
    assert store.db.execute("SELECT count(*) FROM drops").fetchone()[0] == 0


def test_invalid_key_unknown_verification_and_request_limits(setup):
    c, store, services = setup
    assert c.post("/setup/create", json=payload(services, key="bad")).status_code == 400
    assert store.db.execute("SELECT count(*) FROM drops").fetchone()[0] == 0
    r = c.post("/setup/create", json=payload(services, key="unknown"))
    assert r.status_code == 200 and "не подтверждена" in r.json()["message"]
    for headers in [{"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}]:
        r = c.post("/setup/create", json=payload(services), headers=headers)
        assert r.status_code == 403 and r.headers["cache-control"] == "no-store"
    assert c.post("/setup/create", content=b"bad").status_code == 415
    for body, status in [(b"[]", 400), (b"{", 400), (b"x" * 16385, 413)]:
        r = c.post("/setup/create", content=body, headers={"Content-Type": "application/json"})
        assert r.status_code == status and r.headers["cache-control"] == "no-store"


def test_rate_limit(setup):
    c, _, services = setup
    for _ in range(10):
        assert c.post("/setup/create", json=payload(services, key="bad")).status_code == 400
    r = c.post("/setup/create", json=payload(services))
    assert r.status_code == 429 and r.headers["cache-control"] == "no-store"
