"""Webhook Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WebhookEndpointResponse(BaseModel):
    """Webhook endpoint configuration response (secret masked)."""

    id: str = Field(..., description="Unique endpoint identifier")
    url: str = Field(..., description="Webhook URL (HTTPS)")
    events: list[str] = Field(..., description="Subscribed event types")
    enabled: bool = Field(..., description="Whether endpoint is active")
    description: str = Field("", description="Endpoint description")


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery log entry response."""

    id: UUID = Field(..., description="Delivery record ID")
    event_id: UUID = Field(..., description="Event ID")
    event_type: str = Field(..., description="Event type (e.g., user.created)")
    endpoint_id: str = Field(..., description="Target endpoint ID")
    endpoint_url: str = Field(..., description="Target URL at delivery time")
    status: str = Field(..., description="Delivery status: pending, success, failed")
    http_status: int | None = Field(None, description="HTTP response status code")
    error_message: str | None = Field(None, description="Error message if failed")
    attempt_count: int = Field(..., description="Number of delivery attempts")
    latency_ms: int | None = Field(None, description="Delivery latency in milliseconds")
    created_at: datetime = Field(..., description="When delivery was created")
    completed_at: datetime | None = Field(None, description="When delivery completed")


class WebhookReloadResponse(BaseModel):
    """Response for webhook configuration reload."""

    success: bool = Field(..., description="Whether reload succeeded")
    message: str = Field(..., description="Status message")
    endpoint_count: int = Field(..., description="Number of loaded endpoints")
