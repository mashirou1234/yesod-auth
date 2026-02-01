"""Property-based tests for WebhookSigner."""

import json
import uuid

from hypothesis import given, settings
from hypothesis import strategies as st

from app.webhooks.signer import WebhookSigner

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
        assert WebhookSigner.verify(payload, secret, timestamp, signature) is True

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
        assert WebhookSigner.verify(payload, wrong_secret, timestamp, signature) is False

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
