"""Webhook delivery worker."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

from app.valkey import get_valkey
from app.webhooks.config import WebhookConfigLoader, WebhookEndpoint
from app.webhooks.emitter import WEBHOOK_QUEUE_KEY
from app.webhooks.event import WebhookEvent
from app.webhooks.models import DeliveryStatus
from app.webhooks.signer import WebhookSigner

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
MAX_RETRY_EXHAUSTED_LOG_KEY = "webhook_delivery_retry_exhausted"


@dataclass
class DeliveryResult:
    """Result of a webhook delivery attempt."""

    success: bool
    http_status: int | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    attempt_count: int = 1
    signature_algorithm: str | None = None


class WebhookWorker:
    """Processes webhook events from the queue."""

    def __init__(self, db_session_factory=None):
        """
        Initialize the worker.

        Args:
            db_session_factory: Async session factory for database operations
        """
        self._running = False
        self._task: asyncio.Task | None = None
        self._db_session_factory = db_session_factory

    async def start(self) -> None:
        """Start processing events."""
        if self._running:
            logger.warning("WebhookWorker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("WebhookWorker started")

    async def stop(self) -> None:
        """Stop processing events."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("WebhookWorker stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                await self._process_next_event()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in webhook worker loop: %s", e)
                await asyncio.sleep(1)  # Back off on error

    async def _process_next_event(self) -> None:
        """Process the next event from the queue."""
        client = await get_valkey()

        # Blocking pop with timeout (1 second)
        result = await client.blpop(WEBHOOK_QUEUE_KEY, timeout=1)
        if not result:
            return

        _, event_json = result

        try:
            payload = json.loads(event_json)
            event = WebhookEvent.from_payload(payload)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to parse webhook event: %s", e)
            return

        # Get endpoints for this event
        endpoints = WebhookConfigLoader.get_endpoints_for_event(event.event_type)
        if not endpoints:
            logger.debug("No endpoints for event %s", event.event_id)
            return

        # Deliver to all endpoints
        for endpoint in endpoints:
            await self._deliver_to_endpoint(event, endpoint)

    async def _deliver_to_endpoint(
        self,
        event: WebhookEvent,
        endpoint: WebhookEndpoint,
    ) -> DeliveryResult:
        """Deliver event to a single endpoint with retries."""
        config = WebhookConfigLoader.get_config()
        max_retries = config.settings.max_retries
        base_delay = config.settings.retry_base_delay_seconds
        max_delay = config.settings.retry_max_delay_seconds
        jitter_ratio = config.settings.retry_jitter_ratio
        timeout = config.settings.delivery_timeout_seconds
        delivery_id = uuid.uuid4()

        result = DeliveryResult(success=False)

        for attempt in range(max_retries + 1):
            result.attempt_count = attempt + 1

            if attempt > 0:
                raw_delay = base_delay * (2 ** (attempt - 1))
                delay = self._calculate_retry_delay(
                    attempt=attempt,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    jitter_ratio=jitter_ratio,
                )
                logger.info(
                    (
                        "Retrying webhook delivery to %s (attempt %d/%d) after %ds "
                        "(delivery_id=%s event_id=%s raw_delay=%ds, max_delay=%ds, "
                        "jitter_ratio=%.3f)"
                    ),
                    endpoint.id,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                    delivery_id,
                    event.event_id,
                    raw_delay,
                    max_delay,
                    jitter_ratio,
                )
                await asyncio.sleep(delay)

            delivery_result = await self._attempt_delivery(event, endpoint, timeout)
            result = delivery_result
            result.attempt_count = attempt + 1

            if result.success:
                logger.info(
                    "Webhook delivered to %s (event: %s, latency: %dms)",
                    endpoint.id,
                    event.event_id,
                    result.latency_ms or 0,
                )
                break

            # Don't retry on 4xx errors (client errors)
            if result.http_status and 400 <= result.http_status < 500:
                logger.warning(
                    (
                        "Webhook delivery to %s failed with client error %d, not retrying "
                        "(delivery_id=%s event_id=%s signature_algo=%s)"
                    ),
                    endpoint.id,
                    result.http_status,
                    delivery_id,
                    event.event_id,
                    result.signature_algorithm,
                )
                break

        if not result.success:
            failure_reason = result.error_message or (
                f"http_status_{result.http_status}"
                if result.http_status is not None
                else "unknown_error"
            )
            logger.error(
                (
                    "%s delivery_id=%s endpoint_id=%s event_id=%s attempts=%d "
                    "max_attempts=%d failure_reason=%s signature_algo=%s "
                    "http_status=%s error=%s"
                ),
                MAX_RETRY_EXHAUSTED_LOG_KEY,
                delivery_id,
                endpoint.id,
                event.event_id,
                result.attempt_count,
                max_retries + 1,
                failure_reason,
                result.signature_algorithm,
                result.http_status,
                result.error_message,
            )

        # Log delivery to database
        await self._log_delivery(delivery_id, event, endpoint, result)

        return result

    @staticmethod
    def _calculate_retry_delay(
        attempt: int,
        base_delay: int,
        max_delay: int,
        jitter_ratio: float,
    ) -> int:
        """Calculate retry delay with capped exponential backoff and bounded jitter."""
        raw_delay = base_delay * (2 ** (attempt - 1))
        capped_delay = min(raw_delay, max_delay)
        if jitter_ratio <= 0 or capped_delay <= 0:
            return capped_delay

        jitter_span = int(capped_delay * jitter_ratio)
        if jitter_span <= 0:
            return capped_delay

        jitter = random.randint(-jitter_span, jitter_span)
        return max(0, min(max_delay, capped_delay + jitter))

    async def _attempt_delivery(
        self,
        event: WebhookEvent,
        endpoint: WebhookEndpoint,
        timeout: int,
    ) -> DeliveryResult:
        """Attempt a single delivery."""
        # Build payload with webhook_id
        payload_dict = event.to_payload()
        payload_dict["webhook_id"] = endpoint.id
        payload_json = json.dumps(payload_dict)

        # Generate headers with signature
        headers = WebhookSigner.get_headers(
            payload_json,
            endpoint.secret,
            event.event_type,
            endpoint.id,
        )
        signature_algorithm = WebhookSigner.SIGNATURE_PREFIX.removesuffix("=")

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    endpoint.url,
                    content=payload_json,
                    headers=headers,
                )

            latency_ms = int((time.time() - start_time) * 1000)

            if 200 <= response.status_code < 300:
                return DeliveryResult(
                    success=True,
                    http_status=response.status_code,
                    latency_ms=latency_ms,
                    signature_algorithm=signature_algorithm,
                )
            else:
                return DeliveryResult(
                    success=False,
                    http_status=response.status_code,
                    error_message=response.text[:500] if response.text else None,
                    latency_ms=latency_ms,
                    signature_algorithm=signature_algorithm,
                )

        except httpx.TimeoutException:
            return DeliveryResult(
                success=False,
                error_message="Request timeout",
                signature_algorithm=signature_algorithm,
            )
        except httpx.RequestError as e:
            return DeliveryResult(
                success=False,
                error_message=str(e)[:500],
                signature_algorithm=signature_algorithm,
            )

    async def _log_delivery(
        self,
        delivery_id: uuid.UUID,
        event: WebhookEvent,
        endpoint: WebhookEndpoint,
        result: DeliveryResult,
    ) -> None:
        """Log delivery result to database."""
        if not self._db_session_factory:
            return

        try:
            from app.webhooks.models import WebhookDelivery

            async with self._db_session_factory() as session:
                delivery = WebhookDelivery(
                    id=delivery_id,
                    event_id=event.event_id,
                    event_type=event.event_type,
                    endpoint_id=endpoint.id,
                    endpoint_url=endpoint.url,
                    status=(
                        DeliveryStatus.SUCCESS.value
                        if result.success
                        else DeliveryStatus.FAILED.value
                    ),
                    http_status=result.http_status,
                    error_message=result.error_message,
                    attempt_count=result.attempt_count,
                    latency_ms=result.latency_ms,
                    completed_at=datetime.now(UTC),
                )
                session.add(delivery)
                await session.commit()
        except Exception as e:
            logger.error("Failed to log webhook delivery: %s", e)
