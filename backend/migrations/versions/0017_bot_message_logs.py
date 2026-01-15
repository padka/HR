"""Create bot_message_logs table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0017_bot_message_logs"
down_revision = "0016_add_slot_timezone"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    metadata = sa.MetaData()
    table = sa.Table(
        "bot_message_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("candidate_tg_id", sa.BigInteger, nullable=True),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("slot_id", sa.Integer, nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    metadata.create_all(conn, tables=[table])


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback support
    conn.execute(sa.text("DROP TABLE IF EXISTS bot_message_logs"))
