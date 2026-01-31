"""Refactor users table for loose coupling design.

- users: ID only
- user_profiles: display_name, avatar_url
- user_emails: email management
- deleted_users: soft delete support

Revision ID: 003
Revises: 002
Create Date: 2026-01-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_profiles table
    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Create user_emails table
    op.create_table(
        "user_emails",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_emails_email", "user_emails", ["email"], unique=True)
    op.create_index("ix_user_emails_user_id", "user_emails", ["user_id"])

    # Create deleted_users table
    op.create_table(
        "deleted_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_backup", sa.String(255), nullable=False),
        sa.Column("display_name_backup", sa.String(255), nullable=True),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("purge_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("oauth_providers", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deleted_users_purge_at", "deleted_users", ["purge_at"])

    # Migrate existing data from users to new tables
    op.execute("""
        INSERT INTO user_profiles (user_id, display_name, avatar_url, updated_at)
        SELECT id, display_name, avatar_url, updated_at
        FROM users
    """)

    op.execute("""
        INSERT INTO user_emails (user_id, email, is_primary, created_at)
        SELECT id, email, true, created_at
        FROM users
    """)

    # Drop old columns from users table
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "email")
    op.drop_column("users", "display_name")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "updated_at")


def downgrade() -> None:
    # Add columns back to users
    op.add_column(
        "users",
        sa.Column("email", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Migrate data back
    op.execute("""
        UPDATE users u
        SET email = ue.email,
            display_name = up.display_name,
            avatar_url = up.avatar_url,
            updated_at = up.updated_at
        FROM user_emails ue, user_profiles up
        WHERE u.id = ue.user_id AND ue.is_primary = true
          AND u.id = up.user_id
    """)

    # Make email not nullable and add index
    op.alter_column("users", "email", nullable=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Drop new tables
    op.drop_index("ix_deleted_users_purge_at", table_name="deleted_users")
    op.drop_table("deleted_users")
    op.drop_index("ix_user_emails_user_id", table_name="user_emails")
    op.drop_index("ix_user_emails_email", table_name="user_emails")
    op.drop_table("user_emails")
    op.drop_table("user_profiles")
