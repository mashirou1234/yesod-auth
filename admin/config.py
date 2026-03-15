"""Admin configuration."""
import os
from typing import Protocol


def read_secret(name: str, default: str = "") -> str:
    """Read secret from Docker secrets or environment variable."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    return os.getenv(name.upper(), default)


class Settings:
    # Use sync driver (psycopg2) for Streamlit
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://yesod_user:yesod_password@localhost:5432/yesod"
    )
    VALKEY_URL: str = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD: str = read_secret("admin_password", "admin")
    
    # Environment indicator (empty = production, otherwise shows badge)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "")
    
    # Session persistence (hours)
    SESSION_EXPIRY_HOURS: int = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))
    # SameSite(None) is only valid when Secure=true.
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    # Empty means "use framework default" and emit a warning for visibility.
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "").strip()

    # Default language (en, ja, fr, ko, de)
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")


settings = Settings()


class WarningLogger(Protocol):
    def warning(self, msg: str, *args) -> None: ...


def warn_if_session_cookie_samesite_unset(
    logger: WarningLogger,
    *,
    environment: str,
    session_cookie_samesite: str,
    session_cookie_secure: bool = True,
) -> bool:
    env_name = environment.strip() or "production"
    samesite = session_cookie_samesite.strip().lower()

    if not samesite:
        logger.warning(
            "SESSION_COOKIE_SAMESITE is not configured for admin session cookie (environment=%s)",
            env_name,
        )
        return True

    if samesite == "none" and not session_cookie_secure:
        logger.warning(
            "SESSION_COOKIE_SAMESITE=None requires SESSION_COOKIE_SECURE=true for admin session cookie (environment=%s)",
            env_name,
        )
        return True

    return False
