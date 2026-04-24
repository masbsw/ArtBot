import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import CallbackQuery, InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo, Message

RetryResultT = TypeVar("RetryResultT")
MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaPhoto | InputMediaVideo

logger = logging.getLogger(__name__)
RETRY_DELAYS = (1, 2, 3)


async def retry_telegram_request(
    operation_name: str,
    request: Callable[..., Awaitable[RetryResultT]],
    *args: Any,
    **kwargs: Any,
) -> RetryResultT | None:
    for attempt in range(1, len(RETRY_DELAYS) + 2):
        try:
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
