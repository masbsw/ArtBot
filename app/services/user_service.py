from aiogram.types import User as TelegramUser


def extract_full_name(user: TelegramUser) -> str:
    return " ".join(part for part in [user.first_name, user.last_name] if part).strip()
