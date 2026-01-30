import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from backend.core.db import async_session
from backend.domain.models import RescheduleRequest, Slot, SlotAssignment, OutboxNotification, Recruiter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.security import require_principal, Principal

router = APIRouter(prefix="/reschedule-requests", tags=["reschedule-requests"])
logger = logging.getLogger(__name__)

class NewProposalPayload(BaseModel):
    new_start_utc: datetime
    recruiter_comment: str | None = None

@router.get("")
async def list_reschedule_requests(principal: Principal = Depends(require_principal)):
    """List all pending reschedule requests."""
    query = (
        select(RescheduleRequest)
        .where(RescheduleRequest.status == "pending")
        .options(selectinload(RescheduleRequest.slot_assignment).selectinload(SlotAssignment.slot))
    )
    # TODO: Add recruiter scoping for non-admins
    async with async_session() as session:
        requests = await session.scalars(query)
        return requests.all()

@router.post("/{request_id}/approve")
async def approve_reschedule_request(request_id: int, principal: Principal = Depends(require_principal)):
    """Approve a candidate's reschedule request."""
    async with async_session() as session:
        request = await session.get(RescheduleRequest, request_id, options=[selectinload(RescheduleRequest.slot_assignment)])
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # TODO: Check if principal is authorized for this request

        if request.status != "pending":
            raise HTTPException(status_code=409, detail="Request is not pending")

        # 1. Update request status
        request.status = "approved"
        request.decided_at = datetime.now(timezone.utc)
        # decided_by_id logic here

        # 2. Free up the old slot
        old_assignment = request.slot_assignment
        old_slot = await session.get(Slot, old_assignment.slot_id)
        if old_slot:
            old_slot.status = "free"
            old_slot.candidate_id = None # Unlink candidate
        
        old_assignment.status = "cancelled" # Cancel the old assignment

        # 3. Create and confirm a new slot for the candidate
        new_slot = Slot(
            recruiter_id=old_assignment.recruiter_id,
            city_id=old_slot.city_id if old_slot else None,
            start_utc=request.requested_start_utc,
            duration_min=old_slot.duration_min if old_slot else 30,
            status="booked", # Immediately book it
            candidate_id=old_assignment.candidate_id,
            candidate_tg_id=old_assignment.candidate_tg_id
        )
        session.add(new_slot)
        await session.flush() # Get new_slot.id

        # 4. Create a new confirmed assignment
        new_assignment = SlotAssignment(
            slot_id=new_slot.id,
            recruiter_id=new_slot.recruiter_id,
            candidate_id=new_slot.candidate_id,
            status="confirmed",
        )
        session.add(new_assignment)
        
        # 5. Notify candidate
        notification = OutboxNotification(
            type="reschedule_approved_candidate",
            candidate_tg_id=new_slot.candidate_tg_id,
            payload_json={"new_time_utc": new_slot.start_utc.isoformat()}
        )
        session.add(notification)

        await session.commit()
    return {"ok": True, "message": "Reschedule request approved"}


@router.post("/{request_id}/propose-new")
async def propose_new_time(request_id: int, payload: NewProposalPayload, principal: Principal = Depends(require_principal)):
    """Make a counter-proposal to a candidate's reschedule request."""
    # This logic is more complex. For now, we will just decline the request and add a comment.
    # A full implementation would create a new 'offered' slot.
    async with async_session() as session:
        request = await session.get(RescheduleRequest, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # TODO: Check authorization

        request.status = "declined"
        request.decided_at = datetime.now(timezone.utc)
        request.recruiter_comment = payload.recruiter_comment
        
        # Here we should create a new Slot and SlotAssignment, then notify the user.
        # For now, we just notify them of the decline and comment.
        assignment = await session.get(SlotAssignment, request.slot_assignment_id)
        if assignment:
            # Re-open the original offer
            assignment.status = "offered" 
            notification = OutboxNotification(
                type="reschedule_declined_candidate",
                candidate_tg_id=assignment.candidate_tg_id,
                payload_json={"recruiter_comment": payload.recruiter_comment}
            )
            session.add(notification)

        await session.commit()
        
    return {"ok": True, "message": "Counter-proposal logic not fully implemented. Request declined with comment."}
