from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

ADMIN_LIST_ALL_CALLBACK = "admin:view_all_profiles"
ADMIN_LIST_HIDDEN_CALLBACK = "admin:view_hidden_profiles"
ADMIN_LIST_COMPLAINTS_CALLBACK = "admin:view_reported_profiles"
ADMIN_BROADCAST_CALLBACK = "admin:broadcast"
ADMIN_DELETE_PROFILE_PREFIX = "admin:delete:"
ADMIN_BLOCK_USER_PREFIX = "admin:block:"
ADMIN_UNBLOCK_USER_PREFIX = "admin:unblock:"
ADMIN_BROADCAST_CONFIRM_CALLBACK = "admin:broadcast:confirm"
ADMIN_BROADCAST_CANCEL_CALLBACK = "admin:broadcast:cancel"
ADMIN_NEXT_CALLBACK = "admin:next"
ADMIN_COMPLAINTS_VIEW_PREFIX = "admin:complaints:view:"
ADMIN_COMPLAINTS_PREV_PREFIX = "admin:complaints:prev:"
ADMIN_COMPLAINTS_NEXT_PREFIX = "admin:complaints:next:"


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Просмотреть все анкеты",
                    callback_data=ADMIN_LIST_ALL_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Просмотреть скрытые анкеты",
                    callback_data=ADMIN_LIST_HIDDEN_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Просмотреть анкеты с жалобами",
                    callback_data=ADMIN_LIST_COMPLAINTS_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Сделать рассылку",
                    callback_data=ADMIN_BROADCAST_CALLBACK,
                )
            ],
        ]
    )


def admin_profile_actions_keyboard(
    profile_id: int,
    user_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Следующая ➡️",
                    callback_data=ADMIN_NEXT_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Удалить",
                    callback_data=f"{ADMIN_DELETE_PROFILE_PREFIX}{profile_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Заблокировать",
                    callback_data=f"{ADMIN_BLOCK_USER_PREFIX}{user_id}",
                )
            ],
        ]
    )


def admin_profile_moderation_keyboard(
    profile_id: int,
    user_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Удалить",
                    callback_data=f"{ADMIN_DELETE_PROFILE_PREFIX}{profile_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Заблокировать",
                    callback_data=f"{ADMIN_BLOCK_USER_PREFIX}{user_id}",
                )
            ],
        ]
    )


def admin_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить",
                    callback_data=ADMIN_BROADCAST_CONFIRM_CALLBACK,
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=ADMIN_BROADCAST_CANCEL_CALLBACK,
                ),
            ]
        ]
    )


def admin_complaints_navigation_keyboard(
    profile_id: int,
    offset: int,
    total_count: int,
    page_size: int,
) -> InlineKeyboardMarkup | None:
    if total_count <= page_size:
        return None

    rows = [[]]
    if offset > 0:
        rows[0].append(
            InlineKeyboardButton(
                text="⬅️ Предыдущие",
                callback_data=f"{ADMIN_COMPLAINTS_PREV_PREFIX}{profile_id}:{offset}",
            )
        )
    if offset + page_size < total_count:
        rows[0].append(
            InlineKeyboardButton(
                text="Следующие ➡️",
                callback_data=f"{ADMIN_COMPLAINTS_NEXT_PREFIX}{profile_id}:{offset}",
            )
        )
    if not rows[0]:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)
