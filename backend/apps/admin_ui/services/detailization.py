from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timezone, date as date_type, time as time_type
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.detailization.models import DetailizationEntry
from backend.domain.models import City, Recruiter, Slot, SlotAssignment

INTRO_DAY_PURPOSE = "intro_day"

ELIGIBLE_ASSIGNMENT_STATUSES = {
    "confirmed",
    "reschedule_confirmed",
    "completed",
}


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _exclude_reason(user: User) -> Optional[str]:
    """Return exclusion reason if candidate must not appear in detailization."""
    blob = " ".join(
        part
        for part in [
            getattr(user, "rejection_reason", None),
            getattr(user, "intro_decline_reason", None),
        ]
        if part
    )
    text = _normalize_text(blob)
    if not text:
        return None
    if "критер" in text or "не подходит по критериям" in text:
        return "criteria_mismatch"
    if "не приш" in text or "не яв" in text or "no_show" in text or "no show" in text:
        return "no_show"
    return None


def _derive_is_attached(user: User) -> Optional[bool]:
    status = getattr(user, "candidate_status", None)
    slug = status.value if hasattr(status, "value") else status
    if slug == CandidateStatus.HIRED.value:
        return True
    if slug == CandidateStatus.NOT_HIRED.value:
        return False
    return None


@dataclass
class DetailizationItem:
    id: int
    slot_assignment_id: Optional[int]
    slot_id: Optional[int]
    assigned_at: Optional[str]
    conducted_at: Optional[str]
    expert_name: str
    is_attached: Optional[bool]
    recruiter: Optional[dict[str, Any]]
    city: Optional[dict[str, Any]]
    candidate: dict[str, Any]

def _parse_datetime_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            if "T" in raw:
                dt = datetime.fromisoformat(raw)
            else:
                d = date_type.fromisoformat(raw)
                dt = datetime.combine(d, time_type.min)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"message": "Invalid conducted_at"}) from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _ensure_auto_rows(principal: Principal) -> None:
    """Idempotently create missing reporting rows from intro_day assignments/slots."""

    async with async_session() as session:
        # --- Source A: slot_assignments joined to intro_day slots ----------------
        q = (
            select(SlotAssignment, Slot, User)
            .join(Slot, Slot.id == SlotAssignment.slot_id)
            .join(User, User.candidate_id == SlotAssignment.candidate_id)
            .where(func.lower(Slot.purpose) == INTRO_DAY_PURPOSE)
            .where(func.lower(SlotAssignment.status).in_(ELIGIBLE_ASSIGNMENT_STATUSES))
        )
        if principal.type == "recruiter":
            q = q.where(SlotAssignment.recruiter_id == principal.id)

        rows = (await session.execute(q)).all()
        assignment_ids = [int(a.id) for (a, _slot, _user) in rows]
        existing_assignment_ids: set[int] = set()
        if assignment_ids:
            existing_assignment_ids = set(
                (
                    await session.scalars(
                        select(DetailizationEntry.slot_assignment_id).where(
                            DetailizationEntry.slot_assignment_id.in_(assignment_ids)
                        )
                    )
                ).all()
            )

        created = 0
        for assignment, slot, user in rows:
            if int(assignment.id) in existing_assignment_ids:
                continue
            if _exclude_reason(user):
                continue

            assigned_at = assignment.confirmed_at or assignment.offered_at
            conducted_at = getattr(slot, "start_utc", None)

            entry = DetailizationEntry(
                slot_assignment_id=int(assignment.id),
                slot_id=int(slot.id),
                candidate_id=int(user.id),
                recruiter_id=int(assignment.recruiter_id),
                city_id=getattr(slot, "city_id", None),
                assigned_at=assigned_at,
                conducted_at=conducted_at,
                expert_name=None,
                is_attached=_derive_is_attached(user),
                created_by_type="system",
                created_by_id=-1,
            )
            session.add(entry)
            created += 1

        # --- Source B: fallback direct intro_day slots (legacy / no assignment) --
        q2 = (
            select(Slot, User)
            .join(User, User.candidate_id == Slot.candidate_id)
            .where(func.lower(Slot.purpose) == INTRO_DAY_PURPOSE)
            .where(Slot.candidate_id.is_not(None))
            # Fallback rows should only be created when there is no assignment record.
            # Otherwise, slot_assignments is the source of truth (including NO_SHOW).
            .where(~exists(select(SlotAssignment.id).where(SlotAssignment.slot_id == Slot.id)))
        )
        if principal.type == "recruiter":
            q2 = q2.where(Slot.recruiter_id == principal.id)

        rows2 = (await session.execute(q2)).all()
        slot_ids = [int(slot.id) for (slot, _user) in rows2]
        existing_pairs: set[tuple[int, int]] = set()
        if slot_ids:
            existing_rows = (
                await session.execute(
                    select(DetailizationEntry.slot_id, DetailizationEntry.candidate_id).where(
                        DetailizationEntry.slot_id.in_(slot_ids)
                    )
                )
            ).all()
            existing_pairs = {
                (int(r[0]), int(r[1]))
                for r in existing_rows
                if r[0] is not None and r[1] is not None
            }

        for slot, user in rows2:
            pair = (int(slot.id), int(user.id))
            if pair in existing_pairs:
                continue
            if _exclude_reason(user):
                continue

            entry = DetailizationEntry(
                slot_assignment_id=None,
                slot_id=int(slot.id),
                candidate_id=int(user.id),
                recruiter_id=int(slot.recruiter_id),
                city_id=getattr(slot, "city_id", None),
                assigned_at=getattr(slot, "updated_at", None),
                conducted_at=getattr(slot, "start_utc", None),
                expert_name=None,
                is_attached=_derive_is_attached(user),
                created_by_type="system",
                created_by_id=-1,
            )
            session.add(entry)
            created += 1

        if created:
            await session.commit()


