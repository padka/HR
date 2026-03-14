from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .prompts import interview_script_prompts
from .providers.base import AIProvider, AIProviderError, Usage
from .schemas import InterviewScriptPayload

logger = logging.getLogger(__name__)

PROMPT_VERSION_INTERVIEW_SCRIPT = "interview_script_v2"

KB_INTERVIEW_SCRIPT_CATEGORIES = (
    "product_position",
    "od_rules",
    "objections",
    "field_day",
    "city_office",
    "general",
)

SMART_SERVICE_BLOCK_ORDER = [
    "greeting_and_frame",
    "vacancy_interest_and_candidate_filters",
    "company_and_product_pitch",
    "role_and_work_format",
    "resilience_to_rejection",
    "onboarding_and_support",
    "compensation",
    "od_closing_and_confirmation",
]

SMART_SERVICE_BLOCK_DEFAULTS: dict[str, dict[str, Any]] = {
    "greeting_and_frame": {
        "title": "Вступление и рамка",
        "goal": "Установить контакт и коротко объяснить цель звонка.",
        "recruiter_text": "Здравствуйте! Проверю, как меня слышно, и за 5-7 минут пройдёмся по формату работы и следующему шагу.",
    },
    "vacancy_interest_and_candidate_filters": {
        "title": "Интерес к вакансии и базовые фильтры",
        "goal": "Понять, что важно кандидату и подходит ли ему активный формат.",
        "recruiter_text": "Подскажите, вы успели посмотреть вакансию и что для вас сейчас самое важное при выборе работы?",
    },
    "company_and_product_pitch": {
        "title": "Компания и продукт",
        "goal": "Коротко объяснить, чем занимается Smart Service и в чём ценность продукта.",
        "recruiter_text": "Мы помогаем бизнесу получать больше обращений через Яндекс.Карты: улучшаем карточку, визуал и техническую часть профиля.",
    },
    "role_and_work_format": {
        "title": "Роль и формат работы",
        "goal": "Объяснить полевой формат, график и реальную механику работы менеджера.",
        "recruiter_text": "Работа начинается из офиса, дальше менеджер едет по территории, общается с предпринимателями и договаривается о встречах.",
    },
    "resilience_to_rejection": {
        "title": "Устойчивость к отказам",
        "goal": "Понять, как кандидат выдерживает темп и негативную обратную связь.",
        "recruiter_text": "Отказы бывают у всех. Важно понять, насколько спокойно вы продолжаете диалог и держите темп.",
    },
    "onboarding_and_support": {
        "title": "Обучение и поддержка",
        "goal": "Снять тревогу по входу в роль и показать систему адаптации.",
        "recruiter_text": "На старте есть наставник и практика в полях, обычно адаптация занимает 3-5 дней.",
    },
    "compensation": {
        "title": "Доход и мотивация",
        "goal": "Объяснить систему дохода без перегруза деталями.",
        "recruiter_text": "Есть понятная система дохода: фиксированная часть плюс мотивация, либо высокий процентный формат для сильных кандидатов.",
    },
    "od_closing_and_confirmation": {
        "title": "ОД и закрепление",
        "goal": "Либо договориться об ознакомительном дне, либо корректно завершить разговор без предложения ОД.",
        "recruiter_text": "Следующий шаг зависит от итоговой релевантности: либо фиксируем ознакомительный день, либо уточняем критичные моменты и возвращаемся с решением.",
    },
}

_FRAGMENTED_LINE_RE = re.compile(r"^\s*(?:[-*•]+|\d+[\.)]|#+|>{1,3})\s*")
_HEADERISH_LINE_RE = re.compile(
    r"^\s*(?:\d+[\.)]\s*)?(?:вступление|цель|задача|компания|формат|деньги|возражения|блок|этап|проверить|спросить|уточнить|closing|cta)\b[:\s-]*$",
    flags=re.IGNORECASE,
)

_SCRIPT_RISK_REASON_MAP = {
    "AGE_BELOW_MIN": "Есть риск несоответствия возрастным требованиям офиса.",
    "NO_RELEVANT_EXPERIENCE": "Нужно проверить реальный опыт общения с клиентами и переговоров.",
    "INCOME_MISMATCH": "Ожидания по доходу могут быть выше стартовой вилки.",
    "SCHEDULE_RISK": "Есть риск несовпадения по графику и доступности.",
    "LOGISTICS_UNCLEAR": "Нужно заранее проговорить адрес, ориентиры и время выезда.",
    "RESUME_LOW_QUALITY": "По резюме мало конкретики, часть опыта лучше уточнить голосом.",
}

_INTRO_DAY_STATUS_KEYS = {
    "intro_day_scheduled",
    "intro_day_confirmed_preliminary",
    "intro_day_confirmed_day_of",
    "intro_day_declined_invitation",
    "intro_day_declined_day_of",
}


