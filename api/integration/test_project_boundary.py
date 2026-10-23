"""Acceptance tests against disposable real PostgreSQL, no ORM/DB fakes."""

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import aliased, make_transient_to_detached, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.audit import AuditLogger, AuthEventType
from app.auth.router import _find_or_create_user
from app.auth.tokens import create_access_token, create_refresh_token, validate_refresh_token
from app.config import get_settings
from app.db.base import DEFAULT_PROJECT_ID
from app.db.project import ProjectAsyncSession
from app.db.session import async_session_maker, get_db
from app.main import app
from app.models import OAuthAccount, Project, RefreshToken, User, UserEmail, UserProfile
from app.models.project import ensure_default_project
from app.oauth_providers import get_project_provider_credentials
from app.webhooks.emitter import WebhookEmitter


@pytest_asyncio.fixture
async def database():
    url = get_settings().DATABASE_URL
    assert url.endswith("/yesod_foundation_test")
    engine = create_async_engine(url)
    project_b = uuid.uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            Project.__table__.insert().values(id=project_b, name="Boundary test")
        )
    sessions = async_sessionmaker(engine, class_=ProjectAsyncSession, expire_on_commit=False)
    yield engine, sessions, project_b
    # Only this fixture's isolated project/data; no default-project deletion.
    async with engine.begin() as connection:
        for table in (
            "audit.auth_events",
            "audit.login_history",
            "webhook_deliveries",
            "deleted_users",
        ):
            await connection.execute(
                text(f"DELETE FROM {table} WHERE project_id = :id"), {"id": project_b}
            )
        await connection.execute(delete(User.__table__).where(User.project_id == project_b))
        await connection.execute(delete(Project.__table__).where(Project.id == project_b))
    await engine.dispose()


@pytest.mark.asyncio
async def test_application_session_rejects_omitted_project():
    with pytest.raises(ValueError, match="project"):
        async with async_session_maker() as db:
            await db.execute(select(User))


@pytest.mark.asyncio
async def test_default_seed_is_idempotent_under_concurrency(database):
    engine, _, _ = database

    async def seed():
        async with engine.begin() as connection:
            return await ensure_default_project(connection)

    assert await asyncio.gather(*(seed() for _ in range(6))) == [DEFAULT_PROJECT_ID] * 6
    async with engine.connect() as connection:
        assert (
            await connection.scalar(
                select(func.count()).select_from(Project).where(Project.id == DEFAULT_PROJECT_ID)
            )
            == 1
        )


async def login(db, identity, email, provider="google"):
    return await _find_or_create_user(
        db, provider, identity, email, "Boundary user", None, None, None
    )


@pytest.mark.asyncio
async def test_identity_and_email_never_merge_across_projects(database):
    _, sessions, project_b = database
    identity = str(uuid.uuid4())
    email = f"{identity}@example.invalid"
    async with (
        sessions(project_id=DEFAULT_PROJECT_ID) as first,
        sessions(project_id=project_b) as second,
    ):
        user_a = await login(first, identity, email)
        user_b = await login(second, identity, email)
        assert user_a.id != user_b.id
        assert user_a.project_id == DEFAULT_PROJECT_ID
        assert user_b.project_id == project_b
        assert (await login(second, identity, email)).id == user_b.id
        same_email = await login(second, str(uuid.uuid4()), email, "github")
        assert same_email.id != user_b.id
        assert (
            len((await second.scalars(select(UserEmail).where(UserEmail.email == email))).all())
            == 2
        )
        await first.delete(user_a)
        await first.commit()


@pytest.mark.asyncio
async def test_scoped_reads_and_relationships_hide_other_project(database):
    _, sessions, project_b = database
    async with sessions(project_id=project_b) as other:
        target = await login(other, str(uuid.uuid4()), "read-boundary@example.invalid")
    async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
        assert await db.get(User, target.id) is None
        assert await db.scalar(select(User.id).where(User.id == target.id)) is None
        assert (
            await db.scalar(select(func.count()).select_from(User).where(User.id == target.id)) == 0
        )
        alias = aliased(User)
        assert await db.scalar(select(alias).where(alias.id == target.id)) is None
        assert (
            await db.scalar(
                select(OAuthAccount)
                .options(selectinload(OAuthAccount.user))
                .where(OAuthAccount.user_id == target.id)
            )
            is None
        )
        assert await db.scalar(select(Project).where(Project.id == project_b)) is None


