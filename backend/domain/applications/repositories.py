from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from backend.domain.candidates.models import User
from backend.domain.models import (
    Application,
    ApplicationEvent,
    Interview,
    Requisition,
    Slot,
    SlotAssignment,
)
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .contracts import (
    ApplicationCreateRequest,
    ApplicationEventRecord,
    ApplicationEventRepository,
    ApplicationRecord,
    ApplicationResolverRepository,
    ApplicationState,
    ResolverContext,
    ResolverContextConflictError,
    ResolverSnapshot,
)
from .uow import ApplicationUnitOfWork, SqlAlchemyApplicationUnitOfWork

_INTERNAL_METADATA_PREFIX = "_rs_"
_METADATA_PRODUCER_FAMILY = "_rs_producer_family"
_METADATA_SOURCE_REF = "_rs_source_ref"
_METADATA_PAYLOAD_FINGERPRINT = "_rs_payload_fingerprint"
_METADATA_RAW_IDEMPOTENCY_KEY = "_rs_raw_idempotency_key"
_CREATE_IDEMPOTENCY_CACHE = "rs_applications_create_idempotency_cache"
_TERMINAL_STATUSES = {
    "archived",
    "cancelled",
    "canceled",
    "closed",
    "declined",
    "hired",
    "not_hired",
    "rejected",
    "withdrawn",
}


def _as_application_state(model: Application) -> ApplicationState:
    if model.archived_at is not None:
        return ApplicationState.ARCHIVED
    if (model.lifecycle_status or "").strip().lower() in _TERMINAL_STATUSES or model.final_outcome:
        return ApplicationState.TERMINAL
    return ApplicationState.ACTIVE


def _to_application_record(model: Application) -> ApplicationRecord:
    return ApplicationRecord(
        application_id=int(model.id),
        candidate_id=int(model.candidate_id),
        requisition_id=int(model.requisition_id) if model.requisition_id is not None else None,
        vacancy_id=int(model.vacancy_id) if model.vacancy_id is not None else None,
        state=_as_application_state(model),
    )


