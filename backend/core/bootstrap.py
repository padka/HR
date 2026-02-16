"""Application bootstrap helpers ensuring the database is ready."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.core.db import init_models, sync_engine, sync_session
from backend.domain.base import Base
from backend.domain.default_data import DEFAULT_CITIES, default_recruiters
from backend.domain.models import City, Recruiter
import backend.domain.ai.models  # noqa: F401 - register AI/KB tables for metadata create_all
import backend.domain.simulator.models  # noqa: F401 - register simulator tables for metadata create_all
import backend.domain.detailization.models  # noqa: F401 - register reporting tables for metadata create_all

logger = logging.getLogger(__name__)

_bootstrap_lock = asyncio.Lock()
_bootstrap_complete = False


async def ensure_database_ready() -> None:
    """Apply migrations and ensure baseline data exists."""

    global _bootstrap_complete
    if _bootstrap_complete:
        return

    async with _bootstrap_lock:
        if _bootstrap_complete:
            return

        logger.info("Applying database migrations")
        await init_models()

        await asyncio.to_thread(_ensure_schema)
        await asyncio.to_thread(_seed_defaults)

        _bootstrap_complete = True
        logger.info("Database ready")


def _ensure_schema() -> None:
    """Create any tables that might be missing from the metadata."""

    try:
        Base.metadata.create_all(bind=sync_engine)
    except SQLAlchemyError:
        logger.exception("Failed to ensure ORM metadata tables exist")
        raise


def _seed_defaults() -> None:
    """Populate essential reference data for a fresh installation."""

    try:
        with sync_session() as session:
            created = False

            created |= _seed_cities(session)
            created |= _seed_recruiters(session)

            if created:
                session.commit()
    except SQLAlchemyError:
        logger.exception("Failed to seed default data")
        raise


def _seed_cities(session: Session) -> bool:
    existing = {name for name in session.execute(select(City.name)).scalars()}
    payloads = [
        City(name=row["name"], tz=row.get("tz", "Europe/Moscow"), active=True)
        for row in DEFAULT_CITIES
        if row["name"] not in existing
    ]
    if not payloads:
        return False
    session.add_all(payloads)
    logger.info("Seeded %s default cities", len(payloads))
    return True


def _seed_recruiters(session: Session) -> bool:
    payloads = default_recruiters()
    if not payloads:
        return False

    existing = {name for name in session.execute(select(Recruiter.name)).scalars()}
    to_create = [
        Recruiter(
            name=row["name"],
            tz=row.get("tz", "Europe/Moscow"),
            telemost_url=row.get("telemost_url"),
            active=bool(row.get("active", True)),
        )
        for row in payloads
        if row["name"] not in existing
    ]
    if not to_create:
        return False
    session.add_all(to_create)
    logger.info("Seeded %s default recruiters", len(to_create))
    return True


__all__ = ["ensure_database_ready"]
