from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.sql import Select

from backend.core.db import async_session
from backend.domain.candidates.models import TestResult, User
try:
    from backend.domain.models import City, KPIWeekly, Recruiter, Slot, SlotStatus
except ImportError:  # pragma: no cover - optional KPI storage
    from backend.domain.models import City, Recruiter, Slot, SlotStatus
    KPIWeekly = None  # type: ignore[assignment]

__all__ = [
    "get_weekly_kpis",
    "list_weekly_history",
    "get_week_window",
    "compute_weekly_snapshot",
    "store_weekly_snapshot",
    "reset_weekly_cache",
]

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from backend.apps.admin_ui.security import Principal


DEFAULT_COMPANY_TZ = "Europe/Moscow"
BOOKING_STATES = {
    SlotStatus.PENDING,
    SlotStatus.BOOKED,
    SlotStatus.CONFIRMED_BY_CANDIDATE,
}
BOOKING_STATES_LOWER = tuple(state.lower() for state in BOOKING_STATES)
SUCCESS_OUTCOMES = {"success", "passed", "accepted", "hired"}
INTRO_ATTEND_STATES = {SlotStatus.CONFIRMED_BY_CANDIDATE}
INTRO_ATTEND_STATES_LOWER = tuple(state.lower() for state in INTRO_ATTEND_STATES)
CONFIRMED_STATUS = SlotStatus.CONFIRMED_BY_CANDIDATE.lower()
_CACHE_TTL_SECONDS = 60


@dataclass(frozen=True)
class WeekWindow:
    tz: ZoneInfo
    week_start_local: datetime
    week_end_local: datetime
    week_start_utc: datetime
    week_end_utc: datetime
    week_start_date: date


@dataclass(frozen=True)
class WeeklySnapshot:
    week_start: date
    metrics: Dict[str, int]
    computed_at: datetime


_METRIC_META: Tuple[Dict[str, str], ...] = (
    {
        "key": "tested",
        "label": "Проходили тест",
        "tone": "progress",
        "icon": "🧪",
    },
    {
        "key": "completed_test",
        "label": "Дошли до конца теста",
        "tone": "success",
        "icon": "🎯",
    },
    {
        "key": "booked",
        "label": "Записались на собеседование",
        "tone": "progress",
        "icon": "🗓",
    },
    {
        "key": "confirmed",
        "label": "Подтвердили участие",
        "tone": "success",
        "icon": "✅",
    },
    {
        "key": "interview_passed",
        "label": "Прошли собеседование",
        "tone": "success",
        "icon": "🏁",
    },
    {
        "key": "intro_day",
        "label": "Пришли на ознакомительный день",
        "tone": "warning",
        "icon": "🌅",
    },
)


_CACHE_LOCK = asyncio.Lock()
_WTD_CACHE: Optional[Dict[str, object]] = None


def _ensure_kpi_model() -> None:
    if KPIWeekly is None:  # pragma: no cover - defensive guard
        raise RuntimeError("KPIWeekly model is not available in this build")


