import logging
from time import perf_counter

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    ArtistProfile,
    ArtistProfileStatus,
    ClientFilter,
    Complaint,
    ProfileAction,
    ProfileActionType,
)

COMPLAINT_HIDE_THRESHOLD = 3
logger = logging.getLogger(__name__)


async def _query_next_artist_profile(
    session: AsyncSession,
    client_user_id: int,
    client_filter: ClientFilter,
) -> ArtistProfile | None:
    blocked_actions = (
        select(ProfileAction.id)
        .where(
            ProfileAction.client_user_id == client_user_id,
            ProfileAction.profile_id == ArtistProfile.id,
            ProfileAction.action.in_(
                [
                    ProfileActionType.SAVE,
                    ProfileActionType.SKIP,
                ]
            ),
        )
        .limit(1)
    )

    result = await session.execute(
        select(ArtistProfile)
        .options(selectinload(ArtistProfile.portfolio_images))
        .where(ArtistProfile.status == ArtistProfileStatus.ACTIVE)
        .where(ArtistProfile.format == client_filter.format)
        .where(ArtistProfile.deadline_category == client_filter.deadline_category)
        .where(~blocked_actions.exists())
        .order_by(ArtistProfile.id.asc())
        .limit(1)
    )
    return result.scalars().unique().first()


async def clear_skip_actions(
    session: AsyncSession,
    client_user_id: int,
) -> None:
    await session.execute(
        delete(ProfileAction).where(
            ProfileAction.client_user_id == client_user_id,
            ProfileAction.action == ProfileActionType.SKIP,
        )
    )
    await session.commit()


async def get_next_artist_profile(
    session: AsyncSession,
    client_user_id: int,
    client_filter: ClientFilter,
) -> tuple[ArtistProfile | None, bool]:
    started_at = perf_counter()
    profile = await _query_next_artist_profile(session, client_user_id, client_filter)
    if profile is not None:
        logger.info(
            "get_next_artist_profile client_user_id=%s reset_circle=false profile_id=%s duration_ms=%.1f",
            client_user_id,
            profile.id,
            (perf_counter() - started_at) * 1000,
        )
        return profile, False

    await clear_skip_actions(session, client_user_id)
    profile = await _query_next_artist_profile(session, client_user_id, client_filter)
    logger.info(
        "get_next_artist_profile client_user_id=%s reset_circle=true profile_id=%s duration_ms=%.1f",
        client_user_id,
        profile.id if profile is not None else None,
        (perf_counter() - started_at) * 1000,
    )
    return profile, True


async def get_profile_for_action_update(
    session: AsyncSession,
    profile_id: int,
) -> ArtistProfile | None:
    result = await session.execute(
        select(ArtistProfile).where(ArtistProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def get_profile_by_id(
    session: AsyncSession,
    profile_id: int,
) -> ArtistProfile | None:
    result = await session.execute(
        select(ArtistProfile)
        .options(
            selectinload(ArtistProfile.portfolio_images),
            selectinload(ArtistProfile.user),
        )
        .where(ArtistProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def get_existing_action(
    session: AsyncSession,
    client_user_id: int,
    profile_id: int,
    action: ProfileActionType,
) -> ProfileAction | None:
    result = await session.execute(
        select(ProfileAction).where(
            ProfileAction.client_user_id == client_user_id,
            ProfileAction.profile_id == profile_id,
            ProfileAction.action == action,
        )
    )
    return result.scalar_one_or_none()


async def add_like(
    session: AsyncSession,
    client_user_id: int,
    profile_id: int,
) -> bool:
    existing = await get_existing_action(
        session,
        client_user_id,
        profile_id,
        ProfileActionType.LIKE,
    )
    if existing is not None:
        return False

    profile = await get_profile_for_action_update(session, profile_id)
    if profile is None:
        return False

    session.add(
        ProfileAction(
            client_user_id=client_user_id,
            profile_id=profile_id,
            action=ProfileActionType.LIKE,
        )
    )
    profile.likes_count += 1
    await session.commit()
    return True


async def add_save(
    session: AsyncSession,
    client_user_id: int,
    profile_id: int,
) -> bool:
    existing = await get_existing_action(
        session,
        client_user_id,
        profile_id,
        ProfileActionType.SAVE,
    )
    if existing is not None:
        return False

    profile = await get_profile_for_action_update(session, profile_id)
    if profile is None:
        return False

    session.add(
        ProfileAction(
            client_user_id=client_user_id,
            profile_id=profile_id,
            action=ProfileActionType.SAVE,
        )
    )
    profile.saves_count += 1
    await session.commit()
    return True


async def remove_save(
    session: AsyncSession,
    client_user_id: int,
    profile_id: int,
) -> bool:
    existing = await get_existing_action(
        session,
        client_user_id,
        profile_id,
        ProfileActionType.SAVE,
    )
    if existing is None:
        return False

    profile = await get_profile_for_action_update(session, profile_id)
    await session.delete(existing)
    if profile is not None and profile.saves_count > 0:
        profile.saves_count -= 1

    await session.commit()
    return True


async def add_contact(
    session: AsyncSession,
    client_user_id: int,
    profile_id: int,
) -> bool:
    existing = await get_existing_action(
        session,
        client_user_id,
        profile_id,
        ProfileActionType.CONTACT,
    )
    if existing is not None:
        return False

    profile = await get_profile_for_action_update(session, profile_id)
    if profile is None:
        return False

    session.add(
        ProfileAction(
            client_user_id=client_user_id,
            profile_id=profile_id,
            action=ProfileActionType.CONTACT,
        )
    )
    await session.commit()
    return True


async def add_skip(
    session: AsyncSession,
    client_user_id: int,
    profile_id: int,
) -> None:
    existing = await get_existing_action(
        session,
        client_user_id,
        profile_id,
        ProfileActionType.SKIP,
    )

    if existing is None:
        session.add(
            ProfileAction(
                client_user_id=client_user_id,
                profile_id=profile_id,
                action=ProfileActionType.SKIP,
            )
        )

    await session.commit()


async def add_complaint(
    session: AsyncSession,
    client_user_id: int,
    profile_id: int,
    reason: str,
) -> bool:
    existing = await session.execute(
        select(Complaint).where(
            Complaint.reporter_user_id == client_user_id,
            Complaint.profile_id == profile_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    profile = await get_profile_for_action_update(session, profile_id)
    if profile is None:
        return False

    session.add(
        Complaint(
            profile_id=profile_id,
            reporter_user_id=client_user_id,
            reason=reason,
            status="new",
        )
    )
    profile.complaints_count += 1
    if profile.complaints_count >= COMPLAINT_HIDE_THRESHOLD:
        profile.status = ArtistProfileStatus.HIDDEN

    await session.commit()
    return True


async def get_saved_profiles(
    session: AsyncSession,
    client_user_id: int,
) -> list[ArtistProfile]:
    result = await session.execute(
        select(ArtistProfile)
        .join(ProfileAction, ProfileAction.profile_id == ArtistProfile.id)
        .options(selectinload(ArtistProfile.portfolio_images))
        .where(ProfileAction.client_user_id == client_user_id)
        .where(ProfileAction.action == ProfileActionType.SAVE)
        .order_by(ArtistProfile.id.desc())
    )
    return list(result.scalars().unique())
