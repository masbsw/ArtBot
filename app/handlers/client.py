from html import escape
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TelegramUser

from app.db.models import UserRole
from app.db.session import Database
from app.keyboards.common import (
    SAVED_PROFILES_BUTTON,
    SET_FILTERS_BUTTON,
    VIEW_PROFILES_BUTTON,
    role_menu_keyboard,
)
from app.keyboards.client import (
    COMPLAIN_PROFILE_CALLBACK_PREFIX,
    CONTACT_PROFILE_CALLBACK_PREFIX,
    CLIENT_DEADLINE_CALLBACK_PREFIX,
    CLIENT_FORMAT_CALLBACK_PREFIX,
    EDIT_FILTERS_CALLBACK,
    FIND_ARTISTS_CALLBACK,
    LIKE_PROFILE_CALLBACK_PREFIX,
    SAVED_PROFILE_DELETE_CALLBACK_PREFIX,
    SAVED_PROFILE_NEXT_CALLBACK_PREFIX,
    SAVED_PROFILE_PREV_CALLBACK_PREFIX,
    SAVE_PROFILE_CALLBACK_PREFIX,
    SKIP_PROFILE_CALLBACK_PREFIX,
    client_deadline_keyboard,
    client_filters_actions_keyboard,
    client_format_keyboard,
    client_profile_actions_keyboard,
    saved_profile_actions_keyboard,
)
from app.services.artist_profiles import humanize_deadline_category
from app.services.client_filters import (
    get_client_filter,
    upsert_client_filter,
)
from app.services.profile_actions import (
    add_complaint,
    add_contact,
    add_like,
    remove_save,
    add_save,
    add_skip,
    get_next_artist_profile,
    get_profile_by_id,
    get_saved_profiles,
)
from app.services.profile_cards import send_profile_card
from app.services.telegram_api import (
    enforce_callback_rate_limit,
    safe_answer,
    safe_callback_answer,
    safe_edit_text,
)
from app.services.users import get_or_create_user
from app.states.client import ClientFlow

router = Router(name="client")

SAVED_VIEW_MESSAGE_IDS_KEY = "saved_view_message_ids"


def browse_access_denied_text() -> str:
    return (
        "Этот сценарий доступен только для ролей <b>Художник</b> и <b>Заказчик</b>.\n"
        "Сначала выберите роль через /role."
    )


async def get_client_user(message_user, db: Database):
    async with db.session() as session:
        user, _ = await get_or_create_user(session, message_user)
        return user


def can_browse_profiles(role: UserRole) -> bool:
    return role in {UserRole.CLIENT, UserRole.ARTIST}


async def ensure_browse_access(message: Message, db: Database) -> bool:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return False

    user = await get_client_user(message.from_user, db)
    if user is None or not can_browse_profiles(user.role):
        await safe_answer(message, browse_access_denied_text())
        return False
    return True


async def ensure_browse_access_callback(callback: CallbackQuery, db: Database) -> bool:
    if callback.from_user is None:
        await safe_callback_answer(callback)
        return False

    if not await enforce_callback_rate_limit(callback):
        return False

    user = await get_client_user(callback.from_user, db)
    if user is None or not can_browse_profiles(user.role):
        await safe_callback_answer(
            callback,
            "Доступно только для ролей Художник и Заказчик.",
            show_alert=True,
        )
        return False
    return True


def build_filters_text(client_filter) -> str:
    return (
        "<b>Мои фильтры</b>\n\n"
        f"<b>Формат:</b> {escape(client_filter.format or 'Не указано')}\n"
        f"<b>Сроки:</b> {escape(humanize_deadline_category(client_filter.deadline_category))}"
    )


async def start_client_filters_flow(target: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ClientFlow.waiting_for_format)
    await safe_answer(
        target,
        "Шаг 1 из 2. Выберите нужный формат:",
        reply_markup=client_format_keyboard(),
    )


