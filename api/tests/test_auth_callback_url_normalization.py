"""OAuth callback URL normalization tests."""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

auth_router_module = importlib.import_module("app.auth.router")


def test_normalize_callback_url_trims_only_trailing_slash():
    """Only trailing slash should be normalized."""
    normalized = auth_router_module._normalize_callback_url(
        "https://api.example.com/api/v1/auth/google/callback/?code=abc#frag"
    )
    assert normalized == "https://api.example.com/api/v1/auth/google/callback"


@pytest.mark.asyncio
async def test_validate_callback_url_allows_trailing_slash_difference():
    """Trailing slash difference must be accepted."""
    request = SimpleNamespace(
        url=SimpleNamespace(
            replace=lambda **kwargs: "https://api.example.com/api/v1/auth/google/callback/"
        )
    )

    with patch.object(auth_router_module, "record_oauth_failure_metric") as mock_metric, patch.object(
        auth_router_module.AuditLogger, "log_login", new_callable=AsyncMock
    ) as mock_log_login:
        await auth_router_module._validate_callback_url_or_raise(
            request=request,
            db=AsyncMock(),
            provider="google",
            ip_address="127.0.0.1",
            device_info="pytest",
            expected_callback_url="https://api.example.com/api/v1/auth/google/callback",
        )

    mock_metric.assert_not_called()
    mock_log_login.assert_not_called()


@pytest.mark.asyncio
async def test_validate_callback_url_rejects_real_mismatch():
    """Real mismatch should be rejected and logged."""
    request = SimpleNamespace(
        url=SimpleNamespace(
            replace=lambda **kwargs: "https://api.example.com/api/v1/auth/google/other-callback"
        )
    )

    with patch.object(auth_router_module, "record_oauth_failure_metric") as mock_metric, patch.object(
        auth_router_module.AuditLogger, "log_login", new_callable=AsyncMock
    ) as mock_log_login:
        with pytest.raises(HTTPException) as exc_info:
            await auth_router_module._validate_callback_url_or_raise(
                request=request,
                db=AsyncMock(),
                provider="google",
                ip_address="127.0.0.1",
                device_info="pytest",
                expected_callback_url="https://api.example.com/api/v1/auth/google/callback",
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "OAuth callback URL mismatch"
    mock_metric.assert_called_once_with("google", "callback_url_mismatch")
    mock_log_login.assert_awaited_once()
