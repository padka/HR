"""Background tasks for admin UI.

This module contains periodic tasks that run in the background:
- Stalled candidate detection (marks candidates waiting >24h for slots)
- Hourly digest of waiting candidates for recruiters
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from backend.core.db import async_session
from backend.core.error_handler import resilient_task
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter
from backend.domain.repositories import get_active_recruiters_for_city

logger = logging.getLogger(__name__)


async def mark_stalled_waiting_candidates() -> int:
    """Mark candidates waiting for slot >24h as stalled.

    Returns:
        Number of candidates marked as stalled
    """
    threshold = datetime.now(timezone.utc) - timedelta(hours=24)

    async with async_session() as session:
        # Find candidates in waiting_slot status for >24h
        stmt = (
            select(User)
            .where(
                User.candidate_status == CandidateStatus.WAITING_SLOT,
                User.status_changed_at <= threshold,
            )
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        if not candidates:
            logger.debug("No stalled waiting candidates found")
            return 0

        # Update their status to stalled
        candidate_ids = [c.id for c in candidates]
        update_stmt = (
            update(User)
            .where(User.id.in_(candidate_ids))
            .values(
                candidate_status=CandidateStatus.STALLED_WAITING_SLOT,
                status_changed_at=datetime.now(timezone.utc),
            )
        )
        await session.execute(update_stmt)
        await session.commit()

        logger.info(
            "Marked %d candidates as stalled (waiting >24h): %s",
            len(candidate_ids),
            candidate_ids,
        )
        return len(candidate_ids)


async def get_waiting_candidates_summary() -> Dict[str, List[Dict]]:
    """Get summary of candidates waiting for slots, grouped by city.

    Returns:
        Dictionary mapping city_name to list of candidate info dicts
        Each candidate dict contains: id, name, status, waiting_since, telegram_id
    """
    async with async_session() as session:
        stmt = (
            select(User)
            .where(
                User.candidate_status.in_([
                    CandidateStatus.WAITING_SLOT,
                    CandidateStatus.STALLED_WAITING_SLOT,
                ])
            )
            .order_by(User.status_changed_at.asc())
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        # Group by city (using city name from User)
        by_city: Dict[str, List[Dict]] = defaultdict(list)
        for candidate in candidates:
            city_name = candidate.city or "Unknown"

            waiting_time = (
                datetime.now(timezone.utc) - candidate.status_changed_at
                if candidate.status_changed_at
                else timedelta(0)
            )

            by_city[city_name].append({
                "id": candidate.id,
                "telegram_id": candidate.telegram_id,
                "name": candidate.full_name or f"User {candidate.telegram_id}",
                "status": candidate.candidate_status.value if candidate.candidate_status else "unknown",
                "waiting_since": candidate.status_changed_at,
                "waiting_hours": int(waiting_time.total_seconds() / 3600),
            })

        return dict(by_city)


@resilient_task(
    task_name="periodic_stalled_candidate_checker",
    retry_on_error=True,
    retry_delay=300.0,  # 5 minutes
    log_errors=True,
)
async def periodic_stalled_candidate_checker(interval_hours: int = 1) -> None:
    """Run stalled candidate checker periodically.

    Args:
        interval_hours: How often to check (default: every hour)
    """
    logger.info("Started periodic stalled candidate checker (interval: %dh)", interval_hours)

    while True:
        try:
            logger.debug("Running stalled candidate check...")
            marked_count = await mark_stalled_waiting_candidates()
            if marked_count > 0:
                logger.warning("Marked %d candidates as stalled", marked_count)
            else:
                logger.debug("No stalled candidates found")
        except asyncio.CancelledError:
            logger.info("Stalled candidate checker cancelled, shutting down")
            raise
        except Exception as exc:
            logger.error("Error in periodic stalled candidate checker: %s", exc, exc_info=True)
            # Continue running even if one check fails

        # Sleep for the interval
        try:
            await asyncio.sleep(interval_hours * 3600)
        except asyncio.CancelledError:
            logger.info("Stalled candidate checker cancelled during sleep")
            raise
