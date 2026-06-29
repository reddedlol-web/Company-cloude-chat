"""Classify queries into analytics categories."""

import re

OFF_TOPIC_PATTERNS = re.compile(
    r"(?i)^(привет|здравствуй|hi|hello|как дела|что делаешь|"
    r"спасибо|thanks|thank you|пока|bye)\b|^\W{0,5}$"
)

CATEGORIES = frozenset(
    {"answered", "no_answer", "off_topic", "error", "rate_limited", "unauthorized"}
)


def classify_query(
    *,
    status: str,
    max_similarity: float | None,
    question: str,
    similarity_threshold: float,
    had_chunks: bool,
) -> str:
    if status == "unauthorized":
        return "unauthorized"
    if status == "rate_limited":
        return "rate_limited"
    if status == "error":
        return "error"
    if status == "no_answer" or not had_chunks:
        return "no_answer"

    question_stripped = question.strip()
    if OFF_TOPIC_PATTERNS.search(question_stripped):
        return "off_topic"

    if max_similarity is not None and max_similarity < similarity_threshold:
        return "off_topic"

    if status == "success":
        return "answered"

    return "no_answer"
