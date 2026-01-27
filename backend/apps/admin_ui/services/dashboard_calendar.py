from __future__ import annotations

from collections import Counter
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.utils import DEFAULT_TZ, safe_zone
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import Slot, SlotStatus

__all__ = ["dashboard_calendar_snapshot"]


TRACKED_STATUSES: List[str] = [
    getattr(SlotStatus, "CONFIRMED_BY_CANDIDATE", "confirmed_by_candidate"),
]

STATUS_LABELS = {
    "CONFIRMED_BY_CANDIDATE": "Подтверждено кандидатом",
}

STATUS_VARIANTS = {
    "CONFIRMED_BY_CANDIDATE": "success",
}

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _normalize_status(value: Optional[str]) -> str:
    if value is None:
        return "UNKNOWN"
    return (value.value if hasattr(value, "value") else value).strip().upper()


def _selected_label(selected: date_type, today: date_type) -> str:
    if selected == today:
        return "сегодня"
    if selected == today + timedelta(days=1):
        return "завтра"
    return selected.strftime("%d.%m.%Y")


async def dashboard_calendar_snapshot(
    selected_date: Optional[date_type] = None,
    *,
    days: int = 14,
    tz_name: str = DEFAULT_TZ,
    recruiter_id: Optional[int] = None,
) -> Dict[str, object]:
    days = max(days, 1)
    zone = safe_zone(tz_name)
    now_local = datetime.now(timezone.utc).astimezone(zone)
    base_date = selected_date or now_local.date()
    start_local = datetime.combine(base_date, time.min).replace(tzinfo=zone)
    end_local = start_local + timedelta(days=days)

    async with async_session() as session:
        query = (
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(
                Slot.start_utc >= start_local.astimezone(timezone.utc),
                Slot.start_utc < end_local.astimezone(timezone.utc),
                Slot.status.in_(TRACKED_STATUSES),
            )
            .order_by(Slot.start_utc.asc(), Slot.id.asc())
        )
        if recruiter_id is not None:
            query = query.where(Slot.recruiter_id == recruiter_id)
        slots = (await session.scalars(query)).all()

        candidate_ids = {
            int(slot.candidate_tg_id)
            for slot in slots
            if getattr(slot, "candidate_tg_id", None) is not None
        }

        candidates_map = {}
        if candidate_ids:
            users = (
                await session.execute(
                    select(User).where(User.telegram_id.in_(candidate_ids))
                )
            ).scalars().all()
            candidates_map = {user.telegram_id: user for user in users}

    buckets: Dict[date_type, List[Slot]] = {}
    for slot in slots:
        local_start = slot.start_utc.astimezone(zone)
        buckets.setdefault(local_start.date(), []).append(slot)

    days_payload: List[Dict[str, object]] = []
    for offset in range(days):
        day_candidate = base_date + timedelta(days=offset)
        bucket = buckets.get(day_candidate, [])
        label = day_candidate.strftime("%d.%m")
        weekday_label = WEEKDAY_LABELS[day_candidate.weekday() % 7]
        days_payload.append(
            {
                "date": day_candidate.isoformat(),
                "label": label,
                "weekday": weekday_label,
                "count": len(bucket),
                "is_today": day_candidate == now_local.date(),
                "is_selected": day_candidate == base_date,
            }
        )

    selected_bucket = buckets.get(base_date, [])
    status_totals: Counter[str] = Counter()
    events_payload: List[Dict[str, object]] = []

    for slot in selected_bucket:
        status = _normalize_status(slot.status)
        status_totals[status] += 1
        local_start = slot.start_utc.astimezone(zone)
        duration = getattr(slot, "duration_min", None) or 60
        local_end = local_start + timedelta(minutes=duration)

        recruiter = getattr(slot, "recruiter", None)
        city = getattr(slot, "city", None)
        candidate_user = None
        if getattr(slot, "candidate_tg_id", None) is not None:
            candidate_user = candidates_map.get(int(slot.candidate_tg_id))

        candidate_name = (
            candidate_user.fio
            if candidate_user
            else getattr(slot, "candidate_fio", None)
        )
        candidate_profile_url: Optional[str]
        if candidate_user:
            candidate_profile_url = f"/app/candidates/{candidate_user.id}"
        elif getattr(slot, "candidate_tg_id", None):
            candidate_profile_url = f"/app/candidates?search={slot.candidate_tg_id}"
        else:
            candidate_profile_url = None

        candidate_status = None
        if candidate_user is not None:
            raw_status = getattr(candidate_user, "candidate_status", None)
            candidate_status = raw_status.value if hasattr(raw_status, "value") else raw_status

        events_payload.append(
            {
                "id": slot.id,
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "status_variant": STATUS_VARIANTS.get(status, "muted"),
                "start_time": local_start.strftime("%H:%M"),
                "end_time": local_end.strftime("%H:%M"),
                "start_iso": slot.start_utc.isoformat(),
                "duration": duration,
                "recruiter": {
                    "id": recruiter.id if recruiter else None,
                    "name": recruiter.name if recruiter else "",
                    "tz": getattr(recruiter, "tz", DEFAULT_TZ),
                },
                "city": {
                    "id": city.id if city else None,
                    "name": city.name if city else "",
                },
                "candidate": {
                    "id": candidate_user.id if candidate_user else None,
                    "name": candidate_name or "Без имени",
                    "profile_url": candidate_profile_url,
                    "telegram_id": getattr(slot, "candidate_tg_id", None),
                    "status_slug": candidate_status,
                },
            }
        )

    events_total = len(events_payload)
    status_summary = {
        key: status_totals.get(key, 0)
        for key in STATUS_LABELS.keys()
    }
    meta_parts = []
    if status_summary.get("CONFIRMED_BY_CANDIDATE"):
        meta_parts.append(
            f"Подтверждено: {status_summary['CONFIRMED_BY_CANDIDATE']}"
        )
    meta_text = " • ".join(meta_parts) if meta_parts else "Нет назначенных интервью"

    generated_at = datetime.now(timezone.utc)
    generated_local = generated_at.astimezone(zone)

    return {
        "ok": True,
        "selected_date": base_date.isoformat(),
        "selected_label": _selected_label(base_date, now_local.date()),
        "selected_human": base_date.strftime("%d.%m.%Y"),
        "timezone": getattr(zone, "key", getattr(zone, "zone", tz_name)),
        "days": days_payload,
        "events": events_payload,
        "events_total": events_total,
        "status_summary": status_summary,
        "meta": meta_text,
        "updated_label": generated_local.strftime("Обновлено %H:%M"),
        "generated_at": generated_at.isoformat(),
        "window_days": days,
    }
