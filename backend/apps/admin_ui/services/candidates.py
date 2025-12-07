from __future__ import annotations

import logging
import math
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import String, cast, delete, exists, func, literal, literal_column, or_, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select, case

from backend.apps.admin_ui.utils import paginate
from backend.apps.admin_ui.services.chat import get_chat_templates
from backend.apps.admin_ui.timezones import DEFAULT_TZ
from backend.apps.bot.config import PASS_THRESHOLD, TEST2_QUESTIONS
from backend.apps.bot.services import approve_slot_and_notify
from backend.core.db import async_session
from backend.domain.candidates.models import AutoMessage, InterviewNote, QuestionAnswer, TestResult, User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter, Slot, SlotStatus

if TYPE_CHECKING:  # pragma: no cover - used only for typing
    from backend.apps.admin_ui.services.bot_service import BotService


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
    status_slug: str = "new"
    status_label: str = "Новые"


STATUS_DEFINITIONS: "OrderedDict[str, Dict[str, str]]" = OrderedDict(
    [
        # Fallback for candidates without статус
        ("new", {"label": "Новые (без статуса)", "icon": "🆕", "tone": "muted"}),
        # Active statuses
        ("test1_completed", {"label": "Прошел тестирование", "icon": "📝", "tone": "info"}),
        ("waiting_slot", {"label": "Ждет назначения слота", "icon": "⏳", "tone": "warning"}),
        ("stalled_waiting_slot", {"label": "Долго ждет слота (>24ч)", "icon": "⚠️", "tone": "danger"}),
        ("interview_scheduled", {"label": "Назначено собеседование", "icon": "📅", "tone": "primary"}),
        ("interview_confirmed", {"label": "Подтвердился (собес)", "icon": "✅", "tone": "success"}),
        ("test2_sent", {"label": "Прошел собес (Тест 2)", "icon": "📨", "tone": "primary"}),
        ("test2_completed", {"label": "Прошел Тест 2 (ожидает ОД)", "icon": "✅", "tone": "info"}),
        ("intro_day_scheduled", {"label": "Назначен ознакомительный день", "icon": "📆", "tone": "primary"}),
        ("intro_day_confirmed_preliminary", {"label": "Предварительно подтвердился (ОД)", "icon": "👍", "tone": "success"}),
        ("intro_day_confirmed_day_of", {"label": "Подтвердился (ОД в день)", "icon": "✅", "tone": "success"}),
        # Success statuses
        ("hired", {"label": "Закреплен на обучение", "icon": "🎉", "tone": "success"}),
        ("not_hired", {"label": "Не закреплен", "icon": "⚠️", "tone": "warning"}),
        # Rejection statuses
        ("interview_declined", {"label": "Отказ на этапе собеседования", "icon": "❌", "tone": "danger"}),
        ("test2_failed", {"label": "Не прошел Тест 2", "icon": "❌", "tone": "danger"}),
        ("intro_day_declined_invitation", {"label": "Отказ на этапе ОД (приглашение)", "icon": "❌", "tone": "danger"}),
        ("intro_day_declined_day_of", {"label": "Отказ (ОД в день)", "icon": "❌", "tone": "danger"}),
    ]
)

STATUS_ORDER: Dict[str, int] = {slug: idx for idx, slug in enumerate(STATUS_DEFINITIONS.keys())}

FUNNEL_STAGES: List[Dict[str, Any]] = [
    {
        "slug": "new",
        "label": "Новые",
        "icon": "🆕",
        "tone": "muted",
        "statuses": ["new"],
        "track_conversion": True,
    },
    {
        "slug": "test1",
        "label": "Тест 1",
        "icon": "📝",
        "tone": "info",
        "statuses": ["test1_completed", "waiting_slot", "stalled_waiting_slot"],
        "track_conversion": True,
    },
    {
        "slug": "interview",
        "label": "Собеседование",
        "icon": "📅",
        "tone": "primary",
        "statuses": ["interview_scheduled", "interview_confirmed"],
        "track_conversion": True,
    },
    {
        "slug": "test2",
        "label": "Тест 2",
        "icon": "📨",
        "tone": "primary",
        "statuses": ["test2_sent", "test2_completed"],
        "track_conversion": True,
    },
    {
        "slug": "intro_day",
        "label": "Ознакомительный день",
        "icon": "📆",
        "tone": "primary",
        "statuses": [
            "test2_sent",
            "test2_completed",
            "intro_day_scheduled",
            "intro_day_confirmed_preliminary",
            "intro_day_confirmed_day_of",
        ],
        "track_conversion": True,
    },
    {
        "slug": "decision",
        "label": "Решение",
        "icon": "🏁",
        "tone": "success",
        "statuses": ["hired", "not_hired"],
        "track_conversion": True,
    },
    {
        "slug": "declined",
        "label": "Отказы",
        "icon": "⚠️",
        "tone": "danger",
        "statuses": [
            "interview_declined",
            "test2_failed",
            "intro_day_declined_invitation",
            "intro_day_declined_day_of",
        ],
        "track_conversion": False,
    },
]

INTRO_DAY_FUNNEL_STAGES: List[Dict[str, Any]] = [
    {
        "slug": "intro_queue",
        "label": "Ожидают назначение ОД",
        "icon": "⏳",
        "tone": "info",
        "statuses": ["test2_completed"],
        "track_conversion": True,
    },
    {
        "slug": "intro_invited",
        "label": "Приглашены",
        "icon": "📆",
        "tone": "primary",
        "statuses": ["intro_day_scheduled"],
        "track_conversion": True,
    },
    {
        "slug": "intro_confirmed",
        "label": "Подтвердили участие",
        "icon": "👍",
        "tone": "success",
        "statuses": [
            "intro_day_confirmed_preliminary",
            "intro_day_confirmed_day_of",
        ],
        "track_conversion": True,
    },
    {
        "slug": "intro_result",
        "label": "Результат",
        "icon": "🏁",
        "tone": "success",
        "statuses": ["hired", "not_hired"],
        "track_conversion": True,
    },
    {
        "slug": "intro_declined",
        "label": "Отказались",
        "icon": "⚠️",
        "tone": "danger",
        "statuses": [
            "intro_day_declined_invitation",
            "intro_day_declined_day_of",
        ],
        "track_conversion": False,
    },
]

INTERVIEW_PIPELINE_STATUSES = [
    "new",
    "test1_completed",
    "waiting_slot",
    "stalled_waiting_slot",
    "interview_scheduled",
    "interview_confirmed",
    "test2_sent",
]

INTRO_DAY_PIPELINE_STATUSES = [
    "test2_completed",
    "intro_day_scheduled",
    "intro_day_confirmed_preliminary",
    "intro_day_confirmed_day_of",
    "intro_day_declined_invitation",
    "intro_day_declined_day_of",
    "hired",
    "not_hired",
]

PIPELINE_DEFINITIONS: "OrderedDict[str, Dict[str, Any]]" = OrderedDict(
    [
        (
            "interview",
            {
                "label": "Интервью",
                "statuses": INTERVIEW_PIPELINE_STATUSES,
                "stages": FUNNEL_STAGES,
                "droppable_statuses": {
                    "test1_completed",
                    "waiting_slot",
                    "stalled_waiting_slot",
                    "interview_scheduled",
                    "interview_confirmed",
                    "test2_sent",
                },
            },
        ),
        (
            "intro_day",
            {
                "label": "Ознакомительный день",
                "statuses": INTRO_DAY_PIPELINE_STATUSES,
                "stages": INTRO_DAY_FUNNEL_STAGES,
                "droppable_statuses": {
                    "test2_completed",
                    "intro_day_scheduled",
                    "intro_day_confirmed_preliminary",
                },
            },
        ),
    ]
)

