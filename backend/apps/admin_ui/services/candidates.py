from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import case, Select

from backend.apps.admin_ui.utils import paginate
from backend.core.db import async_session
from backend.domain.candidates.models import AutoMessage, QuestionAnswer, TestResult, User
from backend.domain.models import Slot, SlotStatus


@dataclass
class CandidateRow:
    user: User
    tests_total: int
    average_score: Optional[float]
    latest_result: Optional[TestResult]
    messages_total: int
    latest_message: Optional[AutoMessage]
    stage: str
    latest_slot: Optional[Slot]
    upcoming_slot: Optional[Slot]


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _stage_label(latest_slot: Optional[Slot], now: datetime) -> str:
    if not latest_slot:
        return "Без интервью"
    status = (latest_slot.status or "").lower()
    start = _ensure_aware(latest_slot.start_utc) or now
    if status == SlotStatus.PENDING:
        return "Ожидает подтверждения" if start >= now else "Требует реакции"
    if status == SlotStatus.BOOKED:
        return "Интервью назначено" if start >= now else "Интервью завершено"
    if status == SlotStatus.CANCELED:
        return "Отменено"
    if status == SlotStatus.FREE:
        return "Свободный слот"
    return status.upper() or "Без интервью"


async def _distinct_ratings(session) -> List[str]:
    rows = await session.execute(
        select(func.distinct(TestResult.rating)).where(TestResult.rating.isnot(None))
    )
    return [value for value in rows.scalars() if value]


async def _distinct_cities(session) -> List[str]:
    rows = await session.execute(
        select(func.distinct(User.city)).where(User.city.isnot(None)).order_by(User.city.asc())
    )
    return [value for value in rows.scalars() if value]


