"""Fail-closed runtime and JWT contract regressions."""

import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import mock_open, patch

import pytest
from jose import jwt

from app.auth import tokens
from app.config import Settings


@pytest.mark.parametrize("secret", [None, "", "change-me-in-production", "x" * 64, "short"])
def test_production_rejects_weak_jwt_secret(monkeypatch, secret):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setenv("MOCK_OAUTH_ENABLED", "0")
    if secret is None:
        monkeypatch.delenv("JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET", secret)
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings()


@pytest.mark.parametrize("mode", ["", "prod", "staging", "unknown"])
def test_unknown_runtime_mode_rejected(monkeypatch, mode):
    monkeypatch.setenv("RUNTIME_MODE", mode)
    with pytest.raises(ValueError, match="RUNTIME_MODE"):
        Settings()


def test_runtime_defaults_to_fail_closed_production(monkeypatch):
    monkeypatch.delenv("RUNTIME_MODE", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.parametrize("flag", ["TESTING", "MOCK_OAUTH_ENABLED", "DEBUG_OAUTH_ENABLED"])
def test_production_rejects_testing_and_mock_flags(monkeypatch, flag):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    monkeypatch.setenv("JWT_SECRET", JWT_FILE_FIXTURE)
    for key in ("TESTING", "MOCK_OAUTH_ENABLED", "DEBUG_OAUTH_ENABLED"):
        monkeypatch.setenv(key, "0")
    monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match=flag):
        Settings()


def test_settings_read_environment_per_instance(monkeypatch):
    monkeypatch.setenv("RUNTIME_MODE", "development")
    monkeypatch.setenv("JWT_ISSUER", "issuer-one")
    first = Settings()
    monkeypatch.setenv("JWT_ISSUER", "issuer-two")
    second = Settings()
    assert first.JWT_ISSUER == "issuer-one"
    assert second.JWT_ISSUER == "issuer-two"


def test_access_token_has_and_validates_issuer_audience():
    token = tokens.create_access_token("user-id", "user@example.com")
    claims = tokens.decode_access_token(token)
    assert claims["iss"] == tokens.settings.JWT_ISSUER
    assert claims["aud"] == tokens.settings.JWT_AUDIENCE


@pytest.mark.parametrize(
    "claim,value",
    [
        ("iss", "other"),
        ("aud", "other"),
        ("iss", None),
        ("aud", None),
        ("exp", None),
        ("sub", None),
    ],
)
def test_access_token_rejects_wrong_or_missing_claims(claim, value):
    claims = {
        "sub": "user-id",
        "email": "user@example.com",
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=1),
        "iss": "yesod-auth",
        "aud": "yesod-api",
    }
    if value is None:
        claims.pop(claim)
    else:
        claims[claim] = value
    token = jwt.encode(claims, tokens.settings.JWT_SECRET, algorithm="HS256")
    assert tokens.decode_access_token(token) is None


@pytest.mark.asyncio
async def test_debug_endpoint_disabled_by_default(client):
    response = await client.get("/api/v1/auth/debug-tokens?access_token=test&refresh_token=test")
    assert response.status_code == 404


def test_production_accepts_explicit_non_default_settings(monkeypatch):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    monkeypatch.setenv("JWT_SECRET", JWT_FILE_FIXTURE)
    for flag in ("TESTING", "MOCK_OAUTH_ENABLED", "DEBUG_OAUTH_ENABLED"):
        monkeypatch.setenv(flag, "0")
    assert Settings().RUNTIME_MODE == "production"


@pytest.mark.parametrize("key", ["JWT_ISSUER", "JWT_AUDIENCE"])
def test_empty_token_trust_boundary_rejected(monkeypatch, key):
    monkeypatch.setenv(key, " ")
    with pytest.raises(ValueError, match=key):
        Settings()


