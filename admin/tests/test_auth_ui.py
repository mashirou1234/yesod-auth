"""Authentication wiring through Streamlit's actual script execution."""

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import auth_session


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_url_session_cannot_authenticate():
    app = AppTest.from_file(str(APP_PATH))
    app.query_params["session"] = "9999999999.attacker-controlled"
    with patch("db.get_stats") as protected_read:
        app.run()
    assert not app.exception
    assert "session" not in app.query_params
    assert len(app.text_input) == 2
    protected_read.assert_not_called()


def test_expired_session_and_legacy_authenticated_flag_do_not_open_dashboard():
    app = AppTest.from_file(str(APP_PATH))
    app.session_state["authenticated"] = True
    app.session_state["session_token"] = "legacy"
    app.session_state["admin_session"] = {"username": "admin", "issued_at": 10, "expires_at": 20}
    with patch("auth_session.monotonic", return_value=20), patch("db.get_stats") as protected_read:
        app.run()
    assert not app.exception
    assert len(app.text_input) == 2
    protected_read.assert_not_called()


def test_login_stores_server_state_and_logout_clears_it():
    app = AppTest.from_file(str(APP_PATH)).run()
    app.text_input[0].set_value("admin")
    app.text_input[1].set_value("admin")
    with patch("db.get_stats", return_value={"total_users": 0, "total_oauth_accounts": 0, "active_sessions": 0}):
        app.button[0].click().run()
    assert not app.exception
    assert app.session_state["admin_session"]["username"] == "admin"
    assert "session" not in app.query_params
    logout = next(button for button in app.sidebar.button if button.label.endswith("Logout"))
    logout.click().run()
    assert not app.exception
    assert "admin_session" not in app.session_state
    assert len(app.text_input) == 2


def test_expiry_during_render_stops_protected_read():
    app = AppTest.from_file(str(APP_PATH))
    state = {}
    auth_session.start_session(state, "admin", 3600, now=100)
    app.session_state["admin_session"] = state["admin_session"]
    # First main auth check is valid; the protected operation check hits the deadline.
    with patch("auth_session.monotonic", side_effect=[3699, 3700, 3700]), patch("db.get_stats") as protected_read:
        app.run()
    assert not app.exception
    protected_read.assert_not_called()
    assert len(app.text_input) == 2
