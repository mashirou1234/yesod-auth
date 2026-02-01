"""Webhook delivery worker."""

from __future__ import annotations

import asyncio
import json
import logging
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


@dataclass
class DeliveryResult:
    """Result of a webhook delivery attempt."""

    success: bool
    http_status: int | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    attempt_count: int = 1


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
        timeout = config.settings.delivery_timeout_seconds

        result = DeliveryResult(success=False)

        for attempt in range(max_retries + 1):
            result.attempt_count = attempt + 1

            if attempt > 0:
                # Exponential backoff
                delay = base_delay * (2 ** (attempt - 1))
                logger.info(
                    "Retrying webhook delivery to %s (attempt %d/%d) after %ds",
                    endpoint.id,
                    attempt + 1,
                    max_retries + 1,
                    delay,
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
                    "Webhook delivery to %s failed with client error %d, not retrying",
                    endpoint.id,
                    result.http_status,
                )
                break

        if not result.success:
            logger.error(
                "Webhook delivery to %s failed after %d attempts: %s",
                endpoint.id,
                result.attempt_count,
                result.error_message,
            )

        # Log delivery to database
        await self._log_delivery(event, endpoint, result)

        return result

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
                )
            else:
                return DeliveryResult(
                    success=False,
                    http_status=response.status_code,
                    error_message=response.text[:500] if response.text else None,
                    latency_ms=latency_ms,
                )

        except httpx.TimeoutException:
            return DeliveryResult(
                success=False,
                error_message="Request timeout",
            )
        except httpx.RequestError as e:
            return DeliveryResult(
                success=False,
                error_message=str(e)[:500],
            )

    async def _log_delivery(
        self,
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
                    id=uuid.uuid4(),
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
