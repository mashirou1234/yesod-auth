"""User models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, ProjectOwned

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken


class User(ProjectOwned, Base):
    """User identity and its owning project."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("project_id", "id", name="uq_users_project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    profile: Mapped[UserProfile | None] = relationship(
        "UserProfile",
        foreign_keys="UserProfile.user_id",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    emails: Mapped[list[UserEmail]] = relationship(
        "UserEmail",
        foreign_keys="UserEmail.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount",
        foreign_keys="OAuthAccount.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        foreign_keys="RefreshToken.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def email(self) -> str | None:
        """Get primary email."""
        for e in self.emails:
            if e.is_primary:
                return e.email
        return self.emails[0].email if self.emails else None

    @property
    def display_name(self) -> str | None:
        """Get display name from profile."""
        return self.profile.display_name if self.profile else None

    @property
    def avatar_url(self) -> str | None:
        """Get avatar URL from profile."""
        return self.profile.avatar_url if self.profile else None


class UserProfile(ProjectOwned, Base):
    """User profile - display information."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "user_id"], ["users.project_id", "users.id"], ondelete="CASCADE"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="profile",
        foreign_keys=[user_id],
    )


class UserEmail(ProjectOwned, Base):
    """User email - supports multiple emails per user."""

    __tablename__ = "user_emails"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "user_id"], ["users.project_id", "users.id"], ondelete="CASCADE"
        ),
    )
    # Email is an attribute, never an identity/linking key.

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="emails",
        foreign_keys=[user_id],
    )


class DeletedUser(ProjectOwned, Base):
    """Soft-deleted user - for recovery within grace period."""

    __tablename__ = "deleted_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    email_backup: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    display_name_backup: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    purge_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Store OAuth provider IDs for reference
    oauth_providers: Mapped[str | None] = mapped_column(
        String(500),  # JSON string: ["google", "discord"]
        nullable=True,
    )


class OAuthAccount(ProjectOwned, Base):
    """OAuth account linked to a user."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "provider", "provider_user_id", name="uq_oauth_project_identity"
        ),
        ForeignKeyConstraint(
            ["project_id", "user_id"], ["users.project_id", "users.id"], ondelete="CASCADE"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    provider_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    # Provider profile info (for recovery)
    provider_display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    provider_avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    provider_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    # OAuth tokens
    access_token: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    refresh_token: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="oauth_accounts",
        foreign_keys=[user_id],
    )
