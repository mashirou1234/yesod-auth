"""Auth router with security enhancements."""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.session import get_db
from app.models import User, OAuthAccount
from app.valkey import OAuthStateStore
from .jwt import get_current_user
from .tokens import (
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
)
from .oauth import GoogleOAuth, DiscordOAuth
from .pkce import generate_code_verifier, generate_code_challenge
from .rate_limit import limiter
from .schemas import (
    UserResponse,
    UserWithAccountsResponse,
    TokenPairResponse,
    RefreshTokenRequest,
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract device info and IP address from request."""
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


@router.get("/google")
@limiter.limit("10/minute")
async def google_login(request: Request):
    """Start Google OAuth flow with PKCE."""
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "google", code_verifier)
    
    redirect_uri = f"{settings.API_URL}/auth/google/callback"
    authorize_url = GoogleOAuth.get_authorize_url(
        redirect_uri, state, code_challenge
    )
    
    return RedirectResponse(url=authorize_url)


@router.get("/google/callback")
@limiter.limit("10/minute")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback."""
    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "google":
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    code_verifier = state_data.get("code_verifier")
    redirect_uri = f"{settings.API_URL}/auth/google/callback"
    
    # Exchange code for tokens
    token_data = await GoogleOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code")
    
    # Get user info
    user_info = await GoogleOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")
    
    # Find or create user
    user = await _find_or_create_user(
        db=db,
        provider="google",
        provider_user_id=user_info["id"],
        email=user_info["email"],
        display_name=user_info.get("name"),
        avatar_url=user_info.get("picture"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )
    
    # Create tokens
    device_info, ip_address = _get_client_info(request)
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(
        db, user.id, device_info, ip_address
    )
    
    # Redirect to frontend with tokens
    frontend_url = (
        f"{settings.FRONTEND_URL}/auth/callback"
        f"?access_token={access_token}&refresh_token={refresh_token}"
    )
    return RedirectResponse(url=frontend_url)


@router.get("/discord")
@limiter.limit("10/minute")
async def discord_login(request: Request):
    """Start Discord OAuth flow."""
    state = secrets.token_urlsafe(32)
    
    # Store state in Valkey (Discord doesn't support PKCE)
    await OAuthStateStore.save(state, "discord")
    
    redirect_uri = f"{settings.API_URL}/auth/discord/callback"
    authorize_url = DiscordOAuth.get_authorize_url(redirect_uri, state)
    
    return RedirectResponse(url=authorize_url)


@router.get("/discord/callback")
@limiter.limit("10/minute")
async def discord_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Discord OAuth callback."""
    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "discord":
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    redirect_uri = f"{settings.API_URL}/auth/discord/callback"
    
    # Exchange code for tokens
    token_data = await DiscordOAuth.exchange_code(code, redirect_uri)
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code")
    
    # Get user info
    user_info = await DiscordOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")
    
    # Find or create user
    user = await _find_or_create_user(
        db=db,
        provider="discord",
        provider_user_id=user_info["id"],
        email=user_info["email"],
        display_name=user_info.get("username"),
        avatar_url=user_info.get("avatar_url"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )
    
    # Create tokens
    device_info, ip_address = _get_client_info(request)
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(
        db, user.id, device_info, ip_address
    )
    
    # Redirect to frontend with tokens
    frontend_url = (
        f"{settings.FRONTEND_URL}/auth/callback"
        f"?access_token={access_token}&refresh_token={refresh_token}"
    )
    return RedirectResponse(url=frontend_url)


@router.post("/refresh", response_model=TokenPairResponse)
@limiter.limit("30/minute")
async def refresh_tokens(
    request: Request,
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token (with rotation)."""
    device_info, ip_address = _get_client_info(request)
    
    result = await rotate_refresh_token(
        db, body.refresh_token, device_info, ip_address
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    new_refresh_token, user_id = result
    
    # Get user for access token
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    access_token = create_access_token(str(user.id), user.email)
    
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserWithAccountsResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.oauth_accounts))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    return user


@router.post("/logout")
async def logout(
    body: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout - revoke the refresh token."""
    await revoke_refresh_token(db, body.refresh_token)
    return {"message": "Logged out successfully"}


@router.post("/logout/all")
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout from all devices - revoke all refresh tokens."""
    count = await revoke_all_user_tokens(db, current_user.id)
    return {"message": f"Logged out from {count} sessions"}


async def _find_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    display_name: str | None,
    avatar_url: str | None,
    access_token: str | None,
    refresh_token: str | None,
) -> User:
    """Find existing user or create new one."""
    
    # First, check if OAuth account exists
    result = await db.execute(
        select(OAuthAccount)
        .options(selectinload(OAuthAccount.user))
        .where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    oauth_account = result.scalar_one_or_none()
    
    if oauth_account:
        # Update tokens
        oauth_account.access_token = access_token
        oauth_account.refresh_token = refresh_token
        
        # Update user info
        user = oauth_account.user
        if display_name:
            user.display_name = display_name
        if avatar_url:
            user.avatar_url = avatar_url
        
        await db.commit()
        return user
    
    # Check if user with same email exists
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Link new OAuth account to existing user
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        db.add(oauth_account)
        
        # Update user info
        if display_name and not user.display_name:
            user.display_name = display_name
        if avatar_url:
            user.avatar_url = avatar_url
        
        await db.commit()
        return user
    
    # Create new user
    user = User(
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
    )
    db.add(user)
    await db.flush()
    
    # Create OAuth account
    oauth_account = OAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    db.add(oauth_account)
    
    await db.commit()
    await db.refresh(user)
    
    return user
