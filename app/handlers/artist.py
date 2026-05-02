import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db.models import ArtistProfile, UserRole
from app.db.session import Database
from app.keyboards.common import (
    EDIT_PROFILE_BUTTON,
    EDIT_PROFILE_FIELD_BUTTON,
    MY_PROFILE_BUTTON,
    role_menu_keyboard,
)
from app.keyboards.artist import (
    CANCEL_BUTTON_TEXT,
    CURRENCY_CALLBACK_PREFIX,
    DEADLINE_CALLBACK_PREFIX,
    DISABLE_PROFILE_CALLBACK,
    DISABLE_PROFILE_CANCEL_CALLBACK,
    DISABLE_PROFILE_CONFIRM_CALLBACK,
    EDITABLE_PROFILE_FIELDS,
    EDIT_FIELD_CALLBACK_PREFIX,
    EDIT_PROFILE_CALLBACK,
    EDIT_PROFILE_FIELD_CALLBACK,
    FORMAT_CALLBACK_PREFIX,
    cancel_reply_keyboard,
    currency_keyboard,
    deadline_category_keyboard,
    disable_profile_confirm_keyboard,
    format_keyboard,
    portfolio_finish_keyboard,
    profile_field_selection_keyboard,
    profile_actions_keyboard,
)
from app.services.artist_profiles import (
    MAX_PORTFOLIO_IMAGES,
    contacts_have_links,
    disable_artist_profile,
    get_artist_profile,
    humanize_deadline_category,
    is_active_artist_profile,
    upsert_artist_profile,
)
from app.services.profile_cards import build_profile_caption, send_profile_card
from app.services.telegram_api import (
    enforce_callback_rate_limit,
    safe_answer,
    safe_callback_answer,
    safe_edit_text,
    safe_fsm_answer,
)
from app.services.users import get_user_by_telegram_id
from app.states.artist import ArtistFlow

router = Router(name="artist")
logger = logging.getLogger(__name__)

EDITABLE_FIELD_NAMES = {value for _, value in EDITABLE_PROFILE_FIELDS}


def artist_access_denied_text() -> str:
    return (
        "Этот сценарий доступен только для роли <b>Художник</b>.\n"
        "Сначала переключите роль через /role."
    )


async def get_artist_user(message_user, db: Database):
    async with db.session() as session:
        return await get_user_by_telegram_id(session, message_user.id)

async def ensure_artist_access(message: Message, db: Database) -> bool:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return False

    user = await get_artist_user(message.from_user, db)
    if user is None or user.role != UserRole.ARTIST:
        await safe_answer(message, artist_access_denied_text())
        return False
    return True


async def ensure_artist_access_callback(callback: CallbackQuery, db: Database) -> bool:
    if callback.from_user is None:
        await safe_callback_answer(callback)
        return False

    if not await enforce_callback_rate_limit(callback):
        return False

    user = await get_artist_user(callback.from_user, db)
    if user is None or user.role != UserRole.ARTIST:
        await safe_callback_answer(callback, "Доступно только для роли Художник.", show_alert=True)
        return False
    return True


async def state_matches(state: FSMContext, expected_state: ArtistFlow) -> bool:
    return await state.get_state() == expected_state.state


async def can_cancel_current_edit(state: FSMContext) -> bool:
    data = await state.get_data()
    return bool(data.get("can_cancel_edit"))


async def start_artist_profile_flow(
    target: Message,
    state: FSMContext,
    actor_telegram_id: int | None = None,
    can_cancel_edit: bool = False,
) -> None:
    await state.clear()
    await state.update_data(
        edit_mode="full",
        edit_field=None,
        actor_telegram_id=actor_telegram_id,
        can_cancel_edit=can_cancel_edit,
    )
    await state.set_state(ArtistFlow.waiting_for_format)
    if not await state_matches(state, ArtistFlow.waiting_for_format):
        return
    if can_cancel_edit:
        await safe_fsm_answer(
            target,
            "Шаг 1 из 7. Выберите формат работы или нажмите ❌ Отменить.",
            reply_markup=cancel_reply_keyboard(),
        )
        await safe_fsm_answer(target, "Выберите формат:", reply_markup=format_keyboard())
        return
    await safe_fsm_answer(
        target,
        "Шаг 1 из 7. Выберите формат работы:",
        reply_markup=format_keyboard(),
    )


