from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserRole


ROLE_TITLES: dict[UserRole, str] = {
    UserRole.ARTIST: "Художник",
    UserRole.CLIENT: "Заказчик",
    UserRole.ADMIN: "Администратор",
}


def extract_full_name(user: TelegramUser) -> str:
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username or str(user.id)


async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_user: TelegramUser,
    is_admin: bool = False,
) -> tuple[User, bool]:
    user = await get_user_by_telegram_id(session, telegram_user.id)
    created = False
    full_name = extract_full_name(telegram_user)

    if user is None:
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            full_name=full_name,
            role=UserRole.CLIENT,
        )
        session.add(user)
        created = True
    else:
        user.username = telegram_user.username
        user.full_name = full_name

    await session.commit()
    await session.refresh(user)
    return user, created


async def set_user_role(
    session: AsyncSession,
    user: User,
    role: UserRole,
) -> User:
    user.role = role
    await session.commit()
    await session.refresh(user)
    return user
