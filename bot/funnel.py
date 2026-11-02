"""Воронка в SQLite: откуда пришёл человек и докуда дошёл. Имён и текстов сообщений не храним."""

from __future__ import annotations

import html
import time

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, source TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events (user_id INTEGER NOT NULL, name TEXT NOT NULL, ts REAL NOT NULL,
                                   PRIMARY KEY (user_id, name));
"""


class Funnel:
    def __init__(self, path: str):
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self.db = await aiosqlite.connect(self.path)
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def close(self) -> None:
        if self.db:
            await self.db.close()

    async def touch(self, user_id: int, source: str) -> None:
        """Источник считаем по первому касанию: повторный /start его не меняет."""
        await self.db.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (user_id, source[:64], time.time()))
        await self.db.commit()

    async def mark(self, user_id: int, name: str) -> None:
        await self.db.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?)", (user_id, name, time.time()))
        await self.db.commit()

    async def _count(self, name: str) -> int:
        async with self.db.execute("SELECT COUNT(*) FROM events WHERE name = ?", (name,)) as cur:
            return (await cur.fetchone())[0]

    async def stats(self) -> dict:
        async with self.db.execute("SELECT COUNT(*) FROM users") as cur:
            start = (await cur.fetchone())[0]
        async with self.db.execute(
            "SELECT source, COUNT(*) FROM users GROUP BY source ORDER BY COUNT(*) DESC LIMIT 15"
        ) as cur:
            sources = [(html.escape(name), count) for name, count in await cur.fetchall()]
        by_os = {name: await self._count(f"os:{name}") for name in ("mac", "win", "linux")}
        return {
            "start": start,
            "subscribed": await self._count("subscribed"),
            "command": sum(by_os.values()),
            "os": by_os,
            "installed": await self._count("installed"),
            "sources": sources,
        }
