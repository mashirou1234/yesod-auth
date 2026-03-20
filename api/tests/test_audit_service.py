"""Contract tests for audit service request-id backfill behavior."""

import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.audit.service import AuditLogger, AuthEventType


@pytest.mark.asyncio
async def test_log_event_backfills_request_id_when_missing(monkeypatch):
    """Missing request-id should be backfilled and marked explicitly."""
    monkeypatch.setenv("TESTING", "0")
    db = AsyncMock()

    await AuditLogger.log_event(
        db=db,
        event_type=AuthEventType.LOGIN_SUCCESS,
        details={"provider": "github"},
        ip_address="127.0.0.1",
    )

    payload = json.loads(db.execute.await_args.args[1]["details"])
    assert payload["provider"] == "github"
    assert payload["request_id_backfilled"] is True
    assert "request_id" in payload
    UUID(payload["request_id"])
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_log_event_preserves_existing_request_id(monkeypatch):
    """Existing request-id value should remain unchanged."""
    monkeypatch.setenv("TESTING", "0")
    db = AsyncMock()
    details = {"provider": "google", "request_id": "req-fixed-123"}

    await AuditLogger.log_event(
        db=db,
        event_type=AuthEventType.LOGIN_SUCCESS,
        details=details,
    )

    payload = json.loads(db.execute.await_args.args[1]["details"])
    assert payload["request_id"] == "req-fixed-123"
    assert payload["request_id_backfilled"] is False
    db.commit.assert_awaited_once()

