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


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


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
