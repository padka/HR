from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import String, cast, exists, func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from backend.apps.admin_ui.services.bot_service import (
    BotSendResult,
    BotService,
    get_bot_service,
)
from backend.apps.admin_ui.utils import paginate
from backend.core.db import async_session
from backend.domain.candidates.models import (
    AutoMessage,
    QuestionAnswer,
    TestResult,
    User,
)
from backend.domain.models import Slot, SlotStatus


@dataclass
class CandidateRow:
    user: User
    tests_total: int
    average_score: float | None
    latest_result: TestResult | None
    messages_total: int
    latest_message: AutoMessage | None
    stage: str
    latest_slot: Slot | None
    upcoming_slot: Slot | None


INTERVIEW_SCRIPT_STEPS: list[dict[str, str]] = [
    {
        "id": "greeting",
        "title": "Приветствие и ice-breaker",
        "description": "Познакомьтесь, уточните удобен ли формат интервью и настройте кандидата на диалог.",
    },
    {
        "id": "company_intro",
        "title": "Краткий рассказ о компании",
        "description": "Расскажите о миссии SMART, роли команды и основных задачах на позиции.",
    },
    {
        "id": "experience",
        "title": "Обсуждение опыта и мотивации",
        "description": "Уточните прошлые проекты, компетенции кандидата и его интерес к вакансии.",
    },
    {
        "id": "tests_review",
        "title": "Разбор результатов тестов",
        "description": "Обсудите сильные стороны и зоны роста по итогам тестов, задайте уточняющие вопросы.",
    },
    {
        "id": "next_steps",
        "title": "Дальнейшие шаги",
        "description": "Согласуйте ожидания по тесту 2 и ознакомительному дню, расскажите про дальнейший процесс.",
    },
]


