"""Calendar events service for FullCalendar integration.

Provides slots in FullCalendar-compatible format with all statuses.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from backend.apps.admin_ui.utils import DEFAULT_TZ, safe_zone
from backend.apps.admin_ui.perf.cache import keys as cache_keys
from backend.apps.admin_ui.perf.cache.readthrough import get_or_compute
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import City, Recruiter, Slot, SlotStatus

__all__ = ["get_calendar_events"]


# Status configuration for UI
STATUS_CONFIG = {
    SlotStatus.FREE: {
        "label": "Свободен",
        "color": "#5BE1A5",
        "textColor": "#1a1a2e",
        "className": "slot-status-free",
    },
    SlotStatus.PENDING: {
        "label": "Ожидает",
        "color": "#F6C16B",
        "textColor": "#1a1a2e",
        "className": "slot-status-pending",
    },
    SlotStatus.BOOKED: {
        "label": "Забронирован",
        "color": "#6aa5ff",
        "textColor": "#ffffff",
        "className": "slot-status-booked",
    },
    SlotStatus.CONFIRMED: {
        "label": "Подтверждён",
        "color": "#a78bfa",
        "textColor": "#ffffff",
        "className": "slot-status-confirmed",
    },
    SlotStatus.CONFIRMED_BY_CANDIDATE: {
        "label": "Подтверждён",
        "color": "#a78bfa",
        "textColor": "#ffffff",
        "className": "slot-status-confirmed",
    },
    SlotStatus.CANCELED: {
        "label": "Отменён",
        "color": "#F07373",
        "textColor": "#ffffff",
        "className": "slot-status-canceled",
    },
}


def _normalize_status(value: Optional[str]) -> str:
    """Normalize status value to lowercase string."""
    if value is None:
        return "unknown"
    raw = value.value if hasattr(value, "value") else value
    return str(raw).strip().lower()


def _get_status_config(status: str) -> Dict[str, str]:
    """Get status display configuration."""
    normalized = _normalize_status(status)
    for key, config in STATUS_CONFIG.items():
        if _normalize_status(key) == normalized:
            return config
    return {
        "label": status or "Unknown",
        "color": "#888888",
        "textColor": "#ffffff",
        "className": "slot-status-unknown",
    }


async def get_calendar_events(
    start_date: date_type,
    end_date: date_type,
    *,
    recruiter_id: Optional[int] = None,
    city_id: Optional[int] = None,
    statuses: Optional[List[str]] = None,
    tz_name: str = DEFAULT_TZ,
    include_canceled: bool = False,
) -> Dict[str, Any]:
    """
    Fetch slots for calendar view in FullCalendar-compatible format.

    Args:
        start_date: Start of date range
        end_date: End of date range (exclusive)
        recruiter_id: Filter by recruiter ID
        city_id: Filter by city ID
        statuses: List of status values to include (e.g., ['free', 'booked'])
        tz_name: Timezone for date interpretation
        include_canceled: Whether to include canceled slots

    Returns:
        Dictionary with 'events' and 'resources' arrays for FullCalendar
    """
    cache_key = cache_keys.calendar_events(
        start_date=start_date,
        end_date=end_date,
        recruiter_id=recruiter_id,
        city_id=city_id,
        statuses=statuses,
        tz_name=tz_name,
        include_canceled=include_canceled,
    ).value
    async def _compute() -> Dict[str, Any]:
        zone = safe_zone(tz_name)

        # Convert local dates to UTC range
        start_local = datetime.combine(start_date, time.min).replace(tzinfo=zone)
        end_local = datetime.combine(end_date, time.max).replace(tzinfo=zone)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)

        # Build query
        async with async_session() as session:
            query = (
                select(
                    Slot.id,
                    Slot.start_utc,
                    Slot.duration_min,
                    Slot.status,
                    Slot.recruiter_id,
                    Slot.city_id,
                    Slot.candidate_tg_id,
                    Slot.candidate_fio,
                    Slot.candidate_tz,
                    Recruiter.id,
                    Recruiter.name,
                    Recruiter.tz,
                    # city is optional
                    City.id,
                    City.name,
                    City.tz,
                )
                .join(Recruiter, Slot.recruiter_id == Recruiter.id)
                .outerjoin(City, Slot.city_id == City.id)
                .where(
                    Slot.start_utc >= start_utc,
                    Slot.start_utc < end_utc,
                )
                .order_by(Slot.start_utc.asc(), Slot.id.asc())
            )

            # Apply filters
            if recruiter_id is not None:
                query = query.where(Slot.recruiter_id == recruiter_id)

            if city_id is not None:
                query = query.where(Slot.city_id == city_id)

            if statuses:
                normalized_statuses = [s.lower() for s in statuses]
                query = query.where(Slot.status.in_(normalized_statuses))
            elif not include_canceled:
                # Exclude canceled by default
                query = query.where(Slot.status != SlotStatus.CANCELED)

            slot_rows = (await session.execute(query)).all()

            # Load candidate users for profile URLs
            candidate_tg_ids = {
                int(candidate_tg_id)
                for (
                    _slot_id,
                    _start_utc,
                    _duration_min,
                    _status,
                    _recruiter_id,
                    _city_id,
                    candidate_tg_id,
                    _candidate_fio,
                    _candidate_tz,
                    _rec_id,
                    _rec_name,
                    _rec_tz,
                    _c_id,
                    _c_name,
                    _c_tz,
                ) in slot_rows
                if candidate_tg_id is not None
            }

            candidates_map: Dict[int, tuple[int, str]] = {}
            if candidate_tg_ids:
                users = (
                    await session.execute(
                        select(User.telegram_id, User.id, User.fio).where(User.telegram_id.in_(candidate_tg_ids))
                    )
                ).all()
                candidates_map = {int(tg_id): (int(user_id), fio) for tg_id, user_id, fio in users if tg_id is not None}

            # Load all recruiters for resources
            recruiters_query = select(Recruiter.id, Recruiter.name, Recruiter.tz).where(Recruiter.active == True)
            if recruiter_id is not None:
                recruiters_query = recruiters_query.where(Recruiter.id == recruiter_id)
            recruiters = (await session.execute(recruiters_query)).all()

        # Build events array
        events: List[Dict[str, Any]] = []
        for (
            slot_id,
            slot_start_utc,
            slot_duration_min,
            slot_status,
            slot_recruiter_id,
            slot_city_id,
            slot_candidate_tg_id,
            slot_candidate_fio,
            slot_candidate_tz,
            rec_id,
            rec_name,
            rec_tz,
            city_id_row,
            city_name_row,
            city_tz_row,
        ) in slot_rows:
            start_utc_value = slot_start_utc
            if start_utc_value and start_utc_value.tzinfo is None:
                start_utc_value = start_utc_value.replace(tzinfo=timezone.utc)

            status = _normalize_status(slot_status)
            status_config = _get_status_config(status)

            local_start = start_utc_value.astimezone(zone) if start_utc_value else start_utc.astimezone(zone)
            duration = slot_duration_min or 60
            local_end = local_start + timedelta(minutes=duration)

            # Get candidate info
            candidate_user_id = None
            candidate_user_fio = None
            if slot_candidate_tg_id is not None:
                entry = candidates_map.get(int(slot_candidate_tg_id))
                if entry is not None:
                    candidate_user_id, candidate_user_fio = entry

            candidate_name = (
                candidate_user_fio if candidate_user_fio
                else slot_candidate_fio
            )

            # Determine title
            if status == SlotStatus.FREE.lower():
                title = "Свободный слот"
            elif candidate_name:
                title = candidate_name
            else:
                title = status_config["label"]

            # Build event object
            event: Dict[str, Any] = {
                "id": f"slot-{slot_id}",
                "title": title,
                "start": (start_utc_value or start_utc).isoformat(),
                "end": ((start_utc_value or start_utc) + timedelta(minutes=duration)).isoformat(),
                "backgroundColor": status_config["color"],
                "borderColor": status_config["color"],
                "textColor": status_config["textColor"],
                "classNames": [status_config["className"]],
                "editable": status == SlotStatus.FREE.lower(),
                "resourceId": f"recruiter-{slot_recruiter_id}",
                "extendedProps": {
                    "slot_id": slot_id,
                    "status": status,
                    "status_label": status_config["label"],
                    "recruiter_id": rec_id,
                    "recruiter_name": rec_name or "",
                    "recruiter_tz": rec_tz or DEFAULT_TZ,
                    "city_id": city_id_row,
                    "city_name": city_name_row or "",
                    "city_tz": city_tz_row,
                    "candidate_id": candidate_user_id,
                    "candidate_name": candidate_name,
                    "candidate_tg_id": slot_candidate_tg_id,
                    "candidate_tz": slot_candidate_tz,
                    "duration_min": duration,
                    "local_start": local_start.strftime("%H:%M"),
                    "local_end": local_end.strftime("%H:%M"),
                    "local_date": local_start.strftime("%Y-%m-%d"),
                },
            }
            events.append(event)

        # Build resources array (recruiters)
        resources: List[Dict[str, Any]] = []
        for rec_id, rec_name, rec_tz in recruiters:
            resources.append({
                "id": f"recruiter-{rec_id}",
                "title": rec_name,
                "extendedProps": {
                    "recruiter_id": rec_id,
                    "tz": rec_tz or DEFAULT_TZ,
                },
            })

        return {
            "events": events,
            "resources": resources,
            "meta": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timezone": tz_name,
                "total_events": len(events),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    return await get_or_compute(
        cache_key,
        expected_type=dict,
        ttl_seconds=2.0,
        stale_seconds=10.0,
        compute=_compute,
    )
