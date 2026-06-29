"""Unit tests for analytics aggregator."""

from datetime import UTC, datetime, timedelta

from src.analytics.aggregator import AnalyticsAggregator, pct_change, resolve_period
from src.db.repository import Repository


def test_pct_change() -> None:
    assert pct_change(120, 100) == "↑20%"
    assert pct_change(80, 100) == "↓20%"
    assert pct_change(10, 0) is None


def test_resolve_period_today() -> None:
    period = resolve_period("today")
    assert period.kind == "today"
    assert period.start.date() == datetime.now(UTC).date()


def test_aggregator_period_stats(tmp_path) -> None:
    db = tmp_path / "test.db"
    repo = Repository(db)
    repo.init_db()

    now = datetime.now(UTC).isoformat()
    for i in range(5):
        log_id = repo.log_query(
            user_id=100 + i,
            status="success" if i < 4 else "no_answer",
            tokens_input=100,
            tokens_output=50,
            sources=["policy.md"],
        )
        repo.record_query_detail(
            query_log_id=log_id,
            question_text=f"Question {i}?",
            question_hash=f"hash{i}",
            category="answered" if i < 4 else "no_answer",
            max_similarity=0.8,
        )

    agg = AnalyticsAggregator(repo)
    period = resolve_period("today")
    stats = agg.get_stats(period)

    assert stats["total_queries"] == 5
    assert stats["unique_users"] == 5
    assert stats["tokens_input"] == 500
    assert stats["by_status"]["success"] == 4
    assert stats["by_status"]["no_answer"] == 1


def test_compute_daily_stats(tmp_path) -> None:
    db = tmp_path / "test.db"
    repo = Repository(db)
    repo.init_db()

    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=UTC)
    ts = start.replace(hour=12).isoformat()

    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO query_logs (
                telegram_user_id, timestamp, status, tokens_input, tokens_output,
                sources_cited, latency_ms, question_length
            ) VALUES (?, ?, 'success', 10, 5, '[]', 100, 10)
            """,
            (1, ts),
        )

    agg = AnalyticsAggregator(repo)
    stats = agg.compute_daily_stats(yesterday)
    assert stats["total_queries"] == 1

    rows = repo.get_daily_stats_range(yesterday.isoformat(), yesterday.isoformat())
    assert len(rows) == 1
    assert rows[0]["total_queries"] == 1
