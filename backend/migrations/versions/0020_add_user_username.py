"""Add username field to users table

Revision ID: 0020_add_user_username
Revises: 0019_fix_notification_log_unique_index
Create Date: 2025-11-05
"""

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection

# revision identifiers
revision = "0020_add_user_username"
down_revision = "0019_fix_notification_log_unique_index"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Add username field to users table for direct Telegram chat links."""
    context = MigrationContext.configure(connection=conn)
    op = Operations(context)

    op.add_column(
        "users",
        sa.Column("username", sa.String(length=32), nullable=True)
    )
    # Create index for faster lookups
    op.create_index(
        op.f("ix_users_username"),
        "users",
        ["username"],
        unique=False
    )


def downgrade(conn: Connection) -> None:
    """Remove username field from users table."""
    context = MigrationContext.configure(connection=conn)
    op = Operations(context)

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "username")
