"""Add normalized candidate phone column for shared portal lookup."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0099_add_users_phone_normalized"
down_revision = "0098_tg_max_reliability_foundation"
branch_labels = None
depends_on = None


def _normalize_phone(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        return None
    return f"+{digits}"


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "users"):
        return
    if not column_exists(conn, "users", "phone_normalized"):
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN phone_normalized VARCHAR(16)"))
    if not index_exists(conn, "users", "ix_users_phone_normalized"):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_users_phone_normalized "
                "ON users (phone_normalized)"
            )
        )

    rows = conn.execute(sa.text("SELECT id, phone FROM users")).mappings().all()
    for row in rows:
        conn.execute(
            sa.text("UPDATE users SET phone_normalized = :phone_normalized WHERE id = :id"),
            {
                "id": int(row["id"]),
                "phone_normalized": _normalize_phone(row.get("phone")),
            },
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name != "postgresql":
        return
    if index_exists(conn, "users", "ix_users_phone_normalized"):
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_phone_normalized"))
    if column_exists(conn, "users", "phone_normalized"):
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN phone_normalized"))