@pytest.mark.asyncio
async def test_debug_endpoint_cannot_be_enabled_in_production_at_request_time(client, monkeypatch):
    from app.auth.router import settings

    monkeypatch.setattr(settings, "RUNTIME_MODE", "production")
    monkeypatch.setattr(settings, "DEBUG_OAUTH_ENABLED", True)
    response = await client.get("/api/v1/auth/debug-tokens?access_token=test&refresh_token=test")
    assert response.status_code == 404


@pytest.fixture
def production_environment(monkeypatch):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    for flag in ("TESTING", "MOCK_OAUTH_ENABLED", "DEBUG_OAUTH_ENABLED"):
        monkeypatch.setenv(flag, "0")


@pytest.mark.parametrize(
    "secret",
    [
        "password1234567890!password123456",
        "PASSWORD1234567890!PASSWORD123456",
        "qwerty-ABCDEFGHIJKLM-0123456789-test",
        "LetMeIn-ABCDEFGHIJKLM-0123456789-test",
        "P@ssw0rd-ABCDEFGHIJKLM-0123456789-test",
        "key-abcdefghijklmnopqrstuvwxyz-abcdef",
    ],
)
def test_production_rejects_known_predictable_jwt_secret(
    monkeypatch, production_environment, secret
):
    monkeypatch.setenv("JWT_SECRET", secret)
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings()


# Public, synthetic test value: never use it as a deployed credential.
JWT_FILE_FIXTURE = "a817e9c26f5b304d8bc6f7a1943de85229b361fed48a5370cf942da9e0b85c16"


@pytest.mark.parametrize("source", ["environment", "file"])
@pytest.mark.parametrize("position", ["leading", "embedded", "trailing"])
@pytest.mark.parametrize("whitespace", [" ", "\t", "\n", "\r", "\u00a0"])
def test_production_rejects_jwt_whitespace(
    monkeypatch, production_environment, source, position, whitespace
):
    value = {
        "leading": whitespace + JWT_FILE_FIXTURE,
        "embedded": JWT_FILE_FIXTURE[:32] + whitespace + JWT_FILE_FIXTURE[32:],
        "trailing": JWT_FILE_FIXTURE + whitespace,
    }[position]
    monkeypatch.setenv("JWT_SECRET", value)
    if source == "file":
        # The final CRLF is permitted; any whitespace in the value must remain unsafe.
        with (
            patch(
                "app.config.os.path.exists",
                side_effect=lambda path: path == "/run/secrets/jwt_secret",
            ),
            patch("builtins.open", mock_open(read_data=value + "\r\n")),
            pytest.raises(ValueError, match="JWT_SECRET"),
        ):
            Settings()
    else:
        with (
            patch("app.config.os.path.exists", return_value=False),
            pytest.raises(ValueError, match="JWT_SECRET"),
        ):
            Settings()


@pytest.mark.parametrize("terminator", ["", "\n", "\r\n"])
def test_production_accepts_one_file_line_terminator(
    monkeypatch, production_environment, terminator, tmp_path
):
    monkeypatch.setenv("JWT_SECRET", "weak-env-fallback-must-not-be-used")
    secret_file = tmp_path / "jwt_secret"
    secret_file.write_bytes((JWT_FILE_FIXTURE + terminator).encode())
    with (
        patch(
            "app.config.os.path.exists", side_effect=lambda path: path == "/run/secrets/jwt_secret"
        ),
        patch(
            "app.config.open",
            side_effect=lambda path, **kwargs: secret_file.open(**kwargs),
            create=True,
        ),
    ):
        assert Settings().JWT_SECRET == JWT_FILE_FIXTURE


@pytest.mark.parametrize("generator", [secrets.token_hex, secrets.token_urlsafe])
def test_production_accepts_generated_jwt_secret(monkeypatch, production_environment, generator):
    monkeypatch.setenv("JWT_SECRET", generator(32))
    with patch("app.config.os.path.exists", return_value=False):
        assert Settings().RUNTIME_MODE == "production"
