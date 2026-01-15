"""Add recruiter portal auth tables and candidate assignment.

Revision ID: 0037_recruiter_portal_auth
Revises: 0036_ensure_candidate_status_enum_values
Create Date: 2025-12-10 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists


revision = "0037_recruiter_portal_auth"
down_revision = "0036_ensure_candidate_status_enum_values"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Create recruiter_users, oauth_accounts and link candidates."""

    if not table_exists(conn, "recruiter_users"):
        conn.execute(
            sa.text(
                """
                CREATE TABLE recruiter_users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    password_hash VARCHAR(255),
                    full_name VARCHAR(160),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    # Add recruiter_profile_id to recruiter_users if missing
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
        if not index_exists(conn, "recruiter_users", "ix_recruiter_users_profile_id"):
            conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_recruiter_users_profile_id ON recruiter_users (recruiter_profile_id)"))

    if not table_exists(conn, "oauth_accounts"):
        conn.execute(
            sa.text(
                """
                CREATE TABLE oauth_accounts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES recruiter_users (id) ON DELETE CASCADE,
                    provider VARCHAR(32) NOT NULL,
                    provider_user_id VARCHAR(255) NOT NULL,
                    access_token VARCHAR(512),
                    refresh_token VARCHAR(512),
                    expires_at TIMESTAMP WITH TIME ZONE,
                    CONSTRAINT uq_oauth_provider_user UNIQUE (provider, provider_user_id)
                )
                """
            )
        )

    if table_exists(conn, "oauth_accounts") and not index_exists(conn, "oauth_accounts", "ix_oauth_accounts_user_id"):
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_oauth_accounts_user_id ON oauth_accounts (user_id)"))

    if table_exists(conn, "users") and not column_exists(conn, "users", "assigned_recruiter_id"):
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN assigned_recruiter_id INTEGER"))
        conn.execute(
            sa.text(
                """
                ALTER TABLE users
                ADD CONSTRAINT fk_users_assigned_recruiter
                FOREIGN KEY (assigned_recruiter_id)
                REFERENCES recruiter_users (id)
                ON DELETE SET NULL
                """
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_users_assigned_recruiter_id ON users (assigned_recruiter_id)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - destructive downgrade
    """Downgrade support for new tables."""

    if table_exists(conn, "users") and column_exists(conn, "users", "assigned_recruiter_id"):
        conn.execute(sa.text("ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_assigned_recruiter"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_assigned_recruiter_id"))
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN assigned_recruiter_id"))

    if table_exists(conn, "oauth_accounts"):
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_oauth_accounts_user_id"))
        conn.execute(sa.text("DROP TABLE IF EXISTS oauth_accounts CASCADE"))

    if table_exists(conn, "recruiter_users"):
        if column_exists(conn, "recruiter_users", "recruiter_profile_id"):
            conn.execute(sa.text("ALTER TABLE recruiter_users DROP CONSTRAINT IF EXISTS fk_recruiter_users_profile"))
            conn.execute(sa.text("DROP INDEX IF EXISTS ix_recruiter_users_profile_id"))
            conn.execute(sa.text("ALTER TABLE recruiter_users DROP COLUMN recruiter_profile_id"))
        conn.execute(sa.text("DROP TABLE IF EXISTS recruiter_users CASCADE"))
