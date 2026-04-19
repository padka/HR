from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.security import Principal, principal_ctx
from backend.apps.admin_ui.services.candidates.helpers import (
    STATUSES_ARCHIVE_ON_DECLINE,
    _has_passed_test2,
    _latest_test_result_by_rating,
    _recruiter_can_access_candidate,
    _release_intro_day_slots_for_candidate,
    get_candidate_detail,
    update_candidate_status,
)
from backend.apps.admin_ui.services.slots import (
    BotDispatch,
    BotDispatchPlan,
    _trigger_test2,
    set_slot_outcome,
)
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.applications.persistent_idempotency import (
    PersistentIdempotencyConflictError,
)
from backend.domain.candidates.journey import append_journey_event
from backend.domain.candidates.models import (
    CandidateJourneySession,
    CandidateJourneyStepState,
    TestResult,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import (
    StatusTransitionError,
    apply_candidate_status,
)
from backend.domain.candidates.test1_shared import (
    TEST1_STEP_KEY,
    build_test1_restart_snapshot,
    reset_test1_progress,
)
from backend.domain.models import Slot

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.apps.admin_ui.services.candidates.application_dual_write import (
        CandidateStatusDualWriteRequest,
    )


@lru_cache(maxsize=1)
def _candidate_dual_write_runtime() -> SimpleNamespace:
    from backend.apps.admin_ui.services.candidates.application_dual_write import (
        CandidateStatusDualWriteRequest,
        build_candidate_status_fallback_idempotency_key,
        build_candidate_status_payload_fingerprint,
        claim_candidate_status_transition,
        finalize_candidate_status_dual_write,
    )

    return SimpleNamespace(
        CandidateStatusDualWriteRequest=CandidateStatusDualWriteRequest,
        build_candidate_status_fallback_idempotency_key=build_candidate_status_fallback_idempotency_key,
        build_candidate_status_payload_fingerprint=build_candidate_status_payload_fingerprint,
        claim_candidate_status_transition=claim_candidate_status_transition,
        finalize_candidate_status_dual_write=finalize_candidate_status_dual_write,
    )


ALLOWED_SEND_TO_TEST2_STATUSES = {
    CandidateStatus.INTERVIEW_SCHEDULED.value,
    CandidateStatus.INTERVIEW_CONFIRMED.value,
}

ALLOWED_FINALIZE_STATUSES = {
    CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY.value,
    CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF.value,
}

NEGATIVE_REASON_STATUSES = {
    CandidateStatus.INTERVIEW_DECLINED,
    CandidateStatus.TEST2_FAILED,
    CandidateStatus.NOT_HIRED,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF,
}

ALLOWED_RESTART_TEST1_STATUSES = {
    CandidateStatus.TEST1_COMPLETED.value,
    CandidateStatus.WAITING_SLOT.value,
    CandidateStatus.STALLED_WAITING_SLOT.value,
    CandidateStatus.INTERVIEW_DECLINED.value,
    CandidateStatus.TEST2_FAILED.value,
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION.value,
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF.value,
    CandidateStatus.NOT_HIRED.value,
}


@dataclass
class LifecycleUseCaseResult:
    ok: bool
    message: str
    status_code: int
    status: Optional[str] = None
    error: Optional[str] = None
    dispatch: Optional[object] = None
    detail: Optional[dict[str, Any]] = None


def _detail_action_allowed(detail: Mapping[str, Any], action_key: Optional[str]) -> bool:
    normalized = str(action_key or "").strip().lower()
    if not normalized:
        return True
    actions = detail.get("candidate_actions", []) or []
    for action in actions:
        key = action.get("key") if isinstance(action, Mapping) else getattr(action, "key", None)
        if str(key or "").strip().lower() == normalized:
            return True
    return False


def _detail_status_slug(detail: Mapping[str, Any]) -> Optional[str]:
    return str(detail.get("candidate_status_slug") or "").strip().lower() or None


def _issue_codes(detail: Mapping[str, Any]) -> set[str]:
    reconciliation = detail.get("state_reconciliation") or {}
    issues = reconciliation.get("issues") or []
    return {
        str(issue.get("code") or "").strip().lower()
        for issue in issues
        if isinstance(issue, Mapping) and str(issue.get("code") or "").strip()
    }


def _has_scheduling_conflict(detail: Mapping[str, Any]) -> bool:
    operational_summary = detail.get("operational_summary") or {}
    if operational_summary.get("has_scheduling_conflict"):
        return True
    return any(code.startswith("scheduling_") for code in _issue_codes(detail))


def _has_any_active_scheduling(detail: Mapping[str, Any]) -> bool:
    scheduling_summary = detail.get("scheduling_summary") or {}
    return bool(scheduling_summary.get("active"))


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _detail_slots(detail: Mapping[str, Any]) -> list[Slot]:
    return list(detail.get("slots", []) or [])


def _resolve_actor(principal: Optional[Principal]) -> tuple[Optional[str], Optional[int]]:
    principal = principal or principal_ctx.get()
    if principal is None:
        return None, None
    return getattr(principal, "type", None), getattr(principal, "id", None)


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _build_lifecycle_dual_write_request(
    *,
    candidate_id: int,
    status_from: str | None,
    status_to: CandidateStatus,
    reason: str | None,
    comment: str | None,
    principal: Optional[Principal],
    previous_status_changed_at: datetime | None,
    source_ref: str,
) -> CandidateStatusDualWriteRequest:
    runtime = _candidate_dual_write_runtime()
    actor_type, actor_id = _resolve_actor(principal)
    normalized_reason = _normalize_optional_text(reason)
    normalized_comment = _normalize_optional_text(comment)
    return runtime.CandidateStatusDualWriteRequest(
        idempotency_key=runtime.build_candidate_status_fallback_idempotency_key(
            candidate_id=candidate_id,
            status_from=status_from,
            status_to=status_to,
            reason=normalized_reason,
            comment=normalized_comment,
            principal_type=actor_type,
            principal_id=actor_id,
            previous_status_changed_at=previous_status_changed_at,
            source_ref=source_ref,
        ),
        correlation_id=f"candidate-lifecycle-{secrets.token_hex(12)}",
        payload_fingerprint=runtime.build_candidate_status_payload_fingerprint(
            candidate_id=candidate_id,
            status_to=status_to,
            reason=normalized_reason,
            comment=normalized_comment,
            principal_type=actor_type,
            principal_id=actor_id,
            source_ref=source_ref,
        ),
        principal_type=actor_type,
        principal_id=actor_id,
        source_ref=source_ref,
    )


async def _refresh_detail(candidate_id: int, principal: Optional[Principal]) -> Optional[dict[str, Any]]:
    return await get_candidate_detail(candidate_id, principal=principal)


async def _load_candidate_for_write(
    session,
    candidate_id: int,
    principal: Optional[Principal],
    *,
    include_test_results: bool = False,
) -> Optional[User]:
    query = select(User).where(User.id == candidate_id)
    if include_test_results:
        query = query.options(selectinload(User.test_results))
    user = await session.scalar(query)
    if not user:
        return None
    if principal and principal.type == "recruiter":
        if not await _recruiter_can_access_candidate(session, user, principal.id):
            return None
        if user.responsible_recruiter_id is None:
            user.responsible_recruiter_id = principal.id
    return user


def _resolve_interview_slot_id(detail: Mapping[str, Any]) -> tuple[Optional[int], str]:
    scheduling_summary = detail.get("scheduling_summary") or {}
    stage = str(scheduling_summary.get("stage") or "").strip().lower()
    slot_id = scheduling_summary.get("slot_id")
    if stage == "interview" and slot_id:
        try:
            return int(slot_id), "contract"
        except (TypeError, ValueError):
            pass

    now = datetime.now(timezone.utc)
    interview_slots: list[tuple[Slot, Optional[datetime]]] = []
    for slot in _detail_slots(detail):
        if str(getattr(slot, "purpose", "") or "").strip().lower() != "interview":
            continue
        start_utc = _ensure_aware(getattr(slot, "start_utc", None))
        interview_slots.append((slot, start_utc))

    upcoming = sorted(
        (
            (slot, start_utc)
            for slot, start_utc in interview_slots
            if start_utc is not None and start_utc >= now
        ),
        key=lambda item: (item[1], getattr(item[0], "id", 0)),
    )
    if upcoming:
        return int(getattr(upcoming[0][0], "id")), "fallback_upcoming"

    latest = sorted(
        interview_slots,
        key=lambda item: (
            item[1] or datetime.min.replace(tzinfo=timezone.utc),
            getattr(item[0], "id", 0),
        ),
        reverse=True,
    )
    if latest:
        return int(getattr(latest[0][0], "id")), "fallback_latest"

    if stage == "interview" and scheduling_summary.get("active"):
        return None, "missing_interview_slot"
    return None, "missing_interview_scheduling"


def _resolve_intro_day_slot(detail: Mapping[str, Any]) -> Optional[Slot]:
    now = datetime.now(timezone.utc)
    intro_slots = [
        (slot, _ensure_aware(getattr(slot, "start_utc", None)))
        for slot in _detail_slots(detail)
        if str(getattr(slot, "purpose", "") or "").strip().lower() == "intro_day"
    ]
    upcoming = sorted(
        (
            (slot, start_utc)
            for slot, start_utc in intro_slots
            if start_utc is not None and start_utc >= now
        ),
        key=lambda item: (item[1], getattr(item[0], "id", 0)),
    )
    if upcoming:
        return upcoming[0][0]
    latest = sorted(
        intro_slots,
        key=lambda item: (
            item[1] or datetime.min.replace(tzinfo=timezone.utc),
            getattr(item[0], "id", 0),
        ),
        reverse=True,
    )
    return latest[0][0] if latest else None


def _persist_reason_comment(
    user: User,
    *,
    target_status: CandidateStatus,
    reason: Optional[str],
    comment: Optional[str],
) -> None:
    if reason:
        user.rejection_reason = reason
    if not comment:
        return
    if not user.rejection_reason and target_status in NEGATIVE_REASON_STATUSES:
        user.rejection_reason = comment
        return
    user.manual_slot_comment = (user.manual_slot_comment or "") + f"\n{comment}"


def _resolved_rejection_reason(
    user: User,
    *,
    reason: Optional[str],
    comment: Optional[str],
) -> Optional[str]:
    return (
        (reason or "").strip()
        or (comment or "").strip()
        or (getattr(user, "rejection_reason", None) or "").strip()
        or None
    )


async def _dispatch_hh_status_sync_if_enabled(
    user: User,
    target_status: CandidateStatus,
    *,
    session,
) -> None:
    if not get_settings().hh_sync_enabled:
        return
    try:
        from backend.domain.hh_integration.outbound import enqueue_candidate_status_sync

        await enqueue_candidate_status_sync(
            session,
            candidate=user,
            target_status=target_status,
        )
    except Exception:
        logger.exception(
            "hh_sync: failed to enqueue direct HH status sync",
            extra={"candidate_id": user.id, "status": target_status.value},
        )


async def _log_candidate_status_updated(
    candidate_id: int,
    *,
    previous_status: Optional[str],
    target_status: str,
    slot_id: Optional[int] = None,
) -> None:
    await log_audit_action(
        "candidate_status_updated",
        "candidate",
        candidate_id,
        changes={
            "from": previous_status,
            "to": target_status,
            "slot_id": slot_id,
        },
    )


async def _log_test1_restarted(
    candidate_id: int,
    *,
    previous_status: Optional[str],
    restart_snapshot: Mapping[str, Any] | None,
) -> None:
    await log_audit_action(
        "candidate_test1_restarted",
        "candidate",
        candidate_id,
        changes={
            "from": previous_status,
            "to": CandidateStatus.INVITED.value,
            "previous_test_result_id": (
                int(restart_snapshot.get("test_result_id"))
                if restart_snapshot and restart_snapshot.get("test_result_id") is not None
                else None
            ),
            "previous_step": restart_snapshot.get("current_step_key") if restart_snapshot else None,
        },
    )


def _build_not_hired_dispatch(
    user: User,
    *,
    target_slot: Optional[Slot],
    rejection_reason: Optional[str],
) -> Optional[BotDispatch]:
    if CandidateStatus.NOT_HIRED not in STATUSES_ARCHIVE_ON_DECLINE:
        return None
    if getattr(user, "telegram_id", None) is None:
        return None

    template_key = get_settings().rejection_template_key or "candidate_rejection"
    if template_key == "rejection_generic":
        template_key = "candidate_rejection"

    city_name = ""
    city_id = None
    if target_slot is not None:
        city_id = getattr(target_slot, "candidate_city_id", None) or getattr(target_slot, "city_id", None)
        if getattr(target_slot, "city", None):
            city_name = (
                getattr(target_slot.city, "name_plain", "")
                or getattr(target_slot.city, "name", "")
                or ""
            )
    if not city_name and getattr(user, "city", None):
        city_name = user.city or ""

    candidate_name = user.fio or getattr(user, "name", "") or ""
    template_context = {
        "candidate_name": candidate_name,
        "candidate_fio": candidate_name,
        "city_name": city_name,
    }
    if rejection_reason:
        template_context["rejection_reason"] = rejection_reason

    return BotDispatch(
        status="sent_rejection",
        plan=BotDispatchPlan(
            kind="rejection",
            slot_id=target_slot.id if target_slot is not None else 0,
            candidate_id=int(user.telegram_id),
            candidate_name=candidate_name,
            candidate_city_id=city_id,
            template_key=template_key,
            template_context=template_context,
            scheduled_at=datetime.now(timezone.utc),
        ),
    )


def _test2_latest_result_state(results: Sequence[TestResult]) -> tuple[Optional[TestResult], bool]:
    latest = _latest_test_result_by_rating(results, "TEST2")
    if latest is None:
        return None, False
    return latest, _has_passed_test2([latest])


def _result(
    *,
    ok: bool,
    message: str,
    status_code: int,
    status: Optional[str] = None,
    error: Optional[str] = None,
    dispatch: Optional[object] = None,
    detail: Optional[dict[str, Any]] = None,
) -> LifecycleUseCaseResult:
    return LifecycleUseCaseResult(
        ok=ok,
        message=message,
        status_code=status_code,
        status=status,
        error=error,
        dispatch=dispatch,
        detail=detail,
    )


async def execute_send_to_test2(
    candidate_id: int,
    *,
    principal: Optional[Principal],
    bot_service: Optional[object],
    action_key: Optional[str] = None,
) -> LifecycleUseCaseResult:
    principal = principal or principal_ctx.get()
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return _result(
            ok=False,
            message="Candidate not found",
            status_code=404,
            error="candidate_not_found",
        )

    current_status = _detail_status_slug(detail)
    if current_status not in ALLOWED_SEND_TO_TEST2_STATUSES:
        return _result(
            ok=False,
            message="Действие недоступно для текущего статуса кандидата",
            status_code=409,
            error="invalid_transition",
            detail=detail,
            status=current_status,
        )

    if action_key and not _detail_action_allowed(detail, action_key):
        return _result(
            ok=False,
            message="Действие недоступно в текущем статусе",
            status_code=400,
            error="action_not_allowed",
            detail=detail,
            status=current_status,
        )

    if _has_scheduling_conflict(detail):
        return _result(
            ok=False,
            message="Нельзя выполнить действие: Slot и SlotAssignment расходятся. Сначала проверьте scheduling.",
            status_code=409,
            error="scheduling_conflict",
            detail=detail,
            status=current_status,
        )

    slot_id, slot_resolution = _resolve_interview_slot_id(detail)
    if slot_id is None:
        error = "missing_interview_slot" if slot_resolution == "missing_interview_slot" else "missing_interview_scheduling"
        message = (
            "Для действия нужен активный interview slot в scheduling contract."
            if error == "missing_interview_scheduling"
            else "Не удалось определить interview slot для кандидата."
        )
        return _result(
            ok=False,
            message=message,
            status_code=409,
            error=error,
            detail=detail,
            status=current_status,
        )

    ok, message, _stored, dispatch = await set_slot_outcome(
        slot_id,
        "success",
        bot_service=bot_service,
        principal=principal,
    )
    if not ok:
        return _result(
            ok=False,
            message=message or "Не удалось сохранить исход интервью.",
            status_code=409,
            error="missing_interview_slot",
            detail=detail,
            status=current_status,
        )

    actor_type, actor_id = _resolve_actor(principal)
    async with async_session() as session:
        user = await _load_candidate_for_write(session, candidate_id, principal)
        if not user:
            refreshed = await _refresh_detail(candidate_id, principal)
            return _result(
                ok=False,
                message="Candidate not found",
                status_code=404,
                error="candidate_not_found",
                detail=refreshed,
            )
        previous_status = getattr(getattr(user, "candidate_status", None), "value", None)
        dual_write_request = None
        dual_write_claim = None
        if get_settings().candidate_status_dual_write_enabled:
            dual_write_request = _build_lifecycle_dual_write_request(
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.TEST2_SENT,
                reason=None,
                comment=None,
                principal=principal,
                previous_status_changed_at=getattr(user, "status_changed_at", None),
                source_ref="lifecycle:send_to_test2",
            )
            try:
                dual_write_runtime = _candidate_dual_write_runtime()
                dual_write_claim = await dual_write_runtime.claim_candidate_status_transition(
                    session,
                    dual_write_request,
                )
            except PersistentIdempotencyConflictError:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=False,
                    message="Конфликт идемпотентности для перехода кандидата в Тест 2",
                    status_code=409,
                    error="idempotency_conflict",
                    detail=refreshed,
                    status=_detail_status_slug(refreshed or {}),
                )
            if dual_write_claim.reused:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=True,
                    message="Тест 2 уже был отправлен для этого перехода",
                    status_code=200,
                    status=CandidateStatus.TEST2_SENT.value,
                    detail=refreshed,
                )
        try:
            await apply_candidate_status(
                user,
                CandidateStatus.TEST2_SENT,
                session=session,
                force=False,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        except StatusTransitionError:
            await session.rollback()
            refreshed = await _refresh_detail(candidate_id, principal)
            return _result(
                ok=False,
                message="Исход интервью сохранен, но статус кандидата не обновился. Нужна ручная проверка.",
                status_code=409,
                error="partial_transition_requires_repair",
                detail=refreshed,
                status=_detail_status_slug(refreshed or {}),
            )

        await _dispatch_hh_status_sync_if_enabled(
            user,
            CandidateStatus.TEST2_SENT,
            session=session,
        )
        if dual_write_request is not None and dual_write_claim is not None:
            await dual_write_runtime.finalize_candidate_status_dual_write(
                session,
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.TEST2_SENT.value,
                reason=None,
                comment=None,
                request=dual_write_request,
            )
        await session.commit()

    await _log_candidate_status_updated(
        candidate_id,
        previous_status=previous_status,
        target_status=CandidateStatus.TEST2_SENT.value,
        slot_id=slot_id,
    )
    refreshed = await _refresh_detail(candidate_id, principal)
    return _result(
        ok=True,
        message=message or "Тест 2 отправлен",
        status_code=200,
        status=CandidateStatus.TEST2_SENT.value,
        dispatch=dispatch,
        detail=refreshed,
    )


async def execute_resend_test2(
    candidate_id: int,
    *,
    principal: Optional[Principal],
    bot_service: Optional[object],
    action_key: Optional[str] = None,
) -> LifecycleUseCaseResult:
    principal = principal or principal_ctx.get()
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return _result(
            ok=False,
            message="Candidate not found",
            status_code=404,
            error="candidate_not_found",
        )

    current_status = _detail_status_slug(detail)
    if action_key and not _detail_action_allowed(detail, action_key):
        return _result(
            ok=False,
            message="Действие недоступно в текущем статусе",
            status_code=400,
            error="action_not_allowed",
            detail=detail,
            status=current_status,
        )

    candidate = detail.get("user")
    if not isinstance(candidate, User):
        return _result(
            ok=False,
            message="Кандидат не найден",
            status_code=404,
            error="candidate_not_found",
            detail=detail,
            status=current_status,
        )

    telegram_id = getattr(candidate, "telegram_user_id", None) or getattr(candidate, "telegram_id", None)
    max_user_id = str(getattr(candidate, "max_user_id", "") or "").strip() or None
    if not telegram_id and not max_user_id:
        return _result(
            ok=False,
            message="У кандидата нет доступного канала для отправки Теста 2",
            status_code=400,
            error="missing_candidate_channel",
            detail=detail,
            status=current_status,
        )

    slot_filters = []
    if telegram_id:
        slot_filters.append(Slot.candidate_tg_id == telegram_id)
    if candidate.candidate_id is not None:
        slot_filters.append(Slot.candidate_id == candidate.candidate_id)

    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .where(
                or_(*slot_filters)
            )
            .order_by(Slot.start_utc.desc(), Slot.id.desc())
            .limit(1)
        )
        if slot is not None:
            slot.test2_sent_at = datetime.now(timezone.utc)
            await session.commit()

    candidate_city_id = (
        getattr(slot, "candidate_city_id", None)
        or getattr(slot, "city_id", None)
        or getattr(candidate, "city_id", None)
    )
    candidate_tz = (
        getattr(slot, "candidate_tz", None)
        or getattr(candidate, "tz_name", None)
        or get_settings().timezone
    )

    result = await _trigger_test2(
        int(telegram_id or 0),
        candidate_tz,
        candidate_city_id,
        candidate.fio or getattr(candidate, "name", "") or "Кандидат",
        bot_service=bot_service,
        required=get_settings().test2_required,
        slot_id=getattr(slot, "id", None),
        candidate_public_id=str(candidate.candidate_id or "") or None,
        max_user_id=max_user_id,
    )

    stored_status = current_status
    if result.ok:
        ok, message, stored_status, _dispatch = await update_candidate_status(
            candidate_id,
            "test2_sent",
            bot_service=bot_service,
            principal=principal,
        )
        if not ok:
            return _result(
                ok=False,
                message=message or "Не удалось обновить статус кандидата.",
                status_code=400,
                error="status_update_failed",
                detail=detail,
                status=current_status,
            )

    refreshed_detail = await get_candidate_detail(candidate_id, principal=principal)
    return _result(
        ok=result.ok,
        message=result.message or result.error or "",
        status_code=200 if result.ok else 400,
        status=stored_status or _detail_status_slug(refreshed_detail or detail),
        error=None if result.ok else "test2_dispatch_failed",
        detail=refreshed_detail or detail,
    )


