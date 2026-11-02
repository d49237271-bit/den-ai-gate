"""Сквозные проверки бота: настоящий Dispatcher aiogram, фальшивый только транспорт к Telegram."""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.exceptions import ClientDecodeError, TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, GetChatMember, SendMessage
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberRestricted,
    Message,
    Update,
    User,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import texts  # noqa: E402
from config import Settings  # noqa: E402
from funnel import Funnel  # noqa: E402
from handlers import router  # noqa: E402

NOW = dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc)
DP = Dispatcher()  # роутер подключается к диспетчеру один раз, настройки передаём в каждое обновление
DP.include_router(router)
USER = User(id=7, is_bot=False, first_name="Подписчик", username="reader")
ADMIN = User(id=8, is_bot=False, first_name="Ден", username="Denis_Volchek")
CHAT = Chat(id=7, type="private")


class FakeTelegram(BaseSession):
    """Запоминает вызовы API и отвечает как Telegram."""

    def __init__(self):
        super().__init__()
        self.sent: list[SendMessage] = []
        self.alerts: list[AnswerCallbackQuery] = []
        self.status = "member"
        self.member_error = False

    async def make_request(self, bot, method, timeout=None):
        if isinstance(method, GetChatMember):
            if isinstance(self.member_error, Exception):
                raise self.member_error
            if self.member_error:
                raise TelegramBadRequest(method=method, message="member list is inaccessible")
            user = User(id=method.user_id, is_bot=False, first_name="x")
            if self.status == "left":
                return ChatMemberLeft(user=user)
            if self.status == "restricted-out":
                # У этого типа два десятка флагов прав, тесту важен только is_member
                return ChatMemberRestricted.model_construct(user=user, is_member=False, status="restricted")
            return ChatMemberMember(user=user)
        if isinstance(method, SendMessage):
            self.sent.append(method)
            return Message(message_id=len(self.sent), date=NOW, chat=CHAT, text=method.text)
        if isinstance(method, AnswerCallbackQuery):
            self.alerts.append(method)
            return True
        if isinstance(method, EditMessageReplyMarkup):
            return True
        raise AssertionError(f"неожиданный вызов {type(method).__name__}")

    async def close(self):
        pass

    async def stream_content(self, *a, **k):
        yield b""


