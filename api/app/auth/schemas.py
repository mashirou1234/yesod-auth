"""Auth schemas."""
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import uuid


class UserResponse(BaseModel):
    """User response schema."""
    id: uuid.UUID
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class OAuthAccountInfo(BaseModel):
    """OAuth account info."""
    provider: str
    provider_user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserWithAccountsResponse(UserResponse):
    """User with linked OAuth accounts."""
    oauth_accounts: list[OAuthAccountInfo] = []


class TokenPairResponse(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request body for refresh token operations."""
    refresh_token: str
