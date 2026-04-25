import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from time import monotonic
from typing import Any, TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.types import CallbackQuery, InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo, Message

RetryResultT = TypeVar("RetryResultT")
MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaPhoto | InputMediaVideo

logger = logging.getLogger(__name__)
RETRY_DELAYS = (1, 2, 3)
FSM_RETRY_DELAYS = (1,)
TELEGRAM_API_CONCURRENCY_LIMIT = 15
DEFAULT_TELEGRAM_REQUEST_TIMEOUT_SECONDS = 10
MEDIA_GROUP_REQUEST_TIMEOUT_SECONDS = 20
CALLBACK_MIN_INTERVAL_SECONDS = 1.5
CALLBACK_ANSWER_TIMEOUT_SECONDS = 3
FSM_ANSWER_TIMEOUT_SECONDS = 7
telegram_api_semaphore = asyncio.Semaphore(TELEGRAM_API_CONCURRENCY_LIMIT)
_callback_rate_limit_lock = asyncio.Lock()
_callback_last_pressed_at: dict[int, float] = {}


def _is_message_not_modified_error(error: TelegramBadRequest) -> bool:
    message = str(error).lower()
    return "message is not modified" in message


def _is_expired_callback_error(error: TelegramBadRequest) -> bool:
    message = str(error).lower()
    return "query is too old" in message or "query id is invalid" in message


async def retry_telegram_request(
    operation_name: str,
    request: Callable[..., Awaitable[RetryResultT]],
    *args: Any,
    **kwargs: Any,
) -> RetryResultT | None:
    request_kwargs = dict(kwargs)
    request_kwargs.setdefault("request_timeout", DEFAULT_TELEGRAM_REQUEST_TIMEOUT_SECONDS)
    for attempt in range(1, len(RETRY_DELAYS) + 2):
        try:
            async with telegram_api_semaphore:
                return await asyncio.wait_for(
                    request(*args, **request_kwargs),
                    timeout=request_kwargs["request_timeout"],
                )
        except (TelegramNetworkError, TimeoutError):
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
        except TelegramBadRequest as exc:
            if _is_message_not_modified_error(exc):
                logger.debug("Ignoring TelegramBadRequest operation=%s reason=not_modified", operation_name)
                return None
            if _is_expired_callback_error(exc):
                logger.debug("Ignoring TelegramBadRequest operation=%s reason=expired_callback", operation_name)
                return None
            raise


async def retry_fsm_telegram_request(
    operation_name: str,
    request: Callable[..., Awaitable[RetryResultT]],
    *args: Any,
    **kwargs: Any,
) -> RetryResultT | None:
    request_kwargs = dict(kwargs)
    request_kwargs.setdefault("request_timeout", FSM_ANSWER_TIMEOUT_SECONDS)
    for attempt in range(1, len(FSM_RETRY_DELAYS) + 2):
        try:
            async with telegram_api_semaphore:
                return await asyncio.wait_for(
                    request(*args, **request_kwargs),
                    timeout=request_kwargs["request_timeout"],
                )
        except (TelegramNetworkError, TimeoutError):
            if attempt > len(FSM_RETRY_DELAYS):
                logger.warning(
                    "FSM telegram request failed operation=%s attempts=%s",
                    operation_name,
                    attempt,
                )
                return None

            delay = FSM_RETRY_DELAYS[attempt - 1]
            logger.warning(
                "FSM telegram request timeout operation=%s attempt=%s retry_in=%ss",
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


async def safe_fsm_answer(
    message: Message,
    text: str,
    **kwargs: Any,
) -> Message | None:
    return await retry_fsm_telegram_request(
        "message.answer.fsm",
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
    request_kwargs = dict(kwargs)
    request_kwargs.setdefault("request_timeout", MEDIA_GROUP_REQUEST_TIMEOUT_SECONDS)
    result = await retry_telegram_request(
        "message.answer_media_group",
        message.answer_media_group,
        media,
        **request_kwargs,
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
    try:
        async with telegram_api_semaphore:
            result = await asyncio.wait_for(
                callback.answer(
                    text,
                    request_timeout=CALLBACK_ANSWER_TIMEOUT_SECONDS,
                    **kwargs,
                ),
                timeout=CALLBACK_ANSWER_TIMEOUT_SECONDS,
            )
        return result is not None
    except (TelegramNetworkError, TimeoutError):
        logger.warning(
            "Telegram callback answer timed out text=%s",
            text,
        )
        return False
    except TelegramBadRequest as exc:
        if _is_expired_callback_error(exc):
            logger.debug("Ignoring expired callback answer text=%s", text)
            return False
        raise
