"""Invite creation, validation, and redemption."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import bcrypt

from src.config import Settings
from src.db.repository import Repository

INVITE_PREFIX = "invite_"
PASSWORD_ATTEMPT_LIMIT = 3
PASSWORD_ATTEMPT_WINDOW_MINUTES = 15


class InviteError(str, Enum):
    NOT_FOUND = "not_found"
    REVOKED = "revoked"
    EXPIRED = "expired"
    MAX_USES = "max_uses"
    BLOCKED = "blocked"
    ALREADY_ALLOWED = "already_allowed"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    WRONG_PASSWORD = "wrong_password"


@dataclass
class InviteCreateResult:
    invite_id: str
    token: str
    link: str
    label: str | None
    password_plain: str | None
    expires_at: datetime
    max_uses: int


@dataclass
class RedeemResult:
    display_name: str
    invite_label: str | None
    use_count: int
    max_uses: int


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def parse_invite_payload(start_arg: str) -> str | None:
    if not start_arg.startswith(INVITE_PREFIX):
        return None
    token = start_arg[len(INVITE_PREFIX) :]
    return token if token else None


def parse_create_args(args: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in args.split():
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip().lower()] = value.strip()
    return result


class InviteService:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        bot_username: str,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.bot_username = bot_username.lstrip("@")

    def build_link(self, token: str) -> str:
        return f"https://t.me/{self.bot_username}?start={INVITE_PREFIX}{token}"

    def create_invite(
        self,
        *,
        created_by: int,
        label: str | None = None,
        password: str | None = None,
        days: int | None = None,
        max_uses: int | None = None,
    ) -> InviteCreateResult:
        token = secrets.token_urlsafe(12)
        invite_id = str(uuid.uuid4())
        days_val = days if days is not None else self.settings.invite_default_days
        uses_val = max_uses if max_uses is not None else self.settings.invite_default_max_uses
        expires_at = datetime.now(UTC) + timedelta(days=days_val)
        password_hash = _hash_password(password) if password else None

        self.repository.create_invite(
            invite_id=invite_id,
            token=token,
            password_hash=password_hash,
            label=label,
            created_by=created_by,
            max_uses=uses_val,
            expires_at=expires_at.isoformat(),
        )
        return InviteCreateResult(
            invite_id=invite_id,
            token=token,
            link=self.build_link(token),
            label=label,
            password_plain=password,
            expires_at=expires_at,
            max_uses=uses_val,
        )

    def get_invite_for_redeem(self, token: str) -> tuple[dict[str, Any] | None, InviteError | None]:
        invite = self.repository.get_invite_by_token(token)
        if invite is None:
            return None, InviteError.NOT_FOUND

        if invite["status"] == "revoked":
            return None, InviteError.REVOKED

        expires_at = datetime.fromisoformat(invite["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if datetime.now(UTC) >= expires_at:
            self.repository.update_invite_status(invite["id"], "expired")
            return None, InviteError.EXPIRED

        max_uses = int(invite["max_uses"])
        use_count = int(invite["use_count"])
        if max_uses > 0 and use_count >= max_uses:
            return None, InviteError.MAX_USES

        return invite, None

    def check_password_allowed(self, user_id: int, invite_id: str) -> InviteError | None:
        attempts = self.repository.get_password_attempts(user_id, invite_id)
        if not attempts:
            return None
        window_start = datetime.fromisoformat(attempts["window_start"])
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=UTC)
        elapsed = datetime.now(UTC) - window_start
        if elapsed > timedelta(minutes=PASSWORD_ATTEMPT_WINDOW_MINUTES):
            self.repository.reset_password_attempts(user_id, invite_id)
            return None
        if int(attempts["attempt_count"]) >= PASSWORD_ATTEMPT_LIMIT:
            return InviteError.TOO_MANY_ATTEMPTS
        return None

    def record_wrong_password(self, user_id: int, invite_id: str) -> int:
        return self.repository.record_password_attempt(user_id, invite_id)

    def verify_invite_password(self, invite: dict[str, Any], password: str) -> bool:
        password_hash = invite.get("password_hash")
        if not password_hash:
            return True
        return verify_password(password, password_hash)

    def redeem(
        self,
        *,
        invite: dict[str, Any],
        user_id: int,
        username: str | None,
        display_name: str,
    ) -> RedeemResult | InviteError:
        if self.repository.is_user_blocked(user_id):
            return InviteError.BLOCKED

        if self.settings.is_allowed(user_id) or self.repository.is_registered_active(user_id):
            return InviteError.ALREADY_ALLOWED

        self.repository.register_user(
            telegram_user_id=user_id,
            username=username,
            display_name=display_name,
            invite_id=invite["id"],
        )
        self.repository.record_invite_redemption(invite["id"], user_id)
        self.repository.increment_invite_use_count(invite["id"])
        self.repository.reset_password_attempts(user_id, invite["id"])

        updated = self.repository.get_invite_by_token(invite["token"])
        use_count = int(updated["use_count"]) if updated else int(invite["use_count"]) + 1
        max_uses = int(invite["max_uses"])

        return RedeemResult(
            display_name=display_name,
            invite_label=invite.get("label"),
            use_count=use_count,
            max_uses=max_uses,
        )

    def revoke_invite(self, token: str) -> bool:
        return self.repository.revoke_invite_by_token(token)

    @staticmethod
    def format_uses_label(use_count: int, max_uses: int) -> str:
        if max_uses > 0:
            return f"{use_count}/{max_uses}"
        return f"{use_count}/∞"

    def get_invite_uses_label(self, invite: dict[str, Any]) -> str:
        """Actual usage from redemptions (stays in sync with registrations)."""
        count = self.repository.count_invite_redemptions(invite["id"])
        max_uses = int(invite["max_uses"])
        if count != int(invite["use_count"]):
            self.repository.sync_invite_use_count(invite["id"], count)
        return self.format_uses_label(count, max_uses)

    def format_create_message(self, result: InviteCreateResult) -> str:
        from src.utils.timefmt import format_msk_date

        label_part = f"«{result.label}»" if result.label else "(без метки)"
        uses_label = self.format_uses_label(0, result.max_uses)
        expires = format_msk_date(result.expires_at)
        lines = [
            f"🔗 Приглашение создано: {label_part}",
            f"Ссылка: {result.link}",
            f"Срок: до {expires} | Использований: {uses_label}",
        ]
        if result.password_plain:
            lines.append(f"Пароль: {result.password_plain}")
        lines.append("Актуальный счётчик: /invite list")
        return "\n".join(lines)
