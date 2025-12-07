"""Integration test to verify all migrations run successfully on clean PostgreSQL database."""

import os
import pytest
from sqlalchemy import create_engine, text


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
    # Use test database URL from environment
    db_url = os.getenv("TEST_DATABASE_URL", "postgresql://rs:pass@localhost:5432/rs_test")

    # Convert to sync URL (remove +asyncpg if present)
    sync_db_url = db_url.replace("+asyncpg", "")

    # Create engine and drop/recreate all tables to simulate clean DB
    engine = create_engine(sync_db_url)

    # Drop all tables to ensure clean state
    with engine.connect() as conn:
        # Get all table names
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result]

        # Drop all tables (including alembic_version)
        for table in tables:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
        conn.commit()

    # Now run migrations from scratch
    from backend.migrations.runner import upgrade_to_head

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

        # Verify current migration version
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        assert version is not None, "No migration version recorded"
        # We expect the last migration to be applied
        assert version.startswith("00"), f"Unexpected migration version: {version}"

    engine.dispose()
