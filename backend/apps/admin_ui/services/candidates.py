from __future__ import annotations

import logging
import math
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import String, cast, delete, exists, func, literal, literal_column, or_, select, false, and_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select, case

from backend.apps.admin_ui.utils import paginate
from backend.apps.admin_ui.services.bot_service import get_bot_service
from backend.apps.admin_ui.services.chat import get_chat_templates
from backend.apps.admin_ui.timezones import DEFAULT_TZ
from backend.apps.bot.config import PASS_THRESHOLD, TEST2_QUESTIONS
from backend.apps.bot.services import approve_slot_and_notify, cancel_slot_reminders
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.apps.admin_ui.security import principal_ctx, Principal
from backend.domain import analytics
from backend.domain.candidates.models import (
    AutoMessage,
    InterviewNote,
    QuestionAnswer,
    TestResult,
    User,
)
from backend.domain.candidates.workflow import WorkflowStatus
from backend.domain.candidates.status import (
    CandidateStatus,
    STATUS_TRANSITIONS,
    STATUS_CATEGORIES,
    STATUS_COLORS,
    StatusCategory,
    get_next_statuses,
    get_status_color,
    is_terminal_status,
)
from backend.domain.candidate_status_service import CandidateStatusService
from backend.domain.candidates.status_service import FUNNEL_STATUS_EVENTS
from backend.domain.candidates.services import create_candidate_invite_token
from backend.domain.candidates.actions import get_candidate_actions
from backend.domain.candidates.workflow import (
    CandidateWorkflowService,
    WorkflowStatus,
)
from backend.domain.models import City, Recruiter, Slot, SlotStatus, recruiter_city_association
from backend.domain.repositories import find_city_by_plain_name

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


_candidate_status_service = CandidateStatusService()
_workflow_service = CandidateWorkflowService()

WORKFLOW_STATUS_LABELS: Dict[WorkflowStatus, str] = {
    WorkflowStatus.WAITING_FOR_SLOT: "Ждёт назначения слота",
    WorkflowStatus.INTERVIEW_SCHEDULED: "На согласовании",
    WorkflowStatus.INTERVIEW_CONFIRMED: "Собеседование подтверждено",
    WorkflowStatus.INTERVIEW_COMPLETED: "Собеседование проведено",
    WorkflowStatus.TEST_SENT: "Отправлен тест",
    WorkflowStatus.ONBOARDING_DAY_SCHEDULED: "Назначен ознакомительный день",
    WorkflowStatus.ONBOARDING_DAY_CONFIRMED: "ОД подтверждён",
    WorkflowStatus.REJECTED: "Отклонён",
}

WORKFLOW_STATUS_COLORS: Dict[WorkflowStatus, str] = {
    WorkflowStatus.WAITING_FOR_SLOT: "warning",
    WorkflowStatus.INTERVIEW_SCHEDULED: "primary",
    WorkflowStatus.INTERVIEW_CONFIRMED: "primary",
    WorkflowStatus.INTERVIEW_COMPLETED: "info",
    WorkflowStatus.TEST_SENT: "primary",
    WorkflowStatus.ONBOARDING_DAY_SCHEDULED: "primary",
    WorkflowStatus.ONBOARDING_DAY_CONFIRMED: "success",
    WorkflowStatus.REJECTED: "danger",
}


INTERVIEW_SCRIPT_STEPS: List[Dict[str, Any]] = [
    {
        "id": "company_intro",
        "label": "Знакомство с компанией",
        "duration_min": 5,
        "notes": "Кратко рассказать о продукте и формате работы.",
    },
    {
        "id": "candidate_story",
        "label": "Опыт кандидата",
        "duration_min": 10,
        "notes": "Выяснить релевантный опыт, роль, задачи и инструменты.",
    },
    {
        "id": "expectations",
        "label": "Ожидания и мотивация",
        "duration_min": 7,
        "notes": "Понять, что важно кандидату и какие условия критичны.",
    },
    {
        "id": "case_question",
        "label": "Мини-кейс / проверка навыков",
        "duration_min": 8,
        "notes": "1–2 практических вопроса по процессу рекрутинга и коммуникации.",
    },
    {
        "id": "next_steps",
        "label": "Следующие шаги",
        "duration_min": 3,
        "notes": "Озвучить дальнейшие этапы и договориться о сроках обратной связи.",
    },
]

INTRO_DAY_MESSAGE_TEMPLATE: str = (
    "Привет! Напоминаем про ознакомительный день. Приходите вовремя, "
    "возьмите документ и задайте вопросы — мы на связи 🙂"
)

DEFAULT_INTRO_DAY_INVITATION_TEMPLATE: str = (
    "Здравствуйте, [Имя]! Приглашаем вас на ознакомительный день [Дата] в [Время]. "
    "Пожалуйста, возьмите с собой документ, удостоверяющий личность. Ждём вас!"
)


