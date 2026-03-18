"""Admin configuration."""
import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)


def read_secret(name: str, default: str = "") -> str:
    """Read secret from Docker secrets or environment variable."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    return os.getenv(name.upper(), default)


def read_bounded_float_env(
    name: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float value") from exc

    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def read_session_expiry_hours_env(
    name: str = "SESSION_EXPIRY_HOURS",
    *,
    default: int = 24,
) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw)
        if value <= 0:
            raise ValueError("must be positive")
    except ValueError:
        logger.warning(
            "%s is invalid (%r); using default value %d",
            name,
            raw,
            default,
        )
        return default
    return value


class Settings:
    # Use sync driver (psycopg2) for Streamlit
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://yesod_user:yesod_password@localhost:5432/yesod"
    )
    VALKEY_URL: str = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
    VALKEY_RECONNECT_WAIT_SECONDS: float = read_bounded_float_env(
        "VALKEY_RECONNECT_WAIT_SECONDS",
        default=0.2,
        minimum=0.05,
        maximum=30.0,
    )
    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD: str = read_secret("admin_password", "admin")
    
    # Environment indicator (empty = production, otherwise shows badge)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "")
    
    # Session persistence (hours)
    SESSION_EXPIRY_HOURS: int = read_session_expiry_hours_env()
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
