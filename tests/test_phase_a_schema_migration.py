from __future__ import annotations

import importlib

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

migration = importlib.import_module(
    "backend.migrations.versions.0102_phase_a_schema_foundation"
)


def _create_legacy_prereqs(conn: sa.Connection) -> None:
    conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE recruiters (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE vacancies (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE cities (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE slot_assignments (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE ai_request_logs (id INTEGER PRIMARY KEY)"))
    conn.execute(sa.text("CREATE TABLE ai_outputs (id INTEGER PRIMARY KEY)"))
    conn.execute(
        sa.text(
            """
            CREATE TABLE candidate_journey_sessions (
                id INTEGER PRIMARY KEY,
                candidate_id INTEGER NOT NULL,
                status VARCHAR(16) NOT NULL,
                session_version INTEGER NOT NULL DEFAULT 1
            )
            """
        )
    )


def test_phase_a_migration_declares_all_new_tables() -> None:
    metadata = sa.MetaData()
    tables = migration._build_tables(metadata)

    table_names = {table.name for table in tables}

    assert table_names == {
        "candidate_channel_identities",
        "requisitions",
        "applications",
        "application_events",
        "interviews",
        "recruiter_tasks",
        "dedup_candidate_pairs",
        "ai_decision_records",
        "candidate_access_tokens",
        "candidate_access_sessions",
        "message_threads",
        "messages",
        "message_deliveries",
        "provider_receipts",
        "candidate_contact_policies",
        "channel_health_registry",
    }
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_phase_a_migration_applies_additive_schema_on_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        _create_legacy_prereqs(conn)

        migration.upgrade(conn)
        migration.upgrade(conn)

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "candidate_channel_identities",
            "requisitions",
            "applications",
            "application_events",
            "interviews",
            "recruiter_tasks",
            "dedup_candidate_pairs",
            "ai_decision_records",
            "candidate_access_tokens",
            "candidate_access_sessions",
            "message_threads",
            "messages",
            "message_deliveries",
            "provider_receipts",
            "candidate_contact_policies",
            "channel_health_registry",
        }
        assert expected_tables.issubset(tables)

        journey_columns = {col["name"] for col in inspector.get_columns("candidate_journey_sessions")}
        assert {
            "application_id",
            "last_access_session_id",
            "last_surface",
            "last_auth_method",
        }.issubset(journey_columns)

        application_events_indexes = {idx["name"] for idx in inspector.get_indexes("application_events")}
        assert "ix_application_events_correlation_id" in application_events_indexes

        access_token_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("candidate_access_tokens")
        }
        access_token_indexes = {idx["name"] for idx in inspector.get_indexes("candidate_access_tokens")}
        assert "uq_candidate_access_tokens_token_id" in access_token_constraints
        assert "uq_candidate_access_tokens_token_hash" in access_token_constraints
        assert "uq_candidate_access_tokens_start_param" in access_token_indexes

        contact_policy_indexes = {idx["name"] for idx in inspector.get_indexes("candidate_contact_policies")}
        assert "uq_candidate_contact_policies_candidate_purpose" in contact_policy_indexes
        assert "uq_candidate_contact_policies_candidate_application_purpose" in contact_policy_indexes

        deliveries_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("message_deliveries")
        }
        messages_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("messages")
        }
        assert "uq_message_deliveries_idempotency_key" in deliveries_constraints
        assert "uq_messages_idempotency_key" in messages_constraints

