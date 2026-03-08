from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models import (
    RescheduleRequest,
    RescheduleRequestStatus,
    SlotAssignment,
    SlotAssignmentStatus,
)

logger = logging.getLogger(__name__)

_STATE_WAITING_DATETIME = "waiting_candidate_datetime_input"
_ACTIVE_RESCHEDULE_ASSIGNMENT_STATUSES = {
    SlotAssignmentStatus.OFFERED,
    SlotAssignmentStatus.CONFIRMED,
    SlotAssignmentStatus.RESCHEDULE_REQUESTED,
    SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
}


@dataclass(frozen=True)
class RescheduleIntent:
    requested: bool
    created_at: Optional[str] = None
    requested_start_utc: Optional[str] = None
    requested_end_utc: Optional[str] = None
    requested_tz: Optional[str] = None
    candidate_comment: Optional[str] = None
    source: Optional[str] = None


async def get_reschedule_intent_map(
    session: AsyncSession,
    *,
    candidate_ids: Sequence[str],
) -> dict[str, RescheduleIntent]:
    normalized_ids = [str(candidate_id) for candidate_id in candidate_ids if candidate_id]
    if not normalized_ids:
        return {}

    latest_sq = (
        select(
            SlotAssignment.candidate_id.label("candidate_id"),
            func.coalesce(
                RescheduleRequest.created_at,
                SlotAssignment.reschedule_requested_at,
                SlotAssignment.offered_at,
            ).label("created_at"),
            RescheduleRequest.requested_start_utc.label("requested_start_utc"),
            RescheduleRequest.requested_end_utc.label("requested_end_utc"),
            RescheduleRequest.requested_tz.label("requested_tz"),
            RescheduleRequest.candidate_comment.label("candidate_comment"),
            (RescheduleRequest.id.is_not(None)).label("has_request"),
            func.row_number()
            .over(
                partition_by=SlotAssignment.candidate_id,
                order_by=func.coalesce(
                    RescheduleRequest.created_at,
                    SlotAssignment.reschedule_requested_at,
                    SlotAssignment.offered_at,
                ).desc(),
            )
            .label("rn"),
        )
        .select_from(SlotAssignment)
        .outerjoin(
            RescheduleRequest,
            and_(
                RescheduleRequest.slot_assignment_id == SlotAssignment.id,
                RescheduleRequest.status == RescheduleRequestStatus.PENDING,
            ),
        )
        .where(
            SlotAssignment.candidate_id.in_(normalized_ids),
            SlotAssignment.status == SlotAssignmentStatus.RESCHEDULE_REQUESTED,
        )
    ).subquery()

    rows = await session.execute(
        select(
            latest_sq.c.candidate_id,
            latest_sq.c.created_at,
            latest_sq.c.requested_start_utc,
            latest_sq.c.requested_end_utc,
            latest_sq.c.requested_tz,
            latest_sq.c.candidate_comment,
            latest_sq.c.has_request,
        ).where(latest_sq.c.rn == 1)
    )

    result: dict[str, RescheduleIntent] = {}
    for (
        candidate_id,
        created_at,
        requested_start_utc,
        requested_end_utc,
        requested_tz,
        candidate_comment,
        has_request,
    ) in rows:
        if not candidate_id:
            continue
        result[str(candidate_id)] = RescheduleIntent(
            requested=True,
            created_at=created_at.isoformat() if created_at else None,
            requested_start_utc=(
                requested_start_utc.isoformat() if requested_start_utc else None
            ),
            requested_end_utc=(
                requested_end_utc.isoformat() if requested_end_utc else None
            ),
            requested_tz=requested_tz,
            candidate_comment=candidate_comment,
            source="pending_request" if has_request else "assignment_state",
        )
    return result


async def get_bot_state_reschedule_intent(
    session: AsyncSession,
    *,
    candidate_id: Optional[str],
    candidate_tg_id: Optional[int],
) -> Optional[RescheduleIntent]:
    if candidate_tg_id is None:
        return None

    try:
        from backend.apps.bot.services import get_state_manager
    except Exception:
        logger.debug("reschedule_intent.bot_state_import_unavailable", exc_info=True)
        return None

    try:
        state_manager = get_state_manager()
    except Exception:
        logger.debug("reschedule_intent.bot_state_manager_unavailable", exc_info=True)
        return None

    if state_manager is None:
        return None

    try:
        state = await state_manager.get(int(candidate_tg_id))
    except Exception:
        logger.warning(
            "reschedule_intent.bot_state_lookup_failed",
            extra={"candidate_tg_id": candidate_tg_id},
            exc_info=True,
        )
        return None

    if not isinstance(state, dict):
        return None
    if state.get("slot_assignment_state") != _STATE_WAITING_DATETIME:
        return None

    assignment_id_raw = state.get("slot_assignment_id")
    try:
        assignment_id = int(assignment_id_raw)
    except (TypeError, ValueError):
        return None

    assignment = await session.scalar(
        select(SlotAssignment).where(SlotAssignment.id == assignment_id)
    )
    if assignment is None:
        return None
    if assignment.status not in _ACTIVE_RESCHEDULE_ASSIGNMENT_STATUSES:
        return None
    if candidate_id and assignment.candidate_id not in (None, candidate_id):
        return None
    if candidate_tg_id and assignment.candidate_tg_id not in (None, candidate_tg_id):
        return None

    created_at = assignment.reschedule_requested_at or assignment.offered_at
    return RescheduleIntent(
        requested=True,
        created_at=created_at.isoformat() if created_at else None,
        requested_start_utc=None,
        requested_end_utc=None,
        requested_tz=None,
        candidate_comment=None,
        source="bot_state",
    )


async def get_candidate_reschedule_intent(
    session: AsyncSession,
    *,
    candidate_id: Optional[str],
    candidate_tg_id: Optional[int],
) -> Optional[RescheduleIntent]:
    if candidate_id:
        reschedule_map = await get_reschedule_intent_map(session, candidate_ids=[candidate_id])
        intent = reschedule_map.get(str(candidate_id))
        if intent:
            return intent
    return await get_bot_state_reschedule_intent(
        session,
        candidate_id=candidate_id,
        candidate_tg_id=candidate_tg_id,
    )


__all__ = [
    "RescheduleIntent",
    "get_bot_state_reschedule_intent",
    "get_candidate_reschedule_intent",
    "get_reschedule_intent_map",
]
