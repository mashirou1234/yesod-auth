"""Rate limiting configuration."""

import inspect

from fastapi import Request
from fastapi.responses import Response
from slowapi import Limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.metrics import record_oauth_rate_limit_burst_metric
from app.oauth_providers import OAUTH_PROVIDER_ORDER

settings = get_settings()
SUPPORTED_OAUTH_PROVIDERS = frozenset(OAUTH_PROVIDER_ORDER)
MISSING_OAUTH_PROVIDER_KEY = "missing_provider"

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri=settings.VALKEY_URL,
    headers_enabled=True,
)


def get_rate_limit_string() -> str:
    """Get current rate limit as string for dynamic updates."""
    return f"{settings.RATE_LIMIT_PER_MINUTE}/minute"


def extract_oauth_provider_from_path(path: str) -> str | None:
    """Extract OAuth provider from /api/v1/auth/<provider> paths."""
    prefix = "/api/v1/auth/"
    if not path.startswith(prefix):
        return None

    remainder = path.removeprefix(prefix)
    if not remainder or "/" in remainder:
        return None

    provider = remainder
    if provider in SUPPORTED_OAUTH_PROVIDERS:
        return provider
    return None


def resolve_oauth_provider_metric_key(path: str) -> str | None:
    """Resolve provider metric key with stable fallback for auth paths."""
    provider = extract_oauth_provider_from_path(path)
    if provider is not None:
        return provider
    if path.startswith("/api/v1/auth/"):
        return MISSING_OAUTH_PROVIDER_KEY
    return None


async def oauth_rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> Response:
    """Record provider-level burst rate-limit metric before returning 429."""
    provider = resolve_oauth_provider_metric_key(request.url.path)
    if provider is not None:
        record_oauth_rate_limit_burst_metric(provider)

    response = _rate_limit_exceeded_handler(request, exc)
    if inspect.isawaitable(response):
        return await response
    return response
