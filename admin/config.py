"""Admin configuration."""
import logging
import os

logger = logging.getLogger(__name__)

# Keep aligned with the separately deployed API's bounded common-pattern guard.
# Passing these checks does not establish entropy or password uniqueness.
COMMON_SECRET_PATTERNS = (
    "password", "passw0rd", "p@ssw0rd", "qwerty", "letmein", "changeme",
    "welcome123", "admin123", "1234567890", "0123456789", "9876543210",
    "abcdefghijklmnopqrstuvwxyz",
)


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
    default: int = 1,
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
    def __init__(self) -> None:
        self.RUNTIME_MODE = os.getenv("RUNTIME_MODE", "production").strip().lower()
        if self.RUNTIME_MODE not in {"development", "test", "production"}:
            raise ValueError("RUNTIME_MODE must be development, test, or production")
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "postgresql+psycopg2://yesod_user:yesod_password@localhost:5432/yesod"
        )
        self.VALKEY_URL = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
        self.VALKEY_RECONNECT_WAIT_SECONDS = read_bounded_float_env(
            "VALKEY_RECONNECT_WAIT_SECONDS", default=0.2, minimum=0.05, maximum=30.0
        )
        self.ADMIN_USER = os.getenv("ADMIN_USER", "admin").strip()
        self.ADMIN_PASSWORD = read_secret(
            "admin_password", "" if self.RUNTIME_MODE == "production" else "admin"
        )
        if not self.ADMIN_USER:
            raise ValueError("ADMIN_USER must be non-empty")
        if self.RUNTIME_MODE == "production":
            password = self.ADMIN_PASSWORD
            if (
                len(password) < 16
                or len(set(password)) < 8
                or password.casefold() == self.ADMIN_USER.casefold()
                or any(pattern in password.casefold() for pattern in COMMON_SECRET_PATTERNS)
                or any(marker in password.lower() for marker in (
                    "change-me", "change_me", "development", "your-password", "example",
                ))
            ):
                raise ValueError(
                    "ADMIN_PASSWORD must be randomly generated and non-default (16+ characters); "
                    "the format and common-pattern checks failed"
                )
        self.SESSION_EXPIRY_HOURS = read_session_expiry_hours_env()
        if self.SESSION_EXPIRY_HOURS > 24:
            raise ValueError("SESSION_EXPIRY_HOURS must be at most 24")
        self.DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")


settings = Settings()
