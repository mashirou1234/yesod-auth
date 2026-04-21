"""Sessions API tests."""

import uuid
from importlib import import_module
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuthEventType
from app.auth.tokens import create_access_token, create_refresh_token, hash_refresh_token
from app.models.refresh_token import RefreshToken
from app.models.user import User

sessions_router_module = import_module("app.sessions.router")


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


@pytest.mark.asyncio
async def test_revoke_all_sessions_logs_audit_with_revoked_count_and_user_id(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """DELETE /api/v1/sessions should emit one all-sessions audit event."""
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    await create_refresh_token(db_session, user.id)
    await create_refresh_token(db_session, user.id)

    access_token = create_access_token(str(user.id), "revoke-all-audit@example.com")
    auth_header = {"Authorization": f"Bearer {access_token}"}

    mock_log_event = AsyncMock()
    monkeypatch.setattr(sessions_router_module.AuditLogger, "log_event", mock_log_event)

    response = await client.delete("/api/v1/sessions", headers=auth_header)

    assert response.status_code == 200
    assert response.json() == {
        "message": "Sessions revoked successfully",
        "session_id": None,
        "revoked_count": 2,
    }
    mock_log_event.assert_awaited_once()

    _, event_type, user_id, details, *_ = mock_log_event.await_args.args
    assert event_type == AuthEventType.ALL_SESSIONS_REVOKED
    assert user_id == user.id
    assert details["audit_key"] == "revoked_count"
    assert details["revoked_count"] == 2
    assert details["user_id"] == str(user.id)


@pytest.mark.asyncio
async def test_revoke_all_sessions_without_active_tokens_returns_schema_contract(
    client: AsyncClient, db_session: AsyncSession
):
    """DELETE /api/v1/sessions keeps response keys stable when revoked_count is zero."""
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    access_token = create_access_token(str(user.id), "revoke-all-empty@example.com")
    auth_header = {"Authorization": f"Bearer {access_token}"}

    response = await client.delete("/api/v1/sessions", headers=auth_header)

    assert response.status_code == 200
    assert response.json() == {
        "message": "Sessions revoked successfully",
        "session_id": None,
        "revoked_count": 0,
    }
