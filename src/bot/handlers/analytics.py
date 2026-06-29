"""Admin analytics bot commands."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.analytics.reporter import AnalyticsReporter
from src.config import Settings
from src.db.repository import Repository
from src.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

ADMIN_DENY = "⛔ Команда доступна только администраторам."


def create_analytics_router(
    settings: Settings,
    repository: Repository,
    llm: OpenRouterClient,
) -> Router:
    router = Router(name="analytics")
    reporter = AnalyticsReporter(settings, repository, llm)

    def _is_admin(message: Message) -> bool:
        return settings.is_admin(message.from_user.id)

    def _parse_args(message: Message) -> list[str]:
        text = message.text or ""
        parts = text.split()
        return [p.lower() for p in parts[1:]] if len(parts) > 1 else []

    @router.message(Command("stats"))
    async def cmd_stats(message: Message) -> None:
        if not _is_admin(message):
            await message.answer(ADMIN_DENY)
            return
        args = _parse_args(message)
        period = args[0] if args else "today"
        if period not in {"today", "week", "month"}:
            await message.answer("Использование: /stats [today|week|month]")
            return
        await message.answer(reporter.format_stats_message(period))

    @router.message(Command("report"))
    async def cmd_report(message: Message) -> None:
        if not _is_admin(message):
            await message.answer(ADMIN_DENY)
            return
        args = _parse_args(message)
        period = "daily"
        numeric_only = False
        force = False
        for arg in args:
            if arg in {"daily", "weekly", "week"}:
                period = "weekly" if arg in {"weekly", "week"} else "daily"
            elif arg == "--numeric":
                numeric_only = True
            elif arg == "--force":
                force = True

        result = await reporter.generate_report(
            period, numeric_only=numeric_only, force=force
        )
        for msg in result.messages:
            await message.answer(msg)
        if result.report_id and not result.messages[0].startswith("ℹ️"):
            repository.mark_report_sent(result.report_id)

    @router.message(Command("userstats"))
    async def cmd_userstats(message: Message) -> None:
        if not _is_admin(message):
            await message.answer(ADMIN_DENY)
            return
        args = _parse_args(message)
        if not args or not args[0].lstrip("-").isdigit():
            await message.answer("Укажите числовой Telegram ID: /userstats 123456789")
            return
        user_id = int(args[0])
        period = args[1] if len(args) > 1 and args[1] in {"today", "week", "month"} else "week"
        await message.answer(reporter.format_userstats_message(user_id, period))

    return router
