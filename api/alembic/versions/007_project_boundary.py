"""Associate existing data with a default project and enforce ownership.

Revision ID: 007
Revises: 006
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None
DEFAULT_ID = "00000000-0000-4000-8000-000000000001"
TABLES = (
    (None, "users"),
    (None, "user_profiles"),
    (None, "user_emails"),
    (None, "oauth_accounts"),
    (None, "refresh_tokens"),
    (None, "deleted_users"),
    (None, "webhook_deliveries"),
    ("audit", "login_history"),
    ("audit", "auth_events"),
)


def upgrade():
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
    )
    op.execute(
        f"INSERT INTO projects (id, name) VALUES ('{DEFAULT_ID}', 'Default') ON CONFLICT (id) DO NOTHING"
    )
    for schema, table in TABLES:
        op.add_column(
            table, sa.Column("project_id", UUID(as_uuid=True), nullable=True), schema=schema
        )
        qualified = f"{schema}.{table}" if schema else table
        op.execute(f"UPDATE {qualified} SET project_id = '{DEFAULT_ID}' WHERE project_id IS NULL")
        op.alter_column(table, "project_id", nullable=False, schema=schema)
        op.create_foreign_key(
            f"fk_{table}_project",
            table,
            "projects",
            ["project_id"],
            ["id"],
            source_schema=schema,
            referent_schema="public",
        )
        op.create_index(f"ix_{table}_project_id", table, ["project_id"], schema=schema)
        op.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
        predicate = "project_id = NULLIF(current_setting('yesod.project_id', true), '')::uuid"
        op.execute(
            f"CREATE POLICY project_boundary ON {qualified} USING ({predicate}) WITH CHECK ({predicate})"
        )
    op.create_unique_constraint("uq_users_project_id", "users", ["project_id", "id"])
    for table in ("user_profiles", "user_emails", "oauth_accounts", "refresh_tokens"):
        op.create_foreign_key(
            f"fk_{table}_project_user",
            table,
            "users",
            ["project_id", "user_id"],
            ["project_id", "id"],
            ondelete="CASCADE",
        )
    op.drop_index("ix_user_emails_email", table_name="user_emails")
    op.create_index("ix_user_emails_email", "user_emails", ["email"])
    op.drop_index("ix_oauth_accounts_provider_user", table_name="oauth_accounts")
    op.create_unique_constraint(
        "uq_oauth_project_identity",
        "oauth_accounts",
        ["project_id", "provider", "provider_user_id"],
    )


def downgrade():
    raise RuntimeError(
        "Project ownership cannot be discarded safely; restore a verified backup instead"
    )
