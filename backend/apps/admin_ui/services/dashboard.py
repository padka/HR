from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from typing import Dict, List, Optional, Tuple

from sqlalchemy import (
    and_,
    case,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_ui.timezones import DEFAULT_TZ
from backend.apps.admin_ui.utils import fmt_local, safe_zone
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus, recruiter_city_association
from backend.domain.candidates.models import User, ChatMessage, ChatMessageDirection
from backend.domain.ai.models import AIOutput
from backend.domain.analytics import FunnelEvent
from backend.domain.analytics_models import analytics_events as ANALYTICS_EVENTS
from backend.domain.candidates.status import (
    get_status_label,
    get_status_color,
    get_status_category,
    get_funnel_stages,
    StatusCategory,
    CandidateStatus,
)
from backend.domain.candidate_status_service import CandidateStatusService
from backend.apps.bot.metrics import get_test1_metrics_snapshot
from backend.domain.repositories import resolve_city_id_and_tz_by_plain_name
from backend.core.scoping import scope_candidates, scope_slots, scope_cities
from backend.apps.admin_ui.security import Principal
from backend.core.cache import CacheTTL, get_cache
from backend.apps.admin_ui.perf.cache import keys as cache_keys
from backend.apps.admin_ui.perf.cache.readthrough import get_or_compute

__all__ = [
    "dashboard_counts",
    "get_recent_candidates",
    "get_upcoming_interviews",
    "get_hiring_funnel_stats",
    "get_bot_funnel_stats",
    "get_funnel_step_candidates",
    "get_recruiter_performance",
    "get_recruiter_leaderboard",
    "get_recent_activities",
    "get_ai_insights",
    "get_quick_slots",
    "get_waiting_candidates",
    "get_pipeline_snapshot",
    "smart_create_candidate",
    "format_dashboard_candidate",
    "SmartCreateError",
]

_candidate_status_service = CandidateStatusService()

STATUS_COLOR_TO_CLASS = {
    "success": "new",
    "info": "review",
    "primary": "interview",
    "warning": "pending",
    "danger": "declined",
    "secondary": "pending",
}

FUNNEL_STEP_DEFS: List[Dict[str, object]] = [
    {
        "key": "entered",
        "title": "Зашли в бот",
        "events": [FunnelEvent.BOT_ENTERED.value],
    },
    {
        "key": "test1_started",
        "title": "Начали Тест 1",
        "events": [FunnelEvent.TEST1_STARTED.value],
    },
    {
        "key": "test1_completed",
        "title": "Завершили Тест 1",
        "events": [FunnelEvent.TEST1_COMPLETED.value],
    },
    {
        "key": "test2_started",
        "title": "Начали Тест 2",
        "events": [FunnelEvent.TEST2_STARTED.value],
    },
    {
        "key": "test2_completed",
        "title": "Завершили Тест 2",
        "events": [FunnelEvent.TEST2_COMPLETED.value],
    },
    {
        "key": "slot_booked",
        "title": "Записались на слот",
        "events": [FunnelEvent.SLOT_BOOKED.value, "slot_booked"],
    },
    {
        "key": "slot_confirmed",
        "title": "Подтвердили слот",
        "events": [FunnelEvent.SLOT_CONFIRMED.value],
    },
    {
        "key": "show_up",
        "title": "Пришли",
        "events": [FunnelEvent.SHOW_UP.value],
    },
    {
        "key": "offer_accepted",
        "title": "Закреплены",
        "events": [FunnelEvent.OFFER_ACCEPTED.value],
    },
]

FUNNEL_DROP_TTL_HOURS = 24
_DASHBOARD_CACHE_TTL = timedelta(seconds=2)


class SmartCreateError(Exception):
    """Domain error raised when smart candidate creation fails."""


def format_dashboard_candidate(user: User) -> Dict[str, object]:
    """Serialize user into dashboard-friendly payload."""
    status_display = get_status_label(user.candidate_status)
    status_color = get_status_color(user.candidate_status)
    status_class = STATUS_COLOR_TO_CLASS.get(status_color, "review")
    category = get_status_category(user.candidate_status) if user.candidate_status else None
    date_formatted = user.last_activity.strftime("%d %b %Y") if user.last_activity else "—"

    return {
        "id": user.id,
        "name": user.fio,
        "username": user.username,
        "position": user.desired_position,
        "city": user.city or "Не указан",
        "date": date_formatted,
        "status_display": status_display,
        "status_class": status_class,
        "status_color": status_color,
        "category": category.value if category else None,
        "telegram_id": user.telegram_id,
    }


def _format_waiting_window(
    manual_slot_from: Optional[datetime],
    manual_slot_to: Optional[datetime],
    tz_label: str,
) -> Optional[str]:
    if not manual_slot_from or not manual_slot_to:
        return None
    start = manual_slot_from
    end = manual_slot_to
    start_label = fmt_local(start, tz_label)
    end_label = fmt_local(end, tz_label)
    if start_label[:5] == end_label[:5]:
        # Same day — include hours range only for end
        try:
            _, end_time_part = end_label.split(" ", 1)
        except ValueError:
            end_time_part = end_label
        return f"{start_label}–{end_time_part}"
    return f"{start_label} – {end_label}"


async def dashboard_counts(principal: Optional[Principal] = None) -> Dict[str, object]:
    cache_key = cache_keys.dashboard_counts(principal=principal).value
    async def _compute() -> Dict[str, object]:
        async with async_session() as session:
            principal_type = getattr(principal, "type", None)
            principal_id = getattr(principal, "id", None)

            rec_count = await session.scalar(
                select(func.count(Recruiter.id)).where(Recruiter.active.is_(True))
            )
            if principal_type == "recruiter":
                rec_count = 1

            # Count cities without selecting full ORM rows (hot path under load).
            city_stmt = select(City.id).where(City.active.is_(True))
            city_stmt = scope_cities(city_stmt, principal) if principal else city_stmt
            city_count = await session.scalar(select(func.count()).select_from(city_stmt.subquery()))

            slot_stmt = select(Slot.status, func.count(Slot.id)).where(Slot.status != SlotStatus.CANCELED)
            if principal_type == "recruiter":
                slot_stmt = slot_stmt.where(Slot.recruiter_id == principal_id)
            rows = (await session.execute(slot_stmt.group_by(Slot.status))).all()

            # Count candidates without selecting full ORM rows (hot path under load).
            candidate_stmt = select(User.id).where(
                User.candidate_status.in_([
                    CandidateStatus.WAITING_SLOT,
                    CandidateStatus.STALLED_WAITING_SLOT,
                ])
            )
            candidate_stmt = scope_candidates(candidate_stmt, principal) if principal else candidate_stmt
            waiting_total = await session.scalar(
                select(func.count()).select_from(candidate_stmt.subquery())
            )

        test1_metrics = await get_test1_metrics_snapshot()

        status_map: Dict[str, int] = {
            (status.value if hasattr(status, "value") else status): count for status, count in rows
        }
        total = sum(status_map.values())

        def _norm(name: str) -> str:
            obj = getattr(SlotStatus, name, name)
            return obj.value if hasattr(obj, "value") else obj

        return {
            "recruiters": rec_count or 0,
            "cities": city_count or 0,
            "slots_total": total,
            "slots_free": status_map.get(_norm("FREE"), 0),
            "slots_pending": status_map.get(_norm("PENDING"), 0),
            "slots_booked": status_map.get(_norm("BOOKED"), 0),
            "waiting_candidates_total": waiting_total or 0,
            "test1_rejections_total": test1_metrics.rejections_total,
            "test1_total_seen": test1_metrics.total_seen,
            "test1_rejections_percent": test1_metrics.rejection_percent,
            "test1_rejections_breakdown": test1_metrics.rejection_breakdown,
        }

    return await get_or_compute(
        cache_key,
        expected_type=dict,
        ttl_seconds=_DASHBOARD_CACHE_TTL.total_seconds(),
        stale_seconds=10.0,
        compute=_compute,
    )


async def get_recent_candidates(limit: int = 5, *, principal: Optional[Principal] = None) -> List[Dict[str, object]]:
    """Get recent candidates/applications for dashboard."""
    async with async_session() as session:
        stmt = (
            select(User)
            .where(User.is_active == True)
            .order_by(User.last_activity.desc())
            .limit(limit)
        )
        if principal is not None:
            stmt = scope_candidates(stmt, principal)
        result = await session.execute(stmt)
        users = result.scalars().all()

        return [format_dashboard_candidate(user) for user in users]


async def get_waiting_candidates(limit: int = 6, *, principal: Optional[Principal] = None) -> List[Dict[str, object]]:
    """Return candidates waiting for manual slot assignment (prioritized)."""
    cache_key = cache_keys.dashboard_incoming(principal=principal, limit=limit).value
    async def _compute() -> List[Dict[str, object]]:
        last_message_map: Dict[int, dict] = {}
        recruiter_map: Dict[int, str] = {}
        ai_fit_map: Dict[int, Dict[str, Optional[object]]] = {}
        async with async_session() as session:
            recruiter_city_ids: set[int] = set()
            query_limit = limit
            principal_type = getattr(principal, "type", None)
            principal_id = getattr(principal, "id", None)
            if principal_type == "recruiter" and principal_id is not None:
                rows = await session.execute(
                    select(recruiter_city_association.c.city_id).where(
                        recruiter_city_association.c.recruiter_id == principal_id
                    )
                )
                recruiter_city_ids = {row[0] for row in rows}
                query_limit = max(limit * 5, 20)
            status_filter = User.candidate_status.in_([
                CandidateStatus.WAITING_SLOT,
                CandidateStatus.STALLED_WAITING_SLOT,
            ])
            stmt = (
                select(
                    User.id,
                    User.fio,
                    User.city,
                    User.candidate_status,
                    User.status_changed_at,
                    User.manual_slot_requested_at,
                    User.manual_slot_from,
                    User.manual_slot_to,
                    User.manual_slot_comment,
                    User.telegram_id,
                    User.telegram_user_id,
                    User.telegram_username,
                    User.username,
                    User.responsible_recruiter_id,
                )
                .where(status_filter)
                .order_by(User.status_changed_at.asc(), User.id.asc())
                .limit(query_limit)
            )
            if principal is not None and principal_type == "admin":
                stmt = scope_candidates(stmt, principal)
            result = await session.execute(stmt)
            users = result.all()

            user_ids = [int(row.id) for row in users]
            if user_ids:
                last_msg_sq = (
                    select(
                        ChatMessage.candidate_id.label("candidate_id"),
                        ChatMessage.text.label("text"),
                        ChatMessage.created_at.label("created_at"),
                        func.row_number()
                        .over(
                            partition_by=ChatMessage.candidate_id,
                            order_by=ChatMessage.created_at.desc(),
                        )
                        .label("rn"),
                    )
                    .where(
                        ChatMessage.candidate_id.in_(user_ids),
                        ChatMessage.direction == ChatMessageDirection.INBOUND.value,
                    )
                ).subquery()
                rows = await session.execute(
                    select(last_msg_sq.c.candidate_id, last_msg_sq.c.text, last_msg_sq.c.created_at).where(
                        last_msg_sq.c.rn == 1
                    )
                )
                for candidate_id, text, created_at in rows:
                    last_message_map[int(candidate_id)] = {
                        "text": text,
                        "created_at": created_at,
                    }

                ai_sq = (
                    select(
                        AIOutput.scope_id.label("candidate_id"),
                        AIOutput.payload_json.label("payload_json"),
                        AIOutput.created_at.label("created_at"),
                        func.row_number()
                        .over(
                            partition_by=AIOutput.scope_id,
                            order_by=AIOutput.created_at.desc(),
                        )
                        .label("rn"),
                    )
                    .where(
                        AIOutput.scope_type == "candidate",
                        AIOutput.kind == "candidate_summary_v1",
                        AIOutput.scope_id.in_(user_ids),
                    )
                ).subquery()
                ai_rows = await session.execute(
                    select(ai_sq.c.candidate_id, ai_sq.c.payload_json, ai_sq.c.created_at).where(
                        ai_sq.c.rn == 1
                    )
                )
                for candidate_id, payload_json, created_at in ai_rows:
                    candidate_id = int(candidate_id)
                    fit = payload_json.get("fit") if isinstance(payload_json, dict) else None
                    if not isinstance(fit, dict):
                        ai_fit_map[candidate_id] = {
                            "score": None,
                            "level": None,
                            "updated_at": created_at.isoformat() if created_at else None,
                        }
                        continue
                    raw_score = fit.get("score")
                    score: Optional[int] = None
                    if isinstance(raw_score, (int, float)):
                        score = max(0, min(100, int(raw_score)))
                    raw_level = fit.get("level")
                    level = raw_level.lower().strip() if isinstance(raw_level, str) else None
                    if level not in {"high", "medium", "low", "unknown"}:
                        level = None
                    ai_fit_map[candidate_id] = {
                        "score": score,
                        "level": level,
                        "updated_at": created_at.isoformat() if created_at else None,
                    }

            recruiter_ids = {row.responsible_recruiter_id for row in users if row.responsible_recruiter_id}
            if recruiter_ids:
                recruiters = (
                    await session.execute(select(Recruiter).where(Recruiter.id.in_(recruiter_ids)))
                ).scalars().all()
                recruiter_map = {rec.id: rec.name for rec in recruiters}

        now = datetime.now(timezone.utc)
        tz_cache: Dict[str, str] = {}

        async def _resolve_city(city_label: Optional[str]) -> tuple[str, Optional[int]]:
            key = (city_label or "").strip().lower()
            if not key:
                return (DEFAULT_TZ, None)
            if key in tz_cache:
                return tz_cache[key]
            city_id, tz_value = await resolve_city_id_and_tz_by_plain_name(city_label)
            tz_value = tz_value or DEFAULT_TZ
            tz_cache[key] = (tz_value, city_id)
            return tz_cache[key]

        waiting_rows: List[Dict[str, object]] = []
        for (
            user_id,
            user_fio,
            user_city,
            user_candidate_status,
            user_status_changed_at,
            user_manual_slot_requested_at,
            user_manual_slot_from,
            user_manual_slot_to,
            user_manual_slot_comment,
            user_telegram_id,
            user_telegram_user_id,
            user_telegram_username,
            user_username,
            user_responsible_recruiter_id,
        ) in users:
            tz_label, city_id = await _resolve_city(user_city)
            if principal is not None and getattr(principal, "type", None) == "recruiter":
                owner_id = user_responsible_recruiter_id
                if owner_id == getattr(principal, "id", None):
                    pass
                elif city_id and city_id in recruiter_city_ids:
                    pass
                else:
                    continue
            waiting_since = user_status_changed_at or user_manual_slot_requested_at
            waiting_hours = None
            normalized_waiting_since = waiting_since
            if normalized_waiting_since and normalized_waiting_since.tzinfo is None:
                normalized_waiting_since = normalized_waiting_since.replace(tzinfo=timezone.utc)
            if normalized_waiting_since:
                delta = now - normalized_waiting_since
                waiting_hours = max(0, int(delta.total_seconds() // 3600))

            waiting_since_iso = waiting_since.isoformat() if waiting_since else None
            last_msg = last_message_map.get(int(user_id))
            last_msg_at = last_msg.get("created_at") if last_msg else None
            waiting_rows.append(
                {
                    "id": int(user_id),
                    "name": user_fio,
                    "city": user_city or "Не указан",
                    "city_id": city_id,
                    "status_display": get_status_label(user_candidate_status),
                    "status_color": get_status_color(user_candidate_status),
                    "status_slug": user_candidate_status.value if user_candidate_status else None,
                    "waiting_since": waiting_since_iso,
                    "waiting_since_dt": normalized_waiting_since,
                    "waiting_hours": waiting_hours,
                    "availability_window": _format_waiting_window(user_manual_slot_from, user_manual_slot_to, tz_label),
                    "availability_note": user_manual_slot_comment,
                    "tz": tz_label,
                    "telegram_id": user_telegram_id,
                    "telegram_user_id": user_telegram_user_id or user_telegram_id,
                    "telegram_username": user_telegram_username or user_username,
                    "last_message": last_msg.get("text") if last_msg else None,
                    "last_message_at": last_msg_at.isoformat() if last_msg_at else None,
                    "ai_relevance_score": ai_fit_map.get(int(user_id), {}).get("score"),
                    "ai_relevance_level": ai_fit_map.get(int(user_id), {}).get("level"),
                    "ai_relevance_updated_at": ai_fit_map.get(int(user_id), {}).get("updated_at"),
                    "responsible_recruiter_id": user_responsible_recruiter_id,
                    "responsible_recruiter_name": recruiter_map.get(user_responsible_recruiter_id) if user_responsible_recruiter_id else None,
                    "schedule_url": f"/candidates/{int(user_id)}/schedule-slot",
                    "profile_url": f"/candidates/{int(user_id)}",
                    "priority_score": 0,  # will be updated below
                }
            )

        def _priority(row: Dict[str, object]) -> tuple:
            is_stalled = (row.get("status_slug") == CandidateStatus.STALLED_WAITING_SLOT.value)
            wait_hours = row.get("waiting_hours") or 0
            wait_since = row.get("waiting_since_dt") or datetime.now(timezone.utc)
            return (
                0 if is_stalled else 1,            # stalled first
                -int(wait_hours),                  # longer waiting first
                wait_since,                        # older requests first
            )

        prioritized = sorted(waiting_rows, key=_priority)
        for idx, row in enumerate(prioritized, start=1):
            row["priority_score"] = idx
            row.pop("waiting_since_dt", None)

        return prioritized[:limit]

    return await get_or_compute(
        cache_key,
        expected_type=list,
        ttl_seconds=_DASHBOARD_CACHE_TTL.total_seconds(),
        stale_seconds=10.0,
        compute=_compute,
    )


def _format_delta(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 60:
        return "идёт сейчас"
    minutes = total_seconds // 60
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes and not days:
        parts.append(f"{minutes} мин")
    return "через " + " ".join(parts)


SLOT_STATUS_LABELS = {
    SlotStatus.BOOKED: "Подтверждено",
    SlotStatus.CONFIRMED_BY_CANDIDATE: "Подтверждено кандидатом",
}


async def get_upcoming_interviews(
    limit: int = 20,
    recruiter_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> List[Dict[str, object]]:
    """Get upcoming interviews (booked slots) for dashboard."""
    now = datetime.now(timezone.utc)
    # Show ближайшую неделю, чтобы одобренные слоты не терялись за пределами 48 часов.
    window_end = now + timedelta(days=7)

    start_bound = date_from if date_from else now
    end_bound = date_to if date_to else window_end

    async with async_session() as session:
        stmt = (
            select(Slot, Recruiter, City, User)
            .join(Recruiter, Slot.recruiter_id == Recruiter.id)
            .outerjoin(City, Slot.city_id == City.id)
            .outerjoin(
                User,
                or_(
                    User.candidate_id == Slot.candidate_id,
                    User.telegram_id == Slot.candidate_tg_id,
                ),
            )
            .where(
                and_(
                    or_(
                        Slot.status == SlotStatus.PENDING,
                        Slot.status == SlotStatus.BOOKED,
                        Slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE
                    ),
                    Slot.start_utc >= start_bound,
                    Slot.start_utc <= end_bound
                )
            )
            .order_by(Slot.start_utc.asc())
            .limit(limit)
        )
        if recruiter_id:
            stmt = stmt.where(Slot.recruiter_id == recruiter_id)
        result = await session.execute(stmt)
        rows = result.all()

        interviews = []
        for slot, recruiter, city, candidate in rows:
            slot_start = slot.start_utc or now
            if slot_start.tzinfo is None:
                slot_start = slot_start.replace(tzinfo=timezone.utc)
            slot_end = slot_start + timedelta(minutes=slot.duration_min or 60)
            slot_tz = (
                getattr(slot, "tz_name", None)
                or (city.tz if city else None)
                    or recruiter.tz
                    or DEFAULT_TZ
            )
            zone = safe_zone(slot_tz)
            local_start = slot_start.astimezone(zone)
            local_end = slot_end.astimezone(zone)

            countdown = _format_delta(max(slot_start - now, timedelta(seconds=0)))
            telemost_url = (recruiter.telemost_url or "").strip() or None
            city_label = (
                getattr(city, "name_plain", None)
                or getattr(city, "name", None)
                or "Город не указан"
            )
            candidate_name = slot.candidate_fio or (candidate.fio if candidate else "Кандидат")
            candidate_url = f"/candidates/{candidate.id}" if candidate else None
            purpose = (slot.purpose or "").strip().lower()
            position_label = slot.purpose.title() if slot.purpose else "Interview"
            slot_status = SLOT_STATUS_LABELS.get(slot.status, "В графике")
            event_kind = "Ознакомительный день" if purpose == "intro_day" else "Собеседование"

            interviews.append(
                {
                    "id": slot.id,
                    "candidate_name": candidate_name,
                    "candidate_url": candidate_url,
                    "position": f"{position_label} — {city_label}",
                    "recruiter_name": recruiter.name,
                    "city_name": city_label,
                    "telemost_url": telemost_url,
                    "time_range": f"{local_start.strftime('%H:%M')}–{local_end.strftime('%H:%M')} ({slot_tz})",
                    "date_label": local_start.strftime("%d %b"),
                    "local_time": local_start.strftime("%H:%M"),
                    "starts_in": countdown,
                    "slot_status_label": slot_status,
                    "candidate_id": candidate.id if candidate else None,
                    "tz_name": slot_tz,
                    "event_kind": event_kind,
                }
            )

        return interviews


async def get_quick_slots(window_hours: int = 48) -> List[Dict[str, object]]:
    """Return free slots for the smart create modal."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=window_hours)

    async with async_session() as session:
        stmt = (
            select(Slot, Recruiter, City)
            .join(Recruiter, Slot.recruiter_id == Recruiter.id)
            .outerjoin(City, Slot.city_id == City.id)
            .where(
                and_(
                    Slot.status == SlotStatus.FREE,
                    Slot.start_utc >= now,
                    Slot.start_utc <= end,
                )
            )
            .order_by(Slot.start_utc.asc())
        )
        result = await session.execute(stmt)
        rows = result.all()

    options: List[Dict[str, object]] = []
    for slot, recruiter, city in rows:
        local_time = slot.start_utc.astimezone(timezone.utc)
        day_label = local_time.strftime("%d %b, %H:%M")
        recruiter_name = recruiter.name if recruiter else "Рекрутер"
        city_label = city.name if city else "Онлайн"
        options.append(
            {
                "id": slot.id,
                "label": f"{day_label} · {recruiter_name} ({city_label})",
                "start_iso": slot.start_utc.isoformat(),
            }
        )
    return options


async def get_hiring_funnel_stats() -> Dict[str, object]:
    """Get hiring funnel statistics for dashboard visualization."""
    stage_definitions: List[Tuple[str, List[CandidateStatus]]] = []
    for name, statuses in get_funnel_stages():
        if name == "Тестирование":
            statuses = statuses + [
                CandidateStatus.WAITING_SLOT,
                CandidateStatus.STALLED_WAITING_SLOT,
            ]
        stage_definitions.append((name, statuses))

    async with async_session() as session:
        # Count candidates by status
        stmt = select(User.candidate_status, func.count()).where(
            User.is_active == True
        ).group_by(User.candidate_status)
        result = await session.execute(stmt)
        status_counts = dict(result.all())

    funnel_data: List[Dict[str, object]] = []
    total_candidates = sum(status_counts.values())

    for stage_name, statuses in stage_definitions:
        stage_total = sum(status_counts.get(status, 0) for status in statuses)
        sub_statuses = []
        for status in statuses:
            count = status_counts.get(status, 0)
            if count > 0:
                sub_statuses.append({
                    "label": get_status_label(status),
                    "count": count,
                    "color": get_status_color(status),
                })

        funnel_data.append({
            "stage": stage_name,
            "total": stage_total,
            "sub_statuses": sub_statuses,
        })

    # Conversion to next step
    for i in range(len(funnel_data) - 1):
        current = funnel_data[i]["total"]
        next_stage_total = funnel_data[i + 1]["total"]
        funnel_data[i]["conversion"] = round((next_stage_total / current) * 100, 1) if current else 0.0
    if funnel_data:
        funnel_data[-1]["conversion"] = funnel_data[-1].get("conversion", 0.0)

    base_total = funnel_data[0]["total"] if funnel_data else total_candidates
    base_total = base_total or total_candidates
    for stage in funnel_data:
        stage["share_of_base"] = round((stage["total"] / base_total) * 100, 1) if base_total else 0.0

    testing_statuses = {
        CandidateStatus.TEST1_COMPLETED,
        CandidateStatus.WAITING_SLOT,
        CandidateStatus.STALLED_WAITING_SLOT,
        CandidateStatus.TEST2_SENT,
        CandidateStatus.TEST2_COMPLETED,
        CandidateStatus.TEST2_FAILED,
    }
    interview_statuses = {
        CandidateStatus.INTERVIEW_SCHEDULED,
        CandidateStatus.INTERVIEW_CONFIRMED,
    }
    intro_statuses = {
        CandidateStatus.INTRO_DAY_SCHEDULED,
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
    }
    declined_statuses = {
        CandidateStatus.INTERVIEW_DECLINED,
        CandidateStatus.TEST2_FAILED,
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
        CandidateStatus.NOT_HIRED,
    }

    summary = {
        "total": total_candidates,
        "testing": sum(status_counts.get(status, 0) for status in testing_statuses),
        "interviewing": sum(status_counts.get(status, 0) for status in interview_statuses),
        "intro_day": sum(status_counts.get(status, 0) for status in intro_statuses),
        "hired": status_counts.get(CandidateStatus.HIRED, 0),
        "declined": sum(status_counts.get(status, 0) for status in declined_statuses),
    }
    summary["conversion_to_hired"] = round(
        (summary["hired"] / summary["total"]) * 100, 1
    ) if summary["total"] else 0.0

    return {"stages": funnel_data, "summary": summary}


def _normalize_funnel_range(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    *,
    default_days: int = 7,
) -> Tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    end = date_to or now
    start = date_from or (end - timedelta(days=default_days))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start > end:
        start, end = end, start
    return start, end


def _clean_filter_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


def _apply_funnel_filters(
    stmt,
    *,
    city: Optional[str],
    recruiter_id: Optional[int],
    source: Optional[str],
):
    if city:
        stmt = stmt.where(func.lower(User.city) == city.lower())
    if recruiter_id is not None:
        stmt = stmt.where(User.responsible_recruiter_id == recruiter_id)
    if source:
        stmt = stmt.where(User.source == source)
    return stmt


def _subject_key(candidate_id: Optional[int], user_id: Optional[int]) -> Optional[int]:
    if candidate_id is not None:
        return int(candidate_id)
    if user_id is not None:
        return int(user_id)
    return None


async def _fetch_funnel_events(
    session: AsyncSession,
    *,
    event_names: List[str],
    date_from: datetime,
    date_to: datetime,
    city: Optional[str],
    recruiter_id: Optional[int],
    source: Optional[str],
) -> List[Tuple[Optional[int], Optional[int], str, datetime]]:
    ae = ANALYTICS_EVENTS
    stmt = select(
        ae.c.candidate_id,
        ae.c.user_id,
        ae.c.event_name,
        ae.c.created_at,
    ).select_from(ae)
    if any([city, recruiter_id is not None, source]):
        stmt = stmt.join(User, User.id == ae.c.candidate_id)
        stmt = _apply_funnel_filters(
            stmt,
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
    stmt = stmt.where(
        ae.c.event_name.in_(event_names),
        ae.c.created_at >= date_from,
        ae.c.created_at <= date_to,
    )
    rows = await session.execute(stmt)
    return list(rows.all())


def _collect_event_stats(
    rows: List[Tuple[Optional[int], Optional[int], str, datetime]],
    *,
    date_from: datetime,
    date_to: datetime,
) -> Tuple[Dict[str, int], Dict[str, set], Dict[int, Dict[str, List[datetime]]]]:
    event_counts: Dict[str, int] = {}
    subject_sets: Dict[str, set] = {}
    events_by_subject: Dict[int, Dict[str, List[datetime]]] = {}
    for candidate_id, user_id, event_name, created_at in rows:
        subject_id = _subject_key(candidate_id, user_id)
        if subject_id is None:
            continue
        bucket = events_by_subject.setdefault(subject_id, {})
        bucket.setdefault(event_name, []).append(created_at)
        if date_from <= created_at <= date_to:
            event_counts[event_name] = event_counts.get(event_name, 0) + 1
            subject_sets.setdefault(event_name, set()).add(subject_id)
    for subject_events in events_by_subject.values():
        for timestamps in subject_events.values():
            timestamps.sort()
    return event_counts, subject_sets, events_by_subject


def _avg_time_between(
    events_by_subject: Dict[int, Dict[str, List[datetime]]],
    *,
    start_event: str,
    end_event: str,
    date_from: datetime,
    date_to: datetime,
) -> Optional[float]:
    deltas: List[float] = []
    for events in events_by_subject.values():
        start_times = [
            ts for ts in events.get(start_event, []) if date_from <= ts <= date_to
        ]
        if not start_times:
            continue
        start_time = min(start_times)
        end_times = [
            ts for ts in events.get(end_event, []) if start_time <= ts <= date_to
        ]
        if not end_times:
            continue
        delta = (min(end_times) - start_time).total_seconds()
        if delta >= 0:
            deltas.append(delta)
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    if percentile <= 0:
        return min(values)
    if percentile >= 1:
        return max(values)
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[int(index)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _time_deltas_between(
    events_by_subject: Dict[int, Dict[str, List[datetime]]],
    *,
    start_event: str,
    end_event: str,
    date_from: datetime,
    date_to: datetime,
) -> List[float]:
    deltas: List[float] = []
    for events in events_by_subject.values():
        start_times = [
            ts for ts in events.get(start_event, []) if date_from <= ts <= date_to
        ]
        if not start_times:
            continue
        start_time = min(start_times)
        end_times = [
            ts for ts in events.get(end_event, []) if start_time <= ts <= date_to
        ]
        if not end_times:
            continue
        delta = (min(end_times) - start_time).total_seconds()
        if delta >= 0:
            deltas.append(delta)
    return deltas


def _step_counts_from_sets(subject_sets: Dict[str, set]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for step in FUNNEL_STEP_DEFS:
        subjects = set()
        for event_name in step["events"]:
            subjects |= subject_sets.get(event_name, set())
        counts[str(step["key"])] = len(subjects)
    return counts


async def get_bot_funnel_stats(
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    city: Optional[str] = None,
    recruiter_id: Optional[int] = None,
    source: Optional[str] = None,
    ttl_hours: int = FUNNEL_DROP_TTL_HOURS,
) -> Dict[str, object]:
    date_from, date_to = _normalize_funnel_range(date_from, date_to)
    city = _clean_filter_value(city)
    source = _clean_filter_value(source)
    window_end = date_to + timedelta(hours=ttl_hours)
    all_event_names = sorted(
        {name for step in FUNNEL_STEP_DEFS for name in step["events"]}
    )
    async with async_session() as session:
        rows = await _fetch_funnel_events(
            session,
            event_names=all_event_names,
            date_from=date_from,
            date_to=window_end,
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
    event_counts, subject_sets, events_by_subject = _collect_event_stats(
        rows,
        date_from=date_from,
        date_to=date_to,
    )

    steps: List[Dict[str, object]] = []
    for step in FUNNEL_STEP_DEFS:
        event_names = step["events"]
        subjects = set()
        total_events = 0
        for event_name in event_names:
            subjects |= subject_sets.get(event_name, set())
            total_events += event_counts.get(event_name, 0)
        steps.append(
            {
                "key": step["key"],
                "title": step["title"],
                "count": len(subjects),
                "events": total_events,
                "conversion_from_prev": 0.0,
                "conversion_from_prev_events": 0.0,
                "dropoff_count": None,
                "avg_time_to_step_sec": None,
            }
        )

    for idx in range(1, len(steps)):
        prev_unique = steps[idx - 1]["count"] or 0
        prev_events = steps[idx - 1]["events"] or 0
        current_unique = steps[idx]["count"] or 0
        current_events = steps[idx]["events"] or 0
        steps[idx]["conversion_from_prev"] = (
            round((current_unique / prev_unique) * 100, 1) if prev_unique else 0.0
        )
        steps[idx]["conversion_from_prev_events"] = (
            round((current_events / prev_events) * 100, 1) if prev_events else 0.0
        )
        steps[idx]["dropoff_count"] = max(prev_unique - current_unique, 0)

    entered_subjects = subject_sets.get(FunnelEvent.BOT_ENTERED.value, set())
    started_subjects = subject_sets.get(FunnelEvent.TEST1_STARTED.value, set())
    completed_subjects = subject_sets.get(FunnelEvent.TEST1_COMPLETED.value, set())

    no_test1 = len(entered_subjects - started_subjects)

    ttl = timedelta(hours=ttl_hours)
    test1_timeout = 0
    for subject_id in started_subjects:
        start_times = [
            ts
            for ts in events_by_subject.get(subject_id, {}).get(
                FunnelEvent.TEST1_STARTED.value, []
            )
            if date_from <= ts <= date_to
        ]
        if not start_times:
            continue
        start_time = min(start_times)
        completion_times = events_by_subject.get(subject_id, {}).get(
            FunnelEvent.TEST1_COMPLETED.value, []
        )
        completed_on_time = any(
            start_time <= ts <= start_time + ttl for ts in completion_times
        )
        if not completed_on_time:
            test1_timeout += 1

    avg_time_map = {
        "test1_started": _avg_time_between(
            events_by_subject,
            start_event=FunnelEvent.BOT_ENTERED.value,
            end_event=FunnelEvent.TEST1_STARTED.value,
            date_from=date_from,
            date_to=date_to,
        ),
        "test1_completed": _avg_time_between(
            events_by_subject,
            start_event=FunnelEvent.TEST1_STARTED.value,
            end_event=FunnelEvent.TEST1_COMPLETED.value,
            date_from=date_from,
            date_to=date_to,
        ),
        "slot_confirmed": _avg_time_between(
            events_by_subject,
            start_event=FunnelEvent.SLOT_BOOKED.value,
            end_event=FunnelEvent.SLOT_CONFIRMED.value,
            date_from=date_from,
            date_to=date_to,
        ),
        "show_up": _avg_time_between(
            events_by_subject,
            start_event=FunnelEvent.SLOT_CONFIRMED.value,
            end_event=FunnelEvent.SHOW_UP.value,
            date_from=date_from,
            date_to=date_to,
        ),
    }
    for step in steps:
        avg_time = avg_time_map.get(step["key"])
        if avg_time is not None:
            step["avg_time_to_step_sec"] = round(avg_time, 1)

    series_labels: List[str] = []
    series_entered: List[int] = []
    series_completed: List[int] = []
    day_cursor = date_from.date()
    last_day = date_to.date()
    daily_entered: Dict[date, set] = {}
    daily_completed: Dict[date, set] = {}
    for subject_id, events in events_by_subject.items():
        for name, timestamps in events.items():
            if name not in {
                FunnelEvent.BOT_ENTERED.value,
                FunnelEvent.TEST1_COMPLETED.value,
            }:
                continue
            for ts in timestamps:
                if not (date_from <= ts <= date_to):
                    continue
                key = ts.date()
                if name == FunnelEvent.BOT_ENTERED.value:
                    daily_entered.setdefault(key, set()).add(subject_id)
                else:
                    daily_completed.setdefault(key, set()).add(subject_id)

    while day_cursor <= last_day:
        series_labels.append(day_cursor.isoformat())
        series_entered.append(len(daily_entered.get(day_cursor, set())))
        series_completed.append(len(daily_completed.get(day_cursor, set())))
        day_cursor += timedelta(days=1)

    step_counts = {step["key"]: step["count"] for step in steps}
    range_days = max(1, (date_to.date() - date_from.date()).days + 1)
    prev_step_counts: Dict[str, int] = {}
    period_delta = date_to - date_from
    prev_to = date_from - timedelta(seconds=1)
    prev_from = prev_to - period_delta
    prev_window_end = prev_to + timedelta(hours=ttl_hours)
    async with async_session() as session:
        prev_rows = await _fetch_funnel_events(
            session,
            event_names=all_event_names,
            date_from=prev_from,
            date_to=prev_window_end,
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
    _, prev_subject_sets, _ = _collect_event_stats(
        prev_rows,
        date_from=prev_from,
        date_to=prev_to,
    )
    prev_step_counts = _step_counts_from_sets(prev_subject_sets)

    summary_cards = []
    summary_flow = [
        ("entered", "Вошли в бот"),
        ("test1_completed", "Завершили Тест 1"),
        ("slot_booked", "Записались на слот"),
        ("show_up", "Пришли на ОД"),
    ]
    prev_count = None
    for key, label in summary_flow:
        count = int(step_counts.get(key, 0) or 0)
        prev_value = int(prev_step_counts.get(key, 0) or 0)
        delta_abs = count - prev_value if prev_value else None
        delta_pct = round((delta_abs / prev_value) * 100, 1) if prev_value else None
        conversion = (
            round((count / prev_count) * 100, 1)
            if prev_count not in (None, 0)
            else None
        )
        per_day = round(count / range_days, 1) if range_days else 0.0
        summary_cards.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "conversion": conversion,
                "per_day": per_day,
                "delta_abs": delta_abs,
                "delta_pct": delta_pct,
            }
        )
        prev_count = count

    speed_transitions = [
        {
            "key": "test1_started",
            "label": "До старта Теста 1",
            "start_event": FunnelEvent.BOT_ENTERED.value,
            "end_event": FunnelEvent.TEST1_STARTED.value,
        },
        {
            "key": "test1_completed",
            "label": "Тест 1 → завершение",
            "start_event": FunnelEvent.TEST1_STARTED.value,
            "end_event": FunnelEvent.TEST1_COMPLETED.value,
        },
        {
            "key": "test2_completed",
            "label": "Тест 2 → завершение",
            "start_event": FunnelEvent.TEST2_STARTED.value,
            "end_event": FunnelEvent.TEST2_COMPLETED.value,
        },
        {
            "key": "slot_confirmed",
            "label": "Бронь → подтверждение",
            "start_event": FunnelEvent.SLOT_BOOKED.value,
            "end_event": FunnelEvent.SLOT_CONFIRMED.value,
        },
        {
            "key": "show_up",
            "label": "Подтверждение → ОД",
            "start_event": FunnelEvent.SLOT_CONFIRMED.value,
            "end_event": FunnelEvent.SHOW_UP.value,
        },
    ]
    speed_rows: List[Dict[str, object]] = []
    for transition in speed_transitions:
        deltas = _time_deltas_between(
            events_by_subject,
            start_event=transition["start_event"],
            end_event=transition["end_event"],
            date_from=date_from,
            date_to=date_to,
        )
        median = _percentile(deltas, 0.5)
        p75 = _percentile(deltas, 0.75)
        speed_rows.append(
            {
                "key": transition["key"],
                "label": transition["label"],
                "median_sec": round(median, 1) if median is not None else None,
                "p75_sec": round(p75, 1) if p75 is not None else None,
                "samples": len(deltas),
            }
        )

    speed_candidates = [
        item for item in speed_rows if item.get("median_sec") is not None
    ]
    speed_bottleneck = None
    if speed_candidates:
        speed_bottleneck = max(
            speed_candidates,
            key=lambda item: float(item.get("median_sec") or 0),
        )

    conversion_bottleneck = None
    for idx in range(1, len(steps)):
        prev_total = steps[idx - 1]["count"] or 0
        if prev_total < 5:
            continue
        conversion = steps[idx].get("conversion_from_prev")
        if conversion is None:
            continue
        if conversion_bottleneck is None or conversion < conversion_bottleneck["conversion"]:
            conversion_bottleneck = {
                "key": steps[idx]["key"],
                "title": steps[idx]["title"],
                "conversion": conversion,
                "dropoff": steps[idx].get("dropoff_count", 0),
            }

    conversion_total = 0.0
    if summary_cards:
        entered_count = summary_cards[0]["count"]
        last_count = summary_cards[-1]["count"]
        conversion_total = (
            round((last_count / entered_count) * 100, 1)
            if entered_count
            else 0.0
        )

    return {
        "range": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "ttl_hours": ttl_hours,
        },
        "steps": steps,
        "dropoffs": {
            "no_test1": no_test1,
            "test1_timeout": test1_timeout,
            "test1_completed": len(completed_subjects),
        },
        "series": {
            "labels": series_labels,
            "entered": series_entered,
            "test1_completed": series_completed,
        },
        "summary": {
            "cards": summary_cards,
            "conversion_total": conversion_total,
            "range_days": range_days,
        },
        "speed": {
            "transitions": speed_rows,
            "bottlenecks": {
                "speed": speed_bottleneck,
                "conversion": conversion_bottleneck,
            },
        },
        "last_period_comparison": None,
    }


async def get_pipeline_snapshot(
    *,
    city: Optional[str] = None,
    recruiter_id: Optional[int] = None,
    source: Optional[str] = None,
) -> Dict[str, object]:
    city = _clean_filter_value(city)
    source = _clean_filter_value(source)
    stage_definitions: List[Tuple[str, List[CandidateStatus]]] = []
    for name, statuses in get_funnel_stages():
        if name == "Тестирование":
            statuses = statuses + [
                CandidateStatus.WAITING_SLOT,
                CandidateStatus.STALLED_WAITING_SLOT,
            ]
        stage_definitions.append((name, statuses))

    stage_index: Dict[CandidateStatus, int] = {}
    for idx, (_, statuses) in enumerate(stage_definitions):
        for status in statuses:
            stage_index[status] = idx

    counts = [0 for _ in stage_definitions]
    ages: List[List[float]] = [[] for _ in stage_definitions]
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        stmt = (
            select(
                User.candidate_status,
                User.status_changed_at,
                User.last_activity,
            )
            .where(User.is_active == True)
        )
        stmt = _apply_funnel_filters(
            stmt,
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
        rows = await session.execute(stmt)

    for status, status_changed_at, last_activity in rows:
        if status is None:
            continue
        idx = stage_index.get(status)
        if idx is None:
            continue
        counts[idx] += 1
        reference = status_changed_at or last_activity
        if not reference:
            continue
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        age_hours = (now - reference).total_seconds() / 3600
        if age_hours >= 0:
            ages[idx].append(age_hours)

    stages_payload: List[Dict[str, object]] = []
    total = sum(counts)
    for idx, (stage_name, _) in enumerate(stage_definitions):
        median = _percentile(ages[idx], 0.5)
        p75 = _percentile(ages[idx], 0.75)
        stages_payload.append(
            {
                "stage": stage_name,
                "count": counts[idx],
                "median_age_hours": round(median, 1) if median is not None else None,
                "p75_age_hours": round(p75, 1) if p75 is not None else None,
            }
        )

    return {
        "total": total,
        "stages": stages_payload,
    }


async def get_funnel_step_candidates(
    *,
    step_key: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    city: Optional[str] = None,
    recruiter_id: Optional[int] = None,
    source: Optional[str] = None,
    ttl_hours: int = FUNNEL_DROP_TTL_HOURS,
    limit: int = 200,
) -> List[Dict[str, object]]:
    date_from, date_to = _normalize_funnel_range(date_from, date_to)
    city = _clean_filter_value(city)
    source = _clean_filter_value(source)
    window_end = date_to + timedelta(hours=ttl_hours)

    step_def = next(
        (step for step in FUNNEL_STEP_DEFS if step["key"] == step_key),
        None,
    )
    async with async_session() as session:
        if step_def:
            ae = ANALYTICS_EVENTS
            stmt = (
                select(
                    User.id,
                    User.fio,
                    User.username,
                    User.telegram_id,
                    User.telegram_username,
                    User.city,
                    User.responsible_recruiter_id,
                    User.candidate_status,
                    User.last_activity,
                    Recruiter.name.label("recruiter_name"),
                    func.max(ae.c.created_at).label("event_at"),
                )
                .select_from(ae)
                .join(User, User.id == ae.c.candidate_id)
                .outerjoin(Recruiter, Recruiter.id == User.responsible_recruiter_id)
                .where(
                    ae.c.event_name.in_(step_def["events"]),
                    ae.c.created_at >= date_from,
                    ae.c.created_at <= date_to,
                )
                .group_by(
                    User.id,
                    User.fio,
                    User.username,
                    User.telegram_id,
                    User.telegram_username,
                    User.city,
                    User.responsible_recruiter_id,
                    User.candidate_status,
                    User.last_activity,
                    Recruiter.name,
                )
                .order_by(func.max(ae.c.created_at).desc())
                .limit(limit)
            )
            stmt = _apply_funnel_filters(
                stmt,
                city=city,
                recruiter_id=recruiter_id,
                source=source,
            )
            result = await session.execute(stmt)
            rows = result.all()
            payload: List[Dict[str, object]] = []
            for row in rows:
                payload.append(
                    {
                        "id": row.id,
                        "name": row.fio,
                        "username": row.telegram_username or row.username,
                        "telegram_id": row.telegram_id,
                        "city": row.city,
                        "recruiter": row.recruiter_name,
                        "status": row.candidate_status.value if row.candidate_status else None,
                        "status_label": get_status_label(row.candidate_status)
                        if row.candidate_status
                        else None,
                        "last_activity": row.last_activity.isoformat()
                        if row.last_activity
                        else None,
                        "event_at": row.event_at.isoformat() if row.event_at else None,
                        "candidate_url": f"/candidates/{row.id}",
                    }
                )
            return payload

        target = step_key.strip().lower()
        if target not in {"no_test1", "test1_timeout"}:
            return []

        rows = await _fetch_funnel_events(
            session,
            event_names=[
                FunnelEvent.BOT_ENTERED.value,
                FunnelEvent.TEST1_STARTED.value,
                FunnelEvent.TEST1_COMPLETED.value,
            ],
            date_from=date_from,
            date_to=window_end,
            city=city,
            recruiter_id=recruiter_id,
            source=source,
        )
        events_by_candidate: Dict[int, Dict[str, List[datetime]]] = {}
        for candidate_id, user_id, event_name, created_at in rows:
            if candidate_id is None:
                continue
            bucket = events_by_candidate.setdefault(candidate_id, {})
            bucket.setdefault(event_name, []).append(created_at)
        for bucket in events_by_candidate.values():
            for timestamps in bucket.values():
                timestamps.sort()

        now = datetime.now(timezone.utc)
        candidate_ids: List[int] = []
        extra_by_candidate: Dict[int, Dict[str, object]] = {}
        ttl = timedelta(hours=ttl_hours)
        for candidate_id, events in events_by_candidate.items():
            entered_times = [
                ts
                for ts in events.get(FunnelEvent.BOT_ENTERED.value, [])
                if date_from <= ts <= date_to
            ]
            started_times = [
                ts
                for ts in events.get(FunnelEvent.TEST1_STARTED.value, [])
                if date_from <= ts <= date_to
            ]
            if target == "no_test1":
                if entered_times and not started_times:
                    last_ts = max(entered_times)
                    candidate_ids.append(candidate_id)
                    extra_by_candidate[candidate_id] = {
                        "last_step": FunnelEvent.BOT_ENTERED.value,
                        "elapsed_hours": int(
                            (now - last_ts).total_seconds() // 3600
                        ),
                    }
            else:
                if not started_times:
                    continue
                start_ts = min(started_times)
                completion_times = events.get(FunnelEvent.TEST1_COMPLETED.value, [])
                completed_on_time = any(
                    start_ts <= ts <= start_ts + ttl for ts in completion_times
                )
                if not completed_on_time:
                    candidate_ids.append(candidate_id)
                    extra_by_candidate[candidate_id] = {
                        "last_step": FunnelEvent.TEST1_STARTED.value,
                        "elapsed_hours": int(
                            (now - start_ts).total_seconds() // 3600
                        ),
                    }

        if not candidate_ids:
            return []
        details_stmt = (
            select(
                User.id,
                User.fio,
                User.username,
                User.telegram_id,
                User.telegram_username,
                User.city,
                User.responsible_recruiter_id,
                User.candidate_status,
                User.last_activity,
                Recruiter.name.label("recruiter_name"),
            )
            .select_from(User)
            .outerjoin(Recruiter, Recruiter.id == User.responsible_recruiter_id)
            .where(User.id.in_(candidate_ids))
            .limit(limit)
        )
        result = await session.execute(details_stmt)
        rows = result.all()
        payload = []
        for row in rows:
            extra = extra_by_candidate.get(row.id, {})
            payload.append(
                {
                    "id": row.id,
                    "name": row.fio,
                    "username": row.telegram_username or row.username,
                    "telegram_id": row.telegram_id,
                    "city": row.city,
                    "recruiter": row.recruiter_name,
                    "status": row.candidate_status.value if row.candidate_status else None,
                    "status_label": get_status_label(row.candidate_status)
                    if row.candidate_status
                    else None,
                    "last_activity": row.last_activity.isoformat()
                    if row.last_activity
                    else None,
                    "candidate_url": f"/candidates/{row.id}",
                    "last_step": extra.get("last_step"),
                    "elapsed_hours": extra.get("elapsed_hours"),
                }
            )
        return payload


async def get_recruiter_performance(window_days: int = 30) -> List[Dict[str, object]]:
    """Calculate basic efficiency metrics for recruiters."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    async with async_session() as session:
        status_lower = func.lower(Slot.status)
        stmt = (
            select(
                Recruiter.id,
                Recruiter.name,
                Recruiter.tz,
                func.count(Slot.id).label("total_slots"),
                func.sum(case((status_lower == SlotStatus.FREE, 1), else_=0)).label("free_slots"),
                func.sum(case((status_lower == SlotStatus.PENDING, 1), else_=0)).label("pending_slots"),
                func.sum(
                    case(
                        (status_lower.in_([SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE]), 1),
                        else_=0,
                    )
                ).label("booked_slots"),
                func.sum(
                    case(
                        (
                            and_(
                                status_lower.in_([SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE]),
                                Slot.start_utc >= window_start,
                                Slot.start_utc <= now,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("recent_booked"),
                func.sum(
                    case(
                        (
                            and_(
                                status_lower == SlotStatus.CONFIRMED_BY_CANDIDATE,
                                Slot.start_utc >= window_start,
                                Slot.start_utc <= now,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("recent_confirmed"),
                func.sum(case((Slot.start_utc >= now, 1), else_=0)).label("upcoming"),
                func.min(case((Slot.start_utc >= now, Slot.start_utc), else_=None)).label("next_slot"),
            )
            .select_from(Recruiter)
            .outerjoin(Slot, Slot.recruiter_id == Recruiter.id)
            .where(Recruiter.active.is_(True))
            .group_by(Recruiter.id)
        )
        rows = (await session.execute(stmt)).all()

    performance: List[Dict[str, object]] = []
    for row in rows:
        next_slot = row.next_slot
        if isinstance(next_slot, datetime) and next_slot.tzinfo is None:
            next_slot = next_slot.replace(tzinfo=timezone.utc)
        total_slots = int(row.total_slots or 0)
        booked_slots = int(row.booked_slots or 0)
        free_slots = int(row.free_slots or 0)
        pending_slots = int(row.pending_slots or 0)
        recent_booked = int(row.recent_booked or 0)
        recent_confirmed = int(row.recent_confirmed or 0)
        fill_rate = round((booked_slots / total_slots) * 100, 1) if total_slots else 0.0
        confirmation_rate = round(
            (recent_confirmed / recent_booked) * 100, 1
        ) if recent_booked else 0.0

        performance.append(
            {
                "recruiter_id": row.id,
                "name": row.name,
                "tz": row.tz,
                "total_slots": total_slots,
                "booked_slots": booked_slots,
                "free_slots": free_slots,
                "pending_slots": pending_slots,
                "recent_booked": recent_booked,
                "recent_confirmed": recent_confirmed,
                "fill_rate": fill_rate,
                "confirmation_rate": confirmation_rate,
                "upcoming": int(row.upcoming or 0),
                "next_slot": next_slot,
            }
        )

    performance.sort(key=lambda r: (r["booked_slots"], r["total_slots"]), reverse=True)
    return performance


def _normalize_score(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 1.0 if maximum > 0 else 0.0
    return (value - minimum) / (maximum - minimum)


async def get_recruiter_leaderboard(
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    city: Optional[str] = None,
    window_days: int = 30,
) -> Dict[str, object]:
    """Build recruiter leaderboard with efficiency metrics for admin dashboard."""
    date_from, date_to = _normalize_funnel_range(
        date_from, date_to, default_days=window_days
    )
    city = _clean_filter_value(city)
    cache_key = f"dashboard:leaderboard:{date_from.date()}:{date_to.date()}:{city or 'all'}"

    try:
        cache = get_cache()
        cached = await cache.get(cache_key)
        if cached.is_success():
            cached_value = cached.unwrap()
            if cached_value is not None:
                return cached_value
    except Exception:
        cache = None

    interview_statuses = {
        CandidateStatus.INTERVIEW_SCHEDULED,
        CandidateStatus.INTERVIEW_CONFIRMED,
    }
    intro_statuses = {
        CandidateStatus.INTRO_DAY_SCHEDULED,
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
    }
    declined_statuses = {
        CandidateStatus.INTERVIEW_DECLINED,
        CandidateStatus.TEST2_FAILED,
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
        CandidateStatus.NOT_HIRED,
    }

    activity_ref = func.coalesce(User.status_changed_at, User.last_activity)

    async with async_session() as session:
        recruiter_rows = (
            await session.execute(
                select(Recruiter.id, Recruiter.name, Recruiter.tz)
                .where(Recruiter.active.is_(True))
                .order_by(Recruiter.name.asc())
            )
        ).all()
        recruiters = {
            row.id: {"recruiter_id": row.id, "name": row.name, "tz": row.tz}
            for row in recruiter_rows
        }

        candidate_stmt = (
            select(
                User.responsible_recruiter_id.label("recruiter_id"),
                func.count(User.id).label("candidates_total"),
                func.sum(
                    case(
                        (User.candidate_status.in_(interview_statuses), 1),
                        else_=0,
                    )
                ).label("interview_total"),
                func.sum(
                    case(
                        (User.candidate_status.in_(intro_statuses), 1),
                        else_=0,
                    )
                ).label("intro_total"),
                func.sum(
                    case(
                        (User.candidate_status == CandidateStatus.HIRED, 1),
                        else_=0,
                    )
                ).label("hired_total"),
                func.sum(
                    case(
                        (User.candidate_status.in_(declined_statuses), 1),
                        else_=0,
                    )
                ).label("declined_total"),
            )
            .where(
                User.responsible_recruiter_id.isnot(None),
                activity_ref >= date_from,
                activity_ref <= date_to,
            )
        )
        if city:
            candidate_stmt = candidate_stmt.where(func.lower(User.city) == city.lower())
        candidate_stmt = candidate_stmt.group_by(User.responsible_recruiter_id)
        candidate_rows = (await session.execute(candidate_stmt)).all()

        status_lower = func.lower(Slot.status)
        booked_statuses = [
            SlotStatus.BOOKED,
            SlotStatus.CONFIRMED,
            SlotStatus.CONFIRMED_BY_CANDIDATE,
        ]
        slot_stmt = (
            select(
                Slot.recruiter_id.label("recruiter_id"),
                func.count(Slot.id).label("slots_total"),
                func.sum(case((status_lower == SlotStatus.FREE, 1), else_=0)).label("slots_free"),
                func.sum(case((status_lower == SlotStatus.PENDING, 1), else_=0)).label("slots_pending"),
                func.sum(
                    case((status_lower.in_(booked_statuses), 1), else_=0)
                ).label("slots_booked"),
                func.sum(
                    case(
                        (status_lower == SlotStatus.CONFIRMED_BY_CANDIDATE, 1),
                        else_=0,
                    )
                ).label("slots_confirmed"),
                func.sum(
                    case(
                        (
                            and_(
                                Slot.start_utc >= date_from,
                                Slot.start_utc <= date_to,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("slots_window_total"),
                func.sum(
                    case(
                        (
                            and_(
                                Slot.start_utc >= date_from,
                                Slot.start_utc <= date_to,
                                status_lower.in_(booked_statuses),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("slots_window_booked"),
                func.sum(
                    case(
                        (
                            and_(
                                Slot.start_utc >= date_from,
                                Slot.start_utc <= date_to,
                                status_lower == SlotStatus.CONFIRMED_BY_CANDIDATE,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("slots_window_confirmed"),
            )
            .where(Slot.recruiter_id.isnot(None))
            .group_by(Slot.recruiter_id)
        )
        slot_rows = (await session.execute(slot_stmt)).all()

    candidate_by_rec: Dict[int, dict] = {row.recruiter_id: row for row in candidate_rows}
    slots_by_rec: Dict[int, dict] = {row.recruiter_id: row for row in slot_rows}

    items: List[Dict[str, object]] = []
    for recruiter_id, base in recruiters.items():
        cand = candidate_by_rec.get(recruiter_id)
        slot = slots_by_rec.get(recruiter_id)

        candidates_total = int(getattr(cand, "candidates_total", 0) or 0)
        interview_total = int(getattr(cand, "interview_total", 0) or 0)
        intro_total = int(getattr(cand, "intro_total", 0) or 0)
        hired_total = int(getattr(cand, "hired_total", 0) or 0)
        declined_total = int(getattr(cand, "declined_total", 0) or 0)
        progressed_total = interview_total + intro_total + hired_total
        conversion_interview = (
            round((progressed_total / candidates_total) * 100, 1)
            if candidates_total
            else 0.0
        )

        slots_total = int(getattr(slot, "slots_window_total", 0) or 0)
        if slots_total == 0:
            slots_total = int(getattr(slot, "slots_total", 0) or 0)
        slots_booked = int(getattr(slot, "slots_window_booked", 0) or 0)
        if slots_booked == 0:
            slots_booked = int(getattr(slot, "slots_booked", 0) or 0)
        slots_confirmed = int(getattr(slot, "slots_window_confirmed", 0) or 0)
        if slots_confirmed == 0:
            slots_confirmed = int(getattr(slot, "slots_confirmed", 0) or 0)

        fill_rate = round((slots_booked / slots_total) * 100, 1) if slots_total else 0.0
        confirmation_rate = (
            round((slots_confirmed / slots_booked) * 100, 1) if slots_booked else 0.0
        )

        items.append(
            {
                "recruiter_id": recruiter_id,
                "name": base["name"],
                "tz": base["tz"],
                "candidates_total": candidates_total,
                "interview_total": interview_total,
                "intro_total": intro_total,
                "hired_total": hired_total,
                "declined_total": declined_total,
                "conversion_interview": conversion_interview,
                "slots_total": slots_total,
                "slots_booked": slots_booked,
                "slots_confirmed": slots_confirmed,
                "fill_rate": fill_rate,
                "confirmation_rate": confirmation_rate,
                "throughput": candidates_total,
            }
        )

    max_throughput = max((row["throughput"] for row in items), default=0)
    max_fill = max((row["fill_rate"] for row in items), default=0.0)
    max_confirm = max((row["confirmation_rate"] for row in items), default=0.0)
    max_conversion = max((row["conversion_interview"] for row in items), default=0.0)

    for row in items:
        throughput_norm = (
            row["throughput"] / max_throughput if max_throughput else 0.0
        )
        fill_norm = _normalize_score(row["fill_rate"], 0.0, max_fill)
        confirm_norm = _normalize_score(row["confirmation_rate"], 0.0, max_confirm)
        conversion_norm = _normalize_score(
            row["conversion_interview"], 0.0, max_conversion
        )
        score = (
            0.35 * conversion_norm
            + 0.25 * confirm_norm
            + 0.20 * fill_norm
            + 0.20 * throughput_norm
        )
        row["score"] = round(score * 100, 1)

    items.sort(key=lambda row: row["score"], reverse=True)
    for idx, row in enumerate(items, start=1):
        row["rank"] = idx

    payload = {
        "window": {
            "from": date_from.date().isoformat(),
            "to": date_to.date().isoformat(),
            "days": (date_to.date() - date_from.date()).days + 1,
        },
        "items": items,
    }

    if cache:
        try:
            await cache.set(cache_key, payload, ttl=CacheTTL.SHORT)
        except Exception:
            pass

    return payload


async def get_recent_activities(limit: int = 10) -> List[Dict[str, object]]:
    """Get recent activity events for Activity Feed."""
    async with async_session() as session:
        # Get recent candidates ordered by last activity
        stmt = (
            select(User)
            .where(User.is_active == True)
            .order_by(User.last_activity.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

        activities = []
        for user in users:
            # Determine activity type based on status
            activity_type = "update"
            icon = "📝"

            if user.candidate_status:
                status_str = user.candidate_status.value

                if "hired" in status_str:
                    activity_type = "success"
                    icon = "✅"
                elif "declined" in status_str or "failed" in status_str:
                    activity_type = "declined"
                    icon = "❌"
                elif "interview" in status_str:
                    activity_type = "interview"
                    icon = "🎤"
                elif "intro_day" in status_str:
                    activity_type = "intro"
                    icon = "👋"
                elif "test" in status_str:
                    activity_type = "test"
                    icon = "📋"

            # Calculate time ago
            time_ago = "недавно"
            if user.last_activity:
                delta = datetime.now(timezone.utc) - user.last_activity.replace(tzinfo=timezone.utc)
                if delta.days > 0:
                    time_ago = f"{delta.days}д назад"
                elif delta.seconds >= 3600:
                    hours = delta.seconds // 3600
                    time_ago = f"{hours}ч назад"
                elif delta.seconds >= 60:
                    minutes = delta.seconds // 60
                    time_ago = f"{minutes}м назад"
                else:
                    time_ago = "только что"

            activities.append({
                "type": activity_type,
                "icon": icon,
                "title": user.fio,
                "description": get_status_label(user.candidate_status),
                "time": time_ago,
                "timestamp": user.last_activity,
            })

        return activities


async def get_ai_insights() -> Dict[str, object]:
    """Get AI-powered insights and recommendations."""
    async with async_session() as session:
        # Get overall stats
        total_candidates = await session.scalar(
            select(func.count()).select_from(User).where(User.is_active == True)
        )

        # Get stalled candidates (waiting slot > 24h)
        stalled_count = await session.scalar(
            select(func.count()).select_from(User).where(
                and_(
                    User.is_active == True,
                    User.candidate_status == CandidateStatus.STALLED_WAITING_SLOT
                )
            )
        )

        # Get hired count
        hired_count = await session.scalar(
            select(func.count()).select_from(User).where(
                and_(
                    User.is_active == True,
                    User.candidate_status == CandidateStatus.HIRED
                )
            )
        )

        # Get declined count
        declined_statuses = [
            CandidateStatus.INTERVIEW_DECLINED,
            CandidateStatus.TEST2_FAILED,
            CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
            CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
            CandidateStatus.NOT_HIRED,
        ]
        declined_count = await session.scalar(
            select(func.count()).select_from(User).where(
                and_(
                    User.is_active == True,
                    User.candidate_status.in_(declined_statuses)
                )
            )
        )

        # Calculate conversion rate
        conversion_rate = 0
        if total_candidates and total_candidates > 0:
            conversion_rate = round((hired_count / total_candidates) * 100, 1)

        # Generate insight based on data
        insight = ""
        recommendation = ""
        priority = "info"

        if stalled_count and stalled_count > 0:
            insight = f"У вас {stalled_count} кандидат(ов) ждут назначения слота более 24 часов"
            recommendation = "Рекомендуется связаться с рекрутёрами для ускорения процесса"
            priority = "warning"
        elif conversion_rate < 20:
            insight = f"Конверсия в найм составляет {conversion_rate}% — ниже среднего"
            recommendation = "Проанализируйте этапы воронки с наибольшим отсевом"
            priority = "info"
        elif conversion_rate >= 50:
            insight = f"Отличная конверсия в найм: {conversion_rate}%!"
            recommendation = "Продолжайте в том же духе — процесс найма эффективен"
            priority = "success"
        else:
            insight = f"Текущая конверсия в найм: {conversion_rate}%"
            recommendation = "Следите за метриками воронки для выявления узких мест"
            priority = "info"

        return {
            "insight": insight,
            "recommendation": recommendation,
            "priority": priority,
            "metrics": {
                "total_candidates": total_candidates or 0,
                "stalled_count": stalled_count or 0,
                "hired_count": hired_count or 0,
                "declined_count": declined_count or 0,
                "conversion_rate": conversion_rate,
            },
        }


_STAGE_TO_STATUS: Dict[str, Optional[CandidateStatus]] = {
    "new": CandidateStatus.LEAD,
    "screening": CandidateStatus.CONTACTED,
    "interview": CandidateStatus.INTERVIEW_SCHEDULED,
}


async def smart_create_candidate(
    *,
    name: str,
    position: Optional[str],
    stage: str,
    slot_id: Optional[int],
    resume_filename: Optional[str],
) -> Tuple[User, Optional[int]]:
    """Create candidate via modal and optionally book slot."""
    normalized_stage = (stage or "new").strip().lower()
    target_status = _STAGE_TO_STATUS.get(normalized_stage)
    require_slot = normalized_stage == "interview"

    cleaned_name = name.strip()
    if not cleaned_name:
        raise SmartCreateError("Введите имя кандидата.")

    cleaned_position = position.strip() if position else None

    async with async_session() as session:
        async with session.begin():
            now = datetime.now(timezone.utc)
            user = User(
                fio=cleaned_name,
                city=None,
                desired_position=cleaned_position,
                resume_filename=resume_filename,
                is_active=True,
                last_activity=now,
                source="manual_call",
            )
            session.add(user)
            await session.flush()
            if target_status:
                await _candidate_status_service.force(
                    user,
                    target_status,
                    reason="smart create candidate",
                )
                user.status_changed_at = now

            booked_slot_id: Optional[int] = None
            if slot_id is not None:
                slot = await session.scalar(
                    select(Slot)
                    .where(Slot.id == slot_id)
                    .with_for_update()
                )
                if slot is None:
                    raise SmartCreateError("Выбранный слот уже недоступен.")
                if (slot.status or "").lower() != SlotStatus.FREE:
                    raise SmartCreateError("Слот уже забронирован.")

                slot.status = SlotStatus.BOOKED
                slot.candidate_id = user.candidate_id
                slot.candidate_tg_id = user.telegram_id
                slot.candidate_fio = user.fio
                slot.candidate_tz = slot.tz_name
                slot.candidate_city_id = slot.city_id
                booked_slot_id = slot.id
            elif require_slot:
                raise SmartCreateError("Для статуса «Интервью» выберите свободный слот.")

        await session.refresh(user)

    return user, booked_slot_id
