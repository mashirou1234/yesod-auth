"""Narrow administrative transactions for first-administrator registration.

These installation-wide tables deliberately do not use consumer ProjectSession.
No caller-controlled SQL, project selection, or general connection is exposed.
"""

import asyncio
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import exists, func, insert, select, update

from app.db.base import DEFAULT_PROJECT_ID
from app.db.session import engine
from app.models.admin import AdminBootstrap, Administrator

TTL = timedelta(minutes=15)
PASSWORD_ITERATIONS = 600_000
_state = AdminBootstrap.__table__
_administrators = Administrator.__table__


class BootstrapError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def validate_registration(data: object) -> tuple[str, str, str]:
    """Reject malformed input without embedding it in any error or validation object."""
    if not isinstance(data, dict) or set(data) != {"capability", "username", "password"}:
        raise BootstrapError("Invalid registration input")
    capability, username, password = (data[key] for key in ("capability", "username", "password"))
    if (
        not all(isinstance(value, str) for value in (capability, username, password))
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", capability)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}", username)
        or not 16 <= len(password) <= 128
        or not password.strip()
        or password.casefold() == username.casefold()
    ):
        raise BootstrapError("Invalid registration input")
    try:
        if len(password.encode("utf-8")) > 512:
            raise BootstrapError("Invalid registration input")
    except UnicodeError:
        raise BootstrapError("Invalid registration input") from None
    return capability, username, password


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


async def _locked_state(connection):
    state = (
        (await connection.execute(select(_state).where(_state.c.id == 1).with_for_update()))
        .mappings()
        .one_or_none()
    )
    if state is None:
        raise BootstrapError("Registration unavailable", 503)
    if state["initialized_at"] is not None or await connection.scalar(
        select(exists().where(_administrators.c.id.is_not(None)))
    ):
        raise BootstrapError("Registration is closed", 410)
    return state


async def is_initialized() -> bool:
    async with engine.connect() as connection:
        state = (
            (await connection.execute(select(_state).where(_state.c.id == 1)))
            .mappings()
            .one_or_none()
        )
        if state is None:
            raise BootstrapError("Registration unavailable", 503)
        return state["initialized_at"] is not None or bool(
            await connection.scalar(select(exists().where(_administrators.c.id.is_not(None))))
        )


async def issue_capability() -> str:
    """Only the local TTY command calls this issuance operation."""
    async with engine.begin() as connection:
        await _locked_state(connection)
        now = await connection.scalar(select(func.clock_timestamp()))
        capability = secrets.token_urlsafe(32)
        await connection.execute(
            update(_state)
            .where(_state.c.id == 1)
            .values(
                capability_digest=hashlib.sha256(capability.encode("ascii")).hexdigest(),
                expires_at=now + TTL,
            )
        )
    return capability


async def register_admin(data: object) -> None:
    capability, username, password = validate_registration(data)
    async with engine.begin() as connection:
        state = await _locked_state(connection)
        now = await connection.scalar(select(func.clock_timestamp()))
        if (
            state["capability_digest"] is None
            or state["expires_at"] is None
            or now >= state["expires_at"]
            or not hmac.compare_digest(
                state["capability_digest"], hashlib.sha256(capability.encode("ascii")).hexdigest()
            )
        ):
            raise BootstrapError("Capability is invalid or expired", 403)
        password_hash = await asyncio.to_thread(_hash_password, password)
        # Use DB time again after the expensive hash so expiry cannot pass during hashing.
        now = await connection.scalar(select(func.clock_timestamp()))
        if now >= state["expires_at"]:
            raise BootstrapError("Capability is invalid or expired", 403)
        await connection.execute(
            insert(_administrators).values(
                id=uuid.uuid4(),
                project_id=DEFAULT_PROJECT_ID,
                username=username,
                password_hash=password_hash,
                created_at=now,
            )
        )
        await connection.execute(
            update(_state)
            .where(_state.c.id == 1)
            .values(
                initialized_at=now,
                capability_digest=None,
                expires_at=None,
            )
        )
