"""The issuance command writes capability only to an explicit local TTY."""

import io
import secrets
from unittest.mock import AsyncMock, patch

from app.bootstrap import main


def test_no_tty_refuses_before_issuing(capsys):
    with (
        patch("app.bootstrap.open", side_effect=OSError) as opened,
        patch("app.bootstrap.issue_capability", new=AsyncMock()) as issue,
    ):
        assert main() == 1
    issue.assert_not_called()
    opened.assert_called_once_with("/dev/tty", "w", encoding="utf-8")
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
        patch("app.bootstrap.open", return_value=tty) as opened,
        patch("app.bootstrap.issue_capability", new=AsyncMock(return_value=token)),
    ):
        assert main() == 0
    opened.assert_called_once_with("/dev/tty", "w", encoding="utf-8")
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
        patch("app.bootstrap.open", return_value=Terminal()) as opened,
        patch("app.bootstrap.issue_capability", new=AsyncMock(side_effect=SQLAlchemyError(token))),
    ):
        assert main() == 1
    opened.assert_called_once_with("/dev/tty", "w", encoding="utf-8")
    output = capsys.readouterr()
    assert token not in output.out + output.err


def test_non_tty_handle_refuses_before_issuing(capsys):
    with (
        patch("app.bootstrap.open", return_value=io.StringIO()) as opened,
        patch("app.bootstrap.issue_capability", new=AsyncMock()) as issue,
    ):
        assert main() == 1
    opened.assert_called_once_with("/dev/tty", "w", encoding="utf-8")
    issue.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ""
    assert "terminal" in output.err


def test_real_controlling_pty_keeps_standard_streams_empty():
    import os
    import pty
    import re
    import select
    import signal
    import sys
    import time

    program = """
import contextlib, io, secrets
from app import bootstrap
async def fixture_capability():
    return secrets.token_urlsafe(32)
bootstrap.issue_capability = fixture_capability
stdout, stderr = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
    status = bootstrap.main()
raise SystemExit(0 if status == 0 and not stdout.getvalue() and not stderr.getvalue() else 1)
"""
    pid, master = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-c", program])
    terminal = bytearray()
    completed = False
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 4096)
                    terminal.extend(chunk)
                except OSError:
                    break
                if not chunk:
                    break
        else:
            raise AssertionError("Isolated PTY process timed out")
        _, status = os.waitpid(pid, 0)
        completed = True
        assert os.waitstatus_to_exitcode(status) == 0
        assert re.search(rb"(?m)^[A-Za-z0-9_-]{43}\r?$", terminal) is not None
    finally:
        if not completed:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(master)
        terminal.clear()
