import pytest

from src.config import Settings
from src.db.repository import Repository
from src.services.invite import (
    InviteError,
    InviteService,
    parse_create_args,
    parse_invite_payload,
    verify_password,
)


@pytest.fixture
def invite_env(tmp_path):
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        SQLITE_PATH=tmp_path / "bot.db",
        INVITE_DEFAULT_DAYS=7,
        INVITE_DEFAULT_MAX_USES=3,
    )
    repo = Repository(settings.sqlite_path)
    repo.init_db()
    service = InviteService(settings, repo, "TestCompanyBot")
    return settings, repo, service


def test_parse_invite_payload() -> None:
    assert parse_invite_payload("invite_abc123") == "abc123"
    assert parse_invite_payload("hello") is None


def test_parse_create_args() -> None:
    parsed = parse_create_args("label=HR password=secret days=14 uses=5")
    assert parsed["label"] == "HR"
    assert parsed["password"] == "secret"
    assert parsed["days"] == "14"
    assert parsed["uses"] == "5"


def test_create_and_redeem_invite(invite_env) -> None:
    _settings, repo, service = invite_env
    created = service.create_invite(
        created_by=1,
        label="Sales",
        password=None,
        days=7,
        max_uses=1,
    )
    assert "t.me/TestCompanyBot" in created.link

    invite, err = service.get_invite_for_redeem(created.token)
    assert err is None
    assert invite is not None

    result = service.redeem(
        invite=invite,
        user_id=999,
        username="newuser",
        display_name="New User",
    )
    assert not isinstance(result, InviteError)
    assert repo.is_registered_active(999)


def test_redeem_with_password(invite_env) -> None:
    _settings, repo, service = invite_env
    created = service.create_invite(
        created_by=1,
        label="Secure",
        password="summer2026",
        max_uses=5,
    )
    invite, _ = service.get_invite_for_redeem(created.token)
    assert invite is not None
    assert invite["password_hash"]
    assert verify_password("summer2026", invite["password_hash"])
    assert not verify_password("wrong", invite["password_hash"])

    result = service.redeem(
        invite=invite,
        user_id=100,
        username=None,
        display_name="Test",
    )
    assert not isinstance(result, InviteError)
    assert repo.is_registered_active(100)


def test_revoke_invite(invite_env) -> None:
    _settings, _repo, service = invite_env
    created = service.create_invite(created_by=1)
    assert service.revoke_invite(created.token)
    _invite, err = service.get_invite_for_redeem(created.token)
    assert err == InviteError.REVOKED


def test_already_allowed(invite_env) -> None:
    settings, _repo, service = invite_env
    settings.allowed_user_ids.append(555)
    created = service.create_invite(created_by=1)
    invite, _ = service.get_invite_for_redeem(created.token)
    result = service.redeem(
        invite=invite,  # type: ignore[arg-type]
        user_id=555,
        username=None,
        display_name="Admin",
    )
    assert result == InviteError.ALREADY_ALLOWED
