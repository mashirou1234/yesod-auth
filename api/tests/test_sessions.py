"""Session API tests."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.auth.tokens import settings as token_settings


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/sessions"),
        ("delete", "/api/v1/sessions"),
    ],
)
async def test_sessions_endpoints_require_authorization_header(
    client: AsyncClient, method: str, path: str
):
    """Missing Authorization header should be rejected by protected session endpoints."""
    response = await getattr(client, method)(path)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_sessions_list_requires_valid_token(client: AsyncClient):
    """Invalid token should be rejected on session listing endpoint."""
    response = await client.get(
        "/api/v1/sessions",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_sessions_list_rejects_expired_token(client: AsyncClient):
    """Expired access token should be rejected."""
    login_response = await client.get("/api/v1/auth/mock/login")
    assert login_response.status_code == 200

    valid_token = login_response.json()["access_token"]
    payload = jwt.decode(
        valid_token,
        token_settings.JWT_SECRET,
        algorithms=[token_settings.JWT_ALGORITHM],
        options={"verify_exp": False},
    )
    payload["exp"] = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())

    expired_token = jwt.encode(
        payload,
        token_settings.JWT_SECRET,
        algorithm=token_settings.JWT_ALGORITHM,
    )

    response = await client.get(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_sessions_list_with_valid_token_returns_200(client: AsyncClient):
    """Valid token should allow listing sessions."""
    login_response = await client.get("/api/v1/auth/mock/login")
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data
