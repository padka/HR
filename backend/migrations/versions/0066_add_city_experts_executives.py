"""Add CityExpert and CityExecutive."""

from __future__ import annotations

import sqlalchemy as sa

revision = "0066_add_city_experts_executives"
down_revision = "0065_add_intro_day_template_to_city"


def upgrade(conn):
    # CityExpert
    conn.execute(
        sa.text(
            """
            CREATE TABLE city_experts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                city_id INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
    )
    
    # CityExecutive
    conn.execute(
        sa.text(
            """
            CREATE TABLE city_executives (
                id SERIAL PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                city_id INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
    )


def downgrade(conn):
    conn.execute(sa.text("DROP TABLE city_executives"))
    conn.execute(sa.text("DROP TABLE city_experts"))
