"""API endpoints for slot assignments (recruiter/admin actions)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.apps.admin_ui.security import Principal, require_principal, require_csrf_token
from backend.core.db import async_session
from backend.core.time_utils import ensure_aware_utc
from backend.domain.models import SlotAssignment, Slot
from backend.domain.slot_assignment_service import (
    ServiceResult,
    approve_reschedule,
    create_slot_assignment,
    decline_reschedule,
    propose_alternative,
)

router = APIRouter(prefix="/api", tags=["slot-assignments"])


class SlotAssignmentCreateRequest(BaseModel):
    slot_id: int = Field(..., gt=0)
    candidate_id: str = Field(..., min_length=3)
    candidate_tg_id: Optional[int] = None
    candidate_tz: Optional[str] = None


class RescheduleDecisionRequest(BaseModel):
    comment: Optional[str] = None


class AlternativeProposalRequest(BaseModel):
    new_start_utc: datetime
    comment: Optional[str] = None


def _respond(result: ServiceResult) -> dict:
    payload = {"ok": result.ok, "status": result.status}
    if result.message:
        payload["message"] = result.message
    payload.update(result.payload or {})
    return payload


async def _ensure_assignment_scope(
    assignment_id: int, principal: Principal
) -> SlotAssignment:
    async with async_session() as session:
        assignment = await session.scalar(
            select(SlotAssignment).where(SlotAssignment.id == assignment_id)
        )
        if assignment is None:
            raise HTTPException(status_code=404, detail="Назначение не найдено.")
        if principal.type == "recruiter" and assignment.recruiter_id != principal.id:
            raise HTTPException(status_code=404, detail="Назначение не найдено.")
        return assignment


@router.post("/slot-assignments")
async def api_create_slot_assignment(
    payload: SlotAssignmentCreateRequest,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    await require_csrf_token(request)
    async with async_session() as session:
        slot = await session.get(Slot, payload.slot_id)
        if slot is None:
            raise HTTPException(status_code=404, detail="Слот не найден.")
        if principal.type == "recruiter" and slot.recruiter_id != principal.id:
            raise HTTPException(status_code=404, detail="Слот не найден.")

    result = await create_slot_assignment(
        slot_id=payload.slot_id,
        candidate_id=payload.candidate_id,
        candidate_tg_id=payload.candidate_tg_id,
        candidate_tz=payload.candidate_tz,
        created_by=f"{principal.type}:{principal.id}",
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)
    return _respond(result)


@router.post("/slot-assignments/{assignment_id}/approve-reschedule")
async def api_approve_reschedule(
    assignment_id: int,
    payload: RescheduleDecisionRequest,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    await require_csrf_token(request)
    await _ensure_assignment_scope(assignment_id, principal)
    result = await approve_reschedule(
        assignment_id=assignment_id,
        decided_by_id=principal.id,
        decided_by_type=principal.type,
        comment=payload.comment,
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)
    return _respond(result)


@router.post("/slot-assignments/{assignment_id}/propose-alternative")
async def api_propose_alternative(
    assignment_id: int,
    payload: AlternativeProposalRequest,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    await require_csrf_token(request)
    await _ensure_assignment_scope(assignment_id, principal)
    result = await propose_alternative(
        assignment_id=assignment_id,
        decided_by_id=principal.id,
        decided_by_type=principal.type,
        new_start_utc=ensure_aware_utc(payload.new_start_utc),
        comment=payload.comment,
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)
    return _respond(result)


@router.post("/slot-assignments/{assignment_id}/decline-reschedule")
async def api_decline_reschedule(
    assignment_id: int,
    payload: RescheduleDecisionRequest,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    await require_csrf_token(request)
    await _ensure_assignment_scope(assignment_id, principal)
    result = await decline_reschedule(
        assignment_id=assignment_id,
        decided_by_id=principal.id,
        decided_by_type=principal.type,
        comment=payload.comment,
    )
    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.message or result.status)
    return _respond(result)
