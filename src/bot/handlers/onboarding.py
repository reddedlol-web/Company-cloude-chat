"""Onboarding via invite deep links and password FSM."""

import logging
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.config import Settings
from src.db.repository import Repository
from src.services.invite import InviteError, InviteService, parse_invite_payload

logger = logging.getLogger(__name__)


class OnboardingStates(StatesGroup):
    awaiting_password = State()


INVITE_ERRORS = {
    InviteError.NOT_FOUND: "❌ Приглашение недействительно или истекло. Обратитесь к администратору.",
    InviteError.REVOKED: "❌ Приглашение недействительно или истекло. Обратитесь к администратору.",
    InviteError.EXPIRED: "❌ Приглашение недействительно или истекло. Обратитесь к администратору.",
    InviteError.MAX_USES: "❌ Это приглашение уже использовано максимальное число раз.",
    InviteError.BLOCKED: "⛔ Ваш доступ заблокирован.",
    InviteError.ALREADY_ALLOWED: "ℹ️ Вы уже имеете доступ к боту.",
    InviteError.TOO_MANY_ATTEMPTS: (
        "⛔ Слишком много попыток. Попробуйте позже или запросите новое приглашение."
    ),
}


def _display_name(message: Message) -> str:
    user = message.from_user
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or (user.username or str(user.id))


async def _notify_registration(
    bot: Bot,
    settings: Settings,
    *,
    user_id: int,
    username: str | None,
    invite_label: str | None,
    use_count: int,
    max_uses: int,
) -> None:
    from src.services.invite import InviteService
    from src.utils.timefmt import format_msk

    handle = f"@{username}" if username else f"ID {user_id}"
    now = format_msk()
    label = invite_label or "—"
    uses = InviteService.format_uses_label(use_count, max_uses)
    text = (
        f"🆕 Новый пользователь: {handle} ({user_id})\n"
        f"Приглашение: «{label}» | {uses} | {now}"
    )

    targets: list[int] = []
    if settings.admin_notify_chat_id:
        targets.append(settings.admin_notify_chat_id)
    else:
        targets.extend(settings.admin_user_ids)

    for chat_id in targets:
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            logger.exception("Failed to notify registration to %s", chat_id)


def create_onboarding_router(
    settings: Settings,
    repository: Repository,
    invite_service: InviteService,
    bot: Bot,
) -> Router:
    router = Router(name="onboarding")

    async def _complete_registration(
        message: Message,
        invite: dict[str, Any],
        state: FSMContext,
    ) -> None:
        user = message.from_user
        result = invite_service.redeem(
            invite=invite,
            user_id=user.id,
            username=user.username,
            display_name=_display_name(message),
        )
        if isinstance(result, InviteError):
            await message.answer(INVITE_ERRORS[result])
            return

        await state.clear()
        await message.answer(
            f"✅ Добро пожаловать, {_display_name(message)}!\n"
            "Задавайте вопросы по документам компании.\n"
            f"Лимит сегодня: {settings.daily_query_limit} вопросов."
        )
        await _notify_registration(
            bot,
            settings,
            user_id=user.id,
            username=user.username,
            invite_label=result.invite_label,
            use_count=result.use_count,
            max_uses=result.max_uses,
        )

    @router.message(Command("start"))
    async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        user_id = message.from_user.id
        payload = (command.args or "").strip()

        if payload.startswith("invite_"):
            token = parse_invite_payload(payload)
            if not token:
                await message.answer(INVITE_ERRORS[InviteError.NOT_FOUND])
                return

            invite, error = invite_service.get_invite_for_redeem(token)
            if error:
                await message.answer(INVITE_ERRORS[error])
                return
            assert invite is not None

            if settings.is_allowed(user_id) or repository.is_registered_active(user_id):
                await message.answer(INVITE_ERRORS[InviteError.ALREADY_ALLOWED])
                return

            if repository.is_user_blocked(user_id):
                await message.answer(INVITE_ERRORS[InviteError.BLOCKED])
                return

            if invite.get("password_hash"):
                attempt_err = invite_service.check_password_allowed(user_id, invite["id"])
                if attempt_err:
                    await message.answer(INVITE_ERRORS[attempt_err])
                    return
                await state.set_state(OnboardingStates.awaiting_password)
                await state.update_data(invite_id=invite["id"], invite_token=token)
                await message.answer("🔒 Введите пароль приглашения:")
                return

            await _complete_registration(message, invite, state)
            return

        if settings.is_allowed(user_id) or repository.is_registered_active(user_id):
            _, _used, remaining = repository.check_quota(
                user_id, settings.daily_query_limit
            )
            await message.answer(
                "👋 Привет! Я корпоративный помощник.\n"
                "Задайте вопрос по регламентам и документам компании.\n"
                f"Лимит: {remaining}/{settings.daily_query_limit} вопросов сегодня."
            )
            return

        await message.answer(
            "⛔ У вас нет доступа.\n"
            "Попросите у администратора ссылку-приглашение или обратитесь в HR."
        )

    @router.message(OnboardingStates.awaiting_password, F.text)
    async def process_invite_password(
        message: Message, state: FSMContext
    ) -> None:
        data = await state.get_data()
        token = data.get("invite_token")
        if not token:
            await state.clear()
            await message.answer(INVITE_ERRORS[InviteError.NOT_FOUND])
            return

        invite, error = invite_service.get_invite_for_redeem(token)
        if error:
            await state.clear()
            await message.answer(INVITE_ERRORS[error])
            return
        assert invite is not None

        user_id = message.from_user.id
        attempt_err = invite_service.check_password_allowed(user_id, invite["id"])
        if attempt_err:
            await state.clear()
            await message.answer(INVITE_ERRORS[attempt_err])
            return

        password = (message.text or "").strip()
        if not invite_service.verify_invite_password(invite, password):
            remaining = invite_service.record_wrong_password(user_id, invite["id"])
            if remaining <= 0:
                await state.clear()
                await message.answer(INVITE_ERRORS[InviteError.TOO_MANY_ATTEMPTS])
            else:
                await message.answer(f"🔒 Неверный пароль. Осталось попыток: {remaining}")
            return

        await _complete_registration(message, invite, state)

    return router
