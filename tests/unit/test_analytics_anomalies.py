"""Unit tests for anomaly detection."""

from datetime import UTC, datetime

from src.analytics.anomalies import AnomalyDetector
from src.config import Settings
from src.db.repository import Repository


def _settings(**kwargs) -> Settings:
    defaults = {
        "TELEGRAM_BOT_TOKEN": "test:token",
        "OPENROUTER_API_KEY": "sk-test",
        "ANOMALY_NO_ANSWER_RATIO": 0.5,
        "ANOMALY_NO_ANSWER_COUNT": 5,
        "ANOMALY_LIMIT_USAGE_RATIO": 0.9,
        "ANOMALY_TOKEN_USER_DAILY": 10000,
        "DAILY_QUERY_LIMIT": 20,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def test_high_no_answer_ratio(tmp_path) -> None:
    db = tmp_path / "test.db"
    repo = Repository(db)
    repo.init_db()
    settings = _settings()

    now = datetime.now(UTC).isoformat()
    user_id = 42
    for _ in range(8):
        log_id = repo.log_query(
            user_id=user_id,
            status="no_answer",
            question_length=10,
        )
        repo.record_query_detail(
            query_log_id=log_id,
            question_text="unknown topic?",
            question_hash="abc",
            category="no_answer",
            max_similarity=None,
        )

    with repo.connect() as conn:
        conn.execute(
            "UPDATE query_logs SET timestamp = ? WHERE telegram_user_id = ?",
            (now, user_id),
        )

    detector = AnomalyDetector(settings, repo)
    today = datetime.now(UTC).date().isoformat()
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = datetime.now(UTC)

    flags = detector.detect_for_period(start.isoformat(), end.isoformat(), today)
    types = [f.anomaly_type for f in flags]
    assert "high_no_answer_ratio" in types


def test_limit_near(tmp_path) -> None:
    db = tmp_path / "test.db"
    repo = Repository(db)
    repo.init_db()
    settings = _settings(DAILY_QUERY_LIMIT=20)

    day = datetime.now(UTC).date().isoformat()
    repo.increment_usage(99)
    for _ in range(17):
        repo.increment_usage(99)

    now = datetime.now(UTC).isoformat()
    log_id = repo.log_query(user_id=99, status="success")
    repo.record_query_detail(
        query_log_id=log_id,
        question_text="q",
        question_hash="h",
        category="answered",
        max_similarity=0.9,
    )
    with repo.connect() as conn:
        conn.execute(
            "UPDATE query_logs SET timestamp = ? WHERE id = ?",
            (now, log_id),
        )

    detector = AnomalyDetector(settings, repo)
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = datetime.now(UTC)
    flags = detector.detect_for_period(start.isoformat(), end.isoformat(), day)
    assert any(f.anomaly_type == "limit_near" for f in flags)
