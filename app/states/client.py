from aiogram.fsm.state import State, StatesGroup


class ClientFlow(StatesGroup):
    waiting_for_format = State()
    waiting_for_deadline_category = State()
    waiting_for_complaint_reason = State()
