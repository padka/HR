"""Configuration and core constants for the bot application."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from copy import deepcopy
from typing import Any, TypedDict

from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.core.settings import get_settings
from backend.domain.test_questions import load_all_test_questions
from backend.domain.tests.bootstrap import DEFAULT_TEST_QUESTIONS

settings = get_settings()

DEFAULT_TZ = settings.timezone or "Europe/Moscow"
TIME_FMT = "%d.%m %H:%M"
BOT_TOKEN = settings.bot_token
DEFAULT_BOT_PROPERTIES = DefaultBotProperties(parse_mode=ParseMode.HTML)
BOT_BACKEND_URL = settings.bot_backend_url

# Порог прохождения теста 2 (доля правильных)
PASS_THRESHOLD = 0.75
MAX_ATTEMPTS = 3
TIME_LIMIT = 120  # сек на вопрос (Тест 2)

RemKey = tuple[int, int]


class State(TypedDict, total=False):
    """In-memory representation of candidate state."""

    flow: str  # 'interview' | 'intro'
    # Monotonic revision of the in-memory question bank used to build this state.
    # Allows the bot to sync active sessions when admins update questions.
    questions_bank_version: int
    t1_idx: int | None
    t1_current_idx: int | None
    test1_answers: dict[str, str]
    t1_last_prompt_id: int | None
    t1_last_question_text: str
    t1_requires_free_text: bool
    t1_sequence: list[dict[str, Any]]

    fio: str
    city_name: str
    city_id: int | None
    candidate_tz: str

    t2_attempts: dict[int, dict[str, Any]]
    picked_recruiter_id: int | None
    picked_slot_id: int | None

    format_choice: str | None
    study_mode: str | None
    study_schedule: str | None
    study_flex: str | None
    test1_payload: dict[str, Any]

    manual_contact_prompt_sent: bool
    manual_availability_expected: bool
    manual_availability_last_note: str | None

    slot_assignment_id: int | None
    slot_assignment_state: str | None
    slot_assignment_action_token: str | None
    slot_assignment_candidate_tz: str | None
    awaiting_slot_assignment_decline_reason: dict[str, Any]


logger = logging.getLogger(__name__)

_QUESTIONS_BANK: dict[str, list[dict[str, Any]]] = {}
TEST1_QUESTIONS: list[dict[str, Any]] = []
TEST2_QUESTIONS: list[dict[str, Any]] = []
_QUESTIONS_BANK_VERSION: int = 0
_QUESTIONS_BANK_HASH: str = ""
_QUESTIONS_BANK_LOADED_AT: float = 0.0
_QUESTIONS_BANK_SOURCE: str = "unknown"
_OPENAPI_MODE_ENV = "RECRUITSMART_OPENAPI_MODE"


def refresh_questions_bank(*, include_inactive: bool = False) -> None:
    """
    Reload test questions from the database so admin UI changes are visible to the bot
    without restarting the process.
    """

    global _QUESTIONS_BANK, TEST1_QUESTIONS, TEST2_QUESTIONS

    global _QUESTIONS_BANK_VERSION, _QUESTIONS_BANK_HASH, _QUESTIONS_BANK_LOADED_AT, _QUESTIONS_BANK_SOURCE

    source = "db"
    try:
        loaded = load_all_test_questions(include_inactive=include_inactive)
    except Exception as exc:  # pragma: no cover - fallback for missing DB tables
        logger.warning(
            "Falling back to empty questions; database is not available. error=%s",
            exc,
        )
        loaded = deepcopy(DEFAULT_TEST_QUESTIONS)
        source = "fallback"

    if not loaded:
        loaded = deepcopy(DEFAULT_TEST_QUESTIONS)
        source = "default"
    else:
        for key, default_questions in DEFAULT_TEST_QUESTIONS.items():
            if not loaded.get(key):
                loaded[key] = deepcopy(default_questions)

    _QUESTIONS_BANK = loaded
    TEST1_QUESTIONS = _QUESTIONS_BANK.get("test1", []).copy()
    TEST2_QUESTIONS = _QUESTIONS_BANK.get("test2", []).copy()

    _QUESTIONS_BANK_LOADED_AT = float(time.time())
    _QUESTIONS_BANK_SOURCE = source
    new_hash = ""
    try:
        raw = json.dumps(
            _QUESTIONS_BANK,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        new_hash = hashlib.sha256(raw).hexdigest()
    except Exception:  # pragma: no cover - defensive
        new_hash = ""

    # Increment version only when the content actually changed. This prevents
    # unnecessary resync for active sessions when refresh() is called frequently.
    if new_hash and new_hash != _QUESTIONS_BANK_HASH:
        _QUESTIONS_BANK_VERSION += 1
        _QUESTIONS_BANK_HASH = new_hash
    elif not _QUESTIONS_BANK_HASH:
        # First successful load (or hash calculation failed): still set a non-zero version.
        _QUESTIONS_BANK_VERSION = max(1, int(_QUESTIONS_BANK_VERSION))
        if new_hash:
            _QUESTIONS_BANK_HASH = new_hash


def maybe_prime_questions_bank() -> None:
    """Prime the in-memory bank unless tooling explicitly requests quiet schema mode."""

    if str(os.getenv(_OPENAPI_MODE_ENV, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        logger.info("Skipping question bank warmup in OpenAPI tooling mode.")
        return
    refresh_questions_bank()


def get_questions_bank_version() -> int:
    """Return the current in-memory question bank revision."""

    return int(_QUESTIONS_BANK_VERSION)


def get_questions_bank_meta() -> dict[str, object]:
    """Return a small diagnostic snapshot of the in-memory question bank."""

    return {
        "version": int(_QUESTIONS_BANK_VERSION),
        "hash": _QUESTIONS_BANK_HASH,
        "loaded_at": _QUESTIONS_BANK_LOADED_AT,
        "source": _QUESTIONS_BANK_SOURCE,
        "counts": {
            "test1": len(TEST1_QUESTIONS),
            "test2": len(TEST2_QUESTIONS),
        },
    }


# Prime question bank at import so existing imports keep working in normal runtime.
maybe_prime_questions_bank()

FOLLOWUP_NOTICE_PERIOD = {
    "id": "notice_period",
    "prompt": (
        "⏳ Сколько времени потребуется, чтобы закрыть все текущие дела и приступить к обучению в нашей компании?\n"
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
    "BOT_BACKEND_URL",
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
    "get_questions_bank_meta",
    "get_questions_bank_version",
    "maybe_prime_questions_bank",
    "refresh_questions_bank",
    "TIME_FMT",
    "TIME_LIMIT",
]
