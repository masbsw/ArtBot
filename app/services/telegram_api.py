import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from time import monotonic
from typing import Any, TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import CallbackQuery, InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo, Message

RetryResultT = TypeVar("RetryResultT")
MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaPhoto | InputMediaVideo

logger = logging.getLogger(__name__)
RETRY_DELAYS = (1, 2, 3)
TELEGRAM_API_CONCURRENCY_LIMIT = 5
CALLBACK_MIN_INTERVAL_SECONDS = 1.5
telegram_api_semaphore = asyncio.Semaphore(TELEGRAM_API_CONCURRENCY_LIMIT)
_callback_rate_limit_lock = asyncio.Lock()
_callback_last_pressed_at: dict[int, float] = {}


async def retry_telegram_request(
    operation_name: str,
    request: Callable[..., Awaitable[RetryResultT]],
    *args: Any,
    **kwargs: Any,
) -> RetryResultT | None:
    for attempt in range(1, len(RETRY_DELAYS) + 2):
        try:
            async with telegram_api_semaphore:
                return await request(*args, **kwargs)
        except TelegramNetworkError:
            if attempt > len(RETRY_DELAYS):
                logger.exception(
                    "Telegram request failed after retries operation=%s attempts=%s",
                    operation_name,
                    attempt,
                )
                return None

            delay = RETRY_DELAYS[attempt - 1]
            logger.warning(
                "Telegram request timeout operation=%s attempt=%s retry_in=%ss",
                operation_name,
                attempt,
                delay,
            )
            await asyncio.sleep(delay)


async def check_callback_rate_limit(
    callback: CallbackQuery,
    min_interval_seconds: float = CALLBACK_MIN_INTERVAL_SECONDS,
) -> bool:
    if callback.from_user is None:
        return True

    now = monotonic()
    async with _callback_rate_limit_lock:
        last_pressed_at = _callback_last_pressed_at.get(callback.from_user.id)
        if last_pressed_at is not None and now - last_pressed_at < min_interval_seconds:
            return False
        _callback_last_pressed_at[callback.from_user.id] = now
        if len(_callback_last_pressed_at) > 10_000:
            stale_before = now - 300
            stale_user_ids = [
                user_id
                for user_id, pressed_at in _callback_last_pressed_at.items()
                if pressed_at < stale_before
            ]
            for user_id in stale_user_ids:
                _callback_last_pressed_at.pop(user_id, None)
        return True


async def enforce_callback_rate_limit(
    callback: CallbackQuery,
    min_interval_seconds: float = CALLBACK_MIN_INTERVAL_SECONDS,
) -> bool:
    allowed = await check_callback_rate_limit(callback, min_interval_seconds)
    if allowed:
        return True
    await safe_callback_answer(
        callback,
        "Слишком часто. Попробуйте ещё раз через секунду.",
        show_alert=False,
    )
    return False


async def safe_answer(
    message: Message,
    text: str,
    **kwargs: Any,
) -> Message | None:
    return await retry_telegram_request(
        "message.answer",
        message.answer,
        text,
        **kwargs,
    )


async def safe_answer_photo(
    message: Message,
    photo: str,
    **kwargs: Any,
) -> Message | None:
    return await retry_telegram_request(
        "message.answer_photo",
        message.answer_photo,
        photo,
        **kwargs,
    )


async def safe_answer_media_group(
    message: Message,
    media: Sequence[MediaGroupItem],
    **kwargs: Any,
) -> list[Message]:
    result = await retry_telegram_request(
        "message.answer_media_group",
        message.answer_media_group,
        media,
        **kwargs,
    )
    return list(result) if result is not None else []


async def safe_edit_text(
    message: Message,
    text: str,
    **kwargs: Any,
) -> Message | bool | None:
    return await retry_telegram_request(
        "message.edit_text",
        message.edit_text,
        text,
        **kwargs,
    )


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    **kwargs: Any,
) -> Message | None:
    return await retry_telegram_request(
        "bot.send_message",
        bot.send_message,
        chat_id,
        text,
        **kwargs,
    )


async def safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    **kwargs: Any,
) -> bool:
    result = await retry_telegram_request(
        "callback.answer",
        callback.answer,
        text,
        **kwargs,
    )
    return result is not None
