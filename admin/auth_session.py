"""Short-lived authentication state owned exclusively by the Streamlit server."""

import math
from time import monotonic
from collections.abc import MutableMapping
from typing import Any


def clear_session(state: MutableMapping[str, Any]) -> None:
    """Clear all session data, including credentials entered into the API console."""
    state.clear()


def start_session(
    state: MutableMapping[str, Any],
    username: str,
    lifetime_seconds: float,
    *,
    now: float | None = None,
) -> None:
    """Create an absolute deadline, with no browser token or sliding renewal."""
    issued_at = monotonic() if now is None else now
    clear_session(state)
    state["admin_session"] = {
        "username": username,
        "issued_at": issued_at,
        "expires_at": issued_at + lifetime_seconds,
    }


def is_authenticated(
    state: MutableMapping[str, Any],
    username: str,
    lifetime_seconds: float,
    *,
    now: float | None = None,
) -> bool:
    """Fail closed for missing, malformed, expired, or overlong session state."""
    current = monotonic() if now is None else now
    record = state.get("admin_session")
    valid = False
    if isinstance(record, dict) and record.get("username") == username:
        issued_at, expires_at = record.get("issued_at"), record.get("expires_at")
        if all(type(value) in (int, float) and math.isfinite(value) for value in (issued_at, expires_at)):
            valid = (
                issued_at <= current < expires_at
                and 0 < expires_at - issued_at <= lifetime_seconds
            )
    if not valid:
        # Preserve public UI preferences and in-progress login widgets; remove all auth material.
        for key in (
            "admin_session", "authenticated", "session_token",
            "test_access_token", "test_refresh_token", "session_ids",
        ):
            state.pop(key, None)
    return valid
