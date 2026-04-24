from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto

from states.artist import ArtistForm

router = Router()


@router.message(lambda message: message.text == "🎨 Я художник")
async def artist(message: Message):

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Создать анкету")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Вы художник. Создать анкету?",
        reply_markup=kb
    )


@router.message(lambda message: message.text == "📝 Создать анкету")
async def create_profile(message: Message, state: FSMContext):
    await message.answer(
        "Выберите формат:\n"
        "Digital / Traditional / 3D / Animation"
    )
    await state.set_state(ArtistForm.format)


# ---------- ФОРМАТ ----------
@router.message(ArtistForm.format)
async def process_format(message: Message, state: FSMContext):
    await state.update_data(format=message.text)

    await message.answer(
        "Загрузите до 5 фото портфолио.\n"
        "Когда закончите — напишите 'готово'"
    )

    await state.set_state(ArtistForm.portfolio)


# ---------- ПОРТФОЛИО ----------
@router.message(ArtistForm.portfolio)
async def process_portfolio(message: Message, state: FSMContext):

    data = await state.get_data()
    photos = data.get("photos", [])

    if message.photo:
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)

        await message.answer(f"Фото добавлено ({len(photos)}/5)")

        if len(photos) >= 5:
            await message.answer("Напишите описание анкеты")
            await state.set_state(ArtistForm.description)

    elif message.text and message.text.lower() == "готово":
        await message.answer("Напишите описание анкеты")
        await state.set_state(ArtistForm.description)


# ---------- ОПИСАНИЕ ----------
@router.message(ArtistForm.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)

    await message.answer(
        "Введите цену\n"
        "Например: 500-1500 или 'договорная'"
    )

    await state.set_state(ArtistForm.price)


# ---------- ЦЕНА ----------
@router.message(ArtistForm.price)
async def process_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)

    await message.answer(
        "Выберите дедлайн:\n"
        "1-5 часов / 1-5 дней / 1-5 недель / 1-5 месяцев / свободный"
    )

    await state.set_state(ArtistForm.deadline)


# ---------- ДЕДЛАЙН ----------
@router.message(ArtistForm.deadline)
async def process_deadline(message: Message, state: FSMContext):
    await state.update_data(deadline=message.text)

    await message.answer(
        "Выберите валюту:\n"
        "USD / EUR / CNY / RUB / JPY / KZT / BYN / UAH"
    )

    await state.set_state(ArtistForm.currency)


# ---------- ВАЛЮТА ----------
@router.message(ArtistForm.currency)
async def process_currency(message: Message, state: FSMContext):
    await state.update_data(currency=message.text)

    await message.answer("Введите контакты (без ссылок)")
    await state.set_state(ArtistForm.contacts)


# ---------- КОНТАКТЫ ----------
@router.message(ArtistForm.contacts)
async def process_contacts(message: Message, state: FSMContext):
    await state.update_data(contacts=message.text)

    data = await state.get_data()

    photos = data.get("photos", [])

    text = (
        "🎨 Ваша анкета:\n\n"
        f"Формат: {data['format']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: {data['price']} {data['currency']}\n"
        f"Дедлайн: {data['deadline']}\n"
        f"Контакты: {data['contacts']}"
    )

    media = []

    for i, photo in enumerate(photos):
        if i == 0:
            media.append(InputMediaPhoto(media=photo, caption=text))
        else:
            media.append(InputMediaPhoto(media=photo))

    await message.answer_media_group(media)

    await state.clear()