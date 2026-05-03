"""Token utility boundary tests for auth tokens module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import (
    classify_refresh_token_failure,
    create_refresh_token,
    hash_refresh_token,
    validate_refresh_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


class FrozenDateTime(datetime):
    """Controllable datetime replacement for token boundary checks."""

    current = datetime(2026, 1, 1, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        current = cls.current
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        if tz is None:
            return current
        return current.astimezone(tz)


async def _create_user(db_session: AsyncSession) -> User:
    user = User()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_validate_refresh_token_accepts_naive_expiry_just_before_boundary(
    db_session: AsyncSession,
):
    """Token remains valid immediately before expiry even if DB returns naive datetime."""
    user = await _create_user(db_session)

    with patch("app.auth.tokens.datetime", FrozenDateTime):
        FrozenDateTime.current = datetime(2026, 1, 1, tzinfo=UTC)
        refresh_token = await create_refresh_token(db_session, user.id)
        token_record = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        )
        assert token_record is not None

        naive_expiry = token_record.expires_at.replace(tzinfo=None)
        token_record.expires_at = naive_expiry
        await db_session.commit()

        FrozenDateTime.current = naive_expiry.replace(tzinfo=UTC) - timedelta(microseconds=1)
        validated = await validate_refresh_token(db_session, refresh_token)

    assert validated is not None


@pytest.mark.asyncio
async def test_refresh_token_classification_marks_exact_expiry_as_expired(
    db_session: AsyncSession,
):
    """Exact boundary should be treated as expired consistently."""
    user = await _create_user(db_session)

    with patch("app.auth.tokens.datetime", FrozenDateTime):
        FrozenDateTime.current = datetime(2026, 1, 1, tzinfo=UTC)
        refresh_token = await create_refresh_token(db_session, user.id)
        token_record = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        )
        assert token_record is not None

        naive_expiry = token_record.expires_at.replace(tzinfo=None)
        token_record.expires_at = naive_expiry
        await db_session.commit()

        FrozenDateTime.current = naive_expiry.replace(tzinfo=UTC)
        validated = await validate_refresh_token(db_session, refresh_token)
        failure = await classify_refresh_token_failure(db_session, refresh_token)

    assert validated is None
    assert failure == "expired"
