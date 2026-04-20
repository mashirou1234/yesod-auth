"""Accounts API tests."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token
from app.models import OAuthAccount, User


@pytest.mark.asyncio
async def test_list_accounts_requires_authentication(client: AsyncClient):
    """Unauthenticated access to accounts endpoint should be rejected."""
    response = await client.get("/api/v1/accounts")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_input", "expected_detail"),
    [
        ("Google", "Unsupported provider"),
        (" google ", "Unsupported provider"),
        ("github", "Unsupported provider"),
        ("discord%09", "Unsupported provider"),
    ],
    ids=[
        "provider_uppercase",
        "provider_surrounded_by_spaces",
        "provider_unsupported_literal",
        "provider_urlencoded_tab",
    ],
)
async def test_unlink_account_returns_400_for_provider_boundary_inputs(
    client: AsyncClient, db_session: AsyncSession, provider_input: str, expected_detail: str
):
    """Unsupported provider boundary inputs should keep stable 400 contract."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="google-user-449",
            access_token="token-449",
        )
    )
    await db_session.commit()

    access_token = create_access_token(str(user.id), "accounts-boundary@example.com")
    response = await client.delete(
        f"/api/v1/accounts/{provider_input}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == expected_detail


@pytest.mark.asyncio
async def test_unlink_account_returns_404_for_valid_but_unlinked_provider(
    client: AsyncClient, db_session: AsyncSession
):
    """Supported provider without linked account should keep stable 404 error contract."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="linked-google-user",
            access_token="linked-google-token",
        )
    )
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="linked-google-user-2",
            access_token="linked-google-token-2",
        )
    )
    await db_session.commit()

    access_token = create_access_token(str(user.id), "accounts-unlinked-provider@example.com")
    response = await client.delete(
        "/api/v1/accounts/discord",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "No discord account linked"


@pytest.mark.asyncio
async def test_unlink_account_returns_400_when_last_authentication_method(
    client: AsyncClient, db_session: AsyncSession
):
    """Single linked account must keep stable 400 error contract."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="single-google-user",
            access_token="single-token",
        )
    )
    await db_session.commit()

    access_token = create_access_token(str(user.id), "accounts-last-method@example.com")
    response = await client.delete(
        "/api/v1/accounts/google",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Cannot unlink the last authentication method"


def test_build_audit_actor_uses_fallback_for_empty_value():
    """Actor fallback should be stable for empty inputs."""
    from app.accounts.router import _build_audit_actor

    assert _build_audit_actor("") == "unknown-actor"
    assert _build_audit_actor("   ") == "unknown-actor"
    assert _build_audit_actor(None) == "unknown-actor"


def test_build_audit_target_uses_fallback_for_empty_provider_user_id():
    """Target fallback should be stable for missing provider user id."""
    from app.accounts.router import _build_audit_target

    assert _build_audit_target("google", "") == "oauth-account:google:unknown-target"
    assert _build_audit_target("google", "   ") == "oauth-account:google:unknown-target"
    assert _build_audit_target("google", None) == "oauth-account:google:unknown-target"


@pytest.mark.asyncio
async def test_unlink_account_logs_audit_with_request_actor_target(
    client: AsyncClient, db_session: AsyncSession
):
    """Unlink success should keep request_id/actor/target audit contract."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="google-user-audit-1",
            access_token="google-token-audit-1",
        )
    )
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="discord",
            provider_user_id="discord-user-audit-2",
            access_token="discord-token-audit-2",
        )
    )
    await db_session.commit()

    access_token = create_access_token(str(user.id), "accounts-audit@example.com")

    with patch("app.accounts.router.AuditLogger.log_event", new=AsyncMock()) as mock_log_event:
        response = await client.delete(
            "/api/v1/accounts/google",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Request-Id": "req-accounts-unlink-123",
            },
        )

    assert response.status_code == 200
    mock_log_event.assert_awaited_once()
    _, event_type, event_user_id, details, *_ = mock_log_event.await_args.args
    assert event_type.value == "account_unlinked"
    assert str(event_user_id) == str(user.id)
    assert details["request_id"] == "req-accounts-unlink-123"
    assert details["actor"] == str(user.id)
    assert details["target"] == "oauth-account:google:google-user-audit-1"
