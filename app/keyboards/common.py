from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.db.models import UserRole

EDIT_PROFILE_BUTTON = "✏️ Изменить анкету"
EDIT_PROFILE_FIELD_BUTTON = "🧩 Поля"
MY_PROFILE_BUTTON = "👁 Моя анкета"
SET_FILTERS_BUTTON = "⚙️ Фильтры"
VIEW_PROFILES_BUTTON = "🔎 Смотреть анкеты"
SAVED_PROFILES_BUTTON = "⭐ Сохраненные"
CHANGE_ROLE_BUTTON = "🔁 Сменить роль"


def artist_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=EDIT_PROFILE_BUTTON), KeyboardButton(text=EDIT_PROFILE_FIELD_BUTTON)],
            [KeyboardButton(text=MY_PROFILE_BUTTON), KeyboardButton(text=SAVED_PROFILES_BUTTON)],
            [KeyboardButton(text=VIEW_PROFILES_BUTTON)],
            [KeyboardButton(text=CHANGE_ROLE_BUTTON)],
        ],
        resize_keyboard=True,
    )


def client_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SET_FILTERS_BUTTON), KeyboardButton(text=VIEW_PROFILES_BUTTON)],
            [KeyboardButton(text=SAVED_PROFILES_BUTTON)],
            [KeyboardButton(text=CHANGE_ROLE_BUTTON)],
        ],
        resize_keyboard=True,
    )


def role_menu_keyboard(role: UserRole) -> ReplyKeyboardMarkup:
    if role == UserRole.ARTIST:
        return artist_menu_keyboard()
    return client_menu_keyboard()