async def prompt_portfolio_step(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ArtistFlow.waiting_for_portfolio_images)
    if not await state_matches(state, ArtistFlow.waiting_for_portfolio_images):
        return
    data = await state.get_data()
    if data.get("edit_field") != "portfolio":
        await state.update_data(portfolio_images=[])
    if await can_cancel_current_edit(state):
        text = (
            f"Шаг 2 из 7. Отправьте до {MAX_PORTFOLIO_IMAGES} изображений по одному сообщению.\n"
            "Когда закончите, нажмите кнопку <b>Готово</b>.\n"
            "Или нажмите ❌ Отменить."
        )
    else:
        text = (
            f"Шаг 2 из 7. Отправьте до {MAX_PORTFOLIO_IMAGES} изображений по одному сообщению.\n"
            "Когда закончите, нажмите кнопку <b>Готово</b>."
        )
    if isinstance(target, CallbackQuery) and target.message is not None:
        await safe_fsm_answer(target.message, text, reply_markup=portfolio_finish_keyboard())
    else:
        await safe_fsm_answer(target, text, reply_markup=portfolio_finish_keyboard())


async def prompt_description_step(message: Message, state: FSMContext) -> None:
    await state.set_state(ArtistFlow.waiting_for_description)
    if not await state_matches(state, ArtistFlow.waiting_for_description):
        return
    if await can_cancel_current_edit(state):
        await safe_fsm_answer(
            message,
            "Шаг 5 из 7. Напишите краткое описание себя и услуг.\n"
            "Отправь новый текст или нажми ❌ Отменить.",
            reply_markup=cancel_reply_keyboard(),
        )
        return
    await safe_fsm_answer(
        message,
        "Шаг 5 из 7. Напишите краткое описание себя и услуг.",
    )


async def prompt_currency_step(message: Message, state: FSMContext) -> None:
    await state.set_state(ArtistFlow.waiting_for_currency)
    if not await state_matches(state, ArtistFlow.waiting_for_currency):
        return
    if await can_cancel_current_edit(state):
        await safe_fsm_answer(
            message,
            "Шаг 3 из 7. Выберите валюту или нажмите ❌ Отменить.",
            reply_markup=cancel_reply_keyboard(),
        )
        await safe_fsm_answer(message, "Выберите валюту:", reply_markup=currency_keyboard())
        return
    await safe_fsm_answer(
        message,
        "Шаг 3 из 7. Выберите валюту:",
        reply_markup=currency_keyboard(),
    )


async def prompt_currency_step_after_portfolio(message: Message, state: FSMContext) -> None:
    await state.set_state(ArtistFlow.waiting_for_currency)
    if not await state_matches(state, ArtistFlow.waiting_for_currency):
        return
    if await can_cancel_current_edit(state):
        await safe_fsm_answer(
            message,
            f"Портфолио заполнено: {MAX_PORTFOLIO_IMAGES}/{MAX_PORTFOLIO_IMAGES}.\n\n"
            "Шаг 3 из 7. Выберите валюту или нажмите ❌ Отменить.",
            reply_markup=cancel_reply_keyboard(),
        )
        await safe_fsm_answer(message, "Выберите валюту:", reply_markup=currency_keyboard())
        return
    await safe_fsm_answer(
        message,
        f"Портфолио заполнено: {MAX_PORTFOLIO_IMAGES}/{MAX_PORTFOLIO_IMAGES}.\n\n"
        "Шаг 3 из 7. Выберите валюту:",
        reply_markup=currency_keyboard(),
    )


async def prompt_price_text_step(message: Message, state: FSMContext) -> None:
    await state.set_state(ArtistFlow.waiting_for_price_text)
    if not await state_matches(state, ArtistFlow.waiting_for_price_text):
        return
    if await can_cancel_current_edit(state):
        await safe_fsm_answer(
            message,
            "Шаг 4 из 7. Укажите цену в свободной форме.\n"
            "В анкете она будет показана как: ваш текст (валюта).\n"
            "Отправь новый текст или нажми ❌ Отменить.",
            reply_markup=cancel_reply_keyboard(),
        )
        return
    await safe_fsm_answer(
        message,
        "Шаг 4 из 7. Укажите цену в свободной форме.\n"
        "В анкете она будет показана как: ваш текст (валюта)."
    )


