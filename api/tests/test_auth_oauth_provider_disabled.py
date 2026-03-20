"""OAuth provider disabled behavior tests."""

import importlib

import pytest

auth_router_module = importlib.import_module("app.auth.router")

PROVIDER_CREDENTIAL_FIELDS = {
    "google": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
    "discord": ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET"),
    "github": ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"),
    "x": ("X_CLIENT_ID", "X_CLIENT_SECRET"),
    "linkedin": ("LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"),
    "facebook": ("FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET"),
    "slack": ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"),
    "twitch": ("TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"),
}


@pytest.mark.parametrize("provider", list(PROVIDER_CREDENTIAL_FIELDS.keys()))
def test_oauth_provider_disabled_raises_503(monkeypatch, provider: str):
    """Disabled provider must raise stable 503 contract."""
    client_id_field, client_secret_field = PROVIDER_CREDENTIAL_FIELDS[provider]
    monkeypatch.setattr(auth_router_module.settings, client_id_field, "")
    monkeypatch.setattr(auth_router_module.settings, client_secret_field, "")

    with pytest.raises(auth_router_module.HTTPException) as exc_info:
        auth_router_module._ensure_provider_enabled(provider)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        f"OAuth provider '{provider}' is disabled. "
        f"Configure {client_id_field} and {client_secret_field}."
    )


def test_oauth_unknown_provider_raises_400():
    """Unknown provider input must return stable 400 contract."""
    with pytest.raises(auth_router_module.HTTPException) as exc_info:
        auth_router_module._ensure_provider_enabled("unknown")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Unsupported OAuth provider 'unknown'."


def test_oauth_unknown_provider_normalizes_case_before_400():
    """Unknown mixed-case provider input should keep stable detail."""
    with pytest.raises(auth_router_module.HTTPException) as exc_info:
        auth_router_module._ensure_provider_enabled("UnKnown")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Unsupported OAuth provider 'unknown'."
