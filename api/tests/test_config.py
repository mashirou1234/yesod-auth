"""Tests for configuration helpers."""

from unittest.mock import mock_open, patch

from app.config import read_secret


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
