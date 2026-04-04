"""OAuth provider endpoint response code contract tests."""

import importlib

import pytest
from httpx import AsyncClient

auth_router_module = importlib.import_module("app.auth.router")


@pytest.mark.asyncio
async def test_oauth_known_provider_disabled_returns_503(client: AsyncClient, monkeypatch):
    """Known provider with missing credentials should return 503."""
    monkeypatch.setattr(auth_router_module.settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(auth_router_module.settings, "GOOGLE_CLIENT_SECRET", "")

    response = await client.get("/api/v1/auth/google", follow_redirects=False)

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "OAuth provider 'google' is disabled. "
            "Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    }


@pytest.mark.asyncio
async def test_oauth_unsupported_provider_path_returns_404(client: AsyncClient):
    """Unsupported provider path should follow FastAPI route-level 404."""
    response = await client.get("/api/v1/auth/unknown", follow_redirects=False)

    assert response.status_code == 404
