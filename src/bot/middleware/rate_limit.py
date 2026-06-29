from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.config import Settings
from src.db.repository import Repository

RATE_LIMIT_MSG = "⏳ Дневной лимит ({limit}) исчерпан. Попробуйте завтра."


class RateLimitMiddleware(BaseMiddleware):
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

        # Commands handled separately; rate limit applies to Q&A text only
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        if not data.get("is_allowed"):
            return await handler(event, data)

        user_id = event.from_user.id
        ok, used, remaining = self.repository.check_quota(
            user_id, self.settings.daily_query_limit
        )
        data["quota_used"] = used
        data["quota_remaining"] = remaining
        data["quota_limit"] = self.settings.daily_query_limit

        if not ok:
            data["rate_limited"] = True
            await event.answer(
                RATE_LIMIT_MSG.format(limit=self.settings.daily_query_limit)
            )
            self.repository.log_query(
                user_id=user_id,
                status="rate_limited",
                question_length=len(event.text or ""),
            )
            return None

        data["rate_limited"] = False
        return await handler(event, data)
