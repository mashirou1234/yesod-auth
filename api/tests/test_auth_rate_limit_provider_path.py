"""Tests for OAuth provider path extraction in rate-limit metrics."""

import pytest

from app.auth.rate_limit import MISSING_OAUTH_PROVIDER_KEY
from app.auth.rate_limit import extract_oauth_provider_from_path
from app.auth.rate_limit import resolve_oauth_provider_metric_key


@pytest.mark.parametrize(
    ("path", "expected_provider"),
    [
        ("/api/v1/auth/google", "google"),
        ("/api/v1/auth/google/", None),
        ("/api/v1/auth/google/callback", None),
        ("/api/v1/auth/unknown", None),
        ("/api/v1/auth/", None),
        ("/api/v1/users/me", None),
    ],
)
def test_extract_oauth_provider_from_path_boundary(path: str, expected_provider: str | None):
    """Only exact /api/v1/auth/<provider> paths should resolve provider."""
    assert extract_oauth_provider_from_path(path) == expected_provider


@pytest.mark.parametrize(
    ("path", "expected_metric_key"),
    [
        ("/api/v1/auth/google", "google"),
        ("/api/v1/auth/google/callback", MISSING_OAUTH_PROVIDER_KEY),
        ("/api/v1/auth/google/", MISSING_OAUTH_PROVIDER_KEY),
        ("/api/v1/auth/unknown", MISSING_OAUTH_PROVIDER_KEY),
        ("/api/v1/users/me", None),
    ],
)
def test_resolve_oauth_provider_metric_key_boundary(path: str, expected_metric_key: str | None):
    """Auth prefix with unmatched provider should fall back to missing-provider key."""
    assert resolve_oauth_provider_metric_key(path) == expected_metric_key
