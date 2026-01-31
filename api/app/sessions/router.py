"""Session management router."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.db.session import get_db
from app.models import User, RefreshToken
from app.auth.jwt import get_current_user
from .schemas import SessionResponse, SessionListResponse, RevokeResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active sessions for current user."""
    result = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.user_id == current_user.id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        ).order_by(RefreshToken.created_at.desc())
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
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session."""
    result = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.id == session_id,
                RefreshToken.user_id == current_user.id,
                RefreshToken.is_revoked == False,
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found or already revoked"
        )
    
    session.is_revoked = True
    await db.commit()
    
    return RevokeResponse(
        message="Session revoked successfully",
        session_id=session_id,
    )


@router.delete("", response_model=RevokeResponse)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions for current user."""
    result = await db.execute(
        select(RefreshToken).where(
            and_(
                RefreshToken.user_id == current_user.id,
                RefreshToken.is_revoked == False,
            )
        )
    )
    sessions = result.scalars().all()
    
    for session in sessions:
        session.is_revoked = True
    
    await db.commit()
    
    return RevokeResponse(
        message=f"Revoked {len(sessions)} sessions",
        revoked_count=len(sessions),
    )
