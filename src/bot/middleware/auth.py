from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.config import Settings
from src.db.repository import Repository

UNAUTHORIZED_MSG = (
    "⛔ У вас нет доступа к этому боту.\n"
    "Попросите у администратора ссылку-приглашение."
)


class AuthMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        data["user_id"] = user_id
        data["is_allowed"] = self.settings.is_allowed(user_id) or (
            self.repository.is_registered_active(user_id)
        )
        data["is_admin"] = self.settings.is_admin(user_id)
        return await handler(event, data)


def require_allowed(message: Message, data: dict[str, Any]) -> bool:
    if data.get("is_allowed"):
        return True
    return False


async def reply_unauthorized(message: Message) -> None:
    await message.answer(UNAUTHORIZED_MSG)
