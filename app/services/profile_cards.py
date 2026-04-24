from html import escape
import logging
from time import perf_counter

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto, Message

from app.db.models import ArtistProfile
from app.services.artist_profiles import (
    build_price_display,
    display_value,
    humanize_deadline_category,
    humanize_format,
)
from app.services.telegram_api import (
    safe_answer,
    safe_answer_media_group,
    safe_answer_photo,
)

logger = logging.getLogger(__name__)


def build_profile_caption(profile: ArtistProfile, title: str = "Моя анкета") -> str:
    images_count = len(profile.portfolio_images)
    return (
        f"<b>{escape(title)}</b>\n\n"
        f" Формат: {escape(humanize_format(profile.format))}\n"
        f" Описание: {escape(display_value(profile.description))}\n"
        f" Прайс: {escape(build_price_display(profile.price_text, profile.currency))}\n"
        f" Сроки: {escape(humanize_deadline_category(profile.deadline_category))}\n\n"
        f"📩 Контакты: {escape(display_value(profile.contacts_text))}\n"
        f"❤️ Лайки: {profile.likes_count}\n"
    )


async def send_profile_card(
    message: Message,
    profile: ArtistProfile,
    reply_markup: InlineKeyboardMarkup | None = None,
    title: str = "Моя анкета",
    extra_text: str | None = None,
) -> list[Message]:
    started_at = perf_counter()
    caption = build_profile_caption(profile, title=title)
    if extra_text:
        caption = f"{caption}\n\n{extra_text}"
    images = [
        item
        for item in profile.portfolio_images
        if item.telegram_file_id and item.telegram_file_id.strip()
    ]

    if not images:
        sent = await safe_answer(message, caption, reply_markup=reply_markup)
        logger.info(
            "send_profile_card profile_id=%s mode=text image_count=0 duration_ms=%.1f",
            profile.id,
            (perf_counter() - started_at) * 1000,
        )
        return [sent] if sent is not None else []

    if len(images) == 1:
        try:
            sent = await safe_answer_photo(
                message,
                images[0].telegram_file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
        except TelegramBadRequest:
            logger.warning(
                "send_profile_card invalid single photo profile_id=%s file_id=%s fallback=text",
                profile.id,
                images[0].telegram_file_id,
            )
            sent = await safe_answer(message, caption, reply_markup=reply_markup)
        logger.info(
            "send_profile_card profile_id=%s mode=single image_count=1 duration_ms=%.1f",
            profile.id,
            (perf_counter() - started_at) * 1000,
        )
        return [sent] if sent is not None else []

    media = []
    for index, item in enumerate(images):
        if index == 0:
            media.append(
                InputMediaPhoto(
                    media=item.telegram_file_id,
                    caption=caption,
                )
            )
            continue
        media.append(InputMediaPhoto(media=item.telegram_file_id))

    try:
        sent_messages = await safe_answer_media_group(message, media)
        mode = "media_group"
    except TelegramBadRequest:
        logger.warning(
            "send_profile_card media_group_failed profile_id=%s image_count=%s fallback=single",
            profile.id,
            len(images),
        )
        fallback_message = await safe_answer_photo(
            message,
            images[0].telegram_file_id,
            caption=caption,
        )
        sent_messages = [fallback_message] if fallback_message is not None else []
        mode = "single_fallback"
    if reply_markup is not None:
        actions_message = await safe_answer(
            message,
            "Доступные действия:",
            reply_markup=reply_markup,
        )
        if actions_message is not None:
            sent_messages.append(actions_message)
    logger.info(
        "send_profile_card profile_id=%s mode=%s image_count=%s duration_ms=%.1f",
        profile.id,
        mode,
        len(images),
        (perf_counter() - started_at) * 1000,
    )
    return sent_messages
