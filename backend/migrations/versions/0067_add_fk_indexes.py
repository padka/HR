"""Add missing indexes on FK columns for query performance."""

from __future__ import annotations

import sqlalchemy as sa

revision = "0067_add_fk_indexes"
down_revision = "0066_add_city_experts_executives"


def upgrade(conn):
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_slots_city_id ON slots (city_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_cities_responsible_recruiter_id ON cities (responsible_recruiter_id)"
        )
    )


def downgrade(conn):
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_city_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_cities_responsible_recruiter_id"))
