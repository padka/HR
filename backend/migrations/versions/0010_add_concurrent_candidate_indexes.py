"""Add concurrent indexes for candidate and auto message lookups."""

from __future__ import annotations

from typing import Tuple

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0010_add_concurrent_candidate_indexes"
down_revision = "0009_add_missing_indexes"
branch_labels = None
depends_on = None


INDEX_DEFINITIONS = (
    ("slots", "ix_slots_candidate_tg_id", ["candidate_tg_id"]),
    ("auto_messages", "ix_auto_messages_target_chat_id", ["target_chat_id"]),
)


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    standalone_conn = conn.engine.connect() if hasattr(conn, "engine") else conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)

    try:
        with context.begin_transaction():
            for table_name, index_name, columns in INDEX_DEFINITIONS:
                with context.autocommit_block():
                    op.create_index(
                        index_name,
                        table_name,
                        columns,
                        unique=False,
                        postgresql_concurrently=True,
                        if_not_exists=True,
                    )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry only
    op, context, standalone_conn = _get_operations(conn)

    try:
        with context.begin_transaction():
            for table_name, index_name, _ in INDEX_DEFINITIONS:
                with context.autocommit_block():
                    op.drop_index(
                        index_name,
                        table_name=table_name,
                        postgresql_concurrently=True,
                        if_exists=True,
                    )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
