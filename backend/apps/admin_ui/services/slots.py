from __future__ import annotations

import logging
from datetime import date as date_type, datetime, time as time_type, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.utils import paginate, recruiter_time_to_utc, norm_status, status_to_db
from backend.core.db import async_session
from backend.domain.models import Recruiter, Slot, SlotStatus, City

try:  # Bot services are optional in some environments (e.g. unit tests without bot)
    from backend.apps.bot.config import DEFAULT_TZ, TEST1_QUESTIONS, State as BotState
    from backend.apps.bot.services import get_state_manager, start_test2

    _BOT_AVAILABLE = True
except Exception:  # pragma: no cover - bot may be unavailable during certain tests
    DEFAULT_TZ = "Europe/Moscow"
    TEST1_QUESTIONS = []
    BotState = dict  # type: ignore[assignment]
    _BOT_AVAILABLE = False

__all__ = [
    "list_slots",
    "recruiters_for_slot_form",
    "create_slot",
    "bulk_create_slots",
    "api_slots_payload",
    "delete_slot",
    "set_slot_outcome",
]


logger = logging.getLogger(__name__)


async def list_slots(
    recruiter_id: Optional[int],
    status: Optional[str],
    page: int,
    per_page: int,
) -> Dict[str, object]:
    async with async_session() as session:
        base = select(Slot)
        if recruiter_id is not None:
            base = base.where(Slot.recruiter_id == recruiter_id)
        if status:
            base = base.where(Slot.status == status_to_db(status))

        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        pages_total, page, offset = paginate(total, page, per_page)

        query = (
            base.options(selectinload(Slot.recruiter))
            .order_by(Slot.start_utc.desc())
            .offset(offset)
            .limit(per_page)
        )
        items = (await session.scalars(query)).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages_total": pages_total,
    }


async def recruiters_for_slot_form() -> List[Dict[str, object]]:
    inspector = sa_inspect(Recruiter)
    has_active = "active" in getattr(inspector, "columns", {})
    query = select(Recruiter).order_by(Recruiter.name.asc())
    if has_active:
        query = query.where(getattr(Recruiter, "active") == True)  # noqa: E712
    async with async_session() as session:
        recs = (await session.scalars(query)).all()
        if not recs:
            return []

        rec_ids = [rec.id for rec in recs]
        city_rows = (
            await session.scalars(
                select(City)
                .where(City.responsible_recruiter_id.in_(rec_ids))
                .order_by(City.name.asc())
            )
        ).all()

        city_map: Dict[int, List[City]] = {}
        for city in city_rows:
            if city.responsible_recruiter_id is None:
                continue
            city_map.setdefault(city.responsible_recruiter_id, []).append(city)

    return [
        {"rec": rec, "cities": city_map.get(rec.id, [])}
        for rec in recs
    ]


async def create_slot(
    recruiter_id: int,
    date: str,
    time: str,
    *,
    city_id: int,
) -> bool:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return False
        city = await session.get(City, city_id)
        if not city or city.responsible_recruiter_id != recruiter_id:
            return False
        dt_utc = recruiter_time_to_utc(date, time, getattr(recruiter, "tz", None))
        if not dt_utc:
            return False
        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value
        session.add(
            Slot(
                recruiter_id=recruiter_id,
                city_id=city_id,
                start_utc=dt_utc,
                status=status_free,
            )
        )
        await session.commit()
        return True


async def delete_slot(slot_id: int) -> Tuple[bool, Optional[str]]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return False, "Слот не найден"

        status = norm_status(slot.status)
        if status not in {"FREE", "PENDING"}:
            return False, f"Нельзя удалить слот со статусом {status or 'UNKNOWN'}"

        await session.delete(slot)
        await session.commit()
        return True, None


