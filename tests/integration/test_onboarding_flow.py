import pytest

from src.config import Settings
from src.db.repository import Repository
from src.services.invite import InviteError, InviteService, RedeemResult


def test_full_onboarding_flow(tmp_path) -> None:
    settings = Settings(
        TELEGRAM_BOT_TOKEN="t",
        OPENROUTER_API_KEY="k",
        ALLOWED_USER_IDS="1",
        ADMIN_USER_IDS="1",
        SQLITE_PATH=tmp_path / "bot.db",
        INVITE_DEFAULT_MAX_USES=2,
    )
    repo = Repository(settings.sqlite_path)
    repo.init_db()
    service = InviteService(settings, repo, "CorpBot")

    created = service.create_invite(
        created_by=1,
        label="QA Team",
        password="join123",
        max_uses=2,
    )

    invite, err = service.get_invite_for_redeem(created.token)
    assert err is None
    assert invite is not None
    assert service.verify_invite_password(invite, "join123")

    result = service.redeem(
        invite=invite,
        user_id=42,
        username="qa_user",
        display_name="QA User",
    )
    assert isinstance(result, RedeemResult)
    assert repo.is_registered_active(42)

    invite2, _ = service.get_invite_for_redeem(created.token)
    assert invite2 is not None
    service.redeem(
        invite=invite2,
        user_id=43,
        username="qa2",
        display_name="QA Two",
    )
    assert repo.is_registered_active(43)

    _, err3 = service.get_invite_for_redeem(created.token)
    assert err3 == InviteError.MAX_USES
