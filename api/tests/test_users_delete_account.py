"""User account deletion endpoint tests."""

from datetime import UTC, datetime

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
    payload = delete_response.json()
    assert delete_response.status_code == 200
    assert payload["deleted_user_id"] == str(user.id)
    assert payload["deleted_email"] == "delete-session-test@example.com"
    scheduled_delete_at = datetime.fromisoformat(payload["scheduled_delete_at"].replace("Z", "+00:00"))
    assert scheduled_delete_at.tzinfo == UTC

    deleted_user = await db_session.scalar(select(DeletedUser).where(DeletedUser.id == user.id))
    assert deleted_user is not None
    assert deleted_user.purge_at == scheduled_delete_at.replace(tzinfo=None)

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


@pytest.mark.asyncio
async def test_delete_account_second_request_with_same_token_returns_user_not_found(
    client: AsyncClient, db_session: AsyncSession
):
    """Second delete with the same access token should fail because user is already removed."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        UserEmail(
            user_id=user.id,
            email="delete-user-not-found@example.com",
            is_primary=True,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    access_token = create_access_token(str(user.id), "delete-user-not-found@example.com")

    first_delete = await client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert first_delete.status_code == 200

    second_delete = await client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert second_delete.status_code == 401
    assert second_delete.json() == {"detail": "User not found"}


@pytest.mark.asyncio
async def test_delete_account_invalidates_sessions_endpoint_for_same_access_token(
    client: AsyncClient, db_session: AsyncSession
):
    """Deleting a user account should make session endpoints reject the same access token."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        UserEmail(
            user_id=user.id,
            email="delete-session-endpoint@example.com",
            is_primary=True,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    await create_refresh_token(db_session, user.id)
    await create_refresh_token(db_session, user.id)
    access_token = create_access_token(str(user.id), "delete-session-endpoint@example.com")
    auth_header = {"Authorization": f"Bearer {access_token}"}

    sessions_before_delete = await client.get("/api/v1/sessions", headers=auth_header)
    assert sessions_before_delete.status_code == 200
    assert sessions_before_delete.json()["total"] == 2

    delete_response = await client.delete("/api/v1/users/me", headers=auth_header)
    assert delete_response.status_code == 200

    sessions_after_delete = await client.get("/api/v1/sessions", headers=auth_header)
    assert sessions_after_delete.status_code == 401
    assert sessions_after_delete.json() == {"detail": "User not found"}
