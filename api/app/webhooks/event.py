"""Webhook event data model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class WebhookEvent:
    """Represents a webhook event to be delivered."""

    event_type: str
    data: dict[str, Any]
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_payload(self) -> dict[str, Any]:
        """Convert to JSON-serializable payload."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> WebhookEvent:
        """Create WebhookEvent from JSON payload."""
        return cls(
            event_id=uuid.UUID(payload["event_id"]),
            event_type=payload["event_type"],
            timestamp=datetime.fromisoformat(payload["timestamp"]),
            data=payload["data"],
        )
