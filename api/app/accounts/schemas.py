"""Account schemas."""
from datetime import datetime
from pydantic import BaseModel
import uuid


class OAuthAccountResponse(BaseModel):
    """OAuth account response."""
    id: uuid.UUID
    provider: str
    provider_user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UnlinkResponse(BaseModel):
    """Unlink response."""
    message: str
    provider: str
