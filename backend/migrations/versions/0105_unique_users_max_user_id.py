"""Enforce one candidate per non-empty MAX user id.

This migration is intentionally narrow. Historical duplicate cleanup must run
before applying it in production; empty and NULL MAX ids remain unrestricted.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists

revision = "0105_unique_users_max_user_id"
down_revision = "0104_candidate_web_public_intake"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_users_max_user_id_nonempty"


def upgrade(conn: Connection) -> None:
    if index_exists(conn, "users", INDEX_NAME):
        return
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text(
                f"CREATE UNIQUE INDEX {INDEX_NAME} "
                "ON users (max_user_id) "
                "WHERE max_user_id IS NOT NULL AND btrim(max_user_id) <> ''"
            )
        )
        return
    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                f"CREATE UNIQUE INDEX {INDEX_NAME} "
                "ON users (max_user_id) "
                "WHERE max_user_id IS NOT NULL AND trim(max_user_id) <> ''"
            )
        )
        return
    conn.execute(sa.text(f"CREATE UNIQUE INDEX {INDEX_NAME} ON users (max_user_id)"))


def downgrade(conn: Connection) -> None:
    """Additive-only policy: keep the integrity guard in place."""
    _ = conn
