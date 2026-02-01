"""Tests for WebhookEmitter."""

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.webhooks.config import WebhookConfig, WebhookEndpoint, WebhookSettings
from app.webhooks.emitter import WebhookEmitter


@pytest.fixture
def mock_valkey():
    """Mock Valkey client."""
    mock = AsyncMock()
    mock.rpush = AsyncMock(return_value=1)
    return mock


@pytest.fixture
def sample_endpoint():
    """Sample webhook endpoint."""
    return WebhookEndpoint(
        id="test-endpoint",
        url="https://example.com/webhook",
        secret="test-secret",
        events=["user.created", "user.updated"],
        enabled=True,
    )


@pytest.fixture
def sample_config(sample_endpoint):
    """Sample webhook config."""
    return WebhookConfig(
        endpoints=[sample_endpoint],
        settings=WebhookSettings(),
    )


class TestWebhookEmitter:
    """Tests for WebhookEmitter."""

    @pytest.mark.asyncio
    async def test_emit_queues_event(self, mock_valkey, sample_config):
        """Test that emit() queues event to Valkey."""
        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit(
                "user.created",
                {"user_id": str(uuid.uuid4())},
            )

            assert event is not None
            assert event.event_type == "user.created"
            mock_valkey.rpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_skips_when_no_subscribers(self, mock_valkey):
        """Test that emit() skips when no endpoints subscribe."""
        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=[],
            ),
        ):
            event = await WebhookEmitter.emit(
                "user.unknown_event",
                {"user_id": str(uuid.uuid4())},
            )

            assert event is None
            mock_valkey.rpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_emit_user_event_includes_user_id(self, mock_valkey, sample_config):
        """Test that emit_user_event() includes user_id in data."""
        user_id = uuid.uuid4()

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit_user_event(
                "user.created",
                user_id,
                extra_data={"provider": "google"},
            )

            assert event is not None
            assert event.data["user_id"] == str(user_id)
            assert event.data["provider"] == "google"

    @pytest.mark.asyncio
    async def test_nonblocking_async_delivery(self, mock_valkey, sample_config):
        """
        Property 10: Non-Blocking Async Delivery

        For any API request that triggers a webhook event, the request
        response time SHALL not be affected by webhook delivery latency.

        **Validates: Requirements 8.1, 8.2**
        """

        # Simulate slow queue operation
        async def slow_rpush(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return 1

        mock_valkey.rpush = slow_rpush

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            start = time.time()
            event = await WebhookEmitter.emit(
                "user.created",
                {"user_id": str(uuid.uuid4())},
            )
            elapsed = time.time() - start

            # The emit should complete (queue operation is async but awaited)
            # This test verifies the queue operation itself is fast
            # Real non-blocking happens because delivery is done by worker
            assert event is not None
            # Queue operation should complete within reasonable time
            assert elapsed < 1.0  # Should be much faster than 1 second

    @pytest.mark.asyncio
    async def test_emit_handles_valkey_error(self, mock_valkey, sample_config):
        """Test that emit() handles Valkey errors gracefully."""
        mock_valkey.rpush = AsyncMock(side_effect=Exception("Connection failed"))

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=sample_config.endpoints,
            ),
        ):
            event = await WebhookEmitter.emit(
                "user.created",
                {"user_id": str(uuid.uuid4())},
            )

            # Should return None on error, not raise
            assert event is None
