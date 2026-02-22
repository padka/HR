"""Slot assignment flow services (offer/confirm/reschedule) with action tokens."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.core.db import async_session
from backend.domain.candidates.models import User
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


@dataclass
class ServiceResult:
    ok: bool
    status: str
    status_code: int
    message: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


async def create_slot_assignment(
    *,
    slot_id: int,
    candidate_id: str,
    candidate_tg_id: Optional[int] = None,
    candidate_tz: Optional[str] = None,
    created_by: Optional[str] = None,
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

                try:
                    ensure_slot_not_in_past(slot.start_utc, slot_tz=slot.tz_name)
                except SlotValidationError:
                    return ServiceResult(False, "slot_in_past", 409, "Слот уже в прошлом.")

                candidate = await session.scalar(
                    select(User).where(User.candidate_id == candidate_id)
                )
                if candidate is None:
                    return ServiceResult(False, "candidate_not_found", 404, "Кандидат не найден.")

                candidate_tg_id = candidate_tg_id or candidate.telegram_id
                candidate_tz = candidate_tz or slot.tz_name

                existing = await session.scalar(
                    select(SlotAssignment.id)
                    .where(
                        SlotAssignment.candidate_id == candidate_id,
                        SlotAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
                    )
                    .with_for_update()
                )
                if existing:
                    return ServiceResult(
                        False,
                        "candidate_has_active_assignment",
                        409,
                        "У кандидата уже есть активное назначение.",
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
) -> ServiceResult:
    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")

            if candidate_tg_id is not None and assignment.candidate_tg_id not in (None, candidate_tg_id):
                return ServiceResult(False, "forbidden", 403, "Доступ запрещён.")

            if assignment.status not in {
                SlotAssignmentStatus.OFFERED,
                SlotAssignmentStatus.CONFIRMED,
                SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
            }:
                return ServiceResult(False, "invalid_status", 409, "Нельзя подтвердить это назначение.")

            token_ok, token_status = await _consume_action_token(
                session, token=action_token, action=ACTION_CONFIRM, entity_id=assignment_id
            )
            if not token_ok:
                if assignment.status in CONFIRMED_ASSIGNMENT_STATUSES:
                    return ServiceResult(True, "already_confirmed", 200)
                return ServiceResult(False, f"token_{token_status}", 409, "Ссылка устарела.")

            slot = await session.scalar(
                select(Slot).where(Slot.id == assignment.slot_id).with_for_update()
            )
            if slot is None:
                return ServiceResult(False, "slot_not_found", 404, "Слот не найден.")

            confirmed_count = await session.scalar(
                select(func.count())
                .select_from(SlotAssignment)
                .where(
                    SlotAssignment.slot_id == slot.id,
                    SlotAssignment.status.in_(CONFIRMED_ASSIGNMENT_STATUSES),
                )
            )
            capacity = max(int(getattr(slot, "capacity", 1) or 1), 1)
            if assignment.status not in CONFIRMED_ASSIGNMENT_STATUSES and (confirmed_count or 0) >= capacity:
                return ServiceResult(False, "slot_full", 409, "Слот заполнен.")

            if assignment.status in CONFIRMED_ASSIGNMENT_STATUSES:
                return ServiceResult(True, "already_confirmed", 200)

            assignment.status = SlotAssignmentStatus.CONFIRMED
            assignment.confirmed_at = _now()
            assignment.status_before_reschedule = None

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
    requested_start_utc: datetime,
    requested_tz: Optional[str],
    comment: Optional[str] = None,
) -> ServiceResult:
    async with async_session() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(SlotAssignment).where(SlotAssignment.id == assignment_id).with_for_update()
            )
            if assignment is None:
                return ServiceResult(False, "not_found", 404, "Назначение не найдено.")

            if candidate_tg_id is not None and assignment.candidate_tg_id not in (None, candidate_tg_id):
                return ServiceResult(False, "forbidden", 403, "Доступ запрещён.")

            if assignment.status not in {
                SlotAssignmentStatus.OFFERED,
                SlotAssignmentStatus.CONFIRMED,
                SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
            }:
                return ServiceResult(False, "invalid_status", 409, "Запрос переноса недоступен.")

            token_ok, token_status = await _consume_action_token(
                session, token=action_token, action=ACTION_RESCHEDULE, entity_id=assignment_id
            )
            if not token_ok:
                if assignment.status == SlotAssignmentStatus.RESCHEDULE_REQUESTED:
                    return ServiceResult(True, "already_requested", 200)
                return ServiceResult(False, f"token_{token_status}", 409, "Ссылка устарела.")

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

            try:
                ensure_slot_not_in_past(requested_start_utc, allow_past=False)
            except SlotValidationError:
                return ServiceResult(False, "requested_time_in_past", 409, "Нельзя выбрать время в прошлом.")

            request = RescheduleRequest(
                slot_assignment_id=assignment.id,
                requested_start_utc=requested_start_utc,
                requested_tz=requested_tz,
                candidate_comment=comment,
                status=RescheduleRequestStatus.PENDING,
                created_at=_now(),
            )
            session.add(request)
            await session.flush()

            assignment.status_before_reschedule = assignment.status
            assignment.status = SlotAssignmentStatus.RESCHEDULE_REQUESTED
            assignment.reschedule_requested_at = _now()

            recruiter = await session.get(Recruiter, assignment.recruiter_id)
            candidate = await session.scalar(
                select(User).where(User.candidate_id == assignment.candidate_id)
            )
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
                    "requested_start_utc": requested_start_utc.isoformat(),
                    "comment": comment,
                },
                session=session,
            )

            session.add(
                AuditLog(
                    action="slot_assignment.reschedule_requested",
                    entity_type="slot_assignment",
                    entity_id=str(assignment.id),
                    created_at=_now(),
                    changes={"requested_start_utc": requested_start_utc.isoformat()},
                )
            )

            return ServiceResult(
                True,
                "reschedule_requested",
                200,
                payload={"reschedule_request_id": request.id},
            )


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

            slot = await session.scalar(
                select(Slot)
                .where(Slot.id == assignment.slot_id)
                .with_for_update()
            )
            if slot is None:
                return ServiceResult(False, "slot_not_found", 404, "Слот не найден.")

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

            confirmed_count = await session.scalar(
                select(func.count())
                .select_from(SlotAssignment)
                .where(
                    SlotAssignment.slot_id == target_slot.id,
                    SlotAssignment.status.in_(CONFIRMED_ASSIGNMENT_STATUSES),
                )
            )
            capacity = max(int(getattr(target_slot, "capacity", 1) or 1), 1)
            if assignment.status not in CONFIRMED_ASSIGNMENT_STATUSES and (confirmed_count or 0) >= capacity:
                return ServiceResult(False, "slot_full", 409, "Слот заполнен.")

            assignment.slot_id = target_slot.id
            assignment.status = SlotAssignmentStatus.RESCHEDULE_CONFIRMED
            assignment.confirmed_at = _now()
            assignment.status_before_reschedule = None

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

            confirmed_count = await session.scalar(
                select(func.count())
                .select_from(SlotAssignment)
                .where(
                    SlotAssignment.slot_id == target_slot.id,
                    SlotAssignment.status.in_(CONFIRMED_ASSIGNMENT_STATUSES),
                )
            )
            capacity = max(int(getattr(target_slot, "capacity", 1) or 1), 1)
            if assignment.status not in CONFIRMED_ASSIGNMENT_STATUSES and (confirmed_count or 0) >= capacity:
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
