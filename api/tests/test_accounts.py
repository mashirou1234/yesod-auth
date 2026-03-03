"""Accounts API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_accounts_requires_authentication(client: AsyncClient):
    """Unauthenticated access to accounts endpoint should be rejected."""
    response = await client.get("/api/v1/accounts")

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