DEFAULT_PIPELINE = "interview"

TEST_STATUS_LABELS: Dict[str, Dict[str, str]] = {
    "passed": {"label": "Пройден", "icon": "✅"},
    "failed": {"label": "Не пройден", "icon": "❌"},
    "in_progress": {"label": "В процессе", "icon": "⏳"},
    "not_started": {"label": "Не начинал", "icon": "—"},
}

TEST2_TOTAL_QUESTIONS: int = len(TEST2_QUESTIONS)
TEST2_MIN_CORRECT: int = (
    0 if TEST2_TOTAL_QUESTIONS == 0 else max(1, math.ceil(TEST2_TOTAL_QUESTIONS * PASS_THRESHOLD))
)
STATUSES_PENDING_INTRO_DAY: Set[CandidateStatus] = {
    CandidateStatus.TEST2_COMPLETED,
}

logger = logging.getLogger(__name__)

INTERVIEW_RECOMMENDATION_CHOICES = [
    {"value": "proceed", "label": "Пригласить на ознакомительный день", "tone": "success"},
    {"value": "follow_up", "label": "Нужен дополнительный созвон", "tone": "warning"},
    {"value": "reject", "label": "Отказать кандидату", "tone": "danger"},
    {"value": "undecided", "label": "Решение не принято", "tone": "muted"},
]
INTERVIEW_RECOMMENDATION_LOOKUP = {item["value"]: item for item in INTERVIEW_RECOMMENDATION_CHOICES}
INTERVIEW_RECOMMENDATION_VALUES = set(INTERVIEW_RECOMMENDATION_LOOKUP.keys())

INTERVIEW_FORM_SECTIONS = [
    {
        "title": "Паспорт интервью",
        "description": "Фиксируйте базовые данные перед началом разговора.",
        "questions": [
            {"key": "interviewer_name", "type": "text", "label": "Интервьюер", "placeholder": "Например, Ирина С."},
            {"key": "interviewed_at", "type": "datetime", "label": "Дата и время интервью"},
        ],
    },
    {
        "title": "1. Разогрев и ожидания",
        "description": "Понять мотивацию кандидата и его комфорт с форматом.",
        "questions": [
            {"key": "intro_greeting_done", "type": "checkbox", "label": "Связь проверена, кандидат готов"},
            {"key": "expectations_discussed", "type": "checkbox", "label": "Обсудили ожидания и критерии выбора"},
            {"key": "criteria_match", "type": "checkbox", "label": "Наш формат совпадает с критериями кандидата"},
            {"key": "live_meetings_ok", "type": "checkbox", "label": "Комфортно с 70% живых встреч"},
            {"key": "client_experience", "type": "checkbox", "label": "Есть опыт работы с клиентами офлайн"},
            {"key": "candidate_expectations", "type": "textarea", "label": "Три основных критерия кандидата"},
            {"key": "criteria_notes", "type": "textarea", "label": "Комментарии по критериям"},
            {"key": "client_experience_notes", "type": "textarea", "label": "Примеры живых встреч / продаж"},
        ],
    },
    {
        "title": "2. Компания и продукт",
        "description": "Убедитесь, что кандидат понял, чем мы занимаемся.",
        "questions": [
            {"key": "company_story_shared", "type": "checkbox", "label": "Рассказывал про сопровождение карточек"},
            {"key": "services_fit_confirmed", "type": "checkbox", "label": "Кандидату интересен продукт"},
            {"key": "product_interest_notes", "type": "textarea", "label": "Реакция на кейсы / вопросы"},
        ],
    },
    {
        "title": "3. Формат и задачи",
        "description": "Проверяем готовность к полевому формату и обучению.",
        "questions": [
            {"key": "fieldwork_ready", "type": "checkbox", "label": "Готов работать большую часть дня в поле"},
            {"key": "people_ready", "type": "checkbox", "label": "Комфортно вести переговоры с владельцами"},
            {"key": "training_interest", "type": "checkbox", "label": "Мотивирован пройти обучение / наставника"},
            {"key": "format_notes", "type": "textarea", "label": "Как кандидат видит свой рабочий день"},
        ],
    },
    {
        "title": "4. Деньги и мотивация",
        "description": "Фиксируем ожидания по доходу и ключевой драйвер.",
        "questions": [
            {"key": "money_expectations", "type": "text", "label": "Ожидаемый доход", "placeholder": "Например, 80 000 ₽"},
            {"key": "motivation_notes", "type": "textarea", "label": "Что драйвит/останавливает"},
        ],
    },
    {
        "title": "5. Итоги и следующий шаг",
        "description": "Сформулируйте выводы и договорённости.",
        "questions": [
            {"key": "recommendation", "type": "radio", "label": "Решение по кандидату", "options": INTERVIEW_RECOMMENDATION_CHOICES},
            {"key": "strengths", "type": "textarea", "label": "Сильные стороны"},
            {"key": "risks", "type": "textarea", "label": "Риски / сомнения"},
            {"key": "summary_notes", "type": "textarea", "label": "Как прошло интервью"},
            {"key": "next_steps", "type": "textarea", "label": "Что делаем дальше"},
            {"key": "question_log", "type": "textarea", "label": "Какие вопросы задавал кандидат"},
        ],
    },
]


def _has_passed_test2(results: Sequence[TestResult]) -> bool:
    """Return True if there is a passing TEST2 result in the collection."""
    for result in results:
        rating = (result.rating or "").strip().upper()
        if rating != "TEST2":
            continue
        if TEST2_TOTAL_QUESTIONS:
            return (result.raw_score or 0) >= TEST2_MIN_CORRECT
        return (result.final_score or 0) >= 0
    return False


