"""Server-side absolute session expiry independent of Streamlit."""

import pytest

from auth_session import clear_session, is_authenticated, start_session


def test_session_expires_at_absolute_deadline_without_sliding():
    state = {}
    start_session(state, "admin", 3600, now=100)
    assert is_authenticated(state, "admin", 3600, now=3699)
    assert state["admin_session"]["expires_at"] == 3700
    assert not is_authenticated(state, "admin", 3600, now=3700)
    assert "admin_session" not in state


@pytest.mark.parametrize("record", [None, True, {}, {"username": "admin"},
    {"username": "admin", "issued_at": 100, "expires_at": float("nan")},
    {"username": "admin", "issued_at": 100, "expires_at": float("inf")},
    {"username": "admin", "issued_at": 100, "expires_at": "3700"},
    {"username": "admin", "issued_at": True, "expires_at": 3700},
    {"username": "other", "issued_at": 100, "expires_at": 3700},
    {"username": "admin", "issued_at": 100, "expires_at": 999999},
    {"username": "admin", "issued_at": 101, "expires_at": 3700},
])
def test_malformed_authentication_state_fails_closed(record):
    state = {"admin_session": record, "authenticated": True, "session_token": "old"}
    assert not is_authenticated(state, "admin", 3600, now=100)
    assert "admin_session" not in state
    assert "session_token" not in state
    assert "authenticated" not in state


def test_logout_clears_authentication_and_api_test_credentials():
    state = {"language": "ja", "test_access_token": "secret", "test_refresh_token": "secret"}
    start_session(state, "admin", 3600, now=100)
    clear_session(state)
    assert state == {}


def test_changing_admin_identity_invalidates_existing_session():
    state = {}
    start_session(state, "old-admin", 3600, now=100)
    assert not is_authenticated(state, "new-admin", 3600, now=101)
