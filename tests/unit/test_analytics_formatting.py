from src.analytics.formatting import (
    format_breakdown_lines,
    format_token_usage,
    format_users_questions,
    merge_breakdown,
)


def test_merge_user_example() -> None:
    by_status = {"error": 5, "success": 9}
    by_category = {
        "answered": 2,
        "error": 5,
        "off_topic": 3,
        "success": 4,
    }
    merged = merge_breakdown(by_status, by_category)
    assert merged["answered"] == 6
    assert merged["off_topic"] == 3
    assert merged["error"] == 5
    assert sum(merged.values()) == 14


def test_format_breakdown_russian_labels() -> None:
    merged = {"answered": 6, "off_topic": 3, "error": 5}
    lines = format_breakdown_lines(merged, 14)
    text = "\n".join(lines)
    assert "Ответ из базы" in text
    assert "Не по теме" in text
    assert "Ошибка сервиса" in text
    assert "success" not in text
    assert "off_topic" not in text


def test_format_users_questions_russian() -> None:
    assert "2 сотрудника" in format_users_questions(2, 14)
    assert "14 вопросов" in format_users_questions(2, 14)


def test_format_token_usage() -> None:
    assert format_token_usage(1966, 198) == "💰 Расход AI: 2 164 токенов"
