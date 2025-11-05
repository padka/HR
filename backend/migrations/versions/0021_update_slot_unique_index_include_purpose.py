"""Update slot unique index to include purpose field

This migration updates the unique index on slots table to prevent duplicate
bookings per candidate+recruiter+purpose combination, instead of just
candidate+recruiter. This allows the same candidate to have both an interview
slot and an intro_day slot with the same recruiter.

Revision ID: 0021_update_slot_unique_index_include_purpose
Revises: 0020_add_user_username
Create Date: 2025-11-05 16:45:00
"""
from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0021_update_slot_unique_index_include_purpose"
down_revision = "0020_add_user_username"
branch_labels = None
depends_on = None


TABLE_NAME = "slots"
OLD_INDEX_NAME = "uq_slots_candidate_recruiter_active"
NEW_INDEX_NAME = "uq_slots_candidate_recruiter_purpose_active"


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    engine = getattr(conn, "engine", None)
    standalone_conn = engine.connect() if engine is not None else conn
    if engine is not None and engine.dialect.name == "sqlite" and standalone_conn is not conn:
        standalone_conn.close()
        standalone_conn = conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)

    try:
        dialect_name = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect_name.name if dialect_name is not None else ""

        with context.begin_transaction():
            # Drop old index
            if dialect_name == "sqlite":
                op.execute(sa.text(f"DROP INDEX IF EXISTS {OLD_INDEX_NAME}"))
                # Create new index with purpose field
                op.execute(
                    sa.text(
                        """
                        CREATE UNIQUE INDEX {name}
                            ON {table} (candidate_tg_id, recruiter_id, purpose)
                         WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
                        """.format(name=NEW_INDEX_NAME, table=TABLE_NAME)
                    )
                )
            else:
                # PostgreSQL
                with context.autocommit_block():
                    op.drop_index(
                        OLD_INDEX_NAME,
                        table_name=TABLE_NAME,
                        postgresql_concurrently=True,
                    )
                where_clause = sa.text(
                    "lower(status) IN ('pending','booked','confirmed_by_candidate')"
                )
                with context.autocommit_block():
                    op.create_index(
                        NEW_INDEX_NAME,
                        TABLE_NAME,
                        ["candidate_tg_id", "recruiter_id", "purpose"],
                        unique=True,
                        postgresql_where=where_clause,
                        postgresql_concurrently=True,
                    )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context, standalone_conn = _get_operations(conn)

    try:
        dialect_name = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect_name.name if dialect_name is not None else ""

        with context.begin_transaction():
            # Drop new index
            if dialect_name == "sqlite":
                op.execute(sa.text(f"DROP INDEX IF EXISTS {NEW_INDEX_NAME}"))
                # Recreate old index without purpose field
                op.execute(
                    sa.text(
                        """
                        CREATE UNIQUE INDEX {name}
                            ON {table} (candidate_tg_id, recruiter_id)
                         WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
                        """.format(name=OLD_INDEX_NAME, table=TABLE_NAME)
                    )
                )
            else:
                # PostgreSQL
                with context.autocommit_block():
                    op.drop_index(
                        NEW_INDEX_NAME,
                        table_name=TABLE_NAME,
                        postgresql_concurrently=True,
                    )
                where_clause = sa.text(
                    "lower(status) IN ('pending','booked','confirmed_by_candidate')"
                )
                with context.autocommit_block():
                    op.create_index(
                        OLD_INDEX_NAME,
                        TABLE_NAME,
                        ["candidate_tg_id", "recruiter_id"],
                        unique=True,
                        postgresql_where=where_clause,
                        postgresql_concurrently=True,
                    )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
