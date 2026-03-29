"""Session management router."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditLogger, AuthEventType
from app.auth.jwt import get_current_user
from app.db.session import get_db
from app.models import RefreshToken, User

from .schemas import RevokeResponse, SessionListResponse, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])
SESSIONS_LIMIT_MAX = 1000
SESSIONS_LIMIT_EXCEEDED_CODE = "SESSIONS_LIMIT_EXCEEDED"


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract device info and IP address from request."""
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    limit: int = Query(
        100,
        ge=1,
        description="Maximum results",
        json_schema_extra={"maximum": SESSIONS_LIMIT_MAX},
    ),
    db: AsyncSession = Depends(get_db),
):
    """List all active sessions for current user."""
    if limit > SESSIONS_LIMIT_MAX:
        raise HTTPException(
            status_code=400,
            detail={
                "code": SESSIONS_LIMIT_EXCEEDED_CODE,
                "message": f"limit must be less than or equal to {SESSIONS_LIMIT_MAX}",
                "max_limit": SESSIONS_LIMIT_MAX,
            },
        )

    result = await db.execute(
        select(RefreshToken)
        .where(
            and_(
                RefreshToken.user_id == current_user.id,
                RefreshToken.is_revoked.is_(False),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        .order_by(RefreshToken.created_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                device_info=s.device_info,
                ip_address=s.ip_address,
                created_at=s.created_at,
                last_used_at=s.last_used_at,
                expires_at=s.expires_at,
            )
            for s in sessions
        ],
        total=len(sessions),
    )


@router.delete("/{session_id}", response_model=RevokeResponse)
async def revoke_session(
    request: Request,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session."""
    device_info, ip_address = _get_client_info(request)
    result = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.id == session_id,
                RefreshToken.user_id == current_user.id,
            )
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    already_revoked = session.is_revoked
    if not already_revoked:
        session.is_revoked = True
        await db.commit()

    await AuditLogger.log_event(
        db,
        AuthEventType.SESSION_REVOKED,
        current_user.id,
        {
            "audit_key": "session_id",
            "session_id": str(session_id),
            "already_revoked": already_revoked,
        },
        ip_address,
        device_info,
    )

    return RevokeResponse(
        message="Session revoked successfully",
        session_id=session_id,
    )


@router.delete("", response_model=RevokeResponse)
async def revoke_all_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions for current user."""
    device_info, ip_address = _get_client_info(request)
    result = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.user_id == current_user.id,
                RefreshToken.is_revoked.is_(False),
            )
        )
    )
    sessions = result.scalars().all()

    for session in sessions:
        session.is_revoked = True

    await db.commit()

    revoked_count = len(sessions)
    await AuditLogger.log_event(
        db,
        AuthEventType.ALL_SESSIONS_REVOKED,
        current_user.id,
        {
            "audit_key": "revoked_count",
            "revoked_count": revoked_count,
            "user_id": str(current_user.id),
        },
        ip_address,
        device_info,
    )

    return RevokeResponse(
        message=f"Revoked {revoked_count} sessions",
        revoked_count=revoked_count,
    )
