from aiogram.fsm.state import State, StatesGroup


class ArtistFlow(StatesGroup):
    waiting_for_edit_field = State()
    waiting_for_format = State()
    waiting_for_portfolio_images = State()
    waiting_for_description = State()
    waiting_for_currency = State()
    waiting_for_price_text = State()
    waiting_for_deadline_category = State()
    waiting_for_contacts_text = State()
