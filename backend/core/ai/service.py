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
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select

from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain import analytics
from backend.domain.ai.models import (
    AIAgentMessage,
    AIAgentThread,
    AIOutput,
    AIRequestLog,
)
from backend.domain.candidates.models import User
from backend.domain.models import Recruiter

from .context import (
    build_candidate_ai_context,
    build_city_candidate_recommendations_context,
    compute_input_hash,
    get_last_inbound_message_text,
)
from .prompts import (
    agent_chat_reply_prompts,
    candidate_summary_prompts,
    chat_reply_drafts_prompts,
    city_candidate_recommendations_prompts,
    dashboard_insight_prompts,
)
from .providers import AIProvider, AIProviderError, FakeProvider, OpenAIProvider
from .redaction import redact_text
from .schemas import (
    AgentChatReplyV1,
    CandidateSummaryV1,
    ChatReplyDraftsV1,
    CityCandidateRecommendationsV1,
    DashboardInsightV1,
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