async def list_detailization(principal: Principal) -> dict[str, Any]:
    await _ensure_auto_rows(principal)

    async with async_session() as session:
        q = (
            select(DetailizationEntry)
            .options(
                selectinload(DetailizationEntry.candidate),
                selectinload(DetailizationEntry.recruiter),
                selectinload(DetailizationEntry.city),
            )
            .order_by(DetailizationEntry.conducted_at.desc().nullslast(), DetailizationEntry.id.desc())
        )
        if principal.type == "recruiter":
            q = q.where(DetailizationEntry.recruiter_id == principal.id)

        rows = (await session.scalars(q)).all()

        items: list[DetailizationItem] = []
        for entry in rows:
            user = entry.candidate
            if user is None:
                continue
            if _exclude_reason(user):
                continue

            recruiter = entry.recruiter
            city = entry.city

            assigned_at = (
                entry.assigned_at.astimezone(UTC).isoformat() if entry.assigned_at else None
            )
            conducted_at = (
                entry.conducted_at.astimezone(UTC).isoformat() if entry.conducted_at else None
            )

            items.append(
                DetailizationItem(
                    id=int(entry.id),
                    slot_assignment_id=int(entry.slot_assignment_id) if entry.slot_assignment_id else None,
                    slot_id=int(entry.slot_id) if entry.slot_id else None,
                    assigned_at=assigned_at,
                    conducted_at=conducted_at,
                    expert_name=(entry.expert_name or "").strip(),
                    is_attached=entry.is_attached,
                    recruiter=(
                        {"id": int(recruiter.id), "name": recruiter.name}
                        if recruiter is not None
                        else None
                    ),
                    city=(
                        {"id": int(city.id), "name": city.name_plain if hasattr(city, "name_plain") else city.name}
                        if city is not None
                        else None
                    ),
                    candidate={"id": int(user.id), "name": user.fio},
                )
            )

        return {"ok": True, "items": [item.__dict__ for item in items]}


async def update_detailization_entry(
    entry_id: int,
    payload: dict[str, Any],
    *,
    principal: Principal,
) -> dict[str, Any]:
    async with async_session() as session:
        entry = await session.get(DetailizationEntry, entry_id, options=[selectinload(DetailizationEntry.candidate)])
        if entry is None:
            raise HTTPException(status_code=404, detail={"message": "Row not found"})

        if principal.type == "recruiter" and entry.recruiter_id != principal.id:
            raise HTTPException(status_code=404, detail={"message": "Row not found"})

        # Recruiters can only fill manual fields; admin can edit broader.
        allow_full = principal.type == "admin"

        if "expert_name" in payload:
            entry.expert_name = (str(payload.get("expert_name") or "").strip() or None)
        if "is_attached" in payload:
            val = payload.get("is_attached")
            if val is None:
                entry.is_attached = None
            else:
                entry.is_attached = bool(val)

        if "assigned_at" in payload:
            entry.assigned_at = _parse_datetime_utc(payload.get("assigned_at"))

        if "conducted_at" in payload:
            entry.conducted_at = _parse_datetime_utc(payload.get("conducted_at"))

        if allow_full:
            if "recruiter_id" in payload:
                rid = payload.get("recruiter_id")
                entry.recruiter_id = int(rid) if rid is not None else None
            if "city_id" in payload:
                cid = payload.get("city_id")
                entry.city_id = int(cid) if cid is not None else None

        await session.commit()
        return {"ok": True}


async def create_manual_detailization_entry(
    payload: dict[str, Any],
    *,
    principal: Principal,
) -> dict[str, Any]:
    candidate_id = payload.get("candidate_id")
    if candidate_id is None:
        raise HTTPException(status_code=400, detail={"message": "candidate_id required"})

    async with async_session() as session:
        user = await session.get(User, int(candidate_id))
        if user is None:
            raise HTTPException(status_code=404, detail={"message": "Candidate not found"})

        recruiter_id = payload.get("recruiter_id")
        if principal.type == "recruiter":
            recruiter_id = principal.id

        city_id = payload.get("city_id")
        if city_id is None and getattr(user, "city", None):
            # Best-effort: try to map by name (admin can refine later).
            city_row = await session.scalar(
                select(City).where(City.name == user.city)
            )
            city_id = city_row.id if city_row else None

        entry = DetailizationEntry(
            slot_assignment_id=None,
            slot_id=None,
            candidate_id=int(user.id),
            recruiter_id=int(recruiter_id) if recruiter_id is not None else None,
            city_id=int(city_id) if city_id is not None else None,
            assigned_at=_parse_datetime_utc(payload.get("assigned_at")),
            conducted_at=_parse_datetime_utc(payload.get("conducted_at")),
            expert_name=(str(payload.get("expert_name") or "").strip() or None),
            is_attached=payload.get("is_attached", None),
            created_by_type=principal.type,
            created_by_id=principal.id,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return {"ok": True, "id": int(entry.id)}
