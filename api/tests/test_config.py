"""Tests for configuration helpers."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from app.config import (
    DEFAULT_CORS_ORIGINS,
    Settings,
    read_secret,
    resolve_cors_origins,
)


def test_read_secret_prefers_secret_file_over_env(monkeypatch):
    """Docker secret file value must win over environment variable."""
    monkeypatch.setenv("JWT_SECRET", "env-value")

    with patch("app.config.os.path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data="file-value\n")
    ):
        assert read_secret("jwt_secret", "default-value") == "file-value"


def test_read_secret_falls_back_to_env_when_secret_file_missing(monkeypatch):
    """Environment variable is used when secret file does not exist."""
    monkeypatch.setenv("JWT_SECRET", "env-value")

    with patch("app.config.os.path.exists", return_value=False):
        assert read_secret("jwt_secret", "default-value") == "env-value"


def test_read_secret_falls_back_to_default_when_secret_and_env_missing(monkeypatch):
    """Default value is used when both secret file and environment are absent."""
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with patch("app.config.os.path.exists", return_value=False):
        assert read_secret("jwt_secret", "default-value") == "default-value"


def test_resolve_cors_origins_uses_default_when_unset():
    origins, using_default = resolve_cors_origins(None)

    assert origins == DEFAULT_CORS_ORIGINS.split(",")
    assert using_default is True


def test_resolve_cors_origins_uses_default_when_blank():
    origins, using_default = resolve_cors_origins(" , ")

    assert origins == DEFAULT_CORS_ORIGINS.split(",")
    assert using_default is True


def test_resolve_cors_origins_uses_env_value_when_set():
    origins, using_default = resolve_cors_origins("https://example.com, https://admin.example.com")

    assert origins == ["https://example.com", "https://admin.example.com"]
    assert using_default is False


def test_settings_raises_when_provider_client_id_exists_but_secret_is_empty(monkeypatch):
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_ID", "github-client-id")
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_SECRET", "")

    with pytest.raises(
        ValueError, match="GITHUB_CLIENT_SECRET"
    ):
        Settings()


def test_settings_allows_when_provider_secret_is_non_empty(monkeypatch):
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_ID", "github-client-id")
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_SECRET", "github-client-secret")

    settings = Settings()

    assert settings.GITHUB_CLIENT_SECRET == "github-client-secret"


def _load_compose_services() -> dict:
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    with compose_path.open() as f:
        compose = yaml.safe_load(f)
    return compose["services"]


def _environment_values(service: dict) -> list[str]:
    environment = service.get("environment", [])
    if isinstance(environment, dict):
        return [f"{key}={value}" for key, value in environment.items()]
    return [str(value) for value in environment]


@pytest.mark.parametrize(
    ("profile", "service_name"),
    [
        ("default", "api"),
        ("full", "api"),
        ("ci", "api-ci"),
    ],
)
def test_mock_oauth_enabled_is_overridden_to_true_for_each_profile(profile, service_name):
    services = _load_compose_services()
    service = services[service_name]

    assert profile in service.get("profiles", [])
    assert "MOCK_OAUTH_ENABLED=1" in _environment_values(service)
