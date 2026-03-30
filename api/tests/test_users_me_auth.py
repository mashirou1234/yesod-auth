"""Users /me authentication contract tests."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.auth.tokens import settings as token_settings
from app.config import get_settings


@pytest.mark.asyncio
async def test_users_me_requires_valid_token(client: AsyncClient):
    """GET /api/v1/users/me returns fixed 401 contract for invalid JWT."""
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_users_me_rejects_expired_token(client: AsyncClient):
    """GET /api/v1/users/me returns fixed 401 contract for expired JWT."""
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
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_users_me_rejects_token_without_kid_header(client: AsyncClient):
    """GET /api/v1/users/me returns invalid_token_header when JWT kid is missing."""
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "user@example.com",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "type": "access",
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "code": "invalid_token_header",
            "message": "Invalid token header",
            "token_header_fields": ["alg", "typ"],
        }
    }
