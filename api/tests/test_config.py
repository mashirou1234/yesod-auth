"""Tests for configuration helpers."""

import importlib
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from app.config import (
    DEFAULT_CORS_ORIGINS,
    read_secret,
    resolve_cors_origins,
)

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"
PROFILE_SERVICE_CASES = (
    ("default", "api"),
    ("full", "api"),
    ("ci", "api-ci"),
)


def _reload_config_module():
    return importlib.reload(importlib.import_module("app.config"))


def _compose_service(service_name: str) -> dict:
    compose = yaml.safe_load(COMPOSE_FILE.read_text())
    return compose["services"][service_name]


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


def test_mock_oauth_enabled_defaults_to_disabled_when_env_is_unset(monkeypatch):
    monkeypatch.delenv("MOCK_OAUTH_ENABLED", raising=False)

    config_module = _reload_config_module()

    assert config_module.Settings.MOCK_OAUTH_ENABLED is False


def test_mock_oauth_enabled_is_enabled_when_env_requests_it(monkeypatch):
    monkeypatch.setenv("MOCK_OAUTH_ENABLED", "1")

    config_module = _reload_config_module()

    assert config_module.Settings.MOCK_OAUTH_ENABLED is True


@pytest.mark.parametrize(("profile_name", "service_name"), PROFILE_SERVICE_CASES)
@patch("app.config.os.path.exists", return_value=False)
def test_compose_profiles_override_mock_oauth_enabled(_mock_exists, monkeypatch, profile_name, service_name):
    monkeypatch.delenv("MOCK_OAUTH_ENABLED", raising=False)
    config_module = _reload_config_module()

    assert config_module.Settings.MOCK_OAUTH_ENABLED is False

    compose_service = _compose_service(service_name)

    assert profile_name in compose_service["profiles"]
    assert "MOCK_OAUTH_ENABLED=1" in compose_service.get("environment", [])

    monkeypatch.setenv("MOCK_OAUTH_ENABLED", "1")
    config_module = _reload_config_module()

    assert config_module.Settings.MOCK_OAUTH_ENABLED is True
