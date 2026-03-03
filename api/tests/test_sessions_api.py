"""Sessions API tests."""

import uuid

import pytest
from httpx import AsyncClient


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
    assert response.json() == {"detail": "Session not found or already revoked"}
