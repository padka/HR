from datetime import date as date_type
from typing import Optional

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.cities import (
    api_cities_payload,
    api_city_owners_payload,
)
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.dashboard_calendar import (
    dashboard_calendar_snapshot,
)
from backend.apps.admin_ui.services.recruiters import api_recruiters_payload
from backend.apps.admin_ui.services.slots.core import api_slots_payload, serialize_slot
from backend.apps.admin_ui.services.templates import api_templates_payload
from backend.apps.admin_ui.utils import (
    ensure_sequence,
    parse_optional_int,
    status_filter,
)
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.models import Slot, SlotStatus

router = APIRouter(prefix="/api", tags=["api"])


def _normalize_status_filters(values: Optional[list[str]]) -> list[str]:
    normalized: list[str] = []
    for raw in ensure_sequence(values):
        candidate = (raw or "").strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered == "free":
            if "FREE" not in normalized:
                normalized.append("FREE")
            continue
        if lowered == "booked":
            for legacy in ("BOOKED", "CONFIRMED_BY_CANDIDATE"):
                if legacy not in normalized:
                    normalized.append(legacy)
            continue
        if lowered in {"cancelled", "canceled"}:
            if "CANCELED" not in normalized:
                normalized.append("CANCELED")
            continue
        if lowered == "expired":
            # Derived status — filtered client-side.
            continue
        fallback = status_filter(candidate)
        if fallback and fallback not in normalized:
            normalized.append(fallback)
    return normalized


