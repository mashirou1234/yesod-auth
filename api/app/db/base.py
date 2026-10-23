"""Database base and project ownership shared by scoped models."""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

DEFAULT_PROJECT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


class Base(DeclarativeBase):
    pass


class ProjectOwned:
    """No model default: the explicit project session assigns ownership."""

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )

    @declared_attr.directive
    def __mapper_args__(cls):
        # Include immutable ownership in flush UPDATE/DELETE predicates, including
        # detached objects. This also protects deployments with RLS-bypass roles.
        return {"version_id_col": cls.project_id, "version_id_generator": False}
