"""Health check tests."""

import pytest
from httpx import AsyncClient

from app.metrics import (
    record_oauth_failure_metric,
    render_oauth_failure_metrics_lines,
    reset_oauth_failure_metrics,
)


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "YESOD Auth"
    assert "version" in data


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_docs_available(client: AsyncClient):
    """Test OpenAPI docs are available."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_schema(client: AsyncClient):
    """Test OpenAPI schema is available."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "YESOD Auth"
    assert "paths" in schema


@pytest.mark.asyncio
async def test_metrics_include_oauth_failure_classification_counter(client: AsyncClient):
    """OAuth failure counter should be exposed with provider/reason labels."""
    reset_oauth_failure_metrics()
    record_oauth_failure_metric("github", "invalid_state")
    record_oauth_failure_metric("github", "invalid_state")
    assert 'yesod_oauth_failures_total{provider="github",reason="invalid_state"} 2' in (
        render_oauth_failure_metrics_lines()
    )


def test_metrics_normalize_known_oauth_failure_reason():
    """Known reasons should remain backward-compatible after normalization."""
    reset_oauth_failure_metrics()
    record_oauth_failure_metric("github", "invalid-state")
    assert 'yesod_oauth_failures_total{provider="github",reason="invalid_state"} 1' in (
        render_oauth_failure_metrics_lines()
    )


def test_metrics_aggregate_unknown_oauth_failure_reason():
    """Unknown reasons should be aggregated into `unknown`."""
    reset_oauth_failure_metrics()
    record_oauth_failure_metric("github", "provider returned weird error")
    assert 'yesod_oauth_failures_total{provider="github",reason="unknown"} 1' in (
        render_oauth_failure_metrics_lines()
    )
