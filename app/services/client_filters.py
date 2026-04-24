from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ArtistProfile, ArtistProfileStatus, ClientFilter


async def get_client_filter(
    session: AsyncSession,
    user_id: int,
) -> ClientFilter | None:
    result = await session.execute(
        select(ClientFilter).where(ClientFilter.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_client_filter(
    session: AsyncSession,
    user_id: int,
    filter_data: dict[str, str],
) -> ClientFilter:
    client_filter = await get_client_filter(session, user_id)

    if client_filter is None:
        client_filter = ClientFilter(user_id=user_id)
        session.add(client_filter)

    client_filter.format = filter_data["format"]
    client_filter.deadline_category = filter_data["deadline_category"]

    await session.commit()
    await session.refresh(client_filter)
    return client_filter


async def find_matching_artist_profile(
    session: AsyncSession,
    client_filter: ClientFilter,
) -> ArtistProfile | None:
    result = await session.execute(
        select(ArtistProfile)
        .options(selectinload(ArtistProfile.portfolio_images))
        .where(ArtistProfile.status == ArtistProfileStatus.ACTIVE)
        .where(ArtistProfile.format == client_filter.format)
        .where(ArtistProfile.deadline_category == client_filter.deadline_category)
        .order_by(ArtistProfile.id.asc())
    )
    return result.scalars().unique().first()
