"""Prevent duplicate reservations per recruiter."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists


revision = "0007_prevent_duplicate_slot_reservations"
down_revision = "0006_add_slots_recruiter_start_index"
branch_labels = None
depends_on = None


UNIQUE_INDEX_NAME = "uq_slots_candidate_recruiter_active"
LOCKS_TABLE = "slot_reservation_locks"
LOCKS_INDEX = "uq_slot_reservation_locks_key"


def upgrade(conn: Connection) -> None:
    """Create slot_reservation_locks table and unique index on slots."""

    # Если базовые таблицы не созданы — выходим
    if not table_exists(conn, "slots") or not table_exists(conn, "recruiters"):
        return

    def _create_locks_table() -> None:
        metadata = sa.MetaData()
        # Reflect referenced tables so ForeignKey targets are known to the metadata
        sa.Table("slots", metadata, autoload_with=conn)
        sa.Table("recruiters", metadata, autoload_with=conn)
        locks = sa.Table(
            LOCKS_TABLE,
            metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("slot_id", sa.Integer, sa.ForeignKey("slots.id", ondelete="CASCADE"), nullable=False),
            sa.Column("candidate_tg_id", sa.BigInteger, nullable=False),
            sa.Column("recruiter_id", sa.Integer, sa.ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reservation_date", sa.Date, nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sqlite_autoincrement=True,
        )
        metadata.create_all(conn, tables=[locks])

    # Если таблица уже есть — повторно не создаём
    if not table_exists(conn, LOCKS_TABLE):
        _create_locks_table()

    # Создаём уникальный индекс на locks
    if not index_exists(conn, LOCKS_TABLE, LOCKS_INDEX):
        metadata = sa.MetaData()
        locks = sa.Table(LOCKS_TABLE, metadata, autoload_with=conn)
        sa.Index(
            LOCKS_INDEX,
            locks.c.candidate_tg_id,
            locks.c.recruiter_id,
            locks.c.reservation_date,
            unique=True,
        ).create(conn)

    # Создаём уникальный индекс на slots
    if not index_exists(conn, "slots", UNIQUE_INDEX_NAME):
        metadata = sa.MetaData()
        slots = sa.Table("slots", metadata, autoload_with=conn)
        pending_or_booked = sa.func.lower(slots.c.status).in_(("pending", "booked"))
        sa.Index(
            UNIQUE_INDEX_NAME,
            slots.c.candidate_tg_id,
            slots.c.recruiter_id,
            unique=True,
            postgresql_where=pending_or_booked,
            sqlite_where=pending_or_booked,
        ).create(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop slot_reservation_locks table and unique index."""
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {LOCKS_INDEX}"))
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {UNIQUE_INDEX_NAME}"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {LOCKS_TABLE}"))
