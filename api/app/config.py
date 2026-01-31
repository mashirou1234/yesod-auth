"""Application configuration."""
import os
from functools import lru_cache


def read_secret(name: str, default: str = "") -> str:
    """Read secret from Docker secrets or environment variable."""
    # Try Docker secrets first
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    # Fall back to environment variable
    return os.getenv(name.upper(), default)


class Settings:
    """Application settings."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://yesod_user:yesod_password@localhost:5432/yesod"
    )
    
    # JWT
    JWT_SECRET: str = read_secret("jwt_secret", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_LIFETIME_SECONDS: int = int(os.getenv("JWT_LIFETIME_SECONDS", "86400"))
    
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
        "CORS_ORIGINS", 
        "http://localhost:3000,http://localhost:5173"
    ).split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
