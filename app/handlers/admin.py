import asyncio
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from contextlib import suppress

from app.config import Settings
from app.db.session import Database
from app.keyboards.admin import (
    ADMIN_BROADCAST_CALLBACK,
    ADMIN_BROADCAST_CANCEL_CALLBACK,
    ADMIN_BROADCAST_CONFIRM_CALLBACK,
    ADMIN_BLOCK_USER_PREFIX,
    ADMIN_COMPLAINTS_NEXT_PREFIX,
    ADMIN_COMPLAINTS_PREV_PREFIX,
    ADMIN_COMPLAINTS_VIEW_PREFIX,
    ADMIN_DELETE_PROFILE_PREFIX,
    ADMIN_LIST_ALL_CALLBACK,
    ADMIN_LIST_COMPLAINTS_CALLBACK,
    ADMIN_LIST_HIDDEN_CALLBACK,
    ADMIN_NAV_NEXT_PREFIX,
    ADMIN_NAV_PREV_PREFIX,
    ADMIN_RESTORE_PROFILE_PREFIX,
    ADMIN_UNBLOCK_USER_PREFIX,
    admin_complaints_navigation_keyboard,
    admin_broadcast_confirm_keyboard,
    admin_panel_keyboard,
    admin_profile_actions_keyboard,
)
from app.services.admin_profiles import (
    admin_profile_extra,
    delete_profile,
    list_all_user_telegram_ids,
    list_profile_complaints,
    list_all_profiles,
    list_hidden_profiles,
    list_profiles_with_complaints,
    restore_profile,
    set_user_blocked,
)
from app.services.profile_cards import send_profile_card
from app.services.telegram_api import (
    enforce_callback_rate_limit,
    safe_answer,
    safe_callback_answer,
    safe_delete_message,
    safe_edit_text,
    safe_send_message,
)
from app.states.admin import AdminFlow

router = Router(name="admin")

ADMIN_VIEW_MESSAGE_IDS_KEY = "admin_view_message_ids"
BROADCAST_BATCH_SIZE = 20
BROADCAST_BATCH_DELAY_SECONDS = 1


def is_admin(telegram_id: int, settings: Settings) -> bool:
    return telegram_id in settings.admin_ids


async def ensure_admin_message(
    message: Message,
    settings: Settings,
) -> bool:
    if message.from_user is None or not is_admin(message.from_user.id, settings):
        await safe_answer(message, "Доступ только для администраторов.")
        return False
    return True


async def ensure_admin_callback(
    callback: CallbackQuery,
    settings: Settings,
) -> bool:
    if callback.from_user is None:
        await safe_callback_answer(callback)
        return False
    if not await enforce_callback_rate_limit(callback):
        return False
    if not is_admin(callback.from_user.id, settings):
        await safe_callback_answer(callback, "Доступ только для администраторов.", show_alert=True)
        return False
    return True


async def get_admin_profiles_by_scope(
    session,
    scope: str,
) -> tuple[list, str]:
    if scope == "all":
        return await list_all_profiles(session), "Анкет пока нет."
    if scope == "hidden":
        return await list_hidden_profiles(session), "Скрытых анкет нет."
    return await list_profiles_with_complaints(session), "Анкет с жалобами нет."


async def get_admin_view_message_ids(state: FSMContext) -> list[int]:
    data = await state.get_data()
    message_ids = data.get(ADMIN_VIEW_MESSAGE_IDS_KEY, [])
    if not isinstance(message_ids, list):
        return []
    return [message_id for message_id in message_ids if isinstance(message_id, int)]


async def delete_admin_view_messages(
    message: Message,
    state: FSMContext,
    message_ids: list[int] | None = None,
) -> None:
    should_clear_state = message_ids is None
    if message_ids is None:
        message_ids = await get_admin_view_message_ids(state)

    for message_id in message_ids:
        with suppress(TelegramBadRequest):
            await safe_delete_message(message.bot, message.chat.id, message_id)

    if should_clear_state:
        await state.update_data(admin_view_message_ids=[])


async def show_admin_profile(
    message: Message,
    state: FSMContext,
    profile,
    scope: str,
    current_index: int,
    total_count: int,
) -> None:
    old_message_ids = await get_admin_view_message_ids(state)
    reply_markup = admin_profile_actions_keyboard(
        profile_id=profile.id,
        user_id=profile.user_id,
        status=profile.status,
        scope=scope,
        has_complaints=profile.complaints_count > 0,
    )
    sent_messages = await send_profile_card(
        message,
        profile,
        reply_markup=None,
        title=f"Анкета № {current_index}/{total_count}",
        extra_text=admin_profile_extra(profile),
    )
    actions_message = await safe_answer(
        message,
        "Доступные действия:",
        reply_markup=reply_markup,
    )
    if actions_message is not None:
        sent_messages.append(actions_message)
    await state.update_data(
        admin_view_message_ids=[item.message_id for item in sent_messages],
    )
    await delete_admin_view_messages(message, state, old_message_ids)


