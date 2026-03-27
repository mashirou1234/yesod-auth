"""Valkey error classification tests."""

from unittest.mock import AsyncMock, patch

import pytest
from redis import exceptions as redis_exceptions

from app import valkey


@pytest.fixture(autouse=True)
async def _cleanup_pool():
    """Reset global pool before/after each test to avoid cross-test leakage."""
    await valkey.close_valkey()
    yield
    await valkey.close_valkey()


@pytest.mark.asyncio
async def test_get_valkey_classifies_configuration_error():
    """Invalid connection settings are marked as non-retryable."""
    with patch("app.valkey.redis.ConnectionPool.from_url", side_effect=ValueError("bad url")):
        with pytest.raises(RuntimeError, match="configuration error") as exc_info:
            await valkey.get_valkey()

    message = str(exc_info.value)
    assert "retryable=no" in message
    assert "Fix VALKEY_URL/auth settings" in message


@pytest.mark.asyncio
async def test_save_classifies_connection_error_as_retryable():
    """Reachability failures are marked as retryable with recovery guidance."""
    mock_client = AsyncMock()
    mock_client.setex.side_effect = redis_exceptions.ConnectionError("connection refused")

    with patch("app.valkey.get_valkey", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Valkey unavailable") as exc_info:
            await valkey.OAuthStateStore.save("state-1", "github")

    message = str(exc_info.value)
    assert "retryable=yes" in message
    assert "Check Valkey reachability/logs" in message
