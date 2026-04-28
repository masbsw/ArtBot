import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ArtistProfile, ArtistProfileStatus, PortfolioImage

MAX_PORTFOLIO_IMAGES = 2

FORMAT_LABELS: dict[str, str] = {
    "digital": "digital",
    "traditional": "traditional",
    "animation": "animation",
    "3d": "3D",
}


DEADLINE_CATEGORY_LABELS: dict[str, str] = {
    "1-5 hours": "1–5 часов",
    "1-5 days": "1–5 дней",
    "1-5 weeks": "1–5 недель",
    "1-5 months": "1–5 месяцев",
    "free deadline": "Свободный дедлайн",
}

CONTACT_LINK_PATTERN = re.compile(
    r"(https?://|t\.me/|telegram\.me/|www\.|\b[a-z0-9-]+\.(?:ru|com|net|org|site|online)\b)",
    re.IGNORECASE,
)


async def get_artist_profile(
    session: AsyncSession,
    user_id: int,
) -> ArtistProfile | None:
    result = await session.execute(
        select(ArtistProfile)
        .options(selectinload(ArtistProfile.portfolio_images))
        .where(ArtistProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


def contacts_have_links(value: str) -> bool:
    return CONTACT_LINK_PATTERN.search(value) is not None


def humanize_format(value: str | None) -> str:
    if not value:
        return "Не указано"
    return FORMAT_LABELS.get(value, value)





def humanize_deadline_category(value: str | None) -> str:
    if not value:
        return "Не указано"
    return DEADLINE_CATEGORY_LABELS.get(value, value)


def display_value(value: str | None) -> str:
    if value is None:
        return "Не указано"
    normalized = value.strip()
    return normalized or "Не указано"


def build_price_display(price_text: str | None, currency: str | None) -> str:
    price = display_value(price_text)
    curr = display_value(currency)

    if price == "Не указано" and curr == "Не указано":
        return "Не указано"
    if price == "Не указано":
        return "Не указано"
    if curr == "Не указано":
        return price
    return f"{price} ({curr})"


async def upsert_artist_profile(
    session: AsyncSession,
    user_id: int,
    form_data: dict[str, str | list[str]],
) -> ArtistProfile:
    profile = await get_artist_profile(session, user_id)
    image_ids = list(form_data["portfolio_images"])[:MAX_PORTFOLIO_IMAGES]

    if profile is None:
        profile = ArtistProfile(user_id=user_id)
        session.add(profile)

    profile.format = str(form_data["format"])
    profile.description = str(form_data["description"])
    profile.currency = str(form_data["currency"])
    profile.price_text = str(form_data["price_text"])
    profile.price_category = None
    profile.deadline_category = str(form_data["deadline_category"])
    profile.contacts_text = str(form_data["contacts_text"])
    profile.status = ArtistProfileStatus.ACTIVE

    profile.portfolio_images.clear()
    for position, file_id in enumerate(image_ids, start=1):
        profile.portfolio_images.append(
            PortfolioImage(
                telegram_file_id=file_id,
                position=position,
            )
        )

    await session.commit()
    await session.refresh(profile)
    await session.refresh(profile, attribute_names=["portfolio_images"])
    return profile
