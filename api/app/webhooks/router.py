"""Webhook admin API router."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.webhooks.config import WebhookConfigLoader
from app.webhooks.models import WebhookDelivery
from app.webhooks.schemas import (
    WebhookDeliveryResponse,
    WebhookEndpointResponse,
    WebhookReloadResponse,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks-admin"])


@router.post("/reload", response_model=WebhookReloadResponse)
async def reload_webhooks():
    """Reload webhook configuration from file.

    Reloads config/webhooks.yaml and validates all endpoints.
    If validation fails, the existing configuration is kept.
    """
    try:
        config = WebhookConfigLoader.reload()
        return WebhookReloadResponse(
            success=True,
            message=f"Loaded {len(config.endpoints)} endpoint(s)",
            endpoint_count=len(config.endpoints),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload configuration: {e}",
        ) from e


@router.get("/endpoints", response_model=list[WebhookEndpointResponse])
async def list_endpoints():
    """List all configured webhook endpoints.

    Returns endpoint configurations (secrets are masked).
    """
    config = WebhookConfigLoader.get_config()
    return [
        WebhookEndpointResponse(
            id=ep.id,
            url=ep.url,
            events=ep.events,
            enabled=ep.enabled,
            description=ep.description,
        )
        for ep in config.endpoints
    ]


@router.get("/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_deliveries(
    event_type: str | None = Query(None, description="Filter by event type"),
    endpoint_id: str | None = Query(None, description="Filter by endpoint ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
):
    """List recent webhook deliveries.

    Returns delivery history with status, latency, and error details.
    """
    query = select(WebhookDelivery).order_by(desc(WebhookDelivery.created_at))

    if event_type:
        query = query.where(WebhookDelivery.event_type == event_type)
    if endpoint_id:
        query = query.where(WebhookDelivery.endpoint_id == endpoint_id)

    query = query.limit(limit)

    result = await db.execute(query)
    deliveries = result.scalars().all()

    return [
        WebhookDeliveryResponse(
            id=d.id,
            event_id=d.event_id,
            event_type=d.event_type,
            endpoint_id=d.endpoint_id,
            endpoint_url=d.endpoint_url,
            status=d.status,
            http_status=d.http_status,
            error_message=d.error_message,
            attempt_count=d.attempt_count,
            latency_ms=d.latency_ms,
            created_at=d.created_at,
            completed_at=d.completed_at,
        )
        for d in deliveries
    ]
