"""Telegram slash-command menu (setMyCommands) with admin scopes."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
)

from src.config import Settings

logger = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Старт и доступ"),
    BotCommand(command="help", description="Справка"),
    BotCommand(command="limit", description="Остаток запросов на сегодня"),
]

ADMIN_ONLY_COMMANDS = [
    BotCommand(command="invite", description="Создать ссылку-приглашение"),
    BotCommand(command="invites", description="Список приглашений"),
    BotCommand(command="users", description="Список пользователей"),
    BotCommand(command="user", description="Карточка / block / unblock"),
    BotCommand(command="stats", description="Статистика today|week|month"),
    BotCommand(command="report", description="Сводка daily|weekly"),
    BotCommand(command="userstats", description="Статистика по пользователю"),
    BotCommand(command="reindex", description="Переиндексация базы знаний"),
]

ADMIN_COMMANDS = [*USER_COMMANDS, *ADMIN_ONLY_COMMANDS]


async def setup_bot_commands(bot: Bot, settings: Settings) -> None:
    """Register slash suggestions: public for all, full list for each admin."""
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
    logger.info("Registered %s default bot commands", len(USER_COMMANDS))

    for admin_id in settings.admin_user_ids:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
            logger.info("Registered admin commands for user %s", admin_id)
        except Exception:
            logger.exception(
                "Failed to set admin commands for %s "
                "(admin must open a private chat with the bot at least once)",
                admin_id,
            )
