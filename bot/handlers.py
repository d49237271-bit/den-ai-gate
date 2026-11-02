"""Логика бота: подписка → компьютер → команда установки → как пользоваться.

Ключи бот не принимает. Человек вводит их в своём терминале, поэтому они не попадают
ни в историю Telegram, ни на сервер бота.
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import AiogramError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import texts
from config import Settings
from funnel import Funnel

log = logging.getLogger("den-ai-gate-bot")

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

OS_NAMES = ("mac", "win", "linux")
_MEMBER = {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER}


async def is_subscribed(bot: Bot, channel: str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(channel, user_id)
    except AiogramError:
        # Команда установки и так открыта на GitHub: сбой проверки не должен закрывать людям доступ
        log.exception("Подписку проверить не удалось: бот админ в канале %s?", channel)
        return True
    if member.status == ChatMemberStatus.RESTRICTED:
        return member.is_member
    return member.status in _MEMBER


def _gate_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Открыть канал", url=texts.channel_url(settings))],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check")],
    ])


def _os_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🍏 Mac", callback_data="os:mac"),
        InlineKeyboardButton(text="🪟 Windows", callback_data="os:win"),
        InlineKeyboardButton(text="🐧 Linux", callback_data="os:linux"),
    ]])


def _install_keyboard(os_name: str, settings: Settings) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Установил", callback_data="installed"),
         InlineKeyboardButton(text="🛟 Не работает", callback_data="help")],
        [InlineKeyboardButton(text="📄 Посмотреть скрипт установки", url=texts.script_url(os_name, settings))],
    ])


async def _open_flow(message: Message, bot: Bot, settings: Settings, funnel: Funnel, source: str) -> None:
    user_id = message.from_user.id
    await funnel.touch(user_id, source)
    await message.answer(texts.INTRO)
    if await is_subscribed(bot, settings.channel, user_id):
        await funnel.mark(user_id, "subscribed")
        await message.answer(texts.CHOOSE_OS, reply_markup=_os_keyboard())
    else:
        await message.answer(texts.gate(settings), reply_markup=_gate_keyboard(settings))


@router.message(CommandStart())
async def on_start(message: Message, command: CommandObject, bot: Bot, settings: Settings, funnel: Funnel) -> None:
    await _open_flow(message, bot, settings, funnel, source=command.args or "direct")


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("update"))
async def on_update(message: Message) -> None:
    await message.answer(texts.UPDATE)


@router.message(Command("remove"))
async def on_remove(message: Message) -> None:
    await message.answer(texts.REMOVE)


@router.message(Command("stats"))
async def on_stats(message: Message, settings: Settings, funnel: Funnel) -> None:
    username = (message.from_user.username or "").casefold()
    if username in settings.admins:
        await message.answer(texts.stats(await funnel.stats()))
    else:
        await message.answer(texts.UNKNOWN)


@router.message(F.text)
async def on_text(message: Message, bot: Bot, settings: Settings, funnel: Funnel) -> None:
    word = message.text.strip().casefold()
    if word in settings.code_words:
        await _open_flow(message, bot, settings, funnel, source=word)
    else:
        await message.answer(texts.UNKNOWN)


@router.callback_query(F.data == "check")
async def on_check(callback: CallbackQuery, bot: Bot, settings: Settings, funnel: Funnel) -> None:
    if not await is_subscribed(bot, settings.channel, callback.from_user.id):
        await callback.answer(texts.NOT_SUBSCRIBED, show_alert=True)
        return
    await funnel.mark(callback.from_user.id, "subscribed")
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts.CHOOSE_OS, reply_markup=_os_keyboard())


@router.callback_query(F.data.startswith("os:"))
async def on_os(callback: CallbackQuery, settings: Settings, funnel: Funnel) -> None:
    os_name = callback.data.removeprefix("os:")
    if os_name not in OS_NAMES:
        await callback.answer()
        return
    await funnel.mark(callback.from_user.id, f"os:{os_name}")
    await callback.answer()
    await callback.message.answer(texts.install(os_name, settings),
                                  reply_markup=_install_keyboard(os_name, settings))


@router.callback_query(F.data == "installed")
async def on_installed(callback: CallbackQuery, funnel: Funnel) -> None:
    await funnel.mark(callback.from_user.id, "installed")
    await callback.answer()
    await callback.message.answer(texts.USAGE)


@router.callback_query(F.data == "help")
async def on_help_button(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(texts.HELP)
