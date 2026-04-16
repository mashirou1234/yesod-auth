"""Refresh token endpoint tests."""

import time
import importlib
from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from httpx import AsyncClient
from limits import RateLimitItemPerMinute
from slowapi.errors import RateLimitExceeded
from slowapi.wrappers import Limit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rate_limit import MISSING_OAUTH_PROVIDER_KEY
from app.auth.tokens import create_access_token, create_refresh_token, hash_refresh_token
from app.main import app
from app.metrics import (
    render_oauth_rate_limit_burst_metrics_lines,
    reset_oauth_rate_limit_burst_metrics,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserEmail

auth_router = importlib.import_module("app.auth.router")


class FrozenDateTime(datetime):
    """Controllable datetime replacement for token boundary tests."""

    current = datetime(2026, 1, 1, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        current = cls.current
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        if tz is None:
            return current
        return current.astimezone(tz)


@pytest.fixture(autouse=True)
def disable_rate_limiter(request: pytest.FixtureRequest):
    """Avoid external Redis dependency for refresh endpoint tests."""
    if request.node.get_closest_marker("enable_rate_limiter"):
        yield
        return

    original_enabled = app.state.limiter.enabled
    app.state.limiter.enabled = False
    try:
        yield
    finally:
        app.state.limiter.enabled = original_enabled


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token(client: AsyncClient):
    """Invalid refresh token should return 401 with stable detail message."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-refresh-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


@pytest.mark.asyncio
async def test_refresh_rejects_expired_token(client: AsyncClient, db_session: AsyncSession):
    """Expired refresh token should return the same 401 contract."""
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    refresh_token = await create_refresh_token(db_session, user.id)
    token_hash = hash_refresh_token(refresh_token)
    token_record = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    assert token_record is not None
    token_record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


@pytest.mark.asyncio
async def test_refresh_accepts_token_one_second_before_expiry(
    client: AsyncClient, db_session: AsyncSession
):
    """A token remains valid until just before its expiration boundary."""
    user = User()
    user.emails.append(
        UserEmail(
            email="refresh-boundary@example.com",
            is_primary=True,
        )
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    with (
        patch("app.auth.tokens.datetime", FrozenDateTime),
        patch.object(User, "email", new_callable=PropertyMock, return_value="refresh-boundary@example.com"),
    ):
        FrozenDateTime.current = datetime(2026, 1, 1, tzinfo=UTC)
        refresh_token = await create_refresh_token(db_session, user.id)
        token_hash = hash_refresh_token(refresh_token)
        token_record = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        assert token_record is not None

        FrozenDateTime.current = token_record.expires_at - timedelta(seconds=1)
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_rejects_token_at_exact_expiry_boundary(
    client: AsyncClient, db_session: AsyncSession
):
    """A token is invalid once current time reaches its expiration timestamp."""
    user = User()
    user.emails.append(
        UserEmail(
            email="refresh-expired-boundary@example.com",
            is_primary=True,
        )
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    with (
        patch("app.auth.tokens.datetime", FrozenDateTime),
        patch.object(User, "email", new_callable=PropertyMock, return_value="refresh-expired-boundary@example.com"),
    ):
        FrozenDateTime.current = datetime(2026, 1, 1, tzinfo=UTC)
        refresh_token = await create_refresh_token(db_session, user.id)
        token_hash = hash_refresh_token(refresh_token)
        token_record = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        assert token_record is not None

        FrozenDateTime.current = token_record.expires_at
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


@pytest.mark.asyncio
async def test_refresh_rejects_revoked_session_token(
    client: AsyncClient, db_session: AsyncSession
):
    """Revoked session refresh token should not be reusable."""
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    refresh_token = await create_refresh_token(db_session, user.id)
    access_token = create_access_token(str(user.id), "revoke-test@example.com")
    auth_header = {"Authorization": f"Bearer {access_token}"}

    token_record = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(refresh_token)
        )
    )
    assert token_record is not None
    session_id = token_record.id

    revoke_response = await client.delete(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header,
    )
    assert revoke_response.status_code == 200

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json() == {"detail": "Invalid or expired refresh token"}


@pytest.mark.asyncio
async def test_refresh_reuse_logs_revoked_token_status(
    client: AsyncClient, db_session: AsyncSession
):
    """Reusing a rotated refresh token should log stable failure keys."""
    user = User()
    user.emails.append(
        UserEmail(
            email="refresh-reuse@example.com",
            is_primary=True,
        )
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    refresh_token = await create_refresh_token(db_session, user.id)
    with (
        patch("app.auth.router.AuditLogger.log_event", new=AsyncMock()) as mock_log_event,
        patch.object(User, "email", new_callable=PropertyMock, return_value="refresh-reuse@example.com"),
    ):
        first_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert first_refresh.status_code == 200

        second_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    assert second_refresh.status_code == 401
    assert second_refresh.json() == {"detail": "Invalid or expired refresh token"}
    assert mock_log_event.await_count == 2
    failed_call = mock_log_event.await_args_list[1]
    assert failed_call.args[2] is None
    assert failed_call.args[3] == {
        "failure_reason": "invalid_or_expired_refresh_token",
        "token_status": "revoked",
    }


@pytest.mark.asyncio
@pytest.mark.enable_rate_limiter
async def test_refresh_rate_limited_response_includes_retry_after_header(client: AsyncClient):
    """Rate limited refresh response should include Retry-After header."""
    reset_oauth_rate_limit_burst_metrics()
    limiter = app.state.limiter
    limit_item = RateLimitItemPerMinute(30, 1)
    synthetic_limit = Limit(
        limit=limit_item,
        key_func=limiter._key_func,
        scope=None,
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        cost=1,
        override_defaults=False,
    )

    def raise_rate_limit(request, endpoint_func=None, in_middleware=True):
        request.state.view_rate_limit = (limit_item, ["test-client"])
        raise RateLimitExceeded(synthetic_limit)

    reset_at = int(time.time()) + 60
    with (
        patch.object(limiter, "_check_request_limit", side_effect=raise_rate_limit),
        patch.object(limiter.limiter, "get_window_stats", return_value=(reset_at, 0)),
    ):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-refresh-token"},
        )

    assert response.status_code == 429
    retry_after = response.headers.get("Retry-After")
    assert retry_after is not None
    assert retry_after.isdigit()
    assert int(retry_after) >= 0
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("max_retries", "expected_attempts"),
    [
        (1, 2),
        (3, 4),
        (5, 6),
    ],
)
async def test_refresh_retry_limit_is_configurable(monkeypatch, max_retries: int, expected_attempts: int):
    rotate_mock = AsyncMock(side_effect=RuntimeError("temporary failure"))
    monkeypatch.setattr(auth_router, "rotate_refresh_token", rotate_mock)
    monkeypatch.setattr(auth_router.settings, "TOKEN_REFRESH_MAX_RETRIES", max_retries)

    with pytest.raises(RuntimeError, match="temporary failure"):
        await auth_router._rotate_refresh_token_with_retry(None, "token", None, None)

    assert rotate_mock.await_count == expected_attempts


@pytest.mark.asyncio
async def test_refresh_retry_limit_uses_default_when_setting_missing(monkeypatch):
    rotate_mock = AsyncMock(side_effect=RuntimeError("temporary failure"))
    monkeypatch.setattr(auth_router, "rotate_refresh_token", rotate_mock)
    monkeypatch.setattr(auth_router, "settings", SimpleNamespace())

    with pytest.raises(RuntimeError, match="temporary failure"):
        await auth_router._rotate_refresh_token_with_retry(None, "token", None, None)

    assert rotate_mock.await_count == 4


@pytest.mark.asyncio
@pytest.mark.enable_rate_limiter
async def test_oauth_provider_rate_limit_records_burst_metric(client: AsyncClient):
    """OAuth provider endpoint 429 should increment provider-level burst metric."""
    reset_oauth_rate_limit_burst_metrics()
    limiter = app.state.limiter
    limit_item = RateLimitItemPerMinute(10, 1)
    synthetic_limit = Limit(
        limit=limit_item,
        key_func=limiter._key_func,
        scope=None,
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        cost=1,
        override_defaults=False,
    )

    def raise_rate_limit(request, endpoint_func=None, in_middleware=True):
        request.state.view_rate_limit = (limit_item, ["test-client"])
        raise RateLimitExceeded(synthetic_limit)

    reset_at = int(time.time()) + 60
    with (
        patch.object(limiter, "_check_request_limit", side_effect=raise_rate_limit),
        patch.object(limiter.limiter, "get_window_stats", return_value=(reset_at, 0)),
    ):
        response = await client.get("/api/v1/auth/google")

    assert response.status_code == 429
    assert 'yesod_oauth_rate_limit_burst_total{provider="google"} 1' in (
        render_oauth_rate_limit_burst_metrics_lines()
    )
    assert (
        f'yesod_oauth_rate_limit_burst_total{{provider="{MISSING_OAUTH_PROVIDER_KEY}"}} 1'
        not in render_oauth_rate_limit_burst_metrics_lines()
    )
