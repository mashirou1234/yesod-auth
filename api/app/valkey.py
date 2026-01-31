"""Valkey (Redis-compatible) client for OAuth state management."""

import json

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

# Global connection pool
_pool: redis.ConnectionPool | None = None


async def get_valkey() -> redis.Redis:
    """Get Valkey client with connection pooling."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.VALKEY_URL,
            decode_responses=True,
        )
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
        client = await get_valkey()
        data = {"provider": provider}
        if code_verifier:
            data["code_verifier"] = code_verifier

        await client.setex(
            f"{cls.PREFIX}{state}",
            settings.OAUTH_STATE_TTL,
            json.dumps(data),
        )

    @classmethod
    async def save_with_data(cls, state: str, data: dict) -> None:
        """Save OAuth state with custom data."""
        client = await get_valkey()
        await client.setex(
            f"{cls.PREFIX}{state}",
            settings.OAUTH_STATE_TTL,
            json.dumps(data),
        )

    @classmethod
    async def get_and_delete(cls, state: str) -> dict | None:
        """Get and delete OAuth state (one-time use)."""
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

    @classmethod
    async def exists(cls, state: str) -> bool:
        """Check if state exists."""
        client = await get_valkey()
        return await client.exists(f"{cls.PREFIX}{state}") > 0
