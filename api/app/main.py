"""YESOD Auth - Main application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.auth import router as auth_router
from app.accounts import router as accounts_router
from app.sessions import router as sessions_router
from app.users import router as users_router
from app.metrics import router as metrics_router
from app.auth.rate_limit import limiter
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
    description="OAuth authentication API with Google & Discord support",
    version="2.0.0",
    lifespan=lifespan,
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
