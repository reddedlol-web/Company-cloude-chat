import pytest

from src.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        TELEGRAM_BOT_TOKEN="test:token",
        OPENROUTER_API_KEY="test-key",
        ALLOWED_USER_IDS="111,222",
        ADMIN_USER_IDS="111",
        DAILY_QUERY_LIMIT=20,
    )


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
