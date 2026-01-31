"""Mock OAuth tests."""
import pytest
from httpx import AsyncClient


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
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["email"] == "alice@example.com"
