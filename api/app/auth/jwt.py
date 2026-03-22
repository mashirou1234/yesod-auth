"""JWT token handling and user authentication."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import AuditLogger, AuthEventType
from app.config import get_settings
from app.db.session import get_db
from app.models import User

from .tokens import decode_access_token

settings = get_settings()
security = HTTPBearer(auto_error=False)

MISSING_BEARER_TOKEN_DETAIL = "Not authenticated"
MISSING_BEARER_TOKEN_CODE = "missing_bearer_token"
INVALID_TOKEN_HEADER_CODE = "invalid_token_header"
INVALID_TOKEN_HEADER_MESSAGE = "Invalid token header"


def _missing_bearer_token_exception() -> HTTPException:
    """Return a fixed auth error for missing Authorization bearer token."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": MISSING_BEARER_TOKEN_CODE,
            "message": MISSING_BEARER_TOKEN_DETAIL,
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract device info and IP address from request."""
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


def _get_token_header_fields(token: str) -> list[str]:
    """Return sorted JWT header field names or an empty list on parse failure."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return []
    if not isinstance(header, dict):
        return []
    return sorted(str(key) for key in header.keys())


def _token_has_kid(token: str) -> bool:
    """Check whether JWT header contains a non-empty `kid` field."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return True
    if not isinstance(header, dict):
        return False
    kid = header.get("kid")
    return isinstance(kid, str) and bool(kid.strip())


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user."""
    if credentials is None:
        raise _missing_bearer_token_exception()

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_header_fields = _get_token_header_fields(token)
    if not _token_has_kid(token):
        device_info, ip_address = _get_client_info(request)
        await AuditLogger.log_event(
            db,
            AuthEventType.LOGIN_FAILED,
            details={
                "reason": INVALID_TOKEN_HEADER_CODE,
                "token_header_fields": token_header_fields,
            },
            ip_address=ip_address,
            user_agent=device_info,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": INVALID_TOKEN_HEADER_CODE,
                "message": INVALID_TOKEN_HEADER_MESSAGE,
                "token_header_fields": token_header_fields,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.emails),
        )
        .where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