async def list_candidates(
    *,
    page: int,
    per_page: int,
    search: Optional[str],
    city: Optional[str],
    is_active: Optional[bool],
    rating: Optional[str],
    has_tests: Optional[bool],
    has_messages: Optional[bool],
    stage: Optional[str] = None,
) -> Dict[str, object]:
    async with async_session() as session:
        conditions = []
        now = datetime.now(timezone.utc)

        if search:
            like_value = f"%{search.strip()}%"
            clauses = [
                User.fio.ilike(like_value),
                User.city.ilike(like_value),
                cast(User.telegram_id, String).ilike(like_value),
            ]
            try:
                search_id = int(search)
            except (ValueError, TypeError):
                search_id = None
            if search_id is not None:
                clauses.append(User.telegram_id == search_id)
            conditions.append(or_(*clauses))

        if city:
            conditions.append(User.city.ilike(f"%{city.strip()}%"))

        if is_active is True:
            conditions.append(User.is_active.is_(True))
        elif is_active is False:
            conditions.append(User.is_active.is_(False))

        if rating:
            latest_rating = (
                select(TestResult.rating)
                .where(TestResult.user_id == User.id)
                .order_by(TestResult.created_at.desc(), TestResult.id.desc())
                .limit(1)
                .scalar_subquery()
            )
            conditions.append(latest_rating == rating)

        if has_tests is True:
            conditions.append(
                exists(
                    select(1)
                    .where(TestResult.user_id == User.id)
                    .correlate(User)
                )
            )
        elif has_tests is False:
            conditions.append(
                ~exists(
                    select(1)
                    .where(TestResult.user_id == User.id)
                    .correlate(User)
                )
            )

        if has_messages is True:
            conditions.append(
                exists(
                    select(1)
                    .where(AutoMessage.target_chat_id == User.telegram_id)
                    .correlate(User)
                )
            )
        elif has_messages is False:
            conditions.append(
                ~exists(
                    select(1)
                    .where(AutoMessage.target_chat_id == User.telegram_id)
                    .correlate(User)
                )
            )

        stage_value = (stage or "").strip().lower() or None
        if stage_value == "interviews":
            conditions.append(
                exists(
                    select(1)
                    .where(
                        Slot.candidate_tg_id == User.telegram_id,
                        func.lower(Slot.status).in_([SlotStatus.PENDING, SlotStatus.BOOKED]),
                        Slot.start_utc >= now,
                    )
                    .correlate(User)
                )
            )
        elif stage_value == "alerts":
            conditions.append(
                or_(
                    ~exists(
                        select(1)
                        .where(TestResult.user_id == User.id)
                        .correlate(User)
                    ),
                    ~exists(
                        select(1)
                        .where(AutoMessage.target_chat_id == User.telegram_id)
                        .correlate(User)
                    ),
                )
            )

        count_query = select(func.count()).select_from(User)
        if conditions:
            count_query = count_query.where(*conditions)
        total = await session.scalar(count_query) or 0

        pages_total, page, offset = paginate(total, page, per_page)

        list_query: Select = (
            select(User)
            .order_by(User.last_activity.desc(), User.id.desc())
            .offset(offset)
            .limit(per_page)
        )
        if conditions:
            list_query = list_query.where(*conditions)

        users = (await session.scalars(list_query)).all()

        user_ids = [user.id for user in users]
        telegram_ids = [user.telegram_id for user in users if user.telegram_id]

        stats_map: Dict[int, Tuple[int, Optional[float]]] = {}
        latest_result_map: Dict[int, TestResult] = {}
        messages_map: Dict[int, List[AutoMessage]] = {}
        latest_slot_map: Dict[int, Slot] = {}
        upcoming_slot_map: Dict[int, Slot] = {}
        stage_map: Dict[int, str] = {}

        if user_ids:
            stats_rows = await session.execute(
                select(
                    TestResult.user_id,
                    func.count(TestResult.id),
                    func.avg(TestResult.final_score),
                )
                .where(TestResult.user_id.in_(user_ids))
                .group_by(TestResult.user_id)
            )
            for user_id, tests_total, avg_score in stats_rows:
                stats_map[user_id] = (
                    int(tests_total or 0),
                    float(avg_score) if avg_score is not None else None,
                )

            ranked_results = await session.execute(
                select(
                    TestResult,
                    func.row_number()
                    .over(
                        partition_by=TestResult.user_id,
                        order_by=(
                            TestResult.created_at.desc(),
                            TestResult.id.desc(),
                        ),
                    )
                    .label("rnk"),
                )
                .where(TestResult.user_id.in_(user_ids))
            )
            for result, rank in ranked_results:
                if rank == 1:
                    latest_result_map[result.user_id] = result

        if telegram_ids:
            message_rows = await session.execute(
                select(AutoMessage)
                .where(AutoMessage.target_chat_id.in_(telegram_ids))
                .order_by(AutoMessage.target_chat_id, AutoMessage.created_at.desc())
            )
            for message in message_rows.scalars():
                if message.target_chat_id is None:
                    continue
                messages_map.setdefault(message.target_chat_id, []).append(message)

            slot_rows = await session.execute(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(Slot.candidate_tg_id.in_(telegram_ids))
            )
            slots_by_candidate: Dict[int, List[Slot]] = defaultdict(list)
            for slot in slot_rows.scalars():
                if slot.candidate_tg_id is None:
                    continue
                slot.start_utc = _ensure_aware(slot.start_utc)
                slots_by_candidate[slot.candidate_tg_id].append(slot)

            for tg_id, slot_list in slots_by_candidate.items():
                slot_list.sort(key=lambda s: s.start_utc or now)
                latest_slot = slot_list[-1]
                upcoming_slot = next((s for s in slot_list if (s.start_utc or now) >= now), None)
                latest_slot_map[tg_id] = latest_slot
                if upcoming_slot:
                    upcoming_slot_map[tg_id] = upcoming_slot
                stage_map[tg_id] = _stage_label(latest_slot, now)

        items: List[CandidateRow] = []
        for user in users:
            tests_total, avg_score = stats_map.get(user.id, (0, None))
            candidate_messages = messages_map.get(user.telegram_id, [])
            latest_slot = latest_slot_map.get(user.telegram_id)
            upcoming_slot = upcoming_slot_map.get(user.telegram_id)
            stage = stage_map.get(user.telegram_id, "Без интервью")
            items.append(
                CandidateRow(
                    user=user,
                    tests_total=tests_total,
                    average_score=avg_score,
                    latest_result=latest_result_map.get(user.id),
                    messages_total=len(candidate_messages),
                    latest_message=candidate_messages[0] if candidate_messages else None,
                    stage=stage,
                    latest_slot=latest_slot,
                    upcoming_slot=upcoming_slot,
                )
            )

        ratings = await _distinct_ratings(session)
        cities = await _distinct_cities(session)
        analytics = await _collect_candidate_analytics(session, now)

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages_total": pages_total,
        "per_page": per_page,
        "ratings": ratings,
        "cities": cities,
        "analytics": analytics,
        "filters": {
            "search": search or "",
            "city": city or "",
            "is_active": is_active,
            "rating": rating or "",
            "has_tests": has_tests,
            "has_messages": has_messages,
            "stage": stage_value,
        },
    }


