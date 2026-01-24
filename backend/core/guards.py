from __future__ import annotations

from fastapi import HTTPException, status

from backend.apps.admin_ui.security import Principal
from backend.domain.candidates.models import User
from backend.domain.models import Slot


def ensure_candidate_scope(user: User, principal: Principal) -> None:
    if principal.type == "admin":
        return
    if user.responsible_recruiter_id != principal.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")


def ensure_slot_scope(slot: Slot, principal: Principal) -> None:
    if principal.type == "admin":
        return
    if slot.recruiter_id != principal.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
