"""OAuth provider disabled behavior tests."""

import importlib

import pytest

from app.oauth_providers import OAUTH_PROVIDER_CREDENTIAL_FIELDS

auth_router_module = importlib.import_module("app.auth.router")


@pytest.mark.parametrize("provider", list(OAUTH_PROVIDER_CREDENTIAL_FIELDS.keys()))
def test_oauth_provider_disabled_raises_503(monkeypatch, provider: str):
    """Disabled provider must raise stable 503 contract."""
    client_id_field, client_secret_field = OAUTH_PROVIDER_CREDENTIAL_FIELDS[provider]
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


@pytest.mark.parametrize("provider_variant", ["GitHub", "GITHUB", "gItHuB"])
def test_oauth_provider_name_is_case_insensitive(monkeypatch, provider_variant: str):
    """Provider name resolution should ignore letter case."""
    monkeypatch.setattr(auth_router_module.settings, "GITHUB_CLIENT_ID", "")
    monkeypatch.setattr(auth_router_module.settings, "GITHUB_CLIENT_SECRET", "")

    with pytest.raises(auth_router_module.HTTPException) as exc_info:
        auth_router_module._ensure_provider_enabled(provider_variant)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        "OAuth provider 'github' is disabled. Configure GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
    )


def test_oauth_provider_case_variant_passes_when_credentials_exist(monkeypatch):
    """Case variant should resolve to the same provider when configured."""
    monkeypatch.setattr(auth_router_module.settings, "GITHUB_CLIENT_ID", "dummy-id")
    monkeypatch.setattr(auth_router_module.settings, "GITHUB_CLIENT_SECRET", "dummy-secret")

    auth_router_module._ensure_provider_enabled("GitHub")


def test_oauth_unknown_provider_normalizes_case_before_400():
    """Unknown mixed-case provider input should keep stable detail."""
    with pytest.raises(auth_router_module.HTTPException) as exc_info:
        auth_router_module._ensure_provider_enabled("UnKnown")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Unsupported OAuth provider 'unknown'."
