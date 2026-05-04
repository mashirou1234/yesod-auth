"""OAuth provider endpoint response code contract tests."""

import importlib

import pytest
from httpx import AsyncClient

auth_router_module = importlib.import_module("app.auth.router")


@pytest.fixture(autouse=True)
def bypass_rate_limit(monkeypatch):
    """Avoid external Redis dependency for endpoint contract tests."""

    def _fake_check_request_limit(request, *args, **kwargs):
        request.state.view_rate_limit = None

    monkeypatch.setattr(
        auth_router_module.limiter, "_check_request_limit", _fake_check_request_limit
    )


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
async def test_oauth_unsupported_provider_path_returns_400(client: AsyncClient):
    """Unsupported provider path must return explicit 400 contract."""
    response = await client.get("/api/v1/auth/unknown", follow_redirects=False)

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported OAuth provider 'unknown'."}


@pytest.mark.asyncio
async def test_oauth_unsupported_provider_path_variant_keeps_fixed_detail(client: AsyncClient):
    """Unsupported provider case/space variants must keep fixed 400 detail."""
    response = await client.get("/api/v1/auth/%20UnKnOwN%20", follow_redirects=False)

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported OAuth provider 'unknown'."}


@pytest.mark.asyncio
async def test_oauth_provider_path_case_variant_redirects_to_canonical(client: AsyncClient):
    """Mixed-case provider path should be normalized via redirect."""
    response = await client.get("/api/v1/auth/GitHub", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/auth/github"


@pytest.mark.asyncio
async def test_oauth_callback_path_case_variant_redirects_to_canonical(client: AsyncClient):
    """Mixed-case callback path should redirect while preserving query."""
    response = await client.get(
        "/api/v1/auth/GitHub/callback?code=abc&state=xyz",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/auth/github/callback?code=abc&state=xyz"
