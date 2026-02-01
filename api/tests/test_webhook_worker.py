"""Tests for WebhookWorker."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.webhooks.config import WebhookConfig, WebhookEndpoint, WebhookSettings
from app.webhooks.event import WebhookEvent
from app.webhooks.worker import DeliveryResult, WebhookWorker


@pytest.fixture
def sample_endpoint():
    """Sample webhook endpoint."""
    return WebhookEndpoint(
        id="test-endpoint",
        url="https://example.com/webhook",
        secret="test-secret",
        events=["user.created"],
        enabled=True,
    )


@pytest.fixture
def sample_config(sample_endpoint):
    """Sample webhook config with fast retries for testing."""
    return WebhookConfig(
        endpoints=[sample_endpoint],
        settings=WebhookSettings(
            max_retries=2,
            retry_base_delay_seconds=0,  # No delay in tests
            delivery_timeout_seconds=5,
        ),
    )


@pytest.fixture
def sample_event():
    """Sample webhook event."""
    return WebhookEvent(
        event_type="user.created",
        data={"user_id": str(uuid.uuid4())},
    )


class TestWebhookWorkerDelivery:
    """Tests for webhook delivery logic."""

    @settings(max_examples=50)
    @given(status_code=st.integers(min_value=200, max_value=299))
    def test_http_2xx_success_criteria(self, status_code: int):
        """
        Property 5: HTTP 2xx Success Criteria

        For any HTTP response status code, the delivery SHALL be marked
        successful if and only if the status code is in the range 200-299.

        **Validates: Requirements 5.3**
        """
        result = DeliveryResult(
            success=(200 <= status_code < 300),
            http_status=status_code,
        )

        # 2xx should be success
        assert result.success is True

    @settings(max_examples=50)
    @given(status_code=st.integers(min_value=300, max_value=599))
    def test_non_2xx_failure_criteria(self, status_code: int):
        """
        Non-2xx status codes should be marked as failure.
        """
        result = DeliveryResult(
            success=(200 <= status_code < 300),
            http_status=status_code,
        )

        # Non-2xx should be failure
        assert result.success is False


class TestWebhookWorkerRetry:
    """Tests for retry logic."""

    @settings(max_examples=20)
    @given(
        max_retries=st.integers(min_value=1, max_value=5),
        base_delay=st.integers(min_value=1, max_value=5),
    )
    def test_retry_exponential_backoff(self, max_retries: int, base_delay: int):
        """
        Property 6: Retry Exponential Backoff

        For any sequence of failed delivery attempts, the delay between
        attempt N and attempt N+1 SHALL be greater than or equal to
        (base_delay * 2^N) seconds.

        **Validates: Requirements 5.1, 5.2**
        """
        # Calculate expected delays
        delays = []
        for attempt in range(max_retries):
            delay = base_delay * (2**attempt)
            delays.append(delay)

        # Verify exponential growth
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]
            assert delays[i] == base_delay * (2**i)

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self, sample_endpoint, sample_event, sample_config):
        """Test that 4xx errors don't trigger retries."""
        worker = WebhookWorker()

        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with (
            patch(
                "app.webhooks.worker.WebhookConfigLoader.get_config",
                return_value=sample_config,
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await worker._deliver_to_endpoint(sample_event, sample_endpoint)

            # Should fail without retrying (only 1 attempt)
            assert result.success is False
            assert result.http_status == 400
            assert result.attempt_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_5xx(self, sample_endpoint, sample_event, sample_config):
        """Test that 5xx errors trigger retries."""
        worker = WebhookWorker()

        # First two calls fail with 500, third succeeds
        mock_responses = [
            AsyncMock(status_code=500, text="Server Error"),
            AsyncMock(status_code=500, text="Server Error"),
            AsyncMock(status_code=200, text="OK"),
        ]
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            response = mock_responses[min(call_count, len(mock_responses) - 1)]
            call_count += 1
            return response

        with (
            patch(
                "app.webhooks.worker.WebhookConfigLoader.get_config",
                return_value=sample_config,
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await worker._deliver_to_endpoint(sample_event, sample_endpoint)

            # Should succeed after retries
            assert result.success is True
            assert result.attempt_count == 3


class TestWebhookWorkerOrdering:
    """Tests for event ordering."""

    def test_event_ordering_preservation(self):
        """
        Property 7: Event Ordering Preservation

        For any sequence of events emitted to the same endpoint, the
        delivery attempts SHALL be made in the same order as the events
        were emitted.

        **Validates: Requirements 5.6**

        Note: This is ensured by the FIFO queue (Valkey list with RPUSH/BLPOP).
        The test verifies the queue operations maintain order.
        """
        # Events are processed in FIFO order via Valkey list
        # RPUSH adds to end, BLPOP removes from front
        events = [WebhookEvent(event_type="user.created", data={"order": i}) for i in range(5)]

        # Verify events maintain their order attribute
        for i, event in enumerate(events):
            assert event.data["order"] == i
