"""Account schemas."""

import uuid
from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel

AccountProvider = Literal["google", "discord"]
SUPPORTED_ACCOUNT_PROVIDERS = frozenset(get_args(AccountProvider))


class OAuthAccountResponse(BaseModel):
    """OAuth account response with provider info."""

    id: uuid.UUID
    provider: AccountProvider
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
    provider: AccountProvider
