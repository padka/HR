from __future__ import annotations

import importlib

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

migration_0091 = importlib.import_module(
    "backend.migrations.versions.0091_add_hh_integration_foundation"
)
migration_0092 = importlib.import_module(
    "backend.migrations.versions.0092_allow_unbound_hh_vacancy_bindings"
)


def test_hh_foundation_migrations_apply_on_existing_schema() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        conn.execute(sa.text("CREATE TABLE vacancies (id INTEGER PRIMARY KEY)"))

        migration_0091.upgrade(conn)
        migration_0092.upgrade(conn)

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        assert "hh_connections" in tables
        assert "candidate_external_identities" in tables
        assert "external_vacancy_bindings" in tables
        assert "hh_negotiations" in tables
        assert "hh_resume_snapshots" in tables
        assert "hh_sync_jobs" in tables
        assert "hh_webhook_deliveries" in tables

        vacancy_columns = {col["name"] for col in inspector.get_columns("external_vacancy_bindings")}
        assert "vacancy_id" in vacancy_columns
