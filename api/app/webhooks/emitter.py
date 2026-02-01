"""Webhook event emitter."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from app.valkey import get_valkey
from app.webhooks.config import WebhookConfigLoader
from app.webhooks.event import WebhookEvent

logger = logging.getLogger(__name__)

# Queue key for webhook events
WEBHOOK_QUEUE_KEY = "webhook:events"


def _is_testing() -> bool:
    """Check if running in test environment."""
    return os.environ.get("TESTING") == "1"


class WebhookEmitter:
    """Emits webhook events to the queue for async delivery."""

    @staticmethod
    async def emit(event_type: str, data: dict[str, Any]) -> WebhookEvent | None:
        """
        Queue a webhook event for delivery.

        Args:
            event_type: The event type (e.g., "user.created")
            data: The event data payload

        Returns:
            The created WebhookEvent, or None if no endpoints subscribe
        """
        if _is_testing():
            logger.debug("Skipping webhook emission in test environment")
            return None

        # Check if any endpoints subscribe to this event
        endpoints = WebhookConfigLoader.get_endpoints_for_event(event_type)
        if not endpoints:
            logger.debug("No endpoints subscribe to event: %s", event_type)
            return None

        # Create event
        event = WebhookEvent(event_type=event_type, data=data)

        # Queue for async delivery
        try:
            client = await get_valkey()
            await client.rpush(
                WEBHOOK_QUEUE_KEY,
                json.dumps(event.to_payload()),
            )
            logger.info(
                "Queued webhook event %s (type: %s) for %d endpoint(s)",
                event.event_id,
                event_type,
                len(endpoints),
            )
        except Exception as e:
            logger.error("Failed to queue webhook event: %s", e)
            return None

        return event

    @staticmethod
    async def emit_user_event(
        event_type: str,
        user_id: uuid.UUID,
        extra_data: dict[str, Any] | None = None,
    ) -> WebhookEvent | None:
        """
        Convenience method for user-related events.

        Args:
            event_type: The event type (e.g., "user.created")
            user_id: The user's UUID
            extra_data: Additional data to include in the payload

        Returns:
            The created WebhookEvent, or None if skipped
        """
        data: dict[str, Any] = {"user_id": str(user_id)}
        if extra_data:
            data.update(extra_data)

        return await WebhookEmitter.emit(event_type, data)
