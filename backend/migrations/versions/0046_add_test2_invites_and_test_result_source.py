"""Add Test2 invite links and TestResult source column."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists, index_exists

revision = "0046_add_test2_invites_and_test_result_source"
down_revision = "0045_add_candidate_responsible_recruiter"
branch_labels = None
depends_on = None


TABLE_INVITES = "test2_invites"


def upgrade(conn: Connection) -> None:
    if table_exists(conn, "test_results") and not column_exists(conn, "test_results", "source"):
        conn.execute(
            sa.text("ALTER TABLE test_results ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'bot'")
        )
        conn.execute(sa.text("UPDATE test_results SET source = 'bot' WHERE source IS NULL"))

    if table_exists(conn, TABLE_INVITES):
        return

    conn.execute(
        sa.text(
            f"""
            CREATE TABLE {TABLE_INVITES} (
                id INTEGER PRIMARY KEY,
                candidate_id INTEGER NOT NULL,
                token_hash VARCHAR(64) NOT NULL,
                status VARCHAR(16) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                opened_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                created_by_admin VARCHAR(100),
                CONSTRAINT fk_test2_invite_candidate_id
                    FOREIGN KEY(candidate_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT uq_test2_invite_token_hash UNIQUE(token_hash)
            )
            """
        )
    )

    if not index_exists(conn, TABLE_INVITES, "ix_test2_invites_candidate_id"):
        conn.execute(
            sa.text(
                "CREATE INDEX ix_test2_invites_candidate_id ON test2_invites (candidate_id)"
            )
        )

    if not index_exists(conn, TABLE_INVITES, "ix_test2_invites_status"):
        conn.execute(
            sa.text(
                "CREATE INDEX ix_test2_invites_status ON test2_invites (status)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if table_exists(conn, TABLE_INVITES):
        conn.execute(sa.text(f"DROP TABLE {TABLE_INVITES}"))

    if conn.dialect.name == "sqlite":
        return

    if table_exists(conn, "test_results") and column_exists(conn, "test_results", "source"):
        conn.execute(sa.text("ALTER TABLE test_results DROP COLUMN source"))
