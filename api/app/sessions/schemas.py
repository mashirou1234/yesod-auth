"""Session schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import uuid


class SessionResponse(BaseModel):
    """Session response."""
    id: uuid.UUID
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: datetime


class SessionListResponse(BaseModel):
    """Session list response."""
    sessions: list[SessionResponse]
    total: int


class RevokeResponse(BaseModel):
    """Revoke response."""
    message: str
    session_id: Optional[uuid.UUID] = None
    revoked_count: Optional[int] = None
