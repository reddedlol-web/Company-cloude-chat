import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.analytics.scheduler import create_scheduler
from src.bot.commands_menu import setup_bot_commands
from src.bot.handlers.admin import create_admin_router
from src.bot.handlers.analytics import create_analytics_router
from src.bot.handlers.commands import create_commands_router
from src.bot.handlers.messages import create_messages_router
from src.bot.handlers.onboarding import create_onboarding_router
from src.bot.middleware.auth import AuthMiddleware
from src.bot.middleware.rate_limit import RateLimitMiddleware
from src.config import Settings
from src.db.repository import Repository
from src.llm.openrouter import OpenRouterClient
from src.rag.indexer import KnowledgeIndexer
from src.rag.retriever import KnowledgeRetriever
from src.services.invite import InviteService

logger = logging.getLogger(__name__)


async def run_bot(settings: Settings) -> None:
    repository = Repository(settings.sqlite_path)
    repository.init_db()

    llm = OpenRouterClient(settings)
    retriever = KnowledgeRetriever(settings, llm)
    indexer = KnowledgeIndexer(settings, repository, llm)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    bot_username = settings.bot_username or me.username or "bot"
    invite_service = InviteService(settings, repository, bot_username)
    await setup_bot_commands(bot, settings)

    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AuthMiddleware(settings, repository))
    dp.message.middleware(RateLimitMiddleware(settings, repository))

    dp.include_router(
        create_onboarding_router(settings, repository, invite_service, bot)
    )
    dp.include_router(create_admin_router(settings, repository, invite_service))
    dp.include_router(create_commands_router(settings, repository, indexer))
    dp.include_router(create_analytics_router(settings, repository, llm))
    dp.include_router(
        create_messages_router(settings, repository, retriever, llm)
    )

    scheduler = create_scheduler(settings, repository, bot, llm)
    dashboard_task = None

    if settings.analytics_schedule_enabled:
        scheduler.start()
        logger.info("Analytics scheduler started")

    if settings.analytics_dashboard_enabled and settings.analytics_dashboard_token:
        try:
            from src.dashboard.app import start_dashboard_server

            dashboard_task = asyncio.create_task(
                start_dashboard_server(settings, repository)
            )
            logger.info(
                "Analytics dashboard on port %s", settings.analytics_dashboard_port
            )
        except ImportError:
            logger.warning(
                "Dashboard enabled but fastapi/uvicorn not installed. "
                "Run: pip install '.[dashboard]'"
            )

    logger.info("Starting Telegram bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        if settings.analytics_schedule_enabled:
            scheduler.shutdown(wait=False)
        if dashboard_task:
            dashboard_task.cancel()


def main_sync(settings: Settings) -> None:
    asyncio.run(run_bot(settings))