STATUS_DEFINITIONS: "OrderedDict[str, Dict[str, str]]" = OrderedDict(
    [
        # Fallback for candidates without статус
        ("new", {"label": "Новые (без статуса)", "icon": "🆕", "tone": "muted"}),
        # Lead statuses
        ("lead", {"label": "Лид (новый контакт)", "icon": "📇", "tone": "muted"}),
        ("contacted", {"label": "Связались (телефон)", "icon": "📞", "tone": "info"}),
        ("invited", {"label": "Приглашен в бота", "icon": "✉️", "tone": "primary"}),
        # Active statuses
        ("test1_completed", {"label": "Прошел тестирование", "icon": "📝", "tone": "info"}),
        ("waiting_slot", {"label": "Ждет назначения слота", "icon": "⏳", "tone": "warning"}),
        ("stalled_waiting_slot", {"label": "Долго ждет слота (>24ч)", "icon": "⚠️", "tone": "danger"}),
        ("slot_pending", {"label": "Выбрал время, ждет подтверждения", "icon": "🕐", "tone": "warning"}),
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

CANDIDATE_ACTIONS: Dict[CandidateStatus, List[Dict[str, Any]]] = {
    CandidateStatus.LEAD: [
        {"label": "Связаться", "target_status": CandidateStatus.CONTACTED},
        {"label": "Пригласить в бота", "target_status": CandidateStatus.INVITED},
        {"label": "Отметить прохождение Тест 1", "target_status": CandidateStatus.TEST1_COMPLETED},
    ],
    CandidateStatus.CONTACTED: [
        {"label": "Пригласить в бота", "target_status": CandidateStatus.INVITED},
        {"label": "Отметить прохождение Тест 1", "target_status": CandidateStatus.TEST1_COMPLETED},
    ],
    CandidateStatus.INVITED: [
        {"label": "Отметить прохождение Тест 1", "target_status": CandidateStatus.TEST1_COMPLETED},
    ],
    CandidateStatus.TEST1_COMPLETED: [
        {
            "label": "Поставить в ожидание слота",
            "target_status": CandidateStatus.WAITING_SLOT,
        },
        {
            "label": "Назначить собеседование",
            "target_status": CandidateStatus.INTERVIEW_SCHEDULED,
        },
    ],
    CandidateStatus.WAITING_SLOT: [
        {
            "label": "Назначить собеседование",
            "target_status": CandidateStatus.INTERVIEW_SCHEDULED,
        },
    ],
    CandidateStatus.STALLED_WAITING_SLOT: [
        {
            "label": "Назначить собеседование",
            "target_status": CandidateStatus.INTERVIEW_SCHEDULED,
        },
    ],
    CandidateStatus.INTERVIEW_SCHEDULED: [
        {
            "label": "Подтвердить участие",
            "target_status": CandidateStatus.INTERVIEW_CONFIRMED,
        },
        {
            "label": "Отправить Тест 2",
            "target_status": CandidateStatus.TEST2_SENT,
        },
        {
            "label": "Отклонить кандидата",
            "target_status": CandidateStatus.INTERVIEW_DECLINED,
            "danger": True,
        },
    ],
    CandidateStatus.INTERVIEW_CONFIRMED: [
        {
            "label": "Прошел собеседование (отправить Тест 2)",
            "target_status": CandidateStatus.TEST2_SENT,
            "variant": "primary",
        },
        {
            "label": "Отклонить после собеседования",
            "target_status": CandidateStatus.INTERVIEW_DECLINED,
            "danger": True,
            "confirmation": "Подтвердить отказ после собеседования?",
        },
    ],
    CandidateStatus.TEST2_SENT: [
        {
            "label": "Отметить Тест 2 пройден",
            "target_status": CandidateStatus.TEST2_COMPLETED,
        },
        {
            "label": "Отметить Тест 2 не пройден",
            "target_status": CandidateStatus.TEST2_FAILED,
            "danger": True,
        },
    ],
    CandidateStatus.TEST2_COMPLETED: [
        {
            "label": "Назначить ознакомительный день",
            "target_status": CandidateStatus.INTRO_DAY_SCHEDULED,
        },
    ],
    CandidateStatus.INTRO_DAY_SCHEDULED: [
        {
            "label": "Предварительно подтвердить",
            "target_status": CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
        },
        {
            "label": "Отказ на этапе ОД",
            "target_status": CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
            "danger": True,
        },
    ],
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY: [
        {
            "label": "Подтвердить в день ОД",
            "target_status": CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
        },
        {
            "label": "Отказ в день ОД",
            "target_status": CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
            "danger": True,
        },
        {
            "label": "Закрепить на обучение",
            "target_status": CandidateStatus.HIRED,
        },
        {
            "label": "Не закреплять",
            "target_status": CandidateStatus.NOT_HIRED,
            "danger": True,
        },
    ],
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF: [
        {
            "label": "Закрепить на обучение",
            "target_status": CandidateStatus.HIRED,
        },
        {
            "label": "Не закреплять",
            "target_status": CandidateStatus.NOT_HIRED,
            "danger": True,
        },
    ],
}

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
        "slug": "lead",
        "label": "Лиды",
        "icon": "📇",
        "tone": "muted",
        "statuses": ["lead", "contacted", "invited"],
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
    "lead",
    "contacted",
    "invited",
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


def get_candidate_actions_for_status(status_slug: Optional[str]) -> List[Dict[str, Any]]:
    """Return UI actions allowed for the given status, filtered by valid transitions."""
    if not status_slug:
        return []
    try:
        status = CandidateStatus(status_slug)
    except ValueError:
        return []

    allowed_next = set(STATUS_TRANSITIONS.get(status, []))
    actions: List[Dict[str, Any]] = []

    for action in CANDIDATE_ACTIONS.get(status, []):
        target = action.get("target_status")
        if not isinstance(target, CandidateStatus):
            continue
        if target not in allowed_next:
            continue
        actions.append(
            {
                "label": action.get("label", target.value),
                "target_status": target.value,
                "danger": bool(action.get("danger")),
            }
        )
    return actions

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
STATUSES_RELEASE_INTRO_DAY_SLOTS: Set[CandidateStatus] = {
    CandidateStatus.TEST2_FAILED,
    CandidateStatus.INTERVIEW_DECLINED,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
    CandidateStatus.NOT_HIRED,
}
STATUSES_ARCHIVE_ON_DECLINE: Set[CandidateStatus] = {
    CandidateStatus.INTERVIEW_DECLINED,
    CandidateStatus.TEST2_FAILED,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
    CandidateStatus.NOT_HIRED,
}

# Mapping legacy candidate_status to new workflow statuses
LEGACY_TO_WORKFLOW: Dict[str, WorkflowStatus] = {
    CandidateStatus.WAITING_SLOT.value: WorkflowStatus.WAITING_FOR_SLOT,
    CandidateStatus.STALLED_WAITING_SLOT.value: WorkflowStatus.WAITING_FOR_SLOT,
    CandidateStatus.INTERVIEW_SCHEDULED.value: WorkflowStatus.INTERVIEW_SCHEDULED,
    CandidateStatus.INTERVIEW_CONFIRMED.value: WorkflowStatus.INTERVIEW_CONFIRMED,
    CandidateStatus.INTERVIEW_DECLINED.value: WorkflowStatus.REJECTED,
    CandidateStatus.TEST2_SENT.value: WorkflowStatus.TEST_SENT,
    CandidateStatus.TEST2_COMPLETED.value: WorkflowStatus.ONBOARDING_DAY_SCHEDULED,
    CandidateStatus.TEST2_FAILED.value: WorkflowStatus.REJECTED,
    CandidateStatus.INTRO_DAY_SCHEDULED.value: WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY.value: WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION.value: WorkflowStatus.REJECTED,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF.value: WorkflowStatus.REJECTED,
    CandidateStatus.HIRED.value: WorkflowStatus.ONBOARDING_DAY_CONFIRMED,
    CandidateStatus.NOT_HIRED.value: WorkflowStatus.REJECTED,
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


# Pipeline stage definitions for Status Center UI
PIPELINE_STAGES = [
    {
        "key": "lead",
        "label": "Лид",
        "statuses": {StatusCategory.LEAD},
    },
    {
        "key": "test",
        "label": "Тест",
        "statuses": {StatusCategory.TESTING},
    },
    {
        "key": "interview",
        "label": "Собес",
        "statuses": {StatusCategory.INTERVIEW},
    },
    {
        "key": "intro_day",
        "label": "Озн. день",
        "statuses": {StatusCategory.INTRO_DAY},
    },
    {
        "key": "outcome",
        "label": "Итог",
        "statuses": {StatusCategory.HIRED, StatusCategory.DECLINED},
    },
]


def _build_pipeline_stages(
    current_status: Optional[CandidateStatus],
) -> List[Dict[str, Any]]:
    """Build pipeline stages with active/passed/declined state for Status Center UI.

    Pipeline stages map to recruiting funnel:
    - Lead (0): LEAD, CONTACTED, INVITED
    - Test (1): TEST1_COMPLETED, WAITING_SLOT, STALLED_WAITING_SLOT, TEST2_SENT, TEST2_COMPLETED
    - Interview (2): INTERVIEW_SCHEDULED, INTERVIEW_CONFIRMED
    - Intro Day (3): INTRO_DAY_*
    - Outcome (4): HIRED, NOT_HIRED

    Note: Test2 happens AFTER interview, so interview should be marked passed for Test2 statuses.
    """
    if current_status is None:
        # No status - all stages pending
        return [
            {"key": s["key"], "label": s["label"], "state": "pending"}
            for s in PIPELINE_STAGES
        ]

    current_category = STATUS_CATEGORIES.get(current_status, StatusCategory.TESTING)
    is_declined = current_category == StatusCategory.DECLINED

    # Map each status to its pipeline stage index
    # This is more accurate than using categories since Test2 is after Interview
    STATUS_TO_STAGE: Dict[CandidateStatus, int] = {
        CandidateStatus.LEAD: 0,
        CandidateStatus.CONTACTED: 0,
        CandidateStatus.INVITED: 0,
        CandidateStatus.TEST1_COMPLETED: 1,
        CandidateStatus.WAITING_SLOT: 1,
        CandidateStatus.STALLED_WAITING_SLOT: 1,
        CandidateStatus.INTERVIEW_SCHEDULED: 2,
        CandidateStatus.INTERVIEW_CONFIRMED: 2,
        CandidateStatus.INTERVIEW_DECLINED: 2,
        CandidateStatus.TEST2_SENT: 1,  # Test2 shows at test stage but interview passed
        CandidateStatus.TEST2_COMPLETED: 1,
        CandidateStatus.TEST2_FAILED: 1,
        CandidateStatus.INTRO_DAY_SCHEDULED: 3,
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY: 3,
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION: 3,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF: 3,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: 3,
        CandidateStatus.HIRED: 4,
        CandidateStatus.NOT_HIRED: 4,
    }

    # Statuses that occur AFTER interview (interview should show as passed)
    POST_INTERVIEW_STATUSES = {
        CandidateStatus.TEST2_SENT,
        CandidateStatus.TEST2_COMPLETED,
        CandidateStatus.TEST2_FAILED,
        CandidateStatus.INTRO_DAY_SCHEDULED,
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
        CandidateStatus.INTRO_DAY_DECLINED_INVITATION,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
        CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
        CandidateStatus.HIRED,
        CandidateStatus.NOT_HIRED,
    }

    current_stage_idx = STATUS_TO_STAGE.get(current_status, 0)
    is_post_interview = current_status in POST_INTERVIEW_STATUSES

    result = []
    for idx, stage in enumerate(PIPELINE_STAGES):
        if is_declined:
            # For declined statuses
            if is_post_interview and idx == 2:
                # Interview was passed before decline (e.g., TEST2_FAILED)
                state = "passed"
            elif idx < current_stage_idx:
                state = "passed"
            elif idx == current_stage_idx:
                state = "declined"
            else:
                state = "pending"
        elif current_status == CandidateStatus.HIRED:
            # Hired - all stages passed except outcome which is active
            state = "passed" if idx < 4 else "active"
        elif idx == current_stage_idx:
            state = "active"
        elif idx < current_stage_idx:
            state = "passed"
        elif is_post_interview and idx == 2:
            # Interview was passed (for Test2/IntroDay statuses)
            state = "passed"
        else:
            state = "pending"

        result.append({
            "key": stage["key"],
            "label": stage["label"],
            "state": state,
        })

    return result


def _map_to_workflow_status(user: User) -> WorkflowStatus:
    """Derive workflow status from explicit workflow_status or legacy candidate_status."""
    raw_workflow = getattr(user, "workflow_status", None)
    if raw_workflow:
        try:
            return WorkflowStatus(raw_workflow)
        except Exception:
            logging.warning(
                "candidates.invalid_workflow_status",
                extra={"user_id": getattr(user, "id", None), "raw_value": raw_workflow},
            )
    legacy = getattr(user, "candidate_status", None)
    if isinstance(legacy, CandidateStatus):
        mapped = LEGACY_TO_WORKFLOW.get(legacy.value)
        if mapped:
            return mapped
    elif isinstance(legacy, str) and legacy:
        mapped = LEGACY_TO_WORKFLOW.get(legacy.lower())
        if mapped:
            return mapped
    return WorkflowStatus.WAITING_FOR_SLOT


def _workflow_actions_ui(candidate_id: int, allowed: List[str]) -> List[Dict[str, Any]]:
    definitions: Dict[str, Dict[str, str]] = {
        # Для ожидания слота: ведём сразу на экран назначения
        "assign-slot": {
            "label": "Согласовать слот",
            "variant": "primary",
            "method": "GET",
            "url": f"/candidates/{candidate_id}/schedule-slot",
        },
        "confirm-interview": {"label": "Согласовать интервью", "variant": "primary"},
        "complete-interview": {"label": "Завершить интервью", "variant": "secondary"},
        "send-test": {"label": "Отправить тест", "variant": "primary"},
        "schedule-onboarding": {"label": "Назначить ОД", "variant": "primary"},
        "confirm-onboarding": {"label": "Подтвердить ОД", "variant": "secondary"},
        "reject": {"label": "Отказать", "variant": "danger", "confirmation": "Отклонить кандидата?"},
    }
    actions: List[Dict[str, Any]] = []
    for key in allowed:
        meta = definitions.get(key, {"label": key, "variant": "secondary"})
        method = meta.get("method", "POST")
        url_pattern = meta.get("url") or f"/candidates/{candidate_id}/actions/{key}"
        actions.append(
            {
                "key": key,
                "label": meta["label"],
                "url_pattern": url_pattern,
                "variant": meta.get("variant", "secondary"),
                "method": method,
                "danger": meta.get("variant") == "danger",
                "confirmation": meta.get("confirmation"),
                "kind": "workflow",
            }
        )
    return actions


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
            "source": None,
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
            section["source"] = (latest.source or "bot").lower() if latest.source else "bot"
            section["history"] = [
                {
                    "id": res.id,
                    "completed_at": _ensure_aware(res.created_at),
                    "raw_score": res.raw_score,
                    "final_score": res.final_score,
                    "source": (res.source or "bot").lower() if res.source else "bot",
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
    principal: Optional[Principal] = None,
) -> Dict[str, object]:
    principal = principal or principal_ctx.get()
    if principal is None:
        from backend.core.settings import get_settings
        settings = get_settings()
        if settings.environment != "production":
            principal = Principal(type="admin", id=-1)
        else:
            raise RuntimeError("principal is required for list_candidates")

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
    terminal_statuses = {"hired", "not_hired"}
    if is_intro_pipeline:
        pipeline_statuses = [slug for slug in pipeline_statuses if slug not in terminal_statuses]
        allowed_with_terminal -= terminal_statuses

    now = datetime.now(timezone.utc)
    today = now.date()

    normalized_calendar_mode = "day" if calendar_mode else None

    user_specified_start = date_from is not None
    user_specified_end = date_to is not None

    calendar_start: Optional[datetime] = None
    calendar_end: Optional[datetime] = None

    range_start_utc: Optional[datetime] = _ensure_aware(date_from)
    range_end_utc: Optional[datetime] = _ensure_aware(date_to)
    if range_start_utc is not None:
        range_start_utc = range_start_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_end_utc is not None:
        range_end_utc = range_end_utc.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Если пользователь не задавал даты, не ограничиваем выборку по времени,
    # иначе кандидат с назначенным собеседованием может пропасть.
    if not user_specified_start and not user_specified_end:
        normalized_calendar_mode = None
        range_start_utc = None
        range_end_utc = None
    elif normalized_calendar_mode:
        if not user_specified_start or range_start_utc is None:
            range_start_utc = datetime.combine(today, time.min, timezone.utc)
        calendar_start = range_start_utc
        if not user_specified_end or range_end_utc is None:
            # По умолчанию показываем ближайшую неделю, чтобы видеть предстоящие встречи.
            calendar_end = calendar_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            range_end_utc = calendar_end
        else:
            calendar_end = range_end_utc
    else:
        calendar_start = range_start_utc or datetime.combine(today, time.min, timezone.utc)
        calendar_end = range_end_utc or (calendar_start + timedelta(days=6))

    principal = principal or principal_ctx.get()
    if principal is None:
        raise RuntimeError("principal is required for list_candidates")

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
                User.candidate_id.ilike(like_value),
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
                Slot.candidate_id == User.candidate_id,
                Slot.test2_sent_at.isnot(None),
            )
            .correlate(User)
        )

        success_outcome_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                Slot.interview_outcome == 'success',
            )
            .correlate(User)
        )

        reject_outcome_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                Slot.interview_outcome == 'reject',
            )
            .correlate(User)
        )

        pending_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                func.lower(Slot.status) == SlotStatus.PENDING,
                Slot.start_utc >= now,
            )
            .correlate(User)
        )

        booked_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                func.lower(Slot.status) == SlotStatus.BOOKED,
                Slot.start_utc >= now,
            )
            .correlate(User)
        )

        confirmed_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                func.lower(Slot.status) == SlotStatus.CONFIRMED_BY_CANDIDATE,
                Slot.start_utc >= now,
            )
            .correlate(User)
        )

        past_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                Slot.start_utc < now,
                func.lower(Slot.status).in_(
                    [SlotStatus.BOOKED, SlotStatus.CONFIRMED_BY_CANDIDATE]
                ),
                Slot.interview_outcome.is_(None),
            )
            .correlate(User)
        )

        slot_pipeline_expr = (
            Slot.purpose == 'intro_day'
            if is_intro_pipeline
            else or_(Slot.purpose.is_(None), Slot.purpose != 'intro_day')
        )

        has_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                slot_pipeline_expr,
            )
            .correlate(User)
        )

        has_intro_day_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
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

        primary_event_expr = (
            select(func.min(Slot.start_utc))
            .where(
                Slot.candidate_id == User.candidate_id,
                slot_pipeline_expr,
                Slot.start_utc >= now,
            )
            .correlate(User)
            .scalar_subquery()
        ).label('primary_event_at')

        normalized_statuses = [slug for slug in normalized_statuses if slug in allowed_with_terminal]
        status_filter_values = normalized_statuses or (pipeline_statuses or ["__unreachable__"])
        upcoming_slot_expr = exists(
            select(1)
            .where(
                Slot.candidate_id == User.candidate_id,
                slot_pipeline_expr,
                Slot.start_utc >= now,
            )
            .correlate(User)
        )
        # Показываем: (а) статусы в воронке, (б) кандидатов с назначенным слотом в текущей воронке,
        # (в) "новых" кандидатов, у которых уже есть слот.
        conditions.append(
            or_(
                status_case.in_(status_filter_values),
                upcoming_slot_expr,
                and_(status_case == literal('new'), has_slot_expr),
            )
        )

        if recruiter_id is not None:
            conditions.append(
                exists(
                    select(1)
                    .where(
                        Slot.candidate_id == User.candidate_id,
                        Slot.recruiter_id == recruiter_id,
                    )
                    .correlate(User)
                )
            )

        if range_start_utc or range_end_utc:
            range_clauses: List[Any] = [Slot.candidate_id == User.candidate_id]
            if range_start_utc is not None:
                range_clauses.append(Slot.start_utc >= range_start_utc)
            if range_end_utc is not None:
                range_clauses.append(Slot.start_utc <= range_end_utc)
            conditions.append(
                exists(select(1).where(*range_clauses).correlate(User))
            )

        # Scoping: recruiter sees only owned candidates
        if principal and principal.type == "recruiter":
            conditions.append(User.responsible_recruiter_id == principal.id)

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
                        Slot.candidate_id == User.candidate_id,
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
            select(User, status_case, status_rank_expr, primary_event_expr, upcoming_slot_expr)
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
        upcoming_by_user = {row[0].id: bool(row[4]) for row in records}
        primary_event_by_user = {row[0].id: _ensure_aware(row[3]) for row in records}

        user_ids = [user.id for user in users]
        telegram_ids = [user.telegram_id for user in users if user.telegram_id]
        candidate_ids = [user.candidate_id for user in users if user.candidate_id]
        telegram_to_candidate = {
            user.telegram_id: user.candidate_id for user in users if user.telegram_id and user.candidate_id
        }

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

        slots_by_candidate: Dict[str, List[Slot]] = defaultdict(list)
        upcoming_slot_map: Dict[str, Optional[Slot]] = {}
        latest_slot_map: Dict[str, Optional[Slot]] = {}
        stage_map: Dict[str, str] = {}
        test2_sent_map: Dict[str, bool] = {}
        if candidate_ids or telegram_ids:
            slot_rows = await session.execute(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(
                    or_(
                        Slot.candidate_id.in_(candidate_ids) if candidate_ids else false(),
                        Slot.candidate_tg_id.in_(telegram_ids) if telegram_ids else false(),
                    )
                )
                .where(slot_pipeline_expr)
            )
            for slot in slot_rows.scalars():
                candidate_key = slot.candidate_id or telegram_to_candidate.get(slot.candidate_tg_id)
                if candidate_key is None:
                    continue
                slot.start_utc = _ensure_aware(slot.start_utc)
                slot.test2_sent_at = _ensure_aware(getattr(slot, 'test2_sent_at', None))
                slots_by_candidate[candidate_key].append(slot)
                if slot.test2_sent_at is not None:
                    test2_sent_map[candidate_key] = True
            for candidate_id_key, slot_list in slots_by_candidate.items():
                slot_list.sort(key=lambda s: (s.start_utc or datetime.min.replace(tzinfo=timezone.utc), s.id or 0))
                latest_slot = slot_list[-1] if slot_list else None
                upcoming_slot = next((s for s in slot_list if (s.start_utc or now) >= now), None)
                latest_slot_map[candidate_id_key] = latest_slot
                upcoming_slot_map[candidate_id_key] = upcoming_slot
                stage_map[candidate_id_key] = _stage_label(latest_slot, now)

        ratings = await _distinct_ratings(session)
        cities = await _distinct_cities(session)
        analytics = await _collect_candidate_analytics(session, now)

    items: List[CandidateRow] = []
    candidate_cards: List[Dict[str, Any]] = []

    for user in users:
        tests_total, avg_score = stats_map.get(user.id, (0, None))
        candidate_messages = messages_map.get(user.telegram_id, [])
        latest_slot = latest_slot_map.get(user.candidate_id)
        upcoming_slot = upcoming_slot_map.get(user.candidate_id)
        status_slug = status_by_user.get(user.id, 'new')
        # Если статус вне воронки, но у кандидата есть будущий слот — отображаем как interview_scheduled.
        if status_slug not in allowed_with_terminal and upcoming_by_user.get(user.id):
            status_slug = 'interview_scheduled'
        status_label = _status_label(status_slug)
        stage_value = stage_map.get(user.candidate_id, 'Без интервью')
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
        test2_sent = test2_sent_map.get(user.candidate_id, False)

        t1_status = 'passed' if test1_result else 'not_started'

        if test2_result:
            if TEST2_TOTAL_QUESTIONS:
                t2_passed = (test2_result.raw_score or 0) >= TEST2_MIN_CORRECT
            else:
                t2_passed = (test2_result.final_score or 0) >= 0
            t2_status_value = 'passed' if t2_passed else 'failed'
        else:
            t2_status_value = 'in_progress' if test2_sent else 'not_started'

        telemost_url, telemost_source = _resolve_telemost_url(slots_by_candidate.get(user.candidate_id, []))

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
                'candidate_id': user.candidate_id,
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
                'slots': slots_by_candidate.get(
                    user.candidate_id or telegram_to_candidate.get(user.telegram_id),
                    [],
                ),
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
    if normalized_calendar_mode and calendar_start and calendar_end:
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
            if not (normalized_calendar_mode and calendar_start and calendar_end):
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
            Slot.candidate_id.label("candidate_id"),
            Slot.start_utc.label("start_utc"),
            Slot.status.label("status"),
            func.row_number()
            .over(
                partition_by=Slot.candidate_id,
                order_by=(Slot.start_utc.desc(), Slot.id.desc()),
            )
            .label("rnk"),
        )
        .where(Slot.candidate_id.isnot(None))
    ).subquery()

    latest_rows = await session.execute(
        select(
            slot_sub.c.candidate_id,
            slot_sub.c.start_utc,
            slot_sub.c.status,
        )
        .select_from(slot_sub.join(User, User.candidate_id == slot_sub.c.candidate_id))
        .where(slot_sub.c.rnk == 1)
    )

    stage_counts: Dict[str, int] = defaultdict(int)
    upcoming_count = 0
    awaiting_confirmation = 0
    booked_active = 0
    completed_interviews = 0
    canceled_count = 0

    for _candidate_id, start_utc, status in latest_rows:
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
            select(City.id, City.name, City.tz).order_by(City.name.asc())
        )
        city_choices = [
            {"id": city_id, "name": name, "tz": tz}
            for city_id, name, tz in city_rows
            if name
        ]
        cities = [entry["name"] for entry in city_choices]
        ratings = await _distinct_ratings(session)
        recruiter_rows = await session.execute(
            select(Recruiter).order_by(Recruiter.name.asc())
        )
        recruiters = [
            {
                "id": recruiter.id,
                "name": recruiter.name,
                "tz": recruiter.tz,
                "active": recruiter.active,
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


async def _release_intro_day_slots_for_candidate(
    session,
    *,
    candidate_uuid: Optional[str],
    candidate_tg_id: Optional[int],
) -> int:
    """Free any active intro day slots still bound to the candidate."""

    if not candidate_uuid and candidate_tg_id is None:
        return 0

    active_statuses = {
        SlotStatus.BOOKED,
        SlotStatus.PENDING,
        SlotStatus.CONFIRMED,
        SlotStatus.CONFIRMED_BY_CANDIDATE,
    }
    slots_query = (
        select(Slot)
        .where(
            Slot.purpose == "intro_day",
            Slot.status.in_(active_statuses),
            or_(
                Slot.candidate_id == candidate_uuid,
                Slot.candidate_tg_id == candidate_tg_id,
            ),
        )
    )
    slots = (await session.execute(slots_query)).scalars().all()
    released = 0

    for slot in slots:
        slot.status = SlotStatus.FREE
        slot.candidate_id = None
        slot.candidate_tg_id = None
        slot.candidate_fio = None
        slot.candidate_tz = None
        slot.candidate_city_id = None
        slot.interview_outcome = None
        slot.rejection_sent_at = None
        released += 1
        try:
            await cancel_slot_reminders(slot.id)
        except Exception:
            logger.warning(
                "intro_day_slot.cleanup.reminders_failed",
                extra={"slot_id": slot.id},
            )

    if released:
        logger.info(
            "intro_day_slot.cleanup.completed",
            extra={
                "released": released,
                "candidate_tg_id": candidate_tg_id,
                "candidate_uuid": candidate_uuid,
            },
        )

    return released


async def update_candidate_status(
    candidate_id: int,
    status_slug: str,
    *,
    bot_service: Optional["BotService"] = None,
    principal: Optional[Principal] = None,
    reason: Optional[str] = None,
    comment: Optional[str] = None,
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

    principal = principal or principal_ctx.get()
    async with async_session() as session:
        user = await session.get(User, candidate_id)
        if not user:
            return False, "Кандидат не найден", None, None
        if principal and principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            return False, "Кандидат не найден", None, None
        if user.telegram_id is None and normalized not in STATUS_DEFINITIONS:
            return False, "Для кандидата не указан Telegram ID", None, None
        
        # Store reason/comment if provided
        if reason:
            user.rejection_reason = reason
        if comment:
            # Append comment to existing manual_slot_comment or similar if appropriate, 
            # or just set it if we have a specific field. 
            # For now, let's just use rejection_reason if it's a rejection.
            if not user.rejection_reason and normalized in {"interview_declined", "test2_failed", "not_hired", "intro_day_declined_day_of"}:
                user.rejection_reason = comment
            elif comment:
                 user.manual_slot_comment = (user.manual_slot_comment or "") + f"\n{comment}"

        previous_status = getattr(user, "candidate_status", None)
        previous_status_slug = getattr(previous_status, "value", None) if previous_status else None
        if previous_status_slug is None and isinstance(previous_status, str):
            previous_status_slug = previous_status

        status_slot_filters = [Slot.candidate_id == user.candidate_id]
        if user.telegram_id is not None:
            status_slot_filters.append(Slot.candidate_tg_id == user.telegram_id)
        slot_query = (
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(or_(*status_slot_filters))
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
                principal=principal,
            )
            if ok:
                await log_audit_action(
                    "candidate_status_updated",
                    "candidate",
                    candidate_id,
                    changes={
                        "from": previous_status_slug,
                        "to": normalized,
                        "slot_id": target_slot.id if target_slot else None,
                    },
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
                await log_audit_action(
                    "candidate_status_updated",
                    "candidate",
                    candidate_id,
                    changes={
                        "from": previous_status_slug,
                        "to": normalized,
                        "slot_id": target_slot.id if target_slot else None,
                    },
                )
                return True, message, normalized, None

            target_slot.status = slot_status_map[normalized]
            if normalized != "awaiting_confirmation":
                target_slot.interview_outcome = None
            await session.commit()
            await log_audit_action(
                "candidate_status_updated",
                "candidate",
                candidate_id,
                changes={
                    "from": previous_status_slug,
                    "to": normalized,
                    "slot_id": target_slot.id if target_slot else None,
                },
            )
            return True, "Статус обновлён", normalized, None

        if normalized in STATUS_DEFINITIONS:
            dispatch = None
            try:
                target_status = CandidateStatus(normalized)
            except ValueError:
                target_status = None

            if target_status == CandidateStatus.TEST2_SENT:
                if target_slot is None:
                    return False, "Для кандидата не найден подходящий слот", None, None
                from backend.apps.admin_ui.services.slots import set_slot_outcome
                ok, message, _, dispatch = await set_slot_outcome(
                    target_slot.id,
                    "success",
                    bot_service=bot_service,
                    principal=principal,
                )
                if not ok:
                    return False, message or "Не удалось отправить Тест 2.", None, None

            if target_status == user.candidate_status:
                user.status_changed_at = datetime.now(timezone.utc)
                status_changed = False
            else:
                status_changed = await _candidate_status_service.force(
                    user,
                    target_status,
                    reason="admin manual status update",
                )

            if target_status in STATUSES_RELEASE_INTRO_DAY_SLOTS:
                await _release_intro_day_slots_for_candidate(
                    session,
                    candidate_uuid=user.candidate_id,
                    candidate_tg_id=user.telegram_user_id or user.telegram_id,
                )
                user.is_active = False
            elif target_status in STATUSES_ARCHIVE_ON_DECLINE:
                user.is_active = False

            await session.commit()
            funnel_event = FUNNEL_STATUS_EVENTS.get(user.candidate_status) if user.candidate_status else None
            if funnel_event:
                try:
                    await analytics.log_funnel_event(
                        funnel_event,
                        user_id=user.telegram_id,
                        candidate_id=user.id,
                        metadata={"status": user.candidate_status.value, "source": "admin"},
                    )
                except Exception:
                    logger.exception(
                        "Failed to log funnel event after manual status change",
                        extra={"candidate_id": user.id, "status": normalized},
                    )
            await log_audit_action(
                "candidate_status_updated",
                "candidate",
                candidate_id,
                changes={
                    "from": previous_status_slug,
                    "to": normalized,
                    "slot_id": getattr(target_slot, "id", None),
                },
            )
            return True, "Статус обновлён", normalized, dispatch

    return False, "Этот статус нельзя установить вручную", None, None


async def get_candidate_detail(user_id: int, principal: Optional[Principal] = None) -> Optional[Dict[str, object]]:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        # Optimized load: everything relevant in fewer queries
        query = (
            select(User)
            .options(
                selectinload(User.test_results).selectinload(TestResult.answers),
            )
            .where(User.id == user_id)
        )
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        if principal and principal.type == "recruiter":
            if user.responsible_recruiter_id != principal.id:
                # Allow access if candidate city belongs to recruiter's assigned cities
                allowed = False
                if user.city:
                    city_record = await find_city_by_plain_name(user.city)
                    if city_record:
                        rows = await session.execute(
                            select(recruiter_city_association.c.city_id)
                            .where(recruiter_city_association.c.recruiter_id == principal.id)
                        )
                        allowed_city_ids = {row[0] for row in rows}
                        if city_record.id in allowed_city_ids:
                            allowed = True
                if not allowed:
                    return None

        interview_note = await _load_interview_note(session, user_id)
        test_results = sorted(user.test_results, key=lambda r: (r.created_at or datetime.min, r.id), reverse=True)

        answers_by_result: Dict[int, List[QuestionAnswer]] = {
            res.id: list(res.answers) for res in test_results
        }
        answers_map: Dict[int, Dict[str, int]] = {}
        for test_id, answer_items in answers_by_result.items():
            answers_map[test_id] = {
                "questions_total": len(answer_items),
                "questions_correct": sum(1 for item in answer_items if item.is_correct),
                "questions_overtime": sum(1 for item in answer_items if item.overtime),
            }

        if user.telegram_id is None:
            messages = []
        else:
            messages = (
                await session.execute(
                    select(AutoMessage)
                    .where(AutoMessage.target_chat_id == user.telegram_id)
                    .order_by(AutoMessage.created_at.desc(), AutoMessage.id.desc())
                )
            ).scalars().all()

        slot_filters = [Slot.candidate_id == user.candidate_id]
        if user.telegram_id is not None:
            slot_filters.append(Slot.candidate_tg_id == user.telegram_id)
        slots = (
            await session.execute(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(or_(*slot_filters))
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

        # Determine has_intro_day_slot and test2_passed early for action calculation
        active_intro_day_statuses = {
            SlotStatus.BOOKED,
            SlotStatus.PENDING,
            SlotStatus.CONFIRMED,
            SlotStatus.CONFIRMED_BY_CANDIDATE,
        }
        intro_day_cutoff = now - timedelta(hours=1)
        has_intro_day_slot = any(
            (slot.purpose or "").lower() == "intro_day"
            and (slot.status or "").lower() in active_intro_day_statuses
            and slot.start_utc
            and slot.start_utc >= intro_day_cutoff
            for slot in slots
        )
        test2_passed_early = _has_passed_test2(test_results)

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
        test2_status = (test_sections_map.get("test2", {}).get("status") or "").lower()
        has_test2_result = test2_status in {"passed", "failed"}
        test_sections_list = list(test_sections_map.values())

        telemost_url, telemost_source = _resolve_telemost_url(slots)

        responsible_recruiter = None
        if getattr(user, "responsible_recruiter_id", None):
            responsible_recruiter = await session.get(Recruiter, user.responsible_recruiter_id)

        # Autofix статус, если реальный результат теста выше, чем зафиксированный статус
        if test2_status == "passed" and candidate_status in {
            CandidateStatus.TEST2_FAILED,
            CandidateStatus.TEST2_SENT,
            CandidateStatus.INTERVIEW_DECLINED,
            None,
        }:
            try:
                await _candidate_status_service.force(
                    user,
                    CandidateStatus.TEST2_COMPLETED,
                    reason="autofix:test2_passed",
                )
                user.is_active = True
                candidate_status = user.candidate_status
                candidate_status_slug = candidate_status.value if candidate_status else None
                await session.commit()
                await log_audit_action(
                    "candidate_status_autofix",
                    "candidate",
                    user.id,
                    changes={
                        "from": "legacy_or_failed",
                        "to": CandidateStatus.TEST2_COMPLETED.value,
                        "source": "test2_result_passed",
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to autofix candidate status after Test2 pass",
                    extra={"candidate_id": user.id, "status": str(candidate_status)},
                )

        # Check if candidate needs intro day (reuse variables calculated earlier)
        status_requires_intro_day = (
            candidate_status in STATUSES_PENDING_INTRO_DAY if candidate_status else False
        )
        test2_passed = test2_passed_early  # Already calculated for actions
        needs_intro_day = (status_requires_intro_day or test2_passed) and not has_intro_day_slot

        # Decide which status to use for UI actions:
        # - Prefer explicit candidate_status from DB
        # - If Test 2 results show passed/failed but status not updated, derive from test outcome
        action_status = candidate_status
        if candidate_status is None:
            if test2_status == "passed":
                action_status = CandidateStatus.TEST2_COMPLETED
                test2_passed = True
            elif test2_status == "failed":
                action_status = CandidateStatus.TEST2_FAILED
        elif candidate_status in {
            CandidateStatus.TEST2_SENT,
            CandidateStatus.TEST2_COMPLETED,
        }:
            # Align pre-OD statuses with actual test outcome, но не затираем более поздние этапы
            if test2_status == "passed" and candidate_status == CandidateStatus.TEST2_SENT:
                action_status = CandidateStatus.TEST2_COMPLETED
                test2_passed = True
            elif test2_status == "failed":
                action_status = CandidateStatus.TEST2_FAILED

        candidate_actions = get_candidate_actions(
            action_status,
            has_upcoming_slot=upcoming_slot is not None,
            has_test2_passed=test2_passed,
            has_intro_day_slot=has_intro_day_slot,
        )

        effective_workflow_status = _map_to_workflow_status(user)
        user.workflow_status = effective_workflow_status.value
        workflow_state = _workflow_service.describe(user)
        workflow_actions = _workflow_actions_ui(user.id, workflow_state.allowed_actions)
        workflow_status_label = WORKFLOW_STATUS_LABELS.get(
            workflow_state.status, workflow_state.status.value
        )
        workflow_status_color = WORKFLOW_STATUS_COLORS.get(
            workflow_state.status, "muted"
        )
        # Для отображения статуса в UI используем workflow (единственный источник правды)
        stage = workflow_status_label

    # Prepare pipeline stages and allowed next statuses for Status Center UI
    pipeline_stages = _build_pipeline_stages(candidate_status)
    allowed_next = get_next_statuses(candidate_status) if candidate_status else []
    allowed_next_statuses = [
        {
            "slug": status.value,
            "label": label,
            "color": get_status_color(status),
            "is_terminal": is_terminal_status(status),
        }
        for status, label in allowed_next
    ]
    status_is_terminal = is_terminal_status(candidate_status) if candidate_status else False

    intro_day_template = None
    if user.city:
        city_obj = await find_city_by_plain_name(user.city)
        if city_obj:
            async with async_session() as city_session:
                city_result = await city_session.execute(select(City).where(func.lower(City.name) == user.city.lower()))
                city_record = city_result.scalars().first()
                if city_record:
                    intro_day_template = city_record.intro_day_template
    if not intro_day_template:
        intro_day_template = DEFAULT_INTRO_DAY_INVITATION_TEMPLATE

    settings = get_settings()

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
        "candidate_status_color": get_status_color(candidate_status) if candidate_status else "muted",
        "candidate_actions": candidate_actions,
        "workflow_state": workflow_state,
        "workflow_actions": workflow_actions,
        "workflow_status": workflow_state.status.value,
        "workflow_status_label": workflow_status_label,
        "workflow_status_color": workflow_status_color,
        "pipeline_stages": pipeline_stages,
        "allowed_next_statuses": allowed_next_statuses,
        "status_is_terminal": status_is_terminal,
        "stats": {
            "tests_total": tests_total,
            "avg_score": float(avg_score) if avg_score is not None else None,
        },
        "telemost_url": telemost_url,
        "telemost_source": telemost_source,
        "responsible_recruiter": responsible_recruiter,
        "candidate_status_options": [
            {"value": s.value, "label": s.value} for s in CandidateStatus
        ],
        "legacy_status_enabled": settings.enable_legacy_status_api,
        "intro_day_template": intro_day_template,
    }


async def save_interview_notes(
    user_id: int,
    *,
    interviewer_name: Optional[str],
    data: Dict[str, Any],
    principal: Optional["Principal"] = None,
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
        if principal and getattr(principal, "type", None) == "recruiter":
            if user.responsible_recruiter_id != getattr(principal, "id", None):
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
    telegram_id: Optional[int],
    fio: str,
    city: Optional[str],
    phone: Optional[str] = None,
    responsible_recruiter_id: Optional[int] = None,
    manual_slot_from: Optional[datetime] = None,
    manual_slot_to: Optional[datetime] = None,
    manual_slot_timezone: Optional[str] = None,
    is_active: bool,
    last_activity: Optional[datetime] = None,
    source: str = "manual_call",
    initial_status: Optional[CandidateStatus] = CandidateStatus.LEAD,
) -> User:
    clean_fio = fio.strip()
    clean_city = city.strip() if city else None
    clean_phone = phone.strip() if phone else None
    if not clean_fio:
        raise ValueError("Имя кандидата не может быть пустым")

    async with async_session() as session:
        user = None
        if telegram_id is not None:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        last_activity_value = last_activity or now

        if user:
            user.fio = clean_fio
            user.city = clean_city
            user.phone = clean_phone
            user.is_active = is_active
            user.last_activity = last_activity_value
            if responsible_recruiter_id is not None:
                user.responsible_recruiter_id = responsible_recruiter_id
            if manual_slot_from is not None:
                user.manual_slot_from = manual_slot_from
            if manual_slot_to is not None:
                user.manual_slot_to = manual_slot_to
            if manual_slot_timezone is not None:
                user.manual_slot_timezone = manual_slot_timezone
        else:
            user = User(
                telegram_id=telegram_id,
                fio=clean_fio,
                city=clean_city,
                phone=clean_phone,
                responsible_recruiter_id=responsible_recruiter_id,
                manual_slot_from=manual_slot_from,
                manual_slot_to=manual_slot_to,
                manual_slot_timezone=manual_slot_timezone,
                is_active=is_active,
                last_activity=last_activity_value,
                source=source,
            )
            session.add(user)
            await session.flush()
            if initial_status:
                await _candidate_status_service.force(
                    user,
                    initial_status,
                    reason="candidate creation",
                )
                user.status_changed_at = last_activity_value

        await session.commit()
        await session.refresh(user)
        return user


async def toggle_candidate_activity(user_id: int, *, active: bool, principal: Optional[Principal] = None) -> bool:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False
        if principal and principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            return False
        user.is_active = active
        await session.commit()
        return True


async def update_candidate(
    user_id: int,
    *,
    telegram_id: Optional[int],
    fio: str,
    city: Optional[str],
    phone: Optional[str] = None,
    is_active: bool,
    principal: Optional[Principal] = None,
) -> bool:
    clean_fio = fio.strip()
    clean_city = city.strip() if city else None
    clean_phone = phone.strip() if phone else None
    if not clean_fio:
        raise ValueError("Имя кандидата не может быть пустым")

    principal = principal or principal_ctx.get()
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False
        if principal and principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            return False

        if telegram_id is not None:
            user.telegram_id = telegram_id
        user.fio = clean_fio
        user.city = clean_city
        user.phone = clean_phone
        user.is_active = is_active

        await session.commit()
        return True


async def assign_candidate_recruiter(
    user_id: int,
    recruiter_id: int,
    *,
    principal: Optional[Principal] = None,
) -> bool:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False
        if principal and principal.type != "admin":
            return False
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            raise ValueError("recruiter_not_found")
        user.responsible_recruiter_id = recruiter_id
        await session.commit()
        return True


async def delete_candidate(user_id: int, principal: Optional[Principal] = None) -> bool:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return False
        if principal and principal.type == "recruiter" and user.responsible_recruiter_id != principal.id:
            return False

        # Find all slots to cancel reminders before releasing them
        slots_query = select(Slot.id).where(
            or_(
                Slot.candidate_id == user.candidate_id,
                Slot.candidate_tg_id == user.telegram_id
            )
        )
        slot_ids = (await session.execute(slots_query)).scalars().all()
        
        for s_id in slot_ids:
            try:
                await cancel_slot_reminders(s_id)
            except Exception:
                logger.warning("failed_to_cancel_reminders_on_delete", extra={"slot_id": s_id, "user_id": user_id})

        release_result = await session.execute(
            Slot.__table__.update()
            .where(or_(Slot.candidate_id == user.candidate_id, Slot.candidate_tg_id == user.telegram_id))
            .values(
                candidate_id=None,
                candidate_tg_id=None,
                candidate_fio=None,
                candidate_tz=None,
                candidate_city_id=None,
                status=SlotStatus.FREE,
            )
        )
        released = release_result.rowcount or 0
        await session.delete(user)
        await session.commit()
        await log_audit_action(
            "candidate_deleted",
            "candidate",
            user_id,
            changes={"released_slots": released},
        )
        return True


async def generate_candidate_invite_token(
    user_id: int,
    principal: Optional["Principal"] = None,
) -> Optional[str]:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return None
        if principal and getattr(principal, "type", None) == "recruiter":
            if user.responsible_recruiter_id != getattr(principal, "id", None):
                return None
        invite = await create_candidate_invite_token(user.candidate_id)
        current_status = user.candidate_status
        current_slug = (
            current_status.value if isinstance(current_status, CandidateStatus) else current_status
        )
        if current_slug in {None, "lead", "contacted"}:
            await _candidate_status_service.force(
                user,
                CandidateStatus.INVITED,
                reason="generate candidate invite token",
            )
            await session.commit()
        return invite.token


async def delete_all_candidates() -> int:
    """Delete all candidate profiles and release assigned slots."""
    async with async_session() as session:
        candidate_ids = await session.scalars(
            select(User.candidate_id).where(User.candidate_id.is_not(None))
        )
        candidate_list = [value for value in candidate_ids if value]
        candidate_tg_ids = await session.scalars(
            select(User.telegram_id).where(User.telegram_id.is_not(None))
        )
        tg_list = [value for value in candidate_tg_ids if value]

        slot_filters = []
        if candidate_list:
            slot_filters.append(Slot.candidate_id.in_(candidate_list))
        if tg_list:
            slot_filters.append(Slot.candidate_tg_id.in_(tg_list))

        if slot_filters:
            await session.execute(
                Slot.__table__.update()
                .where(or_(*slot_filters))
                .values(
                    candidate_id=None,
                    candidate_tg_id=None,
                    candidate_fio=None,
                    candidate_tz=None,
                    candidate_city_id=None,
                    status=SlotStatus.FREE,
                )
            )

        delete_result = await session.execute(delete(User))
        await session.commit()
        removed = delete_result.rowcount or 0
        await log_audit_action(
            "candidates_bulk_deleted",
            "candidate",
            None,
            changes={"deleted": removed},
        )
        return removed


async def api_candidate_detail_payload(candidate_id: int) -> Optional[Dict[str, object]]:
    detail = await get_candidate_detail(candidate_id)
    if not detail:
        return None
    user: User = detail["user"]
    sections_map = detail.get("test_sections_map", {})
    candidate_actions = detail.get("candidate_actions", []) or []
    slots = detail.get("slots", []) or []

    def _iso(value: Optional[datetime]) -> Optional[str]:
        if not value:
            return None
        return _ensure_aware(value).isoformat()

    def _normalize_username(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = value.strip()
        if cleaned.startswith("@"):
            cleaned = cleaned[1:]
        return cleaned or None

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

    def _action_field(action: object, key: str) -> Optional[object]:
        if isinstance(action, dict):
            return action.get(key)
        return getattr(action, key, None)

    actions_payload = []
    for action in candidate_actions:
        url_pattern = _action_field(action, "url_pattern")
        resolved_url = None
        if isinstance(url_pattern, str):
            resolved_url = url_pattern.replace("{id}", str(user.id))
        actions_payload.append(
            {
                "key": _action_field(action, "key"),
                "label": _action_field(action, "label"),
                "url_pattern": url_pattern,
                "url": resolved_url,
                "icon": _action_field(action, "icon"),
                "variant": _action_field(action, "variant"),
                "method": _action_field(action, "method") or "GET",
                "target_status": _action_field(action, "target_status"),
                "confirmation": _action_field(action, "confirmation"),
                "requires_slot": bool(_action_field(action, "requires_slot")),
                "requires_test2_passed": bool(_action_field(action, "requires_test2_passed")),
            }
        )

    slots_payload = []
    for slot in slots:
        slots_payload.append(
            {
                "id": slot.id,
                "status": slot.status,
                "purpose": slot.purpose,
                "start_utc": _iso(slot.start_utc),
                "candidate_tz": slot.candidate_tz,
                "recruiter_name": getattr(slot.recruiter, "name", None) if getattr(slot, "recruiter", None) else None,
                "city_name": getattr(slot.city, "name", None) if getattr(slot, "city", None) else None,
            }
        )

    responsible_recruiter = detail.get("responsible_recruiter")
    responsible_payload = None
    if responsible_recruiter is not None:
        responsible_payload = {
            "id": getattr(responsible_recruiter, "id", None),
            "name": getattr(responsible_recruiter, "name", None),
        }

    return {
        "id": user.id,
        "fio": user.fio,
        "city": user.city,
        "telegram_id": user.telegram_id,
        "telegram_username": _normalize_username(user.telegram_username or user.username),
        "phone": user.phone,
        "is_active": user.is_active,
        "test1_report_url": f"/candidates/{user.id}/reports/test1"
        if getattr(user, "test1_report_url", None)
        else None,
        "test2_report_url": f"/candidates/{user.id}/reports/test2"
        if getattr(user, "test2_report_url", None)
        else None,
        "test_results": test_results_payload,
        "test_sections": detail.get("test_sections", []),
        "stage": detail.get("stage"),
        "workflow_status": detail.get("workflow_status"),
        "workflow_status_label": detail.get("workflow_status_label"),
        "workflow_status_color": detail.get("workflow_status_color"),
        "candidate_status_slug": detail.get("candidate_status_slug"),
        "candidate_status_color": detail.get("candidate_status_color"),
        "stats": detail.get("stats", {}),
        "telemost_url": detail.get("telemost_url"),
        "telemost_source": detail.get("telemost_source"),
        "responsible_recruiter": responsible_payload,
        "candidate_actions": actions_payload,
        "slots": slots_payload,
        "allowed_next_statuses": detail.get("allowed_next_statuses", []),
        "pipeline_stages": detail.get("pipeline_stages", []),
        "status_is_terminal": detail.get("status_is_terminal", False),
        "candidate_status_options": detail.get("candidate_status_options", []),
        "legacy_status_enabled": detail.get("legacy_status_enabled", False),
        "intro_day_template": detail.get("intro_day_template"),
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