async def set_slot_outcome(slot_id: int, outcome: str) -> Tuple[bool, Optional[str], Optional[str]]:
    normalized = (outcome or "").strip().lower()
    if normalized not in {"passed", "failed"}:
        return False, "Некорректный исход. Выберите «Прошёл» или «Не прошёл».", None

    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return False, "Слот не найден.", None
        if not getattr(slot, "candidate_tg_id", None):
            return False, "Слот не привязан к кандидату, отправить тест нельзя.", None

        slot.interview_outcome = normalized
        await session.commit()

        candidate_id = int(slot.candidate_tg_id)
        candidate_tz = getattr(slot, "candidate_tz", None)
        candidate_city = getattr(slot, "candidate_city_id", None)
        candidate_name = getattr(slot, "candidate_fio", "")

    if normalized == "passed":
        ok, error = await _send_test2(candidate_id, candidate_tz, candidate_city, candidate_name)
        if not ok:
            return False, error or "Не удалось отправить Тест 2 кандидату.", normalized
        message = "Исход «Прошёл» сохранён. Кандидату отправлен Тест 2."
    else:
        message = "Исход «Не прошёл» сохранён."

    return True, message, normalized


async def _send_test2(
    candidate_id: int,
    candidate_tz: Optional[str],
    candidate_city: Optional[int],
    candidate_name: str,
) -> Tuple[bool, Optional[str]]:
    if not _BOT_AVAILABLE:
        logger.warning("Bot services are not configured; cannot send Test 2.")
        return False, "Бот недоступен. Проверьте его конфигурацию."

    try:
        state_manager = get_state_manager()
    except RuntimeError as exc:  # pragma: no cover - depends on runtime configuration
        logger.error("State manager is not configured: %s", exc)
        return False, "Бот недоступен. Проверьте его конфигурацию."

    prev_state = state_manager.get(candidate_id) or {}
    sequence = prev_state.get("t1_sequence")
    if sequence:
        try:
            sequence = list(sequence)
        except TypeError:
            sequence = list(TEST1_QUESTIONS)
    else:
        sequence = list(TEST1_QUESTIONS)

    new_state: BotState = BotState(
        flow="intro",
        t1_idx=None,
        t1_current_idx=None,
        test1_answers=prev_state.get("test1_answers", {}),
        t1_last_prompt_id=None,
        t1_last_question_text="",
        t1_requires_free_text=False,
        t1_sequence=sequence,
        fio=prev_state.get("fio", candidate_name or ""),
        city_name=prev_state.get("city_name", ""),
        city_id=prev_state.get("city_id", candidate_city),
        candidate_tz=candidate_tz or prev_state.get("candidate_tz", DEFAULT_TZ),
        t2_attempts={},
        picked_recruiter_id=None,
        picked_slot_id=None,
    )

    state_manager.set(candidate_id, new_state)

    try:
        await start_test2(candidate_id)
    except Exception as exc:  # pragma: no cover - network errors etc.
        logger.exception("Failed to start Test 2 for candidate %s", candidate_id)
        return False, str(exc)

    return True, None


def _normalize_utc(dt: datetime) -> datetime:
    """Return UTC naive datetime for reliable comparisons across drivers."""
    if dt.tzinfo is None:
        # Assume already UTC naive
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
        if city.responsible_recruiter_id != recruiter_id:
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

        tz = getattr(recruiter, "tz", None)

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
                    dt_utc = recruiter_time_to_utc(current_date.isoformat(), time_str, tz)
                    if not dt_utc:
                        return 0, "Не удалось преобразовать время в UTC"
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

        to_insert = [original for original, norm in planned_pairs if norm not in existing_norms]
        if not to_insert:
            return 0, None

        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        session.add_all(
            [
                Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=dt,
                    status=status_free,
                )
                for dt in to_insert
            ]
        )
        await session.commit()
        return len(to_insert), None


async def api_slots_payload(
    recruiter_id: Optional[int],
    status: Optional[str],
    limit: int,
) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = select(Slot).options(selectinload(Slot.recruiter)).order_by(Slot.start_utc.asc())
        if recruiter_id is not None:
            query = query.where(Slot.recruiter_id == recruiter_id)
        if status:
            query = query.where(Slot.status == status_to_db(status))
        if limit:
            query = query.limit(max(1, min(500, limit)))
        slots = (await session.scalars(query)).all()
    return [
        {
            "id": sl.id,
            "recruiter_id": sl.recruiter_id,
            "recruiter_name": sl.recruiter.name if sl.recruiter else None,
            "start_utc": sl.start_utc.isoformat(),
            "status": norm_status(sl.status),
            "candidate_fio": getattr(sl, "candidate_fio", None),
            "candidate_tg_id": getattr(sl, "candidate_tg_id", None),
        }
        for sl in slots
    ]
