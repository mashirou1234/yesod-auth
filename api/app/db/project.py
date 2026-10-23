"""Fail-closed application sessions with an immutable project context.

Migrations use engine connections explicitly. Application consumers use this session;
raw SQL/bulk mutations cannot opt out of ownership filtering through execute().
"""

import uuid

from sqlalchemy import event, inspect, text
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


async def write_audit(db, statement, values):
    """Narrow raw SQL consumer: internal audit INSERTs always bind session ownership."""
    project_id = project_id_of(db)
    values = dict(values, project_id=str(project_id))
    # Do not expose arbitrary raw SQL on the application session itself.
    connection = await db.connection()
    await connection.execute(statement, values)
