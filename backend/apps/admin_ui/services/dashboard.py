from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_ui.timezones import DEFAULT_TZ
from backend.apps.admin_ui.utils import fmt_local, safe_zone
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.candidates.models import User
from backend.domain.candidates.status import (
    get_status_label,
    get_status_color,
    get_status_category,
    get_funnel_stages,
    StatusCategory,
    CandidateStatus,
)
from backend.apps.bot.metrics import get_test1_metrics_snapshot
from backend.domain.repositories import find_city_by_plain_name

__all__ = [
    "dashboard_counts",
    "get_recent_candidates",
    "get_upcoming_interviews",
    "get_hiring_funnel_stats",
    "get_recent_activities",
    "get_ai_insights",
    "get_quick_slots",
    "get_waiting_candidates",
    "smart_create_candidate",
    "format_dashboard_candidate",
    "SmartCreateError",
]

STATUS_COLOR_TO_CLASS = {
    "success": "new",
    "info": "review",
    "primary": "interview",
    "warning": "pending",
    "danger": "declined",
    "secondary": "pending",
}


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


def _format_waiting_window(user: User, tz_label: str) -> Optional[str]:
    if not user.manual_slot_from or not user.manual_slot_to:
        return None
    start = user.manual_slot_from
    end = user.manual_slot_to
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


