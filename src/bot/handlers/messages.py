import logging
import time

from aiogram import Router
from aiogram.types import Message
from httpx import HTTPError

from src.analytics.recorder import record_query_detail
from src.bot.middleware.auth import reply_unauthorized, require_allowed
from src.config import Settings
from src.db.repository import Repository
from src.llm.openrouter import OpenRouterClient
from src.rag.prompts import SYSTEM_PROMPT, build_user_prompt
from src.rag.retriever import KnowledgeRetriever

logger = logging.getLogger(__name__)

NO_ANSWER_MSG = "❓ В базе знаний нет информации по вашему вопросу."
API_ERROR_MSG = "⚠️ Сервис временно недоступен. Попробуйте позже."
TOO_LONG_MSG = "✂️ Сократите вопрос до {limit} символов."


def _log_with_detail(
    repository: Repository,
    settings: Settings,
    *,
    query_log_id: int,
    question: str,
    status: str,
    max_similarity: float | None,
    had_chunks: bool,
) -> None:
    try:
        record_query_detail(
            repository,
            settings,
            query_log_id=query_log_id,
            question=question,
            status=status,
            max_similarity=max_similarity,
            had_chunks=had_chunks,
        )
    except Exception:
        logger.exception("Failed to record query detail for log %s", query_log_id)


def create_messages_router(
    settings: Settings,
    repository: Repository,
    retriever: KnowledgeRetriever,
    llm: OpenRouterClient,
) -> Router:
    router = Router(name="messages")

    @router.message()
    async def handle_question(message: Message, **data) -> None:
        if data.get("rate_limited"):
            return

        if not require_allowed(message, data):
            await reply_unauthorized(message)
            log_id = repository.log_query(
                user_id=message.from_user.id,
                status="unauthorized",
                question_length=len(message.text or ""),
            )
            _log_with_detail(
                repository,
                settings,
                query_log_id=log_id,
                question=message.text or "",
                status="unauthorized",
                max_similarity=None,
                had_chunks=False,
            )
            return

        question = (message.text or "").strip()
        if not question or question.startswith("/"):
            return

        user_id = message.from_user.id

        if len(question) > settings.max_question_length:
            await message.answer(
                TOO_LONG_MSG.format(limit=settings.max_question_length)
            )
            return

        started = time.perf_counter()
        try:
            chunks, max_similarity = await retriever.retrieve(question)
            if not chunks:
                await message.answer(NO_ANSWER_MSG)
                log_id = repository.log_query(
                    user_id=user_id,
                    status="no_answer",
                    question_length=len(question),
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
                _log_with_detail(
                    repository,
                    settings,
                    query_log_id=log_id,
                    question=question,
                    status="no_answer",
                    max_similarity=max_similarity,
                    had_chunks=False,
                )
                return

            user_prompt = build_user_prompt(question, chunks)
            result = await llm.chat(SYSTEM_PROMPT, user_prompt)

            sources = sorted({str(chunk["title"]) for chunk in chunks})
            sources_line = ", ".join(sources)
            reply = f"{result.content}\n\n📎 Источники: {sources_line}"

            await message.answer(reply)
            repository.increment_usage(user_id)
            log_id = repository.log_query(
                user_id=user_id,
                status="success",
                tokens_input=result.tokens_input,
                tokens_output=result.tokens_output,
                sources=sources,
                latency_ms=int((time.perf_counter() - started) * 1000),
                question_length=len(question),
            )
            _log_with_detail(
                repository,
                settings,
                query_log_id=log_id,
                question=question,
                status="success",
                max_similarity=max_similarity,
                had_chunks=True,
            )
        except HTTPError:
            logger.exception("LLM API error for user %s", user_id)
            await message.answer(API_ERROR_MSG)
            log_id = repository.log_query(
                user_id=user_id,
                status="error",
                question_length=len(question),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            _log_with_detail(
                repository,
                settings,
                query_log_id=log_id,
                question=question,
                status="error",
                max_similarity=None,
                had_chunks=False,
            )
        except Exception:
            logger.exception("Unexpected error handling question")
            await message.answer(API_ERROR_MSG)
            log_id = repository.log_query(
                user_id=user_id,
                status="error",
                question_length=len(question),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            _log_with_detail(
                repository,
                settings,
                query_log_id=log_id,
                question=question,
                status="error",
                max_similarity=None,
                had_chunks=False,
            )

    return router
