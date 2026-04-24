from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.artist import (
    DEADLINE_CATEGORY_OPTIONS,
    FORMAT_OPTIONS,
    build_option_keyboard,
)
from app.services.artist_profiles import humanize_deadline_category

CLIENT_FORMAT_CALLBACK_PREFIX = "client:format:"
CLIENT_DEADLINE_CALLBACK_PREFIX = "client:deadline:"
EDIT_FILTERS_CALLBACK = "client:edit_filters"
FIND_ARTISTS_CALLBACK = "client:find_artists"
LIKE_PROFILE_CALLBACK_PREFIX = "client:action:like:"
SAVE_PROFILE_CALLBACK_PREFIX = "client:action:save:"
CONTACT_PROFILE_CALLBACK_PREFIX = "client:action:contact:"
SKIP_PROFILE_CALLBACK_PREFIX = "client:action:skip:"
COMPLAIN_PROFILE_CALLBACK_PREFIX = "client:action:complain:"
SAVED_PROFILE_DELETE_CALLBACK_PREFIX = "client:saved:delete:"
SAVED_PROFILE_PREV_CALLBACK_PREFIX = "client:saved:prev:"
SAVED_PROFILE_NEXT_CALLBACK_PREFIX = "client:saved:next:"


def client_format_keyboard(current_value: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, value in FORMAT_OPTIONS:
        button_label = f"{label} •" if value == current_value else label
        rows.append(
            [
                InlineKeyboardButton(
                    text=button_label,
                    callback_data=f"{CLIENT_FORMAT_CALLBACK_PREFIX}{value}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def client_deadline_keyboard(current_value: str | None = None) -> InlineKeyboardMarkup:
    return build_option_keyboard(
        DEADLINE_CATEGORY_OPTIONS,
        CLIENT_DEADLINE_CALLBACK_PREFIX,
        current_value,
        label_getter=humanize_deadline_category,
    )


def client_filters_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Редактировать фильтры",
                    callback_data=EDIT_FILTERS_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Искать художников",
                    callback_data=FIND_ARTISTS_CALLBACK,
                )
            ],
        ]
    )


def client_profile_actions_keyboard(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ Лайк",
                    callback_data=f"{LIKE_PROFILE_CALLBACK_PREFIX}{profile_id}",
                ),
                InlineKeyboardButton(
                    text="⭐ Сохранить",
                    callback_data=f"{SAVE_PROFILE_CALLBACK_PREFIX}{profile_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Связаться",
                    callback_data=f"{CONTACT_PROFILE_CALLBACK_PREFIX}{profile_id}",
                ),
                InlineKeyboardButton(
                    text="⏭ Скип",
                    callback_data=f"{SKIP_PROFILE_CALLBACK_PREFIX}{profile_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Пожаловаться",
                    callback_data=f"{COMPLAIN_PROFILE_CALLBACK_PREFIX}{profile_id}",
                )
            ],
        ]
    )


def saved_profile_actions_keyboard(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"{SAVED_PROFILE_DELETE_CALLBACK_PREFIX}{profile_id}",
                ),
                InlineKeyboardButton(
                    text="💬 Связаться",
                    callback_data=f"{CONTACT_PROFILE_CALLBACK_PREFIX}{profile_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Предыдущая",
                    callback_data=f"{SAVED_PROFILE_PREV_CALLBACK_PREFIX}{profile_id}",
                ),
                InlineKeyboardButton(
                    text="Следующая ➡️",
                    callback_data=f"{SAVED_PROFILE_NEXT_CALLBACK_PREFIX}{profile_id}",
                ),
            ],
        ]
    )
