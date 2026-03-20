"""Sessions API tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token, create_refresh_token, hash_refresh_token
from app.models.refresh_token import RefreshToken
from app.models.user import User


@pytest.mark.asyncio
async def test_revoke_session_not_found_returns_contract(client: AsyncClient):
    """DELETE /api/v1/sessions/{session_id} returns 404 contract for missing session."""
    login_response = await client.get("/api/v1/auth/mock/login")
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    missing_session_id = uuid.uuid4()
    response = await client.delete(
        f"/api/v1/sessions/{missing_session_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found"}


@pytest.mark.asyncio
async def test_revoke_session_is_idempotent_for_same_session_id(
    client: AsyncClient, db_session: AsyncSession
):
    """DELETE /api/v1/sessions/{session_id} returns stable success for duplicate revoke."""
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
    session_id = token_record.id
    access_token = create_access_token(str(user.id), "idempotent-revoke@example.com")
    auth_header = {"Authorization": f"Bearer {access_token}"}

    first_response = await client.delete(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header,
    )
    second_response = await client.delete(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header,
    )

    assert first_response.status_code == 200
    assert first_response.json() == {
        "message": "Session revoked successfully",
        "session_id": str(session_id),
        "revoked_count": None,
    }
    assert second_response.status_code == 200
    assert second_response.json() == {
        "message": "Session revoked successfully",
        "session_id": str(session_id),
        "revoked_count": None,
    }
