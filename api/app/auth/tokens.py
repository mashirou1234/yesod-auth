"""Token management - Access tokens and Refresh tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import RefreshToken

settings = get_settings()


def create_access_token(user_id: str, email: str) -> str:
    """Create a short-lived access token (JWT)."""
    expire = datetime.now(UTC) + timedelta(seconds=settings.ACCESS_TOKEN_LIFETIME_SECONDS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def generate_refresh_token() -> str:
    """Generate a secure random refresh token."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Hash refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    device_info: str | None = None,
    ip_address: str | None = None,
) -> str:
    """Create and store a new refresh token."""
    token = generate_refresh_token()
    token_hash = hash_refresh_token(token)

    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_LIFETIME_DAYS)

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        device_info=device_info,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(refresh_token)
    await db.commit()

    return token


async def validate_refresh_token(
    db: AsyncSession,
    token: str,
) -> RefreshToken | None:
    """Validate refresh token and return the record if valid."""
    token_hash = hash_refresh_token(token)

    result = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.token_hash == token_hash,
                not RefreshToken.is_revoked,
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
    )
    return result.scalar_one_or_none()


async def rotate_refresh_token(
    db: AsyncSession,
    old_token: str,
    device_info: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, uuid.UUID] | None:
    """Rotate refresh token - revoke old, create new. Returns (new_token, user_id)."""
    old_record = await validate_refresh_token(db, old_token)
    if not old_record:
        return None

    # Revoke old token
    old_record.is_revoked = True
    old_record.last_used_at = datetime.now(UTC)

    # Create new token
    new_token = await create_refresh_token(
        db,
        old_record.user_id,
        device_info=device_info,
        ip_address=ip_address,
    )

    return new_token, old_record.user_id


async def revoke_refresh_token(db: AsyncSession, token: str) -> bool:
    """Revoke a specific refresh token."""
    record = await validate_refresh_token(db, token)
    if record:
        record.is_revoked = True
        await db.commit()
        return True
    return False


async def revoke_all_user_tokens(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Revoke all refresh tokens for a user. Returns count of revoked tokens."""
    result = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.user_id == user_id,
                not RefreshToken.is_revoked,
            )
        )
    )
    tokens = result.scalars().all()

    for token in tokens:
        token.is_revoked = True

    await db.commit()
    return len(tokens)