async def execute_mark_test2_completed(
    candidate_id: int,
    *,
    principal: Optional[Principal],
) -> LifecycleUseCaseResult:
    principal = principal or principal_ctx.get()
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return _result(
            ok=False,
            message="Candidate not found",
            status_code=404,
            error="candidate_not_found",
        )

    current_status = _detail_status_slug(detail)
    if current_status != CandidateStatus.TEST2_SENT.value:
        return _result(
            ok=False,
            message="Перевод в «Тест 2 пройден» доступен только после отправки Теста 2",
            status_code=409,
            error="invalid_transition",
            detail=detail,
            status=current_status,
        )

    actor_type, actor_id = _resolve_actor(principal)
    async with async_session() as session:
        user = await _load_candidate_for_write(
            session,
            candidate_id,
            principal,
            include_test_results=True,
        )
        if not user:
            return _result(
                ok=False,
                message="Candidate not found",
                status_code=404,
                error="candidate_not_found",
                detail=detail,
            )

        latest_test2, passed = _test2_latest_result_state(list(user.test_results or []))
        if latest_test2 is None:
            return _result(
                ok=False,
                message="Нельзя завершить этап: результат Теста 2 не найден",
                status_code=409,
                error="test2_not_passed",
                detail=detail,
                status=current_status,
            )
        if not passed:
            return _result(
                ok=False,
                message="Нельзя завершить этап: последний результат Теста 2 не является проходным",
                status_code=409,
                error="test2_not_passed",
                detail=detail,
                status=current_status,
            )

        previous_status = getattr(getattr(user, "candidate_status", None), "value", None)
        dual_write_request = None
        dual_write_claim = None
        if get_settings().candidate_status_dual_write_enabled:
            dual_write_request = _build_lifecycle_dual_write_request(
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.TEST2_COMPLETED,
                reason=None,
                comment=None,
                principal=principal,
                previous_status_changed_at=getattr(user, "status_changed_at", None),
                source_ref="lifecycle:mark_test2_completed",
            )
            try:
                dual_write_runtime = _candidate_dual_write_runtime()
                dual_write_claim = await dual_write_runtime.claim_candidate_status_transition(
                    session,
                    dual_write_request,
                )
            except PersistentIdempotencyConflictError:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=False,
                    message="Конфликт идемпотентности для завершения Теста 2",
                    status_code=409,
                    error="idempotency_conflict",
                    detail=refreshed,
                    status=_detail_status_slug(refreshed or {}),
                )
            if dual_write_claim.reused:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=True,
                    message="Тест 2 уже был отмечен как пройденный",
                    status_code=200,
                    status=CandidateStatus.TEST2_COMPLETED.value,
                    detail=refreshed,
                )
        try:
            await apply_candidate_status(
                user,
                CandidateStatus.TEST2_COMPLETED,
                session=session,
                force=False,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        except StatusTransitionError:
            await session.rollback()
            refreshed = await _refresh_detail(candidate_id, principal)
            return _result(
                ok=False,
                message="Недопустимый lifecycle transition для завершения Теста 2",
                status_code=409,
                error="invalid_transition",
                detail=refreshed,
                status=_detail_status_slug(refreshed or {}),
            )

        await _dispatch_hh_status_sync_if_enabled(
            user,
            CandidateStatus.TEST2_COMPLETED,
            session=session,
        )
        if dual_write_request is not None and dual_write_claim is not None:
            await dual_write_runtime.finalize_candidate_status_dual_write(
                session,
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.TEST2_COMPLETED.value,
                reason=None,
                comment=None,
                request=dual_write_request,
            )
        await session.commit()

    await _log_candidate_status_updated(
        candidate_id,
        previous_status=previous_status,
        target_status=CandidateStatus.TEST2_COMPLETED.value,
    )
    refreshed = await _refresh_detail(candidate_id, principal)
    return _result(
        ok=True,
        message="Тест 2 отмечен как пройденный",
        status_code=200,
        status=CandidateStatus.TEST2_COMPLETED.value,
        detail=refreshed,
    )


async def execute_restart_test1(
    candidate_id: int,
    *,
    principal: Optional[Principal],
    action_key: Optional[str] = None,
    reason: Optional[str] = None,
    comment: Optional[str] = None,
) -> LifecycleUseCaseResult:
    principal = principal or principal_ctx.get()
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return _result(
            ok=False,
            message="Candidate not found",
            status_code=404,
            error="candidate_not_found",
        )

    current_status = _detail_status_slug(detail)
    if current_status not in ALLOWED_RESTART_TEST1_STATUSES:
        return _result(
            ok=False,
            message="Повторное прохождение Теста 1 доступно только после завершенного или закрытого этапа отбора.",
            status_code=409,
            error="invalid_transition",
            detail=detail,
            status=current_status,
        )

    if action_key and not _detail_action_allowed(detail, action_key):
        return _result(
            ok=False,
            message="Действие недоступно в текущем статусе",
            status_code=400,
            error="action_not_allowed",
            detail=detail,
            status=current_status,
        )

    if _has_scheduling_conflict(detail):
        return _result(
            ok=False,
            message="Нельзя перезапустить Тест 1: в scheduling contract есть конфликт. Сначала разберите слоты.",
            status_code=409,
            error="scheduling_conflict",
            detail=detail,
            status=current_status,
        )

    if _has_any_active_scheduling(detail):
        return _result(
            ok=False,
            message="Нельзя перезапустить Тест 1, пока у кандидата есть активный слот или назначенный этап.",
            status_code=409,
            error="active_scheduling_exists",
            detail=detail,
            status=current_status,
        )

    actor_type, actor_id = _resolve_actor(principal)
    restart_reason = (
        _normalize_optional_text(reason)
        or _normalize_optional_text(comment)
        or "restart_test1_for_new_selection_cycle"
    )
    restart_snapshot: dict[str, Any] | None = None

    async with async_session() as session:
        user = await _load_candidate_for_write(session, candidate_id, principal)
        if not user:
            return _result(
                ok=False,
                message="Candidate not found",
                status_code=404,
                error="candidate_not_found",
                detail=detail,
            )

        previous_status = getattr(getattr(user, "candidate_status", None), "value", None)
        dual_write_request = None
        dual_write_claim = None
        if get_settings().candidate_status_dual_write_enabled:
            dual_write_request = _build_lifecycle_dual_write_request(
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.INVITED,
                reason=restart_reason,
                comment=comment,
                principal=principal,
                previous_status_changed_at=getattr(user, "status_changed_at", None),
                source_ref="lifecycle:restart_test1",
            )
            try:
                dual_write_runtime = _candidate_dual_write_runtime()
                dual_write_claim = await dual_write_runtime.claim_candidate_status_transition(
                    session,
                    dual_write_request,
                )
            except PersistentIdempotencyConflictError:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=False,
                    message="Конфликт идемпотентности для перезапуска Теста 1",
                    status_code=409,
                    error="idempotency_conflict",
                    detail=refreshed,
                    status=_detail_status_slug(refreshed or {}),
                )
            if dual_write_claim.reused:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=True,
                    message="Тест 1 уже перезапущен",
                    status_code=200,
                    status=CandidateStatus.INVITED.value,
                    detail=refreshed,
                )

        journey_session = await session.scalar(
            select(CandidateJourneySession)
            .where(CandidateJourneySession.candidate_id == candidate_id)
            .order_by(CandidateJourneySession.id.desc())
            .limit(1)
            .with_for_update()
        )
        step_state: CandidateJourneyStepState | None = None
        if journey_session is not None:
            step_state = await session.scalar(
                select(CandidateJourneyStepState)
                .where(
                    CandidateJourneyStepState.session_id == journey_session.id,
                    CandidateJourneyStepState.step_key == TEST1_STEP_KEY,
                )
                .limit(1)
                .with_for_update()
            )
            restart_snapshot = build_test1_restart_snapshot(
                journey_session=journey_session,
                step_state=step_state,
                current_status=user.candidate_status,
                actor_type=actor_type,
                actor_id=actor_id,
                reason=restart_reason,
            )
            reset_test1_progress(
                journey_session=journey_session,
                step_state=step_state,
                restart_snapshot=restart_snapshot,
            )

        user.is_active = True
        user.rejection_reason = None
        user.rejected_at = None
        user.rejected_by = None
        user.intro_decline_reason = None
        user.final_outcome_reason = None
        user.manual_slot_from = None
        user.manual_slot_to = None
        user.manual_slot_comment = None
        user.manual_slot_requested_at = None
        user.manual_slot_response_at = None
        try:
            await apply_candidate_status(
                user,
                CandidateStatus.INVITED,
                session=session,
                force=True,
                actor_type=actor_type,
                actor_id=actor_id,
                reason=restart_reason,
            )
        except StatusTransitionError:
            await session.rollback()
            refreshed = await _refresh_detail(candidate_id, principal)
            return _result(
                ok=False,
                message="Не удалось перезапустить Тест 1 из-за недопустимого lifecycle transition.",
                status_code=409,
                error="invalid_transition",
                detail=refreshed,
                status=_detail_status_slug(refreshed or {}),
            )

        append_journey_event(
            user,
            event_key="test1_restarted",
            stage="test",
            status=CandidateStatus.INVITED,
            actor_type=actor_type,
            actor_id=actor_id,
            summary="Открыт повторный проход Теста 1",
            payload={
                "from_status": previous_status,
                "to_status": CandidateStatus.INVITED.value,
                "reason": restart_reason,
                "restart_snapshot": restart_snapshot,
            },
        )

        if dual_write_request is not None and dual_write_claim is not None:
            await dual_write_runtime.finalize_candidate_status_dual_write(
                session,
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.INVITED.value,
                reason=restart_reason,
                comment=comment,
                request=dual_write_request,
            )
        await session.commit()

    await _log_candidate_status_updated(
        candidate_id,
        previous_status=current_status,
        target_status=CandidateStatus.INVITED.value,
    )
    await _log_test1_restarted(
        candidate_id,
        previous_status=current_status,
        restart_snapshot=restart_snapshot,
    )
    refreshed = await _refresh_detail(candidate_id, principal)
    return _result(
        ok=True,
        message="Тест 1 сброшен. Кандидат может пройти его заново.",
        status_code=200,
        status=CandidateStatus.INVITED.value,
        detail=refreshed,
    )


