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

PROMPT_VERSION_INTERVIEW_SCRIPT = "interview_script_v1"

KB_INTERVIEW_SCRIPT_CATEGORIES = (
    "product_position",
    "od_rules",
    "objections",
    "field_day",
    "city_office",
    "general",
)


def interview_script_json_schema() -> dict[str, Any]:
    """Strict response contract for Interview Script payload."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "InterviewScriptPayload",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "risk_flags",
            "highlights",
            "checks",
            "objections",
            "script_blocks",
            "cta_templates",
        ],
        "properties": {
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


async def generate_interview_script(
    candidate_profile: dict[str, Any],
    hh_resume: dict[str, Any],
    office_context: dict[str, Any],
    *,
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

    errors: list[str] = []
    attempt = 0
    while attempt <= max(0, retries):
        attempt += 1
        system_prompt, user_prompt = interview_script_prompts(
            candidate_profile=candidate_profile,
            hh_resume_normalized=hh_resume_norm,
            office_context=office_context,
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
            validated = InterviewScriptPayload.model_validate(payload).model_dump()
            validated["risk_flags"] = merge_with_llm_flags(
                base_flags=base_flags,
                llm_flags=list(validated.get("risk_flags") or []),
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
