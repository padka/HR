import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from backend.core.db import async_session
from backend.domain.models import SlotAssignment, RescheduleRequest, OutboxNotification, Recruiter, ActionToken, Slot, SlotStatus
from sqlalchemy import select, and_
from backend.domain.repositories import reject_slot
from backend.domain.candidates.status_service import set_status_interview_confirmed

router = APIRouter(prefix="/api/slot-assignments", tags=["slot-assignments"])
logger = logging.getLogger(__name__)

class ActionPayload(BaseModel):
    action_token: str
    candidate_tg_id: int

class ReschedulePayload(ActionPayload):
    requested_start_utc: datetime
    requested_tz: str
    comment: str | None = None

async def _validate_token(session, token: str, action: str, entity_id: int) -> bool:
    action_token = await session.scalar(
        select(ActionToken).where(
            and_(
                ActionToken.token == token,
                ActionToken.action == action,
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
        if not await _validate_token(session, payload.action_token, "confirm_assignment", assignment_id):
            raise HTTPException(status_code=403, detail="Invalid or expired token")

        assignment = await session.get(SlotAssignment, assignment_id)
        if not assignment or assignment.candidate_tg_id != payload.candidate_tg_id:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment.status != "offered":
            raise HTTPException(status_code=409, detail="Assignment not in offered state")

        assignment.status = "confirmed"
        assignment.confirmed_at = datetime.now(timezone.utc)

        slot = await session.get(Slot, assignment.slot_id)
        if slot:
            slot.status = SlotStatus.CONFIRMED_BY_CANDIDATE
            if payload.candidate_tg_id:
                slot.candidate_tg_id = payload.candidate_tg_id

        # Notify recruiter
        recruiter = await session.get(Recruiter, assignment.recruiter_id)
        if recruiter and recruiter.tg_chat_id:
            session.add(OutboxNotification(
                type="slot_confirmed_recruiter",
                recruiter_tg_id=recruiter.tg_chat_id,
                payload_json={"assignment_id": assignment.id}
            ))

        await session.commit()
    if payload.candidate_tg_id:
        await set_status_interview_confirmed(payload.candidate_tg_id)
    return {"ok": True}

@router.post("/{assignment_id}/request-reschedule")
async def request_reschedule(assignment_id: int, payload: ReschedulePayload):
    async with async_session() as session:
        if not await _validate_token(session, payload.action_token, "reschedule_assignment", assignment_id):
            raise HTTPException(status_code=403, detail="Invalid or expired token")

        assignment = await session.get(SlotAssignment, assignment_id)
        if not assignment or assignment.candidate_tg_id != payload.candidate_tg_id:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Guard: allow rescheduling only from valid active states
        if assignment.status not in {"offered", "confirmed"}:
            raise HTTPException(
                status_code=409, 
                detail=f"Cannot request reschedule for assignment in status: {assignment.status}"
            )

        assignment.status = "reschedule_requested"
        
        req = RescheduleRequest(
            slot_assignment_id=assignment_id,
            requested_start_utc=payload.requested_start_utc,
            requested_tz=payload.requested_tz,
            candidate_comment=payload.comment,
            status="pending",
        )
        session.add(req)
        
        # Notify recruiter
        recruiter = await session.get(Recruiter, assignment.recruiter_id)
        if recruiter and recruiter.tg_chat_id:
            session.add(OutboxNotification(
                type="reschedule_requested_recruiter",
                recruiter_tg_id=recruiter.tg_chat_id,
                payload_json={
                    "assignment_id": assignment.id,
                    "requested_start_utc": payload.requested_start_utc.isoformat(),
                }
            ))

        await session.commit()
    return {"ok": True}


@router.post("/{assignment_id}/decline")
async def decline_assignment(assignment_id: int, payload: ActionPayload):
    async with async_session() as session:
        if not await _validate_token(session, payload.action_token, "decline_assignment", assignment_id):
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
