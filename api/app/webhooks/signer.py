"""Webhook payload signer using HMAC-SHA256."""

import hashlib
import hmac
import time


class WebhookSigner:
    """Signs webhook payloads for verification."""

    SIGNATURE_PREFIX = "sha256="

    @staticmethod
    def sign(payload: str, secret: str, timestamp: int | None = None) -> tuple[str, int]:
        """
        Generate HMAC-SHA256 signature for a webhook payload.

        Args:
            payload: The JSON payload string to sign
            secret: The shared secret key
            timestamp: Unix timestamp (defaults to current time)

        Returns:
            Tuple of (signature, timestamp)
        """
        if timestamp is None:
            timestamp = int(time.time())

        # Signature is computed over: timestamp + "." + payload
        message = f"{timestamp}.{payload}"
        signature = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return f"{WebhookSigner.SIGNATURE_PREFIX}{signature}", timestamp

    @staticmethod
    def verify(
        payload: str,
        secret: str,
        timestamp: int,
        signature: str,
    ) -> bool:
        """
        Verify a webhook signature.

        Args:
            payload: The JSON payload string
            secret: The shared secret key
            timestamp: The timestamp from X-Webhook-Timestamp header
            signature: The signature from X-Webhook-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature, _ = WebhookSigner.sign(payload, secret, timestamp)
        return hmac.compare_digest(expected_signature, signature)

    @staticmethod
    def get_headers(payload: str, secret: str, event_type: str, webhook_id: str) -> dict[str, str]:
        """
        Generate all webhook HTTP headers including signature.

        Args:
            payload: The JSON payload string
            secret: The shared secret key
            event_type: The event type (e.g., "user.created")
            webhook_id: The webhook endpoint ID

        Returns:
            Dictionary of HTTP headers
        """
        signature, timestamp = WebhookSigner.sign(payload, secret)

        return {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp),
            "X-Webhook-Event": event_type,
            "X-Webhook-ID": webhook_id,
        }
