from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.db.models import ArtistProfile, ArtistProfileStatus, Complaint, User


def admin_profile_extra(profile: ArtistProfile) -> str:
    owner = profile.user
    blocked = "да" if owner and owner.is_blocked else "нет"
    return (
        f"<b>ID анкеты:</b> {profile.id}\n"
        f"<b>User ID:</b> {profile.user_id}\n"
        f"<b>Статус:</b> {profile.status.value}\n"
        f"<b>Жалобы:</b> {profile.complaints_count}\n"
        f"<b>Лайки:</b> {profile.likes_count}\n"
        f"<b>Сохранения:</b> {profile.saves_count}\n"
        f"<b>Пользователь заблокирован:</b> {blocked}"
    )


async def list_all_profiles(session: AsyncSession) -> list[ArtistProfile]:
    result = await session.execute(
        select(ArtistProfile)
        .options(
            selectinload(ArtistProfile.portfolio_images),
            joinedload(ArtistProfile.user),
        )
        .where(ArtistProfile.status == ArtistProfileStatus.ACTIVE)
        .order_by(ArtistProfile.id.desc())
    )
    return list(result.scalars().unique())


async def list_hidden_profiles(session: AsyncSession) -> list[ArtistProfile]:
    result = await session.execute(
        select(ArtistProfile)
        .options(
            selectinload(ArtistProfile.portfolio_images),
            joinedload(ArtistProfile.user),
        )
        .where(ArtistProfile.status == ArtistProfileStatus.HIDDEN)
        .order_by(ArtistProfile.id.desc())
    )
    return list(result.scalars().unique())


async def list_profiles_with_complaints(session: AsyncSession) -> list[ArtistProfile]:
    result = await session.execute(
        select(ArtistProfile)
        .options(
            selectinload(ArtistProfile.portfolio_images),
            joinedload(ArtistProfile.user),
        )
        .where(ArtistProfile.complaints_count > 0)
        .order_by(ArtistProfile.complaints_count.desc(), ArtistProfile.id.desc())
    )
    return list(result.scalars().unique())


async def get_profile_with_owner(
    session: AsyncSession,
    profile_id: int,
) -> ArtistProfile | None:
    result = await session.execute(
        select(ArtistProfile)
        .options(
            selectinload(ArtistProfile.portfolio_images),
            joinedload(ArtistProfile.user),
        )
        .where(ArtistProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def restore_profile(session: AsyncSession, profile_id: int) -> bool:
    profile = await get_profile_with_owner(session, profile_id)
    if profile is None:
        return False
    profile.status = ArtistProfileStatus.ACTIVE
    await session.commit()
    return True


async def delete_profile(session: AsyncSession, profile_id: int) -> bool:
    profile = await get_profile_with_owner(session, profile_id)
    if profile is None:
        return False
    await session.delete(profile)
    await session.commit()
    return True


async def set_user_blocked(
    session: AsyncSession,
    user_id: int,
    blocked: bool,
) -> bool:
    result = await session.execute(
        select(User)
        .options(joinedload(User.artist_profile))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return False
    user.is_blocked = blocked
    if user.artist_profile is not None and blocked:
        user.artist_profile.status = ArtistProfileStatus.HIDDEN
    await session.commit()
    return True


async def list_all_user_telegram_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(select(User.telegram_id).order_by(User.id.asc()))
    return list(result.scalars())


async def list_profile_complaints(
    session: AsyncSession,
    profile_id: int,
    offset: int = 0,
    limit: int = 5,
) -> tuple[list[Complaint], int]:
    total_result = await session.execute(
        select(func.count(Complaint.id)).where(Complaint.profile_id == profile_id)
    )
    total_count = int(total_result.scalar_one() or 0)

    result = await session.execute(
        select(Complaint)
        .options(joinedload(Complaint.reporter_user))
        .where(Complaint.profile_id == profile_id)
        .order_by(Complaint.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique()), total_count
