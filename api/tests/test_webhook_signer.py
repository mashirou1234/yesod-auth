"""Property-based tests for WebhookSigner."""

import json
import time
import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.webhooks.signer import (
    InvalidWebhookSignatureError,
    MissingWebhookSignatureError,
    WebhookSigner,
)

# Strategies for generating test data
payloads = st.builds(
    lambda event_id, event_type, user_id: json.dumps(
        {
            "event_id": str(event_id),
            "event_type": event_type,
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {"user_id": str(user_id)},
        }
    ),
    event_id=st.uuids(),
    event_type=st.sampled_from(
        [
            "user.created",
            "user.updated",
            "user.deleted",
            "user.login",
        ]
    ),
    user_id=st.uuids(),
)

secrets = st.text(min_size=8, max_size=64, alphabet="abcdefghijklmnopqrstuvwxyz0123456789")

timestamps = st.integers(min_value=1000000000, max_value=2000000000)


class TestWebhookSigner:
    """Tests for webhook signature generation and verification."""

    @settings(max_examples=100)
    @given(payload=payloads, secret=secrets, timestamp=timestamps)
    def test_signature_computation_correctness(
        self,
        payload: str,
        secret: str,
        timestamp: int,
    ):
        """
        Property 4: Signature Computation Correctness

        For any webhook delivery, the X-Webhook-Signature header SHALL equal
        the HMAC-SHA256 of (timestamp + payload_body) using the endpoint's
        secret key, and verifying with the same inputs SHALL return true.

        **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
        """
        # Generate signature
        signature, returned_timestamp = WebhookSigner.sign(payload, secret, timestamp)

        # Timestamp should be preserved
        assert returned_timestamp == timestamp

        # Signature should start with sha256= prefix
        assert signature.startswith("sha256=")

        # Verification with same inputs should succeed
        assert WebhookSigner.verify(payload, secret, timestamp, signature, current_timestamp=timestamp) is True

    @settings(max_examples=50)
    @given(payload=payloads, secret=secrets, timestamp=timestamps)
    def test_signature_changes_with_different_payload(
        self,
        payload: str,
        secret: str,
        timestamp: int,
    ):
        """
        Signatures should be different for different payloads.
        """
        signature1, _ = WebhookSigner.sign(payload, secret, timestamp)

        # Modify payload
        modified_payload = payload + " "
        signature2, _ = WebhookSigner.sign(modified_payload, secret, timestamp)

        assert signature1 != signature2

    @settings(max_examples=50)
    @given(payload=payloads, secret=secrets, timestamp=timestamps)
    def test_signature_changes_with_different_secret(
        self,
        payload: str,
        secret: str,
        timestamp: int,
    ):
        """
        Signatures should be different for different secrets.
        """
        signature1, _ = WebhookSigner.sign(payload, secret, timestamp)

        # Use different secret
        different_secret = secret + "x"
        signature2, _ = WebhookSigner.sign(payload, different_secret, timestamp)

        assert signature1 != signature2

    @settings(max_examples=50)
    @given(payload=payloads, secret=secrets, timestamp=timestamps)
    def test_signature_changes_with_different_timestamp(
        self,
        payload: str,
        secret: str,
        timestamp: int,
    ):
        """
        Signatures should be different for different timestamps.
        """
        signature1, _ = WebhookSigner.sign(payload, secret, timestamp)

        # Use different timestamp
        different_timestamp = timestamp + 1
        signature2, _ = WebhookSigner.sign(payload, secret, different_timestamp)

        assert signature1 != signature2

    @settings(max_examples=50)
    @given(payload=payloads, secret=secrets, timestamp=timestamps)
    def test_verification_fails_with_wrong_secret(
        self,
        payload: str,
        secret: str,
        timestamp: int,
    ):
        """
        Verification should fail when using wrong secret.
        """
        signature, _ = WebhookSigner.sign(payload, secret, timestamp)

        # Verify with wrong secret
        wrong_secret = secret + "wrong"
        assert WebhookSigner.verify(
            payload,
            wrong_secret,
            timestamp,
            signature,
            current_timestamp=timestamp,
        ) is False

    @pytest.mark.parametrize("timestamp_offset", (-300, 300))
    def test_verification_accepts_timestamp_at_skew_boundary(self, timestamp_offset: int):
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})
        secret = "test-secret-key"
        current_timestamp = 1_700_000_000
        timestamp = current_timestamp + timestamp_offset
        signature, _ = WebhookSigner.sign(payload, secret, timestamp)

        assert (
            WebhookSigner.verify(
                payload,
                secret,
                timestamp,
                signature,
                current_timestamp=current_timestamp,
            )
            is True
        )

    @pytest.mark.parametrize("timestamp_offset", (-301, 301))
    def test_verification_rejects_timestamp_outside_skew_boundary(self, timestamp_offset: int):
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})
        secret = "test-secret-key"
        current_timestamp = 1_700_000_000
        timestamp = current_timestamp + timestamp_offset
        signature, _ = WebhookSigner.sign(payload, secret, timestamp)

        assert (
            WebhookSigner.verify(
                payload,
                secret,
                timestamp,
                signature,
                current_timestamp=current_timestamp,
            )
            is False
        )

    def test_verify_with_error_classifies_unsupported_algorithm(self):
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})
        secret = "test-secret-key"
        timestamp = 1_700_000_000
        signature = "sha1=deadbeef"

        result = WebhookSigner.verify_with_error(
            payload=payload,
            secret=secret,
            timestamp=timestamp,
            signature=signature,
            current_timestamp=timestamp,
        )

        assert result.ok is False
        assert result.error_code == "unsupported_signature_algorithm"
        assert result.message == "Unsupported signature algorithm: sha1"

    def test_verify_with_error_keeps_success_path_compatible(self):
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})
        secret = "test-secret-key"
        timestamp = 1_700_000_000
        signature, _ = WebhookSigner.sign(payload, secret, timestamp)

        result = WebhookSigner.verify_with_error(
            payload=payload,
            secret=secret,
            timestamp=timestamp,
            signature=signature,
            current_timestamp=timestamp,
        )

        assert result.ok is True
        assert result.error_code is None
        assert result.message is None

    def test_get_headers_includes_all_required_headers(self):
        """
        Test that get_headers returns all required HTTP headers.
        """
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})
        secret = "test-secret-key"
        event_type = "user.created"
        webhook_id = "test-endpoint"

        headers = WebhookSigner.get_headers(payload, secret, event_type, webhook_id)

        assert headers["Content-Type"] == "application/json"
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")
        assert "X-Webhook-Timestamp" in headers
        assert headers["X-Webhook-Timestamp"].isdigit()
        assert headers["X-Webhook-Event"] == event_type
        assert headers["X-Webhook-ID"] == webhook_id

    def test_verify_or_raise_reports_missing_signature_header(self):
        """Missing signature header should raise a dedicated error."""
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})

        with pytest.raises(MissingWebhookSignatureError) as exc_info:
            WebhookSigner.verify_or_raise(payload, "test-secret-key", 1705297800, None)

        assert exc_info.value.error_code == "missing_signature_header"

    def test_verify_or_raise_reports_invalid_signature_separately(self):
        """Invalid signature should stay distinct from missing-header error."""
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})
        timestamp = int(time.time())

        with pytest.raises(InvalidWebhookSignatureError) as exc_info:
            WebhookSigner.verify_or_raise(payload, "test-secret-key", timestamp, "sha256=deadbeef")

        assert exc_info.value.error_code == "invalid_signature"
        assert "error_code=hmac_mismatch" in str(exc_info.value)
        assert "signature_algorithm=sha256" in str(exc_info.value)

    def test_verify_or_raise_reports_algorithm_in_error_message(self):
        """Unsupported algorithm failures should include algorithm label for triage."""
        payload = json.dumps({"event_id": str(uuid.uuid4()), "data": {}})
        timestamp = int(time.time())

        with pytest.raises(InvalidWebhookSignatureError) as exc_info:
            WebhookSigner.verify_or_raise(payload, "test-secret-key", timestamp, "sha1=deadbeef")

        assert exc_info.value.error_code == "invalid_signature"
        assert "error_code=unsupported_signature_algorithm" in str(exc_info.value)
        assert "signature_algorithm=sha1" in str(exc_info.value)
