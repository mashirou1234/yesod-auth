"""Tests for configuration helpers."""

from unittest.mock import mock_open, patch

from app.config import (
    DEFAULT_CORS_ORIGINS,
    parse_bool_env,
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
        assert "Invalid boolean value for TESTING: 'maybe'" in message
        assert "Allowed values: 1,true,yes,0,false,no" in message
