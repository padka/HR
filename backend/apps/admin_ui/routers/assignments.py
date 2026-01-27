import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

from backend.core.db import async_session
from backend.domain.models import SlotAssignment, RescheduleRequest, OutboxNotification, Recruiter
from sqlalchemy import select as sql_select

router = APIRouter(prefix="/assignments", tags=["assignments"])
logger = logging.getLogger(__name__)

class RescheduleRequestPayload(BaseModel):
    requested_datetime_utc: datetime
    candidate_comment: str | None = None

@router.post("/{assignment_id}/confirm")
async def confirm_assignment(assignment_id: int):
    """Called by the bot when a candidate confirms a slot proposal."""
    async with async_session() as session:
        assignment = await session.get(SlotAssignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment.status != "offered":
            raise HTTPException(status_code=409, detail="Assignment is not in 'offered' state")

        assignment.status = "confirmed"
        
        recruiter = await session.get(Recruiter, assignment.recruiter_id)
        
        notification = OutboxNotification(
            type="slot_confirmed_recruiter",
            recruiter_tg_id=recruiter.tg_chat_id if recruiter else None,
            payload_json={
                "assignment_id": assignment.id,
                "slot_id": assignment.slot_id,
            },
        )
        session.add(notification)
        
        await session.commit()
    return {"ok": True, "message": "Assignment confirmed"}

@router.post("/{assignment_id}/request-reschedule")
async def request_reschedule(assignment_id: int, payload: RescheduleRequestPayload):
    """Called by the bot when a candidate requests a different time."""
    async with async_session() as session:
        assignment = await session.get(SlotAssignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment.status != "offered":
            raise HTTPException(status_code=409, detail="Assignment is not in 'offered' state")

        assignment.status = "reschedule_requested"

        reschedule_request = RescheduleRequest(
            slot_assignment_id=assignment.id,
            requested_start_utc=payload.requested_datetime_utc,
            candidate_comment=payload.candidate_comment,
            status="pending",
        )
        session.add(reschedule_request)
        
        recruiter = await session.get(Recruiter, assignment.recruiter_id)
        
        notification = OutboxNotification(
            type="reschedule_requested_recruiter",
            recruiter_tg_id=recruiter.tg_chat_id if recruiter else None,
            payload_json={
                "assignment_id": assignment.id,
                "slot_id": assignment.slot_id,
                "requested_time_utc": payload.requested_datetime_utc.isoformat(),
            },
        )
        session.add(notification)

        await session.commit()
    return {"ok": True, "message": "Reschedule request submitted"}
