"""Introduce notification and callback logs, extend slot status column."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.engine import Connection


revision = "0010_add_notification_logs"
down_revision = "0009_add_missing_indexes"
branch_labels = None
depends_on = None
metadata = sa.MetaData()


def _create_tables(conn: Connection) -> None:
    notification_logs = sa.Table(
        "notification_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["slots.id"],
            name="fk_notification_logs_booking_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("type", "booking_id", name="uq_notification_logs_type_booking"),
    )

    callback_logs = sa.Table(
        "telegram_callback_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("callback_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("callback_id", name="uq_telegram_callback_logs_callback_id"),
    )

    metadata.create_all(conn, tables=[notification_logs, callback_logs], checkfirst=True)


def _drop_tables(conn: Connection) -> None:
    metadata.reflect(conn, only=["notification_logs", "telegram_callback_logs"])
    metadata.drop_all(
        conn,
        tables=[metadata.tables[name] for name in ["telegram_callback_logs", "notification_logs"] if name in metadata.tables],
        checkfirst=True,
    )


def upgrade(conn: Connection) -> None:
    dialect_name = conn.dialect.name
    if dialect_name != "sqlite":
        conn.execute(text("ALTER TABLE slots ALTER COLUMN status TYPE VARCHAR(32)"))

    _create_tables(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    dialect_name = conn.dialect.name
    _drop_tables(conn)
    if dialect_name != "sqlite":
        conn.execute(text("ALTER TABLE slots ALTER COLUMN status TYPE VARCHAR(20)"))
