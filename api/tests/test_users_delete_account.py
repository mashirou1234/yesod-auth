"""User account deletion endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token, create_refresh_token, hash_refresh_token
from app.main import app
from app.models import DeletedUser, RefreshToken, User, UserEmail


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Avoid external Redis dependency in account deletion tests."""
    original_enabled = app.state.limiter.enabled
    app.state.limiter.enabled = False
    try:
        yield
    finally:
        app.state.limiter.enabled = original_enabled


@pytest.mark.asyncio
async def test_delete_account_invalidates_related_session_tokens(
    client: AsyncClient, db_session: AsyncSession
):
    """Deleting a user account should invalidate existing refresh tokens."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        UserEmail(
            user_id=user.id,
            email="delete-session-test@example.com",
            is_primary=True,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    refresh_token = await create_refresh_token(db_session, user.id)
    access_token = create_access_token(str(user.id), "delete-session-test@example.com")

    delete_response = await client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_user_id"] == str(user.id)

    deleted_user = await db_session.scalar(select(DeletedUser).where(DeletedUser.id == user.id))
    assert deleted_user is not None

    refresh_record = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
    )
    assert refresh_record is None

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json() == {"detail": "Invalid or expired refresh token"}