async def dashboard_counts() -> Dict[str, object]:
    async with async_session() as session:
        rec_count = await session.scalar(
            select(func.count(Recruiter.id)).where(Recruiter.active.is_(True))
        )
        city_count = await session.scalar(
            select(func.count(City.id)).where(City.active.is_(True))
        )
        rows = (
            await session.execute(
                select(Slot.status, func.count(Slot.id))
                .where(Slot.status != SlotStatus.CANCELED)
                .group_by(Slot.status)
            )
        ).all()
        waiting_total = await session.scalar(
            select(func.count()).select_from(User).where(
                User.candidate_status.in_([
                    CandidateStatus.WAITING_SLOT,
                    CandidateStatus.STALLED_WAITING_SLOT,
                ])
            )
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


async def get_recent_candidates(limit: int = 5) -> List[Dict[str, object]]:
    """Get recent candidates/applications for dashboard."""
    async with async_session() as session:
        stmt = (
            select(User)
            .where(User.is_active == True)
            .order_by(User.last_activity.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

        return [format_dashboard_candidate(user) for user in users]


async def get_waiting_candidates(limit: int = 6) -> List[Dict[str, object]]:
    """Return candidates waiting for manual slot assignment."""
    async with async_session() as session:
        status_filter = User.candidate_status.in_([
            CandidateStatus.WAITING_SLOT,
            CandidateStatus.STALLED_WAITING_SLOT,
        ])
        stmt = (
            select(User)
            .where(status_filter)
            .order_by(User.status_changed_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

    now = datetime.now(timezone.utc)
    tz_cache: Dict[str, str] = {}

    async def _resolve_tz(city_label: Optional[str]) -> str:
        key = (city_label or "").strip().lower()
        if not key:
            return DEFAULT_TZ
        if key in tz_cache:
            return tz_cache[key]
        record = await find_city_by_plain_name(city_label)
        tz_value = getattr(record, "tz", None) or DEFAULT_TZ
        tz_cache[key] = tz_value
        return tz_value

    waiting_rows: List[Dict[str, object]] = []
    for user in users:
        tz_label = await _resolve_tz(user.city)
        waiting_since = user.status_changed_at or user.manual_slot_requested_at
        waiting_hours = None
        normalized_waiting_since = waiting_since
        if normalized_waiting_since and normalized_waiting_since.tzinfo is None:
            normalized_waiting_since = normalized_waiting_since.replace(tzinfo=timezone.utc)
        if normalized_waiting_since:
            delta = now - normalized_waiting_since
            waiting_hours = max(0, int(delta.total_seconds() // 3600))

        waiting_rows.append(
            {
                "id": user.id,
                "name": user.fio,
                "city": user.city or "Не указан",
                "status_display": get_status_label(user.candidate_status),
                "status_color": get_status_color(user.candidate_status),
                "status_slug": user.candidate_status.value if user.candidate_status else None,
                "waiting_since": waiting_since,
                "waiting_hours": waiting_hours,
                "availability_window": _format_waiting_window(user, tz_label),
                "availability_note": user.manual_slot_comment,
                "tz": tz_label,
                "telegram_id": user.telegram_id,
                "telegram_user_id": user.telegram_user_id or user.telegram_id,
                "telegram_username": user.telegram_username or user.username,
                "schedule_url": f"/candidates/{user.id}/schedule-slot",
            }
        )

    return waiting_rows


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


async def get_upcoming_interviews(limit: int = 5) -> List[Dict[str, object]]:
    """Get upcoming interviews (booked slots) for dashboard."""
    now = datetime.now(timezone.utc)
    tomorrow_end = now + timedelta(days=2)  # Get today and tomorrow

    async with async_session() as session:
        stmt = (
            select(Slot, Recruiter, City, User)
            .join(Recruiter, Slot.recruiter_id == Recruiter.id)
            .outerjoin(City, Slot.city_id == City.id)
            .outerjoin(User, User.telegram_id == Slot.candidate_tg_id)
            .where(
                and_(
                    or_(
                        Slot.status == SlotStatus.BOOKED,
                        Slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE
                    ),
                    Slot.start_utc >= now,
                    Slot.start_utc <= tomorrow_end
                )
            )
            .order_by(Slot.start_utc.asc())
            .limit(limit)
        )
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
            position_label = slot.purpose.title() if slot.purpose else "Interview"
            slot_status = SLOT_STATUS_LABELS.get(slot.status, "В графике")

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


async def get_hiring_funnel_stats() -> List[Dict[str, object]]:
    """Get hiring funnel statistics for dashboard visualization."""
    funnel_stages = get_funnel_stages()

    async with async_session() as session:
        # Count candidates by status
        stmt = select(User.candidate_status, func.count()).where(
            User.is_active == True
        ).group_by(User.candidate_status)
        result = await session.execute(stmt)
        status_counts = dict(result.all())

    funnel_data = []
    for stage_name, statuses in funnel_stages:
        # Calculate total for this stage
        stage_total = sum(status_counts.get(status, 0) for status in statuses)

        # Calculate sub-statuses breakdown
        sub_statuses = []
        for status in statuses:
            count = status_counts.get(status, 0)
            if count > 0:  # Only include non-zero statuses
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

    # Calculate conversion rates
    for i in range(len(funnel_data) - 1):
        current = funnel_data[i]["total"]
        next_stage = funnel_data[i + 1]["total"]
        if current > 0:
            funnel_data[i]["conversion"] = round((next_stage / current) * 100, 1)
        else:
            funnel_data[i]["conversion"] = 0

    return funnel_data


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
    "new": CandidateStatus.TEST1_COMPLETED,
    "screening": CandidateStatus.WAITING_SLOT,
    "interview": CandidateStatus.INTERVIEW_SCHEDULED,
}


async def _generate_virtual_telegram_id(session: AsyncSession) -> int:
    """Create negative telegram_id for manually added candidates."""
    for _ in range(10):
        synthetic_id = -int(time.time() * 1_000_000) - random.randint(1, 10_000)
        exists = await session.scalar(
            select(func.count()).where(User.telegram_id == synthetic_id)
        )
        if not exists:
            return synthetic_id
    raise SmartCreateError("Не удалось выпустить ID кандидата, повторите попытку.")


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
            telegram_id = await _generate_virtual_telegram_id(session)
            now = datetime.now(timezone.utc)
            user = User(
                telegram_id=telegram_id,
                fio=cleaned_name,
                city=None,
                desired_position=cleaned_position,
                resume_filename=resume_filename,
                candidate_status=target_status,
                is_active=True,
                last_activity=now,
            )
            session.add(user)
            await session.flush()

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
                slot.candidate_tg_id = user.telegram_id
                slot.candidate_fio = user.fio
                slot.candidate_tz = slot.tz_name
                slot.candidate_city_id = slot.city_id
                booked_slot_id = slot.id
            elif require_slot:
                raise SmartCreateError("Для статуса «Интервью» выберите свободный слот.")

        await session.refresh(user)

    return user, booked_slot_id