def _strip_internal_metadata(metadata_json: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(metadata_json or {})
    for key in tuple(payload.keys()):
        if key.startswith(_INTERNAL_METADATA_PREFIX):
            payload.pop(key, None)
    return payload


def _event_metadata(record: ApplicationEventRecord) -> dict[str, Any]:
    metadata = dict(record.metadata_json)
    metadata[_METADATA_PRODUCER_FAMILY] = record.producer_family
    metadata[_METADATA_SOURCE_REF] = record.source_ref
    metadata[_METADATA_PAYLOAD_FINGERPRINT] = record.payload_fingerprint
    metadata[_METADATA_RAW_IDEMPOTENCY_KEY] = record.idempotency_key
    return metadata


def _from_event_model(model: ApplicationEvent) -> ApplicationEventRecord:
    metadata = dict(model.metadata_json or {})
    producer_family = str(metadata.get(_METADATA_PRODUCER_FAMILY, "unknown"))
    source_ref = str(metadata.get(_METADATA_SOURCE_REF, ""))
    payload_fingerprint = str(metadata.get(_METADATA_PAYLOAD_FINGERPRINT, ""))
    raw_idempotency_key = str(metadata.get(_METADATA_RAW_IDEMPOTENCY_KEY, model.idempotency_key or ""))
    return ApplicationEventRecord(
        event_id=model.event_id,
        correlation_id=model.correlation_id or "",
        scoped_idempotency_key=model.idempotency_key or "",
        idempotency_key=raw_idempotency_key,
        producer_family=producer_family,
        event_type=model.event_type,
        occurred_at=model.occurred_at,
        candidate_id=int(model.candidate_id),
        application_id=int(model.application_id) if model.application_id is not None else None,
        requisition_id=int(model.requisition_id) if model.requisition_id is not None else None,
        source_system=model.source or "",
        source_ref=source_ref,
        actor_type=model.actor_type,
        actor_id=model.actor_id,
        channel=model.channel,
        metadata_json=_strip_internal_metadata(metadata),
        payload_fingerprint=payload_fingerprint,
    )


def _sqlite_next_pk(session: Session, model_cls: type[Application] | type[ApplicationEvent]) -> int | None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return None
    next_id = session.execute(select(func.coalesce(func.max(model_cls.id), 0) + 1)).scalar_one()
    return int(next_id)


def _normalize_candidate_id(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _parse_hh_vacancy_id(value: str | None) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        return None
    return int(raw)


class SqlAlchemyApplicationResolverRepository(ApplicationResolverRepository):
    """ORM-backed snapshot loader for the pure Phase B resolver skeleton."""

    def __init__(
        self,
        session: Session,
        *,
        uow: ApplicationUnitOfWork | None = None,
    ) -> None:
        self._session = session
        self._uow = uow or SqlAlchemyApplicationUnitOfWork(session)

    def get_application_by_id(
        self,
        *,
        application_id: int,
        candidate_id: int | None = None,
    ) -> ApplicationRecord | None:
        model = self._session.get(Application, application_id)
        if model is None:
            return None
        if candidate_id is not None and int(model.candidate_id) != candidate_id:
            raise ResolverContextConflictError(
                f"application_id={application_id} does not belong to candidate_id={candidate_id}"
            )
        return _to_application_record(model)

    def find_candidate_applications(
        self,
        *,
        candidate_id: int,
        requisition_id: int | None = None,
        state: ApplicationState | None = None,
    ) -> tuple[ApplicationRecord, ...]:
        models = self._load_applications(candidate_id=candidate_id)
        if requisition_id is not None:
            models = [model for model in models if model.requisition_id == requisition_id]
        records = tuple(_to_application_record(model) for model in models)
        if state is None:
            return records
        return tuple(record for record in records if record.state == state)

    def get_snapshot(self, *, candidate_id: int, context: ResolverContext) -> ResolverSnapshot:
        candidate = self._session.get(User, candidate_id)
        if candidate is None:
            return ResolverSnapshot(candidate_id=candidate_id, candidate_exists=False)
        return self._build_snapshot(candidate_id=candidate_id, context=context)

    def get_slot_assignment_snapshot(
        self, *, slot_assignment_id: int, context: ResolverContext
    ) -> ResolverSnapshot:
        assignment = self._session.get(SlotAssignment, slot_assignment_id)
        if assignment is None:
            return ResolverSnapshot(
                candidate_id=context.candidate_id or 0,
                candidate_exists=bool(context.candidate_id),
                slot_assignment_found=False,
            )

        candidate = self._resolve_candidate_for_slot_assignment(assignment, context)
        if candidate is None:
            candidate_id = context.candidate_id or 0
            return ResolverSnapshot(
                candidate_id=candidate_id,
                candidate_exists=bool(context.candidate_id),
                slot_assignment_found=True,
                scheduling_integrity_error=True,
            )

        slot_matches = tuple(self._load_slot_assignment_matches(slot_assignment_id=slot_assignment_id))
        slot_requisition_ids = tuple(
            sorted(
                {
                    match.requisition_id
                    for match in slot_matches
                    if match.requisition_id is not None
                }
            )
        )
        snapshot = self._build_snapshot(candidate_id=int(candidate.id), context=replace(context, candidate_id=int(candidate.id)))
        return replace(
            snapshot,
            slot_assignment_found=True,
            slot_assignment_matches=slot_matches,
            slot_assignment_requisition_ids=slot_requisition_ids,
        )

    def get_hh_event_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        candidate, hh_conflict = self._resolve_candidate_for_hh(context)
        if candidate is None:
            return ResolverSnapshot(
                candidate_id=context.candidate_id or 0,
                candidate_exists=False,
                hh_identity_conflict=hh_conflict,
            )
        candidate_id = int(candidate.id)
        snapshot = self._build_snapshot(candidate_id=candidate_id, context=replace(context, candidate_id=candidate_id))
        parsed_vacancy_id = _parse_hh_vacancy_id(context.hh_vacancy_id)
        hh_matches = self._load_hh_matches(candidate_id=candidate_id, vacancy_id=parsed_vacancy_id)
        hh_requisition_ids = self._load_hh_requisition_ids(vacancy_id=parsed_vacancy_id)
        if len(hh_requisition_ids) == 1 and len(hh_matches) <= 1:
            requisition_id = hh_requisition_ids[0]
            archived = self.find_candidate_applications(
                candidate_id=candidate_id,
                requisition_id=requisition_id,
                state=ApplicationState.ARCHIVED,
            )
        else:
            archived = ()
        return replace(
            snapshot,
            hh_matches=hh_matches,
            hh_requisition_ids=hh_requisition_ids,
            archived_matches=archived or snapshot.archived_matches,
            hh_identity_conflict=hh_conflict,
        )

    def get_message_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        if context.candidate_id is None:
            raise ResolverContextConflictError("candidate_id is required for message resolution")
        return self.get_snapshot(candidate_id=context.candidate_id, context=context)

    def get_ai_output_snapshot(self, *, context: ResolverContext) -> ResolverSnapshot:
        if context.candidate_id is None:
            raise ResolverContextConflictError("candidate_id is required for AI resolution")
        return self.get_snapshot(candidate_id=context.candidate_id, context=context)

    def get_created_application_by_idempotency(
        self, *, idempotency_key: str
    ) -> ApplicationRecord | None:
        cache = self._session.info.get(_CREATE_IDEMPOTENCY_CACHE, {})
        application_id = cache.get(idempotency_key)
        if application_id is None:
            return None
        model = self._session.get(Application, application_id)
        return _to_application_record(model) if model is not None else None

    def create_application(self, request: ApplicationCreateRequest) -> ApplicationRecord:
        self._uow.ensure_transaction()
        vacancy_id = request.vacancy_id
        if vacancy_id is None and request.requisition_id is not None:
            requisition = self._session.get(Requisition, request.requisition_id)
            vacancy_id = int(requisition.vacancy_id) if requisition and requisition.vacancy_id is not None else None

        model = Application(
            candidate_id=request.candidate_id,
            requisition_id=request.requisition_id,
            vacancy_id=vacancy_id,
            source=request.source_system,
            source_detail=request.source_ref,
            lifecycle_status="new",
        )
        sqlite_id = _sqlite_next_pk(self._session, Application)
        if sqlite_id is not None:
            model.id = sqlite_id
        self._session.add(model)
        self._session.flush()

        cache = self._session.info.setdefault(_CREATE_IDEMPOTENCY_CACHE, {})
        cache[request.idempotency_key] = int(model.id)
        return _to_application_record(model)

    def _build_snapshot(self, *, candidate_id: int, context: ResolverContext) -> ResolverSnapshot:
        applications = self._load_applications(candidate_id=candidate_id)
        active_records = tuple(
            _to_application_record(model)
            for model in applications
            if _as_application_state(model) == ApplicationState.ACTIVE
        )
        explicit_application = None
        if context.explicit_application_id is not None:
            explicit_application = self.get_application_by_id(
                application_id=context.explicit_application_id,
                candidate_id=candidate_id,
            )

        explicit_requisition_ids = self._explicit_requisition_ids(context=context)
        explicit_matches = ()
        duplicate_exact = ()
        archived_matches = ()
        if len(explicit_requisition_ids) == 1:
            target_requisition_id = explicit_requisition_ids[0]
            exact_active = tuple(
                record for record in active_records if record.requisition_id == target_requisition_id
            )
            explicit_matches = exact_active if len(exact_active) == 1 else ()
            duplicate_exact = exact_active if len(exact_active) > 1 else ()
            archived_matches = self.find_candidate_applications(
                candidate_id=candidate_id,
                requisition_id=target_requisition_id,
                state=ApplicationState.ARCHIVED,
            )

        null_matches = tuple(record for record in active_records if record.requisition_id is None)
        duplicate_null = null_matches if len(null_matches) > 1 else ()

        return ResolverSnapshot(
            candidate_id=candidate_id,
            candidate_exists=True,
            explicit_application=explicit_application,
            explicit_requisition_matches=explicit_matches,
            explicit_requisition_ids=explicit_requisition_ids,
            null_requisition_matches=null_matches if len(null_matches) == 1 else (),
            archived_matches=archived_matches,
            duplicate_exact_matches=duplicate_exact,
            duplicate_null_matches=duplicate_null,
        )

    def _explicit_requisition_ids(self, *, context: ResolverContext) -> tuple[int, ...]:
        if context.explicit_requisition_id is not None:
            return (context.explicit_requisition_id,)
        if context.explicit_vacancy_id is None:
            return ()
        query = select(Requisition.id).where(Requisition.vacancy_id == context.explicit_vacancy_id)
        ids = self._session.execute(query).scalars().all()
        return tuple(sorted(int(value) for value in ids))

    def _load_applications(self, *, candidate_id: int) -> list[Application]:
        query = (
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.asc(), Application.id.asc())
        )
        return list(self._session.execute(query).scalars().all())

    def _resolve_candidate_for_slot_assignment(
        self, assignment: SlotAssignment, context: ResolverContext
    ) -> User | None:
        normalized_candidate_key = _normalize_candidate_id(assignment.candidate_id)
        if normalized_candidate_key:
            candidate = self._session.execute(
                select(User).where(User.candidate_id == normalized_candidate_key)
            ).scalar_one_or_none()
            if candidate is None:
                return None
            if context.candidate_id is not None and int(candidate.id) != context.candidate_id:
                raise ResolverContextConflictError(
                    f"slot_assignment_id={assignment.id} does not belong to candidate_id={context.candidate_id}"
                )
            return candidate

        candidate_tg_id = assignment.candidate_tg_id
        if candidate_tg_id is None:
            slot = self._session.get(Slot, assignment.slot_id)
            candidate_tg_id = slot.candidate_tg_id if slot is not None else None
        if candidate_tg_id is None:
            return None
        candidates = self._session.execute(
            select(User).where(
                or_(User.telegram_id == candidate_tg_id, User.telegram_user_id == candidate_tg_id)
            )
        ).scalars().all()
        if len(candidates) != 1:
            return None
        candidate = candidates[0]
        if context.candidate_id is not None and int(candidate.id) != context.candidate_id:
            raise ResolverContextConflictError(
                f"slot_assignment_id={assignment.id} does not belong to candidate_id={context.candidate_id}"
            )
        return candidate

    def _load_slot_assignment_matches(self, *, slot_assignment_id: int) -> Iterable[ApplicationRecord]:
        query = (
            select(Application)
            .join(Interview, Interview.application_id == Application.id)
            .where(Interview.slot_assignment_id == slot_assignment_id)
            .order_by(Application.created_at.asc(), Application.id.asc())
        )
        for model in self._session.execute(query).scalars().all():
            yield _to_application_record(model)

    def _resolve_candidate_for_hh(
        self, context: ResolverContext
    ) -> tuple[User | None, bool]:
        if context.candidate_id is not None:
            candidate = self._session.get(User, context.candidate_id)
            return candidate, False

        filters = []
        if context.hh_resume_id:
            filters.append(User.hh_resume_id == context.hh_resume_id)
        if context.hh_negotiation_id:
            filters.append(User.hh_negotiation_id == context.hh_negotiation_id)
        if context.hh_vacancy_id:
            filters.append(User.hh_vacancy_id == context.hh_vacancy_id)
        if not filters:
            return None, False
        candidates = self._session.execute(select(User).where(or_(*filters))).scalars().all()
        if not candidates:
            return None, False
        if len(candidates) > 1:
            return candidates[0], True
        return candidates[0], False

    def _load_hh_matches(
        self, *, candidate_id: int, vacancy_id: int | None
    ) -> tuple[ApplicationRecord, ...]:
        if vacancy_id is None:
            return ()
        query = (
            select(Application)
            .outerjoin(Requisition, Requisition.id == Application.requisition_id)
            .where(
                Application.candidate_id == candidate_id,
                or_(
                    Application.vacancy_id == vacancy_id,
                    Requisition.vacancy_id == vacancy_id,
                ),
            )
            .order_by(Application.created_at.asc(), Application.id.asc())
        )
        return tuple(_to_application_record(model) for model in self._session.execute(query).scalars().all())

    def _load_hh_requisition_ids(self, *, vacancy_id: int | None) -> tuple[int, ...]:
        if vacancy_id is None:
            return ()
        query = select(Requisition.id).where(Requisition.vacancy_id == vacancy_id)
        ids = self._session.execute(query).scalars().all()
        return tuple(sorted(int(value) for value in ids))


class SqlAlchemyApplicationEventRepository(ApplicationEventRepository):
    """Current-schema event store adapter for the Phase B publisher skeleton."""

    def __init__(
        self,
        session: Session,
        *,
        uow: ApplicationUnitOfWork | None = None,
    ) -> None:
        self._session = session
        self._uow = uow or SqlAlchemyApplicationUnitOfWork(session)

    def ensure_transaction(self) -> None:
        self._uow.ensure_transaction()

    def get_by_scoped_idempotency_key(
        self, *, scoped_idempotency_key: str
    ) -> ApplicationEventRecord | None:
        model = self._session.execute(
            select(ApplicationEvent).where(ApplicationEvent.idempotency_key == scoped_idempotency_key)
        ).scalar_one_or_none()
        if model is None:
            return None
        return _from_event_model(model)

    def append_event(self, record: ApplicationEventRecord) -> ApplicationEventRecord:
        self._uow.ensure_transaction()
        model = ApplicationEvent(
            event_id=record.event_id,
            occurred_at=record.occurred_at,
            actor_type=record.actor_type or "system",
            actor_id=str(record.actor_id) if record.actor_id is not None else None,
            candidate_id=record.candidate_id,
            application_id=record.application_id,
            requisition_id=record.requisition_id,
            event_type=record.event_type,
            status_from=record.metadata_json.get("status_from"),
            status_to=record.metadata_json.get("status_to"),
            source=record.source_system,
            channel=record.channel,
            idempotency_key=record.scoped_idempotency_key,
            correlation_id=record.correlation_id,
            metadata_json=_event_metadata(record),
        )
        sqlite_id = _sqlite_next_pk(self._session, ApplicationEvent)
        if sqlite_id is not None:
            model.id = sqlite_id
        self._session.add(model)
        self._session.flush()
        return _from_event_model(model)


__all__ = [
    "SqlAlchemyApplicationEventRepository",
    "SqlAlchemyApplicationResolverRepository",
]
