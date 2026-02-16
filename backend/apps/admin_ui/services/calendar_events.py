"""Calendar events service for FullCalendar integration.

Provides slots in FullCalendar-compatible format with all statuses.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.utils import DEFAULT_TZ, safe_zone
from backend.core.cache import get_cache
from backend.core.microcache import get as microcache_get, set as microcache_set
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import Recruiter, Slot, SlotStatus

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
    cache = None
    try:
        cache = get_cache()
    except RuntimeError:
        cache = None
    statuses_key = ",".join(sorted((s or "").strip().lower() for s in (statuses or [])) or [])
    cache_key = (
        "calendar:events:v1:"
        f"{start_date.isoformat()}:{end_date.isoformat()}:"
        f"r{recruiter_id or 'all'}:c{city_id or 'all'}:"
        f"s{statuses_key or 'all'}:"
        f"tz{tz_name}:x{int(bool(include_canceled))}"
    )
    micro_payload = microcache_get(cache_key)
    if isinstance(micro_payload, dict) and "events" in micro_payload:
        return micro_payload

    if cache is not None:
        cached = await cache.get(cache_key, default=None)
        cached_payload = cached.unwrap_or(None)
        if isinstance(cached_payload, dict) and "events" in cached_payload:
            microcache_set(cache_key, cached_payload, ttl_seconds=2.0)
            return cached_payload

    zone = safe_zone(tz_name)

    # Convert local dates to UTC range
    start_local = datetime.combine(start_date, time.min).replace(tzinfo=zone)
    end_local = datetime.combine(end_date, time.max).replace(tzinfo=zone)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    # Build query
    async with async_session() as session:
        query = (
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
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

        slots = (await session.scalars(query)).all()

        # Load candidate users for profile URLs
        candidate_tg_ids = {
            int(slot.candidate_tg_id)
            for slot in slots
            if slot.candidate_tg_id is not None
        }

        candidates_map: Dict[int, User] = {}
        if candidate_tg_ids:
            users = (
                await session.execute(
                    select(User).where(User.telegram_id.in_(candidate_tg_ids))
                )
            ).scalars().all()
            candidates_map = {user.telegram_id: user for user in users}

        # Load all recruiters for resources
        recruiters_query = select(Recruiter).where(Recruiter.active == True)
        if recruiter_id is not None:
            recruiters_query = recruiters_query.where(Recruiter.id == recruiter_id)
        recruiters = (await session.scalars(recruiters_query)).all()

    # Build events array
    events: List[Dict[str, Any]] = []
    for slot in slots:
        status = _normalize_status(slot.status)
        status_config = _get_status_config(status)

        local_start = slot.start_utc.astimezone(zone)
        duration = slot.duration_min or 60
        local_end = local_start + timedelta(minutes=duration)

        recruiter = slot.recruiter
        city = slot.city

        # Get candidate info
        candidate_user = None
        if slot.candidate_tg_id is not None:
            candidate_user = candidates_map.get(int(slot.candidate_tg_id))

        candidate_name = (
            candidate_user.fio if candidate_user
            else slot.candidate_fio
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
            "id": f"slot-{slot.id}",
            "title": title,
            "start": slot.start_utc.isoformat(),
            "end": (slot.start_utc + timedelta(minutes=duration)).isoformat(),
            "backgroundColor": status_config["color"],
            "borderColor": status_config["color"],
            "textColor": status_config["textColor"],
            "classNames": [status_config["className"]],
            "editable": status == SlotStatus.FREE.lower(),
            "resourceId": f"recruiter-{slot.recruiter_id}",
            "extendedProps": {
                "slot_id": slot.id,
                "status": status,
                "status_label": status_config["label"],
                "recruiter_id": recruiter.id if recruiter else None,
                "recruiter_name": recruiter.name if recruiter else "",
                "recruiter_tz": getattr(recruiter, "tz", DEFAULT_TZ) if recruiter else DEFAULT_TZ,
                "city_id": city.id if city else None,
                "city_name": city.name if city else "",
                "city_tz": getattr(city, "tz", DEFAULT_TZ) if city else None,
                "candidate_id": candidate_user.id if candidate_user else None,
                "candidate_name": candidate_name,
                "candidate_tg_id": slot.candidate_tg_id,
                "candidate_tz": slot.candidate_tz,
                "duration_min": duration,
                "local_start": local_start.strftime("%H:%M"),
                "local_end": local_end.strftime("%H:%M"),
                "local_date": local_start.strftime("%Y-%m-%d"),
            },
        }
        events.append(event)

    # Build resources array (recruiters)
    resources: List[Dict[str, Any]] = []
    for recruiter in recruiters:
        resources.append({
            "id": f"recruiter-{recruiter.id}",
            "title": recruiter.name,
            "extendedProps": {
                "recruiter_id": recruiter.id,
                "tz": getattr(recruiter, "tz", DEFAULT_TZ),
            },
        })

    result = {
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
    microcache_set(cache_key, result, ttl_seconds=2.0)
    if cache is not None:
        await cache.set(cache_key, result, ttl=timedelta(seconds=2))
    return result
