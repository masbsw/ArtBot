import asyncio
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from app.services.telegram_api import safe_callback_answer


def extract_user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message) and event.from_user is not None:
        return event.from_user.id
    if isinstance(event, CallbackQuery) and event.from_user is not None:
        return event.from_user.id
    if isinstance(event, Update):
        inner_event = event.event
        if isinstance(inner_event, Message) and inner_event.from_user is not None:
            return inner_event.from_user.id
        if isinstance(inner_event, CallbackQuery) and inner_event.from_user is not None:
            return inner_event.from_user.id
    return None


class PerUserLockMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()
        self._inflight_callbacks: set[tuple[int, str]] = set()

    async def _get_lock(self, user_id: int) -> asyncio.Lock:
        async with self._registry_lock:
            lock = self._locks.get(user_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[user_id] = lock
            return lock

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = extract_user_id(event)
        if user_id is None:
            return await handler(event, data)

        callback_key: tuple[int, str] | None = None
        if isinstance(event, CallbackQuery) and event.data:
            callback_key = (user_id, event.data)
            async with self._registry_lock:
                if callback_key in self._inflight_callbacks:
                    await safe_callback_answer(event, "Уже загружаю, подождите…")
                    return None
                self._inflight_callbacks.add(callback_key)

        lock = await self._get_lock(user_id)
        try:
            async with lock:
                return await handler(event, data)
        finally:
            if callback_key is not None:
                async with self._registry_lock:
                    self._inflight_callbacks.discard(callback_key)
