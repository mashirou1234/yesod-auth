"""Tests for DB session cleanup behavior."""

from unittest.mock import AsyncMock

import pytest

from app.db import session as db_session_module


class _SessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_get_db_normal_flow_closes_session(monkeypatch):
    fake_session = AsyncMock()
    monkeypatch.setattr(
        db_session_module,
        "async_session_maker",
        lambda: _SessionContext(fake_session),
    )

    gen = db_session_module.get_db()
    yielded = await anext(gen)

    assert yielded is fake_session

    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    fake_session.rollback.assert_not_awaited()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_exception_flow_rolls_back_and_closes_session(monkeypatch):
    fake_session = AsyncMock()
    monkeypatch.setattr(
        db_session_module,
        "async_session_maker",
        lambda: _SessionContext(fake_session),
    )

    gen = db_session_module.get_db()
    await anext(gen)

    with pytest.raises(RuntimeError, match="boom"):
        await gen.athrow(RuntimeError("boom"))

    fake_session.rollback.assert_awaited_once()
    fake_session.close.assert_awaited_once()
