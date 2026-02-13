"""Add AI Copilot cache and request log tables.

These tables back the recruiter-facing AI Copilot (cached JSON outputs) and
store lightweight request audit rows (no raw prompt/PII).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0074_add_ai_outputs_and_logs"
down_revision = "0073_unify_test_question_sources"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "ai_outputs"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_outputs (
                        id INTEGER PRIMARY KEY,
                        scope_type TEXT NOT NULL,
                        scope_id INTEGER NOT NULL,
                        kind TEXT NOT NULL,
                        input_hash TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        CONSTRAINT uq_ai_outputs_scope_kind_hash
                            UNIQUE (scope_type, scope_id, kind, input_hash)
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_outputs (
                        id SERIAL PRIMARY KEY,
                        scope_type VARCHAR(16) NOT NULL,
                        scope_id INTEGER NOT NULL,
                        kind VARCHAR(64) NOT NULL,
                        input_hash CHAR(64) NOT NULL,
                        payload_json JSONB NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        CONSTRAINT uq_ai_outputs_scope_kind_hash
                            UNIQUE (scope_type, scope_id, kind, input_hash)
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_outputs_scope_kind "
                "ON ai_outputs (scope_type, scope_id, kind)"
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_outputs_expires_at "
                "ON ai_outputs (expires_at)"
            )
        )

    if not table_exists(conn, "ai_request_logs"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_request_logs (
                        id INTEGER PRIMARY KEY,
                        principal_type TEXT NOT NULL,
                        principal_id INTEGER NOT NULL,
                        scope_type TEXT NOT NULL,
                        scope_id INTEGER NOT NULL,
                        kind TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        latency_ms INTEGER NOT NULL,
                        tokens_in INTEGER NOT NULL,
                        tokens_out INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        error_code TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_request_logs (
                        id SERIAL PRIMARY KEY,
                        principal_type VARCHAR(16) NOT NULL,
                        principal_id INTEGER NOT NULL,
                        scope_type VARCHAR(16) NOT NULL,
                        scope_id INTEGER NOT NULL,
                        kind VARCHAR(64) NOT NULL,
                        provider VARCHAR(32) NOT NULL,
                        model VARCHAR(80) NOT NULL,
                        latency_ms INTEGER NOT NULL,
                        tokens_in INTEGER NOT NULL,
                        tokens_out INTEGER NOT NULL,
                        status VARCHAR(16) NOT NULL,
                        error_code VARCHAR(64) NOT NULL DEFAULT '',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_request_logs_principal_day "
                "ON ai_request_logs (principal_type, principal_id, created_at)"
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_request_logs_scope "
                "ON ai_request_logs (scope_type, scope_id, kind)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(sa.text("DROP TABLE IF EXISTS ai_request_logs"))
    conn.execute(sa.text("DROP TABLE IF EXISTS ai_outputs"))

