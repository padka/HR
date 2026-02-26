"""Add HH resume storage, interview-script feedback, and KB document category."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0085_add_interview_script_feedback_and_hh_resume"
down_revision = "0084_allow_intro_day_parallel_slots"
branch_labels = None
depends_on = None


def _add_kb_category_column(conn: Connection) -> None:
    if not table_exists(conn, "knowledge_base_documents"):
        return
    if not column_exists(conn, "knowledge_base_documents", "category"):
        conn.execute(
            sa.text(
                "ALTER TABLE knowledge_base_documents "
                "ADD COLUMN category VARCHAR(64) NOT NULL DEFAULT 'general'"
            )
        )
    if not index_exists(conn, "knowledge_base_documents", "ix_kb_documents_category"):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_kb_documents_category "
                "ON knowledge_base_documents(category)"
            )
        )


def _create_candidate_hh_resumes(conn: Connection) -> None:
    if table_exists(conn, "candidate_hh_resumes"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_hh_resumes (
                    id INTEGER PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    format VARCHAR(16) NOT NULL DEFAULT 'raw_text',
                    resume_json JSON,
                    resume_text TEXT,
                    normalized_json JSON NOT NULL DEFAULT '{}',
                    content_hash VARCHAR(64) NOT NULL DEFAULT '',
                    source_quality_ok BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_hh_resumes (
                    id SERIAL PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    format VARCHAR(16) NOT NULL DEFAULT 'raw_text',
                    resume_json JSON,
                    resume_text TEXT,
                    normalized_json JSON NOT NULL DEFAULT '{}'::json,
                    content_hash VARCHAR(64) NOT NULL DEFAULT '',
                    source_quality_ok BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )

    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_hh_resumes_candidate "
            "ON candidate_hh_resumes(candidate_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_candidate_hh_resumes_content_hash "
            "ON candidate_hh_resumes(content_hash)"
        )
    )


def _create_interview_script_feedback(conn: Connection) -> None:
    if table_exists(conn, "ai_interview_script_feedback"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE ai_interview_script_feedback (
                    id INTEGER PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    principal_type VARCHAR(16) NOT NULL DEFAULT 'recruiter',
                    principal_id INTEGER NOT NULL,
                    helped BOOLEAN,
                    edited BOOLEAN NOT NULL DEFAULT 0,
                    quick_reasons_json JSON NOT NULL DEFAULT '[]',
                    outcome VARCHAR(32) NOT NULL DEFAULT 'unknown',
                    outcome_reason TEXT,
                    idempotency_key VARCHAR(64) NOT NULL,
                    input_redacted_json JSON NOT NULL DEFAULT '{}',
                    output_original_json JSON NOT NULL DEFAULT '{}',
                    output_final_json JSON,
                    labels_json JSON NOT NULL DEFAULT '{}',
                    input_hash VARCHAR(64) NOT NULL DEFAULT '',
                    model VARCHAR(64) NOT NULL DEFAULT '',
                    prompt_version VARCHAR(32) NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE ai_interview_script_feedback (
                    id SERIAL PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    principal_type VARCHAR(16) NOT NULL DEFAULT 'recruiter',
                    principal_id INTEGER NOT NULL,
                    helped BOOLEAN,
                    edited BOOLEAN NOT NULL DEFAULT FALSE,
                    quick_reasons_json JSON NOT NULL DEFAULT '[]'::json,
                    outcome VARCHAR(32) NOT NULL DEFAULT 'unknown',
                    outcome_reason TEXT,
                    idempotency_key VARCHAR(64) NOT NULL,
                    input_redacted_json JSON NOT NULL DEFAULT '{}'::json,
                    output_original_json JSON NOT NULL DEFAULT '{}'::json,
                    output_final_json JSON,
                    labels_json JSON NOT NULL DEFAULT '{}'::json,
                    input_hash VARCHAR(64) NOT NULL DEFAULT '',
                    model VARCHAR(64) NOT NULL DEFAULT '',
                    prompt_version VARCHAR(32) NOT NULL DEFAULT '',
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )

    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_interview_script_feedback_idempotency "
            "ON ai_interview_script_feedback(idempotency_key)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_ai_interview_script_feedback_candidate "
            "ON ai_interview_script_feedback(candidate_id, created_at)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_ai_interview_script_feedback_outcome "
            "ON ai_interview_script_feedback(outcome)"
        )
    )


def upgrade(conn: Connection) -> None:
    _add_kb_category_column(conn)
    _create_candidate_hh_resumes(conn)
    _create_interview_script_feedback(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("DROP TABLE IF EXISTS ai_interview_script_feedback CASCADE"))
        conn.execute(sa.text("DROP TABLE IF EXISTS candidate_hh_resumes CASCADE"))
    else:
        conn.execute(sa.text("DROP TABLE IF EXISTS ai_interview_script_feedback"))
        conn.execute(sa.text("DROP TABLE IF EXISTS candidate_hh_resumes"))
    if conn.dialect.name == "postgresql" and table_exists(conn, "knowledge_base_documents"):
        if index_exists(conn, "knowledge_base_documents", "ix_kb_documents_category"):
            conn.execute(sa.text("DROP INDEX IF EXISTS ix_kb_documents_category"))
        if column_exists(conn, "knowledge_base_documents", "category"):
            conn.execute(sa.text("ALTER TABLE knowledge_base_documents DROP COLUMN category"))
