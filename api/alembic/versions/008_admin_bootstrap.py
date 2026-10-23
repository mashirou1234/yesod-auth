"""Add persistent one-time administrator bootstrap without changing existing data.

Revision ID: 008
Revises: 007
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "administrators",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "admin_bootstrap",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("capability_digest", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("initialized_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="admin_bootstrap_singleton"),
    )
    op.execute("INSERT INTO admin_bootstrap (id) VALUES (1)")


def downgrade():
    raise RuntimeError("Administrator bootstrap state cannot be erased by downgrade")