async def send_admin_profiles(
    message: Message,
    profiles: list,
    empty_text: str,
    state: FSMContext,
    scope: str,
) -> None:
    if not profiles:
        await delete_admin_view_messages(message, state)
        await safe_answer(message, empty_text)
        return
    await show_admin_profile(message, state, profiles[0], scope, 1, len(profiles))


@router.message(Command("admin"))
async def admin_panel_command(
    message: Message,
    settings: Settings,
) -> None:
    if not await ensure_admin_message(message, settings):
        return
    await safe_answer(message, "Панель администратора:", reply_markup=admin_panel_keyboard())


@router.message(Command("admin_profiles"))
async def admin_profiles_command(
    message: Message,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await ensure_admin_message(message, settings):
        return
    async with db.session() as session:
        profiles = await list_all_profiles(session)
    await send_admin_profiles(message, profiles, "Анкет пока нет.", state, "all")


@router.message(Command("admin_hidden"))
async def admin_hidden_command(
    message: Message,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await ensure_admin_message(message, settings):
        return
    async with db.session() as session:
        profiles = await list_hidden_profiles(session)
    await send_admin_profiles(message, profiles, "Скрытых анкет нет.", state, "hidden")


@router.message(Command("admin_complaints"))
async def admin_complaints_command(
    message: Message,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await ensure_admin_message(message, settings):
        return
    async with db.session() as session:
        profiles = await list_profiles_with_complaints(session)
    await send_admin_profiles(message, profiles, "Анкет с жалобами нет.", state, "complaints")


@router.message(Command("broadcast"))
async def broadcast_command(
    message: Message,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await ensure_admin_message(message, settings):
        return
    await state.clear()
    await state.set_state(AdminFlow.waiting_for_broadcast)
    await safe_answer(message, "Отправьте текст рассылки одним сообщением.")


@router.callback_query(F.data == ADMIN_LIST_ALL_CALLBACK)
async def admin_list_all_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.message is None or not await ensure_admin_callback(callback, settings):
        return
    await safe_callback_answer(callback)
    async with db.session() as session:
        profiles = await list_all_profiles(session)
    await send_admin_profiles(callback.message, profiles, "Анкет пока нет.", state, "all")


@router.callback_query(F.data == ADMIN_LIST_HIDDEN_CALLBACK)
async def admin_list_hidden_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.message is None or not await ensure_admin_callback(callback, settings):
        return
    await safe_callback_answer(callback)
    async with db.session() as session:
        profiles = await list_hidden_profiles(session)
    await send_admin_profiles(callback.message, profiles, "Скрытых анкет нет.", state, "hidden")


@router.callback_query(F.data == ADMIN_LIST_COMPLAINTS_CALLBACK)
async def admin_list_complaints_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.message is None or not await ensure_admin_callback(callback, settings):
        return
    await safe_callback_answer(callback)
    async with db.session() as session:
        profiles = await list_profiles_with_complaints(session)
    await send_admin_profiles(callback.message, profiles, "Анкет с жалобами нет.", state, "complaints")


def parse_admin_nav_payload(payload: str) -> tuple[str, int]:
    scope, profile_id = payload.split(":", maxsplit=1)
    return scope, int(profile_id)


def parse_admin_complaints_payload(payload: str) -> tuple[int, int]:
    profile_id, offset = payload.split(":", maxsplit=1)
    return int(profile_id), int(offset)


def build_complaints_text(profile_id: int, complaints: list, offset: int) -> str:
    lines = [f"📄 Жалобы на анкету #{profile_id}", ""]
    for index, complaint in enumerate(complaints, start=offset + 1):
        created_at = complaint.created_at.strftime("%d.%m.%Y %H:%M")
        lines.append(f"{index}. Текст жалобы: {escape(complaint.reason)}")
        lines.append(f"   Дата: {created_at}")
        lines.append(f"   От пользователя: Пользователь #{complaint.reporter_user_id}")
        lines.append("")
    return "\n".join(lines).strip()


@router.callback_query(F.data.startswith(ADMIN_NAV_PREV_PREFIX))
async def admin_nav_prev_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_admin_callback(callback, settings):
        return

    scope, current_profile_id = parse_admin_nav_payload(
        callback.data.removeprefix(ADMIN_NAV_PREV_PREFIX)
    )
    async with db.session() as session:
        profiles, empty_text = await get_admin_profiles_by_scope(session, scope)

    if not profiles:
        await delete_admin_view_messages(callback.message, state)
        await safe_callback_answer(callback)
        await safe_answer(callback.message, empty_text)
        return

    current_index = next((index for index, item in enumerate(profiles) if item.id == current_profile_id), 0)
    prev_index = (current_index - 1) % len(profiles)
    await safe_callback_answer(callback)
    await show_admin_profile(
        callback.message,
        state,
        profiles[prev_index],
        scope,
        prev_index + 1,
        len(profiles),
    )


@router.callback_query(F.data.startswith(ADMIN_NAV_NEXT_PREFIX))
async def admin_nav_next_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_admin_callback(callback, settings):
        return

    scope, current_profile_id = parse_admin_nav_payload(
        callback.data.removeprefix(ADMIN_NAV_NEXT_PREFIX)
    )
    async with db.session() as session:
        profiles, empty_text = await get_admin_profiles_by_scope(session, scope)

    if not profiles:
        await delete_admin_view_messages(callback.message, state)
        await safe_callback_answer(callback)
        await safe_answer(callback.message, empty_text)
        return

    current_index = next((index for index, item in enumerate(profiles) if item.id == current_profile_id), 0)
    next_index = (current_index + 1) % len(profiles)
    await safe_callback_answer(callback)
    await show_admin_profile(
        callback.message,
        state,
        profiles[next_index],
        scope,
        next_index + 1,
        len(profiles),
    )


@router.callback_query(F.data.startswith(ADMIN_COMPLAINTS_VIEW_PREFIX))
async def admin_complaints_view_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_admin_callback(callback, settings):
        return

    profile_id, offset = parse_admin_complaints_payload(
        callback.data.removeprefix(ADMIN_COMPLAINTS_VIEW_PREFIX)
    )
    async with db.session() as session:
        complaints, total_count = await list_profile_complaints(session, profile_id, offset=offset, limit=5)

    await safe_callback_answer(callback)
    if not complaints:
        await safe_answer(callback.message, "Жалоб на эту анкету нет.")
        return

    await safe_answer(
        callback.message,
        build_complaints_text(profile_id, complaints, offset),
        reply_markup=admin_complaints_navigation_keyboard(profile_id, offset, total_count, 5),
    )


@router.callback_query(F.data.startswith(ADMIN_COMPLAINTS_PREV_PREFIX))
async def admin_complaints_prev_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_admin_callback(callback, settings):
        return

    profile_id, current_offset = parse_admin_complaints_payload(
        callback.data.removeprefix(ADMIN_COMPLAINTS_PREV_PREFIX)
    )
    new_offset = max(current_offset - 5, 0)
    async with db.session() as session:
        complaints, total_count = await list_profile_complaints(session, profile_id, offset=new_offset, limit=5)

    await safe_callback_answer(callback)
    if not complaints:
        await safe_edit_text(callback.message, "Жалоб на эту анкету нет.")
        return

    await safe_edit_text(
        callback.message,
        build_complaints_text(profile_id, complaints, new_offset),
        reply_markup=admin_complaints_navigation_keyboard(profile_id, new_offset, total_count, 5),
    )


@router.callback_query(F.data.startswith(ADMIN_COMPLAINTS_NEXT_PREFIX))
async def admin_complaints_next_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_admin_callback(callback, settings):
        return

    profile_id, current_offset = parse_admin_complaints_payload(
        callback.data.removeprefix(ADMIN_COMPLAINTS_NEXT_PREFIX)
    )
    new_offset = current_offset + 5
    async with db.session() as session:
        complaints, total_count = await list_profile_complaints(session, profile_id, offset=new_offset, limit=5)

    await safe_callback_answer(callback)
    if not complaints:
        await safe_edit_text(callback.message, "Жалоб на эту анкету нет.")
        return

    await safe_edit_text(
        callback.message,
        build_complaints_text(profile_id, complaints, new_offset),
        reply_markup=admin_complaints_navigation_keyboard(profile_id, new_offset, total_count, 5),
    )


@router.callback_query(F.data == ADMIN_BROADCAST_CALLBACK)
async def admin_broadcast_callback(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.message is None or not await ensure_admin_callback(callback, settings):
        return
    await state.clear()
    await state.set_state(AdminFlow.waiting_for_broadcast)
    await safe_callback_answer(callback)
    await safe_answer(callback.message, "Отправьте текст рассылки одним сообщением.")


@router.callback_query(F.data.startswith(ADMIN_RESTORE_PROFILE_PREFIX))
async def restore_profile_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.data is None or not await ensure_admin_callback(callback, settings):
        return
    profile_id = int(callback.data.removeprefix(ADMIN_RESTORE_PROFILE_PREFIX))
    async with db.session() as session:
        success = await restore_profile(session, profile_id)
    await safe_callback_answer(callback, "Анкета восстановлена." if success else "Анкета не найдена.")


@router.callback_query(F.data.startswith(ADMIN_DELETE_PROFILE_PREFIX))
async def delete_profile_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.data is None or not await ensure_admin_callback(callback, settings):
        return
    profile_id = int(callback.data.removeprefix(ADMIN_DELETE_PROFILE_PREFIX))
    async with db.session() as session:
        success = await delete_profile(session, profile_id)
    await safe_callback_answer(callback, "Анкета удалена." if success else "Анкета не найдена.")


@router.callback_query(F.data.startswith(ADMIN_BLOCK_USER_PREFIX))
async def block_user_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.data is None or not await ensure_admin_callback(callback, settings):
        return
    user_id = int(callback.data.removeprefix(ADMIN_BLOCK_USER_PREFIX))
    async with db.session() as session:
        success = await set_user_blocked(session, user_id, True)
    await safe_callback_answer(
        callback,
        "Пользователь заблокирован." if success else "Пользователь не найден."
    )


@router.callback_query(F.data.startswith(ADMIN_UNBLOCK_USER_PREFIX))
async def unblock_user_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.data is None or not await ensure_admin_callback(callback, settings):
        return
    user_id = int(callback.data.removeprefix(ADMIN_UNBLOCK_USER_PREFIX))
    async with db.session() as session:
        success = await set_user_blocked(session, user_id, False)
    await safe_callback_answer(
        callback,
        "Пользователь разблокирован." if success else "Пользователь не найден."
    )


@router.message(AdminFlow.waiting_for_broadcast, F.text)
async def broadcast_text_message(
    message: Message,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await ensure_admin_message(message, settings):
        await state.clear()
        return
    broadcast_text = message.text.strip()
    if not broadcast_text:
        await safe_answer(message, "Текст рассылки не должен быть пустым.")
        return
    await state.update_data(broadcast_text=broadcast_text)
    await state.set_state(AdminFlow.waiting_for_broadcast_confirm)
    await safe_answer(
        message,
        f"<b>Предпросмотр рассылки:</b>\n\n{broadcast_text}",
        reply_markup=admin_broadcast_confirm_keyboard(),
    )


@router.message(AdminFlow.waiting_for_broadcast)
async def invalid_broadcast_text_message(message: Message) -> None:
    await safe_answer(message, "Отправьте текст рассылки одним сообщением.")


@router.callback_query(F.data == ADMIN_BROADCAST_CANCEL_CALLBACK)
async def broadcast_cancel_callback(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await ensure_admin_callback(callback, settings):
        return
    await state.clear()
    await safe_callback_answer(callback)
    if callback.message is not None:
        await safe_answer(callback.message, "Рассылка отменена.")


@router.callback_query(
    AdminFlow.waiting_for_broadcast_confirm,
    F.data == ADMIN_BROADCAST_CONFIRM_CALLBACK,
)
async def broadcast_confirm_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_admin_callback(callback, settings):
        await state.clear()
        return

    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    if not isinstance(broadcast_text, str) or not broadcast_text.strip():
        await state.clear()
        await safe_callback_answer(callback)
        await safe_answer(callback.message, "Не найден текст рассылки. Запустите сценарий заново.")
        return

    async with db.session() as session:
        telegram_ids = await list_all_user_telegram_ids(session)

    success_count = 0
    failed_count = 0
    for index, telegram_id in enumerate(telegram_ids, start=1):
        try:
            sent = await safe_send_message(callback.bot, telegram_id, broadcast_text)
            if sent is not None:
                success_count += 1
            else:
                failed_count += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed_count += 1
        except Exception:
            failed_count += 1
        if index % BROADCAST_BATCH_SIZE == 0 and index < len(telegram_ids):
            await asyncio.sleep(BROADCAST_BATCH_DELAY_SECONDS)

    await state.clear()
    await safe_callback_answer(callback)
    await safe_answer(
        callback.message,
        f"Рассылка завершена.\nУспешно отправлено: {success_count}\nНе удалось отправить: {failed_count}"
    )
