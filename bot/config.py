"""Настройки бота из переменных окружения (файл .env подключает systemd)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_REPO = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")


def _words(raw: str) -> frozenset[str]:
    return frozenset(w.strip().casefold().lstrip("@") for w in raw.split(",") if w.strip())


@dataclass(frozen=True)
class Settings:
    token: str
    repo: str
    channel: str = "@den_ai_dev"
    branch: str = "stable"
    admins: frozenset[str] = frozenset({"denis_volchek"})
    code_words: frozenset[str] = frozenset({"шлюз"})
    db_path: str = "bot.db"

    def __post_init__(self) -> None:
        # Без настоящего репозитория бот раздавал бы подписчикам нерабочую команду
        if not _REPO.match(self.repo):
            raise ValueError(f"GITHUB_REPO должен быть вида owner/name, сейчас: {self.repo!r}")

    @property
    def raw_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}"

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.repo}"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            token=env["BOT_TOKEN"],
            repo=env["GITHUB_REPO"],
            channel=env.get("CHANNEL", cls.channel),
            branch=env.get("GITHUB_BRANCH", cls.branch),
            admins=_words(env["ADMINS"]) if env.get("ADMINS") else cls.admins,
            code_words=_words(env["CODE_WORDS"]) if env.get("CODE_WORDS") else cls.code_words,
            db_path=env.get("DB_PATH", cls.db_path),
        )
