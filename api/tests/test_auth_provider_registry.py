"""OAuth provider registry deterministic-order tests."""

import importlib
import logging

from app.oauth_providers import (
    OAUTH_PROVIDER_CREDENTIAL_FIELDS,
    OAUTH_PROVIDER_CREDENTIAL_KEYS,
    OAUTH_PROVIDER_ORDER,
)

auth_router_module = importlib.import_module("app.auth.router")


def test_provider_registry_order_is_stable() -> None:
    """Provider registry order must stay deterministic across modules."""
    assert OAUTH_PROVIDER_ORDER == (
        "google",
        "discord",
        "github",
        "x",
        "linkedin",
        "facebook",
        "slack",
        "twitch",
    )
    assert tuple(OAUTH_PROVIDER_CREDENTIAL_FIELDS.keys()) == OAUTH_PROVIDER_ORDER
    assert OAUTH_PROVIDER_CREDENTIAL_KEYS == tuple(OAUTH_PROVIDER_CREDENTIAL_FIELDS.values())


def test_provider_registry_order_is_logged(caplog) -> None:
    """Registry initialization order should be emitted to logs."""
    with caplog.at_level(logging.INFO, logger=auth_router_module.__name__):
        auth_router_module._log_provider_registry_order()

    assert "OAuth provider registry initialized in deterministic order" in caplog.text
    assert "google -> discord -> github -> x -> linkedin -> facebook -> slack -> twitch" in caplog.text
