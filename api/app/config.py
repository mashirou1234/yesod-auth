"""Application configuration."""

import os
from functools import lru_cache

from app.oauth_providers import OAUTH_PROVIDER_CREDENTIAL_FIELDS, OAUTH_PROVIDER_CREDENTIAL_KEYS

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost:5173"
TRUE_VALUES = {"1", "true", "yes"}
FALSE_VALUES = {"0", "false", "no", ""}


def read_secret(name: str, default: str = "") -> str:
    """Read secret from Docker secrets or environment variable."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            return f.read().strip()
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

    # Environment
    TESTING: bool = parse_bool_env("TESTING", default=False)
    MOCK_OAUTH_ENABLED: bool = parse_bool_env("MOCK_OAUTH_ENABLED", default=False)

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
    TOKEN_REFRESH_MAX_RETRIES: int = int(os.getenv("TOKEN_REFRESH_MAX_RETRIES", "3"))

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

    # OAuth - GitHub
    GITHUB_CLIENT_ID: str = read_secret("github_client_id", "")
    GITHUB_CLIENT_SECRET: str = read_secret("github_client_secret", "")

    # OAuth - X (Twitter)
    X_CLIENT_ID: str = read_secret("x_client_id", "")
    X_CLIENT_SECRET: str = read_secret("x_client_secret", "")

    # OAuth - LinkedIn
    LINKEDIN_CLIENT_ID: str = read_secret("linkedin_client_id", "")
    LINKEDIN_CLIENT_SECRET: str = read_secret("linkedin_client_secret", "")

    # OAuth - Facebook
    FACEBOOK_CLIENT_ID: str = read_secret("facebook_client_id", "")
    FACEBOOK_CLIENT_SECRET: str = read_secret("facebook_client_secret", "")

    # OAuth - Slack
    SLACK_CLIENT_ID: str = read_secret("slack_client_id", "")
    SLACK_CLIENT_SECRET: str = read_secret("slack_client_secret", "")

    # OAuth - Twitch
    TWITCH_CLIENT_ID: str = read_secret("twitch_client_id", "")
    TWITCH_CLIENT_SECRET: str = read_secret("twitch_client_secret", "")

    # URLs
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # CORS
    _cors_origins, _cors_origins_using_default = resolve_cors_origins(os.getenv("CORS_ORIGINS"))
    CORS_ORIGINS: list[str] = _cors_origins
    CORS_ORIGINS_USING_DEFAULT: bool = _cors_origins_using_default

    def __init__(self) -> None:
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
            duplicate_message = ", ".join("/".join(providers) for providers in duplicate_provider_groups)
            raise ValueError(
                "OAuth provider client_id is duplicated across enabled providers. "
                f"Resolve duplicates for: {duplicate_message}."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
