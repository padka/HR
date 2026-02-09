"""Add bot runtime configs table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0072_add_bot_runtime_configs"
down_revision = "0071_add_slot_pending_candidate_status"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "bot_runtime_configs",
        metadata,
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    metadata.create_all(conn)


def downgrade(conn: Connection) -> None:
    conn.execute(sa.text("DROP TABLE IF EXISTS bot_runtime_configs"))
