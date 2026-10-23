"""OAuth provider registry definitions with deterministic order."""

from types import MappingProxyType

_OAUTH_PROVIDER_CREDENTIAL_MAP = MappingProxyType(
    {
        "google": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        "discord": ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET"),
        "github": ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"),
        "x": ("X_CLIENT_ID", "X_CLIENT_SECRET"),
        "linkedin": ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"),
        "facebook": ("FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET"),
        "slack": ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"),
        "twitch": ("TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"),
    }
)

# Keep provider initialization deterministic by sorting provider keys explicitly.
OAUTH_PROVIDER_ORDER: tuple[str, ...] = tuple(sorted(_OAUTH_PROVIDER_CREDENTIAL_MAP))
OAUTH_PROVIDER_CREDENTIAL_FIELDS = MappingProxyType(
    {provider: _OAUTH_PROVIDER_CREDENTIAL_MAP[provider] for provider in OAUTH_PROVIDER_ORDER}
)
OAUTH_PROVIDER_CREDENTIAL_KEYS: tuple[tuple[str, str], ...] = tuple(
    OAUTH_PROVIDER_CREDENTIAL_FIELDS[provider] for provider in OAUTH_PROVIDER_ORDER
)


def get_project_provider_credentials(settings, provider, *, project_id):
    """Environment credentials are a connection owned by the default project only."""
    from app.db.base import DEFAULT_PROJECT_ID

    if project_id != DEFAULT_PROJECT_ID:
        raise ValueError("No provider connection configured for this project")
    id_field, secret_field = OAUTH_PROVIDER_CREDENTIAL_FIELDS[provider]
    return getattr(settings, id_field, ""), getattr(settings, secret_field, "")
