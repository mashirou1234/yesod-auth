"""User management router."""

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import AuditLogger, AuthEventType
from app.auth.jwt import get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.models import DeletedUser, OAuthAccount, User, UserProfile
from app.webhooks.emitter import WebhookEmitter

from .schemas import SyncFromProviderResponse, UserDeleteResponse, UserResponse, UserUpdateRequest

settings = get_settings()
router = APIRouter(prefix="/users", tags=["users"])

# Soft delete grace period (days)
SOFT_DELETE_GRACE_DAYS = 30


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract device info and IP address from request."""
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


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
    request: Request,
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    device_info, ip_address = _get_client_info(request)

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

    # Track changes for audit
    changes = {}

    # Update profile (create if not exists)
    if not user.profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        user.profile = profile

    if update_data.display_name is not None:
        if user.profile.display_name != update_data.display_name:
            changes["display_name"] = {
                "old": user.profile.display_name,
                "new": update_data.display_name,
            }
        user.profile.display_name = update_data.display_name
    if update_data.avatar_url is not None:
        if user.profile.avatar_url != update_data.avatar_url:
            changes["avatar_url"] = {"old": user.profile.avatar_url, "new": update_data.avatar_url}
        user.profile.avatar_url = update_data.avatar_url

    await db.commit()

    # Log profile update
    if changes:
        await AuditLogger.log_event(
            db,
            AuthEventType.PROFILE_UPDATED,
            user.id,
            {"changes": changes},
            ip_address,
            device_info,
        )

        # Emit webhook for profile update
        await WebhookEmitter.emit_user_event(
            "user.updated", user.id, {"changes": list(changes.keys())}
        )

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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete current user account.

    The account will be moved to deleted_users table and
    permanently purged after the grace period (30 days).

    During the grace period, the user cannot log in but
    data can be recovered by an administrator.
    """
    device_info, ip_address = _get_client_info(request)

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

    # Log account deletion before deleting
    await AuditLogger.log_event(
        db,
        AuthEventType.ACCOUNT_DELETED,
        user_id,
        {"email": email, "oauth_providers": oauth_providers},
        ip_address,
        device_info,
    )

    # Emit webhook for account deletion (before actual deletion)
    await WebhookEmitter.emit_user_event(
        "user.deleted", user_id, {"email": email, "oauth_providers": oauth_providers}
    )

    # Create soft delete record
    deleted_user = DeletedUser(
        id=user_id,
        email_backup=email,
        display_name_backup=display_name,
        purge_at=datetime.now(UTC) + timedelta(days=SOFT_DELETE_GRACE_DAYS),
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


@router.post("/me/sync-from-provider", response_model=SyncFromProviderResponse)
async def sync_profile_from_provider(
    request: Request,
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync user profile from OAuth provider.

    Restores display_name and avatar_url from the specified
    OAuth provider's stored information.
    """
    device_info, ip_address = _get_client_info(request)

    if provider not in ["google", "discord"]:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # Find OAuth account for this provider
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == current_user.id,
            OAuthAccount.provider == provider,
        )
    )
    oauth_account = result.scalar_one_or_none()

    if not oauth_account:
        raise HTTPException(status_code=404, detail=f"No {provider} account linked")

    if not oauth_account.provider_display_name and not oauth_account.provider_avatar_url:
        raise HTTPException(
            status_code=400,
            detail=f"No provider info stored for {provider}. Try re-logging in with {provider}.",
        )

    # Reload user with profile
    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == current_user.id)
    )
    user = result.scalar_one()

    # Create profile if not exists
    if not user.profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        user.profile = profile

    # Sync from provider
    updated_fields = []
    if oauth_account.provider_display_name:
        user.profile.display_name = oauth_account.provider_display_name
        updated_fields.append("display_name")
    if oauth_account.provider_avatar_url:
        user.profile.avatar_url = oauth_account.provider_avatar_url
        updated_fields.append("avatar_url")

    await db.commit()

    # Log profile sync
    await AuditLogger.log_event(
        db,
        AuthEventType.PROFILE_SYNCED,
        current_user.id,
        {"provider": provider, "updated_fields": updated_fields},
        ip_address,
        device_info,
    )

    return SyncFromProviderResponse(
        message=f"Profile synced from {provider}",
        provider=provider,
        updated_fields=updated_fields,
        display_name=oauth_account.provider_display_name,
        avatar_url=oauth_account.provider_avatar_url,
    )
