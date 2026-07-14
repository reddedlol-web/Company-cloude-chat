"""Admin commands: invites and user management."""

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.config import Settings
from src.db.repository import Repository
from src.services.invite import InviteService, parse_create_args

logger = logging.getLogger(__name__)

ADMIN_DENY = "⛔ Команда доступна только администраторам."
CB_REVOKE = "inv:rv:"
CB_LIST = "inv:list"


def create_admin_router(
    settings: Settings,
    repository: Repository,
    invite_service: InviteService,
) -> Router:
    router = Router(name="admin")

    def _is_admin_user(user_id: int | None) -> bool:
        return user_id is not None and settings.is_admin(user_id)

    def _create_params_from_args(args: str) -> dict:
        params = parse_create_args(args)
        return {
            "label": params.get("label"),
            "password": params.get("password"),
            "days": int(params["days"]) if params.get("days", "").isdigit() else None,
            "max_uses": int(params["uses"]) if params.get("uses", "").isdigit() else None,
        }

    def _format_invites_list() -> tuple[str, InlineKeyboardMarkup | None]:
        invites = repository.list_active_invites()
        if not invites:
            return "📋 Активных приглашений нет.", None

        from src.utils.timefmt import to_msk

        lines = ["📋 Активные приглашения:"]
        buttons: list[list[InlineKeyboardButton]] = []
        for i, inv in enumerate(invites, 1):
            label = inv.get("label") or "без метки"
            uses = invite_service.get_invite_uses_label(inv)
            exp_dt = datetime.fromisoformat(inv["expires_at"])
            exp = to_msk(exp_dt).strftime("%d.%m")
            link = invite_service.build_link(inv["token"])
            lines.append(f"{i}. {label} — {uses} — до {exp}\n{link}")
            btn_label = f"Отозвать: {label}" if inv.get("label") else f"Отозвать #{i}"
            if len(btn_label) > 64:
                btn_label = f"Отозвать #{i}"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=btn_label,
                        callback_data=f"{CB_REVOKE}{inv['token']}",
                    )
                ]
            )
        return "\n\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)

    def _create_reply_keyboard(token: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Список",
                        callback_data=CB_LIST,
                    ),
                    InlineKeyboardButton(
                        text="🚫 Отозвать",
                        callback_data=f"{CB_REVOKE}{token}",
                    ),
                ]
            ]
        )

    @router.message(Command("invite"))
    async def cmd_invite(message: Message, command: CommandObject) -> None:
        if not _is_admin_user(message.from_user.id if message.from_user else None):
            await message.answer(ADMIN_DENY)
            return

        args = (command.args or "").strip()
        if args:
            parts = args.split(maxsplit=1)
            sub = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""

            if sub == "list":
                text, markup = _format_invites_list()
                await message.answer(text, reply_markup=markup)
                return

            if sub == "revoke":
                token = rest.strip()
                if not token:
                    await message.answer("Укажите токен или откройте /invites и нажмите «Отозвать».")
                    return
                if invite_service.revoke_invite(token):
                    await message.answer("🚫 Приглашение отозвано.")
                else:
                    await message.answer("Приглашение не найдено или уже отозвано.")
                return

            if sub == "create":
                args = rest
            elif sub == "help":
                await message.answer(
                    "Создать ссылку: /invite\n"
                    "С параметрами: /invite label=Отдел password=код days=7 uses=5\n"
                    "Список: /invites\n"
                    "Отзыв — кнопкой в /invites"
                )
                return

        params = _create_params_from_args(args)
        result = invite_service.create_invite(
            created_by=message.from_user.id,
            **params,
        )
        await message.answer(
            invite_service.format_create_message(result),
            reply_markup=_create_reply_keyboard(result.token),
        )

    @router.message(Command("invites"))
    async def cmd_invites(message: Message) -> None:
        if not _is_admin_user(message.from_user.id if message.from_user else None):
            await message.answer(ADMIN_DENY)
            return
        text, markup = _format_invites_list()
        await message.answer(text, reply_markup=markup)

    @router.callback_query(F.data == CB_LIST)
    async def cb_invite_list(query: CallbackQuery) -> None:
        if not _is_admin_user(query.from_user.id if query.from_user else None):
            await query.answer(ADMIN_DENY, show_alert=True)
            return
        text, markup = _format_invites_list()
        await query.message.answer(text, reply_markup=markup)
        await query.answer()

    @router.callback_query(F.data.startswith(CB_REVOKE))
    async def cb_invite_revoke(query: CallbackQuery) -> None:
        if not _is_admin_user(query.from_user.id if query.from_user else None):
            await query.answer(ADMIN_DENY, show_alert=True)
            return
        token = (query.data or "")[len(CB_REVOKE) :]
        if not token:
            await query.answer("Токен не найден", show_alert=True)
            return
        if invite_service.revoke_invite(token):
            await query.answer("Отозвано")
            text, markup = _format_invites_list()
            try:
                await query.message.edit_text(text, reply_markup=markup)
            except Exception:
                await query.message.answer(f"🚫 Приглашение отозвано.\n\n{text}", reply_markup=markup)
        else:
            await query.answer("Уже отозвано или не найдено", show_alert=True)

    @router.message(Command("users"))
    async def cmd_users(message: Message) -> None:
        if not _is_admin_user(message.from_user.id if message.from_user else None):
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
        if not _is_admin_user(message.from_user.id if message.from_user else None):
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
