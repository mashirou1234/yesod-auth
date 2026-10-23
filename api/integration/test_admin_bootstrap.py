"""Defensive acceptance against isolated PostgreSQL schemas and separate connections."""

import asyncio
import hashlib
import hmac
import secrets
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db.base import DEFAULT_PROJECT_ID, Base
from app.models.admin import AdminBootstrap, Administrator
from app.models.project import Project
from app.routers.admin_bootstrap import router
from app.services import admin_bootstrap as service


@pytest_asyncio.fixture
async def bootstrap_db(monkeypatch):
    url = make_url(get_settings().DATABASE_URL)
    assert url.database == "yesod_foundation_test"
    schema = "bootstrap_" + uuid.uuid4().hex
    owner = create_async_engine(url)
    async with owner.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda connection: Base.metadata.create_all(
                connection,
                tables=[Project.__table__, Administrator.__table__, AdminBootstrap.__table__],
            )
        )
        await connection.execute(
            Project.__table__.insert().values(id=DEFAULT_PROJECT_ID, name="Default")
        )
        await connection.execute(AdminBootstrap.__table__.insert().values(id=1))
    monkeypatch.setattr(service, "engine", engine)
    yield engine
    await engine.dispose()
    async with owner.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    await owner.dispose()


async def payload():
    return {
        "capability": await service.issue_capability(),
        "username": "operator.one",
        "password": secrets.token_urlsafe(24),
    }


async def count_admins(engine):
    async with engine.connect() as connection:
        return await connection.scalar(select(func.count()).select_from(Administrator))


@pytest.mark.asyncio
async def test_success_stores_only_hashes_and_closes_every_entry(bootstrap_db, caplog):
    data = await payload()
    async with bootstrap_db.connect() as connection:
        state = (await connection.execute(select(AdminBootstrap.__table__))).mappings().one()
        assert state["capability_digest"] != data["capability"]
        assert (
            899
            < (
                state["expires_at"] - await connection.scalar(select(func.clock_timestamp()))
            ).total_seconds()
            <= 900
        )
    await service.register_admin(data)
    assert await service.is_initialized()
    assert await count_admins(bootstrap_db) == 1
    async with bootstrap_db.connect() as connection:
        admin = (await connection.execute(select(Administrator.__table__))).mappings().one()
        encoded = admin["password_hash"]
        algorithm, rounds, salt, digest = encoded.split("$")
        assert algorithm == "pbkdf2_sha256" and int(rounds) == 600000
        assert hmac.compare_digest(
            hashlib.pbkdf2_hmac(
                "sha256", data["password"].encode(), bytes.fromhex(salt), int(rounds)
            ),
            bytes.fromhex(digest),
        )
        assert admin["project_id"] == DEFAULT_PROJECT_ID
        state = (await connection.execute(select(AdminBootstrap.__table__))).mappings().one()
        assert state["capability_digest"] is None and state["expires_at"] is None
        assert state["initialized_at"] is not None
        serialized = str(dict(admin)) + str(dict(state)) + caplog.text
        assert all(data[key] not in serialized for key in ("capability", "password"))
    for operation in (lambda: service.register_admin(data), service.issue_capability):
        with pytest.raises(service.BootstrapError) as error:
            await operation()
        assert error.value.status == 410


@pytest.mark.asyncio
async def test_concurrent_http_registration_commits_exactly_once(bootstrap_db):
    data = await payload()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")

    async def submit(number):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return (
                await client.post(
                    "/api/v1/admin/bootstrap", json={**data, "username": f"operator{number}"}
                )
            ).status_code

    statuses = await asyncio.gather(*(submit(number) for number in range(8)))
    assert statuses.count(201) == 1
    assert statuses.count(410) == 7
    assert await count_admins(bootstrap_db) == 1


@pytest.mark.asyncio
async def test_separate_processes_cannot_both_initialize(bootstrap_db):
    import json
    import os
    import sys

    data = await payload()
    async with bootstrap_db.connect() as connection:
        schema = await connection.scalar(text("SELECT current_schema()"))
    program = """
import asyncio, json, os, sys
from sqlalchemy.ext.asyncio import create_async_engine
from app.services import admin_bootstrap as service
async def run():
    service.engine = create_async_engine(os.environ["DATABASE_URL"], connect_args={"server_settings": {"search_path": os.environ["BOOTSTRAP_TEST_SCHEMA"]}})
    try:
        await service.register_admin(json.load(sys.stdin))
        print(201)
    except service.BootstrapError as error:
        print(error.status)
    finally:
        await service.engine.dispose()
asyncio.run(run())
"""
    env = {**os.environ, "BOOTSTRAP_TEST_SCHEMA": schema}

    async def submit(number):
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            program,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, errors = await process.communicate(
            json.dumps({**data, "username": f"process{number}"}).encode()
        )
        assert process.returncode == 0 and not errors
        return int(output.strip())

    statuses = await asyncio.gather(submit(1), submit(2))
    assert sorted(statuses) == [201, 410]
    assert await count_admins(bootstrap_db) == 1


