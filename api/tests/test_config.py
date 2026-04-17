"""Tests for configuration helpers."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from app.config import (
    DEFAULT_CORS_ORIGINS,
    parse_bool_env,
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

    with patch("app.config.os.path.exists", return_value=False), patch("builtins.open") as mock_file:
        assert read_secret("jwt_secret", "default-value") == "env-value"
        mock_file.assert_not_called()


def test_read_secret_falls_back_to_default_when_secret_and_env_missing(monkeypatch):
    """Default value is used when both secret file and environment are absent."""
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with patch("app.config.os.path.exists", return_value=False), patch("builtins.open") as mock_file:
        assert read_secret("jwt_secret", "default-value") == "default-value"
        mock_file.assert_not_called()


def test_read_secret_strips_trailing_whitespace_from_secret_file(monkeypatch):
    """Trailing whitespace in secret files must be removed."""
    monkeypatch.setenv("JWT_SECRET", "env-value")

    with patch("app.config.os.path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data="file-value  \n\n")
    ):
        assert read_secret("jwt_secret", "default-value") == "file-value"


def test_resolve_cors_origins_uses_default_when_unset():
    origins, using_default = resolve_cors_origins(None)

    assert origins == DEFAULT_CORS_ORIGINS.split(",")
    assert using_default is True


def test_resolve_cors_origins_uses_default_when_blank():
    origins, using_default = resolve_cors_origins("   ")

    assert origins == DEFAULT_CORS_ORIGINS.split(",")
    assert using_default is True


def test_resolve_cors_origins_uses_env_value_when_set():
    origins, using_default = resolve_cors_origins("https://example.com, https://admin.example.com")

    assert origins == ["https://example.com", "https://admin.example.com"]
    assert using_default is False


def test_parse_bool_env_accepts_truthy_value(monkeypatch):
    monkeypatch.setenv("TESTING", "YeS")

    assert parse_bool_env("TESTING", default=False) is True


def test_parse_bool_env_accepts_falsy_value(monkeypatch):
    monkeypatch.setenv("TESTING", "0")

    assert parse_bool_env("TESTING", default=True) is False


def test_parse_bool_env_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)

    assert parse_bool_env("TESTING", default=True) is True


def test_parse_bool_env_raises_clear_error_on_invalid_value(monkeypatch):
    monkeypatch.setenv("TESTING", "maybe")

    try:
        parse_bool_env("TESTING")
        assert False, "ValueError was not raised for invalid boolean value"
    except ValueError as exc:
        message = str(exc)
        assert "Invalid boolean value for TESTING: raw='maybe', normalized='maybe'" in message
        assert "Allowed values: 1,true,yes,0,false,no" in message


def test_parse_bool_env_raises_with_raw_and_normalized_value(monkeypatch):
    monkeypatch.setenv("TESTING", "  ON  ")

    with pytest.raises(ValueError) as exc_info:
        parse_bool_env("TESTING")

    message = str(exc_info.value)
    assert "raw='  ON  '" in message
    assert "normalized='on'" in message


def test_resolve_cors_origins_raises_when_empty_element_is_present():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        resolve_cors_origins("https://example.com, ,https://admin.example.com")


def test_config_import_fails_fast_when_cors_origins_contains_empty_element():
    env = os.environ.copy()
    env["CORS_ORIGINS"] = "https://example.com, ,https://admin.example.com"

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
        check=False,
    )

    assert result.returncode != 0
    assert "CORS_ORIGINS contains empty element" in (result.stderr + result.stdout)


def test_frontend_url_defaults_when_env_is_unset():
    env = os.environ.copy()
    env.pop("FRONTEND_URL", None)

    result = subprocess.run(
        [sys.executable, "-c", "from app.config import Settings; print(Settings.FRONTEND_URL)"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "http://localhost:3000"


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


def test_settings_raises_when_provider_client_id_is_duplicated(monkeypatch):
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_ID", "shared-client-id")
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_SECRET", "github-client-secret")
    monkeypatch.setattr(Settings, "GOOGLE_CLIENT_ID", "shared-client-id")
    monkeypatch.setattr(Settings, "GOOGLE_CLIENT_SECRET", "google-client-secret")

    with pytest.raises(ValueError, match="duplicated across enabled providers"):
        Settings()


def test_settings_allows_when_provider_client_ids_are_unique(monkeypatch):
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_ID", "github-client-id")
    monkeypatch.setattr(Settings, "GITHUB_CLIENT_SECRET", "github-client-secret")
    monkeypatch.setattr(Settings, "GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(Settings, "GOOGLE_CLIENT_SECRET", "google-client-secret")

    settings = Settings()

    assert settings.GITHUB_CLIENT_ID == "github-client-id"
    assert settings.GOOGLE_CLIENT_ID == "google-client-id"


def test_settings_startup_fails_when_provider_secret_env_is_empty():
    env = os.environ.copy()
    env["GITHUB_CLIENT_ID"] = "github-client-id"
    env["GITHUB_CLIENT_SECRET"] = ""

    result = subprocess.run(
        [sys.executable, "-c", "from app.config import Settings; Settings()"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
        check=False,
    )

    assert result.returncode != 0
    assert "GITHUB_CLIENT_SECRET" in (result.stderr + result.stdout)


def test_settings_startup_succeeds_when_provider_secret_env_is_non_empty():
    env = os.environ.copy()
    env["GITHUB_CLIENT_ID"] = "github-client-id"
    env["GITHUB_CLIENT_SECRET"] = "github-client-secret"

    result = subprocess.run(
        [sys.executable, "-c", "from app.config import Settings; Settings(); print('ok')"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "ok"


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
