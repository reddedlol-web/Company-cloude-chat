import pytest

from src.analytics.aggregator import resolve_period
from src.analytics.reporter import AnalyticsReporter, split_telegram_messages
from src.config import Settings
from src.db.repository import Repository


@pytest.fixture
def reporter(tmp_path):
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        SQLITE_PATH=tmp_path / "bot.db",
    )
    repo = Repository(settings.sqlite_path)
    repo.init_db()
    return AnalyticsReporter(settings, repo, llm=None)


def test_split_telegram_messages_short() -> None:
    text = "hello"
    assert split_telegram_messages(text) == ["hello"]


def test_split_telegram_messages_long() -> None:
    text = "a\n\n" + ("x" * 5000)
    parts = split_telegram_messages(text, limit=1000)
    assert len(parts) >= 2
    assert all(len(p) <= 1000 for p in parts)


def test_format_stats_empty(reporter: AnalyticsReporter) -> None:
    msg = reporter.format_stats_message("today")
    assert "📭" in msg or "Запросы" in msg


@pytest.mark.asyncio
async def test_generate_report_numeric_only(reporter: AnalyticsReporter) -> None:
    repo = reporter.repository
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO query_logs (
                telegram_user_id, timestamp, status, tokens_input, tokens_output,
                sources_cited, question_length
            ) VALUES (1, datetime('now'), 'success', 10, 5, '[]', 20)
            """
        )
    result = await reporter.generate_report("daily", numeric_only=True, force=True)
    assert len(result.messages) >= 1
    assert result.llm_tokens_used == 0
