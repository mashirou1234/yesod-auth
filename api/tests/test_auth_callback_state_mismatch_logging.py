"""OAuth callback invalid-state audit logging contracts."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider",
    ["google", "discord", "github", "x", "linkedin", "facebook", "slack", "twitch"],
)
async def test_callback_mismatched_state_logs_provider_name(client, provider):
    """State mismatch audit reason must always include provider and request-id."""
    with (
        patch("app.auth.rate_limit.limiter._check_request_limit", return_value=None),
        patch("app.auth.router.OAuthStateStore.get_and_delete", new=AsyncMock(return_value=None)),
        patch("app.auth.router.AuditLogger.log_login", new=AsyncMock()) as mock_log_login,
    ):
        response = await client.get(
            f"/api/v1/auth/{provider}/callback?code=test-code&state=unexpected-state",
            headers={"X-Request-Id": "req-state-mismatch"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired state"}
    assert mock_log_login.await_count == 1
    assert (
        mock_log_login.await_args.args[6]
        == f"Invalid state [provider={provider}] [request-id=req-state-mismatch]"
    )
