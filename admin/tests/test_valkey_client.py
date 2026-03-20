"""Tests for admin Valkey reconnect behavior."""
import types
import unittest
from unittest.mock import AsyncMock, patch

import redis.asyncio as redis

import valkey_client


class _FakeClient:
    def __init__(self) -> None:
        self.close = AsyncMock()


class ValkeyClientReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_once_with_configured_wait(self) -> None:
        first = _FakeClient()
        second = _FakeClient()
        operation = AsyncMock(
            side_effect=[redis.ConnectionError("down"), [{"ok": True}]]
        )

        settings = types.SimpleNamespace(
            VALKEY_URL="redis://localhost:6379/0",
            VALKEY_RECONNECT_WAIT_SECONDS=1.25,
        )
        with patch.object(valkey_client, "settings", settings), patch.object(
            valkey_client.redis,
            "from_url",
            side_effect=[first, second],
        ) as from_url, patch.object(valkey_client.asyncio, "sleep", new=AsyncMock()) as sleep:
            result = await valkey_client._execute_with_single_retry(operation)

        self.assertEqual(result, [{"ok": True}])
        self.assertEqual(operation.await_count, 2)
        self.assertEqual(from_url.call_count, 2)
        sleep.assert_awaited_once_with(1.25)
        first.close.assert_awaited_once()
        second.close.assert_awaited_once()

    async def test_raises_after_second_failure(self) -> None:
        first = _FakeClient()
        second = _FakeClient()
        operation = AsyncMock(
            side_effect=[redis.ConnectionError("down"), redis.TimeoutError("timeout")]
        )

        settings = types.SimpleNamespace(
            VALKEY_URL="redis://localhost:6379/0",
            VALKEY_RECONNECT_WAIT_SECONDS=0.5,
        )
        with patch.object(valkey_client, "settings", settings), patch.object(
            valkey_client.redis,
            "from_url",
            side_effect=[first, second],
        ), patch.object(valkey_client.asyncio, "sleep", new=AsyncMock()) as sleep:
            with self.assertRaises(redis.TimeoutError):
                await valkey_client._execute_with_single_retry(operation)

        sleep.assert_awaited_once_with(0.5)
        first.close.assert_awaited_once()
        second.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
