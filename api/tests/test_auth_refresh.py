"""Refresh token endpoint tests."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from limits import RateLimitItemPerMinute
from slowapi.errors import RateLimitExceeded
from slowapi.wrappers import Limit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token, create_refresh_token, hash_refresh_token
from app.main import app
from app.models.refresh_token import RefreshToken
from app.models.user import User


@pytest.fixture(autouse=True)
def disable_rate_limiter(request: pytest.FixtureRequest):
    """Avoid external Redis dependency for refresh endpoint tests."""
    if request.node.get_closest_marker("enable_rate_limiter"):
        yield
        return

    original_enabled = app.state.limiter.enabled
    app.state.limiter.enabled = False
    try:
        yield
    finally:
        app.state.limiter.enabled = original_enabled


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token(client: AsyncClient):
    """Invalid refresh token should return 401 with stable detail message."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-refresh-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


@pytest.mark.asyncio
async def test_refresh_rejects_expired_token(client: AsyncClient, db_session: AsyncSession):
    """Expired refresh token should return the same 401 contract."""
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    refresh_token = await create_refresh_token(db_session, user.id)
    token_hash = hash_refresh_token(refresh_token)
    token_record = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    assert token_record is not None
    token_record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


@pytest.mark.asyncio
async def test_refresh_rejects_revoked_session_token(
    client: AsyncClient, db_session: AsyncSession
):
    """Revoked session refresh token should not be reusable."""
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    refresh_token = await create_refresh_token(db_session, user.id)
    access_token = create_access_token(str(user.id), "revoke-test@example.com")
    auth_header = {"Authorization": f"Bearer {access_token}"}

    token_record = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(refresh_token)
        )
    )
    assert token_record is not None
    session_id = token_record.id

    revoke_response = await client.delete(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header,
    )
    assert revoke_response.status_code == 200

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json() == {"detail": "Invalid or expired refresh token"}


@pytest.mark.asyncio
@pytest.mark.enable_rate_limiter
async def test_refresh_rate_limited_response_includes_retry_after_header(client: AsyncClient):
    """Rate limited refresh response should include Retry-After header."""
    limiter = app.state.limiter
    limit_item = RateLimitItemPerMinute(30, 1)
    synthetic_limit = Limit(
        limit=limit_item,
        key_func=limiter._key_func,
        scope=None,
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        cost=1,
        override_defaults=False,
    )

    def raise_rate_limit(request, endpoint_func=None, in_middleware=True):
        request.state.view_rate_limit = (limit_item, ["test-client"])
        raise RateLimitExceeded(synthetic_limit)

    reset_at = int(time.time()) + 60
    with (
        patch.object(limiter, "_check_request_limit", side_effect=raise_rate_limit),
        patch.object(limiter.limiter, "get_window_stats", return_value=(reset_at, 0)),
    ):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-refresh-token"},
        )

    assert response.status_code == 429
    retry_after = response.headers.get("Retry-After")
    assert retry_after is not None
    assert retry_after.isdigit()
    assert int(retry_after) >= 0