async def _collect_candidate_analytics(session, now: datetime) -> Dict[str, object]:
    total = await session.scalar(select(func.count()).select_from(User)) or 0
    active = await session.scalar(select(func.count()).where(User.is_active.is_(True))) or 0
    inactive = max(total - active, 0)

    seven_days_ago = now - timedelta(days=7)
    tests_last_week = (
        await session.scalar(
            select(func.count()).where(TestResult.created_at >= seven_days_ago)
        )
    ) or 0
    messages_last_week = (
        await session.scalar(
            select(func.count()).where(AutoMessage.created_at >= seven_days_ago)
        )
    ) or 0

    need_followup = (
        await session.scalar(
            select(func.count())
            .where(
                User.is_active.is_(True),
                ~exists(
                    select(1)
                    .where(AutoMessage.target_chat_id == User.telegram_id)
                    .correlate(User)
                ),
            )
        )
    ) or 0

    no_tests = (
        await session.scalar(
            select(func.count())
            .where(
                ~exists(
                    select(1)
                    .where(TestResult.user_id == User.id)
                    .correlate(User)
                )
            )
        )
    ) or 0

    slot_sub = (
        select(
            Slot.candidate_tg_id.label("candidate_tg_id"),
            Slot.start_utc.label("start_utc"),
            Slot.status.label("status"),
            func.row_number()
            .over(
                partition_by=Slot.candidate_tg_id,
                order_by=(Slot.start_utc.desc(), Slot.id.desc()),
            )
            .label("rnk"),
        )
        .where(Slot.candidate_tg_id.isnot(None))
    ).subquery()

    latest_rows = await session.execute(
        select(
            slot_sub.c.candidate_tg_id,
            slot_sub.c.start_utc,
            slot_sub.c.status,
        )
        .select_from(slot_sub.join(User, User.telegram_id == slot_sub.c.candidate_tg_id))
        .where(slot_sub.c.rnk == 1)
    )

    stage_counts: Dict[str, int] = defaultdict(int)
    upcoming_count = 0
    awaiting_confirmation = 0
    booked_active = 0
    completed_interviews = 0
    canceled_count = 0

    for tg_id, start_utc, status in latest_rows:
        start = _ensure_aware(start_utc) or now
        status_norm = (status or "").lower()
        stage_counts[status_norm] += 1
        if status_norm == SlotStatus.PENDING:
            if start > now:
                upcoming_count += 1
            awaiting_confirmation += 1
        elif status_norm == SlotStatus.BOOKED:
            if start > now:
                upcoming_count += 1
                booked_active += 1
            else:
                completed_interviews += 1
        elif status_norm == SlotStatus.CANCELED:
            canceled_count += 1

    stage_total = sum(stage_counts.values())
    without_slot = max(total - stage_total, 0)

    pipeline_labels = {
        SlotStatus.PENDING: "Ожидает подтверждения",
        SlotStatus.BOOKED: "Интервью назначено",
        SlotStatus.CANCELED: "Отменено",
        SlotStatus.FREE: "Свободные слоты",
    }
    stage_slug_map = {
        SlotStatus.PENDING: "interviews",
        SlotStatus.BOOKED: "interviews",
        SlotStatus.CANCELED: "alerts",
        SlotStatus.FREE: None,
    }

    pipeline: List[Dict[str, object]] = []
    for key, label in pipeline_labels.items():
        pipeline.append({
            "label": label,
            "count": int(stage_counts.get(key, 0)),
            "slug": stage_slug_map.get(key),
        })
    pipeline.append({"label": "Без интервью", "count": without_slot, "slug": "alerts" if without_slot else None})

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "upcoming_interviews": upcoming_count,
        "awaiting_confirmation": awaiting_confirmation,
        "booked_active": booked_active,
        "completed_interviews": completed_interviews,
        "canceled": canceled_count,
        "without_slot": without_slot,
        "tests_week": tests_last_week,
        "messages_week": messages_last_week,
        "need_followup": need_followup,
        "no_tests": no_tests,
        "pipeline": pipeline,
    }


async def candidate_filter_options() -> Dict[str, List[str]]:
    async with async_session() as session:
        cities = await _distinct_cities(session)
        ratings = await _distinct_ratings(session)
    return {"cities": cities, "ratings": ratings}


