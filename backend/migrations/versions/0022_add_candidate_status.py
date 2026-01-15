"""Add candidate_status and status_changed_at to users table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists

revision = "0022_add_candidate_status"
down_revision = "0021_update_slot_unique_index_include_purpose"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Add candidate status tracking to users table."""

    # Check if enum type exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'candidate_status_enum'
        )
    """))
    enum_exists = result.scalar()

    if not enum_exists:
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

    # Add columns if they don't exist
    if not column_exists(conn, "users", "candidate_status"):
        conn.execute(sa.text("""
            ALTER TABLE users ADD COLUMN candidate_status candidate_status_enum
        """))

    if not column_exists(conn, "users", "status_changed_at"):
        conn.execute(sa.text("""
            ALTER TABLE users ADD COLUMN status_changed_at TIMESTAMP WITH TIME ZONE
        """))

    # Create index if it doesn't exist
    if not index_exists(conn, "users", "ix_users_candidate_status"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_users_candidate_status ON users (candidate_status)
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback support
    """Remove candidate status tracking."""

    # Drop index
    if index_exists(conn, "users", "ix_users_candidate_status"):
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_candidate_status"))

    # Drop columns
    if column_exists(conn, "users", "status_changed_at"):
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN status_changed_at"))

    if column_exists(conn, "users", "candidate_status"):
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN candidate_status"))

    # Drop enum type
    conn.execute(sa.text("DROP TYPE IF EXISTS candidate_status_enum"))
