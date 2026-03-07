"""Users /me authentication contract tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_users_me_requires_valid_token(client: AsyncClient):
    """GET /api/v1/users/me returns fixed 401 contract for invalid JWT."""
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}
