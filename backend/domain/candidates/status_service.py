"""Service layer for candidate status management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus, can_transition, is_status_retreat

logger = logging.getLogger(__name__)


class StatusTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""

    pass


async def update_candidate_status(
    telegram_id: int,
    new_status: CandidateStatus,
    *,
    force: bool = False,
    session: Optional[AsyncSession] = None,
) -> bool:
    """Update candidate status with validation.

    Args:
        telegram_id: Telegram ID of the candidate
        new_status: New status to set
        force: If True, skip transition validation (use with caution!)
        session: Optional database session (will create new if not provided)

    Returns:
        True if status was updated, False if candidate not found

    Raises:
        StatusTransitionError: If transition is invalid and force=False
    """
    async def _update(sess: AsyncSession) -> bool:
        user = await sess.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )

        if not user:
            logger.warning(f"Candidate not found: telegram_id={telegram_id}")
            return False

        old_status = user.candidate_status

        if old_status == new_status:
            logger.info(
                "Candidate %s already has status %s; skipping update",
                telegram_id,
                new_status,
            )
            return True

        if old_status and is_status_retreat(old_status, new_status):
            logger.info(
                "Ignoring retrograde status transition for user %s: %s -> %s",
                telegram_id,
                old_status,
                new_status,
            )
            return True

        # Validate transition (unless forced)
        if not force and not can_transition(old_status, new_status):
            raise StatusTransitionError(
                f"Invalid status transition for user {telegram_id}: "
                f"{old_status} -> {new_status}"
            )

        # Update status
        user.candidate_status = new_status
        user.status_changed_at = datetime.now(timezone.utc)

        logger.info(
            f"Status updated for user {telegram_id}: {old_status} -> {new_status}"
        )
        return True

    if session:
        return await _update(session)
    else:
        async with async_session() as sess:
            async with sess.begin():
                result = await _update(sess)
            return result


async def get_candidate_status(telegram_id: int) -> Optional[CandidateStatus]:
    """Get current status of a candidate.

    Args:
        telegram_id: Telegram ID of the candidate

    Returns:
        Current status or None if candidate not found
    """
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )
        return user.candidate_status if user else None


async def set_status_test1_completed(telegram_id: int) -> bool:
    """Set status when candidate completes Test 1."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.TEST1_COMPLETED
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set TEST1_COMPLETED: {e}")
        return False


async def set_status_waiting_slot(telegram_id: int) -> bool:
    """Set status when no free interview slots are available."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.WAITING_SLOT, force=True
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set WAITING_SLOT: {e}")
        return False


async def set_status_interview_scheduled(telegram_id: int) -> bool:
    """Set status when recruiter approves interview slot."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTERVIEW_SCHEDULED
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTERVIEW_SCHEDULED: {e}")
        return False


async def set_status_interview_confirmed(telegram_id: int) -> bool:
    """Set status when candidate confirms interview attendance."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTERVIEW_CONFIRMED
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTERVIEW_CONFIRMED: {e}")
        return False


async def set_status_interview_declined(telegram_id: int) -> bool:
    """Set status when candidate declines interview."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTERVIEW_DECLINED, force=True
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTERVIEW_DECLINED: {e}")
        return False


async def set_status_test2_sent(telegram_id: int) -> bool:
    """Set status when Test 2 is sent after successful interview."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.TEST2_SENT
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set TEST2_SENT: {e}")
        return False


async def set_status_test2_completed(telegram_id: int) -> bool:
    """Set status when candidate completes Test 2."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.TEST2_COMPLETED, force=True
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set TEST2_COMPLETED: {e}")
        return False


async def set_status_test2_failed(telegram_id: int) -> bool:
    """Set status when candidate fails Test 2."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.TEST2_FAILED
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set TEST2_FAILED: {e}")
        return False


async def set_status_intro_day_scheduled(telegram_id: int, *, force: bool = False) -> bool:
    """Set status when intro day is scheduled."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTRO_DAY_SCHEDULED, force=force
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTRO_DAY_SCHEDULED: {e}")
        return False


async def set_status_intro_day_confirmed_preliminary(telegram_id: int, *, force: bool = False) -> bool:
    """Set status when candidate confirms intro day attendance (preliminary)."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY, force=force
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTRO_DAY_CONFIRMED_PRELIMINARY: {e}")
        return False


async def set_status_intro_day_declined_invitation(telegram_id: int) -> bool:
    """Set status when candidate declines intro day invitation."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTRO_DAY_DECLINED_INVITATION
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTRO_DAY_DECLINED_INVITATION: {e}")
        return False


async def set_status_intro_day_confirmed_day_of(telegram_id: int, *, force: bool = False) -> bool:
    """Set status when candidate confirms attendance on intro day (2h before)."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF, force=force
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTRO_DAY_CONFIRMED_DAY_OF: {e}")
        return False


async def set_status_intro_day_declined_day_of(telegram_id: int) -> bool:
    """Set status when candidate declines on intro day (2h before)."""
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.INTRO_DAY_DECLINED_DAY_OF
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set INTRO_DAY_DECLINED_DAY_OF: {e}")
        return False


async def set_status_hired(telegram_id: int, force: bool = False) -> bool:
    """Set status when candidate is hired (manual by recruiter).

    Args:
        telegram_id: Telegram ID of the candidate
        force: If True, allow transition from any status

    Returns:
        True if status was updated
    """
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.HIRED, force=force
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set HIRED: {e}")
        return False


async def set_status_not_hired(telegram_id: int, force: bool = False) -> bool:
    """Set status when candidate is not hired (manual by recruiter).

    Args:
        telegram_id: Telegram ID of the candidate
        force: If True, allow transition from any status

    Returns:
        True if status was updated
    """
    try:
        return await update_candidate_status(
            telegram_id, CandidateStatus.NOT_HIRED, force=force
        )
    except StatusTransitionError as e:
        logger.error(f"Failed to set NOT_HIRED: {e}")
        return False


__all__ = [
    "StatusTransitionError",
    "update_candidate_status",
    "get_candidate_status",
    "set_status_test1_completed",
    "set_status_waiting_slot",
    "set_status_interview_scheduled",
    "set_status_interview_confirmed",
    "set_status_interview_declined",
    "set_status_test2_sent",
    "set_status_test2_completed",
    "set_status_test2_failed",
    "set_status_intro_day_scheduled",
    "set_status_intro_day_confirmed_preliminary",
    "set_status_intro_day_declined_invitation",
    "set_status_intro_day_confirmed_day_of",
    "set_status_intro_day_declined_day_of",
    "set_status_hired",
    "set_status_not_hired",
]