async def send_client_menu_after_filters(message: Message) -> None:
    await safe_answer(
        message,
        "Что дальше?",
        reply_markup=role_menu_keyboard(UserRole.CLIENT),
    )


async def send_client_filters_view(message: Message, db: Database) -> None:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return

    async with db.session() as session:
        user, _ = await get_or_create_user(session, message.from_user)
        if user is None or not can_browse_profiles(user.role):
            await safe_answer(message, browse_access_denied_text())
            return
        client_filter = await get_client_filter(session, user.id)

    if client_filter is None:
        await safe_answer(
            message,
            "Фильтры пока не настроены. Используйте /edit_filters.",
            reply_markup=client_filters_actions_keyboard(),
        )
        return

    await safe_answer(
        message,
        build_filters_text(client_filter),
        reply_markup=client_filters_actions_keyboard(),
    )


async def run_artist_search(
    message: Message,
    telegram_user: TelegramUser | None,
    db: Database,
) -> bool:
    if telegram_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return False

    async with db.session() as session:
        user, _ = await get_or_create_user(session, telegram_user)
        if user is None or not can_browse_profiles(user.role):
            await safe_answer(message, browse_access_denied_text())
            return False

        client_filter = await get_client_filter(session, user.id)
        if client_filter is None:
            await safe_answer(
                message,
                "Сначала настройте фильтры. Нажмите «⚙️ Настроить фильтры» или используйте /edit_filters.",
                reply_markup=client_filters_actions_keyboard(),
            )
            return False

        profile, reset_circle = await get_next_artist_profile(session, user.id, client_filter)

    if profile is None:
        await safe_answer(message, "По этим фильтрам анкеты пока не найдены.")
        return False

    if reset_circle:
        await safe_answer(message, "Вы просмотрели все подходящие анкеты. Показываю круг заново.")

    await send_profile_card(
        message,
        profile,
        reply_markup=client_profile_actions_keyboard(profile.id),
        title="✦ Подходящая анкета",
    )
    return True


async def send_next_artist_profile(
    message: Message,
    telegram_user: TelegramUser | None,
    db: Database,
) -> None:
    await run_artist_search(message, telegram_user, db)


