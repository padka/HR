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

import logging
import hashlib
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select

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

from .context import (
    build_candidate_ai_context,
    build_city_candidate_recommendations_context,
    compute_input_hash,
    get_last_inbound_message_text,
)
from .prompts import (
    agent_chat_reply_prompts,
    candidate_coach_drafts_prompts,
    candidate_coach_prompts,
    candidate_summary_prompts,
    chat_reply_drafts_prompts,
    city_candidate_recommendations_prompts,
    dashboard_insight_prompts,
)
from .llm_script_generator import (
    KB_INTERVIEW_SCRIPT_CATEGORIES,
    PROMPT_VERSION_INTERVIEW_SCRIPT,
    generate_interview_script,
    hash_resume_content,
    normalize_hh_resume,
)
from .providers import AIProvider, AIProviderError, FakeProvider, OpenAIProvider
from .redaction import redact_text
from .schemas import (
    AgentChatReplyV1,
    CandidateCoachV1,
    CandidateSummaryV1,
    ChatReplyDraftsV1,
    CityCandidateRecommendationsV1,
    DashboardInsightV1,
    InterviewScriptFeedbackPayload,
    InterviewScriptPayload,
)

logger = logging.getLogger(__name__)


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
                return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

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
            validated = CandidateSummaryV1.model_validate(payload).model_dump()
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc

    async def get_candidate_coach(
        self,
        candidate_id: int,
        *,
        principal: Principal,
        refresh: bool = False,
    ) -> AIResult:
        self._ensure_enabled()
        ctx = await build_candidate_ai_context(candidate_id, principal=principal, include_pii=self._allow_pii)
        input_hash = compute_input_hash(ctx)
        kind = "candidate_coach_v1"

        if not refresh:
            cached = await _get_cached_output(
                scope_type="candidate",
                scope_id=candidate_id,
                kind=kind,
                input_hash=input_hash,
            )
            if cached is not None:
                return AIResult(payload=cached.payload_json, cached=True, input_hash=input_hash)

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
            validated = CandidateCoachV1.model_validate(payload).model_dump()
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc

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

        digest = hashlib.sha256(f"interview_script:{candidate_id}".encode("utf-8")).hexdigest()
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
    ) -> AIResult:
        self._ensure_enabled()
        kind = "interview_script_v1"
        prompt_version = PROMPT_VERSION_INTERVIEW_SCRIPT
        model = self._interview_script_model_for_candidate(candidate_id)

        base_ctx = await build_candidate_ai_context(
            candidate_id,
            principal=principal,
            include_pii=False,
        )
        candidate_profile = base_ctx.get("candidate_profile") or {}
        hh_resume_norm = await self._get_hh_resume_normalized(candidate_id)
        office_context = await self._build_office_context(ctx=base_ctx)

        rag_query_parts = [
            str(office_context.get("city") or ""),
            str(office_context.get("vacancy") or ""),
            str(office_context.get("criteria") or ""),
            str(candidate_profile.get("work_experience") or ""),
        ]
        rag_query = " ".join(part for part in rag_query_parts if part).strip()
        from .knowledge_base import search_excerpts

        rag_context = await search_excerpts(
            rag_query or "правила и возражения рекрутинга",
            limit=6,
            categories=list(KB_INTERVIEW_SCRIPT_CATEGORIES),
        )

        input_envelope = {
            "candidate_profile": candidate_profile,
            "hh_resume_normalized": hh_resume_norm,
            "office_context": office_context,
            "rag_keys": [
                [int(item.get("document_id") or 0), int(item.get("chunk_index") or 0)]
                for item in rag_context
                if isinstance(item, dict)
            ],
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

        await self._ensure_quota(principal)
        started = time.monotonic()
        script_tokens = int(getattr(self._settings, "ai_interview_script_max_tokens", 1800) or 1800)
        timeout_seconds = int(getattr(self._settings, "ai_interview_script_timeout_seconds", self._settings.ai_timeout_seconds))
        cache_ttl_hours = int(getattr(self._settings, "ai_interview_script_cache_ttl_hours", 24) or 24)

        try:
            generated = await generate_interview_script(
                candidate_profile=candidate_profile,
                hh_resume=hh_resume_norm,
                office_context=office_context,
                rag_context=rag_context,
                provider=self._provider,
                model=model,
                timeout_seconds=timeout_seconds,
                max_tokens=max(512, script_tokens),
                retries=2,
            )
            script_payload = InterviewScriptPayload.model_validate(generated.payload).model_dump()
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": "AI provider error"},
            ) from exc

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
