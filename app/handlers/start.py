from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.db.models import User, UserRole
from app.db.session import Database
from app.handlers.artist import start_artist_profile_flow
from app.handlers.client import start_client_filters_flow
from app.keyboards.common import CHANGE_ROLE_BUTTON, role_menu_keyboard
from app.keyboards.start import (
    CHANGE_ROLE_CALLBACK,
    ROLE_CALLBACK_PREFIX,
    change_role_keyboard,
    role_selection_keyboard,
)
from app.services.artist_profiles import get_artist_profile
from app.services.client_filters import get_client_filter
from app.services.telegram_api import (
    enforce_callback_rate_limit,
    safe_answer,
    safe_callback_answer,
    safe_edit_text,
)
from app.services.users import ROLE_TITLES, get_or_create_user, get_user_by_telegram_id, set_user_role
from app.states.artist import ArtistFlow
from app.states.client import ClientFlow

router = Router(name="start")


def build_active_flow_text(current_state: str) -> str:
    artist_steps = {
        ArtistFlow.waiting_for_format.state: "Сейчас активен шаг 1 из 7: выбор формата.",
        ArtistFlow.waiting_for_portfolio_images.state: "Сейчас активен шаг 2 из 7: загрузка портфолио.",
        ArtistFlow.waiting_for_description.state: "Сейчас активен шаг 3 из 7: описание.",
        ArtistFlow.waiting_for_currency.state: "Сейчас активен шаг 4 из 7: выбор валюты.",
        ArtistFlow.waiting_for_price_text.state: "Сейчас активен шаг 5 из 7: прайс.",
        ArtistFlow.waiting_for_deadline_category.state: "Сейчас активен шаг 6 из 7: сроки.",
        ArtistFlow.waiting_for_contacts_text.state: "Сейчас активен шаг 7 из 7: контакты.",
        ArtistFlow.waiting_for_edit_field.state: "Сейчас активно редактирование отдельного поля анкеты.",
    }
    client_steps = {
        ClientFlow.waiting_for_format.state: "Сейчас активна настройка фильтров: выбор формата.",
        ClientFlow.waiting_for_deadline_category.state: "Сейчас активна настройка фильтров: выбор сроков.",
        ClientFlow.waiting_for_complaint_reason.state: "Сейчас ожидается текст жалобы.",
    }
    return artist_steps.get(current_state) or client_steps.get(current_state) or "Сценарий уже выполняется. Продолжайте текущий шаг."


def is_admin_user(telegram_id: int, settings: Settings) -> bool:
    return telegram_id in settings.admin_ids


def build_role_prompt(user: User, created: bool) -> str:
    if created:
        return "Выберите роль. Позже ее можно будет изменить."
    return (
        f"Ваш текущий режим: <b>{ROLE_TITLES[user.role]}</b>.\n\n"
        "При необходимости роль можно сменить:"
    )


async def send_role_selector(message: Message, user: User, created: bool) -> None:
    await safe_answer(
        message,
        build_role_prompt(user, created),
        reply_markup=role_selection_keyboard(None if created else user.role),
    )


async def send_role_home(message: Message, user: User) -> None:
    text = f"Текущая роль: <b>{ROLE_TITLES[user.role]}</b>"
    await safe_answer(message, text, reply_markup=role_menu_keyboard(user.role))


async def continue_role_onboarding(
    message: Message,
    user: User,
    db: Database,
) -> str:
    async with db.session() as session:
        fresh_user = await get_user_by_telegram_id(session, user.telegram_id)
        if fresh_user is None:
            await safe_answer(message, "Не удалось определить пользователя Telegram.")
            return "missing"

        if fresh_user.role == UserRole.ARTIST:
            profile = await get_artist_profile(session, fresh_user.id)
            if profile is None:
                return "artist_onboarding"

        if fresh_user.role == UserRole.CLIENT:
            client_filter = await get_client_filter(session, fresh_user.id)
            if client_filter is None:
                return "client_onboarding"

        return "home"


@router.message(CommandStart())
async def start_command(
    message: Message,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return
    current_state = await state.get_state()
    if current_state is not None:
        await safe_answer(message, build_active_flow_text(current_state))
        return

    async with db.session() as session:
        user, created = await get_or_create_user(
            session=session,
            telegram_user=message.from_user,
            is_admin=is_admin_user(message.from_user.id, settings),
        )

    if created or user.role == UserRole.ADMIN:
        await send_role_selector(message, user, created)
        return

    await send_role_home(message, user)


@router.message(Command("role"))
async def role_command(message: Message, db: Database, settings: Settings) -> None:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return

    async with db.session() as session:
        user, _ = await get_or_create_user(
            session=session,
            telegram_user=message.from_user,
            is_admin=is_admin_user(message.from_user.id, settings),
        )

    await safe_answer(
        message,
        "Выберите роль:",
        reply_markup=role_selection_keyboard(user.role),
    )


@router.message(F.text == CHANGE_ROLE_BUTTON)
async def change_role_button(message: Message, db: Database, settings: Settings) -> None:
    await role_command(message, db, settings)


@router.callback_query(F.data == CHANGE_ROLE_CALLBACK)
async def change_role_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.from_user is None or callback.message is None:
        await safe_callback_answer(callback)
        return
    if not await enforce_callback_rate_limit(callback):
        return

    async with db.session() as session:
        user, _ = await get_or_create_user(
            session=session,
            telegram_user=callback.from_user,
            is_admin=is_admin_user(callback.from_user.id, settings),
        )

    await safe_edit_text(
        callback.message,
        "Выберите новую роль:",
        reply_markup=role_selection_keyboard(user.role),
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith(ROLE_CALLBACK_PREFIX))
async def set_role_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        await safe_callback_answer(callback)
        return
    if not await enforce_callback_rate_limit(callback):
        return

    role_value = callback.data.removeprefix(ROLE_CALLBACK_PREFIX)
    role = UserRole(role_value)

    async with db.session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if user is None:
            user, _ = await get_or_create_user(
                session=session,
                telegram_user=callback.from_user,
                is_admin=False,
            )
        user = await set_user_role(session, user, role)

    await safe_callback_answer(callback)
    result = await continue_role_onboarding(
        callback.message,
        user,
        db,
    )
    if result == "artist_onboarding":
        await safe_edit_text(
            callback.message,
            "Роль сохранена: <b>Художник</b>. Теперь создадим вашу анкету 👇",
            reply_markup=change_role_keyboard(),
        )
        await start_artist_profile_flow(
            callback.message,
            state,
            actor_telegram_id=callback.from_user.id,
        )
        return
    if result == "client_onboarding":
        await safe_edit_text(
            callback.message,
            "Роль сохранена: <b>Заказчик</b>. Теперь настроим фильтры для поиска 👇",
            reply_markup=change_role_keyboard(),
        )
        await start_client_filters_flow(callback.message, state)
        return
    if result == "home":
        await safe_edit_text(
            callback.message,
            f"Роль сохранена: <b>{ROLE_TITLES[user.role]}</b>",
            reply_markup=change_role_keyboard(),
        )
        await safe_answer(
            callback.message,
            f"Текущая роль: <b>{ROLE_TITLES[user.role]}</b>",
            reply_markup=role_menu_keyboard(user.role),
        )
        return

    await safe_edit_text(
        callback.message,
        f"Роль сохранена: <b>{ROLE_TITLES[user.role]}</b>",
        reply_markup=change_role_keyboard(),
    )
