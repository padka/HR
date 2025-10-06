"""Add indexes for candidate and auto message lookups."""

from __future__ import annotations

from typing import Tuple

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0009_add_missing_indexes"
down_revision = "0008_add_slot_reminder_jobs"
branch_labels = None
depends_on = None


SLOTS_TABLE = "slots"
AUTO_MESSAGES_TABLE = "auto_messages"
SLOTS_INDEX_NAME = "ix_slots_candidate_tg_id"
AUTO_MESSAGES_INDEX_NAME = "ix_auto_messages_target_chat_id"


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    standalone_conn = conn.engine.connect() if hasattr(conn, "engine") else conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)

    try:
        with context.begin_transaction():
            with context.autocommit_block():
                op.create_index(
                    SLOTS_INDEX_NAME,
                    SLOTS_TABLE,
                    ["candidate_tg_id"],
                    unique=False,
                    postgresql_concurrently=True,
                    if_not_exists=True,
                )

            with context.autocommit_block():
                op.create_index(
                    AUTO_MESSAGES_INDEX_NAME,
                    AUTO_MESSAGES_TABLE,
                    ["target_chat_id"],
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
            with context.autocommit_block():
                op.drop_index(
                    SLOTS_INDEX_NAME,
                    table_name=SLOTS_TABLE,
                    postgresql_concurrently=True,
                )

            with context.autocommit_block():
                op.drop_index(
                    AUTO_MESSAGES_INDEX_NAME,
                    table_name=AUTO_MESSAGES_TABLE,
                    postgresql_concurrently=True,
                )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()

