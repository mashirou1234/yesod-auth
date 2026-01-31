"""Account schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class OAuthAccountResponse(BaseModel):
    """OAuth account response with provider info."""

    id: uuid.UUID
    provider: str
    provider_user_id: str
    provider_display_name: str | None = None
    provider_avatar_url: str | None = None
    provider_email: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnlinkResponse(BaseModel):
    """Unlink response."""

    message: str
    provider: str