async def prompt_deadline_step(message: Message, state: FSMContext) -> None:
    await state.set_state(ArtistFlow.waiting_for_deadline_category)
    if not await state_matches(state, ArtistFlow.waiting_for_deadline_category):
        return
    if await can_cancel_current_edit(state):
        await safe_fsm_answer(
            message,
            "Шаг 6 из 7. Выберите категорию сроков или нажмите ❌ Отменить.",
            reply_markup=cancel_reply_keyboard(),
        )
        await safe_fsm_answer(message, "Выберите категорию сроков:", reply_markup=deadline_category_keyboard())
        return
    await safe_fsm_answer(
        message,
        "Шаг 6 из 7. Выберите категорию сроков:",
        reply_markup=deadline_category_keyboard(),
    )


async def prompt_contacts_step(message: Message, state: FSMContext) -> None:
    await state.set_state(ArtistFlow.waiting_for_contacts_text)
    if not await state_matches(state, ArtistFlow.waiting_for_contacts_text):
        return
    if await can_cancel_current_edit(state):
        await safe_fsm_answer(
            message,
            "Шаг 7 из 7. Отправьте контакты текстом без ссылок на сайты.\n"
            "Отправь новый текст или нажми ❌ Отменить.",
            reply_markup=cancel_reply_keyboard(),
        )
        return
    await safe_fsm_answer(
        message,
        "Шаг 7 из 7. Отправьте контакты текстом без ссылок на сайты.",
    )


def build_artist_form_data(
    profile: ArtistProfile | None,
    state_data: dict,
) -> dict[str, str | list[str]]:
    existing_images = []
    if profile is not None:
        existing_images = [
            item.telegram_file_id
            for item in sorted(profile.portfolio_images, key=lambda image: image.position)
        ]

    return {
        "format": state_data.get("format") or (profile.format if profile is not None else ""),
        "portfolio_images": list(state_data.get("portfolio_images") or existing_images),
        "description": state_data.get("description") or (profile.description if profile is not None else ""),
        "currency": state_data.get("currency") or (profile.currency if profile is not None else ""),
        "price_text": state_data.get("price_text") or (profile.price_text if profile is not None else ""),
        "deadline_category": state_data.get("deadline_category") or (
            profile.deadline_category if profile is not None else ""
        ),
        "contacts_text": state_data.get("contacts_text") or (profile.contacts_text if profile is not None else ""),
    }


async def send_artist_menu_after_edit(message: Message) -> None:
    await safe_answer(
        message,
        "Что дальше?",
        reply_markup=role_menu_keyboard(UserRole.ARTIST),
    )


async def send_profile_view_with_fallback(message: Message, db: Database) -> None:
    if message.from_user is None:
        return

    async with db.session() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if user is None or user.role != UserRole.ARTIST:
            return
        profile = await get_artist_profile(session, user.id)

    if not is_active_artist_profile(profile):
        await safe_answer(message, "Анкета пока не заполнена.")
        return

    try:
        await send_profile_card(
            message,
            profile,
            reply_markup=profile_actions_keyboard(),
            title="Моя анкета",
        )
        return
    except Exception:
        logger.exception("artist_profile_view_after_cancel_failed user_id=%s", message.from_user.id)

    await safe_answer(
        message,
        "Не удалось загрузить фото анкеты, показываю текстом:\n\n"
        f"{build_profile_caption(profile, title='Моя анкета')}"
    )


async def finish_artist_profile_update(
    message: Message,
    state: FSMContext,
    db: Database,
) -> bool:
    try:
        state_data = await state.get_data()
        actor_telegram_id = state_data.get("actor_telegram_id")
        if actor_telegram_id is None and message.from_user is not None:
            actor_telegram_id = message.from_user.id
        if actor_telegram_id is None:
            await safe_answer(message, "Не удалось определить пользователя Telegram.")
            return False

        async with db.session() as session:
            user = await get_user_by_telegram_id(session, actor_telegram_id)
            if user is None or user.role != UserRole.ARTIST:
                await safe_answer(message, artist_access_denied_text())
                return False

            profile = await get_artist_profile(session, user.id)
            form_data = build_artist_form_data(profile, state_data)
            profile = await upsert_artist_profile(session, user.id, form_data)

        await state.clear()
        await safe_answer(message, "Анкета сохранена ✅")

        try:
            await send_profile_card(
                message,
                profile,
                reply_markup=profile_actions_keyboard(),
                title="Моя анкета",
            )
        except Exception:
            logger.exception("artist_profile_card_send_failed user_id=%s", actor_telegram_id)

        try:
            await send_artist_menu_after_edit(message)
        except Exception:
            logger.exception("artist_menu_send_failed user_id=%s", actor_telegram_id)
        return True
    except Exception:
        logger.exception("artist_finish_profile_update_failed")
        await safe_answer(
            message,
            "Не получилось сохранить анкету. Попробуйте отправить контакты ещё раз обычным текстом."
        )
        return False