INTRO_DAY_MESSAGE_TEMPLATE = (
    "{fio}, поздравляем с успешным интервью! "
    "Мы ждём вас на ознакомительный день {date} в {time}. "
    "Если понадобится перенести встречу — напишите, пожалуйста, заранее."
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _stage_label(latest_slot: Slot | None, now: datetime) -> str:
    if not latest_slot:
        return "Без интервью"
    status = (latest_slot.status or "").lower()
    start = _ensure_aware(latest_slot.start_utc) or now
    if status == SlotStatus.PENDING:
        return "Ожидает подтверждения" if start >= now else "Требует реакции"
    if status in {SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
        return "Интервью назначено" if start >= now else "Интервью завершено"
    if status == SlotStatus.CANCELED:
        return "Отменено"
    if status == SlotStatus.FREE:
        return "Свободный слот"
    return status.upper() or "Без интервью"


def _build_test_stage_summary(results: list[TestResult]) -> list[dict[str, object]]:
    if not results:
        return []
    chronological = sorted(
        results,
        key=lambda item: (
            _ensure_aware(item.created_at) or datetime.min.replace(tzinfo=UTC)
        ),
    )
    summary: list[dict[str, object]] = []
    for index, result in enumerate(chronological[:2]):
        summary.append(
            {
                "label": f"Тест {index + 1}",
                "result": result,
                "score": result.final_score,
                "raw_score": result.raw_score,
                "rating": result.rating,
                "dt": _ensure_aware(result.created_at),
            }
        )
    return summary


async def _distinct_ratings(session) -> list[str]:
    rows = await session.execute(
        select(func.distinct(TestResult.rating)).where(TestResult.rating.isnot(None))
    )
    return [value for value in rows.scalars() if value]


async def _distinct_cities(session) -> list[str]:
    rows = await session.execute(
        select(func.distinct(User.city))
        .where(User.city.isnot(None))
        .order_by(User.city.asc())
    )
    return [value for value in rows.scalars() if value]


async def list_candidates(
    *,
    page: int,
    per_page: int,
    search: str | None,
    city: str | None,
    is_active: bool | None,
    rating: str | None,
    has_tests: bool | None,
    has_messages: bool | None,
    stage: str | None = None,
    sort: str = "last_activity",
    order: str = "desc",
) -> dict[str, object]:
    async with async_session() as session:
        conditions = []
        now = datetime.now(UTC)

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
                exists(select(1).where(TestResult.user_id == User.id).correlate(User))
            )
        elif has_tests is False:
            conditions.append(
                ~exists(select(1).where(TestResult.user_id == User.id).correlate(User))
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
                        func.lower(Slot.status).in_(
                            [
                                SlotStatus.PENDING,
                                SlotStatus.BOOKED,
                                SlotStatus.CONFIRMED_BY_CANDIDATE,
                            ]
                        ),
                        Slot.start_utc >= now,
                    )
                    .correlate(User)
                )
            )
        elif stage_value == "alerts":
            conditions.append(
                or_(
                    ~exists(
                        select(1).where(TestResult.user_id == User.id).correlate(User)
                    ),
                    ~exists(
                        select(1)
                        .where(AutoMessage.target_chat_id == User.telegram_id)
                        .correlate(User)
                    ),
                )
            )

        sort_key = (sort or "last_activity").strip().lower()
        if sort_key not in {"fio", "last_activity"}:
            sort_key = "last_activity"
        order_dir = (order or "desc").strip().lower()
        if order_dir not in {"asc", "desc"}:
            order_dir = "desc"

        count_query = select(func.count()).select_from(User)
        if conditions:
            count_query = count_query.where(*conditions)
        total = await session.scalar(count_query) or 0

        pages_total, page, offset = paginate(total, page, per_page)

        if sort_key == "fio":
            primary_order = User.fio.asc() if order_dir == "asc" else User.fio.desc()
            secondary_order = User.id.asc() if order_dir == "asc" else User.id.desc()
        else:
            primary_order = (
                User.last_activity.asc()
                if order_dir == "asc"
                else User.last_activity.desc()
            )
            secondary_order = User.id.asc() if order_dir == "asc" else User.id.desc()

        list_query: Select = (
            select(User)
            .order_by(primary_order, secondary_order)
            .offset(offset)
            .limit(per_page)
        )
        if conditions:
            list_query = list_query.where(*conditions)

        users = (await session.scalars(list_query)).all()

        user_ids = [user.id for user in users]
        telegram_ids = [user.telegram_id for user in users if user.telegram_id]

        stats_map: dict[int, tuple[int, float | None]] = {}
        latest_result_map: dict[int, TestResult] = {}
        messages_map: dict[int, list[AutoMessage]] = {}
        latest_slot_map: dict[int, Slot] = {}
        upcoming_slot_map: dict[int, Slot] = {}
        stage_map: dict[int, str] = {}

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
                ).where(TestResult.user_id.in_(user_ids))
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
            slots_by_candidate: dict[int, list[Slot]] = defaultdict(list)
            for slot in slot_rows.scalars():
                if slot.candidate_tg_id is None:
                    continue
                slot.start_utc = _ensure_aware(slot.start_utc)
                slots_by_candidate[slot.candidate_tg_id].append(slot)

            for tg_id, slot_list in slots_by_candidate.items():
                slot_list.sort(key=lambda s: s.start_utc or now)
                latest_slot = slot_list[-1]
                upcoming_slot = next(
                    (s for s in slot_list if (s.start_utc or now) >= now), None
                )
                latest_slot_map[tg_id] = latest_slot
                if upcoming_slot:
                    upcoming_slot_map[tg_id] = upcoming_slot
                stage_map[tg_id] = _stage_label(latest_slot, now)

        items: list[CandidateRow] = []
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
                    latest_message=(
                        candidate_messages[0] if candidate_messages else None
                    ),
                    stage=stage,
                    latest_slot=latest_slot,
                    upcoming_slot=upcoming_slot,
                )
            )

        ratings = await _distinct_ratings(session)
        cities = await _distinct_cities(session)
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages_total": pages_total,
        "per_page": per_page,
        "sort": sort_key,
        "order": order_dir,
        "ratings": ratings,
        "cities": cities,
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


