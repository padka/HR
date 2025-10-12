"""Add indexes for candidate and auto message lookups."""

from __future__ import annotations

from typing import Tuple

try:  # pragma: no cover - optional dependency when running without Alembic
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
except ModuleNotFoundError:  # pragma: no cover - allow migrations to no-op in lightweight environments
    Operations = MigrationContext = None  # type: ignore[assignment]
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
    engine = getattr(conn, "engine", None)
    standalone_conn = engine.connect() if engine is not None else conn
    # SQLite keeps a global database-level write lock per connection.  When the
    # migration runner already holds a transaction on the provided connection
    # (as happens in tests), opening an additional connection to run the
    # autocommit blocks ends up racing with that lock and raises
    # ``sqlite3.OperationalError: database is locked``.  Reuse the incoming
    # connection in that case so that the schema change executes within the
    # existing transaction.  Other engines (PostgreSQL in production) are fine
    # with the standalone connection and benefit from the concurrent index
    # creation behaviour.
    if engine is not None and engine.dialect.name == "sqlite" and standalone_conn is not conn:
        standalone_conn.close()
        standalone_conn = conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def upgrade(conn: Connection) -> None:
    if Operations is None or MigrationContext is None:  # pragma: no cover - optional dependency guard
        return
    op, context, standalone_conn = _get_operations(conn)

    try:
        dialect_name = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect_name.name if dialect_name is not None else ""
        with context.begin_transaction():
            if dialect_name == "sqlite":
                op.create_index(
                    SLOTS_INDEX_NAME,
                    SLOTS_TABLE,
                    ["candidate_tg_id"],
                    unique=False,
                    postgresql_concurrently=True,
                    if_not_exists=True,
                )
                op.create_index(
                    AUTO_MESSAGES_INDEX_NAME,
                    AUTO_MESSAGES_TABLE,
                    ["target_chat_id"],
                    unique=False,
                    postgresql_concurrently=True,
                    if_not_exists=True,
                )
            else:
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
    if Operations is None or MigrationContext is None:  # pragma: no cover - optional dependency guard
        return
    op, context, standalone_conn = _get_operations(conn)

    try:
        dialect_name = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect_name.name if dialect_name is not None else ""
        with context.begin_transaction():
            if dialect_name == "sqlite":
                op.drop_index(
                    SLOTS_INDEX_NAME,
                    table_name=SLOTS_TABLE,
                    postgresql_concurrently=True,
                )
                op.drop_index(
                    AUTO_MESSAGES_INDEX_NAME,
                    table_name=AUTO_MESSAGES_TABLE,
                    postgresql_concurrently=True,
                )
            else:
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