async def start_single_field_edit(message: Message, db: Database, state: FSMContext) -> None:
    if not await ensure_artist_access(message, db):
        return

    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return

    async with db.session() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if user is None or user.role != UserRole.ARTIST:
            await safe_answer(message, artist_access_denied_text())
            return
        profile = await get_artist_profile(session, user.id)

    if not is_active_artist_profile(profile):
        await safe_answer(message, "Анкета пока не заполнена. Сначала заполните её полностью.")
        await start_artist_profile_flow(message, state, actor_telegram_id=message.from_user.id)
        return

    await state.clear()
    await state.update_data(
        edit_mode="field",
        edit_field=None,
        actor_telegram_id=message.from_user.id,
        can_cancel_edit=True,
    )
    await state.set_state(ArtistFlow.waiting_for_edit_field)
    await safe_fsm_answer(
        message,
        "Что изменить в анкете? Или нажмите ❌ Отменить.",
        reply_markup=cancel_reply_keyboard(),
    )
    await safe_fsm_answer(
        message,
        "Выберите поле для редактирования:",
        reply_markup=profile_field_selection_keyboard(),
    )


async def start_single_field_edit_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    if not await ensure_artist_access_callback(callback, db):
        return

    async with db.session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if user is None or user.role != UserRole.ARTIST:
            await safe_callback_answer(callback, "Доступно только для роли Художник.", show_alert=True)
            return
        profile = await get_artist_profile(session, user.id)

    if not is_active_artist_profile(profile):
        await safe_callback_answer(callback)
        await safe_answer(callback.message, "Анкета пока не заполнена. Сначала заполните её полностью.")
        await state.clear()
        await state.update_data(
            edit_mode="full",
            edit_field=None,
            actor_telegram_id=callback.from_user.id,
            can_cancel_edit=False,
        )
        await state.set_state(ArtistFlow.waiting_for_format)
        if await state_matches(state, ArtistFlow.waiting_for_format):
            if await can_cancel_current_edit(state):
                await safe_fsm_answer(
                    callback.message,
                    "Шаг 1 из 7. Выберите формат работы или нажмите ❌ Отменить.",
                    reply_markup=cancel_reply_keyboard(),
                )
                await safe_fsm_answer(callback.message, "Выберите формат:", reply_markup=format_keyboard())
            else:
                await safe_fsm_answer(
                    callback.message,
                    "Шаг 1 из 7. Выберите формат работы:",
                    reply_markup=format_keyboard(),
                )
        return

    await safe_callback_answer(callback)
    await state.clear()
    await state.update_data(
        edit_mode="field",
        edit_field=None,
        actor_telegram_id=callback.from_user.id,
        can_cancel_edit=True,
    )
    await state.set_state(ArtistFlow.waiting_for_edit_field)
    await safe_fsm_answer(
        callback.message,
        "Что изменить в анкете? Или нажмите ❌ Отменить.",
        reply_markup=cancel_reply_keyboard(),
    )
    await safe_fsm_answer(
        callback.message,
        "Выберите поле для редактирования:",
        reply_markup=profile_field_selection_keyboard(),
    )