class Stand:
    def __init__(self, tmp_path):
        self.settings = Settings(token="42:TEST", repo="owner/den-ai-gate", db_path=str(tmp_path / "gate.db"))
        self.tg = FakeTelegram()
        self.bot = Bot(self.settings.token, session=self.tg, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.funnel = Funnel(self.settings.db_path)
        self._id = 0

    async def text(self, text: str, user: User = USER) -> None:
        self._id += 1
        msg = Message(message_id=self._id, date=NOW, chat=Chat(id=user.id, type="private"), from_user=user, text=text)
        await self._feed(Update(update_id=self._id, message=msg))

    async def press(self, data: str, user: User = USER) -> None:
        self._id += 1
        msg = Message(message_id=self._id, date=NOW, chat=CHAT, from_user=user, text="кнопки")
        cq = CallbackQuery(id=str(self._id), from_user=user, chat_instance="1", data=data, message=msg)
        await self._feed(Update(update_id=self._id, callback_query=cq))

    async def _feed(self, update: Update) -> None:
        await DP.feed_update(self.bot, update, settings=self.settings, funnel=self.funnel)

    def last(self) -> str:
        return self.tg.sent[-1].text

    def buttons(self) -> list[str]:
        markup = self.tg.sent[-1].reply_markup
        return [b.callback_data or b.url for row in markup.inline_keyboard for b in row]


@pytest.fixture
async def stand(tmp_path):
    s = Stand(tmp_path)
    await s.funnel.open()
    yield s
    await s.funnel.close()


# ---------------------------------------------------------------- подписка

async def test_subscriber_goes_straight_to_os_choice(stand):
    await stand.text("/start")
    assert "Шлюз Ден.AI" in stand.tg.sent[0].text
    assert stand.buttons() == ["os:mac", "os:win", "os:linux"]


async def test_stranger_sees_gate_not_command(stand):
    stand.tg.status = "left"
    await stand.text("/start")
    assert "@den_ai_dev" in stand.last()
    assert "check" in stand.buttons()
    assert not any("install." in m.text for m in stand.tg.sent)


async def test_check_button_keeps_gate_until_subscribed(stand):
    stand.tg.status = "left"
    await stand.text("/start")
    await stand.press("check")
    assert stand.tg.alerts[-1].show_alert is True
    stand.tg.status = "member"
    await stand.press("check")
    assert stand.buttons() == ["os:mac", "os:win", "os:linux"]


async def test_restricted_non_member_is_not_subscribed(stand):
    stand.tg.status = "restricted-out"
    await stand.text("/start")
    assert "check" in stand.buttons()


async def test_telegram_failure_does_not_lock_people_out(stand):
    stand.tg.member_error = True
    await stand.text("/start")
    assert stand.buttons() == ["os:mac", "os:win", "os:linux"]


async def test_unparsable_telegram_reply_does_not_lock_people_out(stand):
    """Telegram добавил поле раньше, чем aiogram его понял: это ClientDecodeError, а не ошибка API."""
    stand.tg.member_error = ClientDecodeError("новый формат", ValueError("x"), {})
    await stand.text("/start")
    assert stand.buttons() == ["os:mac", "os:win", "os:linux"]


# ---------------------------------------------------------------- команда установки

@pytest.mark.parametrize("os_name,tail", [("mac", "install.sh | bash"), ("linux", "install.sh | bash"),
                                          ("win", "install.ps1 | iex")])
async def test_command_matches_os_and_repo(stand, os_name, tail):
    await stand.press(f"os:{os_name}")
    text = stand.last()
    assert f"https://raw.githubusercontent.com/owner/den-ai-gate/stable/{tail}" in text
    assert "<code>" in text


async def test_bot_never_asks_for_a_key_in_chat(stand):
    await stand.press("os:win")
    text = stand.last().casefold()
    assert "бот его не видит" in text
    assert "пришли ключ" not in text and "вставь ключ в чат" not in text


async def test_install_links_to_script_for_review(stand):
    await stand.press("os:win")
    assert "https://github.com/owner/den-ai-gate/blob/stable/install.ps1" in stand.buttons()


async def test_unknown_os_is_ignored(stand):
    await stand.press("os:amiga")
    assert stand.tg.sent == []


async def test_usage_warns_about_data_and_credits_author(stand):
    await stand.press("installed")
    text = stand.last()
    assert "/free" in text and "claude-free" in text
    assert "для обучения" in text and "Мансур" in text and "а не Claude" in text


# ---------------------------------------------------------------- тексты

@pytest.mark.parametrize("text", [
    texts.INTRO, texts.HELP, texts.UPDATE, texts.REMOVE, texts.USAGE, texts.CHOOSE_OS,
])
def test_html_tags_are_balanced(text):
    for tag in ("b", "code", "i"):
        assert len(re.findall(f"<{tag}>", text)) == len(re.findall(f"</{tag}>", text)), tag
    assert len(text) <= 4096, "лимит сообщения Telegram"


def test_install_text_fits_one_message():
    s = Settings(token="1:x", repo="owner/den-ai-gate")
    assert all(len(texts.install(o, s)) <= 4096 for o in ("mac", "win", "linux"))


@pytest.mark.parametrize("text", [
    texts.INTRO, texts.HELP, texts.UPDATE, texts.REMOVE, texts.USAGE,
    texts.install("win", Settings(token="1:x", repo="owner/den-ai-gate")),
])
def test_telegram_can_parse_html(text):
    """Лишний < или & — и Telegram отвергнет сообщение целиком."""
    assert {tag for _, tag in re.findall(r"<(/?)(\w+)", text)} <= {"b", "code", "i"}
    assert "&" not in re.sub(r"&(lt|gt|amp);", "", text)
    assert "<" not in re.sub(r"</?(b|code|i)>", "", text)


def test_placeholder_repo_is_rejected_at_start():
    with pytest.raises(ValueError):
        Settings(token="1:x", repo="__GITHUB" + "_OWNER__/den-ai-gate")


# ---------------------------------------------------------------- прочие команды

@pytest.mark.parametrize("command,needle", [("/help", "neurogate doctor"), ("/update", "neurogate update"),
                                            ("/remove", "Unregister-ScheduledTask")])
async def test_service_commands(stand, command, needle):
    await stand.text(command)
    assert needle in stand.last()


async def test_code_word_opens_flow_any_case(stand):
    await stand.text("  ШЛЮЗ ")
    assert stand.buttons() == ["os:mac", "os:win", "os:linux"]
    stats = await stand.funnel.stats()
    assert stats["sources"] == [("шлюз", 1)]


async def test_random_text_gets_hint(stand):
    await stand.text("привет")
    assert "/start" in stand.last()


# ---------------------------------------------------------------- воронка

async def test_deep_link_source_is_first_touch(stand):
    await stand.text("/start reel12")
    await stand.text("/start reel99")
    assert (await stand.funnel.stats())["sources"] == [("reel12", 1)]


async def test_funnel_counts_each_person_once(stand):
    await stand.text("/start")
    await stand.text("/start")
    await stand.press("os:win")
    await stand.press("os:win")
    await stand.press("installed")
    s = await stand.funnel.stats()
    assert (s["start"], s["subscribed"], s["command"], s["os"]["win"], s["installed"]) == (1, 1, 1, 1, 1)


async def test_stats_only_for_admin_username_any_case(stand):
    await stand.text("/stats")
    assert "Воронка" not in stand.last()
    await stand.text("/stats", user=ADMIN)
    assert "Воронка" in stand.last()


async def test_source_is_escaped_in_stats(stand):
    await stand.text("/start <b>x")
    await stand.text("/stats", user=ADMIN)
    assert "<b>x" not in stand.last() and "&lt;b&gt;x" in stand.last()
