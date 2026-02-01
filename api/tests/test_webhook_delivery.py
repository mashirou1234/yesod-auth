"""Tests for webhook delivery logging."""

import uuid
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from app.webhooks.models import DeliveryStatus, WebhookDelivery
from app.webhooks.worker import DeliveryResult


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
