import json
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.config import Settings
from src.db.repository import Repository
from src.rag.indexer import KnowledgeIndexer

logger = logging.getLogger(__name__)


def create_commands_router(
    settings: Settings,
    repository: Repository,
    indexer: KnowledgeIndexer | None = None,
) -> Router:
    router = Router(name="commands")

    @router.message(Command("help"))
    async def cmd_help(message: Message, **data) -> None:
        if not data.get("is_allowed"):
            await message.answer(
                "⛔ У вас нет доступа.\n"
                "Попросите у администратора ссылку-приглашение или обратитесь в HR."
            )
            return
        await message.answer(
            "📖 Как пользоваться:\n"
            "• Напишите вопрос обычным текстом\n"
            "• Я отвечу на основе документов компании\n"
            "• Если ответа нет в базе — скажу честно\n\n"
            "Команды:\n"
            "/start — начало\n"
            "/help — эта справка\n"
            "/limit — остаток лимита на сегодня"
        )

    @router.message(Command("limit"))
    async def cmd_limit(message: Message, **data) -> None:
        if not data.get("is_allowed"):
            await message.answer(
                "⛔ У вас нет доступа.\n"
                "Попросите у администратора ссылку-приглашение или обратитесь в HR."
            )
            return
        used = repository.get_usage(message.from_user.id)
        remaining = max(0, settings.daily_query_limit - used)
        await message.answer(
            f"📊 Использовано сегодня: {used}/{settings.daily_query_limit}\n"
            f"Осталось: {remaining}\n"
            "Сброс: 00:00 UTC"
        )

    if indexer is not None:

        @router.message(Command("reindex"))
        async def cmd_reindex(message: Message, **data) -> None:
            if not settings.is_admin(message.from_user.id):
                await message.answer("⛔ Команда доступна только администратору.")
                return

            await message.answer("⏳ Индексация запущена...")
            result = await indexer.reindex(force=True)

            if result.errors:
                error_lines = "\n".join(
                    f"• {e['file']}: {e['error']}" for e in result.errors[:5]
                )
                extra = f"\n\n⚠️ Ошибки:\n{error_lines}"
            else:
                extra = ""

            await message.answer(
                f"✅ Индексация завершена.\n"
                f"Документов: {result.documents_indexed}, "
                f"чанков: {result.chunks_created}{extra}"
            )
            if result.errors:
                logger.warning("Reindex errors: %s", json.dumps(result.errors))

    return router
