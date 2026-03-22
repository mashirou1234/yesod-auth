"""Missing bearer token contract tests across protected endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/api/v1/users/me", {}),
        ("get", "/api/v1/sessions", {}),
        ("delete", "/api/v1/sessions", {}),
        ("get", "/api/v1/accounts", {}),
        ("post", "/api/v1/auth/logout", {"json": {"refresh_token": "dummy"}}),
    ],
)
async def test_missing_bearer_token_returns_fixed_contract(
    client: AsyncClient, method: str, path: str, kwargs: dict
):
    """All protected endpoints should return the same 401 contract when token is missing."""
    response = await getattr(client, method)(path, **kwargs)

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "code": "missing_bearer_token",
            "message": "Not authenticated",
        }
    }
