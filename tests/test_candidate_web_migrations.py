from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

migration_0104 = importlib.import_module("backend.migrations.versions.0104_candidate_web_public_intake")
migration_0105 = importlib.import_module("backend.migrations.versions.0105_unique_users_max_user_id")


def _create_0104_prereqs(conn: sa.Connection) -> None:
    conn.execute(sa.text("CREATE TABLE cities (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE recruiters (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, max_user_id VARCHAR(64))"))
    conn.execute(sa.text("CREATE TABLE candidate_access_sessions (id BIGINT PRIMARY KEY)"))


def test_candidate_web_intake_migration_declares_production_chain() -> None:
    assert migration_0104.revision == "0104_candidate_web_public_intake"
    assert migration_0104.down_revision == "0103_persistent_application_idempotency_keys"
    assert migration_0105.revision == "0105_unique_users_max_user_id"
    assert migration_0105.down_revision == "0104_candidate_web_public_intake"


def test_candidate_web_intake_migration_applies_additive_schema_on_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        _create_0104_prereqs(conn)

        migration_0104.upgrade(conn)
        migration_0104.upgrade(conn)

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        assert {"candidate_web_campaigns", "candidate_web_public_intakes"}.issubset(tables)

        campaign_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("candidate_web_campaigns")
        }
        intake_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("candidate_web_public_intakes")
        }
        intake_indexes = {index["name"] for index in inspector.get_indexes("candidate_web_public_intakes")}

        assert "uq_candidate_web_campaigns_slug" in campaign_constraints
        assert {
            "uq_candidate_web_public_intakes_poll",
            "uq_candidate_web_public_intakes_provider_token",
            "uq_candidate_web_public_intakes_handoff",
        }.issubset(intake_constraints)
        assert {
            "ix_candidate_web_public_intakes_campaign_id",
            "ix_candidate_web_public_intakes_campaign_status",
            "ix_candidate_web_public_intakes_provider_status",
            "ix_candidate_web_public_intakes_candidate",
            "ix_candidate_web_public_intakes_expires",
        }.issubset(intake_indexes)


def test_unique_max_user_id_migration_blocks_nonempty_duplicates_only() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, max_user_id VARCHAR(64))"))

        migration_0105.upgrade(conn)
        migration_0105.upgrade(conn)

        indexes = {index["name"] for index in inspect(conn).get_indexes("users")}
        assert "uq_users_max_user_id_nonempty" in indexes

        conn.execute(
            sa.text(
                """
                INSERT INTO users (id, max_user_id)
                VALUES (1, NULL), (2, NULL), (3, ''), (4, ''), (5, 'max-1')
                """
            )
        )
        with pytest.raises(IntegrityError):
            conn.execute(sa.text("INSERT INTO users (id, max_user_id) VALUES (6, 'max-1')"))