def _build_field_types(sections: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    field_types: Dict[str, str] = {}
    for section in sections:
        for question in section.get("questions", []):
            field_types[question["key"]] = question["type"]
    return field_types


INTERVIEW_FIELD_TYPES = _build_field_types(INTERVIEW_FORM_SECTIONS)

def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _serialize_answer(answer: QuestionAnswer) -> Dict[str, Any]:
    return {
        "question_index": answer.question_index,
        "question_text": answer.question_text,
        "user_answer": answer.user_answer,
        "correct_answer": answer.correct_answer,
        "attempts_count": answer.attempts_count,
        "time_spent": answer.time_spent,
        "is_correct": answer.is_correct,
        "overtime": answer.overtime,
    }


def _serialize_interview_note(note: Optional[InterviewNote]) -> Dict[str, Any]:
    if not note:
        return {
            "interviewer_name": None,
            "data": {},
            "updated_at": None,
            "created_at": None,
        }
    return {
        "interviewer_name": note.interviewer_name,
        "data": note.data or {},
        "updated_at": _ensure_aware(note.updated_at),
        "created_at": _ensure_aware(note.created_at),
    }


def _latest_test2_sent(slots: Sequence[Slot]) -> Optional[datetime]:
    latest: Optional[datetime] = None
    for slot in slots:
        sent_at = getattr(slot, "test2_sent_at", None)
        sent_aware = _ensure_aware(sent_at)
        if sent_aware and (latest is None or sent_aware > latest):
            latest = sent_aware
    return latest


def _resolve_telemost_url(slots: Sequence[Slot]) -> Tuple[Optional[str], Optional[str]]:
    """Return telemost URL and the inferred source ('upcoming', 'recent')."""

    now = datetime.now(timezone.utc)
    upcoming: List[Tuple[datetime, str]] = []
    historical: List[Tuple[datetime, str]] = []

    for slot in slots:
        recruiter = getattr(slot, "recruiter", None)
        url = getattr(recruiter, "telemost_url", None) if recruiter else None
        if not url:
            continue
        start = _ensure_aware(getattr(slot, "start_utc", None))
        if start and start >= now:
            upcoming.append((start, url))
        else:
            historical.append((start or datetime.min.replace(tzinfo=timezone.utc), url))

    if upcoming:
        upcoming.sort(key=lambda item: item[0])
        return upcoming[0][1], "upcoming"
    if historical:
        historical.sort(key=lambda item: item[0], reverse=True)
        return historical[0][1], "recent"
    return None, None


def _status_labels() -> Dict[str, str]:
    return {
        "passed": "Пройден",
        "failed": "Не пройден",
        "not_started": "Не проходил",
        "in_progress": "В процессе",
    }


def _status_label(slug: str) -> str:
    return STATUS_DEFINITIONS.get(slug, {}).get("label", slug)


def _status_icon(slug: str) -> str:
    return STATUS_DEFINITIONS.get(slug, {}).get("icon", "")


def _status_tone(slug: str) -> str:
    return STATUS_DEFINITIONS.get(slug, {}).get("tone", "info")


def _build_test_sections(
    results: Sequence[TestResult],
    answers_by_result: Dict[int, List[QuestionAnswer]],
    slots: Sequence[Slot],
) -> "OrderedDict[str, Dict[str, Any]]":
    grouped: Dict[str, List[TestResult]] = defaultdict(list)
    for result in results:
        key = (result.rating or "").strip().upper()
        grouped[key].append(result)

    for items in grouped.values():
        items.sort(key=lambda res: (res.created_at or datetime.min, res.id), reverse=True)

    sections: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    labels = _status_labels()

    test2_last_sent = _latest_test2_sent(slots)

    for key, slug, title in [
        ("TEST1", "test1", "Тест 1"),
        ("TEST2", "test2", "Тест 2"),
    ]:
        entries = grouped.get(key, [])
        section: Dict[str, Any] = {
            "key": slug,
            "title": title,
            "status": "not_started",
            "status_label": labels.get("not_started"),
            "summary": "Тест ещё не проходил",
            "completed_at": None,
            "pending_since": None,
            "details": {
                "questions": [],
                "stats": {
                    "total_questions": 0,
                    "correct_answers": 0,
                    "overtime_questions": 0,
                    "raw_score": 0,
                    "final_score": 0.0,
                    "total_time": 0,
                },
            },
            "history": [],
        }

        if entries:
            latest = entries[0]
            answers = answers_by_result.get(latest.id, [])
            serialized = [_serialize_answer(answer) for answer in answers]
            total_questions = len(serialized)
            correct_answers = sum(1 for answer in answers if answer.is_correct)
            overtime_questions = sum(1 for answer in answers if answer.overtime)

            section["completed_at"] = _ensure_aware(latest.created_at)
            section["details"]["questions"] = serialized
            section["details"]["stats"] = {
                "total_questions": total_questions,
                "correct_answers": correct_answers,
                "overtime_questions": overtime_questions,
                "raw_score": latest.raw_score,
                "final_score": latest.final_score,
                "total_time": latest.total_time,
            }
            section["history"] = [
                {
                    "id": res.id,
                    "completed_at": _ensure_aware(res.created_at),
                    "raw_score": res.raw_score,
                    "final_score": res.final_score,
                }
                for res in entries
            ]

            if key == "TEST1":
                section["status"] = "passed"
                section["status_label"] = labels.get("passed")
                section["summary"] = f"Анкета заполнена ({total_questions} ответов)"
            else:
                total_questions = total_questions or len(answers)
                correct_answers = correct_answers or latest.raw_score or 0
                if total_questions <= 0:
                    # fallback to avoid division errors
                    total_questions = max(int(latest.raw_score or 0), 1)
                ratio = correct_answers / max(1, total_questions)
                status = "passed" if ratio >= PASS_THRESHOLD else "failed"
                section["status"] = status
                section["status_label"] = labels.get(status)
                section["summary"] = (
                    f"{correct_answers}/{total_questions} верных · {latest.final_score:.1f} баллов"
                )
                if test2_last_sent and (
                    section["completed_at"] is None or section["completed_at"] < test2_last_sent
                ):
                    section["status"] = "in_progress"
                    section["status_label"] = labels.get("in_progress")
                    section["pending_since"] = test2_last_sent
                    section["summary"] = "Тест отправлен, ожидаем завершения кандидатом"
        else:
            if key == "TEST2" and test2_last_sent:
                section["status"] = "in_progress"
                section["status_label"] = labels.get("in_progress")
                section["pending_since"] = test2_last_sent
                section["summary"] = "Тест отправлен, ожидаем завершения кандидатом"

        sections[slug] = section

    return sections


def _stage_label(latest_slot: Optional[Slot], now: datetime) -> str:
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
    statuses: Optional[Sequence[str]] = None,
    recruiter_id: Optional[int] = None,
    city_ids: Optional[Sequence[int]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    test1_status: Optional[str] = None,
    test2_status: Optional[str] = None,
    sort: Optional[str] = None,
    sort_dir: Optional[str] = None,
    calendar_mode: Optional[str] = None,
    pipeline: str = DEFAULT_PIPELINE,
) -> Dict[str, object]:
    normalized_statuses: List[str] = [
        slug for slug in (statuses or []) if slug in STATUS_DEFINITIONS
    ]
    test1_status = (test1_status or '').strip().lower() or None
    test2_status = (test2_status or '').strip().lower() or None
    sort_key = (sort or 'event').strip().lower() or 'event'
    sort_direction = 'desc' if (sort_dir or '').lower() in {'desc', 'descending'} else 'asc'

    pipeline_slug = (pipeline or DEFAULT_PIPELINE).strip().lower() or DEFAULT_PIPELINE
    if pipeline_slug not in PIPELINE_DEFINITIONS:
        pipeline_slug = DEFAULT_PIPELINE
    pipeline_config = PIPELINE_DEFINITIONS[pipeline_slug]
    pipeline_statuses: List[str] = pipeline_config["statuses"]
    extra_terminal_statuses = {"hired", "not_hired"}
    allowed_statuses_set = set(pipeline_statuses)
    allowed_with_terminal = allowed_statuses_set | extra_terminal_statuses
    pipeline_stages = pipeline_config["stages"]
    droppable_statuses = set(pipeline_config.get("droppable_statuses", []))
    is_intro_pipeline = pipeline_slug == "intro_day"

    now = datetime.now(timezone.utc)
    today = now.date()

    normalized_calendar_mode = "day" if calendar_mode else None

    user_specified_start = date_from is not None
    user_specified_end = date_to is not None

    range_start_utc: Optional[datetime] = _ensure_aware(date_from)
    range_end_utc: Optional[datetime] = _ensure_aware(date_to)
    if range_start_utc is not None:
        range_start_utc = range_start_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_end_utc is not None:
        range_end_utc = range_end_utc.replace(hour=23, minute=59, second=59, microsecond=999999)

    if normalized_calendar_mode:
        if not user_specified_start or range_start_utc is None:
            range_start_utc = datetime.combine(today, time.min, timezone.utc)
        calendar_start = range_start_utc
        if not user_specified_end or range_end_utc is None:
            calendar_end = calendar_start.replace(hour=23, minute=59, second=59, microsecond=999999)
            range_end_utc = calendar_end
        else:
            calendar_end = range_end_utc
    else:
        calendar_start = range_start_utc or datetime.combine(today, time.min, timezone.utc)
        calendar_end = range_end_utc or (calendar_start + timedelta(days=6))

    async with async_session() as session:
        conditions: List[Any] = []

        city_names: List[str] = []
        if city_ids:
            city_rows = await session.execute(select(City.name).where(City.id.in_(city_ids)))
            city_names = [row[0] for row in city_rows if row[0]]

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

        if city_names:
            conditions.append(User.city.in_(city_names))

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

        has_tests_expr = exists(
            select(1)
            .where(TestResult.user_id == User.id)
            .correlate(User)
        )

        if has_tests is True:
            conditions.append(has_tests_expr)
        elif has_tests is False:
            conditions.append(~has_tests_expr)

        has_messages_expr = exists(
            select(1)
            .where(AutoMessage.target_chat_id == User.telegram_id)
            .correlate(User)
        )

        if has_messages is True:
            conditions.append(has_messages_expr)
        elif has_messages is False:
            conditions.append(~has_messages_expr)

        test1_completed_expr = exists(
            select(1)
            .where(
                TestResult.user_id == User.id,
                func.upper(TestResult.rating) == literal('TEST1'),
            )
            .correlate(User)
        )

        test2_result_expr = exists(
            select(1)
            .where(
                TestResult.user_id == User.id,
                func.upper(TestResult.rating) == literal('TEST2'),
            )
            .correlate(User)
        )

        test2_pass_expr = exists(
            select(1)
            .where(
                TestResult.user_id == User.id,
                func.upper(TestResult.rating) == literal('TEST2'),
                TestResult.raw_score >= TEST2_MIN_CORRECT,
            )
            .correlate(User)
        )

        test2_sent_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                Slot.test2_sent_at.isnot(None),
            )
            .correlate(User)
        )

        success_outcome_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                Slot.interview_outcome == 'success',
            )
            .correlate(User)
        )

        reject_outcome_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                Slot.interview_outcome == 'reject',
            )
            .correlate(User)
        )

        pending_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                func.lower(Slot.status) == SlotStatus.PENDING,
                Slot.start_utc >= now,
            )
            .correlate(User)
        )

        booked_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                func.lower(Slot.status) == SlotStatus.BOOKED,
                Slot.start_utc >= now,
            )
            .correlate(User)
        )

        confirmed_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                func.lower(Slot.status) == SlotStatus.CONFIRMED_BY_CANDIDATE,
                Slot.start_utc >= now,
            )
            .correlate(User)
        )

        past_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                Slot.start_utc < now,
                func.lower(Slot.status).in_(
                    [SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE]
                ),
                Slot.interview_outcome.is_(None),
            )
            .correlate(User)
        )

        has_slot_expr = exists(
            select(1)
            .where(Slot.candidate_tg_id == User.telegram_id)
            .correlate(User)
        )

        has_intro_day_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                Slot.purpose == 'intro_day',
            )
            .correlate(User)
        )

        # Use the new candidate_status field from the database
        # Cast to string and coalesce NULL to 'new'
        status_case = func.lower(
            func.coalesce(
                cast(User.candidate_status, String),
                literal('new')
            )
        ).label('status_slug')

        status_rank_expr = case(
            {slug: rank for slug, rank in STATUS_ORDER.items()},
            value=status_case,
            else_=len(STATUS_ORDER),
        ).label('status_rank')

        slot_pipeline_expr = (
            Slot.purpose == 'intro_day'
            if is_intro_pipeline
            else or_(Slot.purpose.is_(None), Slot.purpose != 'intro_day')
        )

        primary_event_expr = (
            select(func.min(Slot.start_utc))
            .where(
                Slot.candidate_tg_id == User.telegram_id,
                slot_pipeline_expr,
                Slot.start_utc >= now,
            )
            .correlate(User)
            .scalar_subquery()
        ).label('primary_event_at')

        normalized_statuses = [slug for slug in normalized_statuses if slug in allowed_with_terminal]
        status_filter_values = normalized_statuses or (pipeline_statuses or ["__unreachable__"])
        conditions.append(status_case.in_(status_filter_values))

        if recruiter_id is not None:
            conditions.append(
                exists(
                    select(1)
                    .where(
                        Slot.candidate_tg_id == User.telegram_id,
                        Slot.recruiter_id == recruiter_id,
                    )
                    .correlate(User)
                )
            )

        if range_start_utc or range_end_utc:
            range_clauses: List[Any] = [Slot.candidate_tg_id == User.telegram_id]
            if range_start_utc is not None:
                range_clauses.append(Slot.start_utc >= range_start_utc)
            if range_end_utc is not None:
                range_clauses.append(Slot.start_utc <= range_end_utc)
            conditions.append(
                exists(select(1).where(*range_clauses).correlate(User))
            )

        if test1_status == 'passed':
            conditions.append(test1_completed_expr)
        elif test1_status == 'not_started':
            conditions.append(~test1_completed_expr)

        if test2_status == 'passed':
            conditions.append(test2_pass_expr)
        elif test2_status == 'failed':
            conditions.append(test2_result_expr & ~test2_pass_expr)
        elif test2_status == 'in_progress':
            conditions.append(~test2_result_expr & test2_sent_expr)
        elif test2_status == 'not_started':
            conditions.append(~test2_result_expr & ~test2_sent_expr)

        stage_value = (stage or '').strip().lower() or None
        if stage_value == 'interviews':
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
        elif stage_value == 'alerts':
            conditions.append(
                or_(
                    ~has_tests_expr,
                    ~has_messages_expr,
                )
            )

        count_query = select(func.count()).select_from(User)
        if conditions:
            count_query = count_query.where(*conditions)
        total = await session.scalar(count_query) or 0

        pages_total, page, offset = paginate(total, page, per_page)

        totals_rows = await session.execute(
            select(status_case, func.count())
            .select_from(User)
            .where(*conditions)
            .group_by(status_case)
        )
        status_totals = {
            slug: count for slug, count in totals_rows if slug in allowed_with_terminal
        }
        stage_totals = {
            stage['slug']: sum(status_totals.get(status, 0) for status in stage['statuses'])
            for stage in pipeline_stages
        }
        funnel_summary: List[Dict[str, Any]] = []
        prev_stage_total: Optional[int] = None
        for stage in pipeline_stages:
            count = stage_totals.get(stage['slug'], 0)
            share = round((count / total) * 100, 1) if total else 0.0
            conversion = None
            if stage.get('track_conversion', True) and prev_stage_total not in (None, 0):
                conversion = round((count / prev_stage_total) * 100, 1)
            funnel_summary.append(
                {
                    'slug': stage['slug'],
                    'label': stage['label'],
                    'icon': stage['icon'],
                    'count': count,
                    'share': share,
                    'conversion': conversion,
                    'tone': stage.get('tone', 'info'),
                    'statuses': stage.get('statuses', []),
                }
            )
            if stage.get('track_conversion', True):
                prev_stage_total = count

        today_start = datetime.combine(today, time.min, timezone.utc)
        today_end = today_start + timedelta(days=1) - timedelta(microseconds=1)
        today_rows = await session.execute(
            select(status_case, func.count())
            .select_from(User)
            .where(
                *conditions,
                primary_event_expr.is_not(None),
                primary_event_expr >= today_start,
                primary_event_expr <= today_end,
            )
            .group_by(status_case)
        )
        today_counts = {slug: count for slug, count in today_rows if slug in allowed_with_terminal}

        order_columns: List[Any] = []
        if sort_key == 'name':
            order_columns.append(
                func.lower(User.fio).asc() if sort_direction == 'asc' else func.lower(User.fio).desc()
            )
        elif sort_key == 'status':
            order_columns.append(
                status_rank_expr.asc() if sort_direction == 'asc' else status_rank_expr.desc()
            )
            order_columns.append(primary_event_expr.asc())
        elif sort_key == 'activity':
            order_columns.append(
                User.last_activity.asc() if sort_direction == 'asc' else User.last_activity.desc()
            )
        else:
            order_columns.append(
                case((primary_event_expr.is_(None), 1), else_=0).asc()
            )
            order_columns.append(
                primary_event_expr.desc() if sort_direction == 'desc' else primary_event_expr.asc()
            )
            order_columns.append(User.last_activity.desc())
            order_columns.append(User.id.desc())

        list_query: Select = (
            select(User, status_case, status_rank_expr, primary_event_expr)
            .where(*conditions)
            .order_by(*order_columns)
            .offset(offset)
            .limit(per_page)
        )
        rows = await session.execute(list_query)
        records = rows.all()

        users = [row[0] for row in records]
        status_by_user = {row[0].id: row[1] for row in records}
        status_rank_by_user = {row[0].id: row[2] for row in records}
        primary_event_by_user = {row[0].id: _ensure_aware(row[3]) for row in records}

        user_ids = [user.id for user in users]
        telegram_ids = [user.telegram_id for user in users if user.telegram_id]

        stats_map: Dict[int, Tuple[int, Optional[float]]] = {}
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
                stats_map[user_id] = (int(tests_total or 0), float(avg_score) if avg_score is not None else None)

        latest_result_map: Dict[int, Optional[TestResult]] = {}
        test_results_map: Dict[int, Dict[str, Optional[TestResult]]] = defaultdict(lambda: {'TEST1': None, 'TEST2': None})
        if user_ids:
            test_rows = await session.execute(
                select(TestResult)
                .where(TestResult.user_id.in_(user_ids))
                .order_by(TestResult.user_id.asc(), TestResult.created_at.desc(), TestResult.id.desc())
            )
            for result in test_rows.scalars():
                if result.user_id not in latest_result_map:
                    latest_result_map[result.user_id] = result
                rating_key = (result.rating or '').strip().upper()
                if rating_key in {'TEST1', 'TEST2'} and test_results_map[result.user_id][rating_key] is None:
                    test_results_map[result.user_id][rating_key] = result

        messages_map: Dict[int, List[AutoMessage]] = defaultdict(list)
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

        slots_by_candidate: Dict[int, List[Slot]] = defaultdict(list)
        upcoming_slot_map: Dict[int, Optional[Slot]] = {}
        latest_slot_map: Dict[int, Optional[Slot]] = {}
        stage_map: Dict[int, str] = {}
        test2_sent_map: Dict[int, bool] = {}
        if telegram_ids:
            slot_rows = await session.execute(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(Slot.candidate_tg_id.in_(telegram_ids))
                .where(slot_pipeline_expr)
            )
            for slot in slot_rows.scalars():
                if slot.candidate_tg_id is None:
                    continue
                slot.start_utc = _ensure_aware(slot.start_utc)
                slot.test2_sent_at = _ensure_aware(getattr(slot, 'test2_sent_at', None))
                slots_by_candidate[slot.candidate_tg_id].append(slot)
                if slot.test2_sent_at is not None:
                    test2_sent_map[slot.candidate_tg_id] = True
            for tg_id, slot_list in slots_by_candidate.items():
                slot_list.sort(key=lambda s: (s.start_utc or datetime.min.replace(tzinfo=timezone.utc), s.id or 0))
                latest_slot = slot_list[-1] if slot_list else None
                upcoming_slot = next((s for s in slot_list if (s.start_utc or now) >= now), None)
                latest_slot_map[tg_id] = latest_slot
                upcoming_slot_map[tg_id] = upcoming_slot
                stage_map[tg_id] = _stage_label(latest_slot, now)

        ratings = await _distinct_ratings(session)
        cities = await _distinct_cities(session)
        analytics = await _collect_candidate_analytics(session, now)

    items: List[CandidateRow] = []
    candidate_cards: List[Dict[str, Any]] = []

    for user in users:
        tests_total, avg_score = stats_map.get(user.id, (0, None))
        candidate_messages = messages_map.get(user.telegram_id, [])
        latest_slot = latest_slot_map.get(user.telegram_id)
        upcoming_slot = upcoming_slot_map.get(user.telegram_id)
        status_slug = status_by_user.get(user.id, 'new')
        status_label = _status_label(status_slug)
        stage_value = stage_map.get(user.telegram_id, 'Без интервью')
        if status_slug and status_slug != 'new':
            stage_value = _status_label(status_slug)

        items.append(
            CandidateRow(
                user=user,
                tests_total=tests_total,
                average_score=avg_score,
                latest_result=latest_result_map.get(user.id),
                messages_total=len(candidate_messages),
                latest_message=candidate_messages[0] if candidate_messages else None,
                stage=stage_value,
                latest_slot=latest_slot,
                upcoming_slot=upcoming_slot,
                status_slug=status_slug,
                status_label=status_label,
            )
        )

        test1_result = test_results_map[user.id]['TEST1']
        test2_result = test_results_map[user.id]['TEST2']
        test2_sent = test2_sent_map.get(user.telegram_id, False)

        t1_status = 'passed' if test1_result else 'not_started'

        if test2_result:
            if TEST2_TOTAL_QUESTIONS:
                t2_passed = (test2_result.raw_score or 0) >= TEST2_MIN_CORRECT
            else:
                t2_passed = (test2_result.final_score or 0) >= 0
            t2_status_value = 'passed' if t2_passed else 'failed'
        else:
            t2_status_value = 'in_progress' if test2_sent else 'not_started'

        telemost_url, telemost_source = _resolve_telemost_url(slots_by_candidate.get(user.telegram_id, []))

        primary_dt = primary_event_by_user.get(user.id)
        if primary_dt is None and upcoming_slot and upcoming_slot.start_utc:
            primary_dt = upcoming_slot.start_utc
        if primary_dt is None and latest_slot and latest_slot.start_utc:
            primary_dt = latest_slot.start_utc

        if primary_dt is None:
            group_key = 'unscheduled'
            group_label = 'Без даты'
            group_date = None
        else:
            primary_date = primary_dt.date()
            if primary_date == today:
                group_key = 'today'
                group_label = 'Сегодня'
            elif primary_date == today + timedelta(days=1):
                group_key = 'tomorrow'
                group_label = 'Завтра'
            else:
                group_key = primary_date.isoformat()
                group_label = primary_date.strftime('%d.%m.%Y (%a)')
            group_date = primary_date

        recruiter_name = None
        recruiter_id_value = None
        if upcoming_slot and upcoming_slot.recruiter:
            recruiter_name = upcoming_slot.recruiter.name
            recruiter_id_value = upcoming_slot.recruiter.id
        elif latest_slot and latest_slot.recruiter:
            recruiter_name = latest_slot.recruiter.name
            recruiter_id_value = latest_slot.recruiter.id

        candidate_cards.append(
            {
                'id': user.id,
                'telegram_id': user.telegram_id,
                 'telegram_user_id': user.telegram_user_id or user.telegram_id,
                 'telegram_username': user.telegram_username or user.username,
                 'telegram_linked_at': user.telegram_linked_at,
                'fio': user.fio,
                'city': user.city,
                'status': {
                    'slug': status_slug,
                    'label': status_label,
                    'icon': _status_icon(status_slug),
                    'rank': status_rank_by_user.get(user.id, STATUS_ORDER.get(status_slug, 0)),
                    'tone': _status_tone(status_slug),
                },
                'tests': {
                    'test1': {
                        'status': t1_status,
                        'label': TEST_STATUS_LABELS[t1_status]['label'],
                        'icon': TEST_STATUS_LABELS[t1_status]['icon'],
                    },
                    'test2': {
                        'status': t2_status_value,
                        'label': TEST_STATUS_LABELS[t2_status_value]['label'],
                        'icon': TEST_STATUS_LABELS[t2_status_value]['icon'],
                    },
                },
                'stage': stage_value,
                'upcoming_slot': upcoming_slot,
                'latest_slot': latest_slot,
                'slots': slots_by_candidate.get(user.telegram_id, []),
                'messages_total': len(candidate_messages),
                'primary_event_at': primary_dt,
                'group': {
                    'key': group_key,
                    'label': group_label,
                    'date': group_date,
                },
                'telemost_url': telemost_url,
                'telemost_source': telemost_source,
                'recruiter': {
                    'id': recruiter_id_value,
                    'name': recruiter_name,
                } if recruiter_name else None,
            }
        )

    candidate_cards = [card for card in candidate_cards if card['status']['slug'] in allowed_with_terminal]
    items = [row for row in items if row.status_slug in allowed_with_terminal]

    list_groups: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    for card in sorted(
        candidate_cards,
        key=lambda item: (
            item['group']['date'] or date.max,
            STATUS_ORDER.get(item['status']['slug'], 0),
            item['fio'],
        ),
    ):
        group_key = card['group']['key']
        group = list_groups.setdefault(
            group_key,
            {
                'label': card['group']['label'],
                'date': card['group']['date'],
                'candidates': [],
            },
        )
        group['candidates'].append(card)

    kanban_columns: List[Dict[str, Any]] = []
    for slug in pipeline_statuses:
        meta = STATUS_DEFINITIONS.get(slug)
        if not meta:
            continue
        column_cards = [card for card in candidate_cards if card['status']['slug'] == slug]
        kanban_columns.append(
            {
                'slug': slug,
                'label': meta['label'],
                'icon': meta['icon'],
                'tone': meta.get('tone', 'info'),
                'total': status_totals.get(slug, 0),
                'candidates': column_cards,
                'droppable': slug in droppable_statuses,
            }
        )

    calendar_days: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    day_count = max(1, (calendar_end.date() - calendar_start.date()).days + 1)
    for idx in range(day_count):
        day_date = calendar_start.date() + timedelta(days=idx)
        if day_date == today:
            label = 'Сегодня'
        elif day_date == today + timedelta(days=1):
            label = 'Завтра'
        else:
            label = day_date.strftime('%d.%m.%Y (%a)')
        calendar_days[day_date.isoformat()] = {
            'date': day_date,
            'label': label,
            'events': [],
            'totals': defaultdict(int),
        }

    for card in candidate_cards:
        for slot in card['slots']:
            if slot.start_utc is None:
                continue
            start_dt = _ensure_aware(slot.start_utc)
            if start_dt < calendar_start or start_dt > calendar_end:
                continue
            day_key = start_dt.date().isoformat()
            bucket = calendar_days.get(day_key)
            if bucket is None:
                continue
            bucket['events'].append(
                {
                    'candidate': card,
                    'slot': slot,
                    'status': card['status'],
                    'start': start_dt,
                }
            )
            bucket['totals'][card['status']['slug']] += 1

    for info in calendar_days.values():
        info['totals'] = dict(info['totals'])

    upcoming_preview: List[Dict[str, Any]] = []
    for day in calendar_days.values():
        if not day['events']:
            continue
        for event in day['events']:
            upcoming_preview.append(
                {
                    'candidate': event['candidate'],
                    'slot': event['slot'],
                    'status': event['status'],
                    'start': event['start'],
                }
            )
            if len(upcoming_preview) >= 5:
                break
        if len(upcoming_preview) >= 5:
            break

    table_rows: List[Dict[str, Any]] = []
    for card in candidate_cards:
        upcoming_slot = card.get('upcoming_slot')
        latest_slot = card.get('latest_slot')
        intro_slot = upcoming_slot or latest_slot
        row: Dict[str, Any] = {
            'candidate': card,
            'upcoming_slot': upcoming_slot,
            'latest_slot': latest_slot,
        }
        if pipeline_slug == 'intro_day':
            tz_name = (
                getattr(intro_slot, 'candidate_tz', None)
                or getattr(intro_slot, 'tz_name', None)
                or DEFAULT_TZ
            )
            row['intro_day'] = {
                'slot': intro_slot,
                'status': card.get('status'),
                'city': card.get('city'),
                'address': getattr(intro_slot, 'intro_address', None) if intro_slot else None,
                'contact': getattr(intro_slot, 'intro_contact', None) if intro_slot else None,
                'tz_name': tz_name,
                'recruiter': card.get('recruiter'),
            }
        table_rows.append(row)

    today_summary = {
        'total': sum(today_counts.values()),
        'by_status': today_counts,
    }

    return {
        'items': items,
        'total': total,
        'page': page,
        'pages_total': pages_total,
        'per_page': per_page,
        'ratings': ratings,
        'cities': cities,
        'analytics': analytics,
        'filters': {
            'search': search or '',
            'city': city or '',
            'is_active': is_active,
            'rating': rating or '',
            'has_tests': has_tests,
            'has_messages': has_messages,
            'stage': stage_value,
            'statuses': list(normalized_statuses),
            'recruiter_id': recruiter_id,
            'city_ids': list(city_ids or []),
            'date_from': range_start_utc,
            'date_to': range_end_utc,
            'test1_status': test1_status,
            'test2_status': test2_status,
            'sort': sort_key,
            'sort_dir': sort_direction,
            'pipeline': pipeline_slug,
        },
        'views': {
            'list': list_groups,
            'kanban': {
                'columns': kanban_columns,
                'status_totals': status_totals,
                'stage_totals': stage_totals,
            },
            'calendar': {
                'start': calendar_start,
                'end': calendar_end,
                'days': list(calendar_days.values()),
            },
            'table': {
                'rows': table_rows,
            },
            'candidates': candidate_cards,
        },
        'summary': {
            'status_totals': stage_totals,
            'raw_status_totals': status_totals,
            'funnel': funnel_summary,
            'today': today_summary,
            'upcoming': upcoming_preview,
        },
        'pipeline': pipeline_slug,
        'pipeline_meta': {
            'slug': pipeline_slug,
            'label': pipeline_config['label'],
        },
        'pipeline_options': [
            {'slug': slug, 'label': cfg['label']}
            for slug, cfg in PIPELINE_DEFINITIONS.items()
        ],
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
        city_rows = await session.execute(
            select(City.id, City.name).order_by(City.name.asc())
        )
        city_choices = [
            {"id": city_id, "name": name}
            for city_id, name in city_rows
            if name
        ]
        cities = [entry["name"] for entry in city_choices]
        ratings = await _distinct_ratings(session)
        recruiter_rows = await session.execute(
            select(Recruiter)
            .where(Recruiter.active.is_(True))
            .order_by(Recruiter.name.asc())
        )
        recruiters = [
            {
                "id": recruiter.id,
                "name": recruiter.name,
                "tz": recruiter.tz,
            }
            for recruiter in recruiter_rows.scalars()
        ]

    status_options = [
        {
            "slug": slug,
            "label": meta["label"],
            "icon": meta["icon"],
            "tone": meta.get("tone", "info"),
        }
        for slug, meta in STATUS_DEFINITIONS.items()
    ]
    test_status_options = [
        {"slug": key, "label": value["label"], "icon": value["icon"]}
        for key, value in TEST_STATUS_LABELS.items()
    ]
    sort_options = [
        {"value": "event", "label": "По ближайшему событию"},
        {"value": "activity", "label": "По активности"},
        {"value": "name", "label": "По имени"},
        {"value": "status", "label": "По статусу"},
    ]
    view_options = [
        {"value": "list", "label": "Список"},
        {"value": "kanban", "label": "Канбан"},
        {"value": "calendar", "label": "Календарь"},
        {"value": "table", "label": "Таблица"},
    ]

    return {
        "cities": cities,
        "city_choices": city_choices,
        "ratings": ratings,
        "statuses": status_options,
        "recruiters": recruiters,
        "test_statuses": test_status_options,
        "sort_options": sort_options,
        "view_options": view_options,
    }


async def update_candidate_status(
    candidate_id: int,
    status_slug: str,
    *,
    bot_service: Optional["BotService"] = None,
) -> Tuple[bool, str, Optional[str], Optional[object]]:
    """Update candidate workflow status via slot updates or outcomes."""

    normalized = (status_slug or "").strip().lower()
    slot_status_map = {
        "awaiting_confirmation": SlotStatus.PENDING,
        "assigned": SlotStatus.BOOKED,
        "confirmed": SlotStatus.CONFIRMED_BY_CANDIDATE,
    }
    outcome_map = {
        "accepted": "success",
        "rejected": "reject",
    }
    legacy_statuses = set(slot_status_map.keys()) | set(outcome_map.keys())

    if normalized not in STATUS_DEFINITIONS and normalized not in legacy_statuses:
        return False, "Некорректный статус", None, None
    if normalized in legacy_statuses and normalized not in STATUS_DEFINITIONS:
        logger.warning("Legacy candidate status received", extra={"status": normalized, "candidate_id": candidate_id})

    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            return False, "Кандидат не найден", None, None
        if user.telegram_id is None:
            return False, "Для кандидата не указан Telegram ID", None, None

        slot_query = (
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.candidate_tg_id == user.telegram_id)
            .order_by(Slot.start_utc.asc(), Slot.id.asc())
        )
        slot_rows = await session.execute(slot_query)
        slots = list(slot_rows.scalars())

        needs_slot = normalized in slot_status_map or normalized in outcome_map
        if needs_slot and not slots:
            return False, "Для кандидата не найден подходящий слот", None, None

        now = datetime.now(timezone.utc)
        upcoming_slot = None
        for slot in slots:
            slot.start_utc = _ensure_aware(slot.start_utc)
            if upcoming_slot is None and slot.start_utc and slot.start_utc >= now:
                upcoming_slot = slot
        target_slot = upcoming_slot or (slots[-1] if slots else None)

        if normalized in outcome_map:
            if target_slot is None:
                return False, "Для кандидата не найден подходящий слот", None, None
            from backend.apps.admin_ui.services.slots import set_slot_outcome

            ok, message, stored, dispatch = await set_slot_outcome(
                target_slot.id,
                outcome_map[normalized],
                bot_service=bot_service,
            )
            return ok, message or "", normalized, dispatch

        if normalized in slot_status_map:
            if target_slot is None:
                return False, "Для кандидата не найден подходящий слот", None, None

            if normalized == "assigned":
                result = await approve_slot_and_notify(target_slot.id, force_notify=True)
                success_statuses = {"approved", "already", "notify_failed"}
                ok = result.status in success_statuses
                message = result.message or "Не удалось согласовать слот."
                if not ok:
                    return False, message, normalized, None
                return True, message, normalized, None

            target_slot.status = slot_status_map[normalized]
            if normalized != "awaiting_confirmation":
                target_slot.interview_outcome = None
            await session.commit()
            return True, "Статус обновлён", normalized, None

        if normalized in STATUS_DEFINITIONS:
            try:
                user.candidate_status = CandidateStatus(normalized)
            except ValueError:
                user.candidate_status = None
            user.status_changed_at = datetime.now(timezone.utc)
            await session.commit()
            return True, "Статус обновлён", normalized, None

    return False, "Этот статус нельзя установить вручную", None, None


