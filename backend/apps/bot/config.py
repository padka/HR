"""Configuration and core constants for the bot application."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict

import logging

from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.core.settings import get_settings
from backend.domain.default_questions import DEFAULT_TEST_QUESTIONS
from backend.domain.test_questions import load_all_test_questions

settings = get_settings()

DEFAULT_TZ = settings.timezone or "Europe/Moscow"
TIME_FMT = "%d.%m %H:%M"
BOT_TOKEN = settings.bot_token
DEFAULT_BOT_PROPERTIES = DefaultBotProperties(parse_mode=ParseMode.HTML)

# Порог прохождения теста 2 (доля правильных)
PASS_THRESHOLD = 0.75
MAX_ATTEMPTS = 3
TIME_LIMIT = 120  # сек на вопрос (Тест 2)

RemKey = Tuple[int, int]


class State(TypedDict, total=False):
    """In-memory representation of candidate state."""

    flow: str  # 'interview' | 'intro'
    t1_idx: Optional[int]
    t1_current_idx: Optional[int]
    test1_answers: Dict[str, str]
    t1_last_prompt_id: Optional[int]
    t1_last_question_text: str
    t1_requires_free_text: bool
    t1_sequence: List[Dict[str, Any]]

    fio: str
    city_name: str
    city_id: Optional[int]
    candidate_tz: str

    t2_attempts: Dict[int, Dict[str, Any]]
    picked_recruiter_id: Optional[int]
    picked_slot_id: Optional[int]

    format_choice: Optional[str]
    study_mode: Optional[str]
    study_schedule: Optional[str]
    study_flex: Optional[str]
    test1_payload: Dict[str, Any]

    manual_contact_prompt_sent: bool


try:
    _QUESTIONS_BANK = load_all_test_questions()
except Exception:  # pragma: no cover - fallback for missing DB tables
    logging.getLogger(__name__).warning(
        "Falling back to default test questions; database is not available."
    )
    _QUESTIONS_BANK = DEFAULT_TEST_QUESTIONS
TEST2_QUESTIONS: List[Dict[str, Any]] = (
    _QUESTIONS_BANK.get("test2", DEFAULT_TEST_QUESTIONS.get("test2", [])).copy()
)
TEST1_QUESTIONS: List[Dict[str, Any]] = (
    _QUESTIONS_BANK.get("test1", DEFAULT_TEST_QUESTIONS.get("test1", [])).copy()
)

FOLLOWUP_NOTICE_PERIOD = {
    "id": "notice_period",
    "prompt": (
        "⏳ Сколько времени потребуется, чтобы закрыть все текущие дела и пиступить к обучению в нашей компании?\n"
        "<i>Нам важно понимать, сможете ли вы стартовать в ближайшие 2–3 дня.</i>"
    ),
    "placeholder": "Например: через 2 дня / уже готов завтра",
}

FOLLOWUP_STUDY_MODE = {
    "id": "study_mode",
    "prompt": "🎓 Учитесь очно или заочно?",
    "options": [
        "Очно",
        "Очно, но гибкий график",
        "Заочно",
        "Дистанционно",
        "Другое",
    ],
}

FOLLOWUP_STUDY_SCHEDULE = {
    "id": "study_schedule",
    "prompt": (
        "🗓️ Получится ли совмещать учёбу с графиком 5/2 с 9:00 до 18:00?\n"
        "<i>Рабочий график фиксированный, важно понимать вашу готовность.</i>"
    ),
    "options": [
        "Да, смогу",
        "Смогу, но нужен запас по времени",
        "Будет сложно",
        "Нет, не смогу",
    ],
}

FOLLOWUP_STUDY_FLEX = {
    "id": "study_flex",
    "prompt": (
        "🧭 Если понадобится гибкость, готовы обсудить индивидуальный график или перенос занятий?"
    ),
    "options": [
        "Да, готов обсудить",
        "Нужна частичная занятость",
        "Нет, не смогу",
    ],
}

__all__ = [
    "BOT_TOKEN",
    "DEFAULT_BOT_PROPERTIES",
    "DEFAULT_TZ",
    "FOLLOWUP_NOTICE_PERIOD",
    "FOLLOWUP_STUDY_MODE",
    "FOLLOWUP_STUDY_SCHEDULE",
    "FOLLOWUP_STUDY_FLEX",
    "MAX_ATTEMPTS",
    "PASS_THRESHOLD",
    "RemKey",
    "State",
    "TEST1_QUESTIONS",
    "TEST2_QUESTIONS",
    "TIME_FMT",
    "TIME_LIMIT",
]