@pytest.mark.asyncio
async def test_scope_is_immutable_and_raw_bulk_bypasses_are_rejected(database):
    _, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        with pytest.raises(AttributeError):
            db.sync_session.project_id = DEFAULT_PROJECT_ID
        for statement in [
            text("SELECT * FROM users"),
            select(User.__table__),
            update(User).values(project_id=DEFAULT_PROJECT_ID),
            delete(User),
        ]:
            with pytest.raises(ValueError, match="Project sessions"):
                await db.execute(statement)
        for method in ("bulk_save_objects", "bulk_insert_mappings", "bulk_update_mappings"):
            with pytest.raises(ValueError, match="Bulk writes"):
                getattr(db.sync_session, method)([])


@pytest.mark.asyncio
async def test_foreign_objects_and_ownership_changes_are_rejected(database):
    _, sessions, project_b = database
    async with sessions(project_id=project_b) as other:
        user = User()
        other.add(user)
        await other.commit()
    async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
        with pytest.raises(ValueError, match="different project"):
            db.add(user)
    async with sessions(project_id=project_b) as db:
        user = await db.get(User, user.id)
        user.project_id = DEFAULT_PROJECT_ID
        with pytest.raises(ValueError, match="different project"):
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["delete", "update"])
async def test_forged_detached_objects_cannot_mutate_other_project(database, operation):
    _, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        user = User()
        db.add(user)
        await db.commit()
        target_id = user.id
    forged = User(id=target_id, project_id=DEFAULT_PROJECT_ID, created_at=datetime.now(UTC))
    make_transient_to_detached(forged)
    async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
        if operation == "delete":
            await db.delete(forged)
        else:
            db.add(forged)
            forged.created_at = datetime.now(UTC) + timedelta(days=1)
        with pytest.raises(StaleDataError):
            await db.commit()
        await db.rollback()
    async with sessions(project_id=project_b) as db:
        assert await db.get(User, target_id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [UserProfile, UserEmail, OAuthAccount, RefreshToken])
async def test_database_rejects_cross_project_user_relationship(database, model):
    _, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        target = User()
        db.add(target)
        await db.commit()
    values = {"user_id": target.id}
    if model is UserEmail:
        values["email"] = "cross-project@example.invalid"
    if model is OAuthAccount:
        values.update(provider="google", provider_user_id=str(uuid.uuid4()))
    if model is RefreshToken:
        values.update(
            token_hash=str(uuid.uuid4()), expires_at=datetime.now(UTC) + timedelta(days=1)
        )
    async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
        db.add(model(**values))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
async def test_tokens_and_api_reject_project_substitution(database):
    _, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        user = User()
        db.add(user)
        await db.commit()
        refresh = await create_refresh_token(db, user.id)
    async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
        assert await validate_refresh_token(db, refresh) is None

    async def default_db():
        async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
            yield db

    app.dependency_overrides[get_db] = default_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Both genuine foreign-project and falsely default-labelled user tokens fail.
            for token_project in (project_b, DEFAULT_PROJECT_ID):
                token = create_access_token(
                    str(user.id), "other@example.invalid", project_id=token_project
                )
                response = await client.get(
                    f"/api/v1/users/me?project_id={project_b}",
                    headers={"Authorization": f"Bearer {token}", "X-Project-ID": str(project_b)},
                )
                assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_default_connection_settings_do_not_serve_other_projects(database):
    _, _, project_b = database
    settings = get_settings()
    assert get_project_provider_credentials(settings, "google", project_id=DEFAULT_PROJECT_ID)[0]
    with pytest.raises(ValueError, match="project"):
        get_project_provider_credentials(settings, "google", project_id=project_b)
    with pytest.raises(TypeError):
        get_project_provider_credentials(settings, "google")
    assert (
        await WebhookEmitter.emit_user_event("user.created", uuid.uuid4(), project_id=project_b)
        is None
    )


