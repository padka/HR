from __future__ import annotations

import pytest

from scripts.run_migrations import resolve_migration_database_url


def test_production_requires_migrations_database_url() -> None:
    with pytest.raises(RuntimeError, match="MIGRATIONS_DATABASE_URL"):
        resolve_migration_database_url(
            {
                "ENVIRONMENT": "production",
                "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/recruitsmart",
            }
        )


def test_production_uses_migrations_database_url() -> None:
    url, source = resolve_migration_database_url(
        {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/recruitsmart",
            "MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://migrator:pass@localhost:5432/recruitsmart",
        }
    )
    assert source == "MIGRATIONS_DATABASE_URL"
    assert url.startswith("postgresql+asyncpg://migrator:")


def test_non_production_falls_back_to_database_url() -> None:
    url, source = resolve_migration_database_url(
        {
            "ENVIRONMENT": "development",
            "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/recruitsmart",
        }
    )
    assert source == "DATABASE_URL"
    assert url.startswith("postgresql+asyncpg://app:")


def test_migrations_database_url_has_priority_in_non_production() -> None:
    url, source = resolve_migration_database_url(
        {
            "ENVIRONMENT": "staging",
            "DATABASE_URL": "postgresql+asyncpg://app:pass@localhost:5432/recruitsmart",
            "MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://migrator:pass@localhost:5432/recruitsmart",
        }
    )
    assert source == "MIGRATIONS_DATABASE_URL"
    assert url.startswith("postgresql+asyncpg://migrator:")


def test_non_production_without_any_database_url_fails() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        resolve_migration_database_url({"ENVIRONMENT": "development"})
