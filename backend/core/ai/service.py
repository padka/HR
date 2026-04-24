"""AIService — central facade for all AI Copilot operations.

Responsibilities:
- Cache management (check / store AI outputs with TTL).
- Quota enforcement (per-principal daily requests, global daily budget).
- Request logging (tokens, latency, status → AIRequestLog table).
- Provider dispatch (OpenAI or Fake).

All public methods follow the same pattern:
  ensure_enabled → build context → check cache → ensure quota → generate → log → store → return.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain import analytics
from backend.domain.ai.models import (
    AIAgentMessage,
    AIAgentThread,
    AIInterviewScriptFeedback,
    AIOutput,
    AIRequestLog,
    CandidateHHResume,
)
from backend.domain.candidates.models import User
from backend.domain.models import City, Recruiter, Vacancy

from .candidate_scorecard import (
    OBJECTIVE_WEIGHTS,
    SEMANTIC_WEIGHTS,
    build_candidate_scorecard,
    fit_level_from_score,
)
from .context import (
    build_candidate_ai_context,
    build_city_candidate_recommendations_context,
    compute_input_hash,
    get_last_inbound_message_text,
)
from .interview_script_builder import build_structured_interview_script
from .llm_script_generator import (
    KB_INTERVIEW_SCRIPT_CATEGORIES,
    PROMPT_VERSION_INTERVIEW_SCRIPT,
    build_base_risk_flags,
    build_interview_script_fallback,
    generate_interview_script,
    hash_resume_content,
    normalize_hh_resume,
)
from .prompts import (
    agent_chat_reply_prompts,
    candidate_coach_drafts_prompts,
    candidate_coach_prompts,
    candidate_contact_draft_prompts,
    candidate_facts_prompts,
    candidate_summary_prompts,
    chat_reply_drafts_prompts,
    city_candidate_recommendations_prompts,
    dashboard_insight_prompts,
    recruiter_next_best_action_prompts,
)
from .providers import AIProvider, AIProviderError, FakeProvider, OpenAIProvider
from .redaction import redact_text
from .schemas import (
    AgentChatReplyV1,
    CandidateCoachV1,
    CandidateContactDraftsV1,
    CandidateFactsV1,
    CandidateSummaryV1,
    ChatReplyDraftsV1,
    CityCandidateRecommendationsV1,
    DashboardInsightV1,
    InterviewScriptFeedbackPayload,
    InterviewScriptPayload,
    RecruiterNextBestActionV1,
)

logger = logging.getLogger(__name__)
_CANDIDATE_AI_KINDS = (
    "candidate_summary_v1",
    "candidate_coach_v1",
    "candidate_facts_v1",
    "recruiter_next_best_action_v1",
    "candidate_contact_draft_v1",
    "interview_script_v1",
)


class AIDisabledError(RuntimeError):
    """Raised when AI is invoked but ``AI_ENABLED`` is falsy."""


class AIRateLimitedError(RuntimeError):
    """Raised when the principal exceeds daily request limit or budget."""


@dataclass(frozen=True)
class AIResult:
    """Immutable wrapper for an AI generation result."""

    payload: dict
    cached: bool
    input_hash: str


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    try:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    except Exception:
        return None


def _provider_for_settings() -> AIProvider:
    """Instantiate the AI provider from current settings (openai or fake)."""
    settings = get_settings()
    provider = (settings.ai_provider or "").strip().lower()
    if provider == "fake":
        return FakeProvider()
    return OpenAIProvider(settings)


async def _count_today_requests(principal: Principal) -> int:
    """Count AI requests made by *principal* since midnight UTC today."""
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    async with async_session() as session:
        total = await session.scalar(
            select(func.count(AIRequestLog.id))
            .where(
                AIRequestLog.principal_type == principal.type,
                AIRequestLog.principal_id == principal.id,
                AIRequestLog.created_at >= start,
            )
        )
        return int(total or 0)


async def _estimate_today_spend_usd() -> float:
    """Rough estimate of today's AI spend based on logged tokens.

    Uses approximate GPT-5-mini pricing: $0.30/1M input, $1.20/1M output.
    For other models the estimate is conservative (higher cost assumed).
    """
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    async with async_session() as session:
        row = await session.execute(
            select(
                func.coalesce(func.sum(AIRequestLog.tokens_in), 0),
                func.coalesce(func.sum(AIRequestLog.tokens_out), 0),
            ).where(
                AIRequestLog.created_at >= start,
                AIRequestLog.status == "ok",
            )
        )
        tokens_in, tokens_out = row.one()
    # Conservative estimate (GPT-5 mini pricing)
    cost_in = float(tokens_in or 0) / 1_000_000 * 0.30
    cost_out = float(tokens_out or 0) / 1_000_000 * 1.20
    return cost_in + cost_out


async def _log_request(
    *,
    principal: Principal,
    scope_type: str,
    scope_id: int,
    kind: str,
    provider: str,
    model: str,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
    status_value: str,
    error_code: str = "",
) -> None:
    """Persist an AI request log row (tokens, latency, status) for auditing and budget tracking."""
    async with async_session() as session:
        row = AIRequestLog(
            principal_type=principal.type,
            principal_id=principal.id,
            scope_type=scope_type,
            scope_id=scope_id,
            kind=kind,
            provider=provider,
            model=model or "",
            latency_ms=int(latency_ms),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            status=status_value,
            error_code=error_code or "",
            created_at=datetime.now(UTC),
        )
        session.add(row)
        await session.commit()


async def _get_cached_output(
    *,
    scope_type: str,
    scope_id: int,
    kind: str,
    input_hash: str,
) -> AIOutput | None:
    """Fetch a non-expired cached AI output matching scope + input hash."""
    now = datetime.now(UTC)
    async with async_session() as session:
        row = await session.scalar(
            select(AIOutput)
            .where(
                AIOutput.scope_type == scope_type,
                AIOutput.scope_id == scope_id,
                AIOutput.kind == kind,
                AIOutput.input_hash == input_hash,
                AIOutput.expires_at > now,
            )
            .order_by(AIOutput.created_at.desc(), AIOutput.id.desc())
            .limit(1)
        )
        return row


async def _store_output(
    *,
    scope_type: str,
    scope_id: int,
    kind: str,
    input_hash: str,
    payload: dict,
    ttl_hours: int = 24,
) -> None:
    """Upsert a cached AI output (creates or updates existing row for the same scope/kind/hash)."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=ttl_hours)
    async with async_session() as session:
        try:
            existing = await session.scalar(
                select(AIOutput).where(
                    AIOutput.scope_type == scope_type,
                    AIOutput.scope_id == scope_id,
                    AIOutput.kind == kind,
                    AIOutput.input_hash == input_hash,
                )
            )
            if existing is not None:
                existing.payload_json = payload
                existing.expires_at = expires_at
                existing.created_at = now
            else:
                session.add(
                    AIOutput(
                        scope_type=scope_type,
                        scope_id=scope_id,
                        kind=kind,
                        input_hash=input_hash,
                        payload_json=payload,
                        created_at=now,
                        expires_at=expires_at,
                    )
                )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(AIOutput).where(
                    AIOutput.scope_type == scope_type,
                    AIOutput.scope_id == scope_id,
                    AIOutput.kind == kind,
                    AIOutput.input_hash == input_hash,
                )
            )
            if existing is not None:
                existing.payload_json = payload
                existing.expires_at = expires_at
                existing.created_at = now
                await session.commit()
            else:
                raise


def _normalized_resume_context(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    employment_items = value.get("employment_items")
    if not isinstance(employment_items, list):
        employment_items = []
    return {
        "source_format": value.get("source_format"),
        "source_quality_ok": bool(value.get("source_quality_ok")),
        "headline": value.get("headline"),
        "summary": value.get("summary"),
        "skills": list(value.get("skills") or []),
        "employment_items": employment_items[:10],
        "relevant_experience": bool(value.get("relevant_experience")),
    }


def _scorecard_payload(scorecard_state: Any) -> dict[str, Any]:
    return {
        "final_score": scorecard_state.final_score,
        "objective_score": scorecard_state.objective_score,
        "semantic_score": scorecard_state.semantic_score,
        "recommendation": scorecard_state.recommendation,
        "metrics": list(scorecard_state.metrics),
        "blockers": list(scorecard_state.blockers),
        "missing_data": list(scorecard_state.missing_data),
    }


def _criteria_used_from_context(ctx: dict[str, Any]) -> bool:
    city_profile = ctx.get("city_profile") or {}
    kb = ctx.get("knowledge_base") or {}
    return bool(city_profile.get("criteria") or (kb.get("excerpts") or []))


def _scorecard_fit_rationale(scorecard: dict[str, Any] | None) -> str:
    if not isinstance(scorecard, dict):
        return ""
    blockers = scorecard.get("blockers") or []
    if blockers and isinstance(blockers[0], dict):
        return str(blockers[0].get("evidence") or blockers[0].get("label") or "").strip()
    missing = scorecard.get("missing_data") or []
    if missing and isinstance(missing[0], dict):
        return str(missing[0].get("evidence") or missing[0].get("label") or "").strip()
    recommendation = str(scorecard.get("recommendation") or "").strip().lower()
    if recommendation == "od_recommended":
        return "Базовый профиль кандидата соответствует критериям и допускает приглашение на ознакомительный день."
    if recommendation == "clarify_before_od":
        return "Кандидат в целом релевантен, но перед приглашением на ознакомительный день нужны уточнения."
    if recommendation == "not_recommended":
        return "Есть объективные стоп-факторы или непрохождение ключевых регламентных требований."
    return ""


def _apply_candidate_summary_scorecard(
    *,
    context: dict[str, Any],
    resume_context: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    summary = CandidateSummaryV1.model_validate(payload).model_dump()
    scorecard_source = summary.get("scorecard") if isinstance(summary.get("scorecard"), dict) else None
    llm_scorecard_input = scorecard_source
    if isinstance(scorecard_source, dict):
        raw_metrics = scorecard_source.get("metrics") or []
        metric_keys = {
            str(item.get("key") or "").strip()
            for item in raw_metrics
            if isinstance(item, dict)
        }
        if metric_keys & set(OBJECTIVE_WEIGHTS):
            llm_scorecard_input = {
                "metrics": [
                    item
                    for item in raw_metrics
                    if isinstance(item, dict) and str(item.get("key") or "").strip() in set(SEMANTIC_WEIGHTS)
                ],
                "blockers": list(scorecard_source.get("blockers") or []),
                "missing_data": list(scorecard_source.get("missing_data") or []),
            }
    scorecard_state = build_candidate_scorecard(
        context=context,
        resume_context=resume_context,
        llm_scorecard=llm_scorecard_input,
    )
    scorecard = _scorecard_payload(scorecard_state)
    fit = dict(summary.get("fit") or {})
    fit["score"] = scorecard["final_score"]
    fit["level"] = fit_level_from_score(scorecard["final_score"])
    fit["criteria_used"] = bool(fit.get("criteria_used") or _criteria_used_from_context(context))
    fit["rationale"] = str(fit.get("rationale") or "").strip() or _scorecard_fit_rationale(scorecard)
    summary["fit"] = fit
    summary["scorecard"] = scorecard
    return CandidateSummaryV1.model_validate(summary).model_dump()


def _apply_candidate_coach_score(
    *,
    payload: dict[str, Any],
    scorecard: dict[str, Any] | None,
    criteria_used: bool,
) -> dict[str, Any]:
    coach = CandidateCoachV1.model_validate(payload).model_dump()
    if isinstance(scorecard, dict):
        final_score = scorecard.get("final_score")
        if isinstance(final_score, int):
            coach["relevance_score"] = final_score
            coach["relevance_level"] = fit_level_from_score(final_score)
        if not str(coach.get("rationale") or "").strip():
            coach["rationale"] = _scorecard_fit_rationale(scorecard)
    coach["criteria_used"] = bool(coach.get("criteria_used") or criteria_used)
    return CandidateCoachV1.model_validate(coach).model_dump()


def _scorecard_risk_items(scorecard: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(scorecard, dict):
        return []
    items: list[dict[str, Any]] = []
    for blocker in list(scorecard.get("blockers") or []):
        if not isinstance(blocker, dict):
            continue
        items.append(
            {
                "key": str(blocker.get("key") or "blocker"),
                "severity": "high",
                "label": str(blocker.get("label") or blocker.get("key") or "Критичный риск"),
                "explanation": str(blocker.get("evidence") or blocker.get("label") or "").strip(),
            }
        )
    for item in list(scorecard.get("missing_data") or []):
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "key": str(item.get("key") or "missing_data"),
                "severity": "medium",
                "label": str(item.get("label") or item.get("key") or "Нужны уточнения"),
                "explanation": str(item.get("evidence") or item.get("label") or "").strip(),
            }
        )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:6]


