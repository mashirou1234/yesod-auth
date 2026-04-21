"""User schemas."""

import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class OAuthAccountInfo(BaseModel):
    """OAuth account information."""

    id: uuid.UUID = Field(..., description="OAuth account record ID")
    provider: str = Field(..., description="OAuth provider name (google, discord)")
    provider_user_id: str = Field(..., description="User ID from the OAuth provider")
    created_at: datetime = Field(..., description="When the account was linked")

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """User profile response with OAuth accounts.

    Contains the user's profile information and all linked OAuth accounts.
    """

    id: uuid.UUID = Field(..., description="Unique user identifier")
    email: str | None = Field(None, description="User's primary email address")
    display_name: str | None = Field(None, description="User's display name")
    avatar_url: str | None = Field(None, description="URL to user's avatar image")
    created_at: datetime = Field(..., description="Account creation timestamp")
    oauth_accounts: list[OAuthAccountInfo] = Field(
        default_factory=list, description="List of linked OAuth accounts"
    )

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """User profile update request.

    Only provided fields will be updated. Set a field to null to clear it.
    """

    display_name: str | None = Field(
        None, max_length=255, description="New display name (max 255 characters)"
    )
    avatar_url: str | None = Field(
        None, max_length=500, description="New avatar URL (max 500 characters)"
    )

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        """Normalize display_name and reject blank-only input."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        """Normalize avatar_url and allow only http(s) URLs."""
        if value is None:
            return None
        normalized = value.strip()
        parsed = urlparse(normalized)
        if not normalized or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("avatar_url must be a valid http(s) URL")
        return normalized


class UserDeleteResponse(BaseModel):
    """User account deletion response.

    The account is soft-deleted and will be permanently purged after the grace period.
    """

    message: str = Field(..., description="Deletion confirmation message")
    deleted_user_id: uuid.UUID = Field(..., description="ID of the deleted user")
    deleted_email: str = Field(..., description="Email of the deleted user")
    scheduled_delete_at: datetime = Field(
        ..., description="Scheduled permanent deletion datetime (UTC)"
    )


class SyncFromProviderResponse(BaseModel):
    """Response for syncing profile from OAuth provider.

    Restores profile information from the stored OAuth provider data.
    """

    message: str = Field(..., description="Sync result message")
    provider: str = Field(..., description="OAuth provider used for sync")
    updated_fields: list[str] = Field(..., description="List of fields that were updated")
    display_name: str | None = Field(None, description="Synced display name")
    avatar_url: str | None = Field(None, description="Synced avatar URL")
