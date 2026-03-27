"""Valkey (Redis-compatible) client for OAuth state management."""

import json
import logging

import redis.asyncio as redis
from redis import exceptions as redis_exceptions

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Global connection pool
_pool: redis.ConnectionPool | None = None


def _raise_valkey_error(operation: str, error: Exception) -> None:
    """Classify Valkey failures with retryability hints and raise RuntimeError."""
    if isinstance(error, ValueError):
        message = (
            f"Valkey configuration error during {operation}. "
            "retryable=no next_action=Fix VALKEY_URL/auth settings before retry."
        )
    elif isinstance(error, redis_exceptions.ConnectionError):
        message = (
            f"Valkey unavailable during {operation}. "
            "retryable=yes next_action=Check Valkey reachability/logs, then retry."
        )
    elif isinstance(error, redis_exceptions.TimeoutError):
        message = (
            f"Valkey timeout during {operation}. "
            "retryable=yes next_action=Check Valkey load/network and retry with backoff."
        )
    else:
        message = (
            f"Valkey operation failed during {operation}. "
            "retryable=unknown next_action=Inspect API/Valkey logs and exception cause."
        )

    logger.error(message, exc_info=error)
    raise RuntimeError(message) from error


async def get_valkey() -> redis.Redis:
    """Get Valkey client with connection pooling."""
    global _pool
    if _pool is None:
        try:
            _pool = redis.ConnectionPool.from_url(
                settings.VALKEY_URL,
                decode_responses=True,
            )
        except Exception as error:
            _raise_valkey_error("client initialization", error)
    return redis.Redis(connection_pool=_pool)


async def close_valkey():
    """Close Valkey connection pool."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


class OAuthStateStore:
    """OAuth state management using Valkey."""

    PREFIX = "oauth_state:"

    @classmethod
    async def save(
        cls,
        state: str,
        provider: str,
        code_verifier: str | None = None,
    ) -> None:
        """Save OAuth state with TTL."""
        try:
            client = await get_valkey()
            data = {"provider": provider}
            if code_verifier:
                data["code_verifier"] = code_verifier

            await client.setex(
                f"{cls.PREFIX}{state}",
                settings.OAUTH_STATE_TTL,
                json.dumps(data),
            )
        except Exception as error:
            _raise_valkey_error("oauth_state.save", error)

    @classmethod
    async def save_with_data(cls, state: str, data: dict) -> None:
        """Save OAuth state with custom data."""
        try:
            client = await get_valkey()
            await client.setex(
                f"{cls.PREFIX}{state}",
                settings.OAUTH_STATE_TTL,
                json.dumps(data),
            )
        except Exception as error:
            _raise_valkey_error("oauth_state.save_with_data", error)

    @classmethod
    async def get_and_delete(cls, state: str) -> dict | None:
        """Get and delete OAuth state (one-time use)."""
        try:
            client = await get_valkey()
            key = f"{cls.PREFIX}{state}"

            # Get and delete atomically using pipeline
            pipe = client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            results = await pipe.execute()

            data = results[0]
            if data:
                return json.loads(data)
            return None
        except Exception as error:
            _raise_valkey_error("oauth_state.get_and_delete", error)

    @classmethod
    async def exists(cls, state: str) -> bool:
        """Check if state exists."""
        try:
            client = await get_valkey()
            return await client.exists(f"{cls.PREFIX}{state}") > 0
        except Exception as error:
            _raise_valkey_error("oauth_state.exists", error)
