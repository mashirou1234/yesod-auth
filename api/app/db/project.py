"""Fail-closed application sessions with an immutable project context.

Migrations use engine connections explicitly. Application consumers use this session;
raw SQL/bulk mutations cannot opt out of ownership filtering through execute().
"""

import uuid

from sqlalchemy import event, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, with_loader_criteria

from app.db.base import ProjectOwned


class ProjectSession(Session):
    def __init__(self, *args, project_id=None, **kwargs):
        try:
            self.__project_id = uuid.UUID(str(project_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("A valid project_id is required") from None
        super().__init__(*args, **kwargs)

    def connection(self, *args, **kwargs):
        raise ValueError("Raw connections are unavailable on a project session")

    def bulk_save_objects(self, *args, **kwargs):
        raise ValueError("Bulk writes cannot bypass project ownership")

    def bulk_insert_mappings(self, *args, **kwargs):
        raise ValueError("Bulk writes cannot bypass project ownership")

    def bulk_update_mappings(self, *args, **kwargs):
        raise ValueError("Bulk writes cannot bypass project ownership")

    @property
    def project_id(self):
        return self.__project_id


class ProjectAsyncSession(AsyncSession):
    sync_session_class = ProjectSession

    async def connection(self, *args, **kwargs):
        raise ValueError("Raw connections are unavailable on a project session")


def project_id_of(db):
    session = db.sync_session if isinstance(db, AsyncSession) else db
    if not isinstance(session, ProjectSession):
        raise ValueError("A project-scoped application session is required")
    return session.project_id


@event.listens_for(ProjectSession, "after_begin")
def _transaction_project(session, transaction, connection):
    if connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT set_config('yesod.project_id', :project_id, true)"),
            {"project_id": str(session.project_id)},
        )


@event.listens_for(ProjectSession, "do_orm_execute")
def _scope_query(state):
    if not state.is_orm_statement or not state.is_select:
        raise ValueError("Project sessions require ORM reads and scoped object writes")
    from app.models.project import Project

    project_id = state.session.project_id
    state.statement = state.statement.options(
        with_loader_criteria(
            ProjectOwned, lambda cls: cls.project_id == project_id, include_aliases=True
        ),
        with_loader_criteria(Project, lambda cls: cls.id == project_id, include_aliases=True),
    )


@event.listens_for(ProjectSession, "before_attach")
def _validate_attach(session, obj):
    if (
        isinstance(obj, ProjectOwned)
        and obj.project_id is not None
        and obj.project_id != session.project_id
    ):
        raise ValueError("Object belongs to a different project")


@event.listens_for(ProjectSession, "before_flush")
def _scope_writes(session, flush_context, instances):
    for obj in session.new | session.dirty | session.deleted:
        if not isinstance(obj, ProjectOwned):
            raise ValueError("Project root changes require an administrative connection")
        if obj in session.new and obj.project_id is None:
            obj.project_id = session.project_id
        if obj.project_id != session.project_id:
            raise ValueError("Object belongs to a different project")
        history = inspect(obj).attrs.project_id.history
        if obj not in session.new and history.has_changes():
            raise ValueError("Changing project ownership is forbidden")


# These are the only raw SQL operations accepted by the internal audit consumer.
# No connection or arbitrary caller-supplied SQL is returned by the public session.
_AUDIT_INSERTS = (
    "INSERT INTO audit.login_history "
    "(project_id, user_id, provider, ip_address, user_agent, success, failure_reason) "
    "VALUES (:project_id, :user_id, :provider, :ip_address, :user_agent, :success, :failure_reason)",
    "INSERT INTO audit.auth_events "
    "(project_id, user_id, event_type, details, ip_address, user_agent) "
    "VALUES (:project_id, :user_id, :event_type, CAST(:details AS jsonb), :ip_address, :user_agent)",
)
_AUDIT_COUNTS = {
    "login_history": "SELECT success, COUNT(*) FROM audit.login_history "
    "WHERE project_id = :project_id AND created_at > NOW() - INTERVAL '24 hours' GROUP BY success",
    "auth_events": "SELECT event_type, COUNT(*) FROM audit.auth_events "
    "WHERE project_id = :project_id AND created_at > NOW() - INTERVAL '24 hours' GROUP BY event_type",
}


async def _execute_audit_sql(db, statement, values):
    # Explicit superclass use is private to these fixed audit operations. It is
    # not a public opt-out flag or connection accessor on ProjectSession.
    return await db.run_sync(lambda session: Session.connection(session).execute(statement, values))


async def write_audit(db, statement, values):
    """Validate audit subject ownership before executing one of two fixed INSERTs."""
    from app.models import User

    project_id = project_id_of(db)
    normalized = " ".join(str(statement).split())
    if normalized not in _AUDIT_INSERTS:
        raise ValueError("Only fixed project audit inserts are permitted")
    user_id = values.get("user_id")
    if user_id is not None:
        # The scoped read also locks the live subject until the audit commit.
        # Audit history has no cascading user FK and survives later deletion.
        subject = await db.scalar(
            select(User.id).where(User.id == uuid.UUID(str(user_id))).with_for_update()
        )
        if subject is None:
            raise ValueError("Audit user must belong to the session project")
    await _execute_audit_sql(db, text(normalized), dict(values, project_id=str(project_id)))


async def read_audit_counts(db, kind):
    """Return project-local metrics without exposing raw SQL or a connection."""
    project_id = project_id_of(db)
    if kind not in _AUDIT_COUNTS:
        raise ValueError("Unknown project audit counter")
    result = await _execute_audit_sql(
        db, text(_AUDIT_COUNTS[kind]), {"project_id": str(project_id)}
    )
    return result.fetchall()
