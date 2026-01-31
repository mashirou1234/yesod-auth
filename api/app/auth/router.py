"""Auth router."""
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.session import get_db
from app.models import User, OAuthAccount
from .jwt import create_access_token, get_current_user
from .oauth import GoogleOAuth, DiscordOAuth
from .schemas import UserResponse, TokenResponse, UserWithAccountsResponse

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

# Store OAuth states (in production, use Redis or similar)
oauth_states: dict[str, str] = {}


@router.get("/google")
async def google_login(request: Request):
    """Start Google OAuth flow."""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = "google"
    
    redirect_uri = f"{settings.API_URL}/auth/google/callback"
    authorize_url = GoogleOAuth.get_authorize_url(redirect_uri, state)
    
    return RedirectResponse(url=authorize_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback."""
    # Verify state
    if state not in oauth_states or oauth_states[state] != "google":
        raise HTTPException(status_code=400, detail="Invalid state")
    del oauth_states[state]
    
    redirect_uri = f"{settings.API_URL}/auth/google/callback"
    
    # Exchange code for tokens
    token_data = await GoogleOAuth.exchange_code(code, redirect_uri)
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
    
    # Create JWT
    token = create_access_token(str(user.id), user.email)
    
    # Redirect to frontend with token
    frontend_url = f"{settings.FRONTEND_URL}/auth/callback?token={token}"
    return RedirectResponse(url=frontend_url)


@router.get("/discord")
async def discord_login(request: Request):
    """Start Discord OAuth flow."""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = "discord"
    
    redirect_uri = f"{settings.API_URL}/auth/discord/callback"
    authorize_url = DiscordOAuth.get_authorize_url(redirect_uri, state)
    
    return RedirectResponse(url=authorize_url)


@router.get("/discord/callback")
async def discord_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Discord OAuth callback."""
    # Verify state
    if state not in oauth_states or oauth_states[state] != "discord":
        raise HTTPException(status_code=400, detail="Invalid state")
    del oauth_states[state]
    
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
    
    # Create JWT
    token = create_access_token(str(user.id), user.email)
    
    # Redirect to frontend with token
    frontend_url = f"{settings.FRONTEND_URL}/auth/callback?token={token}"
    return RedirectResponse(url=frontend_url)


@router.get("/me", response_model=UserWithAccountsResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info."""
    # Reload with OAuth accounts
    result = await db.execute(
        select(User)
        .options(selectinload(User.oauth_accounts))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    return user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout (client should discard the token)."""
    return {"message": "Logged out successfully"}


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