async def get_candidate_detail(user_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return None

        test_results = (
            await session.execute(
                select(TestResult)
                .where(TestResult.user_id == user_id)
                .order_by(TestResult.created_at.desc(), TestResult.id.desc())
            )
        ).scalars().all()

        test_ids = [result.id for result in test_results]
        answers_map: Dict[int, Dict[str, int]] = {}
        if test_ids:
            answer_rows = await session.execute(
                select(
                    QuestionAnswer.test_result_id,
                    func.count(QuestionAnswer.id),
                    func.sum(case((QuestionAnswer.is_correct.is_(True), 1), else_=0)),
                    func.sum(case((QuestionAnswer.overtime.is_(True), 1), else_=0)),
                )
                .where(QuestionAnswer.test_result_id.in_(test_ids))
                .group_by(QuestionAnswer.test_result_id)
            )
            for test_id, total_q, correct_q, overtime_q in answer_rows:
                answers_map[test_id] = {
                    "questions_total": int(total_q or 0),
                    "questions_correct": int(correct_q or 0),
                    "questions_overtime": int(overtime_q or 0),
                }

        messages = (
            await session.execute(
                select(AutoMessage)
                .where(AutoMessage.target_chat_id == user.telegram_id)
                .order_by(AutoMessage.created_at.desc(), AutoMessage.id.desc())
            )
        ).scalars().all()

        slots = (
            await session.execute(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(Slot.candidate_tg_id == user.telegram_id)
                .order_by(Slot.start_utc.desc(), Slot.id.desc())
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for slot in slots:
            slot.start_utc = _ensure_aware(slot.start_utc)
        upcoming_slot = next((slot for slot in reversed(slots) if slot.start_utc and slot.start_utc >= now), None)
        stage = _stage_label(slots[0] if slots else None, now)

        timeline = []
        for slot in slots:
            timeline.append(
                {
                    "kind": "slot",
                    "dt": slot.start_utc,
                    "status": (slot.status or "").lower(),
                    "recruiter": getattr(slot.recruiter, "name", None),
                    "city": getattr(slot.city, "name", None),
                    "tz": slot.candidate_tz,
                }
            )
        for result in test_results:
            timeline.append(
                {
                    "kind": "test",
                    "dt": _ensure_aware(result.created_at),
                    "score": result.final_score,
                    "rating": result.rating,
                    "tz": None,
                }
            )
        for msg in messages:
            timeline.append(
                {
                    "kind": "message",
                    "dt": _ensure_aware(msg.created_at),
                    "send_time": msg.send_time,
                    "text": msg.message_text,
                    "is_active": msg.is_active,
                    "tz": None,
                }
            )
        timeline.sort(key=lambda item: item["dt"] or now, reverse=True)

        stats = await session.execute(
            select(
                func.count(TestResult.id),
                func.avg(TestResult.final_score),
            ).where(TestResult.user_id == user_id)
        )
        tests_total, avg_score = stats.one()

    return {
        "user": user,
        "tests": test_results,
        "answers_map": answers_map,
        "messages": messages,
        "slots": slots,
        "upcoming_slot": upcoming_slot,
        "stage": stage,
        "timeline": timeline,
        "stats": {
            "tests_total": int(tests_total or 0),
            "average_score": float(avg_score) if avg_score is not None else None,
        },
    }


async def upsert_candidate(
    *,
    telegram_id: int,
    fio: str,
    city: Optional[str],
    is_active: bool,
    last_activity: Optional[datetime] = None,
) -> User:
    clean_fio = fio.strip()
    clean_city = city.strip() if city else None
    if not clean_fio:
        raise ValueError("Имя кандидата не может быть пустым")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        last_activity_value = last_activity or now

        if user:
            user.fio = clean_fio
            user.city = clean_city
            user.is_active = is_active
            user.last_activity = last_activity_value
        else:
            user = User(
                telegram_id=telegram_id,
                fio=clean_fio,
                city=clean_city,
                is_active=is_active,
                last_activity=last_activity_value,
            )
            session.add(user)

        await session.commit()
        await session.refresh(user)
        return user


async def toggle_candidate_activity(user_id: int, *, active: bool) -> bool:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False
        user.is_active = active
        await session.commit()
        return True


async def update_candidate(
    user_id: int,
    *,
    telegram_id: int,
    fio: str,
    city: Optional[str],
    is_active: bool,
) -> bool:
    clean_fio = fio.strip()
    clean_city = city.strip() if city else None
    if not clean_fio:
        raise ValueError("Имя кандидата не может быть пустым")

    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False

        user.telegram_id = telegram_id
        user.fio = clean_fio
        user.city = clean_city
        user.is_active = is_active

        await session.commit()
        return True


async def delete_candidate(user_id: int) -> bool:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False

        await session.execute(
            Slot.__table__.update()
            .where(Slot.candidate_tg_id == user.telegram_id)
            .values(
                candidate_tg_id=None,
                candidate_fio=None,
                candidate_tz=None,
                candidate_city_id=None,
                status=SlotStatus.FREE,
            )
        )
        await session.delete(user)
        await session.commit()
        return True


__all__ = [
    "CandidateRow",
    "list_candidates",
    "candidate_filter_options",
    "get_candidate_detail",
    "upsert_candidate",
    "toggle_candidate_activity",
    "update_candidate",
    "delete_candidate",
]
