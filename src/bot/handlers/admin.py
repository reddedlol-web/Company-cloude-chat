"""Admin commands: invites and user management."""

import logging
from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.config import Settings
from src.db.repository import Repository
from src.services.invite import InviteService, parse_create_args

logger = logging.getLogger(__name__)

ADMIN_DENY = "⛔ Команда доступна только администраторам."


def create_admin_router(
    settings: Settings,
    repository: Repository,
    invite_service: InviteService,
) -> Router:
    router = Router(name="admin")

    def _is_admin(message: Message) -> bool:
        return settings.is_admin(message.from_user.id)

    @router.message(Command("invite"))
    async def cmd_invite(message: Message, command: CommandObject) -> None:
        if not _is_admin(message):
            await message.answer(ADMIN_DENY)
            return

        args = (command.args or "").strip()
        if not args:
            await message.answer(
                "Использование:\n"
                "/invite create label=Отдел password=код days=7 uses=5\n"
                "/invite list\n"
                "/invite revoke <token>"
            )
            return

        parts = args.split(maxsplit=1)
        sub = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "create":
            params = parse_create_args(rest)
            label = params.get("label")
            password = params.get("password")
            days = int(params["days"]) if params.get("days", "").isdigit() else None
            uses = int(params["uses"]) if params.get("uses", "").isdigit() else None
            result = invite_service.create_invite(
                created_by=message.from_user.id,
                label=label,
                password=password,
                days=days,
                max_uses=uses,
            )
            await message.answer(invite_service.format_create_message(result))
            return

        if sub == "list":
            invites = repository.list_active_invites()
            if not invites:
                await message.answer("📋 Активных приглашений нет.")
                return
            lines = ["📋 Активные приглашения:"]
            for i, inv in enumerate(invites, 1):
                label = inv.get("label") or "—"
                uses = invite_service.get_invite_uses_label(inv)
                from src.utils.timefmt import to_msk

                exp_dt = datetime.fromisoformat(inv["expires_at"])
                exp = to_msk(exp_dt).strftime("%d.%m")
                token_short = inv["token"][:8] + "…"
                lines.append(f"{i}. {label} — {uses} — до {exp} — {token_short}")
            await message.answer("\n".join(lines))
            return

        if sub == "revoke":
            token = rest.strip()
            if not token:
                await message.answer("Укажите токен: /invite revoke <token>")
                return
            if invite_service.revoke_invite(token):
                await message.answer(f"🚫 Приглашение {token} отозвано.")
            else:
                await message.answer("Приглашение не найдено или уже отозвано.")
            return

        await message.answer("Неизвестная подкоманда. Используйте create, list или revoke.")

    @router.message(Command("users"))
    async def cmd_users(message: Message) -> None:
        if not _is_admin(message):
            await message.answer(ADMIN_DENY)
            return

        users = repository.list_registered_users(limit=50)
        if not users:
            await message.answer("👥 Зарегистрированных пользователей пока нет.")
            return

        total = repository.count_registered_users()
        lines = [f"👥 Пользователи ({total}):"]
        for u in users:
            uname = f"@{u['username']}" if u.get("username") else f"ID {u['telegram_user_id']}"
            reg = datetime.fromisoformat(u["registered_at"]).strftime("%d.%m")
            used = repository.get_usage(int(u["telegram_user_id"]))
            status = "🚫" if u.get("blocked_at") or not u.get("is_active") else ""
            lines.append(
                f"• {uname} — ID {u['telegram_user_id']} — с {reg} — "
                f"сегодня {used}/{settings.daily_query_limit} {status}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("user"))
    async def cmd_user(message: Message, command: CommandObject) -> None:
        if not _is_admin(message):
            await message.answer(ADMIN_DENY)
            return

        args = (command.args or "").strip().split()
        if not args:
            await message.answer(
                "Использование:\n"
                "/user <telegram_id>\n"
                "/user block <telegram_id>\n"
                "/user unblock <telegram_id>"
            )
            return

        if args[0].lower() == "block":
            if len(args) < 2 or not args[1].isdigit():
                await message.answer("Использование: /user block <telegram_id>")
                return
            uid = int(args[1])
            if repository.block_user(uid, message.from_user.id):
                await message.answer(f"🚫 Пользователь {uid} заблокирован.")
            else:
                await message.answer(f"Пользователь {uid} не найден в registered_users.")
            return

        if args[0].lower() == "unblock":
            if len(args) < 2 or not args[1].isdigit():
                await message.answer("Использование: /user unblock <telegram_id>")
                return
            uid = int(args[1])
            if repository.unblock_user(uid):
                await message.answer(f"✅ Пользователь {uid} разблокирован.")
            else:
                await message.answer(f"Пользователь {uid} не найден.")
            return

        if not args[0].isdigit():
            await message.answer("Укажите числовой Telegram ID.")
            return

        uid = int(args[0])
        user = repository.get_registered_user(uid)
        if not user:
            await message.answer(f"Пользователь {uid} не зарегистрирован через invite.")
            return

        from src.utils.timefmt import format_msk, to_msk

        uname = f"@{user['username']}" if user.get("username") else "—"
        reg = to_msk(datetime.fromisoformat(user["registered_at"])).strftime("%d.%m.%Y")
        invite_label = user.get("invite_label") or "—"
        active = "активен" if user.get("is_active") and not user.get("blocked_at") else "заблокирован"
        used_today = repository.get_usage(uid)
        total_q = repository.count_user_queries(uid)
        last_q = repository.get_last_query_time(uid)
        last_q_str = (
            format_msk(datetime.fromisoformat(last_q)) if last_q else "—"
        )

        await message.answer(
            f"👤 {uname} ({uid})\n"
            f"Регистрация: {reg} via «{invite_label}»\n"
            f"Статус: {active}\n"
            f"Сегодня: {used_today}/{settings.daily_query_limit} | "
            f"Всего запросов: {total_q}\n"
            f"Последний запрос: {last_q_str}"
        )

    return router