async def prompt_selected_field(
    target: Message | CallbackQuery,
    state: FSMContext,
    field_name: str,
) -> None:
    await state.update_data(edit_mode="field", edit_field=field_name)

    target_message = target.message if isinstance(target, CallbackQuery) else target
    if target_message is None:
        return

    if field_name == "format":
        await state.set_state(ArtistFlow.waiting_for_format)
        if await state_matches(state, ArtistFlow.waiting_for_format):
            if await can_cancel_current_edit(state):
                await safe_fsm_answer(
                    target_message,
                    "Выберите новый формат или нажмите ❌ Отменить.",
                    reply_markup=cancel_reply_keyboard(),
                )
                await safe_fsm_answer(target_message, "Выберите новый формат:", reply_markup=format_keyboard())
            else:
                await safe_fsm_answer(target_message, "Выберите новый формат:", reply_markup=format_keyboard())
        return
    if field_name == "portfolio":
        await state.update_data(portfolio_images=[])
        await prompt_portfolio_step(target, state)
        return
    if field_name == "description":
        await state.set_state(ArtistFlow.waiting_for_description)
        if await state_matches(state, ArtistFlow.waiting_for_description):
            if await can_cancel_current_edit(state):
                await safe_fsm_answer(
                    target_message,
                    "Отправьте новое описание.\n"
                    "Отправь новый текст или нажми ❌ Отменить.",
                    reply_markup=cancel_reply_keyboard(),
                )
            else:
                await safe_fsm_answer(target_message, "Отправьте новое описание.")
        return
    if field_name == "price":
        await state.set_state(ArtistFlow.waiting_for_currency)
        if await state_matches(state, ArtistFlow.waiting_for_currency):
            if await can_cancel_current_edit(state):
                await safe_fsm_answer(
                    target_message,
                    "Выберите валюту или нажмите ❌ Отменить.",
                    reply_markup=cancel_reply_keyboard(),
                )
                await safe_fsm_answer(target_message, "Выберите валюту:", reply_markup=currency_keyboard())
            else:
                await safe_fsm_answer(target_message, "Выберите валюту:", reply_markup=currency_keyboard())
        return
    if field_name == "deadline":
        await state.set_state(ArtistFlow.waiting_for_deadline_category)
        if await state_matches(state, ArtistFlow.waiting_for_deadline_category):
            if await can_cancel_current_edit(state):
                await safe_fsm_answer(
                    target_message,
                    "Выберите новые сроки или нажмите ❌ Отменить.",
                    reply_markup=cancel_reply_keyboard(),
                )
                await safe_fsm_answer(
                    target_message,
                    "Выберите новые сроки:",
                    reply_markup=deadline_category_keyboard(),
                )
            else:
                await safe_fsm_answer(
                    target_message,
                    "Выберите новые сроки:",
                    reply_markup=deadline_category_keyboard(),
                )
        return
    if field_name == "contacts":
        await state.set_state(ArtistFlow.waiting_for_contacts_text)
        if await state_matches(state, ArtistFlow.waiting_for_contacts_text):
            if await can_cancel_current_edit(state):
                await safe_fsm_answer(
                    target_message,
                    "Отправьте новые контакты без ссылок.\n"
                    "Отправь новый текст или нажми ❌ Отменить.",
                    reply_markup=cancel_reply_keyboard(),
                )
            else:
                await safe_fsm_answer(target_message, "Отправьте новые контакты без ссылок.")


async def send_profile_view(message: Message, db: Database) -> None:
    if message.from_user is None:
        await safe_answer(message, "Не удалось определить пользователя Telegram.")
        return

    async with db.session() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if user is None or user.role != UserRole.ARTIST:
            await safe_answer(message, artist_access_denied_text())
            return
        profile = await get_artist_profile(session, user.id)

    if not is_active_artist_profile(profile):
        await safe_answer(
            message,
            "Анкета пока не заполнена. Используйте /edit_profile, чтобы создать её."
        )
        return

    await send_profile_card(
        message,
        profile,
        reply_markup=profile_actions_keyboard(),
        title="Моя анкета",
    )


@router.message(F.text == CANCEL_BUTTON_TEXT)
async def cancel_artist_flow(message: Message, state: FSMContext, db: Database) -> None:
    current_state = await state.get_state()
    if current_state is None or not current_state.startswith("ArtistFlow:"):
        return

    if not await can_cancel_current_edit(state):
        await safe_answer(
            message,
            "Создание анкеты ещё не завершено. Продолжите заполнение или используйте /start."
        )
        return

    await state.clear()
    await safe_answer(
        message,
        "Редактирование отменено 👌",
        reply_markup=role_menu_keyboard(UserRole.ARTIST),
    )
    await send_profile_view_with_fallback(message, db)


