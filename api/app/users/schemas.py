"""User schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field
import uuid


class OAuthAccountInfo(BaseModel):
    """OAuth account info."""
    id: uuid.UUID
    provider: str
    provider_user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """User response with OAuth accounts."""
    id: uuid.UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    oauth_accounts: list[OAuthAccountInfo] = []
    
    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """User update request."""
    display_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserDeleteResponse(BaseModel):
    """User delete response."""
    message: str
    deleted_user_id: uuid.UUID
    deleted_email: str


class SyncFromProviderResponse(BaseModel):
    """Response for sync from provider."""
    message: str
    provider: str
    updated_fields: list[str]
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
