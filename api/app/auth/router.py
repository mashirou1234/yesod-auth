"""Auth router with security enhancements."""

import logging
import secrets
import uuid
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import AuditLogger, AuthEventType
from app.config import get_settings
from app.db.session import get_db
from app.metrics import record_oauth_failure_metric
from app.models import OAuthAccount, User
from app.oauth_providers import (
    OAUTH_PROVIDER_CREDENTIAL_FIELDS,
    OAUTH_PROVIDER_ORDER,
)
from app.valkey import OAuthStateStore
from app.webhooks.emitter import WebhookEmitter

from .jwt import get_current_user
from .oauth import (
    DiscordOAuth,
    FacebookOAuth,
    GitHubOAuth,
    GoogleOAuth,
    LinkedInOAuth,
    SlackOAuth,
    TwitchOAuth,
    XOAuth,
)
from .pkce import generate_code_challenge, generate_code_verifier
from .rate_limit import limiter
from .schemas import (
    RefreshTokenRequest,
    TokenPairResponse,
)
from .tokens import (
    classify_refresh_token_failure,
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# API prefix for building URLs
API_V1_PREFIX = "/api/v1"


def _log_provider_registry_order() -> None:
    """Emit provider registry initialization order for diagnostics."""
    logger.info(
        "OAuth provider registry initialized in deterministic order: %s",
        " -> ".join(OAUTH_PROVIDER_ORDER),
    )


_log_provider_registry_order()
KNOWN_OAUTH_CALLBACK_ERROR_CODES = {
    "access_denied",
    "invalid_request",
    "invalid_client",
    "invalid_grant",
    "unauthorized_client",
    "unsupported_grant_type",
    "invalid_scope",
    "server_error",
    "temporarily_unavailable",
}


def _normalize_oauth_provider(provider: str) -> str:
    """Normalize provider input for stable validation."""
    return provider.strip().lower()


def _validate_supported_oauth_provider(provider: str) -> str:
    """Return normalized provider or raise stable 400 contract."""
    normalized_provider = _normalize_oauth_provider(provider)
    if normalized_provider not in OAUTH_PROVIDER_CREDENTIAL_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider '{normalized_provider}'.",
        )
    return normalized_provider


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract device info and IP address from request."""
    device_info = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    return device_info, ip_address


def _get_request_id(request: Request) -> str:
    """Extract request-id header or generate a fallback ID."""
    request_id = request.headers.get("X-Request-Id")
    if request_id:
        return request_id
    return str(uuid.uuid4())


def _invalid_state_reason(request: Request) -> str:
    """Build a fixed invalid-state reason format for audit logs."""
    return f"Invalid state [request-id={_get_request_id(request)}]"


def _normalize_callback_url(url: str) -> str:
    """Normalize callback URL by dropping only trailing slash and query/fragment."""
    parsed = urlsplit(url)
    path = parsed.path
    if path.endswith("/") and path != "/":
        path = path[:-1]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _build_oauth_redirect_uri(provider: str) -> str:
    """Build canonical OAuth redirect URI for provider callback."""
    return f"{settings.API_URL.rstrip('/')}{API_V1_PREFIX}/auth/{provider}/callback"


def _record_unknown_oauth_error_code_metric(provider: str, error_code: str) -> None:
    """Record metric only when provider returned an unclassified OAuth error code."""
    normalized_error_code = error_code.strip().lower()
    if normalized_error_code and normalized_error_code not in KNOWN_OAUTH_CALLBACK_ERROR_CODES:
        record_oauth_failure_metric(provider, "unknown_error_code")


async def _validate_callback_url_or_raise(
    *,
    request: Request,
    db: AsyncSession,
    provider: str,
    ip_address: str | None,
    device_info: str | None,
    expected_callback_url: str,
) -> None:
    """Validate callback URL with trailing-slash normalization."""
    actual_callback_url = str(request.url.replace(query="", fragment=""))
    normalized_expected = _normalize_callback_url(expected_callback_url)
    normalized_actual = _normalize_callback_url(actual_callback_url)
    if normalized_expected == normalized_actual:
        if expected_callback_url != actual_callback_url:
            logger.info(
                "OAuth callback URL normalized for provider=%s expected=%s actual=%s",
                provider,
                expected_callback_url,
                actual_callback_url,
            )
        return

    logger.warning(
        "OAuth callback URL mismatch for provider=%s expected=%s actual=%s normalized_expected=%s normalized_actual=%s",
        provider,
        expected_callback_url,
        actual_callback_url,
        normalized_expected,
        normalized_actual,
    )
    record_oauth_failure_metric(provider, "callback_url_mismatch")
    await AuditLogger.log_login(
        db, None, provider, False, ip_address, device_info, "Callback URL mismatch"
    )
    raise HTTPException(status_code=400, detail="OAuth callback URL mismatch")


def _ensure_provider_enabled(provider: str) -> None:
    """Ensure OAuth provider credentials exist before starting auth flow."""
    provider = _validate_supported_oauth_provider(provider)
    credential_fields = OAUTH_PROVIDER_CREDENTIAL_FIELDS.get(provider)
    assert credential_fields is not None

    client_id_field, client_secret_field = credential_fields
    client_id = getattr(settings, client_id_field, "")
    client_secret = getattr(settings, client_secret_field, "")

    if client_id and client_secret:
        return

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            f"OAuth provider '{provider}' is disabled. "
            f"Configure {client_id_field} and {client_secret_field}."
        ),
    )


@router.get("/google")
@limiter.limit("10/minute")
async def google_login(request: Request):
    """Start Google OAuth flow with PKCE."""
    _ensure_provider_enabled("google")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "google", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("google")
    authorize_url = GoogleOAuth.get_authorize_url(redirect_uri, state, code_challenge)

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
            db, None, "google", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("google")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="google",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

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
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "google", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "google"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "google"})

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
    """Start Discord OAuth flow with PKCE."""
    _ensure_provider_enabled("discord")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "discord", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("discord")
    authorize_url = DiscordOAuth.get_authorize_url(redirect_uri, state, code_challenge)

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
            db, None, "discord", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("discord")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="discord",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

    # Exchange code for tokens with PKCE verifier
    token_data = await DiscordOAuth.exchange_code(code, redirect_uri, code_verifier)
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
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "discord", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "discord"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "discord"})

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


@router.get("/github")
@limiter.limit("10/minute")
async def github_login(request: Request):
    """Start GitHub OAuth flow with PKCE."""
    _ensure_provider_enabled("github")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "github", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("github")
    authorize_url = GitHubOAuth.get_authorize_url(redirect_uri, state, code_challenge)

    return RedirectResponse(url=authorize_url)


@router.get("/github/callback")
@limiter.limit("10/minute")
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub OAuth callback."""
    device_info, ip_address = _get_client_info(request)

    if error:
        _record_unknown_oauth_error_code_metric("github", error)
        await AuditLogger.log_login(
            db, None, "github", False, ip_address, device_info, f"OAuth callback failed: {error}"
        )
        raise HTTPException(status_code=400, detail=f"OAuth callback failed: {error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "github":
        record_oauth_failure_metric("github", "invalid_state")
        await AuditLogger.log_login(
            db, None, "github", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("github")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="github",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

    # Exchange code for tokens
    token_data = await GitHubOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        record_oauth_failure_metric("github", "code_exchange_failed")
        await AuditLogger.log_login(
            db, None, "github", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    # Get user info
    user_info = await GitHubOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        record_oauth_failure_metric("github", "user_info_failed")
        await AuditLogger.log_login(
            db, None, "github", False, ip_address, device_info, "Failed to get user info"
        )
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Find or create user
    user = await _find_or_create_user(
        db=db,
        provider="github",
        provider_user_id=str(user_info["id"]),
        email=user_info["email"],
        display_name=user_info.get("name") or user_info.get("login"),
        avatar_url=user_info.get("avatar_url"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )

    # Create tokens
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "github", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "github"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "github"})

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


@router.get("/x")
@limiter.limit("10/minute")
async def x_login(request: Request):
    """Start X (Twitter) OAuth flow with PKCE."""
    _ensure_provider_enabled("x")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "x", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("x")
    authorize_url = XOAuth.get_authorize_url(redirect_uri, state, code_challenge)

    return RedirectResponse(url=authorize_url)


@router.get("/x/callback")
@limiter.limit("10/minute")
async def x_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle X (Twitter) OAuth callback."""
    device_info, ip_address = _get_client_info(request)

    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "x":
        await AuditLogger.log_login(
            db, None, "x", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("x")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="x",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

    # Exchange code for tokens
    token_data = await XOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        await AuditLogger.log_login(
            db, None, "x", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    # Get user info
    user_info = await XOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        await AuditLogger.log_login(
            db, None, "x", False, ip_address, device_info, "Failed to get user info"
        )
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # X doesn't provide email, generate placeholder
    username = user_info.get("username", "unknown")
    email = f"{username}@x.yesod-auth.local"

    # Find or create user
    user = await _find_or_create_user(
        db=db,
        provider="x",
        provider_user_id=user_info["id"],
        email=email,
        display_name=user_info.get("name") or username,
        avatar_url=user_info.get("profile_image_url"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )

    # Create tokens
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "x", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "x"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "x"})

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


@router.get("/linkedin")
@limiter.limit("10/minute")
async def linkedin_login(request: Request):
    """Start LinkedIn OAuth flow with PKCE."""
    _ensure_provider_enabled("linkedin")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "linkedin", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("linkedin")
    authorize_url = LinkedInOAuth.get_authorize_url(redirect_uri, state, code_challenge)

    return RedirectResponse(url=authorize_url)


@router.get("/linkedin/callback")
@limiter.limit("10/minute")
async def linkedin_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle LinkedIn OAuth callback."""
    device_info, ip_address = _get_client_info(request)

    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "linkedin":
        await AuditLogger.log_login(
            db, None, "linkedin", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("linkedin")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="linkedin",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

    # Exchange code for tokens
    token_data = await LinkedInOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        await AuditLogger.log_login(
            db, None, "linkedin", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    # Get user info
    user_info = await LinkedInOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        await AuditLogger.log_login(
            db, None, "linkedin", False, ip_address, device_info, "Failed to get user info"
        )
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Find or create user (LinkedIn uses OpenID Connect format)
    user = await _find_or_create_user(
        db=db,
        provider="linkedin",
        provider_user_id=user_info["sub"],
        email=user_info["email"],
        display_name=user_info.get("name"),
        avatar_url=user_info.get("picture"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )

    # Create tokens
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "linkedin", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "linkedin"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "linkedin"})

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


@router.get("/facebook")
@limiter.limit("10/minute")
async def facebook_login(request: Request):
    """Start Facebook OAuth flow with PKCE."""
    _ensure_provider_enabled("facebook")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "facebook", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("facebook")
    authorize_url = FacebookOAuth.get_authorize_url(redirect_uri, state, code_challenge)

    return RedirectResponse(url=authorize_url)


@router.get("/facebook/callback")
@limiter.limit("10/minute")
async def facebook_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Facebook OAuth callback."""
    device_info, ip_address = _get_client_info(request)

    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "facebook":
        await AuditLogger.log_login(
            db, None, "facebook", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("facebook")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="facebook",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

    # Exchange code for tokens
    token_data = await FacebookOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        await AuditLogger.log_login(
            db, None, "facebook", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    # Get user info
    user_info = await FacebookOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        await AuditLogger.log_login(
            db, None, "facebook", False, ip_address, device_info, "Failed to get user info"
        )
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Find or create user
    user = await _find_or_create_user(
        db=db,
        provider="facebook",
        provider_user_id=user_info["id"],
        email=user_info["email"],
        display_name=user_info.get("name"),
        avatar_url=user_info.get("picture", {}).get("data", {}).get("url"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )

    # Create tokens
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "facebook", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "facebook"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "facebook"})

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


@router.get("/slack")
@limiter.limit("10/minute")
async def slack_login(request: Request):
    """Start Slack OAuth flow with PKCE."""
    _ensure_provider_enabled("slack")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    nonce = secrets.token_urlsafe(16)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "slack", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("slack")
    authorize_url = SlackOAuth.get_authorize_url(redirect_uri, state, code_challenge, nonce)

    return RedirectResponse(url=authorize_url)


@router.get("/slack/callback")
@limiter.limit("10/minute")
async def slack_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Slack OAuth callback."""
    device_info, ip_address = _get_client_info(request)

    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "slack":
        await AuditLogger.log_login(
            db, None, "slack", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("slack")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="slack",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

    # Exchange code for tokens with PKCE verifier
    token_data = await SlackOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        await AuditLogger.log_login(
            db, None, "slack", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    # Get user info
    user_info = await SlackOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        await AuditLogger.log_login(
            db, None, "slack", False, ip_address, device_info, "Failed to get user info"
        )
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Find or create user (Slack uses OpenID Connect format with "sub")
    user = await _find_or_create_user(
        db=db,
        provider="slack",
        provider_user_id=user_info["sub"],
        email=user_info["email"],
        display_name=user_info.get("name"),
        avatar_url=user_info.get("picture"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )

    # Create tokens
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "slack", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "slack"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "slack"})

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


@router.get("/twitch")
@limiter.limit("10/minute")
async def twitch_login(request: Request):
    """Start Twitch OAuth flow with PKCE."""
    _ensure_provider_enabled("twitch")
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    nonce = secrets.token_urlsafe(16)

    # Store state with code_verifier in Valkey
    await OAuthStateStore.save(state, "twitch", code_verifier)

    redirect_uri = _build_oauth_redirect_uri("twitch")
    authorize_url = TwitchOAuth.get_authorize_url(redirect_uri, state, code_challenge, nonce)

    return RedirectResponse(url=authorize_url)


@router.get("/twitch/callback")
@limiter.limit("10/minute")
async def twitch_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Twitch OAuth callback."""
    device_info, ip_address = _get_client_info(request)

    # Verify and consume state
    state_data = await OAuthStateStore.get_and_delete(state)
    if not state_data or state_data.get("provider") != "twitch":
        await AuditLogger.log_login(
            db, None, "twitch", False, ip_address, device_info, _invalid_state_reason(request)
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = state_data.get("code_verifier")
    redirect_uri = _build_oauth_redirect_uri("twitch")
    await _validate_callback_url_or_raise(
        request=request,
        db=db,
        provider="twitch",
        ip_address=ip_address,
        device_info=device_info,
        expected_callback_url=redirect_uri,
    )

    # Exchange code for tokens with PKCE verifier
    token_data = await TwitchOAuth.exchange_code(code, redirect_uri, code_verifier)
    if not token_data:
        await AuditLogger.log_login(
            db, None, "twitch", False, ip_address, device_info, "Code exchange failed"
        )
        raise HTTPException(status_code=400, detail="Failed to exchange code")

    # Get user info
    user_info = await TwitchOAuth.get_user_info(token_data["access_token"])
    if not user_info:
        await AuditLogger.log_login(
            db, None, "twitch", False, ip_address, device_info, "Failed to get user info"
        )
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # Find or create user
    user = await _find_or_create_user(
        db=db,
        provider="twitch",
        provider_user_id=user_info["id"],
        email=user_info["email"],
        display_name=user_info.get("display_name") or user_info.get("login"),
        avatar_url=user_info.get("profile_image_url"),
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
    )

    # Create tokens
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = await create_refresh_token(db, user.id, device_info, ip_address)

    # Log successful login
    await AuditLogger.log_login(db, user.id, "twitch", True, ip_address, device_info)
    await AuditLogger.log_event(
        db, AuthEventType.LOGIN_SUCCESS, user.id, {"provider": "twitch"}, ip_address, device_info
    )

    # Emit webhook event
    await WebhookEmitter.emit_user_event("user.login", user.id, {"provider": "twitch"})

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

    result = await rotate_refresh_token(db, body.refresh_token, device_info, ip_address)

    if not result:
        token_status = await classify_refresh_token_failure(db, body.refresh_token)
        await AuditLogger.log_event(
            db,
            AuthEventType.TOKEN_REFRESH_FAILED,
            None,
            {"reason": "Invalid or expired token", "token_status": token_status},
            ip_address,
            device_info,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    new_refresh_token, user_id = result

    # Get user for access token
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_token = create_access_token(str(user.id), user.email)

    # Log token refresh
    await AuditLogger.log_event(
        db, AuthEventType.TOKEN_REFRESH, user.id, None, ip_address, device_info
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
        db, AuthEventType.LOGOUT, current_user.id, None, ip_address, device_info
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
    Available providers: google, discord, github, x, linkedin, facebook, slack, twitch
    """
    from .mock_oauth import get_mock_user

    if not settings.MOCK_OAUTH_ENABLED:
        raise HTTPException(
            status_code=403, detail="Mock OAuth is disabled. Set MOCK_OAUTH_ENABLED=1 to enable."
        )

    provider = _validate_supported_oauth_provider(provider)

    device_info, ip_address = _get_client_info(request)
    mock_user = get_mock_user(user)

    # Get user info in provider format
    if provider == "google":
        user_info = mock_user.to_google_format()
        display_name = user_info.get("name")
        avatar_url = user_info.get("picture")
    elif provider == "github":
        user_info = mock_user.to_github_format()
        display_name = user_info.get("name") or user_info.get("login")
        avatar_url = user_info.get("avatar_url")
    elif provider == "x":
        user_info = mock_user.to_x_format()
        display_name = user_info.get("name") or user_info.get("username")
        avatar_url = user_info.get("profile_image_url")
    elif provider == "linkedin":
        user_info = mock_user.to_linkedin_format()
        display_name = user_info.get("name")
        avatar_url = user_info.get("picture")
    elif provider == "facebook":
        user_info = mock_user.to_facebook_format()
        display_name = user_info.get("name")
        avatar_url = user_info.get("picture", {}).get("data", {}).get("url")
    elif provider == "slack":
        user_info = mock_user.to_slack_format()
        display_name = user_info.get("name")
        avatar_url = user_info.get("picture")
    elif provider == "twitch":
        user_info = mock_user.to_twitch_format()
        display_name = user_info.get("display_name") or user_info.get("login")
        avatar_url = user_info.get("profile_image_url")
    else:
        user_info = mock_user.to_discord_format()
        display_name = user_info.get("username")
        avatar_url = user_info.get("avatar_url")

    # Find or create user
    # LinkedIn uses "sub" instead of "id" (OpenID Connect)
    provider_user_id = str(user_info.get("sub") or user_info.get("id"))
    db_user = await _find_or_create_user(
        db=db,
        provider=provider,
        provider_user_id=provider_user_id,
        email=user_info["email"],
        display_name=display_name,
        avatar_url=avatar_url,
        access_token="mock-access-token",
        refresh_token="mock-refresh-token",
    )

    # Create tokens
    access_token = create_access_token(str(db_user.id), db_user.email)
    refresh_token = await create_refresh_token(db, db_user.id, device_info, ip_address)

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
            status_code=403, detail="Mock OAuth is disabled. Set MOCK_OAUTH_ENABLED=1 to enable."
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
    from app.models import UserEmail, UserProfile

    # First, check if OAuth account exists
    result = await db.execute(
        select(OAuthAccount)
        .options(
            selectinload(OAuthAccount.user).selectinload(User.profile),
            selectinload(OAuthAccount.user).selectinload(User.emails),
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
            selectinload(UserEmail.user).selectinload(User.profile),
            selectinload(UserEmail.user).selectinload(User.emails),
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

        # Emit webhook for OAuth account linked
        await WebhookEmitter.emit_user_event("user.oauth_linked", user.id, {"provider": provider})

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

    # Emit webhook for new user created
    await WebhookEmitter.emit_user_event(
        "user.created", user.id, {"provider": provider, "email": email}
    )

    return user
