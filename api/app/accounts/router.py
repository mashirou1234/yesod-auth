"""OAuth account linking/unlinking router."""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditLogger, AuthEventType
from app.auth.jwt import get_current_user
from app.auth.oauth import DiscordOAuth, GoogleOAuth
from app.auth.pkce import generate_code_challenge, generate_code_verifier
from app.config import get_settings
from app.db.session import get_db
from app.models import OAuthAccount, User
from app.valkey import OAuthStateStore

from .schemas import (
    OAuthAccountResponse,
    SUPPORTED_ACCOUNT_PROVIDERS,
    UNLINK_LAST_AUTH_METHOD_ERROR_DETAIL,
    UnlinkResponse,
)

settings = get_settings()
router = APIRouter(prefix="/accounts", tags=["accounts"])

# API prefix for building URLs
API_V1_PREFIX = "/api/v1"


def _get_request_id(request: Request | None) -> str:
    """Extract request-id header or generate a fallback ID."""
    if request is None:
        return str(uuid.uuid4())
    request_id = request.headers.get("X-Request-Id")
    if request_id:
        return request_id
    return str(uuid.uuid4())


def _build_audit_actor(actor_id: str | None) -> str:
    """Build actor value with stable fallback."""
    if isinstance(actor_id, str) and actor_id.strip():
        return actor_id
    return "unknown-actor"


def _build_audit_target(provider: str, provider_user_id: str | None) -> str:
    """Build target value with stable fallback."""
    if isinstance(provider_user_id, str) and provider_user_id.strip():
        return f"oauth-account:{provider}:{provider_user_id}"
    return f"oauth-account:{provider}:unknown-target"


def _get_client_info(request: Request | None) -> tuple[str | None, str | None]:
    """Extract device info and IP address from request."""
    if request is None:
        return None, None
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


@router.get("", response_model=list[OAuthAccountResponse])
async def list_linked_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all OAuth accounts linked to current user."""
    result = await db.execute(select(OAuthAccount).where(OAuthAccount.user_id == current_user.id))
    accounts = result.scalars().all()
    return accounts


@router.get("/link/{provider}")
async def start_link_account(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Start OAuth flow to link a new provider to existing account."""
    if provider not in SUPPORTED_ACCOUNT_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    state = secrets.token_urlsafe(32)

    # Store state with user_id for linking
    state_data = {
        "provider": provider,
        "action": "link",
        "user_id": str(current_user.id),
    }

    if provider == "google":
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state_data["code_verifier"] = code_verifier

        await OAuthStateStore.save_with_data(state, state_data)

        redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/accounts/link/google/callback"
        authorize_url = GoogleOAuth.get_authorize_url(redirect_uri, state, code_challenge)
    else:
        await OAuthStateStore.save_with_data(state, state_data)

        redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/accounts/link/discord/callback"
        authorize_url = DiscordOAuth.get_authorize_url(redirect_uri, state)

    return RedirectResponse(url=authorize_url)


@router.get("/link/google/callback")
async def google_link_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback for account linking."""
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("action") != "link":
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    user_id = state_data.get("user_id")
    code_verifier = state_data.get("code_verifier")

    redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/accounts/link/google/callback"
    token_data = await GoogleOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    user_info = await GoogleOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Check if this OAuth account is already linked to another user
    existing = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == user_info["id"],
        )
    )
    existing_account = existing.scalar_one_or_none()

    if existing_account:
        if str(existing_account.user_id) == user_id:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/settings/accounts?status=already_linked"
            )
        raise HTTPException(
            status_code=400, detail="This account is already linked to another user"
        )

    # Create new OAuth account link
    oauth_account = OAuthAccount(
        user_id=user_id,
        provider="google",
        provider_user_id=user_info["id"],
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )
    db.add(oauth_account)
    await db.commit()

    device_info, ip_address = _get_client_info(request)
    await AuditLogger.log_event(
        db,
        AuthEventType.ACCOUNT_LINKED,
        oauth_account.user_id,
        {
            "provider": "google",
            "provider_user_id": user_info.get("id"),
            "request_id": _get_request_id(request),
            "actor": _build_audit_actor(user_id),
            "target": _build_audit_target("google", user_info.get("id")),
        },
        ip_address,
        device_info,
    )

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/settings/accounts?status=linked&provider=google"
    )


@router.get("/link/discord/callback")
async def discord_link_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Discord OAuth callback for account linking."""
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("action") != "link":
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    user_id = state_data.get("user_id")

    redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/accounts/link/discord/callback"
    token_data = await DiscordOAuth.exchange_code(code, redirect_uri)
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    user_info = await DiscordOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Check if this OAuth account is already linked to another user
    existing = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "discord",
            OAuthAccount.provider_user_id == user_info["id"],
        )
    )
    existing_account = existing.scalar_one_or_none()

    if existing_account:
        if str(existing_account.user_id) == user_id:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/settings/accounts?status=already_linked"
            )
        raise HTTPException(
            status_code=400, detail="This account is already linked to another user"
        )

    # Create new OAuth account link
    oauth_account = OAuthAccount(
        user_id=user_id,
        provider="discord",
        provider_user_id=user_info["id"],
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )
    db.add(oauth_account)
    await db.commit()

    device_info, ip_address = _get_client_info(request)
    await AuditLogger.log_event(
        db,
        AuthEventType.ACCOUNT_LINKED,
        oauth_account.user_id,
        {
            "provider": "discord",
            "provider_user_id": user_info.get("id"),
            "request_id": _get_request_id(request),
            "actor": _build_audit_actor(user_id),
            "target": _build_audit_target("discord", user_info.get("id")),
        },
        ip_address,
        device_info,
    )

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/settings/accounts?status=linked&provider=discord"
    )


@router.delete("/{provider}", response_model=UnlinkResponse)
async def unlink_account(
    request: Request,
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlink an OAuth provider from current user."""
    if provider not in SUPPORTED_ACCOUNT_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # Count linked accounts
    count_result = await db.execute(
        select(func.count())
        .select_from(OAuthAccount)
        .where(OAuthAccount.user_id == current_user.id)
    )
    account_count = count_result.scalar()

    if account_count <= 1:
        raise HTTPException(status_code=400, detail=UNLINK_LAST_AUTH_METHOD_ERROR_DETAIL)

    # Find and delete the OAuth account
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == current_user.id,
            OAuthAccount.provider == provider,
        )
    )
    oauth_account = result.scalar_one_or_none()

    if not oauth_account:
        raise HTTPException(status_code=404, detail=f"No {provider} account linked")

    await db.delete(oauth_account)
    await db.commit()

    device_info, ip_address = _get_client_info(request)
    await AuditLogger.log_event(
        db,
        AuthEventType.ACCOUNT_UNLINKED,
        current_user.id,
        {
            "provider": provider,
            "provider_user_id": oauth_account.provider_user_id,
            "request_id": _get_request_id(request),
            "actor": _build_audit_actor(str(current_user.id)),
            "target": _build_audit_target(provider, oauth_account.provider_user_id),
        },
        ip_address,
        device_info,
    )

    return UnlinkResponse(
        message=f"Successfully unlinked {provider} account",
        provider=provider,
    )
