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
from app.audit import AuditLogger, AuthEventType
from .jwt import get_current_user
from .tokens import (
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
)
from .oauth import GoogleOAuth, DiscordOAuth
from .pkce import generate_code_verifier, generate_code_challenge
from .rate_limit import limiter
from .schemas import (
    TokenPairResponse,
    RefreshTokenRequest,
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

# API prefix for building URLs
API_V1_PREFIX = "/api/v1"


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
    
    redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/auth/google/callback"
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
    device_info, ip_address = _get_client_info(request)
    
    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "google":
        await AuditLogger.log_login(
            db, None, "google", False, ip_address, device_info, "Invalid state"
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    code_verifier = state_data.get("code_verifier")
    redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/auth/google/callback"
    
    # Exchange code for tokens
    token_data = await GoogleOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        await AuditLogger.log_login(
            db, None, "google", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")
    
    # Get user info
    user_info = await GoogleOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        await AuditLogger.log_login(
            db, None, "google", False, ip_address, device_info, "Failed to get user info"
        )
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
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(
        db, user.id, device_info, ip_address
    )
    
    # Log successful login
    await AuditLogger.log_login(db, user.id, "google", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id,
        {"provider": "google"}, ip_address, device_info
    )
    
    # In development, redirect to debug page to show tokens
    # In production, redirect to frontend
    if settings.FRONTEND_URL.startswith("http://localhost"):
        return RedirectResponse(
            url=f"{settings.API_URL}{API_V1_PREFIX}/auth/debug-tokens"
            f"?access_token={access_token}&refresh_token={refresh_token}"
        )
    
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
    
    redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/auth/discord/callback"
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
    device_info, ip_address = _get_client_info(request)
    
    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "discord":
        await AuditLogger.log_login(
            db, None, "discord", False, ip_address, device_info, "Invalid state"
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    redirect_uri = f"{settings.API_URL}{API_V1_PREFIX}/auth/discord/callback"
    
    # Exchange code for tokens
    token_data = await DiscordOAuth.exchange_code(code, redirect_uri)
    if not token_data:
        await AuditLogger.log_login(
            db, None, "discord", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")
    
    # Get user info
    user_info = await DiscordOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        await AuditLogger.log_login(
            db, None, "discord", False, ip_address, device_info, "Failed to get user info"
        )
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
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(
        db, user.id, device_info, ip_address
    )
    
    # Log successful login
    await AuditLogger.log_login(db, user.id, "discord", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id,
        {"provider": "discord"}, ip_address, device_info
    )
    
    # In development, redirect to debug page to show tokens
    # In production, redirect to frontend
    if settings.FRONTEND_URL.startswith("http://localhost"):
        return RedirectResponse(
            url=f"{settings.API_URL}{API_V1_PREFIX}/auth/debug-tokens"
            f"?access_token={access_token}&refresh_token={refresh_token}"
        )
    
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
        await AuditLogger.log_event(
            db, AuthEventType.TOKEN_REFRESH_FAILED, None,
            {"reason": "Invalid or expired token"}, ip_address, device_info
        )
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
    
    # Log token refresh
    await AuditLogger.log_event(
        db, AuthEventType.TOKEN_REFRESH, user.id,
        None, ip_address, device_info
    )
    
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(
    request: Request,
    body: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout - revoke the refresh token."""
    device_info, ip_address = _get_client_info(request)
    
    await revoke_refresh_token(db, body.refresh_token)
    
    # Log logout
    await AuditLogger.log_event(
        db, AuthEventType.LOGOUT, current_user.id,
        None, ip_address, device_info
    )
    
    return {"message": "Logged out successfully"}


@router.get("/debug-tokens")
async def debug_tokens(access_token: str, refresh_token: str):
    """Debug endpoint to display tokens after OAuth login.
    
    Only use in development!
    """
    from fastapi.responses import HTMLResponse
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>YESOD Auth - Login Success</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   max-width: 800px; margin: 50px auto; padding: 20px; }}
            h1 {{ color: #2563eb; }}
            .token-box {{ background: #f3f4f6; padding: 15px; border-radius: 8px; 
                         margin: 10px 0; word-break: break-all; font-family: monospace; }}
            .label {{ font-weight: bold; color: #374151; margin-bottom: 5px; }}
            button {{ background: #2563eb; color: white; border: none; padding: 10px 20px;
                     border-radius: 5px; cursor: pointer; margin: 5px; }}
            button:hover {{ background: #1d4ed8; }}
            .success {{ color: #059669; }}
        </style>
    </head>
    <body>
        <h1>✅ Login Successful!</h1>
        <p>Copy these tokens to use in the Admin API Test console:</p>
        
        <div class="label">Access Token:</div>
        <div class="token-box" id="access">{access_token}</div>
        <button onclick="copyToken('access')">📋 Copy Access Token</button>
        
        <div class="label" style="margin-top: 20px;">Refresh Token:</div>
        <div class="token-box" id="refresh">{refresh_token}</div>
        <button onclick="copyToken('refresh')">📋 Copy Refresh Token</button>
        
        <p style="margin-top: 30px;">
            <a href="http://localhost:8501">← Back to Admin Dashboard</a>
        </p>
        
        <script>
            function copyToken(id) {{
                const text = document.getElementById(id).innerText;
                navigator.clipboard.writeText(text);
                alert('Copied to clipboard!');
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# =============================================================================
# Mock OAuth Endpoints (Development Only)
# =============================================================================

@router.get("/mock/login", include_in_schema=True, tags=["mock-oauth"])
async def mock_login(
    request: Request,
    user: str = "alice",
    provider: str = "google",
    db: AsyncSession = Depends(get_db),
):
    """Mock OAuth login for development/testing.
    
    Bypasses real OAuth flow and creates a user directly.
    Only available when MOCK_OAUTH_ENABLED=1.
    
    Available mock users: alice, bob, charlie
    Available providers: google, discord
    """
    from .mock_oauth import is_mock_oauth_enabled, get_mock_user
    
    if not settings.MOCK_OAUTH_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Mock OAuth is disabled. Set MOCK_OAUTH_ENABLED=1 to enable."
        )
    
    if provider not in ["google", "discord"]:
        raise HTTPException(status_code=400, detail="Provider must be 'google' or 'discord'")
    
    device_info, ip_address = _get_client_info(request)
    mock_user = get_mock_user(user)
    
    # Get user info in provider format
    if provider == "google":
        user_info = mock_user.to_google_format()
        display_name = user_info.get("name")
        avatar_url = user_info.get("picture")
    else:
        user_info = mock_user.to_discord_format()
        display_name = user_info.get("username")
        avatar_url = user_info.get("avatar_url")
    
    # Find or create user
    db_user = await _find_or_create_user(
        db=db,
        provider=provider,
        provider_user_id=user_info["id"],
        email=user_info["email"],
        display_name=display_name,
        avatar_url=avatar_url,
        access_token="mock-access-token",
        refresh_token="mock-refresh-token",
    )
    
    # Create tokens
    access_token = create_access_token(str(db_user.id), db_user.email)
    refresh_token = await create_refresh_token(
        db, db_user.id, device_info, ip_address
    )
    
    # Log mock login
    await AuditLogger.log_login(db, db_user.id, f"mock-{provider}", True, ip_address, device_info)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "mock_user": user,
        "provider": provider,
        "user_id": str(db_user.id),
        "email": db_user.email,
    }


@router.get("/mock/users", include_in_schema=True, tags=["mock-oauth"])
async def list_mock_users():
    """List available mock users for testing.
    
    Only available when MOCK_OAUTH_ENABLED=1.
    """
    from .mock_oauth import MOCK_USERS
    
    if not settings.MOCK_OAUTH_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Mock OAuth is disabled. Set MOCK_OAUTH_ENABLED=1 to enable."
        )
    
    return {
        "mock_users": {
            name: {
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
            }
            for name, user in MOCK_USERS.items()
        },
        "usage": "GET /api/v1/auth/mock/login?user=alice&provider=google",
    }


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
    from app.models import UserProfile, UserEmail
    
    # First, check if OAuth account exists
    result = await db.execute(
        select(OAuthAccount)
        .options(
            selectinload(OAuthAccount.user)
            .selectinload(User.profile),
            selectinload(OAuthAccount.user)
            .selectinload(User.emails),
        )
        .where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    oauth_account = result.scalar_one_or_none()
    
    if oauth_account:
        # Update tokens and provider info
        oauth_account.access_token = access_token
        oauth_account.refresh_token = refresh_token
        oauth_account.provider_display_name = display_name
        oauth_account.provider_avatar_url = avatar_url
        oauth_account.provider_email = email
        
        # Don't auto-update user profile - let user control their profile
        user = oauth_account.user
        
        await db.commit()
        return user
    
    # Check if user with same email exists
    result = await db.execute(
        select(UserEmail)
        .options(
            selectinload(UserEmail.user)
            .selectinload(User.profile),
            selectinload(UserEmail.user)
            .selectinload(User.emails),
        )
        .where(UserEmail.email == email)
    )
    user_email = result.scalar_one_or_none()
    
    if user_email:
        user = user_email.user
        # Link new OAuth account to existing user
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_display_name=display_name,
            provider_avatar_url=avatar_url,
            provider_email=email,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        db.add(oauth_account)
        
        # Update user profile only if empty
        if user.profile:
            if display_name and not user.profile.display_name:
                user.profile.display_name = display_name
            if avatar_url and not user.profile.avatar_url:
                user.profile.avatar_url = avatar_url
        
        await db.commit()
        return user
    
    # Create new user with profile and email
    user = User()
    db.add(user)
    await db.flush()
    
    # Create profile with provider info
    profile = UserProfile(
        user_id=user.id,
        display_name=display_name,
        avatar_url=avatar_url,
    )
    db.add(profile)
    
    # Create email
    user_email = UserEmail(
        user_id=user.id,
        email=email,
        is_primary=True,
    )
    db.add(user_email)
    
    # Create OAuth account with provider info
    oauth_account = OAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_display_name=display_name,
        provider_avatar_url=avatar_url,
        provider_email=email,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    db.add(oauth_account)
    
    await db.commit()
    
    # Reload with relationships
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.emails),
        )
        .where(User.id == user.id)
    )
    user = result.scalar_one()
    
    return user
