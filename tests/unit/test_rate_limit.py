from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.config import Settings
from src.db.repository import Repository


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    r = Repository(tmp_path / "test.db")
    r.init_db()
    return r


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        ALLOWED_USER_IDS="1",
        DAILY_QUERY_LIMIT=3,
        SQLITE_PATH=tmp_path / "test.db",
    )


def test_quota_allows_under_limit(repo: Repository, settings: Settings) -> None:
    ok, used, remaining = repo.check_quota(1, settings.daily_query_limit)
    assert ok is True
    assert used == 0
    assert remaining == 3


def test_quota_blocks_at_limit(repo: Repository, settings: Settings) -> None:
    for _ in range(3):
        repo.increment_usage(1)
    ok, used, remaining = repo.check_quota(1, settings.daily_query_limit)
    assert ok is False
    assert used == 3
    assert remaining == 0


def test_usage_resets_per_day(repo: Repository) -> None:
    repo.increment_usage(1)
    assert repo.get_usage(1) == 1
