"""Add vacancies table and vacancy_id to test_questions."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0078_add_vacancies"
down_revision = "0077_add_detailization_entries"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    # --- vacancies table ---
    if not table_exists(conn, "vacancies"):
        if conn.dialect.name == "sqlite":
            conn.execute(sa.text("""
                CREATE TABLE vacancies (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    slug VARCHAR(80) NOT NULL,
                    city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    description TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
        else:
            conn.execute(sa.text("""
                CREATE TABLE vacancies (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    slug VARCHAR(80) NOT NULL,
                    city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))
        conn.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_vacancy_slug ON vacancies(slug)"
        ))
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_vacancies_city_id ON vacancies(city_id)"
        ))
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_vacancies_active ON vacancies(is_active)"
        ))

    # --- vacancy_id column on test_questions ---
    try:
        conn.execute(sa.text(
            "ALTER TABLE test_questions ADD COLUMN vacancy_id INTEGER"
        ))
    except Exception:
        pass  # column already exists
    try:
        if conn.dialect.name != "sqlite":
            conn.execute(sa.text(
                "ALTER TABLE test_questions ADD CONSTRAINT fk_test_questions_vacancy "
                "FOREIGN KEY (vacancy_id) REFERENCES vacancies(id) ON DELETE SET NULL"
            ))
    except Exception:
        pass
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_test_questions_vacancy_id ON test_questions(vacancy_id)"
    ))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    conn.execute(sa.text("DROP TABLE IF EXISTS vacancies CASCADE"))
