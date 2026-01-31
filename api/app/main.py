"""YESOD Auth - Main application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.accounts import router as accounts_router
from app.auth import router as auth_router
from app.auth.rate_limit import limiter
from app.config import get_settings
from app.metrics import router as metrics_router
from app.sessions import router as sessions_router
from app.users import router as users_router
from app.valkey import close_valkey

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    yield
    # Cleanup on shutdown
    await close_valkey()


app = FastAPI(
    title="YESOD Auth",
    description="""
## OAuth Authentication API

YESOD Auth provides a complete OAuth 2.0 authentication solution with support for multiple providers.

### Features

- 🔑 **OAuth 2.0** - Google and Discord authentication with PKCE support
- 🔄 **Token Rotation** - Secure refresh token rotation
- 👤 **User Management** - Profile updates, account linking
- 📊 **Audit Logging** - Complete authentication event tracking
- 🛡️ **Rate Limiting** - Protection against abuse

### Authentication Flow

1. Redirect user to `/api/v1/auth/{provider}` to start OAuth flow
2. User authenticates with the provider
3. Callback returns `access_token` and `refresh_token`
4. Use `access_token` in `Authorization: Bearer <token>` header
5. Refresh tokens via `/api/v1/auth/refresh` when expired

### Development Mode

Set `MOCK_OAUTH_ENABLED=1` to enable mock OAuth endpoints for testing without real OAuth providers.
    """,
    version="2.0.0",
    lifespan=lifespan,
    contact={
        "name": "YESOD Auth",
        "url": "https://github.com/mashirou1234/yesod-auth",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes - all under /api/v1
API_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(accounts_router, prefix=API_PREFIX)
app.include_router(sessions_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)

# Metrics at root level (for Prometheus scraping)
app.include_router(metrics_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "YESOD Auth",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