def derive_stage_strategy(
    candidate_state: dict[str, Any] | None,
    *,
    recommendation: str,
) -> dict[str, str]:
    state = candidate_state or {}
    status = str(state.get("status") or "").strip().lower()
    workflow_status = str(state.get("workflow_status") or "").strip().lower()
    slot_purpose = str(state.get("upcoming_slot_purpose") or "").strip().lower()

    if recommendation == "not_recommended" or status in {"not_hired", "interview_declined", "test2_failed"}:
        return {
            "key": "soft_closure",
            "stage_label": "Финальная сверка / мягкое закрытие",
            "call_goal": "Корректно снять ожидания, зафиксировать спорные моменты и не обещать следующий этап без внутреннего решения.",
            "guidance": "Не предлагай ознакомительный день. Говори мягко, коротко и без давления.",
        }

    if status in _INTRO_DAY_STATUS_KEYS or "intro" in workflow_status or slot_purpose == "intro_day":
        return {
            "key": "intro_day_confirmation",
            "stage_label": "Подтверждение ознакомительного дня",
            "call_goal": "Подтвердить явку, логистику, дресс-код и правила ознакомительного дня без повторного полного скрининга.",
            "guidance": "Не возвращайся к длинной презентации компании. Сфокусируйся на логистике, правилах и закреплении явки.",
        }

    if status in {"test2_sent", "test2_completed"} or workflow_status in {"test2_sent", "test2_completed"}:
        return {
            "key": "post_interview_qualification",
            "stage_label": "Квалификация после интервью",
            "call_goal": "Уточнить оставшиеся риски после интервью и, если всё сходится, закрыть кандидата на ознакомительный день.",
            "guidance": "Не дублируй холодный старт. Сделай короткое напоминание о роли и быстро переходи к оставшимся вопросам и следующему этапу.",
        }

    if status in {"interview_scheduled", "interview_confirmed", "slot_pending"} or workflow_status in {
        "interview_scheduled",
        "interview_confirmed",
    }:
        return {
            "key": "interview_confirmation",
            "stage_label": "Подтверждение собеседования",
            "call_goal": "Подтвердить участие, снять логистические и мотивационные риски и довести кандидата до встречи без повторного полного скрининга.",
            "guidance": "Скрипт должен быть короче первичного звонка: минимум повторов, максимум ясности по времени, формату и ожиданиям.",
        }

    return {
        "key": "primary_screening",
        "stage_label": "Первичный скрининг",
        "call_goal": "Понять базовую релевантность кандидата, кратко презентовать вакансию и перевести на следующий этап воронки.",
        "guidance": "Это первый полноценный разговор: выстрой контакт, проверь базовые критерии, презентуй компанию и мягко закрой на следующий шаг.",
    }


