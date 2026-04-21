"""Users /me authentication contract tests."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

from app.auth.tokens import settings as token_settings
from app.config import get_settings


async def _login_auth_header(client: AsyncClient) -> dict[str, str]:
    login_response = await client.get("/api/v1/auth/mock/login")
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("jwt_headers", "expected_header_fields"),
    [
        ({"kid": ""}, ["alg", "kid", "typ"]),
        ({"kid": 123}, ["alg", "kid", "typ"]),
    ],
)
async def test_users_me_rejects_token_with_invalid_kid_header_value(
    client: AsyncClient,
    jwt_headers: dict[str, object],
    expected_header_fields: list[str],
):
    """GET /api/v1/users/me keeps invalid_token_header for invalid kid values."""
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
        headers=jwt_headers,
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
            "token_header_fields": expected_header_fields,
        }
    }


@pytest.mark.asyncio
async def test_users_me_update_rejects_blank_display_name(client: AsyncClient):
    auth_header = await _login_auth_header(client)

    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_header,
        json={"display_name": "   "},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "display_name"]
    assert "display_name must not be blank" in response.json()["detail"][0]["msg"]


@pytest.mark.asyncio
@pytest.mark.parametrize("avatar_url", ["not-a-url", "ftp://example.com/avatar.png"])
async def test_users_me_update_rejects_invalid_avatar_url_with_stable_error(
    client: AsyncClient, avatar_url: str
):
    auth_header = await _login_auth_header(client)

    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_header,
        json={"avatar_url": avatar_url},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "avatar_url"]
    assert "avatar_url must be a valid http(s) URL" in response.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_users_me_update_normalizes_trimmed_profile_fields(client: AsyncClient):
    auth_header = await _login_auth_header(client)

    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_header,
        json={
            "display_name": "  Updated Name  ",
            "avatar_url": "  https://example.com/avatar.png  ",
        },
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Name"
    assert response.json()["avatar_url"] == "https://example.com/avatar.png"
