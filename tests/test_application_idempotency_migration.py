from __future__ import annotations

import importlib

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

migration = importlib.import_module(
    "backend.migrations.versions.0103_persistent_application_idempotency_keys"
)


def _create_prereqs(conn: sa.Connection) -> None:
    conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE applications (id BIGINT PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE requisitions (id BIGINT PRIMARY KEY)"))


def test_idempotency_migration_declares_expected_table() -> None:
    metadata = sa.MetaData()
    table = migration._build_table(metadata)

    assert table.name == "application_idempotency_keys"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_idempotency_migration_applies_additive_schema_on_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        _create_prereqs(conn)

        migration.upgrade(conn)
        migration.upgrade(conn)

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        assert "application_idempotency_keys" in tables

        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("application_idempotency_keys")
        }
        indexes = {
            index["name"] for index in inspector.get_indexes("application_idempotency_keys")
        }

        assert "uq_application_idempotency_keys_scope" in unique_constraints
        assert {
            "ix_application_idempotency_keys_candidate_id",
            "ix_application_idempotency_keys_application_id",
            "ix_application_idempotency_keys_requisition_id",
            "ix_application_idempotency_keys_event_id",
            "ix_application_idempotency_keys_correlation_id",
            "ix_application_idempotency_keys_status_created_at",
            "ix_application_idempotency_keys_expires_at",
        }.issubset(indexes)
