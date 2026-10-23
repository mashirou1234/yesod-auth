"""Real PostgreSQL migrations, ORM token lifecycle, audit and Valkey state checks.

Run only against the dedicated disposable services through verify-foundation.sh.
Unlike the SQLite unit fixtures, no DB, audit, or cache dependency is mocked.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.service import AuditLogger
from app.auth.tokens import (
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    validate_refresh_token,
)
from app.config import get_settings
from app.db.base import DEFAULT_PROJECT_ID
from app.db.project import ProjectAsyncSession
from app.db.session import engine as app_engine
from app.main import app
from app.models import User
from app.valkey import OAuthStateStore, close_valkey, get_valkey


@pytest.mark.asyncio
async def test_postgres_token_lifecycle_and_valkey_state():
    settings = get_settings()
    assert settings.RUNTIME_MODE == "test"
    assert settings.DATABASE_URL.endswith("/yesod_foundation_test")
    assert settings.TESTING is False
    engine = create_async_engine(settings.DATABASE_URL)
    sessions = async_sessionmaker(
        engine, class_=ProjectAsyncSession, project_id=DEFAULT_PROJECT_ID, expire_on_commit=False
    )
    user_id = uuid.uuid4()
    state = f"foundation-{uuid.uuid4()}"
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "007"
        async with sessions() as db:
            user = User(id=user_id)
            db.add(user)
            await db.commit()
            token = await create_refresh_token(db, user_id)
            assert (await validate_refresh_token(db, token)).user_id == user_id
            rotated = await rotate_refresh_token(db, token)
            assert rotated is not None
            assert await validate_refresh_token(db, token) is None
            assert (await validate_refresh_token(db, rotated[0])).user_id == user_id
            await AuditLogger.log_login(db, user_id, "google", True, "127.0.0.1", "foundation-ci")
        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM audit.login_history WHERE user_id = :id"),
                    {"id": user_id},
                )
                == 1
            )

        # Exercise the real API dependency graph against the migrated database.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            access_token = create_access_token(str(user_id), "integration@example.invalid")
            response = await client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response.status_code == 200
            assert response.json()["id"] == str(user_id)

        await OAuthStateStore.save(state, "google", "pkce-verifier")
        cache = await get_valkey()
        assert 0 < await cache.ttl(f"oauth_state:{state}") <= settings.OAUTH_STATE_TTL
        assert await OAuthStateStore.get_and_delete(state) == {
            "provider": "google",
            "code_verifier": "pkce-verifier",
        }
        assert await OAuthStateStore.get_and_delete(state) is None
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM audit.login_history WHERE user_id = :id"), {"id": user_id}
            )
        async with sessions() as db:
            user = await db.scalar(select(User).where(User.id == user_id))
            if user:
                await db.delete(user)
            await db.commit()
        cache = await get_valkey()
        await cache.delete(f"oauth_state:{state}")
        await close_valkey()
        await app_engine.dispose()
        await engine.dispose()