@pytest.mark.asyncio
async def test_postgres_rls_for_non_bypass_role(database):
    engine, sessions, project_b = database
    role = f"project_test_{uuid.uuid4().hex}"
    async with sessions(project_id=project_b) as db:
        user = User()
        db.add(user)
        await db.commit()
    async with engine.begin() as connection:
        await connection.execute(text(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS"))
        await connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        await connection.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON users TO {role}"))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {role}"))
            await connection.execute(text("SELECT set_config('yesod.project_id', '', true)"))
            assert await connection.scalar(select(func.count()).select_from(User)) == 0
            await connection.execute(
                text("SELECT set_config('yesod.project_id', :id, true)"), {"id": str(project_b)}
            )
            assert await connection.scalar(select(func.count()).select_from(User)) == 1
        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {role}"))
            await connection.execute(
                text("SELECT set_config('yesod.project_id', :id, true)"),
                {"id": str(DEFAULT_PROJECT_ID)},
            )
            result = await connection.execute(
                update(User).where(User.id == user.id).values(created_at=datetime.now(UTC))
            )
            assert result.rowcount == 0
        with pytest.raises(Exception, match="row-level security"):
            async with engine.begin() as connection:
                await connection.execute(text(f"SET LOCAL ROLE {role}"))
                await connection.execute(
                    text("SELECT set_config('yesod.project_id', :id, true)"),
                    {"id": str(DEFAULT_PROJECT_ID)},
                )
                await connection.execute(
                    User.__table__.insert().values(id=uuid.uuid4(), project_id=project_b)
                )
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP OWNED BY {role}"))
            await connection.execute(text(f"DROP ROLE {role}"))


@pytest.mark.asyncio
async def test_admin_consumers_hide_and_do_not_revoke_other_project(database):
    engine, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        user = await login(db, str(uuid.uuid4()), "admin-other@example.invalid")
        await create_refresh_token(db, user.id)
        token = await db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
        token_id = token.id
        await AuditLogger.log_login(db, user.id, "google", True)
        await AuditLogger.log_event(db, AuthEventType.LOGIN_SUCCESS, user.id)
    env = os.environ.copy()
    env["DATABASE_URL"] = get_settings().DATABASE_URL.replace("+asyncpg", "+psycopg2")
    script = """
import db
from sqlalchemy import text
user_id, token_id, project_b = __import__('sys').argv[1:]
assert user_id not in db.get_users()['ID'].astype(str).tolist()
assert db.get_user_oauth_accounts(user_id).empty
assert db.get_sessions(user_id).empty
assert token_id not in db.get_sessions()['ID'].astype(str).tolist()
assert db.revoke_all_user_sessions(user_id) == 0
assert db.revoke_session(token_id) is False
assert isinstance(db.get_stats()['total_users'], int)
assert isinstance(db.get_table_info()['users']['row_count'], int)
assert isinstance(db.get_deleted_users().shape[0], int)
assert user_id not in db.get_login_history()["User ID"].astype(str).tolist()
assert user_id not in db.get_auth_events()["User ID"].astype(str).tolist()
assert isinstance(db.get_audit_stats()['events_24h'], int)
with db.Session() as session:
    try:
        session.execute(text('SELECT 1'), {'project_id': project_b})
    except ValueError:
        pass
    else:
        raise AssertionError('admin scope substitution accepted')
db.engine.dispose()
"""
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-c", script, str(user.id), str(token_id), str(project_b)],
        cwd=Path(__file__).resolve().parents[2] / "admin",
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    async with engine.connect() as connection:
        assert (
            await connection.scalar(
                select(RefreshToken.is_revoked).where(RefreshToken.id == token_id)
            )
            is False
        )


@pytest.mark.asyncio
async def test_auth_helpers_reject_unscoped_session(database):
    engine, _, _ = database
    async with async_sessionmaker(engine)() as db:
        with pytest.raises(ValueError, match="project-scoped"):
            await login(db, str(uuid.uuid4()), "unscoped@example.invalid")
        with pytest.raises(ValueError, match="project-scoped"):
            await create_refresh_token(db, uuid.uuid4())
        with pytest.raises(ValueError, match="project-scoped"):
            await validate_refresh_token(db, "unscoped-fixture")


