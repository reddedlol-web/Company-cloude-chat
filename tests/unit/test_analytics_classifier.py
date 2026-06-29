import pytest

from src.analytics.classifier import classify_query


def test_classify_answered() -> None:
    assert (
        classify_query(
            status="success",
            max_similarity=0.8,
            question="сколько дней отпуска",
            similarity_threshold=0.35,
            had_chunks=True,
        )
        == "answered"
    )


def test_classify_no_answer() -> None:
    assert (
        classify_query(
            status="no_answer",
            max_similarity=None,
            question="что-то неизвестное",
            similarity_threshold=0.35,
            had_chunks=False,
        )
        == "no_answer"
    )


def test_classify_off_topic_greeting() -> None:
    assert (
        classify_query(
            status="success",
            max_similarity=0.9,
            question="привет как дела",
            similarity_threshold=0.35,
            had_chunks=True,
        )
        == "off_topic"
    )


def test_classify_low_similarity() -> None:
    assert (
        classify_query(
            status="success",
            max_similarity=0.2,
            question="расскажи анекдот",
            similarity_threshold=0.35,
            had_chunks=True,
        )
        == "off_topic"
    )
