from aiogram.fsm.state import StatesGroup, State

class ArtistForm(StatesGroup):
    format = State()
    portfolio = State()
    description = State()
    price = State()
    deadline = State()
    currency = State()
    contacts = State()