import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.db import async_session
from backend.core.time_utils import ensure_aware_utc
from backend.domain.slot_assignment_service import (
    confirm_slot_assignment as confirm_assignment_service,
    request_reschedule as request_reschedule_service,
)
from backend.domain.candidates.status_service import set_status_waiting_slot
from backend.domain.candidates.services import save_manual_slot_response
from backend.domain.models import ActionToken, Slot, SlotAssignment
from sqlalchemy import select, and_, or_
from backend.domain.repositories import reject_slot
from backend.domain.candidates.status_service import set_status_interview_confirmed
from backend.domain.candidates.models import User

router = APIRouter(prefix="/api/slot-assignments", tags=["slot-assignments"])
logger = logging.getLogger(__name__)

class ActionPayload(BaseModel):
    action_token: str
    candidate_tg_id: int

class ReschedulePayload(ActionPayload):
    requested_start_utc: datetime | None = None
    requested_end_utc: datetime | None = None
    requested_tz: str | None = None
    comment: str | None = None

async def _validate_token(session, token: str, actions: set[str], entity_id: int) -> bool:
    action_token = await session.scalar(
        select(ActionToken).where(
            and_(
                ActionToken.token == token,
                ActionToken.action.in_(actions),
                ActionToken.entity_id == str(entity_id),
                ActionToken.expires_at > datetime.now(timezone.utc),
                ActionToken.used_at == None,
            )
        )
    )
    if not action_token:
        return False
    
    action_token.used_at = datetime.now(timezone.utc)
    return True


async def _resolve_candidate_for_assignment(session, assignment: SlotAssignment) -> User | None:
    candidate = None
    if assignment.candidate_id:
        candidate = await session.scalar(
            select(User).where(User.candidate_id == assignment.candidate_id)
        )
    if candidate is None and assignment.candidate_tg_id is not None:
        candidate = await session.scalar(
            select(User).where(
                or_(
                    User.telegram_id == assignment.candidate_tg_id,
                    User.telegram_user_id == assignment.candidate_tg_id,
                )
            )
        )
    return candidate


def _known_candidate_tg_ids(assignment: SlotAssignment, candidate: User | None) -> set[int]:
    ids: set[int] = set()
    for raw in (
        assignment.candidate_tg_id,
        getattr(candidate, "telegram_id", None),
        getattr(candidate, "telegram_user_id", None),
    ):
        if raw is None:
            continue
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


@router.post("/{assignment_id}/confirm")
async def confirm_assignment(assignment_id: int, payload: ActionPayload):
    result = await confirm_assignment_service(
        assignment_id=assignment_id,
        action_token=payload.action_token,
        candidate_tg_id=payload.candidate_tg_id,
        token_actions=("confirm_assignment", "slot_assignment_confirm"),
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)

    if payload.candidate_tg_id:
        await set_status_interview_confirmed(payload.candidate_tg_id)
    return {
        "ok": True,
        "status": result.status,
        "message": result.message or "",
        **(result.payload or {}),
    }

@router.post("/{assignment_id}/request-reschedule")
async def request_reschedule(assignment_id: int, payload: ReschedulePayload):
    requested_start = (
        ensure_aware_utc(payload.requested_start_utc)
        if payload.requested_start_utc is not None
        else None
    )
    requested_end = (
        ensure_aware_utc(payload.requested_end_utc)
        if payload.requested_end_utc is not None
        else None
    )
    result = await request_reschedule_service(
        assignment_id=assignment_id,
        action_token=payload.action_token,
        candidate_tg_id=payload.candidate_tg_id,
        requested_start_utc=requested_start,
        requested_end_utc=requested_end,
        requested_tz=payload.requested_tz,
        comment=payload.comment,
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)

    if payload.candidate_tg_id:
        await set_status_waiting_slot(payload.candidate_tg_id)

    async with async_session() as session:
        assignment = await session.get(SlotAssignment, assignment_id)
        slot = await session.get(Slot, assignment.slot_id) if assignment else None
    if assignment and slot and payload.candidate_tg_id:
        window_end = requested_end
        if window_end is None and requested_start is not None:
            window_end = requested_start + timedelta(minutes=slot.duration_min or 30)
        await save_manual_slot_response(
            payload.candidate_tg_id,
            window_start=requested_start,
            window_end=window_end,
            note=payload.comment,
            timezone_label=payload.requested_tz,
        )

    response = {"ok": True, "status": result.status}
    if result.message:
        response["message"] = result.message
    response.update(result.payload or {})
    return response


@router.post("/{assignment_id}/decline")
async def decline_assignment(assignment_id: int, payload: ActionPayload):
    async with async_session() as session:
        if not await _validate_token(
            session,
            payload.action_token,
            {"decline_assignment", "slot_assignment_decline"},
            assignment_id,
        ):
            raise HTTPException(status_code=403, detail="Invalid or expired token")

        assignment = await session.get(SlotAssignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        candidate = await _resolve_candidate_for_assignment(session, assignment)
        valid_tg_ids = _known_candidate_tg_ids(assignment, candidate)
        if valid_tg_ids and int(payload.candidate_tg_id) not in valid_tg_ids:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if assignment.candidate_tg_id is None:
            assignment.candidate_tg_id = payload.candidate_tg_id

        if assignment.status not in {"offered", "confirmed", "reschedule_requested", "reschedule_confirmed"}:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot decline assignment in status: {assignment.status}",
            )

        assignment.status = "rejected"
        assignment.cancelled_at = datetime.now(timezone.utc)
        slot_id = assignment.slot_id
        await session.commit()

    # Free slot and update candidate status
    try:
        await reject_slot(slot_id)
    except Exception:
        logger.exception("Failed to reject slot after assignment decline", extra={"assignment_id": assignment_id})

    return {"ok": True, "message": "Отказ зафиксирован"}
