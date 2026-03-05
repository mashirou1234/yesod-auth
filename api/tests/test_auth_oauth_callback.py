"""OAuth callback endpoint tests."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Avoid external Redis dependency for callback endpoint tests."""
    original_enabled = app.state.limiter.enabled
    app.state.limiter.enabled = False
    try:
        yield
    finally:
        app.state.limiter.enabled = original_enabled


@pytest.mark.asyncio
async def test_github_callback_missing_state_logs_and_returns_400(client: AsyncClient):
    """Missing state should return 400 and emit an audit login failure."""
    with patch("app.auth.router.AuditLogger.log_login", new=AsyncMock()) as mock_log_login:
        response = await client.get("/api/v1/auth/github/callback", params={"code": "dummy-code"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Missing state parameter"}

    mock_log_login.assert_awaited_once()
    args = mock_log_login.await_args.args
    assert args[2] == "github"
    assert args[3] is False
    assert args[6] == "Missing state parameter"
