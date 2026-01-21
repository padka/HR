from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


revision = "0018_slots_candidate_fields"
down_revision = "0018_candidate_report_urls"
branch_labels = None
depends_on = None


TABLE = "slots"


def _column_exists(conn: Connection, column: str) -> bool:
    inspector = inspect(conn)
    return any(col["name"] == column for col in inspector.get_columns(TABLE))


def upgrade(conn: Connection) -> None:
    statements = [
        ("candidate_phone", "ALTER TABLE slots ADD COLUMN candidate_phone VARCHAR(64)"),
        ("candidate_email", "ALTER TABLE slots ADD COLUMN candidate_email VARCHAR(255)"),
        ("candidate_notes", "ALTER TABLE slots ADD COLUMN candidate_notes TEXT"),
        (
            "booking_confirmed",
            "ALTER TABLE slots ADD COLUMN booking_confirmed BOOLEAN NOT NULL DEFAULT FALSE",
        ),
        (
            "cancelled_at",
            "ALTER TABLE slots ADD COLUMN cancelled_at TIMESTAMP WITH TIME ZONE",
        ),
    ]
    for column, statement in statements:
        if _column_exists(conn, column):
            continue
        conn.execute(sa.text(statement))


def downgrade(conn: Connection) -> None:  # pragma: no cover - parity with upgrade
    statements = [
        "candidate_phone",
        "candidate_email",
        "candidate_notes",
        "booking_confirmed",
        "cancelled_at",
    ]
    for column in statements:
        if not _column_exists(conn, column):
            continue
        conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN {column}"))
