from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.db.models import ArtistProfileStatus

ADMIN_LIST_ALL_CALLBACK = "admin:list:all"
ADMIN_LIST_HIDDEN_CALLBACK = "admin:list:hidden"
ADMIN_LIST_COMPLAINTS_CALLBACK = "admin:list:complaints"
ADMIN_BROADCAST_CALLBACK = "admin:broadcast"
ADMIN_RESTORE_PROFILE_PREFIX = "admin:restore:"
ADMIN_DELETE_PROFILE_PREFIX = "admin:delete:"
ADMIN_BLOCK_USER_PREFIX = "admin:block:"
ADMIN_UNBLOCK_USER_PREFIX = "admin:unblock:"
ADMIN_BROADCAST_CONFIRM_CALLBACK = "admin:broadcast:confirm"
ADMIN_BROADCAST_CANCEL_CALLBACK = "admin:broadcast:cancel"
ADMIN_NAV_PREV_PREFIX = "admin:nav:prev:"
ADMIN_NAV_NEXT_PREFIX = "admin:nav:next:"
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
    status: ArtistProfileStatus,
    scope: str,
    has_complaints: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status in {ArtistProfileStatus.HIDDEN, ArtistProfileStatus.MODERATION}:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Восстановить",
                    callback_data=f"{ADMIN_RESTORE_PROFILE_PREFIX}{profile_id}",
                ),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Удалить",
                callback_data=f"{ADMIN_DELETE_PROFILE_PREFIX}{profile_id}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="Заблокировать пользователя",
                callback_data=f"{ADMIN_BLOCK_USER_PREFIX}{user_id}",
            )
        ]
    )
    if has_complaints:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📄 Жалобы",
                    callback_data=f"{ADMIN_COMPLAINTS_VIEW_PREFIX}{profile_id}:0",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Предыдущая",
                callback_data=f"{ADMIN_NAV_PREV_PREFIX}{scope}:{profile_id}",
            ),
            InlineKeyboardButton(
                text="Следующая ➡️",
                callback_data=f"{ADMIN_NAV_NEXT_PREFIX}{scope}:{profile_id}",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


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
