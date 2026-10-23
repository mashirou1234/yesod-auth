"""The issuance command writes capability only to an explicit local TTY."""

import io
import secrets
from unittest.mock import AsyncMock, patch

from app.bootstrap import main


def test_no_tty_refuses_before_issuing(capsys):
    with (
        patch("app.bootstrap.open", side_effect=OSError),
        patch("app.bootstrap.issue_capability", new=AsyncMock()) as issue,
    ):
        assert main() == 1
    issue.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ""
    assert "terminal" in output.err


def test_only_controlling_tty_receives_secret(capsys):
    token = secrets.token_urlsafe(32)

    class Terminal(io.StringIO):
        def isatty(self):
            return True

        def close(self):
            pass

    tty = Terminal()
    with (
        patch("app.bootstrap.open", return_value=tty),
        patch("app.bootstrap.issue_capability", new=AsyncMock(return_value=token)),
    ):
        assert main() == 0
    output = capsys.readouterr()
    assert token not in output.out + output.err
    assert token in tty.getvalue()


def test_issuance_error_is_generic(capsys):
    token = secrets.token_urlsafe(32)

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    from sqlalchemy.exc import SQLAlchemyError

    with (
        patch("app.bootstrap.open", return_value=Terminal()),
        patch("app.bootstrap.issue_capability", new=AsyncMock(side_effect=SQLAlchemyError(token))),
    ):
        assert main() == 1
    output = capsys.readouterr()
    assert token not in output.out + output.err