def _summary_tldr_from_scorecard(scorecard: dict[str, Any], *, candidate_city: str | None) -> str:
    final_score = scorecard.get("final_score")
    recommendation = str(scorecard.get("recommendation") or "").strip().lower()
    blockers = scorecard.get("blockers") or []
    missing_data = scorecard.get("missing_data") or []
    city_tail = f" по городу {candidate_city}" if candidate_city else ""
    if blockers and isinstance(blockers[0], dict):
        return (
            f"Кандидат сейчас не проходит по ключевым критериям{city_tail}. "
            f"Оценка {final_score}/100, основной стоп-фактор: {blockers[0].get('label') or blockers[0].get('evidence')}."
        )
    if recommendation == "od_recommended":
        return f"Кандидат выглядит релевантным{city_tail} и может двигаться к следующему этапу. Оценка {final_score}/100."
    if missing_data and isinstance(missing_data[0], dict):
        return (
            f"Кандидат потенциально подходит{city_tail}, но перед следующим этапом нужно снять несколько вопросов. "
            f"Оценка {final_score}/100, в первую очередь: {missing_data[0].get('label') or missing_data[0].get('evidence')}."
        )
    return f"Кандидат оценён на {final_score}/100. Решение требует дополнительной проверки по контексту и регламентам."


