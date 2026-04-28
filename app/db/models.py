from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class UserRole(str, Enum):
    ARTIST = "artist"
    CLIENT = "client"
    ADMIN = "admin"


class ArtistProfileStatus(str, Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    MODERATION = "moderation"


class ProfileActionType(str, Enum):
    LIKE = "like"
    SAVE = "save"
    SKIP = "skip"
    CONTACT = "contact"


class User(CreatedAtMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role", native_enum=False),
        default=UserRole.CLIENT,
        nullable=False,
    )
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    artist_profile: Mapped["ArtistProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
    )
    client_filter: Mapped["ClientFilter | None"] = relationship(
        back_populates="user",
        uselist=False,
    )
    profile_actions: Mapped[list["ProfileAction"]] = relationship(
        back_populates="client_user",
        foreign_keys="ProfileAction.client_user_id",
    )
    complaints_reported: Mapped[list["Complaint"]] = relationship(
        back_populates="reporter_user",
        foreign_keys="Complaint.reporter_user_id",
    )


class ArtistProfile(TimestampMixin, Base):
    __tablename__ = "artist_profiles"
    __table_args__ = (
        Index(
            "ix_artist_profiles_status_format_deadline",
            "status",
            "format",
            "deadline_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    format: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    price_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deadline_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contacts_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ArtistProfileStatus] = mapped_column(
        SqlEnum(
            ArtistProfileStatus,
            name="artist_profile_status",
            native_enum=False,
        ),
        default=ArtistProfileStatus.MODERATION,
        nullable=False,
    )
    complaints_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    views_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    likes_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    saves_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    user: Mapped[User] = relationship(back_populates="artist_profile")
    portfolio_images: Mapped[list["PortfolioImage"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="PortfolioImage.position",
    )
    actions: Mapped[list["ProfileAction"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class PortfolioImage(Base):
    __tablename__ = "portfolio_images"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("artist_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile: Mapped[ArtistProfile] = relationship(back_populates="portfolio_images")


class ClientFilter(TimestampMixin, Base):
    __tablename__ = "client_filters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    format: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    max_price_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deadline_category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="client_filter")


class ProfileAction(CreatedAtMixin, Base):
    __tablename__ = "profile_actions"
    __table_args__ = (
        Index(
            "ix_profile_actions_client_profile",
            "client_user_id",
            "profile_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("artist_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[ProfileActionType] = mapped_column(
        SqlEnum(ProfileActionType, name="profile_action_type", native_enum=False),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    client_user: Mapped[User] = relationship(
        back_populates="profile_actions",
        foreign_keys=[client_user_id],
    )
    profile: Mapped[ArtistProfile] = relationship(back_populates="actions")


class Complaint(CreatedAtMixin, Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("artist_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)

    profile: Mapped[ArtistProfile] = relationship(back_populates="complaints")
    reporter_user: Mapped[User] = relationship(
        back_populates="complaints_reported",
        foreign_keys=[reporter_user_id],
    )
