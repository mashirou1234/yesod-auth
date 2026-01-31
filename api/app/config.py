"""Application configuration."""

import os
from functools import lru_cache


def read_secret(name: str, default: str = "") -> str:
    """Read secret from Docker secrets or environment variable."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            return f.read().strip()
    return os.getenv(name.upper(), default)


class Settings:
    """Application settings."""

    # Environment
    TESTING: bool = os.getenv("TESTING", "").lower() in ("1", "true", "yes")
    MOCK_OAUTH_ENABLED: bool = os.getenv("MOCK_OAUTH_ENABLED", "").lower() in ("1", "true", "yes")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://yesod_user:yesod_password@localhost:5432/yesod"
    )

    # Valkey (Redis-compatible)
    VALKEY_URL: str = os.getenv("VALKEY_URL", "redis://localhost:6379/0")

    # JWT / Tokens
    JWT_SECRET: str = read_secret("jwt_secret", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_LIFETIME_SECONDS: int = int(os.getenv("ACCESS_TOKEN_LIFETIME_SECONDS", "900"))
    REFRESH_TOKEN_LIFETIME_DAYS: int = int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", "7"))

    # OAuth State TTL (seconds)
    OAUTH_STATE_TTL: int = int(os.getenv("OAUTH_STATE_TTL", "300"))

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

    # OAuth - Google
    GOOGLE_CLIENT_ID: str = read_secret("google_client_id", "")
    GOOGLE_CLIENT_SECRET: str = read_secret("google_client_secret", "")

    # OAuth - Discord
    DISCORD_CLIENT_ID: str = read_secret("discord_client_id", "")
    DISCORD_CLIENT_SECRET: str = read_secret("discord_client_secret", "")

    # URLs
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
