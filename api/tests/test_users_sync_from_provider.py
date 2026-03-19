"""Users sync-from-provider contract tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token
from app.models import OAuthAccount, User, UserProfile


@pytest.mark.asyncio
async def test_sync_from_provider_returns_conflict_contract_for_mismatched_profile(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /api/v1/users/me/sync-from-provider returns fixed 409 contract on conflict."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id,
            display_name="Local Name",
            avatar_url="https://example.com/local.png",
        )
    )
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="google-user-1",
            provider_display_name="Provider Name",
            provider_avatar_url="https://example.com/provider.png",
        )
    )
    await db_session.commit()

    access_token = create_access_token(str(user.id), "sync-conflict@example.com")
    response = await client.post(
        "/api/v1/users/me/sync-from-provider?provider=google",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "SYNC_FROM_PROVIDER_CONFLICT",
            "message": (
                "Local profile already has different values. "
                "Clear conflicting fields before syncing from provider."
            ),
            "conflicting_fields": ["display_name", "avatar_url"],
        }
    }


@pytest.mark.asyncio
async def test_sync_from_provider_keeps_success_response_contract(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /api/v1/users/me/sync-from-provider keeps success response unchanged."""
    user = User()
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserProfile(user_id=user.id))
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="google-user-2",
            provider_display_name="Provider User",
            provider_avatar_url="https://example.com/provider-user.png",
        )
    )
    await db_session.commit()

    access_token = create_access_token(str(user.id), "sync-success@example.com")
    response = await client.post(
        "/api/v1/users/me/sync-from-provider?provider=google",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Profile synced from google",
        "provider": "google",
        "updated_fields": ["display_name", "avatar_url"],
        "display_name": "Provider User",
        "avatar_url": "https://example.com/provider-user.png",
    }
