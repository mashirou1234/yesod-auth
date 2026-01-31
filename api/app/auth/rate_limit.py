"""Rate limiting configuration."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri=settings.VALKEY_URL,
)


def get_rate_limit_string() -> str:
    """Get current rate limit as string for dynamic updates."""
    return f"{settings.RATE_LIMIT_PER_MINUTE}/minute"
