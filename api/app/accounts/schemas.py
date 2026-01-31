"""Account schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import uuid


class OAuthAccountResponse(BaseModel):
    """OAuth account response with provider info."""
    id: uuid.UUID
    provider: str
    provider_user_id: str
    provider_display_name: Optional[str] = None
    provider_avatar_url: Optional[str] = None
    provider_email: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class UnlinkResponse(BaseModel):
    """Unlink response."""
    message: str
    provider: str
