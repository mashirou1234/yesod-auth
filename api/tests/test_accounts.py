"""Accounts API tests."""

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
    ],
    ids=["provider_uppercase", "provider_surrounded_by_spaces"],
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
