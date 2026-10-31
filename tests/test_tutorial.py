from fastapi import FastAPI
from fastapi.testclient import TestClient

from neurogate.tutorial import router


def test_video_stream_ranges_and_missing_assets(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_MEDIA_DIR", str(tmp_path))
    (tmp_path / "neurogate-tutorial.mp4").write_bytes(b"video-content")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    head = client.head("/media/neurogate-tutorial.mp4")
    assert head.status_code == 200
    assert head.headers["content-type"] == "video/mp4"
    assert head.headers["accept-ranges"] == "bytes"
    assert head.content == b""
    part = client.get("/media/neurogate-tutorial.mp4", headers={"Range": "bytes=0-4"})
    assert part.status_code == 206
    assert part.content == b"video"
    assert part.headers["content-range"] == "bytes 0-4/13"
    assert client.get("/media/neurogate-tutorial.mp4", headers={"Range": "bytes=99-"}).status_code == 416
    assert client.get("/media/neurogate-tutorial.jpg").status_code == 404
    assert client.get("/media/keybot.db").status_code == 404
