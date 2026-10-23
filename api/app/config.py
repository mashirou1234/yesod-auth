"""Application configuration."""

import os
from functools import lru_cache

from app.oauth_providers import OAUTH_PROVIDER_CREDENTIAL_FIELDS, OAUTH_PROVIDER_CREDENTIAL_KEYS

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost:5173"
TRUE_VALUES = {"1", "true", "yes"}
FALSE_VALUES = {"0", "false", "no", ""}
# A bounded guard against common mistakes, not an estimate of secret entropy.
COMMON_SECRET_PATTERNS = (
    "password",
    "passw0rd",
    "p@ssw0rd",
    "qwerty",
    "letmein",
    "changeme",
    "welcome123",
    "admin123",
    "1234567890",
    "0123456789",
    "9876543210",
    "abcdefghijklmnopqrstuvwxyz",
)


def read_secret(name: str, default: str = "") -> str:
    """Read a secret; files may end in one LF or CRLF, env values stay exact."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, newline="") as f:
            value = f.read()
        if value.endswith("\r\n"):
            return value[:-2]
        if value.endswith("\n"):
            return value[:-1]
        return value
    return os.getenv(name.upper(), default)


def resolve_cors_origins(raw_value: str | None) -> tuple[list[str], bool]:
    """Resolve CORS origins and whether default values are in use."""
    if raw_value is None or not raw_value.strip():
        return DEFAULT_CORS_ORIGINS.split(","), True

    raw_origins = [origin.strip() for origin in raw_value.split(",")]
    if any(not origin for origin in raw_origins):
        raise ValueError(
            "CORS_ORIGINS contains empty element. "
            "Set non-empty comma-separated values for CORS_ORIGINS."
        )

    # Normalize slash/case notation drift and deduplicate while preserving first-seen order.
    normalized_origins: list[str] = []
    seen_origins: set[str] = set()
    for origin in raw_origins:
        normalized_origin = origin.rstrip("/")
        canonical_key = normalized_origin.casefold()
        if canonical_key in seen_origins:
            continue
        seen_origins.add(canonical_key)
        normalized_origins.append(normalized_origin)

    return normalized_origins, False


def parse_bool_env(name: str, default: bool = False) -> bool:
    """Parse boolean environment variables with explicit invalid-value errors."""
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False

    allowed_values = "1,true,yes,0,false,no"
    raise ValueError(
        f"Invalid boolean value for {name}: raw={raw!r}, normalized={normalized!r}. "
        f"Allowed values: {allowed_values} (case-insensitive, surrounding whitespace is ignored)."
    )


class Settings:
    """Application settings."""

    def __init__(self) -> None:
        # Read at construction, so importing this module never freezes deployment state.
        self.RUNTIME_MODE = os.getenv("RUNTIME_MODE", "production").strip().lower()
        if self.RUNTIME_MODE not in {"development", "test", "production"}:
            raise ValueError("RUNTIME_MODE must be development, test, or production")
        self.TESTING = parse_bool_env("TESTING", default=self.RUNTIME_MODE == "test")
        self.MOCK_OAUTH_ENABLED = parse_bool_env("MOCK_OAUTH_ENABLED")
        self.DEBUG_OAUTH_ENABLED = parse_bool_env("DEBUG_OAUTH_ENABLED")
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://yesod_user:yesod_password@localhost:5432/yesod"
        )
        self.VALKEY_URL = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
        self.JWT_SECRET = read_secret(
            "jwt_secret", "" if self.RUNTIME_MODE == "production" else "development-only-jwt-secret"
        )
        self.JWT_ALGORITHM = "HS256"
        self.JWT_ISSUER = os.getenv("JWT_ISSUER", "yesod-auth").strip()
        self.JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "yesod-api").strip()
        if not self.JWT_ISSUER or not self.JWT_AUDIENCE:
            raise ValueError("JWT_ISSUER and JWT_AUDIENCE must be non-empty")
        for name, default in (
            ("ACCESS_TOKEN_LIFETIME_SECONDS", 900),
            ("REFRESH_TOKEN_LIFETIME_DAYS", 7),
            ("TOKEN_REFRESH_MAX_RETRIES", 3),
            ("OAUTH_STATE_TTL", 300),
            ("RATE_LIMIT_PER_MINUTE", 20),
        ):
            value = int(os.getenv(name, str(default)))
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            setattr(self, name, value)
        for keys in OAUTH_PROVIDER_CREDENTIAL_KEYS:
            for key in keys:
                setattr(self, key, read_secret(key.lower()))
        self.API_URL = os.getenv("API_URL", "http://localhost:8000")
        self.FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
        self.CORS_ORIGINS, self.CORS_ORIGINS_USING_DEFAULT = resolve_cors_origins(
            os.getenv("CORS_ORIGINS")
        )
        if self.RUNTIME_MODE == "production":
            secret = self.JWT_SECRET
            if (
                len(secret.encode()) < 32
                or len(set(secret)) < 12
                or any(character.isspace() for character in secret)
                or any(pattern in secret.casefold() for pattern in COMMON_SECRET_PATTERNS)
                or any(
                    marker in secret.lower()
                    for marker in (
                        "change-me",
                        "change_me",
                        "development",
                        "your-secret",
                        "example",
                    )
                )
            ):
                raise ValueError(
                    "JWT_SECRET must be randomly generated, non-default, and whitespace-free "
                    "(32+ bytes); the format and common-pattern checks failed"
                )
            for flag in ("TESTING", "MOCK_OAUTH_ENABLED", "DEBUG_OAUTH_ENABLED"):
                if getattr(self, flag):
                    raise ValueError(f"{flag} is forbidden in production")
        self._validate_oauth_provider_secrets()
        self._validate_oauth_provider_client_ids_are_unique()

    def _validate_oauth_provider_secrets(self) -> None:
        for client_id_key, client_secret_key in OAUTH_PROVIDER_CREDENTIAL_KEYS:
            client_id = str(getattr(self, client_id_key, "")).strip()
            client_secret = str(getattr(self, client_secret_key, "")).strip()
            if client_id and not client_secret:
                raise ValueError(
                    f"OAuth provider secret is empty. Set non-empty value for {client_secret_key}."
                )

    def _validate_oauth_provider_client_ids_are_unique(self) -> None:
        normalized_client_id_providers: dict[str, list[str]] = {}

        for provider, credential_keys in OAUTH_PROVIDER_CREDENTIAL_FIELDS.items():
            client_id_key, _ = credential_keys
            client_id = str(getattr(self, client_id_key, "")).strip()
            if not client_id:
                continue
            normalized = client_id.casefold()
            normalized_client_id_providers.setdefault(normalized, []).append(provider)

        duplicate_provider_groups = sorted(
            sorted(providers)
            for providers in normalized_client_id_providers.values()
            if len(providers) > 1
        )
        if duplicate_provider_groups:
            duplicate_message = ", ".join(
                "/".join(providers) for providers in duplicate_provider_groups
            )
            raise ValueError(
                "OAuth provider client_id is duplicated across enabled providers. "
                f"Resolve duplicates for: {duplicate_message}."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
