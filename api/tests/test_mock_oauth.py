"""Mock OAuth tests."""

import pytest
from httpx import AsyncClient

from app.auth.mock_oauth import MockOAuthUser


@pytest.mark.asyncio
async def test_mock_login_alice(client: AsyncClient):
    """Test mock login with default user (alice)."""
    response = await client.get("/api/v1/auth/mock/login")
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["mock_user"] == "alice"
    assert data["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_mock_login_bob(client: AsyncClient):
    """Test mock login with bob user."""
    response = await client.get("/api/v1/auth/mock/login?user=bob")
    assert response.status_code == 200

    data = response.json()
    assert data["mock_user"] == "bob"
    assert data["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_mock_login_with_discord(client: AsyncClient):
    """Test mock login with discord provider."""
    response = await client.get("/api/v1/auth/mock/login?provider=discord")
    assert response.status_code == 200

    data = response.json()
    assert data["provider"] == "discord"


@pytest.mark.asyncio
async def test_mock_login_invalid_provider(client: AsyncClient):
    """Test mock login with invalid provider."""
    response = await client.get("/api/v1/auth/mock/login?provider=invalid")
    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported OAuth provider 'unknown'."}


@pytest.mark.asyncio
async def test_mock_login_provider_is_case_insensitive(client: AsyncClient):
    """Mixed-case provider should be normalized and accepted."""
    response = await client.get("/api/v1/auth/mock/login?provider=GitHub")
    assert response.status_code == 200
    assert response.json()["provider"] == "github"


@pytest.mark.asyncio
async def test_mock_login_unknown_provider_keeps_fixed_detail(client: AsyncClient):
    """Unknown provider variants should keep a fixed 400 detail."""
    response = await client.get("/api/v1/auth/mock/login?provider=%20InVaLiD%20")
    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported OAuth provider 'unknown'."}


@pytest.mark.asyncio
async def test_list_mock_users(client: AsyncClient):
    """Test listing available mock users."""
    response = await client.get("/api/v1/auth/mock/users")
    assert response.status_code == 200

    data = response.json()
    assert "mock_users" in data
    assert "alice" in data["mock_users"]
    assert "bob" in data["mock_users"]
    assert "charlie" in data["mock_users"]


@pytest.mark.asyncio
async def test_authenticated_request(client: AsyncClient):
    """Test making authenticated request with mock token."""
    # Login first
    login_response = await client.get("/api/v1/auth/mock/login")
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    # Use token to access protected endpoint
    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_mock_login_github_avoids_provider_user_id_collision(
    client: AsyncClient, monkeypatch
):
    """GitHub mock provider_user_id must avoid collisions even with same numeric suffix IDs."""
    collision_users = {
        "alice": MockOAuthUser(
            id="mock-alice-999",
            email="alice@example.com",
            name="Alice Developer",
            picture=None,
        ),
        "dup-a": MockOAuthUser(
            id="mock-dup-a-123",
            email="dup-a@example.com",
            name="Duplicate A",
            picture=None,
        ),
        "dup-b": MockOAuthUser(
            id="mock-dup-b-123",
            email="dup-b@example.com",
            name="Duplicate B",
            picture=None,
        ),
    }
    monkeypatch.setattr("app.auth.mock_oauth.MOCK_USERS", collision_users)

    response_a = await client.get("/api/v1/auth/mock/login?provider=github&user=dup-a")
    response_b = await client.get("/api/v1/auth/mock/login?provider=github&user=dup-b")

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["email"] == "dup-a@example.com"
    assert response_b.json()["email"] == "dup-b@example.com"
    assert response_a.json()["user_id"] != response_b.json()["user_id"]