def _build_candidate_summary_fallback(
    *,
    context: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    metrics = [item for item in list(scorecard.get("metrics") or []) if isinstance(item, dict)]
    met_metrics = [item for item in metrics if str(item.get("status") or "").strip().lower() == "met"]
    not_met_metrics = [item for item in metrics if str(item.get("status") or "").strip().lower() == "not_met"]
    latest_tests = ((context.get("tests") or {}).get("latest") or {}) if isinstance(context.get("tests"), dict) else {}
    candidate = context.get("candidate") or {}
    candidate_profile = context.get("candidate_profile") or {}
    candidate_city = candidate.get("city") if isinstance(candidate, dict) else None
    recommendation = str(scorecard.get("recommendation") or "clarify_before_od").strip().lower()
    final_score = scorecard.get("final_score")

    strengths = [
        {
            "key": str(item.get("key") or ""),
            "label": str(item.get("label") or ""),
            "evidence": str(item.get("evidence") or item.get("label") or "").strip(),
        }
        for item in met_metrics[:4]
    ]
    weaknesses = [
        {
            "key": str(item.get("key") or ""),
            "label": str(item.get("label") or ""),
            "evidence": str(item.get("evidence") or item.get("label") or "").strip(),
        }
        for item in not_met_metrics[:4]
    ]
    checklist = [
        {
            "key": str(item.get("key") or ""),
            "status": str(item.get("status") or "unknown"),
            "label": str(item.get("label") or ""),
            "evidence": str(item.get("evidence") or "").strip(),
        }
        for item in metrics[:8]
    ]
    risks = _scorecard_risk_items(scorecard)

    test1 = latest_tests.get("TEST1") if isinstance(latest_tests, dict) else None
    test2 = latest_tests.get("TEST2") if isinstance(latest_tests, dict) else None
    test_insights_parts: list[str] = []
    if isinstance(test1, dict) and test1.get("final_score") is not None:
        test_insights_parts.append(f"Тест 1: {test1.get('final_score')} звезды")
    if isinstance(test2, dict) and test2.get("final_score") is not None:
        test_insights_parts.append(f"Тест 2: {test2.get('final_score')} звезды")
    if candidate_profile.get("work_experience"):
        test_insights_parts.append(f"Опыт: {str(candidate_profile.get('work_experience'))[:160]}")
    test_insights = ". ".join(part for part in test_insights_parts if part) or None

    if recommendation == "od_recommended":
        next_actions = [
            {
                "key": "assign_intro_day",
                "label": "Предложить следующий этап",
                "rationale": "Профиль и базовые критерии выглядят достаточными для движения дальше.",
                "cta": "Зафиксировать ознакомительный день и подтвердить явку.",
            }
        ]
    elif recommendation == "not_recommended":
        blocker = (scorecard.get("blockers") or [{}])[0]
        next_actions = [
            {
                "key": "hold_and_escalate",
                "label": "Не предлагать следующий этап",
                "rationale": str(blocker.get("evidence") or blocker.get("label") or "Есть критичный стоп-фактор."),
                "cta": "Мягко закрыть диалог или передать на внутреннюю проверку.",
            }
        ]
    else:
        missing = (scorecard.get("missing_data") or [{}])[0]
        next_actions = [
            {
                "key": "clarify_critical_points",
                "label": "Сначала уточнить риски",
                "rationale": str(missing.get("evidence") or missing.get("label") or "Нужно снять ключевые вопросы перед следующим шагом."),
                "cta": "Задать 2-3 уточняющих вопроса и только потом принимать решение по ОД.",
            }
        ]

    fit_rationale = _scorecard_fit_rationale(scorecard)
    summary = {
        "tldr": _summary_tldr_from_scorecard(scorecard, candidate_city=candidate_city),
        "fit": {
            "score": final_score,
            "level": fit_level_from_score(final_score),
            "rationale": fit_rationale,
            "criteria_used": _criteria_used_from_context(context),
        },
        "vacancy_fit": {
            "score": final_score,
            "level": fit_level_from_score(final_score),
            "summary": fit_rationale or _summary_tldr_from_scorecard(scorecard, candidate_city=candidate_city),
            "evidence": [
                {
                    "factor": str(item.get("label") or item.get("key") or ""),
                    "assessment": (
                        "positive"
                        if str(item.get("status") or "").strip().lower() == "met"
                        else "negative"
                        if str(item.get("status") or "").strip().lower() == "not_met"
                        else "neutral"
                    ),
                    "detail": str(item.get("evidence") or item.get("label") or "").strip(),
                }
                for item in metrics[:6]
            ],
            "criteria_source": "both" if _criteria_used_from_context(context) else "none",
        },
        "strengths": strengths,
        "weaknesses": weaknesses,
        "criteria_checklist": checklist,
        "test_insights": test_insights,
        "risks": risks,
        "next_actions": next_actions,
        "notes": "Сводка собрана из регламентов, тестов, резюме и карточки кандидата без ожидания внешней LLM-генерации.",
        "scorecard": scorecard,
    }
    return CandidateSummaryV1.model_validate(summary).model_dump()


def _questions_from_scorecard(scorecard: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    for item in list(scorecard.get("missing_data") or []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("key") or "").strip().lower()
        if "формат" in label or "разъезд" in label:
            questions.append("Насколько вам реально подходит полевой и выездной формат работы в течение дня?")
        elif "речь" in label or "коммуника" in label:
            questions.append("Какой у вас реальный опыт живого общения с клиентами и как чувствуете себя в переговорах?")
        elif "тест" in label:
            questions.append("Готовы ли вы оперативно пройти или перепройти нужный этап тестирования без паузы?")
        else:
            questions.append(f"Уточните, пожалуйста: {str(item.get('label') or item.get('evidence') or '').strip()}?")
    for item in list(scorecard.get("blockers") or []):
        if not isinstance(item, dict):
            continue
        questions.append(f"Подтвердите корректно, пожалуйста: {str(item.get('label') or item.get('evidence') or '').strip()}?")
    deduped: list[str] = []
    seen: set[str] = set()
    for value in questions:
        clean = value.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    if not deduped:
        deduped = [
            "Что для вас сейчас ключевое при выборе работы: доход, график или развитие?",
            "Насколько вам комфортна работа с большим количеством живого общения?",
            "Когда вы реально готовы выйти на следующий этап?",
        ]
    return deduped[:6]


def _build_candidate_coach_fallback(
    *,
    context: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    recommendation = str(scorecard.get("recommendation") or "clarify_before_od").strip().lower()
    final_score = scorecard.get("final_score")
    risks = _scorecard_risk_items(scorecard)
    strengths = [
        {
            "key": str(item.get("key") or ""),
            "label": str(item.get("label") or ""),
            "evidence": str(item.get("evidence") or item.get("label") or "").strip(),
        }
        for item in list(scorecard.get("metrics") or [])
        if isinstance(item, dict) and str(item.get("status") or "").strip().lower() == "met"
    ][:4]
    if recommendation == "od_recommended":
        next_best_action = "Переходить к закреплению следующего этапа и подтверждению явки без лишней теории."
        message_drafts = [
            {
                "text": "По вашему профилю вижу хорошее совпадение. Предлагаю сразу закрепить следующий этап и отправлю все детали одним сообщением.",
                "reason": "Быстро переводит релевантного кандидата к действию.",
            }
        ]
    elif recommendation == "not_recommended":
        next_best_action = "Не обещать следующий этап, мягко закрыть ожидания и при необходимости эскалировать кейс руководителю."
        message_drafts = [
            {
                "text": "Спасибо за открытый разговор. Я корректно зафиксирую детали и вернусь с итогом после внутренней сверки по критериям.",
                "reason": "Снимает напряжение и не обещает ОД при стоп-факторах.",
            }
        ]
    else:
        next_best_action = "Снять 1-2 критичных вопроса по формату/мотивации и только потом предлагать следующий этап."
        message_drafts = [
            {
                "text": "Вижу потенциал по вашему профилю. Чтобы не тратить ваше время, хочу коротко уточнить пару моментов и после этого смогу предложить следующий шаг.",
                "reason": "Сохраняет интерес кандидата и не ведёт к преждевременному обещанию ОД.",
            }
        ]

    coach = {
        "relevance_score": final_score,
        "relevance_level": fit_level_from_score(final_score),
        "rationale": _scorecard_fit_rationale(scorecard),
        "criteria_used": _criteria_used_from_context(context),
        "strengths": strengths,
        "risks": risks,
        "interview_questions": _questions_from_scorecard(scorecard),
        "next_best_action": next_best_action,
        "message_drafts": message_drafts,
    }
    return CandidateCoachV1.model_validate(coach).model_dump()


def _is_ambiguous_fact(value: str | None) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    markers = (
        "если",
        "завис",
        "обсуд",
        "подума",
        "не уверен",
        "не знаю",
        "смотря",
        "по ситуации",
        "посмотр",
    )
    return any(marker in text for marker in markers)


def _build_candidate_facts_fallback(
    *,
    context: dict[str, Any],
    resume_context: dict[str, Any],
) -> dict[str, Any]:
    candidate = context.get("candidate") if isinstance(context.get("candidate"), dict) else {}
    profile = context.get("candidate_profile") if isinstance(context.get("candidate_profile"), dict) else {}
    facts: list[dict[str, Any]] = []

    def add_fact(
        key: str,
        label: str,
        value: Any,
        *,
        source: str,
        confidence: str = "medium",
        confirmed: bool = True,
        ambiguity_note: str | None = None,
    ) -> None:
        text = str(value or "").strip()
        if not text:
            return
        facts.append(
            {
                "key": key,
                "label": label,
                "value": text,
                "confidence": confidence,
                "source": source,
                "confirmed": confirmed,
                "ambiguity_note": ambiguity_note,
            }
        )

    add_fact("city", "Город", candidate.get("city"), source="system", confidence="high")
    add_fact("desired_income", "Желаемый доход", profile.get("desired_income"), source="test1")
    add_fact("start_readiness", "Готовность выйти", profile.get("start_readiness"), source="test1")
    add_fact("field_format_readiness", "Полевой формат", profile.get("field_format_readiness"), source="test1")
    add_fact("work_status", "Текущий статус", profile.get("work_status"), source="test1")
    add_fact("work_experience", "Опыт продаж / переговоров", profile.get("work_experience"), source="test1")
    add_fact("motivation", "Мотивация", profile.get("motivation"), source="test1")
    add_fact("skills", "Ключевые навыки", profile.get("skills"), source="test1")
    if resume_context.get("headline") or resume_context.get("summary"):
        add_fact(
            "hh_resume",
            "HH / резюме",
            resume_context.get("headline") or "Есть дополнительный контекст из резюме",
            source="hh_resume",
            confidence="medium",
        )

    ambiguous_keys = [
        item["key"]
        for item in facts
        if _is_ambiguous_fact(str(item.get("value") or "")) or str(item.get("ambiguity_note") or "").strip()
    ]
    confirmed_keys = [item["key"] for item in facts if item["key"] not in ambiguous_keys]
    prefill_ready_keys = list(confirmed_keys)

    clarification_question: str | None = None
    if "desired_income" in ambiguous_keys or not profile.get("desired_income"):
        clarification_question = "Подскажите, пожалуйста, какой доход на старте для вас комфортен?"
    elif "start_readiness" in ambiguous_keys or not profile.get("start_readiness"):
        clarification_question = "Когда вы реально готовы выйти на следующий этап или приступить к обучению?"
    elif "field_format_readiness" in ambiguous_keys or not profile.get("field_format_readiness"):
        clarification_question = "Насколько вам комфортен полевой формат работы и выезды по городу?"

    summary_parts: list[str] = []
    if confirmed_keys:
        summary_parts.append(f"Можно переиспользовать {len(confirmed_keys)} подтверждённых фактов из анкеты.")
    if ambiguous_keys:
        summary_parts.append(f"Нужно уточнить: {', '.join(ambiguous_keys[:3])}.")
    if not summary_parts:
        summary_parts.append("Структурированных фактов пока мало, лучше уточнить ключевые вводные вручную.")

    return CandidateFactsV1.model_validate(
        {
            "summary": " ".join(summary_parts),
            "facts": facts,
            "confirmed_keys": confirmed_keys,
            "ambiguous_keys": ambiguous_keys,
            "prefill_ready_keys": prefill_ready_keys,
            "clarification_question": clarification_question,
        }
    ).model_dump()


def _stage_from_context(context: dict[str, Any]) -> str:
    candidate = context.get("candidate") if isinstance(context.get("candidate"), dict) else {}
    slots = context.get("slots") if isinstance(context.get("slots"), dict) else {}
    upcoming = slots.get("upcoming") if isinstance(slots.get("upcoming"), dict) else {}
    status = str(candidate.get("status") or "").strip().lower()
    slot_status = str(upcoming.get("status") or "").strip().lower()
    if status in {"slot_pending", "waiting_for_slot", "stalled_waiting_slot"}:
        if upcoming.get("id"):
            return "awaiting_recruiter_slot_decision"
        return "awaiting_slot_offer"
    if status.startswith("interview"):
        if slot_status in {"booked", "confirmed", "reserved", "pending"}:
            return "interview_scheduled"
        return "interview_flow"
    if status.startswith("test2"):
        return "test2"
    return "active_screening"


def _build_recruiter_next_best_action_fallback(
    *,
    context: dict[str, Any],
    scorecard: dict[str, Any],
    facts_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stage = _stage_from_context(context)
    recommendation = str(scorecard.get("recommendation") or "clarify_before_od").strip().lower()
    facts = facts_payload if isinstance(facts_payload, dict) else {}
    ambiguous_keys = list(facts.get("ambiguous_keys") or [])
    risks = _scorecard_risk_items(scorecard)
    strengths = [
        {
            "key": str(item.get("key") or ""),
            "label": str(item.get("label") or ""),
            "evidence": str(item.get("evidence") or item.get("label") or "").strip(),
        }
        for item in list(scorecard.get("metrics") or [])
        if isinstance(item, dict) and str(item.get("status") or "").strip().lower() == "met"
    ][:3]

    if stage == "awaiting_recruiter_slot_decision":
        recommended_action = {
            "key": "approve_or_adjust_slot",
            "label": "Быстро согласовать слот",
            "rationale": "Кандидат уже выбрал время. Чем быстрее закрыть решение, тем выше шанс сохранить контакт.",
            "cta": "Либо согласуйте выбранный слот, либо сразу предложите альтернативу.",
        }
        outreach_goal = "Закрыть решение по выбранному слоту в этом касании."
        playbook = {
            "what_to_write": "Коротко подтвердить, что слот увидели и возвращаетесь с финальным решением без паузы.",
            "what_to_offer": "Либо текущее время, либо одна чёткая альтернатива.",
            "likely_objection": "Кандидат может переживать, что процесс завис.",
            "best_cta": "Подтвердите, что это время ещё актуально, и я сразу закреплю решение.",
        }
    elif stage == "awaiting_slot_offer":
        recommended_action = {
            "key": "offer_concrete_slot",
            "label": "Предложить ближайшие слоты",
            "rationale": "После Теста 1 важно быстро перевести кандидата в календарь, а не продолжать долгий диалог.",
            "cta": "Дайте 2 конкретных времени на выбор или попросите удобный диапазон.",
        }
        outreach_goal = "Получить от кандидата конкретный слот или диапазон сегодня."
        playbook = {
            "what_to_write": "Коротко подтвердить интерес и сразу предложить 2 варианта времени.",
            "what_to_offer": "Ближайшие слоты, без широкого меню из 5-6 вариантов.",
            "likely_objection": "Может попросить другое время или сначала детали по работе.",
            "best_cta": "Какой вариант вам удобнее: сегодня вечером или завтра утром?",
        }
    elif stage == "interview_scheduled":
        recommended_action = {
            "key": "confirm_attendance",
            "label": "Дожать подтверждение явки",
            "rationale": "Сейчас критично получить короткое подтверждение и не потерять кандидата перед встречей.",
            "cta": "Напомнить о встрече и попросить ответить, что всё в силе.",
        }
        outreach_goal = "Получить подтверждение явки без лишней переписки."
        playbook = {
            "what_to_write": "Напомнить дату и время, убрать лишнюю теорию, попросить одно короткое подтверждение.",
            "what_to_offer": "Если неудобно, дать один безопасный путь для переноса.",
            "likely_objection": "Может написать, что планы изменились или нужна ссылка заново.",
            "best_cta": "Подтвердите, пожалуйста, что встреча актуальна и вы будете на связи.",
        }
    elif recommendation == "not_recommended":
        recommended_action = {
            "key": "manual_review",
            "label": "Остановиться и перепроверить кейс",
            "rationale": "Есть объективные стоп-факторы, поэтому нельзя переводить кандидата дальше автоматически.",
            "cta": "Сверьте кейс вручную и решите, нужен ли мягкий отказ или эскалация.",
        }
        outreach_goal = "Не обещать следующий этап до ручной проверки."
        playbook = {
            "what_to_write": "Спокойно сообщить, что вы фиксируете детали и вернётесь с итогом после внутренней проверки.",
            "what_to_offer": "Ничего не обещать заранее.",
            "likely_objection": "Кандидат может попросить быстрый ответ по решению.",
            "best_cta": "Спасибо, я зафиксирую всё корректно и вернусь с итогом после проверки.",
        }
    else:
        recommended_action = {
            "key": "clarify_and_move",
            "label": "Снять ключевые неясности",
            "rationale": "По профилю есть потенциал, но остаются вопросы, которые лучше закрыть до следующего этапа.",
            "cta": "Задайте 1-2 коротких уточнения и сразу переведите к следующему шагу.",
        }
        outreach_goal = "Снять ambiguity и сразу довести до следующего действия."
        likely_objection = (
            f"Кандидат может ответить расплывчато по: {', '.join(ambiguous_keys[:2])}."
            if ambiguous_keys
            else "Кандидат может попросить сначала больше деталей по роли."
        )
        playbook = {
            "what_to_write": "Показать, что профиль интересен, и попросить ответить буквально на 1-2 уточняющих вопроса.",
            "what_to_offer": "Сразу обозначить, какой шаг будет следующим после уточнения.",
            "likely_objection": likely_objection,
            "best_cta": str(facts.get("clarification_question") or "Подскажите, пожалуйста, этот момент, и я сразу предложу следующий шаг."),
        }

    summary = recommended_action["rationale"]
    if risks:
        summary = f"{summary} Главный риск сейчас: {risks[0].get('label') or risks[0].get('explanation')}."

    return RecruiterNextBestActionV1.model_validate(
        {
            "summary": summary,
            "ai_confidence": "medium" if ambiguous_keys else "high",
            "recommended_action": recommended_action,
            "reasons": strengths,
            "risks": risks,
            "interview_focus": _questions_from_scorecard(scorecard)[:4],
            "outreach_goal": outreach_goal,
            "playbook": playbook,
            "feedback_state": "pending",
        }
    ).model_dump()


def _build_candidate_contact_draft_fallback(
    *,
    context: dict[str, Any],
    scorecard: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    stage = _stage_from_context(context)
    candidate = context.get("candidate") if isinstance(context.get("candidate"), dict) else {}
    channel = "telegram" if bool(candidate.get("telegram_linked")) else "max"
    if stage == "awaiting_recruiter_slot_decision":
        analysis = "Кандидат уже выбрал время, поэтому нужно быстро подтвердить, что слот увидели и решение не зависло."
        intent_key = "slot_followup"
        drafts = [
            {
                "text": "Добрый день! Видим ваш выбранный слот и уже сверяем его с расписанием рекрутёра. Чуть позже вернусь с подтверждением или сразу предложу ближайшую альтернативу.",
                "reason": "Снимает тревогу у кандидата и удерживает его в процессе.",
            },
            {
                "text": "Спасибо, слот зафиксировали в работе. Если это время перестанет быть удобным, напишите, и я сразу подберу ближайший вариант без потери этапа.",
                "reason": "Сохраняет контакт и снижает риск тихой отмены.",
            },
        ]
    elif stage == "awaiting_slot_offer":
        analysis = "После Теста 1 лучше сразу сузить выбор до двух конкретных вариантов времени."
        intent_key = "offer_slot"
        drafts = [
            {
                "text": "Добрый день! По вашему профилю можно двигаться дальше. Предлагаю сразу выбрать удобное время: сегодня после 16:00 или завтра до 12:00. Какой вариант вам ближе?",
                "reason": "Сужает выбор и ускоряет запись на интервью.",
            },
            {
                "text": "Чтобы не затягивать процесс, напишите, пожалуйста, какой диапазон времени вам удобен сегодня или завтра, и я быстро закреплю слот.",
                "reason": "Подходит, если у кандидата нет удобства под готовые варианты.",
            },
        ]
    elif stage == "interview_scheduled":
        analysis = "Здесь важнее короткое подтверждение явки, чем длинное объяснение процесса."
        intent_key = "confirm_interview"
        drafts = [
            {
                "text": "Напоминаю о встрече и прошу коротко подтвердить, что всё в силе. Если время изменилось, сразу напишите, чтобы мы успели перестроить слот.",
                "reason": "Закрывает основной риск no-show перед интервью.",
            },
            {
                "text": "Пожалуйста, подтвердите, что встреча для вас актуальна. Если нужен перенос, лучше сообщить сейчас, и я предложу ближайшую альтернативу.",
                "reason": "Даёт понятный CTA и безопасный путь к переносу.",
            },
        ]
    elif recommendation := str(scorecard.get("recommendation") or "").strip().lower():
        analysis = "Сейчас лучше снять одну-две ключевые неясности и только потом вести кандидата дальше."
        intent_key = "clarify"
        drafts = [
            {
                "text": "Спасибо за ответы. Чтобы не тратить ваше время, хочу уточнить буквально один момент и после этого сразу предложу следующий шаг.",
                "reason": "Сохраняет интерес и помогает быстро дособрать нужные вводные.",
            },
            {
                "text": "Вижу потенциал по вашему профилю. Давайте коротко уточним пару деталей, чтобы я предложил вам следующий этап уже без задержки.",
                "reason": "Мягко дожимает кандидата до полного контекста.",
            },
        ]
        if recommendation == "od_recommended":
            analysis = "Кандидат выглядит тёплым, поэтому лучше не растягивать переписку, а перевести его к следующему действию."
            intent_key = "move_forward"
    else:
        analysis = "Нужен короткий нейтральный follow-up с понятным следующим шагом."
        intent_key = "follow_up"
        drafts = [
            {
                "text": "Добрый день! Возвращаюсь по вашему отклику. Если вопрос с работой ещё актуален, давайте сегодня закроем следующий шаг, чтобы не затягивать процесс.",
                "reason": "Возвращает кандидата в диалог и задаёт темп.",
            }
        ]

    if mode == "short":
        drafts = [{**item, "text": item["text"].split(". ")[0].strip() + "."} for item in drafts]
    elif mode == "supportive":
        drafts = [{**item, "text": f"{item['text']} Если где-то неудобно по времени, подстроюсь и подберу лучший вариант."} for item in drafts]

    return CandidateContactDraftsV1.model_validate(
        {
            "analysis": analysis,
            "intent_key": intent_key,
            "recommended_channel": channel,
            "drafts": drafts,
            "used_context": {"safe_text_used": False, "stage": stage},
        }
    ).model_dump()


async def build_candidate_live_score_snapshot(
    candidate_id: int,
    *,
    principal: Principal | None = None,
) -> dict[str, Any]:
    from backend.apps.admin_ui.security import admin_principal

    principal_value = principal or admin_principal()
    ctx = await build_candidate_ai_context(candidate_id, principal=principal_value, include_pii=False)
    service = AIService()
    resume_context = _normalized_resume_context(await service._get_hh_resume_normalized(candidate_id))
    scorecard = _scorecard_payload(
        build_candidate_scorecard(
            context=ctx,
            resume_context=resume_context,
            llm_scorecard=None,
        )
    )
    risks = _scorecard_risk_items(scorecard)
    return {
        "score": scorecard.get("final_score"),
        "level": fit_level_from_score(scorecard.get("final_score")),
        "recommendation": scorecard.get("recommendation"),
        "risk_hint": risks[0]["label"] if risks else None,
        "scorecard": scorecard,
    }


async def invalidate_candidate_ai_outputs(
    candidate_id: int,
    *,
    kinds: tuple[str, ...] = _CANDIDATE_AI_KINDS,
) -> None:
    await invalidate_candidates_ai_outputs([candidate_id], kinds=kinds)


async def invalidate_candidates_ai_outputs(
    candidate_ids: list[int] | tuple[int, ...] | set[int],
    *,
    kinds: tuple[str, ...] = _CANDIDATE_AI_KINDS,
) -> None:
    ids: list[int] = []
    for candidate_id in candidate_ids:
        try:
            normalized = int(candidate_id)
        except (TypeError, ValueError):
            continue
        if normalized > 0:
            ids.append(normalized)
    ids = sorted(set(ids))
    if not ids:
        return
    async with async_session() as session:
        await session.execute(
            update(AIOutput)
            .where(
                AIOutput.scope_type == "candidate",
                AIOutput.scope_id.in_(ids),
                AIOutput.kind.in_(tuple(kinds)),
            )
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()


async def _warm_candidate_ai_outputs(
    candidate_id: int,
    *,
    principal: Principal,
    refresh: bool,
) -> None:
    service = AIService()
    if not service._settings.ai_enabled:
        return
    try:
        # Warm the cache through the normal code path. Callers usually invalidate first,
        # so forcing refresh only adds external latency without changing the result shape.
        summary = await service.get_candidate_summary(candidate_id, principal=principal, refresh=False)
        await service.get_candidate_coach(
            candidate_id,
            principal=principal,
            refresh=False,
            summary_result=summary,
        )
        await service.get_candidate_interview_script(
            candidate_id,
            principal=principal,
            refresh=False,
            summary_result=summary,
        )
    except Exception:
        logger.warning("ai.warm_candidate.failed", extra={"candidate_id": candidate_id}, exc_info=True)


async def warm_candidate_ai_outputs(
    candidate_id: int,
    *,
    principal: Principal | None = None,
    refresh: bool = True,
) -> None:
    from backend.apps.admin_ui.security import admin_principal

    await _warm_candidate_ai_outputs(
        int(candidate_id),
        principal=principal or admin_principal(),
        refresh=refresh,
    )


async def warm_candidates_ai_outputs(
    candidate_ids: list[int] | tuple[int, ...] | set[int],
    *,
    principal: Principal | None = None,
    refresh: bool = True,
) -> None:
    ids = sorted({int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) > 0})
    if not ids:
        return
    from backend.apps.admin_ui.security import admin_principal

    principal_value = principal or admin_principal()
    for candidate_id in ids:
        await _warm_candidate_ai_outputs(candidate_id, principal=principal_value, refresh=refresh)


def schedule_warm_candidate_ai_outputs(
    candidate_id: int,
    *,
    principal: Principal | None = None,
    refresh: bool = True,
) -> asyncio.Task[None] | None:
    if (get_settings().environment or "").strip().lower() == "test":
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(
        warm_candidate_ai_outputs(
            candidate_id,
            principal=principal,
            refresh=refresh,
        )
    )


def schedule_warm_candidates_ai_outputs(
    candidate_ids: list[int] | tuple[int, ...] | set[int],
    *,
    principal: Principal | None = None,
    refresh: bool = True,
) -> asyncio.Task[None] | None:
    if (get_settings().environment or "").strip().lower() == "test":
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(
        warm_candidates_ai_outputs(
            candidate_ids,
            principal=principal,
            refresh=refresh,
        )
    )


async def refresh_active_city_candidates_ai_outputs(
    city_id: int,
    *,
    principal: Principal | None = None,
    refresh: bool = True,
) -> None:
    async with async_session() as session:
        city = await session.get(City, city_id)
        if city is None:
            return
        city_names = {
            str(name).strip().lower()
            for name in (getattr(city, "name_plain", None), getattr(city, "name", None))
            if str(name or "").strip()
        }
        if not city_names:
            return
        rows = await session.execute(
            select(User.id).where(
                User.is_active.is_(True),
                func.lower(func.coalesce(User.city, "")).in_(city_names),
            )
        )
        candidate_ids = [int(candidate_id) for candidate_id in rows.scalars().all()]
    await invalidate_candidates_ai_outputs(candidate_ids)
    await warm_candidates_ai_outputs(candidate_ids, principal=principal, refresh=refresh)


def schedule_refresh_active_city_candidates_ai_outputs(
    city_id: int,
    *,
    principal: Principal | None = None,
    refresh: bool = True,
) -> asyncio.Task[None] | None:
    if (get_settings().environment or "").strip().lower() == "test":
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(
        refresh_active_city_candidates_ai_outputs(
            city_id,
            principal=principal,
            refresh=refresh,
        )
    )


class AIService:
    """Facade for all AI operations (summaries, drafts, insights, chat).

    Instantiated per-request via ``get_ai_service()`` FastAPI dependency.
    Handles caching, quota enforcement, logging and provider dispatch.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._provider = _provider_for_settings()
        self._allow_pii = (self._settings.ai_pii_mode or "").strip().lower() == "full"

    def _ensure_enabled(self) -> None:
        """Raise ``AIDisabledError`` if ``AI_ENABLED`` is falsy."""
        if not self._settings.ai_enabled:
            raise AIDisabledError("ai_disabled")

    async def _ensure_quota(self, principal: Principal) -> None:
        """Raise ``AIRateLimitedError`` if daily request count or budget is exceeded."""
        limit = int(self._settings.ai_max_requests_per_principal_per_day or 0)
        if limit > 0:
            used = await _count_today_requests(principal)
            if used >= limit:
                raise AIRateLimitedError("rate_limited")
        budget = float(self._settings.ai_daily_budget_usd or 0)
        if budget > 0:
            spent = await _estimate_today_spend_usd()
            if spent >= budget:
                logger.warning("ai.budget.exceeded", extra={"spent_usd": round(spent, 4), "budget_usd": budget})
                raise AIRateLimitedError("daily_budget_exceeded")

    async def get_candidate_summary(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        refresh: bool = False,
    ) -> AIResult:
        """Generate or retrieve a cached AI summary for a candidate.

        Args:
            candidate_id: Target candidate PK.
            principal: Authenticated admin/recruiter.
            refresh: If True, bypass cache and force re-generation.

        Returns:
            AIResult with validated CandidateSummaryV1 payload.

        Raises:
            AIDisabledError: AI is turned off.
            AIRateLimitedError: Daily quota/budget exceeded.
            HTTPException 502: Provider returned an error.
        """
        self._ensure_enabled()
        ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)
        resume_context = _normalized_resume_context(await self._get_hh_resume_normalized(candidate_id))
        ctx["resume_context"] = resume_context
        input_hash = compute_input_hash(ctx)
        kind = "candidate_summary_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                # View metrics: safe, aggregated
                try:
                    await analytics.log_event(
                        "ai_summary_viewed",
                        candidate_id=candidate_id,
                        metadata={"cached": True, "kind": kind},
                    )
                except Exception:  # pragma: no cover - analytics is non-critical
                    pass
                cached_payload = cached.payload_json if isinstance(cached.payload_json, dict) else {}
                return AIResult(
                    payload=_apply_candidate_summary_scorecard(
                        context=ctx,
                        resume_context=resume_context,
                        payload=cached_payload,
                    ),
                    cached=True,
                    input_hash=input_hash,
                )

            fallback_payload = _build_candidate_summary_fallback(
                context=ctx,
                scorecard=_scorecard_payload(
                    build_candidate_scorecard(
                        context=ctx,
                        resume_context=resume_context,
                        llm_scorecard=None,
                    )
                ),
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

        await self._ensure_quota(principal)

        system_prompt, user_prompt = candidate_summary_prompts(context=ctx, allow_pii=self._allow_pii)
        model = self._settings.openai_model
        max_tokens = int(self._settings.ai_max_tokens)
        # GPT-5 responses can produce large JSON payloads; 800 tokens is often insufficient,
        # leading to truncated/malformed JSON. Keep other endpoints on the configured limit.
        if (model or "").strip().lower().startswith("gpt-5") and max_tokens < 1800:
            max_tokens = 1800
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=max_tokens,
            )
            validated = _apply_candidate_summary_scorecard(
                context=ctx,
                resume_context=resume_context,
                payload=CandidateSummaryV1.model_validate(payload).model_dump(),
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            try:
                await analytics.log_event(
                    "ai_summary_generated",
                    candidate_id=candidate_id,
                    metadata={"kind": kind},
                )
                await analytics.log_event(
                    "ai_summary_viewed",
                    candidate_id=candidate_id,
                    metadata={"cached": False, "kind": kind},
                )
            except Exception:  # pragma: no cover
                pass
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except (AIProviderError, Exception) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.candidate_summary.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            fallback_payload = _build_candidate_summary_fallback(
                context=ctx,
                scorecard=_scorecard_payload(
                    build_candidate_scorecard(
                        context=ctx,
                        resume_context=resume_context,
                        llm_scorecard=None,
                    )
                ),
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

    async def get_candidate_coach(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        refresh: bool = False,
        summary_result: AIResult | None = None,
    ) -> AIResult:
        self._ensure_enabled()
        if summary_result is None:
            summary_result = await self.get_candidate_summary(
                candidate_id,
                principal=principal,
                refresh=refresh,
            )
        summary_payload = summary_result.payload if isinstance(summary_result.payload, dict) else {}
        ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)
        resume_context = _normalized_resume_context(await self._get_hh_resume_normalized(candidate_id))
        ctx["resume_context"] = resume_context
        ctx["summary_scorecard"] = summary_payload.get("scorecard") if isinstance(summary_payload.get("scorecard"), dict) else None
        ctx["summary_fit"] = summary_payload.get("fit") if isinstance(summary_payload.get("fit"), dict) else None
        hash_ctx = dict(ctx)
        hash_ctx.pop("summary_scorecard", None)
        hash_ctx.pop("summary_fit", None)
        input_hash = compute_input_hash(
            {
                "context": hash_ctx,
                "summary_input_hash": summary_result.input_hash,
            }
        )
        kind = "candidate_coach_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                cached_payload = cached.payload_json if isinstance(cached.payload_json, dict) else {}
                return AIResult(
                    payload=_apply_candidate_coach_score(
                        payload=cached_payload,
                        scorecard=ctx.get("summary_scorecard") if isinstance(ctx.get("summary_scorecard"), dict) else None,
                        criteria_used=_criteria_used_from_context(ctx),
                    ),
                    cached=True,
                    input_hash=input_hash,
                )

            fallback_payload = _build_candidate_coach_fallback(
                context=ctx,
                scorecard=ctx.get("summary_scorecard") if isinstance(ctx.get("summary_scorecard"), dict) else {},
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

        await self._ensure_quota(principal)
        system_prompt, user_prompt = candidate_coach_prompts(context=ctx, allow_pii=self._allow_pii)
        model = self._settings.openai_model
        max_tokens = int(self._settings.ai_max_tokens)
        if (model or "").strip().lower().startswith("gpt-5") and max_tokens < 1600:
            max_tokens = 1600
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=max_tokens,
            )
            validated = _apply_candidate_coach_score(
                payload=CandidateCoachV1.model_validate(payload).model_dump(),
                scorecard=ctx.get("summary_scorecard") if isinstance(ctx.get("summary_scorecard"), dict) else None,
                criteria_used=_criteria_used_from_context(ctx),
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.candidate_coach.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            fallback_payload = _build_candidate_coach_fallback(
                context=ctx,
                scorecard=ctx.get("summary_scorecard") if isinstance(ctx.get("summary_scorecard"), dict) else {},
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

    async def get_candidate_facts(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        refresh: bool = False,
    ) -> AIResult:
        self._ensure_enabled()
        ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)
        resume_context = _normalized_resume_context(await self._get_hh_resume_normalized(candidate_id))
        ctx["resume_context"] = resume_context
        input_hash = compute_input_hash(ctx)
        kind = "candidate_facts_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                cached_payload = cached.payload_json if isinstance(cached.payload_json, dict) else {}
                return AIResult(
                    payload=CandidateFactsV1.model_validate(cached_payload).model_dump(),
                    cached=True,
                    input_hash=input_hash,
                )

            fallback_payload = _build_candidate_facts_fallback(context=ctx, resume_context=resume_context)
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

        await self._ensure_quota(principal)
        system_prompt, user_prompt = candidate_facts_prompts(context=ctx, allow_pii=self._allow_pii)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = CandidateFactsV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.candidate_facts.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            fallback_payload = _build_candidate_facts_fallback(context=ctx, resume_context=resume_context)
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

    async def get_recruiter_next_best_action(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        refresh: bool = False,
        summary_result: AIResult | None = None,
        facts_result: AIResult | None = None,
    ) -> AIResult:
        self._ensure_enabled()
        if summary_result is None:
            summary_result = await self.get_candidate_summary(candidate_id, principal=principal, refresh=False)
        if facts_result is None:
            facts_result = await self.get_candidate_facts(candidate_id, principal=principal, refresh=False)

        ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)
        ctx["summary_scorecard"] = (
            summary_result.payload.get("scorecard")
            if isinstance(summary_result.payload, dict) and isinstance(summary_result.payload.get("scorecard"), dict)
            else None
        )
        ctx["summary_fit"] = (
            summary_result.payload.get("fit")
            if isinstance(summary_result.payload, dict) and isinstance(summary_result.payload.get("fit"), dict)
            else None
        )
        ctx["candidate_facts"] = facts_result.payload if isinstance(facts_result.payload, dict) else {}
        input_hash = compute_input_hash(
            {
                "context": ctx,
                "summary_input_hash": summary_result.input_hash,
                "facts_input_hash": facts_result.input_hash,
            }
        )
        kind = "recruiter_next_best_action_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                cached_payload = cached.payload_json if isinstance(cached.payload_json, dict) else {}
                return AIResult(
                    payload=RecruiterNextBestActionV1.model_validate(cached_payload).model_dump(),
                    cached=True,
                    input_hash=input_hash,
                )

            fallback_payload = _build_recruiter_next_best_action_fallback(
                context=ctx,
                scorecard=ctx.get("summary_scorecard") if isinstance(ctx.get("summary_scorecard"), dict) else {},
                facts_payload=ctx.get("candidate_facts") if isinstance(ctx.get("candidate_facts"), dict) else {},
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

        await self._ensure_quota(principal)
        system_prompt, user_prompt = recruiter_next_best_action_prompts(context=ctx, allow_pii=self._allow_pii)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = RecruiterNextBestActionV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.recruiter_next_best_action.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            fallback_payload = _build_recruiter_next_best_action_fallback(
                context=ctx,
                scorecard=ctx.get("summary_scorecard") if isinstance(ctx.get("summary_scorecard"), dict) else {},
                facts_payload=ctx.get("candidate_facts") if isinstance(ctx.get("candidate_facts"), dict) else {},
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

    async def get_candidate_contact_drafts(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        mode: str,
    ) -> AIResult:
        self._ensure_enabled()
        summary_result = await self.get_candidate_summary(candidate_id, principal=principal, refresh=False)
        facts_result = await self.get_candidate_facts(candidate_id, principal=principal, refresh=False)
        next_best_action_result = await self.get_recruiter_next_best_action(
            candidate_id,
            principal=principal,
            refresh=False,
            summary_result=summary_result,
            facts_result=facts_result,
        )
        base_ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)
        base_ctx["summary_scorecard"] = (
            summary_result.payload.get("scorecard")
            if isinstance(summary_result.payload, dict) and isinstance(summary_result.payload.get("scorecard"), dict)
            else None
        )
        base_ctx["candidate_facts"] = facts_result.payload if isinstance(facts_result.payload, dict) else {}
        base_ctx["next_best_action"] = next_best_action_result.payload if isinstance(next_best_action_result.payload, dict) else {}
        base_ctx["draft_mode"] = mode

        input_hash = compute_input_hash(
            {
                "context": base_ctx,
                "summary_input_hash": summary_result.input_hash,
                "facts_input_hash": facts_result.input_hash,
                "next_best_action_input_hash": next_best_action_result.input_hash,
                "mode": mode,
            }
        )
        kind = "candidate_contact_draft_v1"

        cached = await _get_cached_output(
            scope_type="candidate",
            scope_id=candidate_id,
            kind=kind,
            input_hash=input_hash,
        )
        if cached is not None:
            cached_payload = cached.payload_json if isinstance(cached.payload_json, dict) else {}
            return AIResult(
                payload=CandidateContactDraftsV1.model_validate(cached_payload).model_dump(),
                cached=True,
                input_hash=input_hash,
            )

        await self._ensure_quota(principal)
        system_prompt, user_prompt = candidate_contact_draft_prompts(
            context=base_ctx,
            mode=mode,
            allow_pii=self._allow_pii,
        )
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = CandidateContactDraftsV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            try:
                await analytics.log_event(
                    "ai_candidate_contact_drafts_generated",
                    candidate_id=candidate_id,
                    metadata={"kind": kind, "mode": mode},
                )
            except Exception:
                pass
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.candidate_contact_drafts.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            fallback_payload = _build_candidate_contact_draft_fallback(
                context=base_ctx,
                scorecard=base_ctx.get("summary_scorecard") if isinstance(base_ctx.get("summary_scorecard"), dict) else {},
                mode=mode,
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=fallback_payload,
            )
            return AIResult(payload=fallback_payload, cached=False, input_hash=input_hash)

    async def save_recruiter_next_best_action_feedback(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        action: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        if action not in {"accept", "dismiss", "edit_and_send"}:
            raise ValueError("Некорректное действие feedback")
        await build_candidate_ai_context(candidate_id, principal=principal, include_pii=False)
        feedback_state = "edited" if action == "edit_and_send" else "accepted" if action == "accept" else "dismissed"
        try:
            await analytics.log_event(
                "ai_recruiter_next_best_action_feedback",
                candidate_id=candidate_id,
                metadata={
                    "action": action,
                    "feedback_state": feedback_state,
                    "note": (str(note or "").strip()[:500] or None),
                    "principal_type": principal.type,
                    "principal_id": principal.id,
                },
            )
        except Exception:
            logger.warning("ai.recruiter_next_best_action_feedback.failed", extra={"candidate_id": candidate_id}, exc_info=True)
        return {
            "candidate_id": int(candidate_id),
            "feedback_state": feedback_state,
            "action": action,
            "saved_at": _iso(datetime.now(UTC)),
        }

    async def get_candidate_coach_drafts(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        mode: str,
    ) -> AIResult:
        self._ensure_enabled()
        base_ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)

        inbound_raw = await get_last_inbound_message_text(candidate_id, principal=principal)
        candidate_fio = None
        recruiter_name = None
        try:
            async with async_session() as session:
                user = await session.get(User, candidate_id)
                if user is not None:
                    candidate_fio = user.fio
                if principal.type == "recruiter":
                    recruiter = await session.get(Recruiter, principal.id)
                    recruiter_name = recruiter.name if recruiter is not None else None
        except Exception:  # pragma: no cover - redaction helper should never break flow
            candidate_fio = None
            recruiter_name = None

        redaction = redact_text(
            inbound_raw or "",
            candidate_fio=candidate_fio,
            recruiter_name=recruiter_name,
        )
        ctx = dict(base_ctx)
        ctx["inbound_message"] = {
            "present": bool(inbound_raw),
            "safe_text_used": bool(inbound_raw) and (True if self._allow_pii else redaction.safe_to_send),
            "text": (
                str(inbound_raw)[:1200]
                if inbound_raw and self._allow_pii
                else (redaction.text if inbound_raw and redaction.safe_to_send else None)
            ),
        }
        ctx["draft_mode"] = mode

        input_hash = compute_input_hash(ctx)
        kind = "candidate_coach_drafts_v1"

        cached = await _get_cached_output(
            scope_type="candidate",
            scope_id=candidate_id,
            kind=kind,
            input_hash=input_hash,
        )
        if cached is not None:
            return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)

        system_prompt, user_prompt = candidate_coach_drafts_prompts(context=ctx, mode=mode, allow_pii=self._allow_pii)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = ChatReplyDraftsV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.candidate_coach_drafts.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc

    async def get_chat_reply_drafts(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        mode: str,
    ) -> AIResult:
        """Generate reply draft suggestions for a recruiter's chat with a candidate.

        Args:
            candidate_id: Target candidate PK.
            principal: Authenticated recruiter.
            mode: Tone — ``"short"`` | ``"neutral"`` | ``"supportive"``.

        Returns:
            AIResult with validated ChatReplyDraftsV1 payload.
        """
        self._ensure_enabled()
        base_ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)

        inbound_raw = await get_last_inbound_message_text(candidate_id, principal=principal)
        candidate_fio = None
        recruiter_name = None
        try:
            async with async_session() as session:
                user = await session.get(User, candidate_id)
                if user is not None:
                    candidate_fio = user.fio
                if principal.type == "recruiter":
                    recruiter = await session.get(Recruiter, principal.id)
                    recruiter_name = recruiter.name if recruiter is not None else None
        except Exception:  # pragma: no cover - redaction helper should never break flow
            candidate_fio = None
            recruiter_name = None
        redaction = redact_text(
            inbound_raw or "",
            candidate_fio=candidate_fio,
            recruiter_name=recruiter_name,
        )
        ctx = dict(base_ctx)
        ctx["inbound_message"] = {
            "present": bool(inbound_raw),
            "safe_text_used": bool(inbound_raw) and (True if self._allow_pii else redaction.safe_to_send),
            "text": (str(inbound_raw)[:1200] if inbound_raw and self._allow_pii else (redaction.text if inbound_raw and redaction.safe_to_send else None)),
        }
        ctx["draft_mode"] = mode

        input_hash = compute_input_hash(ctx)
        kind = "reply_drafts_v1"

        cached = await _get_cached_output(
            scope_type="candidate",
            scope_id=candidate_id,
            kind=kind,
            input_hash=input_hash,
        )
        if cached is not None:
            return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)

        system_prompt, user_prompt = chat_reply_drafts_prompts(context=ctx, mode=mode, allow_pii=self._allow_pii)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = ChatReplyDraftsV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            try:
                await analytics.log_event(
                    "ai_drafts_generated",
                    candidate_id=candidate_id,
                    metadata={"kind": kind, "mode": mode},
                )
            except Exception:  # pragma: no cover
                pass
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.chat_drafts.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc

    async def get_dashboard_insights(
        self,
        *,
        principal: Principal,
        context: dict[str, Any],
        scope_id: int = 0,
        refresh: bool = False,
    ) -> AIResult:
        """Generate AI-powered dashboard insights (anomalies, recommendations).

        Args:
            principal: Authenticated admin.
            context: Aggregated dashboard data (funnel, pipeline, outbox stats).
            scope_id: City ID for city-scoped insights, 0 for global.
            refresh: If True, bypass cache.

        Returns:
            AIResult with validated DashboardInsightV1 payload.
        """
        self._ensure_enabled()
        input_hash = compute_input_hash(context)
        kind = "dashboard_insight_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)
        system_prompt, user_prompt = dashboard_insight_prompts(context=context)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = DashboardInsightV1.model_validate(payload).model_dump()
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="dashboard",
                scope_id=scope_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc

    async def get_city_candidate_recommendations(
        self,
        city_id: int,
        *,
        principal: Principal,
        limit: int = 30,
        refresh: bool = False,
    ) -> AIResult:
        """Rank and recommend candidates for a city based on AI analysis.

        Post-processes results to filter out hallucinated candidate IDs.

        Args:
            city_id: Target city PK.
            principal: Authenticated recruiter/admin.
            limit: Max candidates to consider (capped at 80).
            refresh: If True, bypass cache.

        Returns:
            AIResult with validated CityCandidateRecommendationsV1 payload.
        """
        self._ensure_enabled()
        ctx = await build_city_candidate_recommendations_context(city_id, principal=principal, limit=limit)
        input_hash = compute_input_hash(ctx)
        kind = "city_candidate_recommendations_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

        await self._ensure_quota(principal)

        system_prompt, user_prompt = city_candidate_recommendations_prompts(context=ctx)
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = CityCandidateRecommendationsV1.model_validate(payload).model_dump()
            try:
                allowed_ids = {
                    int(item.get("id"))
                    for item in ((ctx.get("candidates") or {}).get("items") or [])
                    if isinstance(item, dict) and isinstance(item.get("id"), int)
                }
                recs = validated.get("recommended") or []
                filtered = []
                for rec in recs:
                    if not isinstance(rec, dict):
                        continue
                    cid = rec.get("candidate_id")
                    if isinstance(cid, int) and cid in allowed_ids:
                        filtered.append(rec)
                validated["recommended"] = filtered[:10]
                validated["criteria_used"] = bool((ctx.get("city") or {}).get("criteria_present"))
            except Exception:  # pragma: no cover - best-effort guardrail
                pass
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                input_hash=input_hash,
                payload=validated,
            )
            return AIResult(payload=validated, cached=False, input_hash=input_hash)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="city",
                scope_id=city_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.city_recommendations.failed", extra={"city_id": city_id}, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc

    def _interview_script_model_for_candidate(self, candidate_id: int) -> str:
        base_model = self._settings.openai_model
        ft_model = (getattr(self._settings, "ai_interview_script_ft_model", "") or "").strip()
        try:
            ab_percent = int(getattr(self._settings, "ai_interview_script_ab_percent", 0) or 0)
        except Exception:
            ab_percent = 0
        ab_percent = max(0, min(100, ab_percent))
        if not ft_model or ab_percent <= 0:
            return base_model

        digest = hashlib.sha256(f"interview_script:{candidate_id}".encode()).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return ft_model if bucket < ab_percent else base_model

    @staticmethod
    def _extract_income_range(text: str | None) -> dict[str, int] | None:
        if not text:
            return None
        vals = [int(x) for x in re.findall(r"\d{2,6}", text) if x.isdigit()]
        if len(vals) < 2:
            return None
        return {"min": min(vals), "max": max(vals)}

    @staticmethod
    def _extract_min_age(text: str | None) -> int | None:
        if not text:
            return None
        low = text.lower()
        m = re.search(r"от\s+(\d{2})\s*лет", low)
        if not m:
            m = re.search(r"(\d{2})\s*\+", low)
        if not m:
            return None
        try:
            age = int(m.group(1))
        except Exception:
            return None
        return age if 14 <= age <= 80 else None

    async def _build_office_context(self, *, ctx: dict[str, Any]) -> dict[str, Any]:
        candidate = ctx.get("candidate") or {}
        city_profile = ctx.get("city_profile") or {}
        city_id = city_profile.get("id")
        desired_position = candidate.get("desired_position")

        office_context: dict[str, Any] = {
            "city_id": city_id,
            "city": city_profile.get("name"),
            "vacancy": desired_position,
            "vacancy_id": None,
            "vacancy_description": None,
            "criteria": city_profile.get("criteria"),
            "address": None,
            "landmarks": None,
            "contact_name": None,
            "contact_phone": None,
            "schedule_rules": None,
            "income_range": None,
            "min_age": None,
            "must_have_experience": False,
        }

        async with async_session() as session:
            city = await session.get(City, int(city_id)) if isinstance(city_id, int) else None
            if city is not None:
                office_context["address"] = city.intro_address
                office_context["contact_name"] = city.contact_name
                office_context["contact_phone"] = city.contact_phone
                if city.intro_address:
                    # Best-effort landmarks for script logistics.
                    chunks = [part.strip() for part in str(city.intro_address).split(",") if part.strip()]
                    if len(chunks) > 1:
                        office_context["landmarks"] = ", ".join(chunks[1:3])

            vacancy_obj: Vacancy | None = None
            if isinstance(desired_position, str) and desired_position.strip():
                desired = desired_position.strip().lower()
                stmt = (
                    select(Vacancy)
                    .where(Vacancy.is_active.is_(True))
                    .order_by(Vacancy.updated_at.desc(), Vacancy.id.desc())
                )
                if isinstance(city_id, int):
                    stmt = stmt.where((Vacancy.city_id == city_id) | (Vacancy.city_id.is_(None)))
                rows = (await session.execute(stmt.limit(30))).scalars().all()
                for row in rows:
                    if desired in (row.title or "").lower():
                        vacancy_obj = row
                        break
                if vacancy_obj is None and rows:
                    vacancy_obj = rows[0]
            elif isinstance(city_id, int):
                vacancy_obj = await session.scalar(
                    select(Vacancy)
                    .where(Vacancy.city_id == city_id, Vacancy.is_active.is_(True))
                    .order_by(Vacancy.updated_at.desc(), Vacancy.id.desc())
                    .limit(1)
                )

        if vacancy_obj is not None:
            office_context["vacancy_id"] = int(vacancy_obj.id)
            office_context["vacancy"] = vacancy_obj.title
            office_context["vacancy_description"] = (vacancy_obj.description or "")[:1800] or None

        rules_blob = " ".join(
            str(x or "")
            for x in (
                office_context.get("criteria"),
                office_context.get("vacancy_description"),
            )
        ).strip()
        office_context["income_range"] = self._extract_income_range(rules_blob)
        office_context["min_age"] = self._extract_min_age(rules_blob)
        office_context["schedule_rules"] = rules_blob[:500] or None
        office_context["must_have_experience"] = "опыт" in rules_blob.lower()
        return office_context

    async def _get_hh_resume_normalized(self, candidate_id: int) -> dict[str, Any]:
        async with async_session() as session:
            row = await session.scalar(
                select(CandidateHHResume).where(CandidateHHResume.candidate_id == candidate_id)
            )
        if row is None:
            return normalize_hh_resume(format="raw_text", resume_json=None, resume_text=None)
        normalized = row.normalized_json if isinstance(row.normalized_json, dict) else {}
        if not normalized:
            normalized = normalize_hh_resume(
                format=row.format or "raw_text",
                resume_json=row.resume_json if isinstance(row.resume_json, dict) else None,
                resume_text=row.resume_text,
            )
        return normalized

    async def upsert_candidate_hh_resume(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        format: str,
        resume_json: dict[str, Any] | None,
        resume_text: str | None,
    ) -> dict[str, Any]:
        # Scope guard via existing context checker.
        await build_candidate_ai_context(candidate_id, principal=principal, include_pii=False)
        normalized = normalize_hh_resume(
            format=format,
            resume_json=resume_json if isinstance(resume_json, dict) else None,
            resume_text=resume_text,
        )
        content_hash = hash_resume_content(
            format=format,
            resume_json=resume_json if isinstance(resume_json, dict) else None,
            resume_text=resume_text,
        )

        now = datetime.now(UTC)
        async with async_session() as session:
            row = await session.scalar(
                select(CandidateHHResume).where(CandidateHHResume.candidate_id == candidate_id)
            )
            if row is None:
                row = CandidateHHResume(
                    candidate_id=candidate_id,
                    format=format,
                    resume_json=resume_json if isinstance(resume_json, dict) else None,
                    resume_text=resume_text,
                    normalized_json=normalized,
                    content_hash=content_hash,
                    source_quality_ok=bool(normalized.get("source_quality_ok")),
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.format = format
                row.resume_json = resume_json if isinstance(resume_json, dict) else None
                row.resume_text = resume_text
                row.normalized_json = normalized
                row.content_hash = content_hash
                row.source_quality_ok = bool(normalized.get("source_quality_ok"))
                row.updated_at = now
            await session.commit()

        await invalidate_candidate_ai_outputs(candidate_id)
        schedule_warm_candidate_ai_outputs(candidate_id, principal=principal, refresh=True)

        return {
            "normalized_resume": normalized,
            "content_hash": content_hash,
            "updated_at": now.isoformat(),
        }

    async def get_candidate_interview_script(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        refresh: bool = False,
        summary_result: AIResult | None = None,
    ) -> AIResult:
        self._ensure_enabled()
        kind = "interview_script_v1"
        prompt_version = PROMPT_VERSION_INTERVIEW_SCRIPT
        model = self._interview_script_model_for_candidate(candidate_id)
        if summary_result is None:
            summary_result = await self.get_candidate_summary(
                candidate_id,
                principal=principal,
                refresh=refresh,
            )
        summary_payload = summary_result.payload if isinstance(summary_result.payload, dict) else {}
        scorecard = summary_payload.get("scorecard") if isinstance(summary_payload.get("scorecard"), dict) else None

        base_ctx = await build_candidate_ai_context(
            candidate_id,
            principal=principal,
            include_pii=False,
        )
        candidate_state = {
            "status": (base_ctx.get("candidate") or {}).get("status"),
            "workflow_status": (base_ctx.get("candidate") or {}).get("workflow_status"),
            "last_activity": (base_ctx.get("candidate") or {}).get("last_activity"),
            "tests_completed": sorted((base_ctx.get("tests") or {}).get("latest", {}).keys()),
            "upcoming_slot_purpose": ((base_ctx.get("slots") or {}).get("upcoming") or {}).get("purpose"),
            "upcoming_slot_status": ((base_ctx.get("slots") or {}).get("upcoming") or {}).get("status"),
        }
        candidate_profile = base_ctx.get("candidate_profile") or {}
        hh_resume_norm = await self._get_hh_resume_normalized(candidate_id)
        office_context = await self._build_office_context(ctx=base_ctx)

        rag_query_parts = [
            str(office_context.get("city") or ""),
            str(office_context.get("vacancy") or ""),
            str(office_context.get("criteria") or ""),
            str(candidate_profile.get("work_experience") or ""),
            str(candidate_state.get("status") or ""),
        ]
        rag_query = " ".join(part for part in rag_query_parts if part).strip()
        from .knowledge_base import search_excerpts

        rag_context = await search_excerpts(
            rag_query or "правила и возражения рекрутинга",
            limit=6,
            categories=list(KB_INTERVIEW_SCRIPT_CATEGORIES),
        )
        rag_keys = sorted(
            {
                (int(item.get("document_id") or 0), int(item.get("chunk_index") or 0))
                for item in rag_context
                if isinstance(item, dict)
            }
        )

        input_envelope = {
            "candidate_state": candidate_state,
            "candidate_profile": candidate_profile,
            "hh_resume_normalized": hh_resume_norm,
            "office_context": office_context,
            "scorecard": scorecard,
            "rag_keys": [[document_id, chunk_index] for document_id, chunk_index in rag_keys],
            "model": model,
            "prompt_version": prompt_version,
        }
        input_hash = compute_input_hash(input_envelope)

        if not refresh:
            cached = await _get_cached_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None and isinstance(cached.payload_json, dict):
                payload = dict(cached.payload_json)
                if "script" not in payload:
                    payload = {
                        "generated_at": _iso(cached.created_at),
                        "model": model,
                        "prompt_version": prompt_version,
                        "script": payload,
                    }
                return AIResult(payload=payload, cached=True, input_hash=input_hash)

            fallback_script = build_interview_script_fallback(
                candidate_state=candidate_state,
                candidate_profile=candidate_profile,
                office_context=office_context,
                scorecard=scorecard,
                base_flags=build_base_risk_flags(candidate_profile, hh_resume_norm, office_context),
            )
            payload = {
                "generated_at": datetime.now(UTC).isoformat(),
                "model": "local-fallback",
                "prompt_version": prompt_version,
                "script": InterviewScriptPayload.model_validate(
                    build_structured_interview_script(
                        script_payload=fallback_script,
                        candidate_fio=(base_ctx.get("candidate") or {}).get("fio"),
                        candidate_profile=candidate_profile,
                        tests_context=base_ctx.get("tests") or {},
                        scorecard=scorecard,
                    )
                ).model_dump(),
            }
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=payload,
                ttl_hours=int(getattr(self._settings, "ai_interview_script_cache_ttl_hours", 24) or 24),
            )
            return AIResult(payload=payload, cached=False, input_hash=input_hash)

        await self._ensure_quota(principal)
        started = time.monotonic()
        script_tokens = int(getattr(self._settings, "ai_interview_script_max_tokens", 1800) or 1800)
        timeout_seconds = int(getattr(self._settings, "ai_interview_script_timeout_seconds", self._settings.ai_timeout_seconds))
        cache_ttl_hours = int(getattr(self._settings, "ai_interview_script_cache_ttl_hours", 24) or 24)

        try:
            generated = await generate_interview_script(
                candidate_state=candidate_state,
                candidate_profile=candidate_profile,
                hh_resume=hh_resume_norm,
                office_context=office_context,
                rag_context=rag_context,
                scorecard=scorecard,
                provider=self._provider,
                model=model,
                timeout_seconds=timeout_seconds,
                max_tokens=max(512, script_tokens),
                retries=2,
            )
            script_payload = InterviewScriptPayload.model_validate(
                build_structured_interview_script(
                    script_payload=generated.payload,
                    candidate_fio=(base_ctx.get("candidate") or {}).get("fio"),
                    candidate_profile=candidate_profile,
                    tests_context=base_ctx.get("tests") or {},
                    scorecard=scorecard,
                )
            ).model_dump()
            payload = {
                "generated_at": datetime.now(UTC).isoformat(),
                "model": model,
                "prompt_version": prompt_version,
                "script": script_payload,
            }

            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=generated.usage.tokens_in,
                tokens_out=generated.usage.tokens_out,
                status_value="ok",
                error_code="",
            )
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=payload,
                ttl_hours=cache_ttl_hours,
            )
            return AIResult(payload=payload, cached=False, input_hash=input_hash)
        except (ValidationError, AIProviderError, Exception) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.interview_script.failed", extra={"candidate_id": candidate_id}, exc_info=True)
            fallback_script = build_interview_script_fallback(
                candidate_state=candidate_state,
                candidate_profile=candidate_profile,
                office_context=office_context,
                scorecard=scorecard,
                base_flags=build_base_risk_flags(candidate_profile, hh_resume_norm, office_context),
            )
            payload = {
                "generated_at": datetime.now(UTC).isoformat(),
                "model": "local-fallback",
                "prompt_version": prompt_version,
                "script": InterviewScriptPayload.model_validate(
                    build_structured_interview_script(
                        script_payload=fallback_script,
                        candidate_fio=(base_ctx.get("candidate") or {}).get("fio"),
                        candidate_profile=candidate_profile,
                        tests_context=base_ctx.get("tests") or {},
                        scorecard=scorecard,
                    )
                ).model_dump(),
            }
            await _store_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
                payload=payload,
                ttl_hours=cache_ttl_hours,
            )
            return AIResult(payload=payload, cached=False, input_hash=input_hash)

    async def save_interview_script_feedback(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        validated = InterviewScriptFeedbackPayload.model_validate(payload)

        base_ctx = await build_candidate_ai_context(
            candidate_id,
            principal=principal,
            include_pii=False,
        )
        hh_resume_norm = await self._get_hh_resume_normalized(candidate_id)
        office_context = await self._build_office_context(ctx=base_ctx)
        input_redacted_json = {
            "candidate_profile": base_ctx.get("candidate_profile") or {},
            "hh_resume_normalized": hh_resume_norm,
            "office_context": office_context,
        }

        async with async_session() as session:
            existing = await session.scalar(
                select(AIInterviewScriptFeedback).where(
                    AIInterviewScriptFeedback.idempotency_key == validated.idempotency_key
                )
            )
            if existing is not None:
                return {"feedback_id": int(existing.id), "created": False}

            latest_output = await session.scalar(
                select(AIOutput)
                .where(
                    AIOutput.scope_type == "candidate",
                    AIOutput.scope_id == candidate_id,
                    AIOutput.kind == "interview_script_v1",
                )
                .order_by(AIOutput.created_at.desc(), AIOutput.id.desc())
                .limit(1)
            )

            output_original_json: dict[str, Any] = {}
            output_model = self._interview_script_model_for_candidate(candidate_id)
            output_prompt_version = PROMPT_VERSION_INTERVIEW_SCRIPT
            input_hash = ""
            if latest_output is not None:
                input_hash = latest_output.input_hash or ""
                src_payload = latest_output.payload_json if isinstance(latest_output.payload_json, dict) else {}
                if "script" in src_payload and isinstance(src_payload.get("script"), dict):
                    output_original_json = src_payload.get("script") or {}
                else:
                    output_original_json = src_payload
                output_model = str(src_payload.get("model") or output_model)
                output_prompt_version = str(src_payload.get("prompt_version") or output_prompt_version)

            final_script = validated.final_script.model_dump() if validated.final_script else None
            labels_json = {
                "helped": validated.helped,
                "edited": bool(validated.edited),
                "quick_reasons": list(validated.quick_reasons),
                "outcome": validated.outcome,
                "outcome_reason": validated.outcome_reason,
                "scorecard": validated.scorecard.model_dump() if validated.scorecard else None,
            }

            row = AIInterviewScriptFeedback(
                candidate_id=candidate_id,
                principal_type=principal.type,
                principal_id=principal.id,
                helped=validated.helped,
                edited=bool(validated.edited),
                quick_reasons_json=list(validated.quick_reasons),
                outcome=validated.outcome,
                outcome_reason=validated.outcome_reason,
                idempotency_key=validated.idempotency_key,
                input_redacted_json=input_redacted_json,
                output_original_json=output_original_json,
                output_final_json=final_script,
                labels_json=labels_json,
                input_hash=input_hash,
                model=output_model,
                prompt_version=output_prompt_version,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {"feedback_id": int(row.id), "created": True}

    async def get_agent_chat_state(
        self,
        *,
        principal: Principal,
        limit: int = 80,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Return (thread_id, messages) for the internal copilot chat."""

        self._ensure_enabled()
        limit_value = max(1, min(int(limit or 80), 200))

        async with async_session() as session:
            thread = await session.scalar(
                select(AIAgentThread).where(
                    AIAgentThread.principal_type == principal.type,
                    AIAgentThread.principal_id == principal.id,
                )
            )
            if thread is None:
                thread = AIAgentThread(
                    principal_type=principal.type,
                    principal_id=principal.id,
                    title="Copilot",
                )
                session.add(thread)
                await session.commit()
                await session.refresh(thread)

            rows = (
                await session.execute(
                    select(AIAgentMessage)
                    .where(AIAgentMessage.thread_id == thread.id)
                    .order_by(AIAgentMessage.created_at.desc(), AIAgentMessage.id.desc())
                    .limit(limit_value)
                )
            ).scalars().all()

        messages = [
            {
                "id": int(m.id),
                "role": str(m.role or "user"),
                "text": str(m.content_text or ""),
                "created_at": (m.created_at.astimezone(UTC).isoformat() if m.created_at else None),
                "meta": m.metadata_json or {},
            }
            for m in reversed(list(rows))
        ]
        return int(thread.id), messages

    async def send_agent_chat_message(
        self,
        *,
        principal: Principal,
        text: str,
        history_limit: int = 14,
        kb_limit: int = 5,
    ) -> dict[str, Any]:
        """Send a user message to the Copilot agent and get an AI reply.

        Flow:
        1. Redact PII from user message; reject if unsafe.
        2. Search KB for relevant excerpts.
        3. Load chat history.
        4. Call AI provider with context.
        5. Filter hallucinated KB sources.
        6. Persist assistant reply.

        Args:
            principal: Authenticated user.
            text: Raw user message (max 4000 chars).
            history_limit: Max previous messages to include as context.
            kb_limit: Max KB excerpts to retrieve.

        Returns:
            Dict with ``reply`` (AgentChatReplyV1) and ``kb_excerpts_used``.

        Raises:
            HTTPException 400: Empty message or PII detected.
            HTTPException 502: Provider error.
        """
        self._ensure_enabled()

        raw = (text or "").strip()
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Сообщение пустое"})
        if len(raw) > 4000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Сообщение слишком длинное"})

        if self._allow_pii:
            safe_text = raw[:2000]
            safe_to_send = True
            replacements = 0
        else:
            r = redact_text(raw, max_len=2000, mask_person_names=True)
            safe_text = r.text
            safe_to_send = r.safe_to_send
            replacements = r.replacements

        if not safe_to_send:
            # Store redacted input but do not call the provider.
            async with async_session() as session:
                thread = await session.scalar(
                    select(AIAgentThread).where(
                        AIAgentThread.principal_type == principal.type,
                        AIAgentThread.principal_id == principal.id,
                    )
                )
                if thread is None:
                    thread = AIAgentThread(
                        principal_type=principal.type,
                        principal_id=principal.id,
                        title="Copilot",
                    )
                    session.add(thread)
                    await session.commit()
                    await session.refresh(thread)

                session.add(
                    AIAgentMessage(
                        thread_id=int(thread.id),
                        role="user",
                        content_text=safe_text,
                        metadata_json={"safe_to_send": False, "replacements": int(replacements or 0)},
                    )
                )
                await session.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "В сообщении обнаружены потенциальные персональные данные. Уберите ФИО/телефон/ссылки и повторите.",
                    "error": "pii_detected",
                },
            )

        from .knowledge_base import (
            kb_state_snapshot,
            list_active_documents,
            search_excerpts,
        )

        kb_excerpts = await search_excerpts(safe_text, limit=max(1, min(int(kb_limit), 10)))
        kb_state = await kb_state_snapshot()
        kb_docs = await list_active_documents(limit=12)

        # If the query doesn't match anything but KB is present, include a small
        # default excerpt set so the agent can explain what regulations exist.
        if not kb_excerpts and int(kb_state.get("active_documents_total") or 0) > 0:
            kb_excerpts = await search_excerpts(
                "критерии оценки кандидатов регламент рекрутинга",
                limit=max(1, min(int(kb_limit), 3)),
            )

        history_limit_value = max(0, min(int(history_limit or 14), 30))
        thread_id: int
        async with async_session() as session:
            thread = await session.scalar(
                select(AIAgentThread).where(
                    AIAgentThread.principal_type == principal.type,
                    AIAgentThread.principal_id == principal.id,
                )
            )
            if thread is None:
                thread = AIAgentThread(
                    principal_type=principal.type,
                    principal_id=principal.id,
                    title="Copilot",
                )
                session.add(thread)
                await session.commit()
                await session.refresh(thread)
            thread_id = int(thread.id)

            # Load recent history (already redacted at write time).
            prev = (
                await session.execute(
                    select(AIAgentMessage)
                    .where(AIAgentMessage.thread_id == thread.id)
                    .order_by(AIAgentMessage.created_at.desc(), AIAgentMessage.id.desc())
                    .limit(history_limit_value)
                )
            ).scalars().all()
            prev_msgs = [
                {"role": str(m.role or "user"), "text": str(m.content_text or "")}
                for m in reversed(list(prev))
            ]

            # Persist the new user message first to keep order stable.
            session.add(
                AIAgentMessage(
                    thread_id=int(thread.id),
                    role="user",
                    content_text=safe_text,
                    metadata_json={"safe_to_send": True, "replacements": int(replacements or 0)},
                )
            )
            await session.commit()

        ctx = {
            "question": {"text": safe_text},
            "history": prev_msgs[-history_limit_value:] if history_limit_value else [],
            "knowledge_base": {
                "documents": kb_docs,
                "excerpts": kb_excerpts,
                "state": kb_state,
            },
        }

        kind = "agent_chat_reply_v1"
        model = self._settings.openai_model
        started = time.monotonic()
        try:
            await self._ensure_quota(principal)
            system_prompt, user_prompt = agent_chat_reply_prompts(context=ctx, allow_pii=self._allow_pii)
            payload, usage = await self._provider.generate_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout_seconds=int(self._settings.ai_timeout_seconds),
                max_tokens=int(self._settings.ai_max_tokens),
            )
            validated = AgentChatReplyV1.model_validate(payload).model_dump()

            # Only allow sources from excerpts we actually provided.
            allowed = {
                (int(ex.get("document_id") or 0), int(ex.get("chunk_index") or 0)): ex
                for ex in (kb_excerpts or [])
                if isinstance(ex, dict)
            }
            filtered_sources = []
            for src in validated.get("kb_sources") or []:
                if not isinstance(src, dict):
                    continue
                key = (int(src.get("document_id") or 0), int(src.get("chunk_index") or 0))
                if key in allowed:
                    filtered_sources.append(
                        {
                            "document_id": key[0],
                            "title": str(allowed[key].get("document_title") or src.get("title") or ""),
                            "chunk_index": key[1],
                        }
                    )
            validated["kb_sources"] = filtered_sources[:6]

            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="thread",
                scope_id=thread_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                status_value="ok",
                error_code="",
            )

            async with async_session() as session:
                thread = await session.scalar(
                    select(AIAgentThread).where(
                        AIAgentThread.principal_type == principal.type,
                        AIAgentThread.principal_id == principal.id,
                    )
                )
                if thread is not None:
                    session.add(
                        AIAgentMessage(
                            thread_id=int(thread.id),
                            role="assistant",
                            content_text=str(validated.get("answer") or "").strip(),
                            metadata_json={
                                "confidence": validated.get("confidence"),
                                "kb_sources": validated.get("kb_sources") or [],
                            },
                        )
                    )
                    await session.commit()

            return {"reply": validated, "kb_excerpts_used": kb_excerpts}
        except HTTPException:
            raise
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            await _log_request(
                principal=principal,
                scope_type="thread",
                scope_id=thread_id,
                kind=kind,
                provider=self._provider.name,
                model=model,
                latency_ms=latency_ms,
                tokens_in=0,
                tokens_out=0,
                status_value="error",
                error_code=exc.__class__.__name__,
            )
            logger.warning("ai.agent_chat.failed", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc


def get_ai_service() -> AIService:
    """FastAPI dependency that provides a fresh AIService instance per request."""
    return AIService()
