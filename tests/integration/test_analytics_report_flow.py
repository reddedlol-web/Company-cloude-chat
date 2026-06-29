from unittest.mock import AsyncMock, patch

import pytest

from src.analytics.reporter import AnalyticsReporter
from src.config import Settings
from src.db.repository import Repository


@pytest.mark.asyncio
async def test_report_flow_dry_run(tmp_path) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        SQLITE_PATH=tmp_path / "bot.db",
    )
    repo = Repository(settings.sqlite_path)
    repo.init_db()

    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO query_logs (
                telegram_user_id, timestamp, status, tokens_input, tokens_output,
                sources_cited, question_length
            ) VALUES (1, datetime('now'), 'success', 100, 40, '["policy"]', 25)
            """
        )
        log_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO query_details (
                query_log_id, question_hash, category, question_text
            ) VALUES (?, 'abc', 'answered', 'Какой отпуск?')
            """,
            (log_id,),
        )

    reporter = AnalyticsReporter(settings, repo, llm=None)

    with patch.object(reporter, "_llm_insights", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = ("Темы: отпуск", 50)
        result = await reporter.generate_report("today", force=True)

    assert len(result.messages) >= 1
    assert result.report_id is not None
