"""Introduce recruiter-to-city link table for managing assignments."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists


revision = "0015_recruiter_city_links"
down_revision = "0015_add_kpi_weekly_table"
branch_labels = None
depends_on = None


TABLE_NAME = "recruiter_cities"


def upgrade(conn: Connection) -> None:
    """Create recruiter_cities table and migrate data from cities.responsible_recruiter_id."""

    # Создаём таблицу recruiter_cities
    if not table_exists(conn, TABLE_NAME):
        conn.execute(sa.text("""
            CREATE TABLE recruiter_cities (
                recruiter_id INTEGER NOT NULL,
                city_id INTEGER NOT NULL,
                PRIMARY KEY (recruiter_id, city_id),
                CONSTRAINT uq_recruiter_city_unique_city UNIQUE (city_id),
                CONSTRAINT fk_recruiter_cities_recruiter_id
                    FOREIGN KEY (recruiter_id) REFERENCES recruiters(id) ON DELETE CASCADE,
                CONSTRAINT fk_recruiter_cities_city_id
                    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
            )
        """))

    # Гарантируем уникальность city_id для корректной UPSERT-логики
    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_recruiter_city_unique_city ON recruiter_cities (city_id)"
        )
    )

    # Мигрируем данные из cities.responsible_recruiter_id, если колонка существует
    if table_exists(conn, "cities") and column_exists(conn, "cities", "responsible_recruiter_id"):
        # Переносим данные
        conn.execute(sa.text("""
            INSERT INTO recruiter_cities (recruiter_id, city_id)
            SELECT responsible_recruiter_id, id
            FROM cities
            WHERE responsible_recruiter_id IS NOT NULL
            ON CONFLICT (city_id) DO NOTHING
        """))

        # Удаляем старую колонку
        conn.execute(sa.text("ALTER TABLE cities DROP COLUMN responsible_recruiter_id"))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Restore cities.responsible_recruiter_id and drop recruiter_cities table."""

    # Добавляем колонку обратно
    if table_exists(conn, "cities") and not column_exists(conn, "cities", "responsible_recruiter_id"):
        conn.execute(sa.text("ALTER TABLE cities ADD COLUMN responsible_recruiter_id INTEGER"))

    # Восстанавливаем данные
    if table_exists(conn, TABLE_NAME):
        conn.execute(sa.text("""
            UPDATE cities
            SET responsible_recruiter_id = rc.recruiter_id
            FROM recruiter_cities rc
            WHERE cities.id = rc.city_id
        """))

        # Удаляем таблицу
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE"))
