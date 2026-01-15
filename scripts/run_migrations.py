#!/usr/bin/env python3
"""
Database migration script.

This script should be run before starting any application services.
It applies all pending Alembic migrations to bring the database schema up to date.

Usage:
    python scripts/run_migrations.py

Environment Variables:
    DATABASE_URL - Database connection string

Exit Codes:
    0 - Success
    1 - Migration failed
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.db import init_models
from backend.core.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Run database migrations."""
    try:
        settings = get_settings()
        logger.info("=" * 60)
        logger.info("Database Migration Script")
        logger.info("=" * 60)
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
