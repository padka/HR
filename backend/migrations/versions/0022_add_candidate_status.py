"""Add candidate_status and status_changed_at to users table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0022_add_candidate_status"
down_revision = "0021_update_slot_unique_index_include_purpose"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Add candidate status tracking to users table."""
    dialect = conn.dialect.name

    if dialect == "postgresql":
        # Create enum type for PostgreSQL
        conn.execute(sa.text("""
            CREATE TYPE candidate_status_enum AS ENUM (
                'test1_completed',
                'interview_scheduled',
                'interview_confirmed',
                'interview_declined',
                'test2_sent',
                'test2_completed',
                'test2_failed',
                'intro_day_scheduled',
                'intro_day_confirmed_preliminary',
                'intro_day_declined_invitation',
                'intro_day_confirmed_day_of',
                'intro_day_declined_day_of',
                'hired',
                'not_hired'
            )
        """))

        # Add columns with enum type
        conn.execute(sa.text("""
            ALTER TABLE users ADD COLUMN candidate_status candidate_status_enum
        """))
    else:
        # For SQLite, use VARCHAR
        conn.execute(sa.text("""
            ALTER TABLE users ADD COLUMN candidate_status VARCHAR(50)
        """))

    # Add status_changed_at column (works for both SQLite and PostgreSQL)
    conn.execute(sa.text("""
        ALTER TABLE users ADD COLUMN status_changed_at TIMESTAMP
    """))

    # Create index on candidate_status for efficient filtering
    if dialect == "postgresql":
        conn.execute(sa.text("""
            CREATE INDEX ix_users_candidate_status ON users (candidate_status)
        """))
    else:
        # SQLite also supports indexes
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_users_candidate_status ON users (candidate_status)
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback support
    """Remove candidate status tracking."""
    dialect = conn.dialect.name

    if dialect == "sqlite":
        # SQLite doesn't support DROP COLUMN easily, would need table recreation
        return

    # Drop index
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_candidate_status"))

    # Drop columns
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN status_changed_at"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN candidate_status"))

    # Drop enum type (PostgreSQL only)
    if dialect == "postgresql":
        conn.execute(sa.text("DROP TYPE IF EXISTS candidate_status_enum"))