async def execute_finalize_hired(
    candidate_id: int,
    *,
    principal: Optional[Principal],
    action_key: Optional[str] = None,
) -> LifecycleUseCaseResult:
    principal = principal or principal_ctx.get()
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return _result(
            ok=False,
            message="Candidate not found",
            status_code=404,
            error="candidate_not_found",
        )

    current_status = _detail_status_slug(detail)
    if current_status not in ALLOWED_FINALIZE_STATUSES:
        return _result(
            ok=False,
            message="Закрепление доступно только после подтвержденного ознакомительного дня",
            status_code=409,
            error="invalid_transition",
            detail=detail,
            status=current_status,
        )

    if action_key and not _detail_action_allowed(detail, action_key):
        return _result(
            ok=False,
            message="Действие недоступно в текущем статусе",
            status_code=400,
            error="action_not_allowed",
            detail=detail,
            status=current_status,
        )

    if _has_scheduling_conflict(detail):
        return _result(
            ok=False,
            message="Нельзя завершить кандидата: scheduling contract содержит конфликт.",
            status_code=409,
            error="scheduling_conflict",
            detail=detail,
            status=current_status,
        )

    actor_type, actor_id = _resolve_actor(principal)
    async with async_session() as session:
        user = await _load_candidate_for_write(session, candidate_id, principal)
        if not user:
            return _result(
                ok=False,
                message="Candidate not found",
                status_code=404,
                error="candidate_not_found",
                detail=detail,
            )
        previous_status = getattr(getattr(user, "candidate_status", None), "value", None)
        dual_write_request = None
        dual_write_claim = None
        if get_settings().candidate_status_dual_write_enabled:
            dual_write_request = _build_lifecycle_dual_write_request(
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.HIRED,
                reason=None,
                comment=None,
                principal=principal,
                previous_status_changed_at=getattr(user, "status_changed_at", None),
                source_ref="lifecycle:finalize_hired",
            )
            try:
                dual_write_runtime = _candidate_dual_write_runtime()
                dual_write_claim = await dual_write_runtime.claim_candidate_status_transition(
                    session,
                    dual_write_request,
                )
            except PersistentIdempotencyConflictError:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=False,
                    message="Конфликт идемпотентности для закрепления кандидата",
                    status_code=409,
                    error="idempotency_conflict",
                    detail=refreshed,
                    status=_detail_status_slug(refreshed or {}),
                )
            if dual_write_claim.reused:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=True,
                    message="Кандидат уже закреплен",
                    status_code=200,
                    status=CandidateStatus.HIRED.value,
                    detail=refreshed,
                )
        try:
            await apply_candidate_status(
                user,
                CandidateStatus.HIRED,
                session=session,
                force=False,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        except StatusTransitionError:
            await session.rollback()
            refreshed = await _refresh_detail(candidate_id, principal)
            return _result(
                ok=False,
                message="Недопустимый lifecycle transition для закрепления кандидата",
                status_code=409,
                error="invalid_transition",
                detail=refreshed,
                status=_detail_status_slug(refreshed or {}),
            )

        await _dispatch_hh_status_sync_if_enabled(
            user,
            CandidateStatus.HIRED,
            session=session,
        )
        if dual_write_request is not None and dual_write_claim is not None:
            await dual_write_runtime.finalize_candidate_status_dual_write(
                session,
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.HIRED.value,
                reason=None,
                comment=None,
                request=dual_write_request,
            )
        await session.commit()

    await _log_candidate_status_updated(
        candidate_id,
        previous_status=previous_status,
        target_status=CandidateStatus.HIRED.value,
    )
    refreshed = await _refresh_detail(candidate_id, principal)
    return _result(
        ok=True,
        message="Кандидат закреплен",
        status_code=200,
        status=CandidateStatus.HIRED.value,
        detail=refreshed,
    )


async def execute_finalize_not_hired(
    candidate_id: int,
    *,
    principal: Optional[Principal],
    reason: Optional[str] = None,
    comment: Optional[str] = None,
    action_key: Optional[str] = None,
) -> LifecycleUseCaseResult:
    principal = principal or principal_ctx.get()
    detail = await get_candidate_detail(candidate_id, principal=principal)
    if not detail:
        return _result(
            ok=False,
            message="Candidate not found",
            status_code=404,
            error="candidate_not_found",
        )

    current_status = _detail_status_slug(detail)
    if current_status not in ALLOWED_FINALIZE_STATUSES:
        return _result(
            ok=False,
            message="Финальный отказ доступен только после подтвержденного ознакомительного дня",
            status_code=409,
            error="invalid_transition",
            detail=detail,
            status=current_status,
        )

    if action_key and not _detail_action_allowed(detail, action_key):
        return _result(
            ok=False,
            message="Действие недоступно в текущем статусе",
            status_code=400,
            error="action_not_allowed",
            detail=detail,
            status=current_status,
        )

    if _has_scheduling_conflict(detail):
        return _result(
            ok=False,
            message="Нельзя завершить кандидата: scheduling contract содержит конфликт.",
            status_code=409,
            error="scheduling_conflict",
            detail=detail,
            status=current_status,
        )

    actor_type, actor_id = _resolve_actor(principal)
    intro_day_slot = _resolve_intro_day_slot(detail)
    async with async_session() as session:
        user = await _load_candidate_for_write(session, candidate_id, principal)
        if not user:
            return _result(
                ok=False,
                message="Candidate not found",
                status_code=404,
                error="candidate_not_found",
                detail=detail,
            )

        previous_status = getattr(getattr(user, "candidate_status", None), "value", None)
        _persist_reason_comment(
            user,
            target_status=CandidateStatus.NOT_HIRED,
            reason=reason,
            comment=comment,
        )
        rejection_reason = _resolved_rejection_reason(
            user,
            reason=reason,
            comment=comment,
        )
        dual_write_request = None
        dual_write_claim = None
        if get_settings().candidate_status_dual_write_enabled:
            dual_write_request = _build_lifecycle_dual_write_request(
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.NOT_HIRED,
                reason=rejection_reason,
                comment=comment,
                principal=principal,
                previous_status_changed_at=getattr(user, "status_changed_at", None),
                source_ref="lifecycle:finalize_not_hired",
            )
            try:
                dual_write_runtime = _candidate_dual_write_runtime()
                dual_write_claim = await dual_write_runtime.claim_candidate_status_transition(
                    session,
                    dual_write_request,
                )
            except PersistentIdempotencyConflictError:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=False,
                    message="Конфликт идемпотентности для финального отказа",
                    status_code=409,
                    error="idempotency_conflict",
                    detail=refreshed,
                    status=_detail_status_slug(refreshed or {}),
                )
            if dual_write_claim.reused:
                await session.rollback()
                refreshed = await _refresh_detail(candidate_id, principal)
                return _result(
                    ok=True,
                    message="Кандидат уже помечен как не закрепленный",
                    status_code=200,
                    status=CandidateStatus.NOT_HIRED.value,
                    detail=refreshed,
                )
        try:
            await apply_candidate_status(
                user,
                CandidateStatus.NOT_HIRED,
                session=session,
                force=False,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        except StatusTransitionError:
            await session.rollback()
            refreshed = await _refresh_detail(candidate_id, principal)
            return _result(
                ok=False,
                message="Недопустимый lifecycle transition для финального отказа",
                status_code=409,
                error="invalid_transition",
                detail=refreshed,
                status=_detail_status_slug(refreshed or {}),
            )

        dispatch = _build_not_hired_dispatch(
            user,
            target_slot=intro_day_slot,
            rejection_reason=rejection_reason,
        )
        user.is_active = False
        await _release_intro_day_slots_for_candidate(
            session,
            candidate_uuid=user.candidate_id,
            candidate_tg_id=user.telegram_user_id or user.telegram_id,
        )
        await _dispatch_hh_status_sync_if_enabled(
            user,
            CandidateStatus.NOT_HIRED,
            session=session,
        )
        if dual_write_request is not None and dual_write_claim is not None:
            await dual_write_runtime.finalize_candidate_status_dual_write(
                session,
                candidate_id=candidate_id,
                status_from=previous_status,
                status_to=CandidateStatus.NOT_HIRED.value,
                reason=rejection_reason,
                comment=comment,
                request=dual_write_request,
            )
        await session.commit()

    await _log_candidate_status_updated(
        candidate_id,
        previous_status=previous_status,
        target_status=CandidateStatus.NOT_HIRED.value,
        slot_id=getattr(intro_day_slot, "id", None),
    )
    refreshed = await _refresh_detail(candidate_id, principal)
    return _result(
        ok=True,
        message="Кандидат помечен как не закрепленный",
        status_code=200,
        status=CandidateStatus.NOT_HIRED.value,
        detail=refreshed,
        dispatch=dispatch,
    )
