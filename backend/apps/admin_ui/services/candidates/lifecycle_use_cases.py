from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.security import Principal, principal_ctx
from backend.apps.admin_ui.services.candidates.helpers import (
    STATUSES_ARCHIVE_ON_DECLINE,
    _has_passed_test2,
    _latest_test_result_by_rating,
    _recruiter_can_access_candidate,
    _release_intro_day_slots_for_candidate,
    get_candidate_detail,
)
from backend.apps.admin_ui.services.slots import (
    BotDispatch,
    BotDispatchPlan,
    set_slot_outcome,
)
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.candidates.models import TestResult, User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import (
    StatusTransitionError,
    apply_candidate_status,
)
from backend.domain.models import Slot


logger = logging.getLogger(__name__)


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
