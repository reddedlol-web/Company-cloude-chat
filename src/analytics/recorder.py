"""Record per-query analytics details."""

import hashlib
from datetime import UTC, datetime

from src.analytics.classifier import classify_query
from src.config import Settings
from src.db.repository import Repository

QUESTION_TEXT_MAX = 500


def _truncate(text: str, limit: int = QUESTION_TEXT_MAX) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _question_hash(text: str) -> str:
    normalized = text.strip()[:QUESTION_TEXT_MAX]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def record_query_detail(
    repository: Repository,
    settings: Settings,
    *,
    query_log_id: int,
    question: str,
    status: str,
    max_similarity: float | None,
    had_chunks: bool,
) -> None:
    category = classify_query(
        status=status,
        max_similarity=max_similarity,
        question=question,
        similarity_threshold=settings.analytics_off_topic_similarity_threshold,
        had_chunks=had_chunks,
    )
    question_text = (
        _truncate(question) if settings.analytics_store_questions else None
    )
    repository.record_query_detail(
        query_log_id=query_log_id,
        question_text=question_text,
        question_hash=_question_hash(question),
        category=category,
        max_similarity=max_similarity,
    )
