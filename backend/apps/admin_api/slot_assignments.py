"""Public bot-facing slot assignment endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.time_utils import ensure_aware_utc
from backend.domain.slot_assignment_service import (
    ServiceResult,
    confirm_slot_assignment,
    request_reschedule,
)

router = APIRouter(prefix="/api", tags=["slot-assignments"])


class SlotAssignmentConfirmRequest(BaseModel):
    action_token: str = Field(..., min_length=6, max_length=128)
    candidate_tg_id: Optional[int] = None


class SlotAssignmentRescheduleRequest(BaseModel):
    action_token: str = Field(..., min_length=6, max_length=128)
    candidate_tg_id: Optional[int] = None
    requested_start_utc: datetime
    requested_tz: Optional[str] = None
    comment: Optional[str] = None


def _respond(result: ServiceResult) -> dict:
    payload = {"ok": result.ok, "status": result.status}
    if result.message:
        payload["message"] = result.message
    payload.update(result.payload or {})
    return payload


@router.post("/slot-assignments/{assignment_id}/confirm")
async def api_confirm_slot_assignment(
    assignment_id: int,
    payload: SlotAssignmentConfirmRequest,
):
    result = await confirm_slot_assignment(
        assignment_id=assignment_id,
        action_token=payload.action_token,
        candidate_tg_id=payload.candidate_tg_id,
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)
    return _respond(result)


@router.post("/slot-assignments/{assignment_id}/request-reschedule")
async def api_request_reschedule(
    assignment_id: int,
    payload: SlotAssignmentRescheduleRequest,
):
    requested_start = ensure_aware_utc(payload.requested_start_utc)
    result = await request_reschedule(
        assignment_id=assignment_id,
        action_token=payload.action_token,
        candidate_tg_id=payload.candidate_tg_id,
        requested_start_utc=requested_start,
        requested_tz=payload.requested_tz,
        comment=payload.comment,
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)
    return _respond(result)
