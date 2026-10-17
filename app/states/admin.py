from aiogram.fsm.state import State, StatesGroup


class AdminFlow(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_broadcast_confirm = State()
    waiting_for_profile_id = State()
    waiting_for_moderation_reason = State()
