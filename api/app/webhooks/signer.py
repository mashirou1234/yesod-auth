"""Webhook payload signer using HMAC-SHA256."""

import hashlib
import hmac
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureVerificationResult:
    """Detailed result for signature verification."""

    ok: bool
    error_code: str | None = None
    message: str | None = None


class WebhookSignatureError(ValueError):
    """Base class for webhook signature validation errors."""

    error_code = "invalid_signature"


class MissingWebhookSignatureError(WebhookSignatureError):
    """Raised when signature header is missing."""

    error_code = "missing_signature_header"

    def __init__(self):
        super().__init__("Missing required X-Webhook-Signature header")


class InvalidWebhookSignatureError(WebhookSignatureError):
    """Raised when signature verification fails."""

    error_code = "invalid_signature"

    def __init__(
        self,
        *,
        verify_error_code: str | None = None,
        signature_algorithm: str | None = None,
    ):
        details: list[str] = []
        if verify_error_code:
            details.append(f"error_code={verify_error_code}")
        if signature_algorithm:
            details.append(f"signature_algorithm={signature_algorithm}")
        detail_text = " ".join(details) if details else "error_code=invalid_signature"
        super().__init__(f"Webhook signature verification failed {detail_text}")


class WebhookSigner:
    """Signs webhook payloads for verification."""

    SIGNATURE_PREFIX = "sha256="
    SIGNATURE_ALGORITHM = SIGNATURE_PREFIX.removesuffix("=")
    DEFAULT_MAX_TIMESTAMP_SKEW_SECONDS = 300
    ERROR_TIMESTAMP_SKEW = "timestamp_skew"
    ERROR_INVALID_SIGNATURE_FORMAT = "invalid_signature_format"
    ERROR_UNSUPPORTED_SIGNATURE_ALGORITHM = "unsupported_signature_algorithm"
    ERROR_HMAC_MISMATCH = "hmac_mismatch"

    @staticmethod
    def signature_algorithm(signature: str) -> str | None:
        """Extract signature algorithm from '<algorithm>=<digest>' format."""
        if "=" not in signature:
            return None
        algorithm, _ = signature.split("=", 1)
        return algorithm.strip() or None

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
        current_timestamp: int | None = None,
        max_timestamp_skew_seconds: int = DEFAULT_MAX_TIMESTAMP_SKEW_SECONDS,
    ) -> bool:
        """
        Verify a webhook signature.

        Args:
            payload: The JSON payload string
            secret: The shared secret key
            timestamp: The timestamp from X-Webhook-Timestamp header
            signature: The signature from X-Webhook-Signature header
            current_timestamp: The current Unix timestamp used for skew checks
            max_timestamp_skew_seconds: Maximum allowed skew in seconds

        Returns:
            True if signature is valid, False otherwise
        """
        result = WebhookSigner.verify_with_error(
            payload=payload,
            secret=secret,
            timestamp=timestamp,
            signature=signature,
            current_timestamp=current_timestamp,
            max_timestamp_skew_seconds=max_timestamp_skew_seconds,
        )
        return result.ok

    @staticmethod
    def verify_with_error(
        payload: str,
        secret: str,
        timestamp: int,
        signature: str,
        current_timestamp: int | None = None,
        max_timestamp_skew_seconds: int = DEFAULT_MAX_TIMESTAMP_SKEW_SECONDS,
    ) -> SignatureVerificationResult:
        """Verify signature and return a normalized error classification."""
        if current_timestamp is None:
            current_timestamp = int(time.time())

        if abs(current_timestamp - timestamp) > max_timestamp_skew_seconds:
            return SignatureVerificationResult(
                ok=False,
                error_code=WebhookSigner.ERROR_TIMESTAMP_SKEW,
                message="Timestamp outside allowed skew window",
            )

        if "=" not in signature:
            return SignatureVerificationResult(
                ok=False,
                error_code=WebhookSigner.ERROR_INVALID_SIGNATURE_FORMAT,
                message="Signature must be in '<algorithm>=<digest>' format",
            )

        algorithm, _ = signature.split("=", 1)
        if algorithm != WebhookSigner.SIGNATURE_ALGORITHM:
            return SignatureVerificationResult(
                ok=False,
                error_code=WebhookSigner.ERROR_UNSUPPORTED_SIGNATURE_ALGORITHM,
                message=f"Unsupported signature algorithm: {algorithm}",
            )

        expected_signature, _ = WebhookSigner.sign(payload, secret, timestamp)
        if not hmac.compare_digest(expected_signature, signature):
            return SignatureVerificationResult(
                ok=False,
                error_code=WebhookSigner.ERROR_HMAC_MISMATCH,
                message="Signature does not match payload",
            )

        return SignatureVerificationResult(ok=True)

    @staticmethod
    def verify_or_raise(
        payload: str,
        secret: str,
        timestamp: int,
        signature: str | None,
    ) -> None:
        """
        Verify signature and raise a classified error when verification fails.

        Raises:
            MissingWebhookSignatureError: Signature header is missing/empty
            InvalidWebhookSignatureError: Signature value does not match payload
        """
        if signature is None or not signature.strip():
            raise MissingWebhookSignatureError()
        result = WebhookSigner.verify_with_error(
            payload=payload,
            secret=secret,
            timestamp=timestamp,
            signature=signature,
        )
        if not result.ok:
            raise InvalidWebhookSignatureError(
                verify_error_code=result.error_code,
                signature_algorithm=WebhookSigner.signature_algorithm(signature),
            )

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
