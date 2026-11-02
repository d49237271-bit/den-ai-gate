"""Запуск бота. Long polling: на сервере не нужны домен, nginx и открытые порты."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import AiogramError
from aiogram.types import BotCommand, LinkPreviewOptions

from config import Settings
from funnel import Funnel
from handlers import log, router


async def warn_if_not_admin(bot: Bot, settings: Settings) -> None:
    """Telegram показывает подписчиков канала только его админам."""
    try:
        me = await bot.me()
        member = await bot.get_chat_member(settings.channel, me.id)
    except AiogramError as exc:
        log.error("Нет доступа к каналу %s: %s. Добавь бота в админы канала.", settings.channel, exc)
        return
    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        log.error("Бот не админ в канале %s: подписка не проверяется.", settings.channel)


def build_dispatcher(settings: Settings, funnel: Funnel) -> Dispatcher:
    dp = Dispatcher(settings=settings, funnel=funnel)
    dp.include_router(router)
    return dp


async def run() -> None:
    settings = Settings.from_env()
    funnel = Funnel(settings.db_path)
    await funnel.open()
    bot = Bot(settings.token, default=DefaultBotProperties(
        parse_mode=ParseMode.HTML, link_preview=LinkPreviewOptions(is_disabled=True)))
    dp = build_dispatcher(settings, funnel)
    await warn_if_not_admin(bot, settings)
    await bot.delete_webhook()
    await bot.set_my_commands([
        BotCommand(command="start", description="Получить команду установки"),
        BotCommand(command="help", description="Что делать, если не работает"),
        BotCommand(command="update", description="Обновить шлюз"),
        BotCommand(command="remove", description="Удалить шлюз"),
    ])
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await funnel.close()
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
