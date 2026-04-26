"""Integration test to verify all migrations run successfully on clean PostgreSQL database."""

import os

import pytest
from sqlalchemy import create_engine, text


def _postgres_proof_url() -> str:
    db_url = os.getenv("TEST_DATABASE_URL")
    if not db_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL migration proof")
    if not db_url.startswith("postgresql"):
        pytest.skip("PostgreSQL is required for migration integration test")
    return db_url


def _drop_public_tables(engine):
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                """
            )
        )
        tables = [row[0] for row in result]

        for table in tables:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
        conn.commit()


LATEST_MIGRATION = "0106_chat_message_delivery_recovery_fields"


def _assert_latest_schema(conn):
    result = conn.execute(text("SELECT version_num FROM alembic_version"))
    version = result.scalar()
    assert version == LATEST_MIGRATION

    result = conn.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'users'
              AND indexname = 'uq_users_max_user_id_nonempty'
            """
        )
    )
    indexdef = result.scalar()
    assert indexdef is not None
    assert "WHERE" in indexdef
    assert "max_user_id IS NOT NULL" in indexdef
    assert "btrim" in indexdef

    recovery_columns = {
        "delivery_attempts",
        "delivery_locked_at",
        "delivery_next_retry_at",
        "delivery_last_attempt_at",
        "delivery_dead_at",
    }
    result = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'chat_messages'
              AND column_name = ANY(:column_names)
            """
        ),
        {"column_names": list(recovery_columns)},
    )
    assert {row[0] for row in result} == recovery_columns

    result = conn.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'chat_messages'
              AND indexname = 'ix_chat_messages_max_delivery_recovery'
            """
        )
    )
    recovery_index = result.scalar()
    assert recovery_index is not None
    assert "delivery_next_retry_at" in recovery_index
    assert "delivery_locked_at" in recovery_index


@pytest.mark.no_db_cleanup
def test_migrations_on_clean_postgres():
    """
    Test that all migrations run successfully on a clean PostgreSQL database.

    This test verifies that:
    1. All migration files are valid Python
    2. Migrations can be applied in sequence
    3. All tables, indexes, and constraints are created correctly
    4. No SQLite-specific code breaks on PostgreSQL
    """
    db_url = _postgres_proof_url()

    # Convert to sync URL (remove +asyncpg if present)
    sync_db_url = db_url.replace("+asyncpg", "")

    # Create engine and drop/recreate all tables to simulate clean DB
    engine = create_engine(sync_db_url)

    _drop_public_tables(engine)

    # Now run migrations from scratch
    from backend.migrations.runner import _discover_migrations, upgrade_to_head

    try:
        upgrade_to_head(sync_db_url)
    except Exception as e:
        pytest.fail(f"Migrations failed on clean PostgreSQL database: {e}")

    # Verify that migrations created expected tables
    with engine.connect() as conn:
        # Check that alembic_version table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'alembic_version'
            )
        """))
        assert result.scalar(), "alembic_version table was not created"

        # Check that some core tables exist
        core_tables = [
            "users",
            "recruiters",
            "cities",
            "slots",
            "message_templates",
            "candidate_channel_identities",
            "requisitions",
            "applications",
            "application_events",
            "application_idempotency_keys",
            "interviews",
            "recruiter_tasks",
            "dedup_candidate_pairs",
            "ai_decision_records",
            "candidate_access_tokens",
            "candidate_access_sessions",
            "candidate_web_campaigns",
            "candidate_web_public_intakes",
            "message_threads",
            "messages",
            "message_deliveries",
            "provider_receipts",
            "candidate_contact_policies",
            "channel_health_registry",
        ]

        for table_name in core_tables:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = '{table_name}'
                )
            """))
            assert result.scalar(), f"Core table '{table_name}' was not created"

        latest_revision = _discover_migrations()[-1].revision
        assert latest_revision == LATEST_MIGRATION
        _assert_latest_schema(conn)

    engine.dispose()


@pytest.mark.no_db_cleanup
def test_migrations_upgrade_from_0103_to_recovered_0105_postgres():
    db_url = _postgres_proof_url()

    sync_db_url = db_url.replace("+asyncpg", "")
    engine = create_engine(sync_db_url)
    _drop_public_tables(engine)

    from backend.migrations.runner import (
        _assert_schema_create_privilege,
        _discover_migrations,
        _ensure_version_storage,
        _set_current_revision,
        upgrade_to_head,
    )

    migrations = _discover_migrations()
    with engine.begin() as conn:
        _assert_schema_create_privilege(conn)
        _ensure_version_storage(conn)

    for migration in migrations:
        if migration.revision in {"0104_candidate_web_public_intake", "0105_unique_users_max_user_id"}:
            break
        with engine.begin() as conn:
            upgrade = getattr(migration.module, "upgrade")
            upgrade(conn)
            _set_current_revision(conn, migration.revision)

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "0103_persistent_application_idempotency_keys"

    upgrade_to_head(sync_db_url)

    with engine.connect() as conn:
        _assert_latest_schema(conn)
        result = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'candidate_web_public_intakes'
                )
                """
            )
        )
        assert result.scalar()
    engine.dispose()
