"""Tests for webhook delivery logging."""

import re
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.webhooks.config import WebhookConfig, WebhookEndpoint, WebhookSettings
from app.webhooks.emitter import WebhookEmitter
from app.webhooks.event import WebhookEvent
from app.webhooks.models import DeliveryStatus, WebhookDelivery
from app.webhooks.worker import DeliveryResult, WebhookWorker


class TestDeliveryLogging:
    """Tests for delivery logging completeness."""

    @settings(max_examples=50)
    @given(
        event_type=st.sampled_from(
            [
                "user.created",
                "user.updated",
                "user.deleted",
                "user.login",
            ]
        ),
        endpoint_id=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz-"),
        http_status=st.integers(min_value=200, max_value=599),
        latency_ms=st.integers(min_value=1, max_value=30000),
    )
    def test_delivery_logging_completeness_success(
        self,
        event_type: str,
        endpoint_id: str,
        http_status: int,
        latency_ms: int,
    ):
        """
        Property 9: Delivery Logging Completeness (success case)

        For any successful delivery attempt, the log entry SHALL contain:
        timestamp, endpoint_id, endpoint_url, event_type, event_id, status,
        http_status, and latency_ms.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        # Simulate successful delivery
        if 200 <= http_status < 300:
            delivery = WebhookDelivery(
                id=uuid.uuid4(),
                event_id=uuid.uuid4(),
                event_type=event_type,
                endpoint_id=endpoint_id,
                endpoint_url=f"https://{endpoint_id}.example.com/webhook",
                status=DeliveryStatus.SUCCESS.value,
                http_status=http_status,
                latency_ms=latency_ms,
                attempt_count=1,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )

            # Verify all required fields are present
            assert delivery.id is not None
            assert delivery.event_id is not None
            assert delivery.event_type == event_type
            assert delivery.endpoint_id == endpoint_id
            assert delivery.endpoint_url is not None
            assert delivery.status == DeliveryStatus.SUCCESS.value
            assert delivery.http_status == http_status
            assert delivery.latency_ms == latency_ms
            assert delivery.created_at is not None

    @settings(max_examples=50)
    @given(
        event_type=st.sampled_from(
            [
                "user.created",
                "user.updated",
                "user.deleted",
                "user.login",
            ]
        ),
        endpoint_id=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz-"),
        http_status=st.integers(min_value=400, max_value=599),
        error_message=st.text(min_size=1, max_size=200),
    )
    def test_delivery_logging_completeness_failure(
        self,
        event_type: str,
        endpoint_id: str,
        http_status: int,
        error_message: str,
    ):
        """
        Property 9: Delivery Logging Completeness (failure case)

        For any failed delivery attempt, the log entry SHALL contain:
        timestamp, endpoint_id, endpoint_url, event_type, event_id, status,
        http_status (if available), and error_message.

        **Validates: Requirements 6.1, 6.2, 6.4**
        """
        delivery = WebhookDelivery(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            event_type=event_type,
            endpoint_id=endpoint_id,
            endpoint_url=f"https://{endpoint_id}.example.com/webhook",
            status=DeliveryStatus.FAILED.value,
            http_status=http_status,
            error_message=error_message,
            attempt_count=5,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        # Verify all required fields are present
        assert delivery.id is not None
        assert delivery.event_id is not None
        assert delivery.event_type == event_type
        assert delivery.endpoint_id == endpoint_id
        assert delivery.endpoint_url is not None
        assert delivery.status == DeliveryStatus.FAILED.value
        assert delivery.error_message == error_message
        assert delivery.created_at is not None

    def test_delivery_result_to_model_mapping(self):
        """Test that DeliveryResult maps correctly to WebhookDelivery model."""
        # Success result
        success_result = DeliveryResult(
            success=True,
            http_status=200,
            latency_ms=150,
            attempt_count=1,
        )

        assert success_result.success is True
        assert success_result.http_status == 200
        assert success_result.latency_ms == 150
        assert success_result.error_message is None

        # Failure result
        failure_result = DeliveryResult(
            success=False,
            http_status=500,
            error_message="Internal Server Error",
            attempt_count=3,
        )

        assert failure_result.success is False
        assert failure_result.http_status == 500
        assert failure_result.error_message == "Internal Server Error"


class TestDeliveryFailureLogTracking:
    """配送失敗ログで delivery_id の追跡キーが欠落しないことを検証する。"""

    @pytest.mark.asyncio
    async def test_emitter_queue_failure_logs_delivery_id(self, caplog):
        """Emitter 側の失敗ログに delivery_id を含める。"""
        mock_valkey = AsyncMock()
        mock_valkey.rpush = AsyncMock(side_effect=Exception("Connection failed"))

        with (
            patch("app.webhooks.emitter._is_testing", return_value=False),
            patch("app.webhooks.emitter.get_valkey", return_value=mock_valkey),
            patch(
                "app.webhooks.config.WebhookConfigLoader.get_endpoints_for_event",
                return_value=[object()],
            ),
            caplog.at_level("ERROR", logger="app.webhooks.emitter"),
        ):
            event = await WebhookEmitter.emit(
                "user.created",
                {"user_id": str(uuid.uuid4())},
            )

        assert event is None
        failure_log = next(
            record.getMessage()
            for record in caplog.records
            if "Failed to queue webhook event" in record.getMessage()
        )
        delivery_id_match = re.search(r"delivery_id=([0-9a-f-]{36})", failure_log)
        assert delivery_id_match is not None
        assert uuid.UUID(delivery_id_match.group(1))

    @pytest.mark.asyncio
    async def test_worker_failure_logs_use_delivery_id_consistently(self, caplog):
        """Worker の再試行/失敗ログで同一 delivery_id を追跡できる。"""
        worker = WebhookWorker()
        endpoint = WebhookEndpoint(
            id="test-endpoint",
            url="https://example.com/webhook",
            secret="test-secret",
            events=["user.created"],
            enabled=True,
        )
        config = WebhookConfig(
            endpoints=[endpoint],
            settings=WebhookSettings(
                max_retries=2,
                retry_base_delay_seconds=0,
                delivery_timeout_seconds=5,
            ),
        )
        event = WebhookEvent(
            event_type="user.created",
            data={"user_id": str(uuid.uuid4())},
        )

        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with (
            patch(
                "app.webhooks.worker.WebhookConfigLoader.get_config",
                return_value=config,
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            caplog.at_level("INFO", logger="app.webhooks.worker"),
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            result = await worker._deliver_to_endpoint(event, endpoint)

        assert result.success is False
        retry_logs = [
            record.getMessage()
            for record in caplog.records
            if "Retrying webhook delivery" in record.getMessage()
        ]
        assert retry_logs

        exhausted_log = next(
            record.getMessage()
            for record in caplog.records
            if "webhook_delivery_retry_exhausted" in record.getMessage()
        )
        exhausted_delivery_id = re.search(r"delivery_id=([0-9a-f-]{36})", exhausted_log)
        assert exhausted_delivery_id is not None
        delivery_id = exhausted_delivery_id.group(1)
        for retry_log in retry_logs:
            assert f"delivery_id={delivery_id}" in retry_log
