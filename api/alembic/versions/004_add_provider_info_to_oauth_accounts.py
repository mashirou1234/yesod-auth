"""Add provider info to oauth_accounts.

Store original display name, avatar, email from OAuth provider
for recovery purposes.

Revision ID: 004
Revises: 003
Create Date: 2026-01-31
"""

import sqlalchemy as sa

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "oauth_accounts",
        sa.Column("provider_display_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("provider_avatar_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "oauth_accounts",
        sa.Column("provider_email", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oauth_accounts", "provider_email")
    op.drop_column("oauth_accounts", "provider_avatar_url")
    op.drop_column("oauth_accounts", "provider_display_name")
