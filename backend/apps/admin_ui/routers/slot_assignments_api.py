import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from backend.core.db import async_session
from backend.core.time_utils import ensure_aware_utc
from backend.domain.slot_assignment_service import request_reschedule as request_reschedule_service
from backend.domain.candidates.status_service import set_status_waiting_slot
from backend.domain.candidates.services import save_manual_slot_response
from backend.domain.models import SlotAssignment, RescheduleRequest, OutboxNotification, Recruiter, ActionToken, Slot, SlotStatus
from sqlalchemy import select, and_
from backend.domain.repositories import reject_slot, reserve_slot
from backend.domain.candidates.status_service import set_status_interview_confirmed
from backend.apps.bot.services import approve_slot_and_notify
from backend.domain.candidates.models import User

router = APIRouter(prefix="/api/slot-assignments", tags=["slot-assignments"])
logger = logging.getLogger(__name__)

class ActionPayload(BaseModel):
    action_token: str
    candidate_tg_id: int

class ReschedulePayload(ActionPayload):
    requested_start_utc: datetime
    requested_tz: str
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

@router.post("/{assignment_id}/confirm")
async def confirm_assignment(assignment_id: int, payload: ActionPayload):
    async with async_session() as session:
        if not await _validate_token(
            session,
            payload.action_token,
            {"confirm_assignment", "slot_assignment_confirm"},
            assignment_id,
        ):
            raise HTTPException(status_code=403, detail="Invalid or expired token")

        assignment = await session.get(SlotAssignment, assignment_id)
        if not assignment or assignment.candidate_tg_id != payload.candidate_tg_id:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment.status not in {"offered", "confirmed"}:
            raise HTTPException(status_code=409, detail="Assignment not in offered state")

        assignment.status = "confirmed"
        assignment.confirmed_at = datetime.now(timezone.utc)

        slot = await session.get(Slot, assignment.slot_id)
        candidate = None
        if assignment.candidate_id:
            candidate = await session.scalar(select(User).where(User.candidate_id == assignment.candidate_id))
        allow_reschedule_replace = bool(getattr(assignment, "reschedule_requested_at", None))
        await session.commit()

    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")

    if payload.candidate_tg_id:
        if slot.status in {SlotStatus.FREE, SlotStatus.PENDING, SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
            if slot.status == SlotStatus.FREE:
                reservation = await reserve_slot(
                    slot.id,
                    payload.candidate_tg_id,
                    candidate.fio if candidate else "",
                    slot.tz_name,
                    candidate_id=assignment.candidate_id,
                    candidate_city_id=slot.city_id,
                    candidate_username=getattr(candidate, "username", None) if candidate else None,
                    purpose="interview",
                    expected_recruiter_id=assignment.recruiter_id,
                    expected_city_id=slot.city_id,
                    allow_candidate_replace=False,
                )
                if reservation.status == "duplicate_candidate" and allow_reschedule_replace:
                    # Reschedule flow: candidate might already have an active slot with the same recruiter.
                    # Replace the old slot atomically in reserve_slot() to avoid blocking negotiation.
                    reservation = await reserve_slot(
                        slot.id,
                        payload.candidate_tg_id,
                        candidate.fio if candidate else "",
                        slot.tz_name,
                        candidate_id=assignment.candidate_id,
                        candidate_city_id=slot.city_id,
                        candidate_username=getattr(candidate, "username", None) if candidate else None,
                        purpose="interview",
                        expected_recruiter_id=assignment.recruiter_id,
                        expected_city_id=slot.city_id,
                        allow_candidate_replace=True,
                    )
                if reservation.status != "reserved":
                    raise HTTPException(status_code=409, detail="Slot is no longer available")

            result = await approve_slot_and_notify(slot.id, force_notify=True)
            if result.status not in {"approved", "already", "notify_failed"}:
                raise HTTPException(status_code=409, detail="Failed to finalize slot")

    if payload.candidate_tg_id:
        await set_status_interview_confirmed(payload.candidate_tg_id)
    return {"ok": True, "message": "Время подтверждено. Приглашение отправлено."}

@router.post("/{assignment_id}/request-reschedule")
async def request_reschedule(assignment_id: int, payload: ReschedulePayload):
    requested_start = ensure_aware_utc(payload.requested_start_utc)
    result = await request_reschedule_service(
        assignment_id=assignment_id,
        action_token=payload.action_token,
        candidate_tg_id=payload.candidate_tg_id,
        requested_start_utc=requested_start,
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
        duration = slot.duration_min or 30
        await save_manual_slot_response(
            payload.candidate_tg_id,
            window_start=requested_start,
            window_end=requested_start + timedelta(minutes=duration),
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
        if not assignment or assignment.candidate_tg_id != payload.candidate_tg_id:
            raise HTTPException(status_code=404, detail="Assignment not found")

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
