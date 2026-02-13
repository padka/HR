"""Add knowledge base and AI agent chat tables.

The knowledge base stores internal documents (text/markdown) that the AI
Copilot can cite and use for candidate assessments and recruiter questions.

The AI agent chat stores redacted messages for an internal copilot chat UI.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0075_add_kb_and_ai_chat"
down_revision = "0074_add_ai_outputs_and_logs"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "knowledge_base_documents"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE knowledge_base_documents (
                        id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL DEFAULT '',
                        filename TEXT NOT NULL DEFAULT '',
                        mime_type TEXT NOT NULL DEFAULT '',
                        content_text TEXT NOT NULL DEFAULT '',
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_by_type TEXT NOT NULL DEFAULT 'admin',
                        created_by_id INTEGER NOT NULL DEFAULT -1,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE knowledge_base_documents (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL DEFAULT '',
                        filename VARCHAR(255) NOT NULL DEFAULT '',
                        mime_type VARCHAR(80) NOT NULL DEFAULT '',
                        content_text TEXT NOT NULL DEFAULT '',
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_by_type VARCHAR(16) NOT NULL DEFAULT 'admin',
                        created_by_id INTEGER NOT NULL DEFAULT -1,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_kb_documents_active_updated "
                "ON knowledge_base_documents (is_active, updated_at)"
            )
        )

    if not table_exists(conn, "knowledge_base_chunks"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE knowledge_base_chunks (
                        id INTEGER PRIMARY KEY,
                        document_id INTEGER NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content_text TEXT NOT NULL DEFAULT '',
                        content_hash TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMP,
                        CONSTRAINT uq_kb_chunk_doc_index
                            UNIQUE (document_id, chunk_index),
                        FOREIGN KEY(document_id) REFERENCES knowledge_base_documents(id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE knowledge_base_chunks (
                        id SERIAL PRIMARY KEY,
                        document_id INTEGER NOT NULL REFERENCES knowledge_base_documents(id) ON DELETE CASCADE,
                        chunk_index INTEGER NOT NULL,
                        content_text TEXT NOT NULL DEFAULT '',
                        content_hash CHAR(64) NOT NULL DEFAULT '',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        CONSTRAINT uq_kb_chunk_doc_index
                            UNIQUE (document_id, chunk_index)
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_kb_chunks_document "
                "ON knowledge_base_chunks (document_id)"
            )
        )

    if not table_exists(conn, "ai_agent_threads"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_agent_threads (
                        id INTEGER PRIMARY KEY,
                        principal_type TEXT NOT NULL,
                        principal_id INTEGER NOT NULL,
                        title TEXT NOT NULL DEFAULT 'Copilot',
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP,
                        CONSTRAINT uq_ai_agent_threads_principal
                            UNIQUE (principal_type, principal_id)
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_agent_threads (
                        id SERIAL PRIMARY KEY,
                        principal_type VARCHAR(16) NOT NULL,
                        principal_id INTEGER NOT NULL,
                        title VARCHAR(200) NOT NULL DEFAULT 'Copilot',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        CONSTRAINT uq_ai_agent_threads_principal
                            UNIQUE (principal_type, principal_id)
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_agent_threads_principal "
                "ON ai_agent_threads (principal_type, principal_id)"
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_agent_threads_updated "
                "ON ai_agent_threads (updated_at)"
            )
        )

    if not table_exists(conn, "ai_agent_messages"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_agent_messages (
                        id INTEGER PRIMARY KEY,
                        thread_id INTEGER NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user',
                        content_text TEXT NOT NULL DEFAULT '',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        created_at TIMESTAMP,
                        FOREIGN KEY(thread_id) REFERENCES ai_agent_threads(id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE ai_agent_messages (
                        id SERIAL PRIMARY KEY,
                        thread_id INTEGER NOT NULL REFERENCES ai_agent_threads(id) ON DELETE CASCADE,
                        role VARCHAR(16) NOT NULL DEFAULT 'user',
                        content_text TEXT NOT NULL DEFAULT '',
                        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_ai_agent_messages_thread_time "
                "ON ai_agent_messages (thread_id, created_at)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(sa.text("DROP TABLE IF EXISTS ai_agent_messages"))
    conn.execute(sa.text("DROP TABLE IF EXISTS ai_agent_threads"))
    conn.execute(sa.text("DROP TABLE IF EXISTS knowledge_base_chunks"))
    conn.execute(sa.text("DROP TABLE IF EXISTS knowledge_base_documents"))

