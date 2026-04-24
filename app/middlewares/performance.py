import logging
from time import perf_counter
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

logger = logging.getLogger(__name__)
SLOW_UPDATE_THRESHOLD_SECONDS = 3


class SlowUpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started_at = perf_counter()
        try:
            return await handler(event, data)
        finally:
            duration_seconds = perf_counter() - started_at
            if duration_seconds <= SLOW_UPDATE_THRESHOLD_SECONDS:
                return

            update = data.get("event_update")
            update_id = update.update_id if isinstance(update, Update) else None
            user_id = None
            if isinstance(event, Message) and event.from_user is not None:
                user_id = event.from_user.id
            elif isinstance(event, CallbackQuery) and event.from_user is not None:
                user_id = event.from_user.id

            logger.warning(
                "Slow update detected update_id=%s event_type=%s user_id=%s duration_ms=%.1f",
                update_id,
                type(event).__name__,
                user_id,
                duration_seconds * 1000,
            )