async def get_candidate_detail(user_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return None

        interview_note = await _load_interview_note(session, user_id)

        test_results = (
            await session.execute(
                select(TestResult)
                .where(TestResult.user_id == user_id)
                .order_by(TestResult.created_at.desc(), TestResult.id.desc())
            )
        ).scalars().all()

        test_ids = [result.id for result in test_results]
        answers_by_result: Dict[int, List[QuestionAnswer]] = defaultdict(list)
        answers_map: Dict[int, Dict[str, int]] = {}
        if test_ids:
            answer_rows = await session.execute(
                select(QuestionAnswer)
                .where(QuestionAnswer.test_result_id.in_(test_ids))
                .order_by(QuestionAnswer.test_result_id.asc(), QuestionAnswer.question_index.asc())
            )
            for answer in answer_rows.scalars():
                answers_by_result[answer.test_result_id].append(answer)

            for test_id, answer_items in answers_by_result.items():
                answers_map[test_id] = {
                    "questions_total": len(answer_items),
                    "questions_correct": sum(1 for item in answer_items if item.is_correct),
                    "questions_overtime": sum(1 for item in answer_items if item.overtime),
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
            slot.test2_sent_at = _ensure_aware(getattr(slot, "test2_sent_at", None))
        upcoming_slot = next((slot for slot in reversed(slots) if slot.start_utc and slot.start_utc >= now), None)

        # Use candidate_status field for stage label
        candidate_status = getattr(user, "candidate_status", None)
        candidate_status_slug = (
            candidate_status.value
            if isinstance(candidate_status, CandidateStatus)
            else (candidate_status or None)
        )
        if candidate_status_slug:
            stage = _status_label(candidate_status_slug)
        else:
            # Fallback to old logic if no candidate_status
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
            rating_raw = (result.rating or "").strip().upper()
            test_slug = None
            rating_label = result.rating
            if rating_raw == "TEST1":
                test_slug = "test1"
                rating_label = "Тест 1"
            elif rating_raw == "TEST2":
                test_slug = "test2"
                rating_label = "Тест 2"
            timeline.append(
                {
                    "kind": "test",
                    "dt": _ensure_aware(result.created_at),
                    "score": result.final_score,
                    "rating": rating_label,
                    "test_key": test_slug,
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

        test_sections_map = _build_test_sections(test_results, answers_by_result, slots)
        if "test1" in test_sections_map:
            test_sections_map["test1"]["report_url"] = (
                f"/candidates/{user.id}/reports/test1" if getattr(user, "test1_report_url", None) else None
            )
        if "test2" in test_sections_map:
            test_sections_map["test2"]["report_url"] = (
                f"/candidates/{user.id}/reports/test2" if getattr(user, "test2_report_url", None) else None
            )
    test_sections_list = list(test_sections_map.values())

    telemost_url, telemost_source = _resolve_telemost_url(slots)

    # Check if candidate needs intro day
    has_intro_day_slot = any(slot.purpose == "intro_day" for slot in slots)
    status_requires_intro_day = (
        candidate_status in STATUSES_PENDING_INTRO_DAY if candidate_status else False
    )
    test2_passed = _has_passed_test2(test_results)
    needs_intro_day = (status_requires_intro_day or test2_passed) and not has_intro_day_slot

    return {
        "user": user,
        "tests": test_results,
        "answers_map": answers_map,
        "test_sections": test_sections_list,
        "test_sections_map": test_sections_map,
        "messages": messages,
        "slots": slots,
        "upcoming_slot": upcoming_slot,
        "stage": stage,
        "timeline": timeline,
        "needs_intro_day": needs_intro_day,
        "has_intro_day_slot": has_intro_day_slot,
        "can_schedule_intro_day": needs_intro_day,
        "candidate_status_slug": candidate_status_slug,
        "test2_passed": test2_passed,
        "stats": {
            "tests_total": int(tests_total or 0),
            "average_score": float(avg_score) if avg_score is not None else None,
        },
        "telemost_url": telemost_url,
        "telemost_source": telemost_source,
        "interview_form_sections": INTERVIEW_FORM_SECTIONS,
        "interview_recommendation_choices": INTERVIEW_RECOMMENDATION_CHOICES,
        "interview_recommendation_lookup": INTERVIEW_RECOMMENDATION_LOOKUP,
        "interview_notes": _serialize_interview_note(interview_note),
        "chat_templates": get_chat_templates(),
    }


async def save_interview_notes(
    user_id: int,
    *,
    interviewer_name: Optional[str],
    data: Dict[str, Any],
) -> bool:
    """Create or update interview notes for a candidate."""
    sanitized_data = {
        key: value
        for key, value in data.items()
    }
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False

        try:
            note = (
                await session.execute(
                    select(InterviewNote).where(InterviewNote.user_id == user_id)
                )
            ).scalar_one_or_none()
        except (OperationalError, ProgrammingError) as exc:
            await session.rollback()
            logger.warning(
                "interview.notes.disabled",
                extra={"reason": str(exc), "user_id": user_id},
            )
            return False

        now = datetime.now(timezone.utc)
        display_name = (interviewer_name or "").strip() or None

        if note:
            note.interviewer_name = display_name
            note.data = sanitized_data
            note.updated_at = now
        else:
            note = InterviewNote(
                user_id=user_id,
                interviewer_name=display_name,
                data=sanitized_data,
                created_at=now,
                updated_at=now,
            )
            session.add(note)

        try:
            await session.commit()
        except (OperationalError, ProgrammingError) as exc:
            await session.rollback()
            logger.warning(
                "interview.notes.commit_failed",
                extra={"reason": str(exc), "user_id": user_id},
            )
            return False
        return True


async def _load_interview_note(session, user_id: int) -> Optional[InterviewNote]:
    try:
        return (
            await session.execute(
                select(InterviewNote).where(InterviewNote.user_id == user_id)
            )
        ).scalar_one_or_none()
    except (OperationalError, ProgrammingError) as exc:
        logger.warning(
            "interview.notes.unavailable",
            extra={"reason": str(exc), "user_id": user_id},
        )
        return None


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


async def delete_all_candidates() -> int:
    """Delete all candidate profiles and release assigned slots."""
    async with async_session() as session:
        telegram_ids = await session.scalars(
            select(User.telegram_id).where(User.telegram_id.is_not(None))
        )
        tg_list = [value for value in telegram_ids if value]
        if tg_list:
            await session.execute(
                Slot.__table__.update()
                .where(Slot.candidate_tg_id.in_(tg_list))
                .values(
                    candidate_tg_id=None,
                    candidate_fio=None,
                    candidate_tz=None,
                    candidate_city_id=None,
                    status=SlotStatus.FREE,
                )
            )

        delete_result = await session.execute(delete(User))
        await session.commit()
        return delete_result.rowcount or 0


async def api_candidate_detail_payload(candidate_id: int) -> Optional[Dict[str, object]]:
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return None
    user: User = detail["user"]
    sections_map = detail.get("test_sections_map", {})

    def _iso(value: Optional[datetime]) -> Optional[str]:
        if not value:
            return None
        return _ensure_aware(value).isoformat()

    test_results_payload: Dict[str, Dict[str, Any]] = {}
    for slug, section in sections_map.items():
        details_block = section.get("details", {})
        stats_block = details_block.get("stats", {})
        stats_payload = {}
        for key, value in stats_block.items():
            if isinstance(value, datetime):
                stats_payload[key] = _iso(value)
            else:
                stats_payload[key] = value
        history_payload = []
        for item in section.get("history", []):
            history_payload.append(
                {
                    "id": item.get("id"),
                    "completed_at": _iso(item.get("completed_at")),
                    "raw_score": item.get("raw_score"),
                    "final_score": item.get("final_score"),
                }
            )
        test_results_payload[slug] = {
            "status": section.get("status"),
            "status_label": section.get("status_label"),
            "summary": section.get("summary"),
            "completed_at": _iso(section.get("completed_at")),
            "pending_since": _iso(section.get("pending_since")),
            "details": {
                "questions": details_block.get("questions", []),
                "stats": stats_payload,
            },
            "history": history_payload,
            "report_url": section.get("report_url"),
        }

    return {
        "id": user.id,
        "fio": user.fio,
        "city": user.city,
        "telegram_id": user.telegram_id,
        "is_active": user.is_active,
        "test1_report_url": f"/candidates/{user.id}/reports/test1"
        if getattr(user, "test1_report_url", None)
        else None,
        "test2_report_url": f"/candidates/{user.id}/reports/test2"
        if getattr(user, "test2_report_url", None)
        else None,
        "test_results": test_results_payload,
        "telemost_url": detail.get("telemost_url"),
        "telemost_source": detail.get("telemost_source"),
    }


__all__ = [
    "CandidateRow",
    "list_candidates",
    "candidate_filter_options",
    "get_candidate_detail",
    "upsert_candidate",
    "toggle_candidate_activity",
    "update_candidate",
    "delete_candidate",
    "delete_all_candidates",
    "api_candidate_detail_payload",
    "PIPELINE_DEFINITIONS",
    "DEFAULT_PIPELINE",
]
