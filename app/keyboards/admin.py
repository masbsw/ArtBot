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
ADMIN_NEXT_CALLBACK = "admin:page:next"
ADMIN_FIND_PROFILE_CALLBACK = "admin:find_profile"
ADMIN_LIST_RECENT_CALLBACK = "admin:view_recent_profiles"
ADMIN_LIST_NO_PHOTOS_CALLBACK = "admin:view_profiles_without_photos"
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
            [
                InlineKeyboardButton(
                    text="🔍 Найти анкету",
                    callback_data=ADMIN_FIND_PROFILE_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆕 Новые за 7 дней",
                    callback_data=ADMIN_LIST_RECENT_CALLBACK,
                ),
                InlineKeyboardButton(
                    text="🖼 Без фото",
                    callback_data=ADMIN_LIST_NO_PHOTOS_CALLBACK,
                ),
            ],
        ]
    )


def admin_profile_actions_keyboard(
    profile_id: int,
    user_id: int,
    complaints_count: int = 0,
) -> InlineKeyboardMarkup:
    rows = []
    if complaints_count > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📄 Жалобы",
                    callback_data=f"{ADMIN_COMPLAINTS_VIEW_PREFIX}{profile_id}:0",
                )
            ]
        )
    rows.extend(
        [
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
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def admin_page_navigation_keyboard(has_next_page: bool) -> InlineKeyboardMarkup | None:
    if not has_next_page:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Следующие 10 ➡️",
                    callback_data=ADMIN_NEXT_CALLBACK,
                )
            ]
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