def interview_script_json_schema() -> dict[str, Any]:
    """Strict response contract for Interview Script payload."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "InterviewScriptPayload",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "stage_label",
            "call_goal",
            "conversation_script",
            "risk_flags",
            "highlights",
            "checks",
            "objections",
            "script_blocks",
            "cta_templates",
        ],
        "properties": {
            "stage_label": {"type": "string", "minLength": 1, "maxLength": 120},
            "call_goal": {"type": "string", "minLength": 1, "maxLength": 240},
            "conversation_script": {"type": "string", "minLength": 1, "maxLength": 12000},
            "risk_flags": {
                "type": "array",
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["code", "severity", "reason", "question", "recommended_phrase"],
                    "properties": {
                        "code": {"type": "string", "minLength": 1, "maxLength": 64},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                        "question": {"type": "string", "minLength": 1, "maxLength": 300},
                        "recommended_phrase": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                },
            },
            "highlights": {
                "type": "array",
                "maxItems": 12,
                "items": {"type": "string", "minLength": 1, "maxLength": 300},
            },
            "checks": {
                "type": "array",
                "maxItems": 20,
                "items": {"type": "string", "minLength": 1, "maxLength": 300},
            },
            "objections": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["topic", "candidate_says", "recruiter_answer"],
                    "properties": {
                        "topic": {"type": "string", "minLength": 1, "maxLength": 120},
                        "candidate_says": {"type": "string", "minLength": 1, "maxLength": 300},
                        "recruiter_answer": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                },
            },
            "script_blocks": {
                "type": "array",
                "minItems": 3,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "id",
                        "title",
                        "goal",
                        "recruiter_text",
                        "candidate_questions",
                        "if_answers",
                    ],
                    "properties": {
                        "id": {"type": "string", "minLength": 1, "maxLength": 64},
                        "title": {"type": "string", "minLength": 1, "maxLength": 120},
                        "goal": {"type": "string", "minLength": 1, "maxLength": 300},
                        "recruiter_text": {"type": "string", "minLength": 1, "maxLength": 1200},
                        "candidate_questions": {
                            "type": "array",
                            "maxItems": 12,
                            "items": {"type": "string", "minLength": 1, "maxLength": 300},
                        },
                        "if_answers": {
                            "type": "array",
                            "maxItems": 12,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["pattern", "hint"],
                                "properties": {
                                    "pattern": {"type": "string", "minLength": 1, "maxLength": 200},
                                    "hint": {"type": "string", "minLength": 1, "maxLength": 400},
                                },
                            },
                        },
                    },
                },
            },
            "cta_templates": {
                "type": "array",
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "text"],
                    "properties": {
                        "type": {"type": "string", "minLength": 1, "maxLength": 64},
                        "text": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                },
            },
        },
    }


def hash_resume_content(*, format: str, resume_json: dict[str, Any] | None, resume_text: str | None) -> str:
    payload = {
        "format": format,
        "resume_json": resume_json or None,
        "resume_text": (resume_text or "").strip() or None,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_total_exp_years(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(?:лет|года|год)", text.lower())
    if not m:
        return None
    try:
        years = int(m.group(1))
    except Exception:
        return None
    if years < 0 or years > 60:
        return None
    return years


def normalize_hh_resume(*, format: str, resume_json: dict[str, Any] | None, resume_text: str | None) -> dict[str, Any]:
    """Normalize HH resume data from JSON or raw text into a stable shape."""
    fmt = (format or "").strip().lower()
    if fmt not in {"json", "raw_text"}:
        raise ValueError("format must be json or raw_text")

    normalized: dict[str, Any] = {
        "source_format": fmt,
        "source_quality_ok": True,
        "headline": None,
        "summary": None,
        "skills": [],
        "relevant_experience": False,
        "total_experience_years": None,
        "employment_items": [],
    }

    if fmt == "json":
        data = resume_json or {}
        if not isinstance(data, dict):
            raise ValueError("resume_json must be an object for format=json")
        skills = data.get("skills")
        if isinstance(skills, list):
            normalized["skills"] = [str(s).strip() for s in skills if str(s).strip()][:30]
        elif isinstance(skills, str) and skills.strip():
            normalized["skills"] = [s.strip() for s in re.split(r"[,\n;]", skills) if s.strip()][:30]

        for key in ("title", "position", "specialization", "headline", "desired_position"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                normalized["headline"] = value.strip()[:200]
                break

        summary_parts: list[str] = []
        for key in ("about", "summary", "experience_summary"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                summary_parts.append(value.strip())
        exp_items = data.get("experience") or data.get("employment") or []
        if isinstance(exp_items, list):
            cleaned_items = []
            for item in exp_items[:20]:
                if isinstance(item, dict):
                    title = str(item.get("title") or item.get("position") or "").strip()
                    company = str(item.get("company") or "").strip()
                    row = {
                        "title": title[:160] or None,
                        "company": company[:160] or None,
                        "description": str(item.get("description") or "").strip()[:600] or None,
                    }
                    cleaned_items.append(row)
            normalized["employment_items"] = cleaned_items
            if cleaned_items:
                normalized["relevant_experience"] = any(
                    bool((row.get("title") or "").strip()) for row in cleaned_items
                )
        years_raw = data.get("total_experience_years")
        if isinstance(years_raw, (int, float)) and 0 <= int(years_raw) <= 60:
            normalized["total_experience_years"] = int(years_raw)

        summary = " ".join(part for part in summary_parts if part).strip()
        if not summary and normalized["employment_items"]:
            summary = "; ".join(
                f"{item.get('title') or ''} {item.get('company') or ''}".strip()
                for item in normalized["employment_items"][:5]
            )
        normalized["summary"] = summary[:1500] if summary else None

    else:
        text = (resume_text or "").strip()
        text_short = text[:9000]
        if not text_short:
            normalized["source_quality_ok"] = False
            normalized["summary"] = None
            return normalized
        lines = [ln.strip() for ln in text_short.splitlines() if ln.strip()]
        normalized["headline"] = lines[0][:200] if lines else None
        normalized["summary"] = text_short[:1500]
        normalized["total_experience_years"] = _extract_total_exp_years(text_short)

        skills_hits = []
        for token in ("продаж", "переговор", "клиент", "call", "crm", "excel", "1c", "b2b", "b2c"):
            if token in text_short.lower():
                skills_hits.append(token)
        normalized["skills"] = skills_hits[:20]
        normalized["relevant_experience"] = bool(
            normalized["total_experience_years"] or any(skills_hits)
        )
        if len(text_short) < 80:
            normalized["source_quality_ok"] = False

    return normalized


def income_mismatch(desired_income: Any, income_range: Any) -> bool:
    if not desired_income or not income_range:
        return False
    desired_str = str(desired_income)
    desired_vals = [int(x) for x in re.findall(r"\d+", desired_str) if x.isdigit()]
    if not desired_vals:
        return False
    desired = max(desired_vals)

    if isinstance(income_range, dict):
        max_val = income_range.get("max") or income_range.get("to")
        try:
            max_income = int(max_val) if max_val is not None else None
        except Exception:
            max_income = None
    else:
        vals = [int(x) for x in re.findall(r"\d+", str(income_range)) if x.isdigit()]
        max_income = max(vals) if vals else None
    if max_income is None:
        return False
    return desired > max_income


def schedule_mismatch(work_status: Any, schedule_rules: Any) -> bool:
    if not work_status or not schedule_rules:
        return False
    ws = str(work_status).lower()
    sr = str(schedule_rules).lower()
    if "учеб" in ws and ("полный день" in sr or "6/1" in sr):
        return True
    if "только вечер" in ws and "утро" in sr:
        return True
    return False


def dedupe_and_sort(flags: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    rank = {"high": 3, "medium": 2, "low": 1}
    by_code: dict[str, tuple[str, str, str]] = {}
    for code, severity, reason in flags:
        prev = by_code.get(code)
        if prev is None or rank.get(severity, 0) > rank.get(prev[1], 0):
            by_code[code] = (code, severity, reason)
    return sorted(by_code.values(), key=lambda it: rank.get(it[1], 0), reverse=True)


def build_base_risk_flags(
    candidate_profile: dict[str, Any],
    hh_resume_norm: dict[str, Any],
    office_context: dict[str, Any],
) -> list[tuple[str, str, str]]:
    flags: list[tuple[str, str, str]] = []

    age = candidate_profile.get("age_years")
    min_age = office_context.get("min_age")
    if isinstance(age, int) and isinstance(min_age, int) and age < min_age:
        flags.append(("AGE_BELOW_MIN", "high", "Возраст ниже порога офиса"))

    if office_context.get("must_have_experience") and not hh_resume_norm.get("relevant_experience"):
        flags.append(("NO_RELEVANT_EXPERIENCE", "high", "Не найден релевантный опыт"))

    if income_mismatch(candidate_profile.get("desired_income"), office_context.get("income_range")):
        flags.append(("INCOME_MISMATCH", "medium", "Ожидания по доходу выше вилки"))

    if schedule_mismatch(candidate_profile.get("work_status"), office_context.get("schedule_rules")):
        flags.append(("SCHEDULE_RISK", "medium", "Риск конфликта по графику"))

    if not office_context.get("address") or not office_context.get("landmarks"):
        flags.append(("LOGISTICS_UNCLEAR", "medium", "Недостаточно логистики для доезда"))

    if not hh_resume_norm.get("source_quality_ok"):
        flags.append(("RESUME_LOW_QUALITY", "low", "Резюме неполное/шумное, нужно уточнение"))

    return dedupe_and_sort(flags)


def _build_clarifying_question(code: str) -> str:
    mapping = {
        "AGE_BELOW_MIN": "Подтвердите, пожалуйста, ваш возраст и возможность выхода по правилам офиса?",
        "NO_RELEVANT_EXPERIENCE": "Какой у вас опыт в коммуникации с клиентами и продажах?",
        "INCOME_MISMATCH": "Какой диапазон дохода вы считаете приемлемым на старте?",
        "SCHEDULE_RISK": "Какой график для вас реально доступен в ближайший месяц?",
        "LOGISTICS_UNCLEAR": "Насколько удобно вам добираться до точки в обозначённые часы?",
        "RESUME_LOW_QUALITY": "Какие 2-3 ключевые роли/задачи были у вас в последней работе?",
    }
    return mapping.get(code, "Есть ли ограничения, которые могут повлиять на выход в ближайшие дни?")


def _build_recommended_phrase(code: str) -> str:
    mapping = {
        "AGE_BELOW_MIN": "Проверю правила офиса по возрасту и сразу вернусь с корректным маршрутом.",
        "NO_RELEVANT_EXPERIENCE": "Сфокусируемся на вашем опыте общения с людьми и формате обучения на старте.",
        "INCOME_MISMATCH": "Давайте синхронизируемся по реальной вилке и точкам роста дохода.",
        "SCHEDULE_RISK": "Подберём формат и слот, чтобы график был выполнимым без срывов.",
        "LOGISTICS_UNCLEAR": "Сейчас уточню адрес, ориентиры и окно приезда, чтобы всё было прозрачно.",
        "RESUME_LOW_QUALITY": "Чтобы не терять время, зафиксируем ваш релевантный опыт в 2-3 пунктах.",
    }
    return mapping.get(code, "Уточним это сразу и зафиксируем следующий шаг.")


def merge_with_llm_flags(
    base_flags: list[tuple[str, str, str]],
    llm_flags: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rank = {"high": 3, "medium": 2, "low": 1}
    merged: dict[str, dict[str, Any]] = {}

    for item in llm_flags:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        merged[code] = item

    for code, severity, reason in base_flags:
        if code not in merged:
            merged[code] = {
                "code": code,
                "severity": severity,
                "reason": reason,
                "question": _build_clarifying_question(code),
                "recommended_phrase": _build_recommended_phrase(code),
            }
            continue
        current = merged[code]
        if rank.get(severity, 0) > rank.get(str(current.get("severity") or "low"), 0):
            current["severity"] = severity
        if not current.get("reason"):
            current["reason"] = reason
        if not current.get("question"):
            current["question"] = _build_clarifying_question(code)
        if not current.get("recommended_phrase"):
            current["recommended_phrase"] = _build_recommended_phrase(code)

    return sorted(
        merged.values(),
        key=lambda x: rank.get(str(x.get("severity") or "low"), 0),
        reverse=True,
    )


@dataclass(frozen=True)
class ScriptGenerationResult:
    payload: dict[str, Any]
    usage: Usage


def _normalize_script_block(block_id: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(SMART_SERVICE_BLOCK_DEFAULTS[block_id])
    src = payload if isinstance(payload, dict) else {}
    return {
        "id": block_id,
        "title": str(src.get("title") or base["title"])[:120],
        "goal": str(src.get("goal") or base["goal"])[:300],
        "recruiter_text": str(src.get("recruiter_text") or base["recruiter_text"])[:1200],
        "candidate_questions": [
            str(item).strip()[:300]
            for item in (src.get("candidate_questions") or [])
            if str(item).strip()
        ][:12],
        "if_answers": [
            {
                "pattern": str(item.get("pattern") or "").strip()[:200],
                "hint": str(item.get("hint") or "").strip()[:400],
            }
            for item in (src.get("if_answers") or [])
            if isinstance(item, dict) and str(item.get("pattern") or "").strip() and str(item.get("hint") or "").strip()
        ][:12],
    }


def _clean_sentence(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value.strip(" -•*")


def _sanitize_conversation_script(text: Any) -> str:
    raw = str(text or "").replace("\r", "\n")
    if not raw.strip():
        return ""

    lines = []
    for source_line in raw.splitlines():
        line = source_line.strip()
        if not line:
            lines.append("")
            continue
        line = _FRAGMENTED_LINE_RE.sub("", line)
        line = re.sub(r"^\*\*(.*?)\*\*$", r"\1", line)
        line = re.sub(r"^_{1,3}(.*?)_{1,3}$", r"\1", line)
        line = line.strip(" -")
        if not line or _HEADERISH_LINE_RE.match(line):
            continue
        lines.append(line)

    paragraphs: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if not line:
            if buffer:
                paragraphs.append(_clean_sentence(" ".join(buffer)))
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        paragraphs.append(_clean_sentence(" ".join(buffer)))

    cleaned: list[str] = []
    for paragraph in paragraphs:
        normalized = _clean_sentence(paragraph)
        if not normalized:
            continue
        if cleaned and cleaned[-1] == normalized:
            continue
        cleaned.append(normalized)
    return "\n\n".join(cleaned)[:12000]


def _looks_fragmented_conversation(text: str) -> bool:
    cleaned = _sanitize_conversation_script(text)
    if not cleaned:
        return True
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return True
    bulletish = sum(1 for line in lines if _FRAGMENTED_LINE_RE.match(line) or _HEADERISH_LINE_RE.match(line))
    short_lines = sum(1 for line in lines if len(line) < 48)
    return (bulletish / len(lines)) >= 0.25 or (short_lines / len(lines)) >= 0.5


def _conversation_paragraph_from_block(block: dict[str, Any]) -> str:
    parts: list[str] = []
    recruiter_text = _clean_sentence(str(block.get("recruiter_text") or ""))
    if recruiter_text:
        parts.append(recruiter_text)
    questions = [
        _clean_sentence(str(item))
        for item in (block.get("candidate_questions") or [])
        if _clean_sentence(str(item))
    ]
    if questions:
        for question in questions[:2]:
            if question.lower() in recruiter_text.lower():
                continue
            if not question.endswith("?"):
                question = f"{question}?"
            parts.append(question)
    return " ".join(part for part in parts if part).strip()


def _compose_conversation_script(
    *,
    script: dict[str, Any],
    candidate_state: dict[str, Any],
    office_context: dict[str, Any],
    scorecard: dict[str, Any] | None,
) -> str:
    stage_strategy = derive_stage_strategy(
        candidate_state,
        recommendation=str((scorecard or {}).get("recommendation") or "clarify_before_od"),
    )
    recommendation = str((scorecard or {}).get("recommendation") or "clarify_before_od")
    blocks = list(script.get("script_blocks") or [])
    block_by_id = {str(item.get("id") or ""): item for item in blocks if isinstance(item, dict)}

    if stage_strategy["key"] == "interview_confirmation":
        greeting = _conversation_paragraph_from_block(block_by_id.get("greeting_and_frame") or {})
        filters = _conversation_paragraph_from_block(block_by_id.get("vacancy_interest_and_candidate_filters") or {})
        return _sanitize_conversation_script(
            "\n\n".join(
                paragraph
                for paragraph in [
                    greeting
                    or "Здравствуйте. Хочу коротко подтвердить нашу встречу и проверить, что по времени и формату всё по-прежнему удобно.",
                    filters
                    or "Подскажите, пожалуйста, ничего не изменилось по графику, дороге и готовности созвониться или приехать в назначённое время?",
                    "С моей стороны задача простая: снять последние бытовые и мотивационные вопросы, чтобы собеседование прошло спокойно и без сюрпризов. Если что-то поменялось по занятости, дороге или ожиданиям от вакансии, лучше проговорить это сейчас, чтобы мы сразу скорректировали план.",
                    "Если участие подтверждаете, я закрепляю за вами встречу, ещё раз отправляю детали по времени и формату и остаюсь на связи, если понадобится перенос или короткое уточнение.",
                ]
                if paragraph
            )
        )[:12000]
    elif stage_strategy["key"] == "post_interview_qualification":
        selected_ids = [
            "greeting_and_frame",
            "company_and_product_pitch",
            "role_and_work_format",
            "resilience_to_rejection",
            "compensation",
            "od_closing_and_confirmation",
        ]
    elif stage_strategy["key"] == "intro_day_confirmation":
        city = str(office_context.get("city") or "городу").strip()
        address = str(office_context.get("address") or "").strip()
        logistics = f" Офис: {address}." if address else ""
        return (
            f"Здравствуйте. Хочу коротко подтвердить ваш ознакомительный день по вакансии Smart Service в городе {city}.{logistics} "
            "Напомню, что это практический этап примерно на полтора-два часа: вы вместе с наставником увидите, как выглядит работа вживую, и сможете задать все вопросы по формату, задачам и обучению.\n\n"
            "Пожалуйста, подтвердите, что время вам по-прежнему подходит, как планируете добираться и во сколько нужно выехать, чтобы приехать спокойно и без опоздания. Сразу напомню про аккуратный деловой или smart-casual вид и просьбу предупредить заранее, если что-то поменяется.\n\n"
            "Если всё в силе, я закрепляю за вами слот и прошу одним сообщением написать подтверждение, что вы будете в назначенное время. Если нужен перенос, лучше согласуем его сейчас, чтобы не терять этап."
        )[:12000]
    elif stage_strategy["key"] == "soft_closure":
        return (
            "Здравствуйте. Спасибо, что нашли время выйти на связь. Я коротко сверю несколько моментов, чтобы не дать вам неверных ожиданий по следующему этапу.\n\n"
            "По тем данным, которые у нас уже есть, сейчас есть спорные точки, которые требуют внутренней проверки. Поэтому я не буду обещать следующий этап или быстрый переход дальше, пока не сверю их с правилами офиса и действующими критериями.\n\n"
            "Если захотите, можете коротко добавить всё важное по опыту, готовности к формату и срокам выхода. После этого я зафиксирую информацию и вернусь к вам с итогом без лишних обещаний."
        )[:12000]
    else:
        selected_ids = SMART_SERVICE_BLOCK_ORDER

    paragraphs: list[str] = []
    for block_id in selected_ids:
        block = block_by_id.get(block_id)
        if not isinstance(block, dict):
            continue
        paragraph = _conversation_paragraph_from_block(block)
        if paragraph:
            paragraphs.append(paragraph)

    if recommendation == "clarify_before_od" and paragraphs:
        paragraphs[-1] = (
            f"{paragraphs[-1]} Сначала хочу подтвердить один-два критичных момента по формату и доступности, "
            "и если всё сходится, сразу зафиксируем следующий этап."
        )[:1500]
    elif recommendation == "od_recommended" and paragraphs:
        paragraphs[-1] = (
            f"{paragraphs[-1]} Если по разговору видим, что базовые критерии совпадают, сразу предложу конкретное время следующего этапа и закреплю детали сообщением."
        )[:1500]

    return _sanitize_conversation_script("\n\n".join(paragraphs))[:12000]


def _normalize_script_payload(
    script: dict[str, Any],
    *,
    recommendation: str,
    candidate_state: dict[str, Any] | None = None,
    office_context: dict[str, Any] | None = None,
    scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocks_by_id: dict[str, dict[str, Any]] = {}
    for block in list(script.get("script_blocks") or []):
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "").strip()
        if block_id:
            blocks_by_id[block_id] = block

    normalized_blocks = [
        _normalize_script_block(block_id, blocks_by_id.get(block_id))
        for block_id in SMART_SERVICE_BLOCK_ORDER
    ]
    script["script_blocks"] = normalized_blocks
    stage_strategy = derive_stage_strategy(candidate_state, recommendation=recommendation)
    script["stage_label"] = str(script.get("stage_label") or stage_strategy["stage_label"])[:120]
    script["call_goal"] = str(script.get("call_goal") or stage_strategy["call_goal"])[:240]

    if recommendation == "not_recommended":
        script["cta_templates"] = [
            {
                "type": "soft_close",
                "text": "Спасибо за разговор. Зафиксирую уточнения и вернусь с итогом после внутренней сверки по критериям.",
            }
        ]
        closing = normalized_blocks[-1]
        closing["recruiter_text"] = (
            "Сейчас не буду обещать следующий этап. Корректно зафиксирую риски и вернусь к вам с итогом после внутренней проверки."
        )
        closing["candidate_questions"] = ["Есть ли что-то важное, что вы хотите добавить перед финальной сверкой?"]
        closing["if_answers"] = [
            {
                "pattern": "просит решение сейчас",
                "hint": "Спокойно объяснить, что без проверки по критериям обещать следующий этап нельзя.",
            }
        ]
    elif recommendation == "clarify_before_od":
        existing = [item for item in (script.get("cta_templates") or []) if isinstance(item, dict)]
        existing.append(
            {
                "type": "conditional_od",
                "text": "Если подтверждаем критичные моменты по формату и доступности, сразу фиксируем ознакомительный день.",
            }
        )
        script["cta_templates"] = existing[:10]
        closing = normalized_blocks[-1]
        if "условно" not in closing["recruiter_text"].lower():
            closing["recruiter_text"] = (
                f"{closing['recruiter_text']} Сначала уточним 1-2 критичных момента, после этого смогу закрепить вас на ОД."
            )[:1200]
    else:
        has_od = any(
            "ознаком" in str(item.get("text") or "").lower()
            for item in (script.get("cta_templates") or [])
            if isinstance(item, dict)
        )
        if not has_od:
            existing = [item for item in (script.get("cta_templates") or []) if isinstance(item, dict)]
            existing.append(
                {
                    "type": "od_confirm",
                    "text": "Подтверждаю ознакомительный день и сразу отправляю время, адрес, дресс-код и просьбу подтвердить явку сообщением.",
                }
            )
            script["cta_templates"] = existing[:10]

    raw_conversation = _sanitize_conversation_script(script.get("conversation_script"))
    if not raw_conversation or _looks_fragmented_conversation(str(script.get("conversation_script") or "")):
        raw_conversation = _compose_conversation_script(
            script=script,
            candidate_state=candidate_state or {},
            office_context=office_context or {},
            scorecard=scorecard,
        )
    script["conversation_script"] = _sanitize_conversation_script(raw_conversation)[:12000]
    return script


def build_interview_script_fallback(
    *,
    candidate_state: dict[str, Any] | None,
    candidate_profile: dict[str, Any],
    office_context: dict[str, Any],
    scorecard: dict[str, Any] | None,
    base_flags: list[tuple[str, str, str]],
) -> dict[str, Any]:
    recommendation = str((scorecard or {}).get("recommendation") or "clarify_before_od")
    stage_strategy = derive_stage_strategy(candidate_state, recommendation=recommendation)
    vacancy = str(office_context.get("vacancy") or "вакансия Smart Service").strip()
    city = str(office_context.get("city") or "ваш город").strip()
    address = str(office_context.get("address") or "").strip()
    logistics_tail = f" Офис: {address}." if address else ""
    work_experience = str(candidate_profile.get("work_experience") or "").strip()
    motivation = str(candidate_profile.get("motivation") or "").strip()

    blockers = (scorecard or {}).get("blockers") or []
    missing_data = (scorecard or {}).get("missing_data") or []
    metrics = (scorecard or {}).get("metrics") or []
    met_metrics = [
        item for item in metrics if isinstance(item, dict) and str(item.get("status") or "").strip().lower() == "met"
    ]
    unknown_metrics = [
        item for item in metrics if isinstance(item, dict) and str(item.get("status") or "").strip().lower() == "unknown"
    ]

    risk_flags: list[dict[str, Any]] = []
    for code, severity, reason in base_flags[:4]:
        risk_flags.append(
            {
                "code": code,
                "severity": severity,
                "reason": _SCRIPT_RISK_REASON_MAP.get(code, reason),
                "question": _build_clarifying_question(code),
                "recommended_phrase": _build_recommended_phrase(code),
            }
        )
    for item in blockers[:2]:
        if not isinstance(item, dict):
            continue
        risk_flags.append(
            {
                "code": str(item.get("key") or "BLOCKER").upper()[:64],
                "severity": "high",
                "reason": str(item.get("label") or item.get("evidence") or "Есть критичный риск.")[:500],
                "question": "Подтвердите, пожалуйста, этот момент простыми словами, чтобы я не делал неверных обещаний по следующему этапу.",
                "recommended_phrase": "Сейчас корректно зафиксирую этот риск и не буду обещать следующий этап без внутренней проверки.",
            }
        )
    deduped_flags: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for item in risk_flags:
        code = str(item.get("code") or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        deduped_flags.append(item)
    risk_flags = deduped_flags[:8]

    highlights: list[str] = []
    if work_experience:
        highlights.append(f"Опыт кандидата: {work_experience[:140]}")
    if motivation:
        highlights.append(f"Мотивация: {motivation[:140]}")
    for item in met_metrics[:3]:
        highlights.append(str(item.get("label") or item.get("evidence") or "").strip()[:180])
    if not highlights:
        highlights.append(f"Фокус на вакансии {vacancy} в городе {city}.")

    checks: list[str] = []
    for item in blockers[:3]:
        if not isinstance(item, dict):
            continue
        checks.append(str(item.get("evidence") or item.get("label") or "").strip()[:200])
    for item in missing_data[:3]:
        if not isinstance(item, dict):
            continue
        checks.append(str(item.get("evidence") or item.get("label") or "").strip()[:200])
    for item in unknown_metrics[:2]:
        if not isinstance(item, dict):
            continue
        checks.append(f"Уточнить: {str(item.get('label') or item.get('evidence') or '').strip()[:180]}")
    if not checks:
        checks.append("Проверить готовность к полевому формату и ближайшему выходу.")

    objections = [
        {
            "topic": "Доход",
            "candidate_says": "Хочу понять, какой доход реально можно сделать на старте.",
            "recruiter_answer": "Коротко и честно объясните стартовую систему выплат, от чего растёт доход и какой формат подойдёт именно ему.",
        },
        {
            "topic": "Разъездной формат",
            "candidate_says": "Я не до конца понимаю, насколько это выездная работа.",
            "recruiter_answer": "Спокойно раскройте реальный ритм дня: старт из офиса, территория, встречи с предпринимателями и поддержка наставника на входе.",
        },
        {
            "topic": "Без опыта",
            "candidate_says": "У меня мало прямого опыта продаж.",
            "recruiter_answer": "Сделайте акцент на обучении 3-5 дней, наставнике и том, что важнее коммуникация и темп, чем идеально релевантный прошлый опыт.",
        },
    ]

    short_pitch = (
        "Мы помогаем бизнесу получать больше обращений через Яндекс.Карты: обновляем карточку, усиливаем визуал и технически оптимизируем профиль."
    )
    long_pitch = (
        "Мы берём профиль бизнеса на обслуживание под ключ: делаем профессиональную съёмку или 3D-панораму, обновляем карточку, контакты, описание и визуальную часть, "
        "а также технически оптимизируем профиль, чтобы он выше показывался в поиске и собирал больше просмотров."
    )
    pitch_text = long_pitch if recommendation != "not_recommended" else short_pitch

    script = {
        "stage_label": stage_strategy["stage_label"],
        "call_goal": stage_strategy["call_goal"],
        "conversation_script": "",
        "risk_flags": risk_flags,
        "highlights": highlights[:8],
        "checks": checks[:10],
        "objections": objections,
        "script_blocks": [
            {
                "id": "greeting_and_frame",
                "recruiter_text": (
                    f"Здравствуйте! Как меня слышно? Коротко пройдёмся по вакансии {vacancy}, формату работы и следующему шагу.{logistics_tail}"
                ),
                "candidate_questions": [
                    "Удобно ли сейчас говорить 5-7 минут?",
                    "Вы успели посмотреть вакансию до отклика?",
                ],
            },
            {
                "id": "vacancy_interest_and_candidate_filters",
                "recruiter_text": (
                    "Подскажите, что для вас сейчас важнее всего при выборе работы: доход, график, развитие, стабильность или коллектив? "
                    "И насколько вам комфортна работа, где много живого общения и движения в течение дня?"
                ),
                "candidate_questions": [
                    "Сколько времени вам добираться до офиса?",
                    "Был ли опыт постоянного общения с людьми вживую?",
                ],
            },
            {
                "id": "company_and_product_pitch",
                "recruiter_text": pitch_text,
                "candidate_questions": [
                    "Насколько вам в целом интересен продукт, связанный с продвижением бизнеса на Яндекс.Картах?",
                    "Как бы оценили интерес к такой роли по шкале от 1 до 10?",
                ],
            },
            {
                "id": "role_and_work_format",
                "recruiter_text": (
                    "График у нас 5/2, с 9:00 до 18:00. День начинается в офисе, дальше менеджер работает на закреплённой территории, знакомится с предпринимателями "
                    "и переводит интерес в полноценные переговоры."
                ),
                "candidate_questions": [
                    "Насколько вам подходит полевой формат без постоянного сидения в офисе?",
                    "Если будет нужно быстро выйти на обучение, это реалистично для вас?",
                ],
            },
            {
                "id": "resilience_to_rejection",
                "recruiter_text": (
                    "Отказы в такой работе бывают регулярно. Для меня важно понять, насколько спокойно вы продолжаете разговор, когда слышите «неинтересно» или «нет времени»."
                ),
                "candidate_questions": [
                    "Как обычно реагируете на отказ или жёсткий ответ?",
                ],
            },
            {
                "id": "onboarding_and_support",
                "recruiter_text": (
                    "Опыт в продажах не обязателен: на старте есть наставник и внутренняя школа, обычно адаптация занимает 3-5 дней, всё показывают на практике."
                ),
                "candidate_questions": [
                    "Насколько вам комфортен вход через обучение и разбор реальных кейсов?",
                ],
            },
            {
                "id": "compensation",
                "recruiter_text": (
                    "По деньгам всё прозрачно: есть фиксированная часть плюс мотивация, а для сильных кандидатов возможен формат с большей переменной частью."
                ),
                "candidate_questions": [
                    "Какой формат вам ближе: больше стабильности или больше переменной части за результат?",
                ],
            },
            {
                "id": "od_closing_and_confirmation",
                "recruiter_text": (
                    "Если видим, что по базовым критериям всё ок, следующим шагом фиксируем ознакомительный день на 1.5-2 часа с наставником."
                ),
                "candidate_questions": [
                    "Если мы подходим друг другу, готовы двигаться к следующему этапу без долгой паузы?",
                ],
            },
        ],
        "cta_templates": [],
    }
    return _normalize_script_payload(
        script,
        recommendation=recommendation,
        candidate_state=candidate_state,
        office_context=office_context,
        scorecard=scorecard,
    )


async def generate_interview_script(
    candidate_state: dict[str, Any],
    candidate_profile: dict[str, Any],
    hh_resume: dict[str, Any],
    office_context: dict[str, Any],
    *,
    scorecard: dict[str, Any],
    rag_context: list[dict[str, Any]],
    provider: AIProvider,
    model: str,
    timeout_seconds: int,
    max_tokens: int,
    retries: int = 2,
) -> ScriptGenerationResult:
    """Generate interview script via provider with strict schema validation + retries."""
    hh_resume_norm = hh_resume if isinstance(hh_resume, dict) else {}
    base_flags = build_base_risk_flags(candidate_profile, hh_resume_norm, office_context)
    base_risk_hints = [
        {"code": code, "severity": severity, "reason": reason}
        for code, severity, reason in base_flags
    ]
    stage_strategy = derive_stage_strategy(
        candidate_state,
        recommendation=str((scorecard or {}).get("recommendation") or "clarify_before_od"),
    )

    errors: list[str] = []
    attempt = 0
    while attempt <= max(0, retries):
        attempt += 1
        system_prompt, user_prompt = interview_script_prompts(
            candidate_state=candidate_state,
            stage_strategy=stage_strategy,
            candidate_profile=candidate_profile,
            hh_resume_normalized=hh_resume_norm,
            office_context=office_context,
            scorecard=scorecard,
            rag_context=rag_context,
            base_risk_hints=base_risk_hints,
        )
        if errors:
            user_prompt += (
                "\nPrevious validation errors (fix them and return valid JSON):\n"
                + "\n".join(f"- {e}" for e in errors[-6:])
            )
        try:
            payload, usage = await provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(timeout_seconds),
                max_tokens=max(512, int(max_tokens)),
            )
            normalized_payload = _normalize_script_payload(
                dict(payload) if isinstance(payload, dict) else {},
                recommendation=str((scorecard or {}).get("recommendation") or "clarify_before_od"),
                candidate_state=candidate_state,
                office_context=office_context,
                scorecard=scorecard,
            )
            validated = InterviewScriptPayload.model_validate(normalized_payload).model_dump()
            validated["risk_flags"] = merge_with_llm_flags(
                base_flags=base_flags,
                llm_flags=list(validated.get("risk_flags") or []),
            )
            validated = _normalize_script_payload(
                validated,
                recommendation=str((scorecard or {}).get("recommendation") or "clarify_before_od"),
                candidate_state=candidate_state,
                office_context=office_context,
                scorecard=scorecard,
            )
            return ScriptGenerationResult(payload=validated, usage=usage)
        except (ValidationError, AIProviderError, ValueError) as exc:
            logger.warning(
                "ai.interview_script.validation_failed",
                extra={"attempt": attempt, "error": exc.__class__.__name__},
            )
            errors.append(str(exc))
            if attempt > max(0, retries):
                raise

    raise RuntimeError("interview script generation failed")