@pytest.mark.asyncio
async def test_metrics_counts_only_default_project(database):
    engine, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        user = User()
        db.add(user)
        await db.commit()
    async with engine.connect() as connection:
        expected = await connection.scalar(
            select(func.count()).select_from(User).where(User.project_id == DEFAULT_PROJECT_ID)
        )

    async def default_db():
        async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
            yield db

    app.dependency_overrides[get_db] = default_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/metrics")
            assert response.status_code == 200
            assert f"yesod_users_total {expected}\n" in response.text
            assert (
                "yesod_logins_24h" in response.text
                or "yesod_auth_events_24h" in response.text
                or expected == 0
            )
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_migration_preserves_existing_data_and_seeds_empty_database():
    """Own second disposable database: exercise empty ->006 data ->007 twice."""
    from sqlalchemy.engine import make_url

    source_url = make_url(get_settings().DATABASE_URL)
    assert source_url.database == "yesod_foundation_test"
    name = f"yesod_project_migration_{uuid.uuid4().hex}"
    maintenance = create_async_engine(source_url, isolation_level="AUTOCOMMIT")
    target_url = source_url.set(database=name)
    migrated = create_async_engine(target_url)
    user_id = uuid.uuid4()
    token_id = uuid.uuid4()
    deleted_id = uuid.uuid4()
    retained_tables = (
        "users",
        "user_profiles",
        "user_emails",
        "oauth_accounts",
        "refresh_tokens",
        "deleted_users",
        "webhook_deliveries",
        "audit.login_history",
        "audit.auth_events",
    )
    before_rows = {}
    env = os.environ.copy()
    env["DATABASE_URL"] = target_url.render_as_string(hide_password=False)

    async def upgrade(revision):
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    try:
        async with maintenance.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
        await upgrade("006")
        async with migrated.begin() as connection:
            await connection.execute(text("INSERT INTO users(id) VALUES (:id)"), {"id": user_id})
            await connection.execute(
                text(
                    "INSERT INTO user_emails(id,user_id,email) VALUES (:id,:uid,'preserved@example.invalid')"
                ),
                {"id": uuid.uuid4(), "uid": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO refresh_tokens(id,user_id,token_hash,is_revoked,expires_at) VALUES (:id,:uid,'preserved-test-hash',true,NOW())"
                ),
                {"id": token_id, "uid": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO user_profiles(user_id,display_name,avatar_url) "
                    "VALUES (:uid,'Preserved profile','https://example.invalid/profile.png')"
                ),
                {"uid": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO oauth_accounts(id,user_id,provider,provider_user_id,provider_display_name,"
                    "provider_avatar_url,provider_email,access_token,refresh_token) "
                    "VALUES (:id,:uid,'google','retained-identity','Provider profile',"
                    "'https://example.invalid/provider.png','provider@example.invalid',"
                    "'synthetic-access-fixture','synthetic-refresh-fixture')"
                ),
                {"id": uuid.uuid4(), "uid": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO refresh_tokens(id,user_id,token_hash,is_revoked,expires_at) "
                    "VALUES (:id,:uid,'preserved-active-test-hash',false,NOW() + INTERVAL '1 day')"
                ),
                {"id": uuid.uuid4(), "uid": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO deleted_users(id,email_backup,display_name_backup,purge_at,oauth_providers) "
                    "VALUES (:id,'deleted@example.invalid','Deleted profile',NOW()+INTERVAL '30 days','[\"google\"]')"
                ),
                {"id": deleted_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO webhook_deliveries(id,event_id,event_type,endpoint_id,endpoint_url,status,"
                    "http_status,error_message,attempt_count,latency_ms,completed_at) "
                    "VALUES (:id,:event,'user.deleted','retained-endpoint','https://example.invalid/webhook',"
                    "'failed',503,'fixture-unavailable',3,123,NOW())"
                ),
                {"id": uuid.uuid4(), "event": uuid.uuid4()},
            )
            await connection.execute(
                text(
                    "INSERT INTO audit.login_history(user_id,provider,ip_address,user_agent,success,failure_reason) "
                    "VALUES (:uid,'google','127.0.0.1','retained-fixture',false,'fixture-failure')"
                ),
                {"uid": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO audit.auth_events(user_id,event_type,details,ip_address,user_agent) "
                    "VALUES (:uid,'account_deleted',CAST(:details AS jsonb),'127.0.0.1','retained-fixture')"
                ),
                {"uid": deleted_id, "details": '{"request_id":"retained-fixture","deleted":true}'},
            )
            # Capture every original column, including timestamps and revocation state.
            for table in retained_tables:
                rows = (
                    (await connection.execute(text(f"SELECT to_jsonb(t) FROM {table} t")))
                    .scalars()
                    .all()
                )
                assert rows, f"retention fixture missing for {table}"
                before_rows[table] = sorted(rows, key=lambda row: str(sorted(row.items())))
        await upgrade("head")
        await upgrade("head")
        async with migrated.connect() as connection:
            assert await connection.scalar(select(func.count()).select_from(Project)) == 1
            for table in retained_tables:
                rows = (
                    await connection.execute(
                        text(
                            f"SELECT to_jsonb(t) - 'project_id' AS original, project_id FROM {table} t"
                        )
                    )
                ).all()
                assert (
                    sorted((row.original for row in rows), key=lambda row: str(sorted(row.items())))
                    == before_rows[table]
                ), table
                assert all(row.project_id == DEFAULT_PROJECT_ID for row in rows), table
                assert (
                    await connection.scalar(
                        text(
                            f"SELECT count(*) FROM {table} WHERE project_id IS NULL OR project_id <> :project_id"
                        ),
                        {"project_id": DEFAULT_PROJECT_ID},
                    )
                    == 0
                )
            assert (
                await connection.scalar(select(User.project_id).where(User.id == user_id))
                == DEFAULT_PROJECT_ID
            )
            assert (
                await connection.scalar(select(UserEmail.email).where(UserEmail.user_id == user_id))
                == "preserved@example.invalid"
            )
            assert (
                await connection.scalar(
                    select(RefreshToken.is_revoked).where(RefreshToken.id == token_id)
                )
                is True
            )
            assert (
                await connection.scalar(
                    select(RefreshToken.project_id).where(RefreshToken.id == token_id)
                )
                == DEFAULT_PROJECT_ID
            )
    finally:
        await migrated.dispose()
        async with maintenance.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        await maintenance.dispose()


@pytest.mark.asyncio
async def test_database_rejects_missing_row_ownership(database):
    engine, _, _ = database
    with pytest.raises(IntegrityError, match="project_id"):
        async with engine.begin() as connection:
            await connection.execute(User.__table__.insert().values(id=uuid.uuid4()))


@pytest.mark.parametrize("invalid_project", [None, "", "not-a-uuid"])
def test_application_session_rejects_invalid_project(invalid_project):
    with pytest.raises(ValueError, match="project_id"):
        async_session_maker(project_id=invalid_project)


@pytest.mark.asyncio
@pytest.mark.parametrize("interface", ["async", "sync"])
async def test_public_project_connection_rejects_low_level_access(database, interface):
    """Defensive contract only: never execute SQL through a returned connection."""
    _, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        with pytest.raises(ValueError, match="project"):
            if interface == "async":
                await db.connection()
            else:
                await db.run_sync(lambda session: session.connection())


@pytest.mark.asyncio
@pytest.mark.parametrize("event_kind", ["login", "event"])
async def test_audit_rejects_user_from_another_project(database, event_kind):
    engine, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        user = User()
        db.add(user)
        await db.commit()
        user_id = user.id
    try:
        async with sessions(project_id=DEFAULT_PROJECT_ID) as db:
            with pytest.raises(ValueError, match="project"):
                if event_kind == "login":
                    await AuditLogger.log_login(db, user_id, "google", True)
                else:
                    await AuditLogger.log_event(db, AuthEventType.LOGIN_SUCCESS, user_id)
        async with engine.connect() as connection:
            for table in ("audit.login_history", "audit.auth_events"):
                assert (
                    await connection.scalar(
                        text(f"SELECT count(*) FROM {table} WHERE user_id = :id"), {"id": user_id}
                    )
                    == 0
                )
    finally:
        # Cleanup only this fixture's rows, including any pre-fix rejected-contract artifact.
        async with engine.begin() as connection:
            for table in ("audit.login_history", "audit.auth_events"):
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :id"), {"id": user_id}
                )


@pytest.mark.asyncio
async def test_audit_keeps_history_after_user_deletion(database):
    engine, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        user = User()
        db.add(user)
        await db.commit()
        user_id = user.id
        await AuditLogger.log_login(db, user_id, "google", True)
        await AuditLogger.log_event(db, AuthEventType.ACCOUNT_DELETED, user_id)
        await db.delete(user)
        await db.commit()
        await AuditLogger.log_login(db, None, "google", False)
    async with engine.connect() as connection:
        for table in ("audit.login_history", "audit.auth_events"):
            rows = (
                (
                    await connection.execute(
                        text(f"SELECT project_id FROM {table} WHERE user_id = :id"), {"id": user_id}
                    )
                )
                .scalars()
                .all()
            )
            assert rows == [project_b]


@pytest.mark.asyncio
async def test_audit_helpers_accept_only_fixed_operations(database):
    from app.db.project import read_audit_counts, write_audit

    _, sessions, project_b = database
    async with sessions(project_id=project_b) as db:
        with pytest.raises(ValueError, match="fixed project audit"):
            await write_audit(db, text("SELECT 1"), {})
        with pytest.raises(ValueError, match="Unknown project audit"):
            await read_audit_counts(db, "unknown")
        await AuditLogger.log_login(db, None, "google", False)
        assert await read_audit_counts(db, "login_history") == [(False, 1)]
