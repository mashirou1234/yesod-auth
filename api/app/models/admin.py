"""Installation administrator credentials, separate from OAuth consumer users."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminBootstrap(Base):
    __tablename__ = "admin_bootstrap"
    __table_args__ = (CheckConstraint("id = 1", name="admin_bootstrap_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    capability_digest: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
