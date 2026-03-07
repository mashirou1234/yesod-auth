"""Auth logout endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_logout_without_auth_returns_401(client: AsyncClient):
    """Unauthenticated logout request should be rejected by auth guard."""
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "dummy-refresh-token"},
    )

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)
