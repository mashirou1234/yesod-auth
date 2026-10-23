"""Explicit local issuance: python -m app.bootstrap (a controlling TTY is required)."""

import asyncio
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.services.admin_bootstrap import BootstrapError, issue_capability


def main() -> int:
    try:
        terminal = open("/dev/tty", "w", encoding="utf-8")
    except OSError:
        print(
            "A local controlling terminal is required; no capability was issued.", file=sys.stderr
        )
        return 1
    with terminal:
        if not terminal.isatty():
            print(
                "A local controlling terminal is required; no capability was issued.",
                file=sys.stderr,
            )
            return 1
        try:
            capability = asyncio.run(issue_capability())
            terminal.write("First administrator capability (expires in 15 minutes):\n")
            terminal.write(capability + "\n")
            terminal.flush()
        except (BootstrapError, SQLAlchemyError, OSError):
            print(
                "Capability issuance unavailable. Check initialization and database readiness.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
