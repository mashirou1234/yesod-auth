"""OAuth account linking/unlinking router."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.auth.oauth import DiscordOAuth, GoogleOAuth
from app.auth.pkce import generate_code_challenge, generate_code_verifier
from app.config import get_settings
from app.db.session import get_db
from app.models import OAuthAccount, User
from app.valkey import OAuthStateStore

from .schemas import OAuthAccountResponse, UnlinkResponse

settings = get_settings()
router = APIRouter(prefix="/accounts", tags=["accounts"])

# API prefix for building URLs
API_V1_PREFIX = "/api/v1"


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
    if provider not in ["google", "discord"]:
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

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/settings/accounts?status=linked&provider=google"
    )


@router.get("/link/discord/callback")
async def discord_link_callback(
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

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/settings/accounts?status=linked&provider=discord"
    )


@router.delete("/{provider}", response_model=UnlinkResponse)
async def unlink_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlink an OAuth provider from current user."""
    if provider not in ["google", "discord"]:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # Count linked accounts
    count_result = await db.execute(
        select(func.count())
        .select_from(OAuthAccount)
        .where(OAuthAccount.user_id == current_user.id)
    )
    account_count = count_result.scalar()

    if account_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot unlink the last authentication method")

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

    return UnlinkResponse(
        message=f"Successfully unlinked {provider} account",
        provider=provider,
    )