def _normalize_timezone_name(tz_name: Optional[str]) -> str:
    if tz_name and tz_name.strip():
        candidate = tz_name.strip()
    else:
        candidate = os.getenv("COMPANY_TZ") or os.getenv("TZ") or DEFAULT_COMPANY_TZ
    return candidate


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")
    except Exception:  # pragma: no cover - defensive fallback
        return ZoneInfo("UTC")


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_week_window(now: Optional[datetime] = None, tz_name: Optional[str] = None) -> WeekWindow:
    current = _ensure_aware(now or datetime.now(timezone.utc))
    tz = _resolve_timezone(_normalize_timezone_name(tz_name))
    local_now = current.astimezone(tz)
    days_since_sunday = (local_now.weekday() + 1) % 7
    week_start_local = (local_now - timedelta(days=days_since_sunday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end_local = week_start_local + timedelta(days=7)
    week_start_utc = week_start_local.astimezone(timezone.utc)
    week_end_utc = week_end_local.astimezone(timezone.utc)
    return WeekWindow(
        tz=tz,
        week_start_local=week_start_local,
        week_end_local=week_end_local,
        week_start_utc=week_start_utc,
        week_end_utc=week_end_utc,
        week_start_date=week_start_local.date(),
    )


def _window_for_week_start(week_start: date, tz: ZoneInfo) -> WeekWindow:
    local_start = datetime.combine(week_start, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=7)
    return WeekWindow(
        tz=tz,
        week_start_local=local_start,
        week_end_local=local_end,
        week_start_utc=local_start.astimezone(timezone.utc),
        week_end_utc=local_end.astimezone(timezone.utc),
        week_start_date=week_start,
    )


async def _query_metrics(
    session,
    start_utc: datetime,
    end_utc: datetime,
    *,
    recruiter_id: Optional[int] = None,
) -> Dict[str, int]:
    metrics: Dict[str, int] = {}

    tested_query = (
        select(func.count(func.distinct(TestResult.user_id)))
        .join(User, User.id == TestResult.user_id)
        .where(
            TestResult.created_at >= start_utc,
            TestResult.created_at < end_utc,
        )
    )
    if recruiter_id is not None:
        tested_query = tested_query.where(User.responsible_recruiter_id == recruiter_id)
    tested = await session.scalar(tested_query)
    metrics["tested"] = int(tested or 0)
    metrics["completed_test"] = metrics["tested"]

    booking_conditions = (
        Slot.candidate_tg_id.isnot(None),
        func.lower(Slot.purpose) == "interview",
        Slot.updated_at >= start_utc,
        Slot.updated_at < end_utc,
    )

    booked_query = select(func.count(func.distinct(Slot.candidate_tg_id))).where(
        *booking_conditions,
        func.lower(Slot.status).in_(BOOKING_STATES_LOWER),
    )
    if recruiter_id is not None:
        booked_query = booked_query.where(Slot.recruiter_id == recruiter_id)
    booked = await session.scalar(booked_query)
    metrics["booked"] = int(booked or 0)

    confirmed_query = select(func.count(func.distinct(Slot.candidate_tg_id))).where(
        *booking_conditions,
        func.lower(Slot.status) == CONFIRMED_STATUS,
    )
    if recruiter_id is not None:
        confirmed_query = confirmed_query.where(Slot.recruiter_id == recruiter_id)
    confirmed = await session.scalar(confirmed_query)
    metrics["confirmed"] = int(confirmed or 0)

    interview_query = select(func.count(func.distinct(Slot.candidate_tg_id))).where(
        Slot.candidate_tg_id.isnot(None),
        func.lower(Slot.purpose) == "interview",
        func.lower(Slot.interview_outcome).in_(SUCCESS_OUTCOMES),
        Slot.updated_at >= start_utc,
        Slot.updated_at < end_utc,
    )
    if recruiter_id is not None:
        interview_query = interview_query.where(Slot.recruiter_id == recruiter_id)
    interview_passed = await session.scalar(interview_query)
    metrics["interview_passed"] = int(interview_passed or 0)

    intro_query = select(func.count(func.distinct(Slot.candidate_tg_id))).where(
        Slot.candidate_tg_id.isnot(None),
        func.lower(Slot.purpose) == "intro_day",
        func.lower(Slot.status).in_(INTRO_ATTEND_STATES_LOWER),
        Slot.updated_at >= start_utc,
        Slot.updated_at < end_utc,
    )
    if recruiter_id is not None:
        intro_query = intro_query.where(Slot.recruiter_id == recruiter_id)
    intro_day = await session.scalar(intro_query)
    metrics["intro_day"] = int(intro_day or 0)

    return metrics


def _format_event(dt: datetime, tz: ZoneInfo) -> Tuple[str, str, str]:
    aware = _ensure_aware(dt)
    localized = aware.astimezone(tz)
    iso_value = localized.isoformat()
    label = f"{localized.strftime('%d.%m.%Y %H:%M')} {localized.tzname() or tz.key}"
    return iso_value, label, getattr(localized.tzinfo, "key", tz.key)


def _safe_zone(name: Optional[str], default: ZoneInfo) -> ZoneInfo:
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            return default
        except Exception:  # pragma: no cover - defensive
            return default
    return default


async def _test_details(
    session,
    start_utc: datetime,
    end_utc: datetime,
    tz: ZoneInfo,
    *,
    recruiter_id: Optional[int] = None,
) -> List[Dict[str, object]]:
    query: Select = (
        select(
            TestResult.user_id,
            TestResult.created_at,
            User.fio,
            User.city,
        )
        .join(User, User.id == TestResult.user_id)
        .where(
            TestResult.created_at >= start_utc,
            TestResult.created_at < end_utc,
        )
        .order_by(TestResult.created_at.desc(), TestResult.id.desc())
    )
    if recruiter_id is not None:
        query = query.where(User.responsible_recruiter_id == recruiter_id)
    rows = await session.execute(query)
    seen: set[int] = set()
    details: List[Dict[str, object]] = []
    for user_id, created_at, fio, city in rows:
        if user_id in seen:
            continue
        seen.add(int(user_id))
        iso_value, label, tz_label = _format_event(created_at, tz)
        details.append(
            {
                "candidate": fio or f"User #{user_id}",
                "recruiter": "—",
                "event_at": iso_value,
                "event_label": label,
                "city": city or "—",
                "timezone": tz_label,
            }
        )
    return details


async def _slot_details(
    session,
    start_utc: datetime,
    end_utc: datetime,
    tz: ZoneInfo,
    *,
    purpose: str,
    status_filter: Optional[Iterable[str]] = None,
    outcome_filter: Optional[Iterable[str]] = None,
    recruiter_id: Optional[int] = None,
) -> List[Dict[str, object]]:
    conditions = [
        Slot.candidate_tg_id.isnot(None),
        Slot.updated_at >= start_utc,
        Slot.updated_at < end_utc,
        func.lower(Slot.purpose) == purpose.lower(),
    ]
    if recruiter_id is not None:
        conditions.append(Slot.recruiter_id == recruiter_id)
    if status_filter is not None:
        lowered = {value.lower() for value in status_filter}
        conditions.append(func.lower(Slot.status).in_(lowered))
    if outcome_filter is not None:
        lowered = {value.lower() for value in outcome_filter}
        conditions.append(func.lower(Slot.interview_outcome).in_(lowered))

    query: Select = (
        select(
            Slot.candidate_tg_id,
            Slot.candidate_fio,
            Slot.updated_at,
            Recruiter.name.label("recruiter_name"),
            City.name.label("city_name"),
            Slot.candidate_tz,
            City.tz.label("city_tz"),
        )
        .join(Recruiter, Slot.recruiter_id == Recruiter.id, isouter=True)
        .join(City, Slot.city_id == City.id, isouter=True)
        .where(*conditions)
        .order_by(Slot.updated_at.desc(), Slot.id.desc())
    )

    rows = await session.execute(query)
    details: List[Dict[str, object]] = []
    seen: set[int] = set()
    for (
        candidate_tg_id,
        candidate_fio,
        updated_at,
        recruiter_name,
        city_name,
        candidate_tz,
        city_tz,
    ) in rows:
        if candidate_tg_id is None:
            continue
        candidate_key = int(candidate_tg_id)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        zone = _safe_zone(candidate_tz or city_tz, tz)
        iso_value, label, tz_label = _format_event(updated_at, zone)
        display_name = candidate_fio or f"TG {candidate_key}"
        recruiter_value = recruiter_name or "—"
        details.append(
            {
                "candidate": display_name,
                "recruiter": recruiter_value,
                "event_at": iso_value,
                "event_label": label,
                "city": city_name or "—",
                "timezone": tz_label,
            }
        )
    return details


async def _collect_details(
    session,
    start_utc: datetime,
    end_utc: datetime,
    tz: ZoneInfo,
    *,
    recruiter_id: Optional[int] = None,
) -> Dict[str, List[Dict[str, object]]]:
    details: Dict[str, List[Dict[str, object]]] = {}
    tested_details = await _test_details(session, start_utc, end_utc, tz, recruiter_id=recruiter_id)
    details["tested"] = tested_details
    details["completed_test"] = tested_details

    details["booked"] = await _slot_details(
        session,
        start_utc,
        end_utc,
        tz,
        purpose="interview",
        status_filter=BOOKING_STATES,
        recruiter_id=recruiter_id,
    )

    details["confirmed"] = await _slot_details(
        session,
        start_utc,
        end_utc,
        tz,
        purpose="interview",
        status_filter={SlotStatus.CONFIRMED_BY_CANDIDATE},
        recruiter_id=recruiter_id,
    )

    details["interview_passed"] = await _slot_details(
        session,
        start_utc,
        end_utc,
        tz,
        purpose="interview",
        outcome_filter=SUCCESS_OUTCOMES,
        recruiter_id=recruiter_id,
    )

    details["intro_day"] = await _slot_details(
        session,
        start_utc,
        end_utc,
        tz,
        purpose="intro_day",
        status_filter=INTRO_ATTEND_STATES,
        recruiter_id=recruiter_id,
    )

    return details


def _trend(current: int, previous: int) -> Dict[str, Optional[float]]:
    if previous <= 0:
        return {"direction": "up" if current > 0 else "flat", "percent": None}
    delta = current - previous
    change = round((delta / previous) * 100, 1)
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    return {"direction": direction, "percent": change}


def _trend_info(trend: Dict[str, Optional[float]]) -> Dict[str, object]:
    percent = trend.get("percent")
    direction = trend.get("direction", "flat")
    if percent is None:
        return {
            "direction": direction,
            "percent": None,
            "display": "—",
            "label": "Нет данных за прошлую неделю",
            "arrow": "→",
            "magnitude": None,
        }
    magnitude = abs(percent)
    formatted = f"{magnitude:.1f}".rstrip("0").rstrip(".")
    arrow = "↑" if direction == "up" else "↓" if direction == "down" else "→"
    if direction == "up":
        label = f"Рост на {formatted}%"
    elif direction == "down":
        label = f"Снижение на {formatted}%"
    else:
        label = "Без изменений"
    return {
        "direction": direction,
        "percent": percent,
        "display": f"{arrow} {formatted}%",
        "label": label,
        "arrow": arrow,
        "magnitude": formatted,
    }


def _serialize_cards(
    metrics: Dict[str, int],
    previous_metrics: Dict[str, int],
    details: Dict[str, List[Dict[str, object]]],
) -> List[Dict[str, object]]:
    cards: List[Dict[str, object]] = []
    for meta in _METRIC_META:
        key = meta["key"]
        current_value = metrics.get(key, 0)
        previous_value = previous_metrics.get(key, 0)
        trend = _trend_info(_trend(current_value, previous_value))
        card = {
            "key": key,
            "label": meta["label"],
            "tone": meta["tone"],
            "icon": meta["icon"],
            "value": current_value,
            "previous": previous_value,
            "trend": trend,
            "details": details.get(key, []),
        }
        cards.append(card)
    return cards


async def _load_previous_metrics(
    week_start: date,
    start_utc: datetime,
    end_utc: datetime,
) -> Tuple[Dict[str, int], Optional[str]]:
    if KPIWeekly is None:
        async with async_session() as session:
            metrics = await _query_metrics(session, start_utc, end_utc)
            return metrics, None

    async with async_session() as session:
        stored = await session.get(KPIWeekly, week_start)
        if stored is not None:
            return (
                {
                    "tested": stored.tested,
                    "completed_test": stored.completed_test,
                    "booked": stored.booked,
                    "confirmed": stored.confirmed,
                    "interview_passed": stored.interview_passed,
                    "intro_day": stored.intro_day,
                },
                _ensure_aware(stored.computed_at).astimezone(timezone.utc).isoformat(),
            )

    async with async_session() as fresh_session:
        metrics = await _query_metrics(fresh_session, start_utc, end_utc)
        return metrics, None


def _week_label(start: date) -> str:
    end = start + timedelta(days=6)
    return f"{start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}"


def _current_time() -> datetime:
    override = os.getenv("KPI_NOW")
    if override:
        try:
            parsed = datetime.fromisoformat(override)
        except ValueError:
            parsed = None
        else:
            return _ensure_aware(parsed)
    return datetime.now(timezone.utc)


async def _compute_payload(
    tz_name: Optional[str],
    reference_now: datetime,
    *,
    window: Optional[WeekWindow] = None,
    recruiter_id: Optional[int] = None,
) -> Dict[str, object]:
    window = window or get_week_window(now=reference_now, tz_name=tz_name)
    async with async_session() as session:
        metrics = await _query_metrics(
            session,
            window.week_start_utc,
            window.week_end_utc,
            recruiter_id=recruiter_id,
        )
        details = await _collect_details(
            session,
            window.week_start_utc,
            window.week_end_utc,
            window.tz,
            recruiter_id=recruiter_id,
        )

    previous_start = window.week_start_date - timedelta(days=7)
    previous_window = _window_for_week_start(previous_start, window.tz)
    previous_metrics, previous_computed = await _load_previous_metrics(
        previous_start,
        previous_window.week_start_utc,
        previous_window.week_end_utc,
    )

    cards = _serialize_cards(metrics, previous_metrics, details)
    payload = {
        "timezone": getattr(window.tz, "key", str(window.tz)),
        "current": {
            "week_start": window.week_start_date.isoformat(),
            "week_end": (window.week_start_date + timedelta(days=7)).isoformat(),
            "label": _week_label(window.week_start_date),
            "metrics": cards,
        },
        "previous": {
            "week_start": previous_start.isoformat(),
            "week_end": (previous_start + timedelta(days=7)).isoformat(),
            "label": _week_label(previous_start),
            "metrics": previous_metrics,
            "computed_at": previous_computed,
        },
    }
    return payload


async def get_weekly_kpis(
    company_tz: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
    principal: Optional["Principal"] = None,
    recruiter_id: Optional[int] = None,
) -> Dict[str, object]:
    tz_name = _normalize_timezone_name(company_tz)
    reference_now = _ensure_aware(now) if now else _current_time()
    scoped_recruiter_id = recruiter_id
    if getattr(principal, "type", None) == "recruiter":
        scoped_recruiter_id = getattr(principal, "id", None)
    if now is not None:
        return await _compute_payload(tz_name, reference_now, recruiter_id=scoped_recruiter_id)

    window = get_week_window(now=reference_now, tz_name=tz_name)
    cache = _WTD_CACHE if scoped_recruiter_id is None else None
    if scoped_recruiter_id is None:
        if (
            cache
            and cache.get("tz") == tz_name
            and cache.get("week_start") == window.week_start_date
            and cache.get("expires_at") > reference_now
        ):
            return cache["data"]  # type: ignore[return-value]

    async with _CACHE_LOCK:
        cache = _WTD_CACHE if scoped_recruiter_id is None else None
        if scoped_recruiter_id is None:
            if (
                cache
                and cache.get("tz") == tz_name
                and cache.get("week_start") == window.week_start_date
                and cache.get("expires_at") > datetime.now(timezone.utc)
            ):
                return cache["data"]  # type: ignore[return-value]
        payload = await _compute_payload(tz_name, reference_now, window=window, recruiter_id=scoped_recruiter_id)
        if scoped_recruiter_id is None:
            _set_cache(tz_name, window.week_start_date, payload, reference_now)
        return payload


def _set_cache(
    tz_name: str,
    week_start: date,
    payload: Dict[str, object],
    reference_now: datetime,
) -> None:
    global _WTD_CACHE
    _WTD_CACHE = {
        "tz": tz_name,
        "data": payload,
        "week_start": week_start,
        "expires_at": reference_now + timedelta(seconds=_CACHE_TTL_SECONDS),
    }


async def list_weekly_history(limit: int = 12, offset: int = 0) -> List[Dict[str, object]]:
    if KPIWeekly is None:
        return []
    async with async_session() as session:
        rows = await session.execute(
            select(KPIWeekly)
                .order_by(KPIWeekly.week_start.desc())
                .offset(max(0, offset))
                .limit(max(0, limit))
        )
        history: List[Dict[str, object]] = []
        for row in rows.scalars():
            history.append(
                {
                    "week_start": row.week_start.isoformat(),
                    "computed_at": _ensure_aware(row.computed_at)
                    .astimezone(timezone.utc)
                    .isoformat(),
                    "tested": row.tested,
                    "completed_test": row.completed_test,
                    "booked": row.booked,
                    "confirmed": row.confirmed,
                    "interview_passed": row.interview_passed,
                    "intro_day": row.intro_day,
                }
            )
        return history


async def compute_weekly_snapshot(
    week_start: date,
    *,
    tz_name: Optional[str] = None,
) -> WeeklySnapshot:
    tz = _resolve_timezone(_normalize_timezone_name(tz_name))
    window = _window_for_week_start(week_start, tz)
    async with async_session() as session:
        metrics = await _query_metrics(session, window.week_start_utc, window.week_end_utc)
    return WeeklySnapshot(
        week_start=week_start,
        metrics=metrics,
        computed_at=datetime.now(timezone.utc),
    )


async def store_weekly_snapshot(snapshot: WeeklySnapshot) -> None:
    _ensure_kpi_model()
    async with async_session() as session:
        async with session.begin():
            existing = await session.get(KPIWeekly, snapshot.week_start, with_for_update=True)
            if existing is None:
                entry = KPIWeekly(
                    week_start=snapshot.week_start,
                    tested=snapshot.metrics.get("tested", 0),
                    completed_test=snapshot.metrics.get("completed_test", 0),
                    booked=snapshot.metrics.get("booked", 0),
                    confirmed=snapshot.metrics.get("confirmed", 0),
                    interview_passed=snapshot.metrics.get("interview_passed", 0),
                    intro_day=snapshot.metrics.get("intro_day", 0),
                    computed_at=snapshot.computed_at,
                )
                session.add(entry)
            else:
                existing.tested = snapshot.metrics.get("tested", 0)
                existing.completed_test = snapshot.metrics.get("completed_test", 0)
                existing.booked = snapshot.metrics.get("booked", 0)
                existing.confirmed = snapshot.metrics.get("confirmed", 0)
                existing.interview_passed = snapshot.metrics.get("interview_passed", 0)
                existing.intro_day = snapshot.metrics.get("intro_day", 0)
                existing.computed_at = snapshot.computed_at


async def reset_weekly_cache() -> None:
    global _WTD_CACHE
    _WTD_CACHE = None