async def _collect_candidate_analytics(session, now: datetime) -> dict[str, object]:
    total = await session.scalar(select(func.count()).select_from(User)) or 0
    active = (
        await session.scalar(select(func.count()).where(User.is_active.is_(True))) or 0
    )
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
            select(func.count()).where(
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
            select(func.count()).where(
                ~exists(select(1).where(TestResult.user_id == User.id).correlate(User))
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
        ).where(Slot.candidate_tg_id.isnot(None))
    ).subquery()

    latest_rows = await session.execute(
        select(
            slot_sub.c.candidate_tg_id,
            slot_sub.c.start_utc,
            slot_sub.c.status,
        )
        .select_from(
            slot_sub.join(User, User.telegram_id == slot_sub.c.candidate_tg_id)
        )
        .where(slot_sub.c.rnk == 1)
    )

    stage_counts: dict[str, int] = defaultdict(int)
    upcoming_count = 0
    awaiting_confirmation = 0
    booked_active = 0
    completed_interviews = 0
    canceled_count = 0

    for _tg_id, start_utc, status in latest_rows:
        start = _ensure_aware(start_utc) or now
        status_norm = (status or "").lower()
        stage_counts[status_norm] += 1
        if status_norm == SlotStatus.PENDING:
            if start > now:
                upcoming_count += 1
            awaiting_confirmation += 1
        elif status_norm in {SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
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
        SlotStatus.CONFIRMED_BY_CANDIDATE: "Интервью назначено",
        SlotStatus.CANCELED: "Отменено",
        SlotStatus.FREE: "Свободные слоты",
    }
    stage_slug_map = {
        SlotStatus.PENDING: "interviews",
        SlotStatus.BOOKED: "interviews",
        SlotStatus.CONFIRMED_BY_CANDIDATE: "interviews",
        SlotStatus.CANCELED: "alerts",
        SlotStatus.FREE: None,
    }

    pipeline: list[dict[str, object]] = []
    for key, label in pipeline_labels.items():
        pipeline.append(
            {
                "label": label,
                "count": int(stage_counts.get(key, 0)),
                "slug": stage_slug_map.get(key),
            }
        )
    pipeline.append(
        {
            "label": "Без интервью",
            "count": without_slot,
            "slug": "alerts" if without_slot else None,
        }
    )

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


async def candidate_filter_options() -> dict[str, list[str]]:
    async with async_session() as session:
        cities = await _distinct_cities(session)
        ratings = await _distinct_ratings(session)
    return {"cities": cities, "ratings": ratings}


