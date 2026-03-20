"""Valkey operations for admin."""
import asyncio
import json
import redis.asyncio as redis
from config import settings


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_oauth_states() -> list[dict]:
    async def _read(client) -> list[dict]:
        keys = await client.keys("oauth_state:*")
        states = []
        for key in keys:
            ttl = await client.ttl(key)
            value = await client.get(key)
            data = json.loads(value) if value else {}
            states.append({
                "state": key.replace("oauth_state:", "")[:16] + "...",
                "provider": data.get("provider", "unknown"),
                "has_pkce": "code_verifier" in data,
                "ttl_seconds": ttl,
            })
        return states

    return await _execute_with_single_retry(_read)


async def _get_rate_limit_info() -> list[dict]:
    async def _read(client) -> list[dict]:
        keys = await client.keys("LIMITER:*")
        limits = []
        for key in keys:
            ttl = await client.ttl(key)
            value = await client.get(key)
            limits.append({
                "key": key,
                "count": value,
                "ttl_seconds": ttl,
            })
        return limits

    return await _execute_with_single_retry(_read)


async def _execute_with_single_retry(operation):
    for attempt in range(2):
        client = redis.from_url(settings.VALKEY_URL, decode_responses=True)
        try:
            return await operation(client)
        except (redis.ConnectionError, redis.TimeoutError):
            if attempt == 1:
                raise
            await asyncio.sleep(settings.VALKEY_RECONNECT_WAIT_SECONDS)
        finally:
            await client.close()


def get_oauth_states() -> list[dict]:
    return run_async(_get_oauth_states())


def get_rate_limit_info() -> list[dict]:
    return run_async(_get_rate_limit_info())
