"""Webhook SQLAlchemy models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class WebhookDelivery(Base):
    """Webhook delivery log entry."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    endpoint_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    endpoint_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Delivery status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DeliveryStatus.PENDING.value,
    )
    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timing
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