@pytest.mark.asyncio
async def test_expiry_during_password_hash_rejects_commit(bootstrap_db, monkeypatch):
    import time

    data = await payload()
    original = service._hash_password

    def slow_hash(password):
        time.sleep(0.15)
        return original(password)

    monkeypatch.setattr(service, "_hash_password", slow_hash)
    async with bootstrap_db.begin() as connection:
        await connection.execute(
            text(
                "UPDATE admin_bootstrap SET expires_at = clock_timestamp() + interval '0.1 seconds'"
            )
        )
    with pytest.raises(service.BootstrapError) as error:
        await service.register_admin(data)
    assert error.value.status == 403
    assert await count_admins(bootstrap_db) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unissued", "wrong", "expired", "reissued"])
async def test_rejected_capability_never_creates_admin(bootstrap_db, case):
    data = {
        "capability": secrets.token_urlsafe(32),
        "username": "operator.one",
        "password": secrets.token_urlsafe(24),
    }
    if case != "unissued":
        data = await payload()
    if case == "wrong":
        data["capability"] = secrets.token_urlsafe(32)
    elif case == "expired":
        async with bootstrap_db.begin() as connection:
            await connection.execute(
                update(AdminBootstrap).values(expires_at=func.clock_timestamp())
            )
    elif case == "reissued":
        replacement = await service.issue_capability()
    with pytest.raises(service.BootstrapError) as error:
        await service.register_admin(data)
    assert error.value.status == 403
    assert await count_admins(bootstrap_db) == 0
    if case == "reissued":
        await service.register_admin({**data, "capability": replacement})
        assert await count_admins(bootstrap_db) == 1


@pytest.mark.asyncio
async def test_initialization_survives_pool_restart_and_administrator_deletion(bootstrap_db):
    await service.register_admin(await payload())
    await bootstrap_db.dispose()
    async with bootstrap_db.begin() as connection:
        await connection.execute(delete(Administrator))
    assert await service.is_initialized()
    with pytest.raises(service.BootstrapError) as error:
        await service.issue_capability()
    assert error.value.status == 410


@pytest.mark.asyncio
async def test_constraint_failure_rolls_back_account_and_consumption(bootstrap_db):
    data = await payload()
    # A test-only rejecting constraint reproduces an ordinary DB write failure.
    async with bootstrap_db.begin() as connection:
        await connection.execute(
            text(
                "ALTER TABLE admin_bootstrap ADD CONSTRAINT reject_initialization CHECK (initialized_at IS NULL)"
            )
        )
    with pytest.raises(SQLAlchemyError):
        await service.register_admin(data)
    assert await count_admins(bootstrap_db) == 0
    assert not await service.is_initialized()
    async with bootstrap_db.begin() as connection:
        await connection.execute(
            text("ALTER TABLE admin_bootstrap DROP CONSTRAINT reject_initialization")
        )
    await service.register_admin(data)
    assert await count_admins(bootstrap_db) == 1


@pytest.mark.asyncio
async def test_reissue_and_consume_share_lock(bootstrap_db):
    data = await payload()
    results = await asyncio.gather(
        service.issue_capability(), service.register_admin(data), return_exceptions=True
    )
    count = await count_admins(bootstrap_db)
    assert count in (0, 1)
    assert sum(isinstance(value, service.BootstrapError) for value in results) == 1
    if count == 0:
        assert isinstance(results[0], str)
        await service.register_admin({**data, "capability": results[0]})
    else:
        assert isinstance(results[0], service.BootstrapError)
    assert await count_admins(bootstrap_db) == 1


@pytest.mark.asyncio
async def test_missing_state_and_preexisting_administrator_fail_closed(bootstrap_db):
    data = await payload()
    await service.register_admin(data)
    async with bootstrap_db.begin() as connection:
        await connection.execute(update(AdminBootstrap).values(initialized_at=None))
    with pytest.raises(service.BootstrapError) as error:
        await service.issue_capability()
    assert error.value.status == 410
    async with bootstrap_db.begin() as connection:
        await connection.execute(delete(AdminBootstrap))
    with pytest.raises(service.BootstrapError) as error:
        await service.is_initialized()
    assert error.value.status == 503
