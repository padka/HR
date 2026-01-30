from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from datetime import time as time_type
from typing import List, Optional, Tuple

from sqlalchemy import select

from backend.apps.admin_ui.utils import local_naive_to_utc, validate_timezone_name
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus, recruiter_city_association


def _normalize_utc(dt: datetime) -> datetime:
    """Return UTC naive datetime for reliable comparisons across drivers."""

    if dt.tzinfo is None:
        return dt.replace(tzinfo=None)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _as_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC for database comparisons."""

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def bulk_create_slots(
    recruiter_id: int,
    start_date: str,
    end_date: str,
    start_time: str,
    end_time: str,
    break_start: str,
    break_end: str,
    step_min: int,
    include_weekends: bool,
    use_break: bool,
    *,
    city_id: int,
) -> Tuple[int, Optional[str]]:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return 0, "Рекрутёр не найден"

        city = await session.get(City, city_id)
        if not city:
            return 0, "Город не найден"

        # Check M2M recruiter_cities association (not just responsible_recruiter_id)
        m2m = await session.scalar(
            select(recruiter_city_association.c.city_id).where(
                recruiter_city_association.c.recruiter_id == recruiter_id,
                recruiter_city_association.c.city_id == city_id,
            ).limit(1)
        )
        if m2m is None and city.responsible_recruiter_id != recruiter_id:
            return 0, "Город не привязан к выбранному рекрутёру"

        try:
            start = date_type.fromisoformat(start_date)
            end = date_type.fromisoformat(end_date)
        except ValueError:
            return 0, "Некорректные даты"
        if end < start:
            return 0, "Дата окончания раньше даты начала"

        try:
            window_start = time_type.fromisoformat(start_time)
            window_end = time_type.fromisoformat(end_time)
            pause_start = time_type.fromisoformat(break_start)
            pause_end = time_type.fromisoformat(break_end)
        except ValueError:
            return 0, "Некорректное время"

        if window_end <= window_start:
            return 0, "Время окончания должно быть позже времени начала"
        if step_min <= 0:
            return 0, "Шаг должен быть положительным"

        if use_break and pause_end <= pause_start:
            return 0, "Время окончания перерыва должно быть позже его начала"

        start_minutes = window_start.hour * 60 + window_start.minute
        end_minutes = window_end.hour * 60 + window_end.minute
        break_start_minutes = pause_start.hour * 60 + pause_start.minute
        break_end_minutes = pause_end.hour * 60 + pause_end.minute

        try:
            tz = validate_timezone_name(recruiter.tz or city.tz)
        except ValueError:
            return 0, "Некорректный часовой пояс региона"

        planned_pairs: List[Tuple[datetime, datetime]] = []  # (original, normalized)
        planned_norms = set()
        current_date = start
        while current_date <= end:
            if include_weekends or current_date.weekday() < 5:
                current_minutes = start_minutes
                while current_minutes < end_minutes:
                    if (
                        use_break
                        and break_start_minutes < break_end_minutes
                        and break_start_minutes <= current_minutes < break_end_minutes
                    ):
                        current_minutes += step_min
                        continue

                    hours, minutes = divmod(current_minutes, 60)
                    time_str = f"{hours:02d}:{minutes:02d}"
                    try:
                        dt_local = datetime.fromisoformat(
                            f"{current_date.isoformat()}T{time_str}"
                        )
                    except ValueError:
                        return 0, "Некорректное время"
                    dt_utc = local_naive_to_utc(dt_local, tz)
                    norm_dt = _normalize_utc(dt_utc)
                    if norm_dt not in planned_norms:
                        planned_norms.add(norm_dt)
                        planned_pairs.append((dt_utc, norm_dt))
                    current_minutes += step_min
            current_date += timedelta(days=1)

        if not planned_pairs:
            return 0, "Нет доступных слотов для создания"

        norm_values = [norm for _, norm in planned_pairs]
        range_start = min(norm_values)
        range_end = max(norm_values)

        existing_rows = await session.scalars(
            select(Slot.start_utc)
            .where(Slot.recruiter_id == recruiter_id)
            .where(Slot.start_utc >= _as_utc(range_start))
            .where(Slot.start_utc <= _as_utc(range_end))
        )
        existing_norms = {_normalize_utc(dt) for dt in existing_rows}

        to_insert = [
            original for original, norm in planned_pairs if norm not in existing_norms
        ]
        if not to_insert:
            return 0, None

        session.add_all(
            [
                Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=dt,
                    status=SlotStatus.FREE,
                    duration_min=max(step_min, 1),
                )
                for dt in to_insert
            ]
        )
        await session.commit()
        return len(to_insert), None