async def get_candidate_detail(user_id: int) -> dict[str, object] | None:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return None

        test_results = (
            (
                await session.execute(
                    select(TestResult)
                    .where(TestResult.user_id == user_id)
                    .order_by(TestResult.created_at.desc(), TestResult.id.desc())
                )
            )
            .scalars()
            .all()
        )

        test_ids = [result.id for result in test_results]
        answers_map: dict[int, dict[str, object]] = {}
        if test_ids:
            answer_rows = await session.execute(
                select(QuestionAnswer)
                .where(QuestionAnswer.test_result_id.in_(test_ids))
                .order_by(
                    QuestionAnswer.test_result_id.asc(),
                    QuestionAnswer.question_index.asc(),
                )
            )
            raw_map: dict[int, dict[str, object]] = defaultdict(
                lambda: {
                    "questions_total": 0,
                    "questions_correct": 0,
                    "questions_overtime": 0,
                    "questions": [],
                }
            )
            for answer in answer_rows.scalars():
                entry = raw_map[answer.test_result_id]
                entry["questions"].append(answer)
                entry["questions_total"] = int(entry["questions_total"]) + 1
                if answer.is_correct:
                    entry["questions_correct"] = int(entry["questions_correct"]) + 1
                if answer.overtime:
                    entry["questions_overtime"] = int(entry["questions_overtime"]) + 1
            answers_map = {
                test_id: {
                    "questions_total": int(values["questions_total"]),
                    "questions_correct": int(values["questions_correct"]),
                    "questions_overtime": int(values["questions_overtime"]),
                    "questions": list(values["questions"]),
                }
                for test_id, values in raw_map.items()
            }

        messages = (
            (
                await session.execute(
                    select(AutoMessage)
                    .where(AutoMessage.target_chat_id == user.telegram_id)
                    .order_by(AutoMessage.created_at.desc(), AutoMessage.id.desc())
                )
            )
            .scalars()
            .all()
        )

        slots = (
            (
                await session.execute(
                    select(Slot)
                    .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                    .where(Slot.candidate_tg_id == user.telegram_id)
                    .order_by(Slot.start_utc.desc(), Slot.id.desc())
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(UTC)
        for slot in slots:
            slot.start_utc = _ensure_aware(slot.start_utc)
        upcoming_slot = next(
            (
                slot
                for slot in reversed(slots)
                if slot.start_utc and slot.start_utc >= now
            ),
            None,
        )
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

        latest_interview = slots[0] if slots else None
        interview_feedback = {}
        if latest_interview and latest_interview.interview_feedback:
            # ensure we return a shallow copy to avoid accidental mutations downstream
            stored = latest_interview.interview_feedback or {}
            checklist = stored.get("checklist") if isinstance(stored, dict) else None
            interview_feedback = {
                "checklist": checklist if isinstance(checklist, dict) else {},
                "notes": stored.get("notes") if isinstance(stored, dict) else None,
                "updated_at": (
                    stored.get("updated_at") if isinstance(stored, dict) else None
                ),
            }

        stats = await session.execute(
            select(
                func.count(TestResult.id),
                func.avg(TestResult.final_score),
            ).where(TestResult.user_id == user_id)
        )
        tests_total, avg_score = stats.one()

        test_stage_summary = _build_test_stage_summary(test_results)

    return {
        "user": user,
        "tests": test_results,
        "answers_map": answers_map,
        "messages": messages,
        "slots": slots,
        "upcoming_slot": upcoming_slot,
        "stage": stage,
        "timeline": timeline,
        "test_stage_summary": test_stage_summary,
        "latest_interview": latest_interview,
        "interview_feedback": interview_feedback,
        "interview_script": INTERVIEW_SCRIPT_STEPS,
        "intro_message_template": INTRO_DAY_MESSAGE_TEMPLATE,
        "stats": {
            "tests_total": int(tests_total or 0),
            "average_score": float(avg_score) if avg_score is not None else None,
        },
        "test2_completed": int(tests_total or 0) >= 2,
    }


async def set_interview_outcome(
    candidate_id: int,
    slot_id: int,
    outcome: str,
) -> tuple[bool, str | None, dict[str, object] | None, dict[str, object] | None]:
    normalized = (outcome or "").strip().lower()
    aliases = {"passed": "success", "failed": "reject"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"success", "reject"}:
        return False, "Некорректный исход интервью.", None, None

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            return False, "Кандидат не найден.", None, None

        slot = await session.get(Slot, slot_id)
        if not slot:
            return False, "Интервью не найдено.", None, None

        if slot.candidate_tg_id and slot.candidate_tg_id != user.telegram_id:
            return (
                False,
                "Интервью относится к другому кандидату.",
                None,
                None,
            )

        slot.interview_outcome = normalized
        if normalized != "success":
            slot.test2_sent_at = None
        await session.commit()

        slot_info: dict[str, object] = {
            "id": slot.id,
            "candidate_tg_id": slot.candidate_tg_id,
            "candidate_tz": getattr(slot, "candidate_tz", None),
            "candidate_city_id": getattr(slot, "candidate_city_id", None),
            "candidate_fio": getattr(slot, "candidate_fio", None),
        }
        user_info: dict[str, object] = {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "fio": user.fio,
        }

    return True, normalized, slot_info, user_info


async def send_test2(
    user_id: int,
    *,
    bot_service: BotService | None = None,
    slot_data: dict[str, object] | None = None,
) -> BotSendResult:
    service = bot_service
    if service is None:
        try:
            service = get_bot_service()
        except RuntimeError:
            return BotSendResult(
                ok=False,
                status="skipped:not_configured",
                error="Бот недоступен. Проверьте конфигурацию интеграции.",
            )

    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user or not user.telegram_id:
            return BotSendResult(
                ok=False,
                status="skipped:not_found",
                error="Кандидат не найден или не привязан к Telegram.",
            )

        telegram_id = int(user.telegram_id)
        candidate_name = user.fio
        candidate_tz: str | None = None
        candidate_city: int | None = None
        slot_id: int | None = None

        if slot_data:
            slot_id_value = slot_data.get("id")
            if isinstance(slot_id_value, int):
                slot_id = slot_id_value
            elif isinstance(slot_id_value, str) and slot_id_value.isdigit():
                slot_id = int(slot_id_value)

            tz_value = slot_data.get("candidate_tz")
            if isinstance(tz_value, str) and tz_value.strip():
                candidate_tz = tz_value

            city_value = slot_data.get("candidate_city_id")
            if isinstance(city_value, int):
                candidate_city = city_value
            elif isinstance(city_value, str) and city_value.isdigit():
                candidate_city = int(city_value)

            slot_name = slot_data.get("candidate_fio")
            if isinstance(slot_name, str) and slot_name.strip():
                candidate_name = slot_name

        if slot_id is None:
            slot = await session.scalar(
                select(Slot)
                .where(Slot.candidate_tg_id == telegram_id)
                .order_by(Slot.start_utc.desc(), Slot.id.desc())
            )
            if slot:
                slot_id = slot.id
                candidate_tz = getattr(slot, "candidate_tz", None)
                candidate_city = getattr(slot, "candidate_city_id", None)
                candidate_name = getattr(slot, "candidate_fio", None) or candidate_name

    result = await service.send_test2(
        telegram_id,
        candidate_tz,
        candidate_city,
        candidate_name,
    )

    if result.ok and slot_id:
        async with async_session() as session:
            slot = await session.get(Slot, slot_id)
            if slot:
                slot.test2_sent_at = datetime.now(UTC)
                await session.commit()

    return result


async def send_intro_message(
    candidate_id: int,
    *,
    date_value: str,
    time_value: str,
    message_text: str | None,
    bot_service: BotService | None = None,
) -> tuple[bool, str]:
    date_clean = (date_value or "").strip()
    time_clean = (time_value or "").strip()
    if not date_clean or not time_clean:
        return False, "Укажите дату и время ознакомительного дня."

    try:
        visit_date = date.fromisoformat(date_clean)
    except ValueError:
        return False, "Некорректная дата ознакомительного дня."

    try:
        visit_time = time.fromisoformat(time_clean)
    except ValueError:
        return False, "Некорректное время ознакомительного дня."

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user or not user.telegram_id:
            return False, "Кандидат не найден или не привязан к Telegram."
        telegram_id = int(user.telegram_id)
        fio = user.fio

    clean_message = (message_text or "").strip()
    if not clean_message:
        clean_message = INTRO_DAY_MESSAGE_TEMPLATE.format(
            fio=fio,
            date=visit_date.strftime("%d.%m.%Y"),
            time=visit_time.strftime("%H:%M"),
        )

    service = bot_service
    if service is None:
        try:
            service = get_bot_service()
        except RuntimeError:
            return False, "Бот недоступен. Проверьте конфигурацию."

    result = await service.send_intro_message(telegram_id, clean_message)
    if not result.ok:
        reason = result.error or result.message or "Не удалось отправить сообщение."
        return False, reason

    send_time = datetime.combine(visit_date, visit_time).strftime("%Y-%m-%d %H:%M")
    async with async_session() as session:
        record = AutoMessage(
            message_text=clean_message,
            send_time=send_time,
            target_chat_id=telegram_id,
        )
        session.add(record)
        await session.commit()

    return True, "Сообщение отправлено кандидату."


async def save_interview_feedback(
    slot_id: int,
    checklist_ids: list[str],
    notes: str,
    *,
    candidate_id: int | None = None,
) -> tuple[bool, str]:
    step_ids = {step["id"] for step in INTERVIEW_SCRIPT_STEPS}
    normalized: dict[str, bool] = {step_id: False for step_id in step_ids}
    for checked in checklist_ids:
        if checked in normalized:
            normalized[checked] = True

    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return False, "Интервью не найдено."

        if candidate_id is not None:
            user = await session.get(User, candidate_id)
            if not user:
                return False, "Кандидат не найден."
            if slot.candidate_tg_id and slot.candidate_tg_id != user.telegram_id:
                return False, "Интервью не относится к выбранному кандидату."

        slot.interview_feedback = {
            "checklist": normalized,
            "notes": notes.strip() or None,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        await session.commit()

    return True, "Отметки по собеседованию сохранены."


async def schedule_intro_day_message(
    candidate_id: int,
    *,
    date_value: str,
    time_value: str,
    message_text: str | None,
) -> tuple[bool, str]:
    return await send_intro_message(
        candidate_id,
        date_value=date_value,
        time_value=time_value,
        message_text=message_text,
    )


async def upsert_candidate(
    *,
    telegram_id: int,
    fio: str,
    city: str | None,
    is_active: bool,
    last_activity: datetime | None = None,
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
        now = datetime.now(UTC)
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
    city: str | None,
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
    "set_interview_outcome",
    "send_test2",
    "send_intro_message",
    "schedule_intro_day_message",
    "save_interview_feedback",
    "upsert_candidate",
    "toggle_candidate_activity",
    "update_candidate",
    "delete_candidate",
]
