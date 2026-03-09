"""Add candidate portal journey sessions and step states."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists

revision = "0095_add_candidate_portal_journey"
down_revision = "0094_add_candidate_chat_archive_state"
branch_labels = None
depends_on = None


def _create_candidate_journey_sessions(conn) -> None:
    if table_exists(conn, "candidate_journey_sessions"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_journey_sessions (
                    id INTEGER PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    journey_key VARCHAR(64) NOT NULL DEFAULT 'candidate_portal',
                    journey_version VARCHAR(32) NOT NULL DEFAULT 'v1',
                    entry_channel VARCHAR(32) NOT NULL DEFAULT 'web',
                    current_step_key VARCHAR(64) NOT NULL DEFAULT 'profile',
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    payload_json JSON,
                    started_at TIMESTAMP NOT NULL,
                    last_activity_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_journey_sessions (
                    id SERIAL PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    journey_key VARCHAR(64) NOT NULL DEFAULT 'candidate_portal',
                    journey_version VARCHAR(32) NOT NULL DEFAULT 'v1',
                    entry_channel VARCHAR(32) NOT NULL DEFAULT 'web',
                    current_step_key VARCHAR(64) NOT NULL DEFAULT 'profile',
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    payload_json JSONB,
                    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMP WITH TIME ZONE
                )
                """
            )
        )

    if not index_exists(
        conn,
        "candidate_journey_sessions",
        "ix_candidate_journey_sessions_candidate_status",
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_candidate_journey_sessions_candidate_status "
                "ON candidate_journey_sessions (candidate_id, status)"
            )
        )


def _create_candidate_journey_step_states(conn) -> None:
    if table_exists(conn, "candidate_journey_step_states"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_journey_step_states (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES candidate_journey_sessions(id) ON DELETE CASCADE,
                    step_key VARCHAR(64) NOT NULL,
                    step_type VARCHAR(32) NOT NULL DEFAULT 'form',
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    payload_json JSON,
                    started_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    CONSTRAINT uq_candidate_journey_step_session_key UNIQUE (session_id, step_key)
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_journey_step_states (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES candidate_journey_sessions(id) ON DELETE CASCADE,
                    step_key VARCHAR(64) NOT NULL,
                    step_type VARCHAR(32) NOT NULL DEFAULT 'form',
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    payload_json JSONB,
                    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMP WITH TIME ZONE,
                    CONSTRAINT uq_candidate_journey_step_session_key UNIQUE (session_id, step_key)
                )
                """
            )
        )

    if not index_exists(
        conn,
        "candidate_journey_step_states",
        "ix_candidate_journey_step_states_session_status",
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_candidate_journey_step_states_session_status "
                "ON candidate_journey_step_states (session_id, status)"
            )
        )


def upgrade(conn: Connection) -> None:
    _create_candidate_journey_sessions(conn)
    _create_candidate_journey_step_states(conn)


def downgrade(conn: Connection) -> None:
    if table_exists(conn, "candidate_journey_step_states"):
        conn.execute(sa.text("DROP TABLE candidate_journey_step_states"))
    if table_exists(conn, "candidate_journey_sessions"):
        conn.execute(sa.text("DROP TABLE candidate_journey_sessions"))