async def delete_saved_view_messages(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    message_ids = data.get(SAVED_VIEW_MESSAGE_IDS_KEY, [])
    if not isinstance(message_ids, list):
        message_ids = []

    for message_id in message_ids:
        if not isinstance(message_id, int):
            continue
        with suppress(TelegramBadRequest):
            await message.bot.delete_message(message.chat.id, message_id)

    await state.update_data(saved_view_message_ids=[])


async def show_saved_profile(
    message: Message,
    state: FSMContext,
    profile,
    current_index: int,
    total_count: int,
) -> None:
    await delete_saved_view_messages(message, state)
    sent_messages = await send_profile_card(
        message,
        profile,
        reply_markup=saved_profile_actions_keyboard(profile.id),
        title=f"Сохранённая анкета {current_index}/{total_count}",
    )
    await state.update_data(
        saved_view_message_ids=[item.message_id for item in sent_messages],
    )


async def send_saved_profile_by_id(
    message: Message,
    state: FSMContext,
    db: Database,
    telegram_user: TelegramUser,
    profile_id: int,
) -> bool:
    async with db.session() as session:
        user, _ = await get_or_create_user(session, telegram_user)
        if user is None or not can_browse_profiles(user.role):
            await safe_answer(message, browse_access_denied_text())
            return False

        profiles = await get_saved_profiles(session, user.id)

    if not profiles:
        await delete_saved_view_messages(message, state)
        await safe_answer(message, "У вас пока нет сохраненных анкет.")
        return False

    profile = next((item for item in profiles if item.id == profile_id), None)
    if profile is None:
        profile = profiles[0]

    current_index = next(
        (index for index, item in enumerate(profiles, start=1) if item.id == profile.id),
        1,
    )
    await show_saved_profile(message, state, profile, current_index, len(profiles))
    return True


@router.message(Command("edit_filters"))
async def edit_filters_command(message: Message, db: Database, state: FSMContext) -> None:
    if not await ensure_browse_access(message, db):
        return
    await start_client_filters_flow(message, state)


@router.message(Command("my_filters"))
async def my_filters_command(message: Message, db: Database) -> None:
    await send_client_filters_view(message, db)


@router.message(Command("find_artists"))
async def find_artists_command(message: Message, db: Database) -> None:
    await run_artist_search(message, message.from_user, db)


@router.message(Command("saved_profiles"))
async def saved_profiles_command(message: Message, db: Database, state: FSMContext) -> None:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return

    async with db.session() as session:
        user, _ = await get_or_create_user(session, message.from_user)
        if user is None or not can_browse_profiles(user.role):
            await safe_answer(message, browse_access_denied_text())
            return
        profiles = await get_saved_profiles(session, user.id)

    if not profiles:
        await delete_saved_view_messages(message, state)
        await safe_answer(message, "У вас пока нет сохраненных анкет.")
        return

    await show_saved_profile(message, state, profiles[0], 1, len(profiles))


@router.callback_query(F.data == EDIT_FILTERS_CALLBACK)
async def edit_filters_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.message is None or not await ensure_browse_access_callback(callback, db):
        return
    await safe_callback_answer(callback)
    await start_client_filters_flow(callback.message, state)


@router.callback_query(F.data == FIND_ARTISTS_CALLBACK)
async def find_artists_callback(callback: CallbackQuery, db: Database) -> None:
    if callback.message is None or not await ensure_browse_access_callback(callback, db):
        return
    await safe_callback_answer(callback)
    await run_artist_search(callback.message, callback.from_user, db)


@router.callback_query(F.data.startswith(LIKE_PROFILE_CALLBACK_PREFIX))
async def like_profile_callback(callback: CallbackQuery, db: Database) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    profile_id = int(callback.data.removeprefix(LIKE_PROFILE_CALLBACK_PREFIX))
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        created = await add_like(session, user.id, profile_id)

    await safe_callback_answer(callback, "Лайк сохранён." if created else "Вы уже лайкали эту анкету.")


@router.callback_query(F.data.startswith(SAVE_PROFILE_CALLBACK_PREFIX))
async def save_profile_callback(callback: CallbackQuery, db: Database) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    profile_id = int(callback.data.removeprefix(SAVE_PROFILE_CALLBACK_PREFIX))
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        created = await add_save(session, user.id, profile_id)

    await safe_callback_answer(
        callback,
        "Анкета сохранена." if created else "Эта анкета уже в сохранённых."
    )
    await send_next_artist_profile(callback.message, callback.from_user, db)


@router.callback_query(F.data.startswith(CONTACT_PROFILE_CALLBACK_PREFIX))
async def contact_profile_callback(callback: CallbackQuery, db: Database) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    profile_id = int(callback.data.removeprefix(CONTACT_PROFILE_CALLBACK_PREFIX))
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        profile = await get_profile_by_id(session, profile_id)
        if profile is None:
            await safe_callback_answer(callback, "Анкета не найдена.", show_alert=True)
            return
        await add_contact(session, user.id, profile_id)

    owner_username = profile.user.username if profile.user is not None else None
    contact_value = (
        f"@{owner_username}"
        if owner_username
        else (profile.contacts_text or "Не указано")
    )

    await safe_callback_answer(callback)
    await safe_answer(
        callback.message,
        f"<b>Контакт художника:</b>\n{escape(contact_value)}"
    )


@router.callback_query(F.data.startswith(SAVED_PROFILE_PREV_CALLBACK_PREFIX))
async def saved_profile_prev_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    current_profile_id = int(callback.data.removeprefix(SAVED_PROFILE_PREV_CALLBACK_PREFIX))
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        profiles = await get_saved_profiles(session, user.id)

    if not profiles:
        await delete_saved_view_messages(callback.message, state)
        await safe_callback_answer(callback)
        await safe_answer(callback.message, "У вас пока нет сохраненных анкет.")
        return

    current_index = next((index for index, item in enumerate(profiles) if item.id == current_profile_id), 0)
    prev_index = (current_index - 1) % len(profiles)

    await safe_callback_answer(callback)
    await show_saved_profile(
        callback.message,
        state,
        profiles[prev_index],
        prev_index + 1,
        len(profiles),
    )


@router.callback_query(F.data.startswith(SAVED_PROFILE_NEXT_CALLBACK_PREFIX))
async def saved_profile_next_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    current_profile_id = int(callback.data.removeprefix(SAVED_PROFILE_NEXT_CALLBACK_PREFIX))
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        profiles = await get_saved_profiles(session, user.id)

    if not profiles:
        await delete_saved_view_messages(callback.message, state)
        await safe_callback_answer(callback)
        await safe_answer(callback.message, "У вас пока нет сохраненных анкет.")
        return

    current_index = next((index for index, item in enumerate(profiles) if item.id == current_profile_id), 0)
    next_index = (current_index + 1) % len(profiles)

    await safe_callback_answer(callback)
    await show_saved_profile(
        callback.message,
        state,
        profiles[next_index],
        next_index + 1,
        len(profiles),
    )


@router.callback_query(F.data.startswith(SAVED_PROFILE_DELETE_CALLBACK_PREFIX))
async def saved_profile_delete_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    profile_id = int(callback.data.removeprefix(SAVED_PROFILE_DELETE_CALLBACK_PREFIX))
    previous_profiles: list = []
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        previous_profiles = await get_saved_profiles(session, user.id)
        removed = await remove_save(session, user.id, profile_id)
        profiles = await get_saved_profiles(session, user.id)

    if not removed:
        await safe_callback_answer(callback, "Эта анкета уже удалена из сохранённых.")
        if profiles:
            await show_saved_profile(callback.message, state, profiles[0], 1, len(profiles))
        else:
            await delete_saved_view_messages(callback.message, state)
            await safe_answer(callback.message, "У вас пока нет сохраненных анкет.")
        return

    await safe_callback_answer(callback, "Анкета удалена из сохранённых.")
    if not profiles:
        await delete_saved_view_messages(callback.message, state)
        await safe_answer(callback.message, "У вас пока нет сохраненных анкет.")
        return

    removed_index = next(
        (index for index, item in enumerate(previous_profiles) if item.id == profile_id),
        0,
    )
    next_index = min(removed_index, len(profiles) - 1)
    next_profile = profiles[next_index]
    await show_saved_profile(
        callback.message,
        state,
        next_profile,
        next_index + 1,
        len(profiles),
    )


@router.callback_query(F.data.startswith(SKIP_PROFILE_CALLBACK_PREFIX))
async def skip_profile_callback(callback: CallbackQuery, db: Database) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    profile_id = int(callback.data.removeprefix(SKIP_PROFILE_CALLBACK_PREFIX))
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        await add_skip(session, user.id, profile_id)

    await safe_callback_answer(callback)
    await send_next_artist_profile(callback.message, callback.from_user, db)


@router.callback_query(F.data.startswith(COMPLAIN_PROFILE_CALLBACK_PREFIX))
async def complain_profile_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_browse_access_callback(callback, db):
        return

    profile_id = int(callback.data.removeprefix(COMPLAIN_PROFILE_CALLBACK_PREFIX))
    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        profile = await get_profile_by_id(session, profile_id)
        if profile is None:
            await safe_callback_answer(callback, "Анкета не найдена.", show_alert=True)
            return

    await state.set_state(ClientFlow.waiting_for_complaint_reason)
    await state.update_data(complaint_profile_id=profile_id)
    await safe_callback_answer(callback)
    await safe_answer(callback.message, "Напишите причину жалобы одним сообщением.")


@router.callback_query(
    ClientFlow.waiting_for_format,
    F.data.startswith(CLIENT_FORMAT_CALLBACK_PREFIX),
)
async def set_client_format(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return

    value = callback.data.removeprefix(CLIENT_FORMAT_CALLBACK_PREFIX)
    await state.update_data(format=value)
    await safe_edit_text(callback.message, f"Шаг 1 из 2. Формат: <b>{escape(value)}</b>.")
    await safe_callback_answer(callback)
    await state.set_state(ClientFlow.waiting_for_deadline_category)
    await safe_answer(
        callback.message,
        "Шаг 2 из 2. Выберите категорию сроков:",
        reply_markup=client_deadline_keyboard(),
    )


@router.callback_query(
    ClientFlow.waiting_for_deadline_category,
    F.data.startswith(CLIENT_DEADLINE_CALLBACK_PREFIX),
)
async def set_client_deadline(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return

    value = callback.data.removeprefix(CLIENT_DEADLINE_CALLBACK_PREFIX)
    await state.update_data(deadline_category=value)
    await safe_edit_text(
        callback.message,
        f"Шаг 2 из 2. Сроки: <b>{escape(humanize_deadline_category(value))}</b>."
    )
    data = await state.get_data()

    async with db.session() as session:
        user, _ = await get_or_create_user(session, callback.from_user)
        if user is None or not can_browse_profiles(user.role):
            await safe_answer(callback.message, browse_access_denied_text())
            await state.clear()
            await safe_callback_answer(callback)
            return
        client_filter = await upsert_client_filter(session, user.id, data)

    await state.clear()
    await safe_callback_answer(callback, "Фильтры сохранены.")
    await safe_answer(
        callback.message,
        build_filters_text(client_filter),
        reply_markup=client_filters_actions_keyboard(),
    )
    await send_client_menu_after_filters(callback.message)


@router.message(ClientFlow.waiting_for_complaint_reason, F.text)
async def complaint_reason_message(
    message: Message,
    state: FSMContext,
    db: Database,
) -> None:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return

    reason = message.text.strip()
    if not reason:
        await safe_answer(message, "Причина жалобы не должна быть пустой.")
        return

    data = await state.get_data()
    profile_id = data.get("complaint_profile_id")
    if not isinstance(profile_id, int):
        await state.clear()
        await safe_answer(message, "Не удалось определить анкету для жалобы.")
        return

    async with db.session() as session:
        user, _ = await get_or_create_user(session, message.from_user)
        if user is None or not can_browse_profiles(user.role):
            await safe_answer(message, browse_access_denied_text())
            await state.clear()
            return
        created = await add_complaint(session, user.id, profile_id, reason)

    await state.clear()
    await safe_answer(
        message,
        "Жалоба отправлена." if created else "Вы уже жаловались на эту анкету."
    )
    await send_next_artist_profile(message, message.from_user, db)


@router.message(ClientFlow.waiting_for_complaint_reason)
async def invalid_complaint_reason(message: Message) -> None:
    await safe_answer(message, "Отправьте причину жалобы текстом одним сообщением.")


@router.message(F.text == SET_FILTERS_BUTTON)
async def edit_filters_button(message: Message, db: Database, state: FSMContext) -> None:
    await edit_filters_command(message, db, state)


@router.message(F.text == VIEW_PROFILES_BUTTON)
async def view_profiles_button(message: Message, db: Database) -> None:
    await find_artists_command(message, db)


@router.message(F.text == SAVED_PROFILES_BUTTON)
async def saved_profiles_button(message: Message, db: Database, state: FSMContext) -> None:
    await saved_profiles_command(message, db, state)


@router.callback_query(ClientFlow.waiting_for_deadline_category)
@router.callback_query(ClientFlow.waiting_for_format)
async def invalid_client_callback(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "Выберите вариант кнопкой ниже.", show_alert=True)
