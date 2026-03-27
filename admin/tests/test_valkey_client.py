"""Tests for admin valkey_client behavior."""
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import redis.asyncio as redis

import valkey_client


class _FakeClient:
    def __init__(self) -> None:
        self.close = AsyncMock()


class _AsyncIterator:
    def __init__(self, values):
        self._iterator = iter(values)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


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


class ValkeyClientScanTests(unittest.TestCase):
    def _make_client(self, keys, ttl_map, value_map):
        client = Mock()
        client.scan_iter = Mock(return_value=_AsyncIterator(keys))
        client.ttl = AsyncMock()
        client.ttl.side_effect = lambda key: ttl_map[key]
        client.get = AsyncMock()
        client.get.side_effect = lambda key: value_map[key]
        client.keys = AsyncMock()
        client.close = AsyncMock()
        return client

    @patch("valkey_client.redis.from_url")
    def test_get_oauth_states_uses_scan_iter_and_preserves_shape(
        self, mock_from_url
    ) -> None:
        client = self._make_client(
            keys=["oauth_state:abcdefghijklmnopqrstuvwxyz", "oauth_state:state-2"],
            ttl_map={
                "oauth_state:abcdefghijklmnopqrstuvwxyz": 120,
                "oauth_state:state-2": 60,
            },
            value_map={
                "oauth_state:abcdefghijklmnopqrstuvwxyz": '{"provider":"github","code_verifier":"x"}',
                "oauth_state:state-2": '{"provider":"discord"}',
            },
        )
        mock_from_url.return_value = client

        states = valkey_client.get_oauth_states()

        self.assertEqual(
            states,
            [
                {
                    "state": "abcdefghijklmnop...",
                    "provider": "github",
                    "has_pkce": True,
                    "ttl_seconds": 120,
                },
                {
                    "state": "state-2...",
                    "provider": "discord",
                    "has_pkce": False,
                    "ttl_seconds": 60,
                },
            ],
        )
        client.scan_iter.assert_called_once_with(match="oauth_state:*")
        client.keys.assert_not_called()
        client.close.assert_awaited_once()

    @patch("valkey_client.redis.from_url")
    def test_get_rate_limit_info_handles_empty_scan_result(self, mock_from_url) -> None:
        client = self._make_client(keys=[], ttl_map={}, value_map={})
        mock_from_url.return_value = client

        limits = valkey_client.get_rate_limit_info()

        self.assertEqual(limits, [])
        client.scan_iter.assert_called_once_with(match="LIMITER:*")
        client.keys.assert_not_called()
        client.close.assert_awaited_once()

    @patch("valkey_client.redis.from_url")
    def test_get_rate_limit_info_handles_multiple_scan_results(
        self, mock_from_url
    ) -> None:
        client = self._make_client(
            keys=["LIMITER:1", "LIMITER:2"],
            ttl_map={"LIMITER:1": 30, "LIMITER:2": 15},
            value_map={"LIMITER:1": "3", "LIMITER:2": "7"},
        )
        mock_from_url.return_value = client

        limits = valkey_client.get_rate_limit_info()

        self.assertEqual(
            limits,
            [
                {"key": "LIMITER:1", "count": "3", "ttl_seconds": 30},
                {"key": "LIMITER:2", "count": "7", "ttl_seconds": 15},
            ],
        )
        client.scan_iter.assert_called_once_with(match="LIMITER:*")
        client.keys.assert_not_called()
        client.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
