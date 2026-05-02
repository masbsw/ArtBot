from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.services.artist_profiles import humanize_deadline_category

FORMAT_OPTIONS = [
    ("Digital", "digital"),
    ("Traditional", "traditional"),
    ("Animation", "animation"),
    ("3D", "3d"),
]

CURRENCY_OPTIONS = ["USD", "EUR", "CNY", "RUB", "JPY", "KZT", "BYN", "UAH"]

DEADLINE_CATEGORY_OPTIONS = [
    "1-5 hours",
    "1-5 days",
    "1-5 weeks",
    "1-5 months",
    "free deadline",
]

FORMAT_CALLBACK_PREFIX = "artist:format:"
CURRENCY_CALLBACK_PREFIX = "artist:currency:"
DEADLINE_CALLBACK_PREFIX = "artist:deadline:"
EDIT_PROFILE_CALLBACK = "artist:edit_profile"
EDIT_PROFILE_FIELD_CALLBACK = "artist:edit_profile_field"
EDIT_FIELD_CALLBACK_PREFIX = "artist:edit_field:"
DISABLE_PROFILE_CALLBACK = "artist:disable_profile"
DISABLE_PROFILE_CONFIRM_CALLBACK = "artist:disable_profile:confirm"
DISABLE_PROFILE_CANCEL_CALLBACK = "artist:disable_profile:cancel"

EDITABLE_PROFILE_FIELDS = [
    ("Формат", "format"),
    ("Портфолио", "portfolio"),
    ("Описание", "description"),
    ("Прайс", "price"),
    ("Сроки", "deadline"),
    ("Контакты", "contacts"),
]
CANCEL_BUTTON_TEXT = "❌ Отменить"


def build_option_keyboard(
    options: list[str],
    callback_prefix: str,
    current_value: str | None = None,
    label_getter=None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for option in options:
        display_label = label_getter(option) if label_getter is not None else option
        label = f"{display_label} •" if option == current_value else display_label
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{callback_prefix}{option}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_keyboard(current_value: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, value in FORMAT_OPTIONS:
        button_label = f"{label} •" if value == current_value else label
        rows.append(
            [
                InlineKeyboardButton(
                    text=button_label,
                    callback_data=f"{FORMAT_CALLBACK_PREFIX}{value}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def currency_keyboard(current_value: str | None = None) -> InlineKeyboardMarkup:
    return build_option_keyboard(CURRENCY_OPTIONS, CURRENCY_CALLBACK_PREFIX, current_value)


def deadline_category_keyboard(current_value: str | None = None) -> InlineKeyboardMarkup:
    return build_option_keyboard(
        DEADLINE_CATEGORY_OPTIONS,
        DEADLINE_CALLBACK_PREFIX,
        current_value,
        label_getter=humanize_deadline_category,
    )


def portfolio_finish_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Готово")],
            [KeyboardButton(text=CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def profile_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Полностью изменить анкету",
                    callback_data=EDIT_PROFILE_CALLBACK,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧩 Редактировать отдельно",
                    callback_data=EDIT_PROFILE_FIELD_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Отключить анкету",
                    callback_data=DISABLE_PROFILE_CALLBACK,
                )
            ],
        ]
    )


def disable_profile_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да",
                    callback_data=DISABLE_PROFILE_CONFIRM_CALLBACK,
                ),
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data=DISABLE_PROFILE_CANCEL_CALLBACK,
                ),
            ]
        ]
    )


def profile_field_selection_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, value in EDITABLE_PROFILE_FIELDS:
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{EDIT_FIELD_CALLBACK_PREFIX}{value}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