@router.message(Command("edit_profile"))
async def edit_profile_command(message: Message, db: Database, state: FSMContext) -> None:
    if not await ensure_artist_access(message, db):
        return
    can_cancel_edit = False
    if message.from_user is not None:
        async with db.session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if user is not None and user.role == UserRole.ARTIST:
                can_cancel_edit = is_active_artist_profile(await get_artist_profile(session, user.id))
    await start_artist_profile_flow(
        message,
        state,
        actor_telegram_id=message.from_user.id if message.from_user else None,
        can_cancel_edit=can_cancel_edit,
    )


@router.message(Command("my_profile"))
async def my_profile_command(message: Message, db: Database) -> None:
    await send_profile_view(message, db)


@router.message(F.text == EDIT_PROFILE_BUTTON)
async def edit_profile_button(message: Message, db: Database, state: FSMContext) -> None:
    await edit_profile_command(message, db, state)


@router.message(F.text == EDIT_PROFILE_FIELD_BUTTON)
async def edit_profile_field_button(message: Message, db: Database, state: FSMContext) -> None:
    await start_single_field_edit(message, db, state)


@router.message(F.text == MY_PROFILE_BUTTON)
async def my_profile_button(message: Message, db: Database) -> None:
    await my_profile_command(message, db)


@router.callback_query(F.data == EDIT_PROFILE_CALLBACK)
async def edit_profile_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.message is None or callback.from_user is None or not await ensure_artist_access_callback(callback, db):
        return
    can_cancel_edit = False
    async with db.session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if user is not None and user.role == UserRole.ARTIST:
            can_cancel_edit = is_active_artist_profile(await get_artist_profile(session, user.id))
    await safe_callback_answer(callback)
    await start_artist_profile_flow(
        callback.message,
        state,
        actor_telegram_id=callback.from_user.id,
        can_cancel_edit=can_cancel_edit,
    )


@router.callback_query(F.data == EDIT_PROFILE_FIELD_CALLBACK)
async def edit_profile_field_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    await start_single_field_edit_callback(callback, db, state)


@router.callback_query(F.data == DISABLE_PROFILE_CALLBACK)
async def disable_profile_callback(
    callback: CallbackQuery,
    db: Database,
) -> None:
    if callback.message is None or callback.from_user is None:
        await safe_callback_answer(callback)
        return
    logger.info(
        "artist_disable_profile_clicked user_id=%s data=%s",
        callback.from_user.id,
        callback.data,
    )
    if not await ensure_artist_access_callback(callback, db):
        return
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "Вы точно хотите отключить анкету?",
        reply_markup=disable_profile_confirm_keyboard(),
    )
    logger.info("artist_disable_profile_confirm_shown user_id=%s", callback.from_user.id)


@router.callback_query(F.data == DISABLE_PROFILE_CANCEL_CALLBACK)
async def disable_profile_cancel_callback(
    callback: CallbackQuery,
    db: Database,
) -> None:
    if callback.message is None or callback.from_user is None or not await ensure_artist_access_callback(callback, db):
        return
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "Действия:",
        reply_markup=profile_actions_keyboard(),
    )
    logger.info("artist_disable_profile_cancelled user_id=%s", callback.from_user.id)


@router.callback_query(F.data == DISABLE_PROFILE_CONFIRM_CALLBACK)
async def disable_profile_confirm_callback(
    callback: CallbackQuery,
    db: Database,
    state: FSMContext,
) -> None:
    if callback.message is None or callback.from_user is None or not await ensure_artist_access_callback(callback, db):
        return

    async with db.session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if user is None or user.role != UserRole.ARTIST:
            await safe_callback_answer(callback, "Доступно только для роли Художник.", show_alert=True)
            return
        success = await disable_artist_profile(session, user.id)

    await safe_callback_answer(callback)
    if not success:
        await safe_answer(
            callback.message,
            "Анкета пока не заполнена. Нажмите «Изменить анкету», чтобы создать её."
        )
        return

    await state.clear()
    logger.info("artist_disable_profile_confirmed user_id=%s", callback.from_user.id)
    await safe_answer(
        callback.message,
        "Анкета отключена. Вы можете заполнить новую через «Изменить анкету».",
        reply_markup=role_menu_keyboard(UserRole.ARTIST),
    )


