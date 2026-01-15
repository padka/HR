"""Link recruiter_users to recruiters profile.

Revision ID: 0038_recruiter_user_profile_link
Revises: 0037_recruiter_portal_auth
Create Date: 2025-12-10 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists


revision = "0038_recruiter_user_profile_link"
down_revision = "0037_recruiter_portal_auth"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if table_exists(conn, "recruiter_users") and not column_exists(conn, "recruiter_users", "recruiter_profile_id"):
        conn.execute(sa.text("ALTER TABLE recruiter_users ADD COLUMN recruiter_profile_id INTEGER"))
        conn.execute(
            sa.text(
                """
                ALTER TABLE recruiter_users
                ADD CONSTRAINT fk_recruiter_users_profile
                FOREIGN KEY (recruiter_profile_id)
                REFERENCES recruiters (id)
                ON DELETE SET NULL
                """
            )
        )
        if not index_exists(conn, "recruiter_users", "ix_recruiter_users_recruiter_profile_id"):
            conn.execute(
                sa.text(
                    "CREATE INDEX IF NOT EXISTS ix_recruiter_users_recruiter_profile_id "
                    "ON recruiter_users (recruiter_profile_id)"
                )
            )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if table_exists(conn, "recruiter_users") and column_exists(conn, "recruiter_users", "recruiter_profile_id"):
        conn.execute(sa.text("ALTER TABLE recruiter_users DROP CONSTRAINT IF EXISTS fk_recruiter_users_profile"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_recruiter_users_recruiter_profile_id"))
        conn.execute(sa.text("ALTER TABLE recruiter_users DROP COLUMN recruiter_profile_id"))
