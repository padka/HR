from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.workflow import (
    CandidateStateDTO,
    CandidateWorkflowService,
    WorkflowAction,
    WorkflowConflict,
    WorkflowStatus,
)
from backend.core.audit import log_audit_action


router = APIRouter(prefix="/candidates", tags=["workflow"])
_service = CandidateWorkflowService()


def _serialize_state(state: CandidateStateDTO) -> dict:
    return {
        "status": state.status.value,
        "allowed_actions": state.allowed_actions,
        "rejection_stage": state.rejection_stage,
    }


@router.get("/{candidate_id}/state")
async def get_candidate_state(candidate_id: int) -> JSONResponse:
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(status_code=404, detail="Candidate not found")

        state = _service.describe(user)
        return JSONResponse(_serialize_state(state))


@router.post("/{candidate_id}/actions/{action}")
async def apply_action(
    request: Request,
    candidate_id: int,
    action: str,
) -> JSONResponse:
    try:
        action_enum = WorkflowAction(action)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown action")

    actor = request.headers.get("X-Admin-User") or "admin"

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            raise HTTPException(status_code=404, detail="Candidate not found")

        try:
            state = _service.transition(user, action_enum, actor=actor)
            await session.commit()
            await log_audit_action(
                "candidate_workflow_transition",
                "candidate",
                candidate_id,
                changes={
                    "action": action_enum.value,
                    "status": state.status.value,
                    "allowed": state.allowed_actions,
                    "rejection_stage": state.rejection_stage,
                    "actor": actor,
                },
            )
            return JSONResponse(_serialize_state(state))
        except WorkflowConflict as exc:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "status": exc.current.value,
                    "allowed_actions": exc.allowed,
                },
            )

