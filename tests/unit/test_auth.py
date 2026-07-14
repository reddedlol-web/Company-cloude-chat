import pytest

from src.config import Settings
from src.db.repository import Repository


@pytest.fixture
def settings() -> Settings:
    return Settings(
        TELEGRAM_BOT_TOKEN="test:token",
        OPENROUTER_API_KEY="test-key",
        ALLOWED_USER_IDS="111,222",
        ADMIN_USER_IDS="111",
        DAILY_QUERY_LIMIT=20,
    )


@pytest.fixture
def repo(tmp_path):
    r = Repository(tmp_path / "bot.db")
    r.init_db()
    return r


def test_is_allowed(settings: Settings) -> None:
    assert settings.is_allowed(111) is True
    assert settings.is_allowed(222) is True
    assert settings.is_allowed(999) is False


def test_is_admin(settings: Settings) -> None:
    assert settings.is_admin(111) is True
    assert settings.is_admin(222) is False


def test_parse_single_id() -> None:
    s = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        ALLOWED_USER_IDS=42,
    )
    assert s.allowed_user_ids == [42]


def test_registered_user_access(settings: Settings, repo: Repository) -> None:
    repo.register_user(
        telegram_user_id=333,
        username="ivan",
        display_name="Ivan",
        invite_id="test-invite-id",
    )
    assert not settings.is_allowed(333)
    assert repo.is_registered_active(333)
    combined = settings.is_allowed(333) or repo.is_registered_active(333)
    assert combined is True


def test_blocked_user(repo: Repository) -> None:
    repo.register_user(
        telegram_user_id=444,
        username=None,
        display_name="Blocked",
        invite_id="x",
    )
    repo.block_user(444, blocked_by=1)
    assert repo.is_user_blocked(444)
    assert not repo.is_registered_active(444)
