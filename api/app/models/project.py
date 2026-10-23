"""Project root and concurrency-safe default seed."""

import uuid

from sqlalchemy import String
from sqlalchemy import Uuid as UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import DEFAULT_PROJECT_ID, Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


async def ensure_default_project(connection) -> uuid.UUID:
    """Seed only the reserved default ID; caller owns the administrative transaction."""
    await connection.execute(
        insert(Project)
        .values(id=DEFAULT_PROJECT_ID, name="Default")
        .on_conflict_do_nothing(index_elements=["id"])
    )
    return DEFAULT_PROJECT_ID
