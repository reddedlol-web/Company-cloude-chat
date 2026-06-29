"""Scheduled analytics report jobs."""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.analytics.delivery import deliver_report
from src.analytics.reporter import AnalyticsReporter
from src.config import Settings
from src.db.repository import Repository
from src.llm.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


def create_scheduler(
    settings: Settings,
    repository: Repository,
    bot: Bot,
    llm: OpenRouterClient,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    reporter = AnalyticsReporter(settings, repository, llm)

    async def run_report(period_kind: str) -> None:
        logger.info("Running scheduled %s analytics report", period_kind)
        result = await reporter.generate_report(period_kind)
        if result.messages and not result.messages[0].startswith("ℹ️"):
            await deliver_report(bot, settings, result.messages)
            if result.report_id:
                repository.mark_report_sent(result.report_id)

    async def run_daily() -> None:
        await run_report("daily")

    async def run_weekly() -> None:
        await run_report("weekly")

    if settings.analytics_schedule_enabled:
        scheduler.add_job(
            run_daily,
            CronTrigger.from_crontab(settings.analytics_daily_cron),
            id="analytics_daily",
            replace_existing=True,
        )
        scheduler.add_job(
            run_weekly,
            CronTrigger.from_crontab(settings.analytics_weekly_cron),
            id="analytics_weekly",
            replace_existing=True,
        )

    return scheduler
