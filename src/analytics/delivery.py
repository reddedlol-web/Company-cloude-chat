"""Deliver analytics reports via Telegram."""

import logging

from aiogram import Bot

from src.config import Settings

logger = logging.getLogger(__name__)


async def deliver_report(
    bot: Bot,
    settings: Settings,
    messages: list[str],
    *,
    admin_chat_id: int | None = None,
) -> None:
    chat_ids: list[int] = []

    if settings.analytics_report_chat_id:
        chat_ids.append(settings.analytics_report_chat_id)
    elif settings.admin_notify_chat_id:
        chat_ids.append(settings.admin_notify_chat_id)
    else:
        chat_ids.extend(settings.admin_user_ids)

    if admin_chat_id and admin_chat_id not in chat_ids:
        chat_ids.insert(0, admin_chat_id)

    for chat_id in chat_ids:
        for msg in messages:
            try:
                await bot.send_message(chat_id, msg)
            except Exception:
                logger.exception("Failed to send report to chat %s", chat_id)
