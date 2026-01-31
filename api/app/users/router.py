"""User management router."""
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.session import get_db
from app.models import User, UserProfile, UserEmail, DeletedUser
from app.auth.jwt import get_current_user
from .schemas import UserResponse, UserUpdateRequest, UserDeleteResponse

settings = get_settings()
router = APIRouter(prefix="/users", tags=["users"])

# Soft delete grace period (days)
SOFT_DELETE_GRACE_DAYS = 30


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile with OAuth accounts."""
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.emails),
            selectinload(User.oauth_accounts),
        )
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    return user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    # Reload user with profile
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.emails),
            selectinload(User.oauth_accounts),
        )
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    
    # Update profile (create if not exists)
    if not user.profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        user.profile = profile
    
    if update_data.display_name is not None:
        user.profile.display_name = update_data.display_name
    if update_data.avatar_url is not None:
        user.profile.avatar_url = update_data.avatar_url
    
    await db.commit()
    
    # Reload with all relationships
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.emails),
            selectinload(User.oauth_accounts),
        )
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    
    return user


@router.delete("/me", response_model=UserDeleteResponse)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete current user account.
    
    The account will be moved to deleted_users table and
    permanently purged after the grace period (30 days).
    
    During the grace period, the user cannot log in but
    data can be recovered by an administrator.
    """
    # Reload user with all relationships
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.emails),
            selectinload(User.oauth_accounts),
        )
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    
    user_id = user.id
    email = user.email or "unknown"
    display_name = user.display_name
    
    # Get OAuth providers for reference
    oauth_providers = [oa.provider for oa in user.oauth_accounts]
    
    # Create soft delete record
    deleted_user = DeletedUser(
        id=user_id,
        email_backup=email,
        display_name_backup=display_name,
        purge_at=datetime.now(timezone.utc) + timedelta(days=SOFT_DELETE_GRACE_DAYS),
        oauth_providers=json.dumps(oauth_providers) if oauth_providers else None,
    )
    db.add(deleted_user)
    
    # Delete user (cascades to profile, emails, oauth_accounts, refresh_tokens)
    await db.delete(user)
    await db.commit()
    
    return UserDeleteResponse(
        message=f"Account scheduled for deletion. Will be permanently removed after {SOFT_DELETE_GRACE_DAYS} days.",
        deleted_user_id=user_id,
        deleted_email=email,
    )
