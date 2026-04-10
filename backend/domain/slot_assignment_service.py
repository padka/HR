"""Slot assignment flow services (offer/confirm/reschedule) with action tokens."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.scheduling_integrity import (
    WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
    build_scheduling_integrity_report,
)
from backend.domain.models import (
    ActionToken,
    AuditLog,
    Recruiter,
    RescheduleRequest,
    RescheduleRequestStatus,
    Slot,
    SlotAssignment,
    SlotAssignmentStatus,
    SlotStatus,
)
from backend.domain.repositories import add_outbox_notification
from backend.domain.slot_service import ensure_slot_not_in_past, SlotValidationError

logger = logging.getLogger(__name__)

ACTION_CONFIRM = "slot_assignment_confirm"
ACTION_RESCHEDULE = "slot_assignment_reschedule_request"

ACTION_TOKEN_TTL_HOURS = 48

ACTIVE_ASSIGNMENT_STATUSES = {
    SlotAssignmentStatus.OFFERED,
    SlotAssignmentStatus.CONFIRMED,
    SlotAssignmentStatus.RESCHEDULE_REQUESTED,
    SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
}
CONFIRMED_ASSIGNMENT_STATUSES = {
    SlotAssignmentStatus.CONFIRMED,
    SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
}
ACTIVE_SLOT_STATUSES = {
    SlotStatus.PENDING,
    SlotStatus.BOOKED,
    SlotStatus.CONFIRMED,
    SlotStatus.CONFIRMED_BY_CANDIDATE,
}


@dataclass
class ServiceResult:
    ok: bool
    status: str
    status_code: int
    message: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_candidate_tg_id(candidate: User, preferred: Optional[int] = None) -> Optional[int]:
    return preferred or candidate.telegram_user_id or candidate.telegram_id


async def _resolve_candidate_for_assignment(session, assignment: SlotAssignment) -> User | None:
    candidate = None
    if assignment.candidate_id:
        candidate = await session.scalar(
            select(User).where(User.candidate_id == assignment.candidate_id)
        )
    if candidate is None and assignment.candidate_tg_id is not None:
        candidate = await session.scalar(
            select(User).where(
                or_(
                    User.telegram_id == assignment.candidate_tg_id,
                    User.telegram_user_id == assignment.candidate_tg_id,
                )
            )
        )
    return candidate


def _known_candidate_tg_ids(
    assignment: SlotAssignment,
    candidate: User | None,
    preferred: Optional[int] = None,
) -> set[int]:
    ids: set[int] = set()
    for raw in (
        preferred,
        assignment.candidate_tg_id,
        getattr(candidate, "telegram_id", None),
        getattr(candidate, "telegram_user_id", None),
    ):
        if raw is None:
            continue
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


def _slot_claimed_by_other_candidate(
    slot: Slot,
    *,
    candidate_id: Optional[str],
    candidate_tg_ids: set[int],
) -> bool:
    slot_candidate_id = getattr(slot, "candidate_id", None)
    slot_candidate_tg_id = getattr(slot, "candidate_tg_id", None)
    if slot_candidate_id is None and slot_candidate_tg_id is None:
        return False
    if candidate_id is not None and slot_candidate_id == candidate_id:
        return False
    if slot_candidate_tg_id is not None:
        try:
            if int(slot_candidate_tg_id) in candidate_tg_ids:
                return False
        except (TypeError, ValueError):
            pass
    return True


def _clear_slot_binding(slot: Slot) -> None:
    slot.status = SlotStatus.FREE
    slot.candidate_id = None
    slot.candidate_tg_id = None
    slot.candidate_fio = None
    slot.candidate_tz = None
    slot.candidate_city_id = None


def _bind_slot_to_assignment(
    slot: Slot,
    *,
    assignment: SlotAssignment,
    candidate: User | None,
    slot_status: str,
) -> None:
    slot.status = slot_status
    slot.candidate_id = assignment.candidate_id or slot.candidate_id
    slot.candidate_tg_id = assignment.candidate_tg_id
    if candidate is not None and getattr(candidate, "fio", None):
        slot.candidate_fio = candidate.fio
    slot.candidate_tz = assignment.candidate_tz or slot.candidate_tz or slot.tz_name
    slot.candidate_city_id = slot.candidate_city_id or slot.city_id


async def _load_assignment_integrity(
    session,
    *,
    assignment: SlotAssignment,
    candidate: User | None,
) -> Optional[dict[str, Any]]:
    candidate_tg_ids = _known_candidate_tg_ids(assignment, candidate)
    slot_filters = []
    if assignment.candidate_id:
        slot_filters.append(Slot.candidate_id == assignment.candidate_id)
    if candidate_tg_ids:
        slot_filters.append(Slot.candidate_tg_id.in_(sorted(candidate_tg_ids)))
    assignment_filters = []
    if assignment.candidate_id:
        assignment_filters.append(SlotAssignment.candidate_id == assignment.candidate_id)
    if candidate_tg_ids:
        assignment_filters.append(SlotAssignment.candidate_tg_id.in_(sorted(candidate_tg_ids)))
    if not slot_filters and not assignment_filters:
        return None

    slots = []
    if slot_filters:
        slots = (
            await session.execute(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(or_(*slot_filters))
                .order_by(Slot.start_utc.desc(), Slot.id.desc())
            )
        ).scalars().all()

    assignments = []
    if assignment_filters:
        assignments = (
            await session.execute(
                select(SlotAssignment)
                .options(selectinload(SlotAssignment.slot))
                .where(or_(*assignment_filters))
                .order_by(SlotAssignment.updated_at.desc(), SlotAssignment.id.desc())
            )
        ).scalars().all()

    report = build_scheduling_integrity_report(
        slots=slots,
        slot_assignments=assignments,
    )
    report["slots"] = list(slots)
    report["slot_assignments"] = list(assignments)
    return report


async def _manual_repair_conflict(
    session,
    *,
    assignment: SlotAssignment,
    candidate: User | None,
) -> Optional[ServiceResult]:
    integrity = await _load_assignment_integrity(
        session,
        assignment=assignment,
        candidate=candidate,
    )
    if integrity is None:
        return None
    if integrity.get("write_behavior") != WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR:
        return None
    return ServiceResult(
        False,
        "scheduling_conflict",
        409,
        "Найдены конфликты между Slot и SlotAssignment. Нужна ручная проверка scheduling.",
    )


async def _active_other_assignments_count(
    session,
    *,
    slot_id: int,
    current_assignment_id: int,
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(SlotAssignment)
        .where(
            SlotAssignment.slot_id == slot_id,
            SlotAssignment.id != current_assignment_id,
            SlotAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        )
    )
    return int(count or 0)


async def _release_replaced_active_slots(
    session,
    *,
    assignment: SlotAssignment,
    candidate_tg_ids: set[int],
    current_slot: Slot,
) -> Optional[ServiceResult]:
    slot_filters = []
    if assignment.candidate_id:
        slot_filters.append(Slot.candidate_id == assignment.candidate_id)
    if candidate_tg_ids:
        slot_filters.append(Slot.candidate_tg_id.in_(sorted(candidate_tg_ids)))
    if not slot_filters:
        return None

    same_purpose = (current_slot.purpose or "interview").strip().lower()
    existing_slots = (
        await session.execute(
            select(Slot)
            .where(
                Slot.id != current_slot.id,
                or_(*slot_filters),
                Slot.status.in_(ACTIVE_SLOT_STATUSES),
                func.lower(func.coalesce(Slot.purpose, "interview")) == same_purpose,
            )
            .with_for_update()
        )
    ).scalars().all()

    for existing_slot in existing_slots:
        if existing_slot.recruiter_id != assignment.recruiter_id:
            return ServiceResult(
                False,
                "scheduling_conflict",
                409,
                "У кандидата найден другой активный слот. Нужна ручная проверка scheduling.",
            )
        other_assignments = (
            await session.execute(
                select(SlotAssignment)
                .where(
                    SlotAssignment.slot_id == existing_slot.id,
                    SlotAssignment.id != assignment.id,
                    SlotAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                )
                .with_for_update()
            )
        ).scalars().all()
        if other_assignments:
            return ServiceResult(
                False,
                "scheduling_conflict",
                409,
                "У старого слота осталось активное назначение. Нужна ручная проверка scheduling.",
            )
        _clear_slot_binding(existing_slot)
    return None


async def cancel_active_interview_slots_for_candidate(
    *,
    candidate_id: Optional[str],
    candidate_tg_ids: Iterable[int],
    cancelled_by: str = "superseded_by_intro_day",
) -> Dict[str, list[int]]:
    """Remove active interview slots/assignments so candidate stays in one active stage."""
    tg_ids = {int(value) for value in candidate_tg_ids if value is not None}
    if not candidate_id and not tg_ids:
        return {"slot_ids": [], "assignment_ids": []}

    slot_statuses = {
        SlotStatus.PENDING,
        SlotStatus.BOOKED,
        SlotStatus.CONFIRMED,
        SlotStatus.CONFIRMED_BY_CANDIDATE,
    }
    assignment_statuses = {
        SlotAssignmentStatus.OFFERED,
        SlotAssignmentStatus.CONFIRMED,
        SlotAssignmentStatus.RESCHEDULE_REQUESTED,
        SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
    }
    async with async_session() as session:
        async with session.begin():
            candidate_predicates = []
            if candidate_id:
                candidate_predicates.append(Slot.candidate_id == candidate_id)
            if tg_ids:
                candidate_predicates.append(Slot.candidate_tg_id.in_(list(tg_ids)))

            slot_ids_set: set[int] = set()
            if candidate_predicates:
                slots = (
                    await session.execute(
                        select(Slot)
                        .where(
                            func.coalesce(Slot.purpose, "interview") == "interview",
                            Slot.status.in_(slot_statuses),
                            or_(*candidate_predicates),
                        )
                        .with_for_update()
                    )
                ).scalars().all()
            else:
                slots = []

            for slot in slots:
                slot_ids_set.add(int(slot.id))

            assignment_predicates = []
            if candidate_id:
                assignment_predicates.append(SlotAssignment.candidate_id == candidate_id)
            if tg_ids:
                assignment_predicates.append(SlotAssignment.candidate_tg_id.in_(list(tg_ids)))

            if assignment_predicates:
                assignments = (
                    await session.execute(
                        select(SlotAssignment)
                        .join(Slot, Slot.id == SlotAssignment.slot_id)
                        .where(
                            func.coalesce(Slot.purpose, "interview") == "interview",
                            SlotAssignment.status.in_(assignment_statuses),
                            or_(*assignment_predicates),
                        )
                        .with_for_update()
                    )
                ).scalars().all()
            else:
                assignments = []

            assignment_ids: list[int] = []
            for assignment in assignments:
                assignment_ids.append(int(assignment.id))
                if assignment.slot_id:
                    slot_ids_set.add(int(assignment.slot_id))

            if assignment_ids:
                for assignment_id in assignment_ids:
                    await _invalidate_action_tokens(session, assignment_id=assignment_id)
                await session.execute(
                    delete(RescheduleRequest).where(
                        RescheduleRequest.slot_assignment_id.in_(assignment_ids),
                    )
                )
                await session.execute(
                    delete(SlotAssignment).where(
                        SlotAssignment.id.in_(assignment_ids),
                    )
                )

            if slot_ids_set:
                slots_to_delete = (
                    await session.execute(
                        select(Slot)
                        .where(
                            Slot.id.in_(list(slot_ids_set)),
                            func.coalesce(Slot.purpose, "interview") == "interview",
                        )
                        .with_for_update()
                    )
                ).scalars().all()
                for slot in slots_to_delete:
                    await session.delete(slot)

    return {
        "slot_ids": sorted(slot_ids_set),
        "assignment_ids": assignment_ids,
    }


async def _create_action_token(
    session, action: str, entity_id: int, *, ttl_hours: int = ACTION_TOKEN_TTL_HOURS
) -> str:
    token = secrets.token_urlsafe(12)
    expires_at = _now() + timedelta(hours=ttl_hours)
    session.add(
        ActionToken(
            token=token,
            action=action,
            entity_id=str(entity_id),
            expires_at=expires_at,
            created_at=_now(),
        )
    )
    return token


async def _invalidate_action_tokens(session, *, assignment_id: int) -> None:
    now = _now()
    rows = await session.execute(
        select(ActionToken).where(ActionToken.entity_id == str(assignment_id))
    )
    for token in rows.scalars():
        if token.used_at is None:
            token.used_at = now


async def _consume_action_token(
    session, *, token: str, action: str, entity_id: int
) -> tuple[bool, str]:
    row = await session.get(ActionToken, token, with_for_update=True)
    if row is None:
        return False, "not_found"
    if row.action != action or row.entity_id != str(entity_id):
        return False, "mismatch"
    if row.used_at is not None:
        return False, "used"
    # Defensive: some DBs/drivers (or legacy schemas) may return naive timestamps.
    expires_at = row.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        return False, "expired"
    row.used_at = _now()
    return True, "ok"


async def _peek_action_token(
    session, *, token: str, action: str, entity_id: int
) -> tuple[bool, str]:
    row = await session.get(ActionToken, token, with_for_update=True)
    if row is None:
        return False, "not_found"
    if row.action != action or row.entity_id != str(entity_id):
        return False, "mismatch"
    if row.used_at is not None:
        return False, "used"
    expires_at = row.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        return False, "expired"
    return True, "ok"


async def create_slot_assignment(
    *,
    slot_id: int,
    candidate_id: str,
    candidate_tg_id: Optional[int] = None,
    candidate_tz: Optional[str] = None,
    created_by: Optional[str] = None,
    allow_replace_active_assignment: bool = False,
) -> ServiceResult:
    async with async_session() as session:
        try:
            async with session.begin():
                slot = await session.scalar(
                    select(Slot)
                    .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                    .where(Slot.id == slot_id)
                    .with_for_update()
                )
                if slot is None:
                    return ServiceResult(False, "slot_not_found", 404, "Слот не найден.")
                if (slot.status or "").lower() == SlotStatus.CANCELED:
                    return ServiceResult(False, "slot_cancelled", 409, "Слот отменён.")
                if (slot.status or "").lower() != SlotStatus.FREE:
                    return ServiceResult(False, "slot_not_available", 409, "Слот уже занят.")

                try:
                    ensure_slot_not_in_past(slot.start_utc, slot_tz=slot.tz_name)
                except SlotValidationError:
                    return ServiceResult(False, "slot_in_past", 409, "Слот уже в прошлом.")

                candidate = await session.scalar(
                    select(User).where(User.candidate_id == candidate_id)
                )
                if candidate is None:
                    return ServiceResult(False, "candidate_not_found", 404, "Кандидат не найден.")

                candidate_tg_id = _resolve_candidate_tg_id(candidate, candidate_tg_id)
                if candidate_tg_id is None:
                    return ServiceResult(
                        False,
                        "candidate_telegram_missing",
                        400,
                        "У кандидата не привязан Telegram.",
                    )
                candidate_tz = candidate_tz or slot.tz_name

                existing = await session.scalar(
                    select(SlotAssignment)
                    .where(
                        SlotAssignment.candidate_id == candidate_id,
                        SlotAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                    )
                    .with_for_update()
                )
                if existing:
                    if not allow_replace_active_assignment:
                        return ServiceResult(
                            False,
                            "candidate_has_active_assignment",
                            409,
                            "У кандидата уже есть активное назначение.",
                        )
                    if existing.recruiter_id != slot.recruiter_id:
                        return ServiceResult(
                            False,
                            "candidate_has_active_assignment",
                            409,
                            "У кандидата уже есть активное назначение у другого рекрутёра.",
                        )

                    replacement_now = _now()
                    existing_slot = await session.scalar(
                        select(Slot)
                        .where(Slot.id == existing.slot_id)
                        .with_for_update()
                    )
                    if existing_slot is not None and existing_slot.id != slot.id:
                        old_status = (existing_slot.status or "").lower()
                        if old_status in {
                            SlotStatus.PENDING,
                            SlotStatus.BOOKED,
                            SlotStatus.CONFIRMED_BY_CANDIDATE,
                        } and (
                            existing_slot.candidate_id == candidate_id
                            or (
                                candidate_tg_id is not None
                                and existing_slot.candidate_tg_id == candidate_tg_id
                            )
                        ):
                            existing_slot.status = SlotStatus.FREE
                            existing_slot.candidate_id = None
                            existing_slot.candidate_tg_id = None
                            existing_slot.candidate_fio = None
                            existing_slot.candidate_tz = None
                            existing_slot.candidate_city_id = None

                    await _invalidate_action_tokens(session, assignment_id=existing.id)
                    pending_requests = await session.execute(
                        select(RescheduleRequest)
                        .where(
                            RescheduleRequest.slot_assignment_id == existing.id,
                            RescheduleRequest.status == RescheduleRequestStatus.PENDING,
                        )
                        .with_for_update()
                    )
                    for req in pending_requests.scalars():
                        req.status = RescheduleRequestStatus.EXPIRED
                        req.decided_at = replacement_now
                        req.recruiter_comment = "superseded_by_recruiter_reschedule"

                    existing.status = SlotAssignmentStatus.CANCELLED
                    existing.cancelled_at = replacement_now
                    existing.status_before_reschedule = None
                    existing.reschedule_requested_at = None
                    # SQLite test schema may keep UNIQUE(candidate_id) without partial filter.
                    # Preserve cross-DB portability of replacement flow.
                    existing.candidate_id = None

                slot_purpose = (slot.purpose or "interview").strip().lower()
                active_slot_predicates = [Slot.candidate_id == candidate_id]
                if candidate_tg_id is not None:
                    active_slot_predicates.append(Slot.candidate_tg_id == candidate_tg_id)
                active_slot_other_purpose = await session.scalar(
                    select(Slot)
                    .where(
                        Slot.id != slot.id,
                        or_(*active_slot_predicates),
                        Slot.status.in_(ACTIVE_SLOT_STATUSES),
                        func.lower(func.coalesce(Slot.purpose, "interview")) != slot_purpose,
                    )
                    .with_for_update()
                )
                if active_slot_other_purpose is not None:
                    return ServiceResult(
                        False,
                        "candidate_has_active_assignment",
                        409,
                        "У кандидата уже есть активная встреча в другом типе.",
                    )

                active_count = await session.scalar(
                    select(func.count())
                    .select_from(SlotAssignment)
                    .where(
                        SlotAssignment.slot_id == slot.id,
                        SlotAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                    )
                )
                capacity = max(int(getattr(slot, "capacity", 1) or 1), 1)
                if (active_count or 0) >= capacity:
                    return ServiceResult(False, "slot_full", 409, "Слот заполнен.")

                slot.status = SlotStatus.PENDING
                slot.candidate_id = candidate.candidate_id
                slot.candidate_tg_id = candidate_tg_id
                slot.candidate_fio = candidate.fio
                slot.candidate_tz = candidate_tz or slot.tz_name
                slot.candidate_city_id = slot.candidate_city_id or slot.city_id

                assignment = SlotAssignment(
                    slot_id=slot.id,
                    recruiter_id=slot.recruiter_id,
                    candidate_id=candidate_id,
                    candidate_tg_id=candidate_tg_id,
                    candidate_tz=candidate_tz,
                    status=SlotAssignmentStatus.OFFERED,
                    offered_at=_now(),
                )
                session.add(assignment)
                await session.flush()

                confirm_token = await _create_action_token(
                    session, ACTION_CONFIRM, assignment.id
                )
                reschedule_token = await _create_action_token(
                    session, ACTION_RESCHEDULE, assignment.id
                )

                payload = {
                    "slot_assignment_id": assignment.id,
                    "slot_id": slot.id,
                    "candidate_id": candidate_id,
                    "candidate_name": candidate.fio,
                    "candidate_tg_id": candidate_tg_id,
                    "candidate_tz": candidate_tz,
                    "recruiter_id": slot.recruiter_id,
                    "recruiter_name": slot.recruiter.name if slot.recruiter else None,
                    "city_id": slot.city_id,
                    "city_name": slot.city.name if slot.city else None,
                    "start_utc": slot.start_utc.isoformat(),
                    "duration_min": slot.duration_min,
                    "action_tokens": {
                        "confirm": confirm_token,
                        "reschedule": reschedule_token,
                    },
                }

                await add_outbox_notification(
                    notification_type="slot_assignment_offer",
                    booking_id=slot.id,
                    candidate_tg_id=candidate_tg_id,
                    payload=payload,
                    session=session,
                )

                session.add(
                    AuditLog(
                        username=created_by,
                        action="slot_assignment.offered",
                        entity_type="slot_assignment",
                        entity_id=str(assignment.id),
                        created_at=_now(),
                        changes={
                            "slot_id": slot.id,
                            "candidate_id": candidate_id,
                        },
                    )
                )

            return ServiceResult(
                True,
                "offered",
                201,
                payload={
                    "slot_assignment_id": assignment.id,
                    "confirm_token": confirm_token,
                    "reschedule_token": reschedule_token,
                },
            )
        except IntegrityError:
            logger.warning("slot_assignment_create_integrity_error", exc_info=True)
            return ServiceResult(
                False,
                "candidate_has_active_assignment",
                409,
                "У кандидата уже есть активное назначение.",
            )


async def confirm_slot_assignment(
    *,
    assignment_id: int,
    action_token: str,
    candidate_tg_id: Optional[int],
    token_actions: tuple[str, ...] = (ACTION_CONFIRM,),
) -> ServiceResult:
    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")

            candidate = await _resolve_candidate_for_assignment(session, assignment)
            valid_tg_ids = _known_candidate_tg_ids(
                assignment,
                candidate,
                preferred=candidate_tg_id,
            )
            if valid_tg_ids and candidate_tg_id is not None and int(candidate_tg_id) not in valid_tg_ids:
                return ServiceResult(False, "forbidden", 403, "Доступ запрещён.")
            if candidate_tg_id is not None and assignment.candidate_tg_id != candidate_tg_id:
                assignment.candidate_tg_id = candidate_tg_id
            if (
                candidate is not None
                and candidate.responsible_recruiter_id != assignment.recruiter_id
            ):
                candidate.responsible_recruiter_id = assignment.recruiter_id

            integrity_conflict = await _manual_repair_conflict(
                session,
                assignment=assignment,
                candidate=candidate,
            )
            if integrity_conflict is not None:
                return integrity_conflict

            if assignment.status not in {
                SlotAssignmentStatus.OFFERED,
                SlotAssignmentStatus.CONFIRMED,
                SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
            }:
                return ServiceResult(False, "invalid_status", 409, "Нельзя подтвердить это назначение.")

            token_ok = False
            token_status = "not_found"
            for action in token_actions:
                token_ok, token_status = await _consume_action_token(
                    session,
                    token=action_token,
                    action=action,
                    entity_id=assignment_id,
                )
                if token_ok or token_status != "mismatch":
                    break
            if not token_ok:
                if assignment.status in CONFIRMED_ASSIGNMENT_STATUSES:
                    return ServiceResult(True, "already_confirmed", 200)
                return ServiceResult(False, f"token_{token_status}", 409, "Ссылка устарела.")

            slot = await session.scalar(
                select(Slot).where(Slot.id == assignment.slot_id).with_for_update()
            )
            if slot is None:
                return ServiceResult(False, "slot_not_found", 404, "Слот не найден.")

            allowed_slot_statuses = {
                SlotStatus.FREE,
                SlotStatus.PENDING,
                SlotStatus.BOOKED,
                SlotStatus.CONFIRMED_BY_CANDIDATE,
            }
            slot_status = (slot.status or "").lower()
            if slot_status not in allowed_slot_statuses:
                return ServiceResult(False, "slot_not_available", 409, "Слот больше недоступен.")
            if _slot_claimed_by_other_candidate(
                slot,
                candidate_id=assignment.candidate_id,
                candidate_tg_ids=valid_tg_ids,
            ):
                return ServiceResult(False, "slot_not_available", 409, "Слот уже занят другим кандидатом.")

            other_active_assignments = await _active_other_assignments_count(
                session,
                slot_id=slot.id,
                current_assignment_id=assignment.id,
            )
            capacity = max(int(getattr(slot, "capacity", 1) or 1), 1)
            if assignment.status not in CONFIRMED_ASSIGNMENT_STATUSES and other_active_assignments >= capacity:
                return ServiceResult(False, "slot_full", 409, "Слот заполнен.")

            if assignment.status in CONFIRMED_ASSIGNMENT_STATUSES:
                return ServiceResult(True, "already_confirmed", 200)

            slot_release_conflict = await _release_replaced_active_slots(
                session,
                assignment=assignment,
                candidate_tg_ids=valid_tg_ids,
                current_slot=slot,
            )
            if slot_release_conflict is not None:
                return slot_release_conflict

            assignment.status = SlotAssignmentStatus.CONFIRMED
            assignment.confirmed_at = _now()
            assignment.status_before_reschedule = None
            _bind_slot_to_assignment(
                slot,
                assignment=assignment,
                candidate=candidate,
                slot_status=SlotStatus.BOOKED,
            )

            session.add(
                AuditLog(
                    action="slot_assignment.confirmed",
                    entity_type="slot_assignment",
                    entity_id=str(assignment.id),
                    created_at=_now(),
                )
            )

            return ServiceResult(
                True,
                "confirmed",
                200,
                payload={
                    "slot_id": assignment.slot_id,
                    "slot_assignment_id": assignment.id,
                },
            )


async def request_reschedule(
    *,
    assignment_id: int,
    action_token: str,
    candidate_tg_id: Optional[int],
    requested_start_utc: Optional[datetime],
    requested_end_utc: Optional[datetime] = None,
    requested_tz: Optional[str] = None,
    comment: Optional[str] = None,
) -> ServiceResult:
    normalized_comment = (comment or "").strip() or None

    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")

            candidate = await _resolve_candidate_for_assignment(session, assignment)
            valid_tg_ids = _known_candidate_tg_ids(
                assignment,
                candidate,
                preferred=candidate_tg_id,
            )
            if valid_tg_ids and candidate_tg_id is not None and int(candidate_tg_id) not in valid_tg_ids:
                return ServiceResult(False, "forbidden", 403, "Доступ запрещён.")
            integrity_conflict = await _manual_repair_conflict(
                session,
                assignment=assignment,
                candidate=candidate,
            )
            if integrity_conflict is not None:
                return integrity_conflict

            if assignment.status not in {
                SlotAssignmentStatus.OFFERED,
                SlotAssignmentStatus.CONFIRMED,
                SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
                SlotAssignmentStatus.RESCHEDULE_REQUESTED,
            }:
                return ServiceResult(False, "invalid_status", 409, "Запрос переноса недоступен.")

            existing = await session.scalar(
                select(RescheduleRequest)
                .where(
                    RescheduleRequest.slot_assignment_id == assignment_id,
                    RescheduleRequest.status == RescheduleRequestStatus.PENDING,
                )
                .with_for_update()
            )
            if existing:
                return ServiceResult(True, "already_requested", 200)

            token_ok, token_status = await _consume_action_token(
                session, token=action_token, action=ACTION_RESCHEDULE, entity_id=assignment_id
            )
            if not token_ok:
                return ServiceResult(False, f"token_{token_status}", 409, "Ссылка устарела.")

            if requested_start_utc is None and normalized_comment is None:
                return ServiceResult(
                    False,
                    "requested_time_missing",
                    409,
                    "Укажите желаемое время или комментарий.",
                )

            if requested_start_utc is not None:
                try:
                    ensure_slot_not_in_past(requested_start_utc, allow_past=False)
                except SlotValidationError:
                    return ServiceResult(
                        False,
                        "requested_time_in_past",
                        409,
                        "Нельзя выбрать время в прошлом.",
                    )
            if requested_end_utc is not None:
                if requested_start_utc is None:
                    return ServiceResult(
                        False,
                        "requested_window_missing_start",
                        409,
                        "Для диапазона нужно указать начало окна.",
                    )
                if requested_end_utc <= requested_start_utc:
                    return ServiceResult(
                        False,
                        "requested_window_invalid",
                        409,
                        "Конец диапазона должен быть позже начала.",
                    )

            request = RescheduleRequest(
                slot_assignment_id=assignment.id,
                requested_start_utc=requested_start_utc,
                requested_end_utc=requested_end_utc,
                requested_tz=requested_tz,
                candidate_comment=normalized_comment,
                status=RescheduleRequestStatus.PENDING,
                created_at=_now(),
            )
            session.add(request)
            await session.flush()

            if assignment.status != SlotAssignmentStatus.RESCHEDULE_REQUESTED:
                assignment.status_before_reschedule = assignment.status
            assignment.status = SlotAssignmentStatus.RESCHEDULE_REQUESTED
            assignment.reschedule_requested_at = assignment.reschedule_requested_at or _now()

            recruiter = await session.get(Recruiter, assignment.recruiter_id)
            if candidate is not None and candidate.responsible_recruiter_id is None:
                # Ensure the reschedule request is routed back to the same recruiter in CRM views
                # that are scoped by responsible_recruiter_id.
                candidate.responsible_recruiter_id = assignment.recruiter_id
            recruiter_tg_id = recruiter.tg_chat_id if recruiter else None
            await add_outbox_notification(
                notification_type="slot_assignment_reschedule_requested",
                booking_id=assignment.slot_id,
                candidate_tg_id=assignment.candidate_tg_id,
                recruiter_tg_id=recruiter_tg_id,
                payload={
                    "slot_assignment_id": assignment.id,
                    "slot_id": assignment.slot_id,
                    "recruiter_id": assignment.recruiter_id,
                    "candidate_id": assignment.candidate_id,
                    "candidate_name": candidate.fio if candidate else None,
                    "candidate_tg_id": assignment.candidate_tg_id,
                    "candidate_tz": assignment.candidate_tz,
                    "requested_start_utc": (
                        requested_start_utc.isoformat()
                        if requested_start_utc is not None
                        else None
                    ),
                    "requested_end_utc": (
                        requested_end_utc.isoformat()
                        if requested_end_utc is not None
                        else None
                    ),
                    "requested_tz": requested_tz,
                    "comment": normalized_comment,
                },
                session=session,
            )

            audit_changes: Dict[str, Any] = {}
            if requested_start_utc is not None:
                audit_changes["requested_start_utc"] = requested_start_utc.isoformat()
            if requested_end_utc is not None:
                audit_changes["requested_end_utc"] = requested_end_utc.isoformat()
            if normalized_comment is not None:
                audit_changes["comment"] = normalized_comment

            session.add(
                AuditLog(
                    action="slot_assignment.reschedule_requested",
                    entity_type="slot_assignment",
                    entity_id=str(assignment.id),
                    created_at=_now(),
                    changes=audit_changes,
                )
            )

            return ServiceResult(
                True,
                "reschedule_requested",
                200,
                payload={"reschedule_request_id": request.id},
            )


async def begin_reschedule_request(
    *,
    assignment_id: int,
    action_token: str,
    candidate_tg_id: Optional[int],
) -> ServiceResult:
    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")

            candidate = await _resolve_candidate_for_assignment(session, assignment)
            valid_tg_ids = _known_candidate_tg_ids(
                assignment,
                candidate,
                preferred=candidate_tg_id,
            )
            if valid_tg_ids and candidate_tg_id is not None and int(candidate_tg_id) not in valid_tg_ids:
                return ServiceResult(False, "forbidden", 403, "Доступ запрещён.")
            integrity_conflict = await _manual_repair_conflict(
                session,
                assignment=assignment,
                candidate=candidate,
            )
            if integrity_conflict is not None:
                return integrity_conflict

            if assignment.status == SlotAssignmentStatus.RESCHEDULE_REQUESTED:
                return ServiceResult(True, "reschedule_pending_input", 200)

            if assignment.status not in {
                SlotAssignmentStatus.OFFERED,
                SlotAssignmentStatus.CONFIRMED,
                SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
            }:
                return ServiceResult(False, "invalid_status", 409, "Запрос переноса недоступен.")

            token_ok, token_status = await _peek_action_token(
                session,
                token=action_token,
                action=ACTION_RESCHEDULE,
                entity_id=assignment_id,
            )
            if not token_ok:
                return ServiceResult(False, f"token_{token_status}", 409, "Ссылка устарела.")

            assignment.status_before_reschedule = assignment.status
            assignment.status = SlotAssignmentStatus.RESCHEDULE_REQUESTED
            assignment.reschedule_requested_at = assignment.reschedule_requested_at or _now()

            if candidate is not None and candidate.responsible_recruiter_id is None:
                candidate.responsible_recruiter_id = assignment.recruiter_id

            session.add(
                AuditLog(
                    action="slot_assignment.reschedule_prompted",
                    entity_type="slot_assignment",
                    entity_id=str(assignment.id),
                    created_at=_now(),
                )
            )

            return ServiceResult(True, "reschedule_pending_input", 200)


async def approve_reschedule(
    *,
    assignment_id: int,
    decided_by_id: int,
    decided_by_type: str,
    comment: Optional[str] = None,
) -> ServiceResult:
    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")
            if assignment.status != SlotAssignmentStatus.RESCHEDULE_REQUESTED:
                return ServiceResult(False, "invalid_status", 409, "Запрос переноса не ожидается.")

            request = await session.scalar(
                select(RescheduleRequest)
                .where(
                    RescheduleRequest.slot_assignment_id == assignment_id,
                    RescheduleRequest.status == RescheduleRequestStatus.PENDING,
                )
                .with_for_update()
            )
            if request is None:
                return ServiceResult(False, "request_not_found", 404, "Запрос переноса не найден.")
            if request.requested_start_utc is None or request.requested_end_utc is not None:
                return ServiceResult(
                    False,
                    "request_requires_recruiter_offer",
                    409,
                    "Запрос без точного времени нельзя подтвердить напрямую. Предложите кандидату новый слот.",
                )

            slot = await session.scalar(
                select(Slot)
                .where(Slot.id == assignment.slot_id)
                .with_for_update()
            )
            if slot is None:
                return ServiceResult(False, "slot_not_found", 404, "Слот не найден.")
            candidate = await _resolve_candidate_for_assignment(session, assignment)
            integrity_conflict = await _manual_repair_conflict(
                session,
                assignment=assignment,
                candidate=candidate,
            )
            if integrity_conflict is not None:
                return integrity_conflict
            candidate_tg_ids = _known_candidate_tg_ids(assignment, candidate)

            try:
                ensure_slot_not_in_past(request.requested_start_utc, allow_past=False)
            except SlotValidationError:
                return ServiceResult(False, "requested_time_in_past", 409, "Нельзя выбрать время в прошлом.")

            target_slot = await session.scalar(
                select(Slot)
                .where(
                    Slot.recruiter_id == assignment.recruiter_id,
                    Slot.start_utc == request.requested_start_utc,
                    Slot.status != SlotStatus.CANCELED,
                )
                .with_for_update()
            )
            if target_slot is None:
                target_slot = Slot(
                    recruiter_id=assignment.recruiter_id,
                    city_id=slot.city_id,
                    candidate_city_id=slot.candidate_city_id,
                    purpose=slot.purpose,
                    tz_name=slot.tz_name,
                    start_utc=request.requested_start_utc,
                    duration_min=slot.duration_min,
                    status=SlotStatus.FREE,
                    capacity=max(int(getattr(slot, "capacity", 1) or 1), 1),
                )
                session.add(target_slot)
                await session.flush()

            target_slot_status = (target_slot.status or "").lower()
            if target_slot.id != slot.id and target_slot_status != SlotStatus.FREE:
                return ServiceResult(False, "slot_not_available", 409, "Новый слот больше недоступен.")
            if _slot_claimed_by_other_candidate(
                target_slot,
                candidate_id=assignment.candidate_id,
                candidate_tg_ids=candidate_tg_ids,
            ):
                return ServiceResult(False, "slot_not_available", 409, "Новый слот уже занят другим кандидатом.")

            other_active_assignments = await _active_other_assignments_count(
                session,
                slot_id=target_slot.id,
                current_assignment_id=assignment.id,
            )
            capacity = max(int(getattr(target_slot, "capacity", 1) or 1), 1)
            if other_active_assignments >= capacity:
                return ServiceResult(False, "slot_full", 409, "Слот заполнен.")

            if target_slot.id != slot.id:
                _clear_slot_binding(slot)
            assignment.slot_id = target_slot.id
            assignment.status = SlotAssignmentStatus.RESCHEDULE_CONFIRMED
            assignment.confirmed_at = _now()
            assignment.status_before_reschedule = None
            _bind_slot_to_assignment(
                target_slot,
                assignment=assignment,
                candidate=candidate,
                slot_status=SlotStatus.BOOKED,
            )

            request.status = RescheduleRequestStatus.APPROVED
            request.decided_at = _now()
            request.decided_by_id = decided_by_id
            request.decided_by_type = decided_by_type
            request.recruiter_comment = comment
            request.alternative_slot_id = target_slot.id

            await add_outbox_notification(
                notification_type="slot_assignment_reschedule_approved",
                booking_id=target_slot.id,
                candidate_tg_id=assignment.candidate_tg_id,
                payload={
                    "slot_assignment_id": assignment.id,
                    "slot_id": target_slot.id,
                    "start_utc": target_slot.start_utc.isoformat(),
                    "candidate_tz": assignment.candidate_tz or target_slot.tz_name,
                    "comment": comment,
                },
                session=session,
            )

            session.add(
                AuditLog(
                    action="slot_assignment.reschedule_approved",
                    entity_type="slot_assignment",
                    entity_id=str(assignment.id),
                    created_at=_now(),
                    changes={"slot_id": target_slot.id},
                )
            )

            return ServiceResult(
                True,
                "reschedule_approved",
                200,
                payload={"slot_id": target_slot.id},
            )


async def propose_alternative(
    *,
    assignment_id: int,
    decided_by_id: int,
    decided_by_type: str,
    new_start_utc: datetime,
    comment: Optional[str] = None,
) -> ServiceResult:
    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")
            if assignment.status != SlotAssignmentStatus.RESCHEDULE_REQUESTED:
                return ServiceResult(False, "invalid_status", 409, "Запрос переноса не ожидается.")

            request = await session.scalar(
                select(RescheduleRequest)
                .where(
                    RescheduleRequest.slot_assignment_id == assignment_id,
                    RescheduleRequest.status == RescheduleRequestStatus.PENDING,
                )
                .with_for_update()
            )
            if request is None:
                return ServiceResult(False, "request_not_found", 404, "Запрос переноса не найден.")

            slot = await session.scalar(
                select(Slot)
                .where(Slot.id == assignment.slot_id)
                .with_for_update()
            )
            if slot is None:
                return ServiceResult(False, "slot_not_found", 404, "Слот не найден.")
            candidate = await _resolve_candidate_for_assignment(session, assignment)
            integrity_conflict = await _manual_repair_conflict(
                session,
                assignment=assignment,
                candidate=candidate,
            )
            if integrity_conflict is not None:
                return integrity_conflict
            candidate_tg_ids = _known_candidate_tg_ids(assignment, candidate)

            try:
                ensure_slot_not_in_past(new_start_utc, allow_past=False)
            except SlotValidationError:
                return ServiceResult(False, "requested_time_in_past", 409, "Нельзя выбрать время в прошлом.")

            target_slot = await session.scalar(
                select(Slot)
                .where(
                    Slot.recruiter_id == assignment.recruiter_id,
                    Slot.start_utc == new_start_utc,
                    Slot.status != SlotStatus.CANCELED,
                )
                .with_for_update()
            )
            if target_slot is None:
                target_slot = Slot(
                    recruiter_id=assignment.recruiter_id,
                    city_id=slot.city_id,
                    candidate_city_id=slot.candidate_city_id,
                    purpose=slot.purpose,
                    tz_name=slot.tz_name,
                    start_utc=new_start_utc,
                    duration_min=slot.duration_min,
                    status=SlotStatus.FREE,
                    capacity=max(int(getattr(slot, "capacity", 1) or 1), 1),
                )
                session.add(target_slot)
                await session.flush()

            if target_slot.id != slot.id and (target_slot.status or "").lower() != SlotStatus.FREE:
                return ServiceResult(False, "slot_not_available", 409, "Новый слот больше недоступен.")
            if _slot_claimed_by_other_candidate(
                target_slot,
                candidate_id=assignment.candidate_id,
                candidate_tg_ids=candidate_tg_ids,
            ):
                return ServiceResult(False, "slot_not_available", 409, "Новый слот уже занят другим кандидатом.")

            other_active_assignments = await _active_other_assignments_count(
                session,
                slot_id=target_slot.id,
                current_assignment_id=assignment.id,
            )
            capacity = max(int(getattr(target_slot, "capacity", 1) or 1), 1)
            if other_active_assignments >= capacity:
                return ServiceResult(False, "slot_full", 409, "Слот заполнен.")

            assignment.slot_id = target_slot.id
            assignment.status = SlotAssignmentStatus.OFFERED
            assignment.offered_at = _now()
            assignment.status_before_reschedule = None

            request.status = RescheduleRequestStatus.DECLINED
            request.decided_at = _now()
            request.decided_by_id = decided_by_id
            request.decided_by_type = decided_by_type
            request.recruiter_comment = comment
            request.alternative_slot_id = target_slot.id

            await _invalidate_action_tokens(session, assignment_id=assignment.id)
            confirm_token = await _create_action_token(
                session, ACTION_CONFIRM, assignment.id
            )
            reschedule_token = await _create_action_token(
                session, ACTION_RESCHEDULE, assignment.id
            )

            await add_outbox_notification(
                notification_type="slot_assignment_offer",
                booking_id=target_slot.id,
                candidate_tg_id=assignment.candidate_tg_id,
                payload={
                    "slot_assignment_id": assignment.id,
                    "slot_id": target_slot.id,
                    "candidate_id": assignment.candidate_id,
                    "candidate_tg_id": assignment.candidate_tg_id,
                    "candidate_tz": assignment.candidate_tz or target_slot.tz_name,
                    "recruiter_id": assignment.recruiter_id,
                    "start_utc": target_slot.start_utc.isoformat(),
                    "duration_min": target_slot.duration_min,
                    "action_tokens": {
                        "confirm": confirm_token,
                        "reschedule": reschedule_token,
                    },
                    "comment": comment,
                    "is_alternative": True,
                },
                session=session,
            )

            session.add(
                AuditLog(
                    action="slot_assignment.alternative_proposed",
                    entity_type="slot_assignment",
                    entity_id=str(assignment.id),
                    created_at=_now(),
                    changes={"slot_id": target_slot.id},
                )
            )

            return ServiceResult(
                True,
                "alternative_offered",
                200,
                payload={
                    "slot_id": target_slot.id,
                    "confirm_token": confirm_token,
                    "reschedule_token": reschedule_token,
                },
            )


async def decline_reschedule(
    *,
    assignment_id: int,
    decided_by_id: int,
    decided_by_type: str,
    comment: Optional[str] = None,
) -> ServiceResult:
    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")
            if assignment.status != SlotAssignmentStatus.RESCHEDULE_REQUESTED:
                return ServiceResult(False, "invalid_status", 409, "Запрос переноса не ожидается.")

            request = await session.scalar(
                select(RescheduleRequest)
                .where(
                    RescheduleRequest.slot_assignment_id == assignment_id,
                    RescheduleRequest.status == RescheduleRequestStatus.PENDING,
                )
                .with_for_update()
            )
            if request is None:
                return ServiceResult(False, "request_not_found", 404, "Запрос переноса не найден.")

            previous_status = assignment.status_before_reschedule or SlotAssignmentStatus.OFFERED
            assignment.status = previous_status
            assignment.status_before_reschedule = None

            request.status = RescheduleRequestStatus.DECLINED
            request.decided_at = _now()
            request.decided_by_id = decided_by_id
            request.decided_by_type = decided_by_type
            request.recruiter_comment = comment

            await add_outbox_notification(
                notification_type="slot_assignment_reschedule_declined",
                booking_id=assignment.slot_id,
                candidate_tg_id=assignment.candidate_tg_id,
                payload={
                    "slot_assignment_id": assignment.id,
                    "slot_id": assignment.slot_id,
                    "candidate_tz": assignment.candidate_tz,
                    "comment": comment,
                },
                session=session,
            )

            session.add(
                AuditLog(
                    action="slot_assignment.reschedule_declined",
                    entity_type="slot_assignment",
                    entity_id=str(assignment.id),
                    created_at=_now(),
                )
            )

            return ServiceResult(True, "reschedule_declined", 200)