@router.callback_query(
    ArtistFlow.waiting_for_edit_field,
    F.data.startswith(EDIT_FIELD_CALLBACK_PREFIX),
)
async def select_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return

    field_name = callback.data.removeprefix(EDIT_FIELD_CALLBACK_PREFIX)
    if field_name not in EDITABLE_FIELD_NAMES:
        await safe_callback_answer(callback, "Неизвестное поле.", show_alert=True)
        return

    await safe_callback_answer(callback)
    await safe_edit_text(callback.message, "Выберите поле для редактирования:")
    await prompt_selected_field(callback, state, field_name)


@router.callback_query(
    ArtistFlow.waiting_for_format,
    F.data.startswith(FORMAT_CALLBACK_PREFIX),
)
async def set_artist_format(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return

    value = callback.data.removeprefix(FORMAT_CALLBACK_PREFIX)
    await state.update_data(format=value)
    await safe_edit_text(
        callback.message,
        f"Шаг 1 из 7. Формат выбран: <b>{value}</b>."
    )
    await safe_callback_answer(callback)
    state_data = await state.get_data()
    if state_data.get("edit_mode") == "field" and state_data.get("edit_field") == "format":
        await finish_artist_profile_update(callback.message, state, db)
        return
    await prompt_portfolio_step(callback, state)


@router.message(ArtistFlow.waiting_for_portfolio_images, F.photo)
async def collect_portfolio_image(message: Message, state: FSMContext) -> None:
    if not await state_matches(state, ArtistFlow.waiting_for_portfolio_images):
        return

    data = await state.get_data()
    image_ids = list(data.get("portfolio_images", []))

    if len(image_ids) >= MAX_PORTFOLIO_IMAGES:
        return

    photo = message.photo[-2] if len(message.photo) >= 2 else message.photo[-1]
    image_ids.append(photo.file_id)
    if len(image_ids) > MAX_PORTFOLIO_IMAGES:
        image_ids = image_ids[:MAX_PORTFOLIO_IMAGES]
    await state.update_data(portfolio_images=image_ids)

    if len(image_ids) >= MAX_PORTFOLIO_IMAGES:
        await prompt_currency_step_after_portfolio(message, state)
        return


@router.message(ArtistFlow.waiting_for_portfolio_images, F.document)
async def invalid_portfolio_document(message: Message) -> None:
    await safe_fsm_answer(
        message,
        "Пожалуйста, отправьте изображение именно как фото, не как файл."
    )


@router.message(ArtistFlow.waiting_for_portfolio_images, F.text == "Готово")
async def finish_portfolio_step(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    image_ids = list(data.get("portfolio_images", []))

    if not image_ids:
        await safe_fsm_answer(
            message,
            "Сначала отправьте хотя бы одно изображение для портфолио."
        )
        return

    if data.get("edit_mode") == "field" and data.get("edit_field") == "portfolio":
        await finish_artist_profile_update(message, state, db)
        return

    await prompt_currency_step_after_portfolio(message, state)


@router.message(ArtistFlow.waiting_for_portfolio_images)
async def invalid_portfolio_input(message: Message) -> None:
    await safe_fsm_answer(
        message,
        "На этом шаге нужно отправить фото или нажать Готово."
    )


@router.message(ArtistFlow.waiting_for_description, F.text)
async def set_description(message: Message, state: FSMContext, db: Database) -> None:
    description = message.text.strip()
    if not description:
        await safe_fsm_answer(message, "Описание не должно быть пустым.")
        return
    await state.update_data(description=description)
    data = await state.get_data()
    if data.get("edit_mode") == "field" and data.get("edit_field") == "description":
        await finish_artist_profile_update(message, state, db)
        return
    await prompt_deadline_step(message, state)


@router.callback_query(
    ArtistFlow.waiting_for_currency,
    F.data.startswith(CURRENCY_CALLBACK_PREFIX),
)
async def set_currency(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return

    value = callback.data.removeprefix(CURRENCY_CALLBACK_PREFIX)
    await state.update_data(currency=value)
    data = await state.get_data()
    if data.get("edit_mode") == "field" and data.get("edit_field") == "price":
        await safe_edit_text(callback.message, f"Валюта: <b>{value}</b>.")
        await safe_callback_answer(callback)
        await state.set_state(ArtistFlow.waiting_for_price_text)
        if await state_matches(state, ArtistFlow.waiting_for_price_text):
            await safe_fsm_answer(
                callback.message,
                "Отправьте новый прайс.\n"
                "В анкете он будет показан как: ваш текст (валюта).\n"
                "Отправь новый текст или нажми ❌ Отменить.",
                reply_markup=cancel_reply_keyboard(),
            )
        return

    await safe_edit_text(callback.message, f"Шаг 3 из 7. Валюта: <b>{value}</b>.")
    await safe_callback_answer(callback)
    await prompt_price_text_step(callback.message, state)


@router.message(ArtistFlow.waiting_for_price_text, F.text)
async def set_price_text(message: Message, state: FSMContext, db: Database) -> None:
    price_text = message.text.strip()
    if not price_text:
        await safe_fsm_answer(message, "Прайс не должен быть пустым.")
        return
    await state.update_data(price_text=price_text)
    data = await state.get_data()
    if data.get("edit_mode") == "field" and data.get("edit_field") == "price":
        await finish_artist_profile_update(message, state, db)
        return
    await prompt_description_step(message, state)


@router.callback_query(
    ArtistFlow.waiting_for_deadline_category,
    F.data.startswith(DEADLINE_CALLBACK_PREFIX),
)
async def set_deadline_category(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if callback.data is None or callback.message is None:
        await safe_callback_answer(callback)
        return

    value = callback.data.removeprefix(DEADLINE_CALLBACK_PREFIX)
    await state.update_data(deadline_category=value)
    data = await state.get_data()
    if data.get("edit_mode") == "field" and data.get("edit_field") == "deadline":
        await safe_edit_text(
            callback.message,
            f"Сроки: <b>{humanize_deadline_category(value)}</b>."
        )
        await safe_callback_answer(callback)
        await finish_artist_profile_update(callback.message, state, db)
        return

    await safe_edit_text(
        callback.message,
        f"Шаг 6 из 7. Сроки: <b>{humanize_deadline_category(value)}</b>."
    )
    await safe_callback_answer(callback)
    await prompt_contacts_step(callback.message, state)


@router.message(ArtistFlow.waiting_for_contacts_text, F.text)
async def set_contacts_text(
    message: Message,
    state: FSMContext,
    db: Database,
) -> None:
    logger.info(
        "artist_contacts_handler_entered user_id=%s text_len=%s state=%s",
        message.from_user.id if message.from_user else None,
        len(message.text or ""),
        await state.get_state(),
    )
    contacts_text = message.text.strip()
    if not contacts_text:
        await safe_fsm_answer(message, "Контакты не должны быть пустыми.")
        return
    if contacts_have_links(contacts_text):
        logger.info(
            "artist_contacts_validation_failed user_id=%s text=%r",
            message.from_user.id if message.from_user else None,
            contacts_text,
        )
        await safe_fsm_answer(
            message,
            "Контакты должны быть без ссылок на сайты. Уберите URL и домены."
        )
        return

    logger.info(
        "artist_contacts_before_save user_id=%s text=%r",
        message.from_user.id if message.from_user else None,
        contacts_text,
    )
    await state.update_data(contacts_text=contacts_text)
    saved = await finish_artist_profile_update(message, state, db)
    if saved:
        logger.info(
            "artist_contacts_saved user_id=%s",
            message.from_user.id if message.from_user else None,
        )


@router.callback_query(
    ArtistFlow.waiting_for_edit_field,
    (~F.data.startswith("admin:")) & (~F.data.startswith("artist:")),
)
async def invalid_edit_field_callback(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "Выберите поле кнопкой ниже.", show_alert=True)


@router.message(ArtistFlow.waiting_for_description)
@router.message(ArtistFlow.waiting_for_price_text)
async def invalid_text_input(message: Message) -> None:
    await safe_fsm_answer(message, "На этом шаге ожидается текстовое сообщение.")


@router.message(ArtistFlow.waiting_for_contacts_text)
async def invalid_contacts_input(message: Message) -> None:
    await safe_fsm_answer(message, "На этом шаге отправьте контакты обычным текстом.")


@router.callback_query(
    ArtistFlow.waiting_for_currency,
    (~F.data.startswith("admin:")) & (~F.data.startswith("artist:")),
)
@router.callback_query(
    ArtistFlow.waiting_for_deadline_category,
    (~F.data.startswith("admin:")) & (~F.data.startswith("artist:")),
)
async def invalid_option_callback(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "Выберите вариант кнопкой ниже.", show_alert=True)
