"""Session schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionResponse(BaseModel):
    """Session response."""

    id: uuid.UUID
    device_info: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime


class SessionListResponse(BaseModel):
    """Session list response."""

    sessions: list[SessionResponse]
    total: int


class RevokeResponse(BaseModel):
    """Revoke response."""

    message: str
    session_id: uuid.UUID | None = None
    revoked_count: int | None = None
