from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def start(message: Message):

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎨 Я художник")],
            [KeyboardButton(text="🧑‍💼 Я заказчик")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Привет! Это бот для поиска художников 🎨\n\nКто вы?",
        reply_markup=kb
    )