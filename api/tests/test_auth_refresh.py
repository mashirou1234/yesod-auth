"""Refresh token endpoint tests."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_refresh_token, hash_refresh_token
from app.main import app
from app.models.refresh_token import RefreshToken
from app.models.user import User


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Avoid external Redis dependency for refresh endpoint tests."""
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
