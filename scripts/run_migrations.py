#!/usr/bin/env python3
"""
Database migration script.

This script should be run before starting any application services.
It applies all pending Alembic migrations to bring the database schema up to date.

Usage:
    python scripts/run_migrations.py

Environment Variables:
    MIGRATIONS_DATABASE_URL - Dedicated DB URL for migration role (priority)
    DATABASE_URL - Fallback DB URL (non-production only)

Exit Codes:
    0 - Success
    1 - Migration failed
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Mapping, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def resolve_migration_database_url(env: Mapping[str, str] | None = None) -> Tuple[str, str]:
    """Resolve the DB URL for migration runs.

    Priority:
    1) MIGRATIONS_DATABASE_URL
    2) DATABASE_URL (non-production only)

    In production, MIGRATIONS_DATABASE_URL is mandatory to enforce role separation
    between migration (DDL) and app runtime (DML).
    """
    env_map = env or os.environ
    environment = (env_map.get("ENVIRONMENT", "development").strip().lower() or "development")
    migrations_url = env_map.get("MIGRATIONS_DATABASE_URL", "").strip()
    database_url = env_map.get("DATABASE_URL", "").strip()

    if migrations_url:
        return migrations_url, "MIGRATIONS_DATABASE_URL"

    if environment == "production":
        raise RuntimeError(
            "ENVIRONMENT=production requires MIGRATIONS_DATABASE_URL. "
            "Use a dedicated migration role with DDL privileges."
        )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required. "
            "Alternatively set MIGRATIONS_DATABASE_URL explicitly."
        )

    return database_url, "DATABASE_URL"


async def main():
    """Run database migrations."""
    try:
        resolved_url, source = resolve_migration_database_url()
        # Ensure settings/db modules read the migration URL before import-time caching.
        os.environ["DATABASE_URL"] = resolved_url

        from backend.core.settings import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        from backend.core.db import init_models

        logger.info("=" * 60)
        logger.info("Database Migration Script")
        logger.info("=" * 60)
        logger.info(f"Database source: {source}")
        logger.info(f"Database URL: {settings.database_url_sync.split('@')[-1]}")  # Hide credentials
        logger.info("Running migrations...")

        # Run migrations
        await init_models()

        logger.info("✓ Migrations completed successfully")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error("=" * 60)
        logger.error("✗ Migration failed!")
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
