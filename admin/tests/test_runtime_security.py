"""Runtime validation for administrator credentials."""

import secrets

import pytest

from config import Settings


@pytest.mark.parametrize("password", [None, "", "admin", "password", "x" * 32, "short"])
def test_production_rejects_weak_admin_password(monkeypatch, password):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    if password is None:
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("ADMIN_PASSWORD", password)
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings()


def test_runtime_defaults_to_production(monkeypatch):
    monkeypatch.delenv("RUNTIME_MODE", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings()


def test_invalid_runtime_rejected(monkeypatch):
    monkeypatch.setenv("RUNTIME_MODE", "dev")
    with pytest.raises(ValueError, match="RUNTIME_MODE"):
        Settings()


def test_runtime_reads_environment_for_each_instance(monkeypatch):
    monkeypatch.setenv("RUNTIME_MODE", "test")
    monkeypatch.setenv("ADMIN_USER", "first")
    assert Settings().ADMIN_USER == "first"
    monkeypatch.setenv("ADMIN_USER", "second")
    assert Settings().ADMIN_USER == "second"


def test_production_accepts_strong_explicit_admin_password(monkeypatch):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", secrets.token_urlsafe(32))
    assert Settings().RUNTIME_MODE == "production"


@pytest.mark.parametrize(
    "password",
    [
        "password12345678!",
        "PASSWORD12345678!",
        "Qwerty-0123456789!",
        "LetMeIn-0123456789!",
        "P@ssw0rd-0123456789!",
        "abcdefghijklmnopqrstuvwxyz",
    ],
)
def test_production_rejects_known_predictable_admin_password(monkeypatch, password):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", password)
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings()


@pytest.mark.parametrize("generator", [secrets.token_hex, secrets.token_urlsafe])
def test_production_accepts_generated_admin_password(monkeypatch, generator):
    monkeypatch.setenv("RUNTIME_MODE", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", generator(32))
    assert Settings().RUNTIME_MODE == "production"
