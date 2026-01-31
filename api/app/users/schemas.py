"""User schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


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
    email: Optional[str] = Field(None, description="User's primary email address")
    display_name: Optional[str] = Field(None, description="User's display name")
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar image")
    created_at: datetime = Field(..., description="Account creation timestamp")
    oauth_accounts: list[OAuthAccountInfo] = Field(
        default_factory=list,
        description="List of linked OAuth accounts"
    )
    
    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """User profile update request.
    
    Only provided fields will be updated. Set a field to null to clear it.
    """
    display_name: Optional[str] = Field(
        None,
        max_length=255,
        description="New display name (max 255 characters)"
    )
    avatar_url: Optional[str] = Field(
        None,
        max_length=500,
        description="New avatar URL (max 500 characters)"
    )


class UserDeleteResponse(BaseModel):
    """User account deletion response.
    
    The account is soft-deleted and will be permanently purged after the grace period.
    """
    message: str = Field(..., description="Deletion confirmation message")
    deleted_user_id: uuid.UUID = Field(..., description="ID of the deleted user")
    deleted_email: str = Field(..., description="Email of the deleted user")


class SyncFromProviderResponse(BaseModel):
    """Response for syncing profile from OAuth provider.
    
    Restores profile information from the stored OAuth provider data.
    """
    message: str = Field(..., description="Sync result message")
    provider: str = Field(..., description="OAuth provider used for sync")
    updated_fields: list[str] = Field(..., description="List of fields that were updated")
    display_name: Optional[str] = Field(None, description="Synced display name")
    avatar_url: Optional[str] = Field(None, description="Synced avatar URL")
