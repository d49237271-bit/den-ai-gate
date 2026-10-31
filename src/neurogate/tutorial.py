"""Public tutorial assets, stored in the bot's persistent data volume."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()
_ASSETS = {
    "neurogate-tutorial.mp4": "video/mp4",
    "neurogate-tutorial.jpg": "image/jpeg",
}


@router.api_route("/media/{filename}", methods=["GET", "HEAD"])
async def tutorial_asset(filename: str):
    if filename not in _ASSETS:
        raise HTTPException(404, "Файл не найден")
    path = Path(os.getenv("BOT_MEDIA_DIR", "/data/media")) / filename
    if not path.is_file():
        raise HTTPException(404, "Видео пока недоступно. Попробуйте позже.")
    return FileResponse(path, media_type=_ASSETS[filename], headers={
        "Cache-Control": "public, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    })