class CandidateUpdatePayload(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=160)
    phone: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)
    booking_confirmed: Optional[bool] = None

    @field_validator("full_name", "phone", "email", "notes", mode="before")
    @classmethod
    def _strip(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return str(value)

@router.get("/health")
async def api_health():
    counts = await dashboard_counts()
    return counts


@router.get("/dashboard/calendar")
async def api_dashboard_calendar(
    date: Optional[str] = Query(default=None),
    days: int = Query(default=14, ge=1, le=60),
):
    target_date: Optional[date_type] = None
    if date:
        try:
            target_date = date_type.fromisoformat(date)
        except ValueError:
            return JSONResponse(
                {"ok": False, "error": "invalid_date"}, status_code=400
            )
    snapshot = await dashboard_calendar_snapshot(target_date, days=days)
    return JSONResponse(snapshot)


@router.get("/recruiters")
async def api_recruiters():
    return JSONResponse(await api_recruiters_payload())


@router.get("/cities")
async def api_cities():
    return JSONResponse(await api_cities_payload())


@router.get("/slots")
async def api_slots(
    recruiter_id: Optional[str] = Query(default=None),
    status: Optional[list[str]] = Query(default=None),
    city_id: Optional[str] = Query(default=None),
    purpose: Optional[list[str]] = Query(default=None),
    date_from: Optional[str] = Query(default=None, alias="date_from"),
    date_to: Optional[str] = Query(default=None, alias="date_to"),
    date: Optional[str] = Query(default=None),
    future: Optional[str] = Query(default=None),
    free_only: Optional[str] = Query(default=None, alias="free_only"),
    search: Optional[list[str]] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    recruiter = parse_optional_int(recruiter_id)
    statuses = _normalize_status_filters(status)
    city_filter = parse_optional_int(city_id)
    purpose_values = [item.lower() for item in ensure_sequence(purpose)]
    date_start: Optional[date_type] = None
    date_end: Optional[date_type] = None
    if date_from:
        try:
            date_start = date_type.fromisoformat(date_from)
        except ValueError:
            date_start = None
    if date_to:
        try:
            date_end = date_type.fromisoformat(date_to)
        except ValueError:
            date_end = None
    if not date_start and not date_end and date:
        try:
            parsed = date_type.fromisoformat(date)
            date_start = parsed
            date_end = parsed
        except ValueError:
            date_start = None
            date_end = None
    tokens: list[str] = []
    if search:
        for chunk in search:
            if not chunk:
                continue
            for part in chunk.split(','):
                value = part.strip()
                if value and value not in tokens:
                    tokens.append(value)
    future_only = (future or '').lower() in {'1', 'true', 'yes'}
    free_only_flag = (free_only or '').lower() in {'1', 'true', 'yes'}
    payload = await api_slots_payload(
        recruiter,
        statuses,
        limit,
        city_id=city_filter,
        purposes=purpose_values,
        date_from=date_start,
        date_to=date_end,
        search_tokens=tokens,
        free_only=free_only_flag,
        future_only=future_only,
    )
    return JSONResponse(payload)


@router.get("/slots/{slot_id}")
async def api_slot_detail(slot_id: int):
    async with async_session() as session:
        slot = await session.get(
            Slot,
            slot_id,
            options=[selectinload(Slot.city), selectinload(Slot.recruiter)],
        )
        if slot is None:
            raise HTTPException(status_code=404, detail="slot_not_found")
        payload = serialize_slot(slot, now=datetime.now(timezone.utc))
    return JSONResponse(payload)


@router.patch("/slots/{slot_id}/candidate")
async def api_slot_candidate_update(slot_id: int, payload: CandidateUpdatePayload):
    async with async_session() as session:
        slot = await session.get(
            Slot,
            slot_id,
            options=[selectinload(Slot.city), selectinload(Slot.recruiter)],
        )
        if slot is None:
            raise HTTPException(status_code=404, detail="slot_not_found")

        if payload.full_name is not None:
            slot.candidate_fio = payload.full_name
        if payload.phone is not None:
            slot.candidate_phone = payload.phone
        if payload.email is not None:
            slot.candidate_email = payload.email
        if payload.notes is not None:
            slot.candidate_notes = payload.notes
        if payload.booking_confirmed is not None:
            slot.booking_confirmed = bool(payload.booking_confirmed)

        if slot.cancelled_at:
            slot.status = SlotStatus.CANCELED
        elif slot.booking_confirmed:
            slot.status = SlotStatus.BOOKED
        elif slot.candidate_fio:
            slot.status = SlotStatus.BOOKED
        else:
            slot.status = SlotStatus.FREE

        await session.commit()
        await session.refresh(slot)
        serialized = serialize_slot(slot, now=datetime.now(timezone.utc))

    return JSONResponse({"ok": True, "slot": serialized})


@router.post("/slots/{slot_id}/cancel")
async def api_slot_cancel(slot_id: int):
    async with async_session() as session:
        slot = await session.get(
            Slot,
            slot_id,
            options=[selectinload(Slot.city), selectinload(Slot.recruiter)],
        )
        if slot is None:
            raise HTTPException(status_code=404, detail="slot_not_found")

        now = datetime.now(timezone.utc)
        slot.cancelled_at = now
        slot.status = SlotStatus.CANCELED
        await session.commit()
        await session.refresh(slot)
        serialized = serialize_slot(slot, now=now)

    return JSONResponse({"ok": True, "slot": serialized})


@router.post("/slots/{slot_id}/restore")
async def api_slot_restore(slot_id: int):
    async with async_session() as session:
        slot = await session.get(
            Slot,
            slot_id,
            options=[selectinload(Slot.city), selectinload(Slot.recruiter)],
        )
        if slot is None:
            raise HTTPException(status_code=404, detail="slot_not_found")

        slot.cancelled_at = None
        if slot.booking_confirmed:
            slot.status = SlotStatus.BOOKED
        elif slot.candidate_fio:
            slot.status = SlotStatus.BOOKED
        else:
            slot.status = SlotStatus.FREE

        await session.commit()
        await session.refresh(slot)
        serialized = serialize_slot(slot, now=datetime.now(timezone.utc))

    return JSONResponse({"ok": True, "slot": serialized})


@router.get("/templates")
async def api_templates(city_id: Optional[int] = None, key: Optional[str] = None):
    payload = await api_templates_payload(city_id, key)
    status_code = 200
    if isinstance(payload, dict) and payload.get("found") is False:
        status_code = 404
    return JSONResponse(payload, status_code=status_code)


@router.get("/kpis/current")
async def api_weekly_kpis(company_tz: Optional[str] = Query(default=None)):
    return JSONResponse(await get_weekly_kpis(company_tz))


@router.get("/kpis/history")
async def api_weekly_history(
    limit: int = Query(default=12, ge=1, le=104),
    offset: int = Query(default=0, ge=0),
):
    return JSONResponse(await list_weekly_history(limit=limit, offset=offset))


@router.get("/template_keys")
async def api_template_keys():
    return JSONResponse(
        [
            "invite_interview",
            "confirm_interview",
            "after_approval",
            "intro_day_reminder",
            "confirm_2h",
            "reminder_1h",
            "followup_missed",
            "after_meeting",
            "slot_rejected",
        ]
    )


@router.get("/city_owners")
async def api_city_owners():
    payload = await api_city_owners_payload()
    status_code = 200 if payload.get("ok") else 400
    return JSONResponse(payload, status_code=status_code)


@router.get("/bot/integration")
async def api_bot_integration_status(request: Request):
    switch = getattr(request.app.state, "bot_integration_switch", None)
    bot_service = getattr(request.app.state, "bot_service", None)
    settings = get_settings()
    runtime_enabled = (
        switch.is_enabled() if switch else settings.bot_integration_enabled
    )
    payload = {
        "config_enabled": settings.bot_integration_enabled,
        "runtime_enabled": runtime_enabled,
        "updated_at": switch.updated_at.isoformat() if switch else None,
        "service_health": bot_service.health_status if bot_service else "missing",
        "service_ready": bot_service.is_ready() if bot_service else False,
    }
    return JSONResponse(payload)


@router.post("/bot/integration")
async def api_bot_integration_update(request: Request):
    switch = getattr(request.app.state, "bot_integration_switch", None)
    if switch is None:
        return JSONResponse(
            {"ok": False, "error": "switch_unavailable"}, status_code=503
        )

    enabled_value: Optional[bool] = None
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        data = await request.json()
        enabled_value = bool(data.get("enabled"))
    else:
        form = await request.form()
        if "enabled" in form:
            raw = str(form.get("enabled") or "").strip().lower()
            enabled_value = raw in {"1", "true", "yes", "on"}

    if enabled_value is None:
        return JSONResponse(
            {"ok": False, "error": "enabled_not_provided"}, status_code=400
        )

    switch.set(enabled_value)
    bot_service = getattr(request.app.state, "bot_service", None)
    payload = {
        "ok": True,
        "runtime_enabled": switch.is_enabled(),
        "updated_at": switch.updated_at.isoformat(),
        "service_health": bot_service.health_status if bot_service else "missing",
        "service_ready": bot_service.is_ready() if bot_service else False,
    }
    return JSONResponse(payload)
