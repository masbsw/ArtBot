from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import UserRole

CHANGE_ROLE_CALLBACK = "start:change_role"
ROLE_CALLBACK_PREFIX = "start:set_role:"

ROLE_LABELS: dict[UserRole, str] = {
    UserRole.ARTIST: "Художник",
    UserRole.CLIENT: "Заказчик",
    UserRole.ADMIN: "Администратор",
}


def role_selection_keyboard(current_role: UserRole | None = None) -> InlineKeyboardMarkup:
    artist_label = ROLE_LABELS[UserRole.ARTIST]
    client_label = ROLE_LABELS[UserRole.CLIENT]

    if current_role == UserRole.ARTIST:
        artist_label = f"{artist_label} •"
    if current_role == UserRole.CLIENT:
        client_label = f"{client_label} •"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=artist_label,
                    callback_data=f"{ROLE_CALLBACK_PREFIX}{UserRole.ARTIST.value}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=client_label,
                    callback_data=f"{ROLE_CALLBACK_PREFIX}{UserRole.CLIENT.value}",
                )
            ],
        ]
    )


def change_role_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сменить роль",
                    callback_data=CHANGE_ROLE_CALLBACK,
                )
            ]
        ]
    )
