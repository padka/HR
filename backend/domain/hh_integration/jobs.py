"""Queue and worker helpers for HH integration sync jobs."""

from __future__ import annotations

import json
import logging
import random
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.core.ai.service import schedule_warm_candidates_ai_outputs
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.candidates.models import User
from backend.domain.hh_integration.client import (
    HHApiClient,
    HHApiError,
    normalize_hh_api_error,
)
from backend.domain.hh_integration.contracts import (
    HHConnectionStatus,
    HHIdentitySyncStatus,
    HHSyncDirection,
    HHSyncFailureCode,
    HHSyncJobStatus,
)
from backend.domain.hh_integration.importer import (
    import_hh_negotiations,
    import_hh_vacancies,
    serialize_import_result,
)
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    HHConnection,
    HHNegotiation,
    HHSyncJob,
)
from backend.domain.hh_integration.service import decrypt_access_token
from sqlalchemy import and_, delete, func, or_, select

logger = logging.getLogger(__name__)

_JOB_RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))
_RUNNING_STALE_AFTER = timedelta(minutes=15)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _retry_delay(attempts: int, *, retry_after_seconds: int | None = None) -> timedelta:
    if retry_after_seconds is not None:
        return timedelta(seconds=max(int(retry_after_seconds), 1))
    base_delay = _JOB_RETRY_DELAYS[min(max(attempts, 1) - 1, len(_JOB_RETRY_DELAYS) - 1)]
    jitter_ratio = random.uniform(0.85, 1.15)
    return timedelta(seconds=max(1.0, base_delay.total_seconds() * jitter_ratio))


def serialize_hh_sync_job(job: HHSyncJob) -> dict[str, object]:
    return {
        "id": job.id,
        "connection_id": job.connection_id,
        "candidate_id": job.candidate_id,
        "job_type": job.job_type,
        "direction": job.direction,
        "entity_type": job.entity_type,
        "entity_external_id": job.entity_external_id,
        "status": job.status,
        "attempts": job.attempts,
        "payload": dict(job.payload_json or {}),
        "result": dict(job.result_json or {}) if isinstance(job.result_json, dict) else None,
        "last_error": job.last_error,
        "failure_code": job.failure_code,
        "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


async def enqueue_hh_sync_job(
    session,
    *,
    connection: HHConnection | None,
    job_type: str,
    entity_type: str | None = None,
    entity_external_id: str | None = None,
    payload_json: dict | None = None,
    direction: str = HHSyncDirection.INBOUND,
    idempotency_key: str | None = None,
    candidate_id: int | None = None,
) -> tuple[HHSyncJob, bool]:
    payload = dict(payload_json or {})
    signature = [
        HHSyncJob.connection_id.is_(None) if connection is None else HHSyncJob.connection_id == connection.id,
        HHSyncJob.job_type == job_type,
        HHSyncJob.direction == direction,
        HHSyncJob.entity_type.is_(entity_type) if entity_type is None else HHSyncJob.entity_type == entity_type,
        HHSyncJob.entity_external_id.is_(entity_external_id)
        if entity_external_id is None
        else HHSyncJob.entity_external_id == entity_external_id,
        HHSyncJob.status.in_([HHSyncJobStatus.PENDING, HHSyncJobStatus.RUNNING]),
    ]
    existing = (
        await session.execute(select(HHSyncJob).where(and_(*signature)).order_by(HHSyncJob.id.desc()).limit(1))
    ).scalar_one_or_none()
    if existing is not None and dict(existing.payload_json or {}) == payload:
        return existing, False

    job = HHSyncJob(
        connection_id=connection.id if connection is not None else None,
        candidate_id=candidate_id,
        job_type=job_type,
        direction=direction,
        entity_type=entity_type,
        entity_external_id=entity_external_id,
        status=HHSyncJobStatus.PENDING,
        idempotency_key=idempotency_key or uuid4().hex,
        payload_json=payload,
        next_retry_at=None,
    )
    session.add(job)
    await session.flush()
    return job, True


async def list_hh_sync_jobs(
    session,
    *,
    connection_id: int,
    limit: int = 20,
    status: str | None = None,
) -> list[HHSyncJob]:
    stmt = select(HHSyncJob).where(HHSyncJob.connection_id == connection_id)
    if status:
        stmt = stmt.where(HHSyncJob.status == status)
    stmt = stmt.order_by(HHSyncJob.id.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def count_hh_sync_jobs_by_status(session, *, connection_id: int) -> dict[str, int]:
    rows = (
        await session.execute(
            select(HHSyncJob.status, func.count(HHSyncJob.id))
            .where(HHSyncJob.connection_id == connection_id)
            .group_by(HHSyncJob.status)
        )
    ).all()
    return {str(status): int(count) for status, count in rows}


async def retry_hh_sync_job(session, *, connection: HHConnection, job_id: int) -> HHSyncJob | None:
    job = (
        await session.execute(
            select(HHSyncJob).where(HHSyncJob.id == job_id, HHSyncJob.connection_id == connection.id).limit(1)
        )
    ).scalar_one_or_none()
    if job is None:
        return None
    job.status = HHSyncJobStatus.PENDING
    job.next_retry_at = None
    job.last_error = None
    job.failure_code = None
    job.result_json = None
    job.finished_at = None
    job.started_at = None
    await session.flush()
    return job


async def _claim_hh_sync_jobs(batch_size: int) -> list[int]:
    now = _utcnow()
    stale_before = now - _RUNNING_STALE_AFTER
    async with async_session() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(HHSyncJob)
                    .where(
                        or_(
                            HHSyncJob.status == HHSyncJobStatus.PENDING,
                            and_(
                                HHSyncJob.status == HHSyncJobStatus.RUNNING,
                                HHSyncJob.started_at.is_not(None),
                                HHSyncJob.started_at <= stale_before,
                            ),
                        ),
                        or_(HHSyncJob.next_retry_at.is_(None), HHSyncJob.next_retry_at <= now),
                    )
                    .order_by(HHSyncJob.id.asc())
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).scalars().all()
            claimed: list[int] = []
            for row in rows:
                row.status = HHSyncJobStatus.RUNNING
                row.started_at = now
                row.finished_at = None
                row.attempts = int(row.attempts or 0) + 1
                claimed.append(row.id)
            return claimed


async def _complete_job(job_id: int, *, result_payload: dict | None = None) -> None:
    async with async_session() as session:
        async with session.begin():
            job = await session.get(HHSyncJob, job_id, with_for_update=True)
            if job is None:
                return
            payload = dict(job.payload_json or {})
            if result_payload:
                payload["last_result"] = result_payload
            job.payload_json = payload
            job.result_json = result_payload or None
            job.status = HHSyncJobStatus.DONE
            job.last_error = None
            job.failure_code = None
            job.next_retry_at = None
            job.finished_at = _utcnow()


async def _fail_job(
    job_id: int,
    *,
    error_message: str,
    failure_code: str,
    retryable: bool,
    result_payload: dict | None = None,
    retry_after_seconds: int | None = None,
) -> None:
    async with async_session() as session:
        async with session.begin():
            job = await session.get(HHSyncJob, job_id, with_for_update=True)
            if job is None:
                return
            attempts = max(int(job.attempts or 0), 1)
            job.last_error = error_message
            job.failure_code = failure_code
            job.result_json = result_payload or None
            job.finished_at = _utcnow()
            if not retryable or attempts >= len(_JOB_RETRY_DELAYS) + 1:
                job.status = (
                    HHSyncJobStatus.FORBIDDEN
                    if failure_code == HHSyncFailureCode.ACCESS_FORBIDDEN
                    else HHSyncJobStatus.DEAD
                )
                job.next_retry_at = None
            else:
                job.status = HHSyncJobStatus.PENDING
                job.next_retry_at = _utcnow() + _retry_delay(
                    attempts,
                    retry_after_seconds=retry_after_seconds,
                )


async def _record_connection_failure(
    *,
    connection_id: int | None,
    normalized_error,
) -> None:
    if connection_id is None:
        return
    async with async_session() as session:
        async with session.begin():
            connection = await session.get(HHConnection, connection_id, with_for_update=True)
            if connection is None:
                return
            connection.last_error = normalized_error.message
            if not normalized_error.retryable:
                connection.status = HHConnectionStatus.ERROR


async def cleanup_hh_sync_jobs(
    *,
    done_retention_days: int | None = None,
    dead_retention_days: int | None = None,
    keep_last_dead_per_connection: int | None = None,
) -> dict[str, int]:
    """Apply idempotent retention for terminal HH sync jobs."""
    settings = get_settings()
    done_days = int(done_retention_days or settings.hh_sync_done_retention_days)
    dead_days = int(dead_retention_days or settings.hh_sync_dead_retention_days)
    keep_dead = int(
        settings.hh_sync_keep_last_dead_per_connection
        if keep_last_dead_per_connection is None
        else keep_last_dead_per_connection
    )
    now = _utcnow()
    done_cutoff = now - timedelta(days=max(done_days, 1))
    dead_cutoff = now - timedelta(days=max(dead_days, 1))

    async with async_session() as session:
        async with session.begin():
            done_ids = list(
                (
                    await session.execute(
                        select(HHSyncJob.id)
                        .where(
                            HHSyncJob.status == HHSyncJobStatus.DONE,
                            or_(
                                HHSyncJob.finished_at <= done_cutoff,
                                and_(HHSyncJob.finished_at.is_(None), HHSyncJob.created_at <= done_cutoff),
                            ),
                        )
                    )
                ).scalars().all()
            )
            if done_ids:
                await session.execute(delete(HHSyncJob).where(HHSyncJob.id.in_(done_ids)))
            done_deleted = len(done_ids)

            dead_jobs = (
                await session.execute(
                    select(HHSyncJob.id, HHSyncJob.connection_id)
                    .where(
                        HHSyncJob.status.in_([HHSyncJobStatus.DEAD, HHSyncJobStatus.FORBIDDEN]),
                        or_(
                            HHSyncJob.finished_at <= dead_cutoff,
                            and_(HHSyncJob.finished_at.is_(None), HHSyncJob.created_at <= dead_cutoff),
                        ),
                    )
                    .order_by(HHSyncJob.connection_id.asc(), HHSyncJob.id.desc())
                )
            ).all()
            seen_by_connection: dict[int | None, int] = {}
            dead_delete_ids: list[int] = []
            for job_id, connection_id in dead_jobs:
                key = int(connection_id) if connection_id is not None else None
                seen = seen_by_connection.get(key, 0)
                seen_by_connection[key] = seen + 1
                if seen >= keep_dead:
                    dead_delete_ids.append(int(job_id))

            if dead_delete_ids:
                await session.execute(
                    delete(HHSyncJob).where(HHSyncJob.id.in_(dead_delete_ids))
                )
            dead_deleted = len(dead_delete_ids)

    return {"done_deleted": done_deleted, "dead_deleted": dead_deleted}


def _iter_actions(actions_snapshot: dict[str, Any]) -> Iterable[dict[str, Any]]:
    actions = actions_snapshot.get("actions")
    if not isinstance(actions, list):
        return []
    return [action for action in actions if isinstance(action, dict)]


def _action_tokens(*parts: object) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        text = str(part or "").strip().lower()
        if not text:
            continue
        tokens.add(text)
        tokens.update(chunk for chunk in text.replace("-", "_").replace("/", "_").split("_") if chunk)
    return tokens


def _collect_action_markers(action: dict[str, Any]) -> set[str]:
    markers = set()
    markers.update(_action_tokens(action.get("id")))
    markers.update(_action_tokens(action.get("name")))
    markers.update(_action_tokens(action.get("url")))
    resulting = action.get("resulting_employer_state")
    if isinstance(resulting, dict):
        markers.update(_action_tokens(resulting.get("id")))
        markers.update(_action_tokens(resulting.get("name")))
    return markers


def _matches_action_intent(action: dict[str, Any], intent: str) -> bool:
    markers = _collect_action_markers(action)
    if intent == "invite_to_interview":
        return bool({"invite", "invitation", "interview"} & markers)
    if intent == "reject_candidate":
        return bool({"discard", "reject", "rejection", "decline", "refusal"} & markers)
    if intent == "mark_hired":
        return bool({"hired", "hire"} & markers)
    return False


def _pack_terminal_error(*, code: str, message: str, retryable: bool) -> RuntimeError:
    return RuntimeError(
        json.dumps(
            {
                "failure_code": code,
                "retryable": retryable,
                "result": {"code": code, "message": message},
            }
        )
    )


async def _load_identity_and_negotiation(
    session,
    *,
    candidate_id: int,
) -> tuple[CandidateExternalIdentity | None, HHNegotiation | None]:
    identity = (
        await session.execute(
            select(CandidateExternalIdentity).where(
                CandidateExternalIdentity.candidate_id == candidate_id,
                CandidateExternalIdentity.source == "hh",
            )
        )
    ).scalar_one_or_none()
    negotiation = None
    if identity is not None:
        negotiation = (
            await session.execute(
                select(HHNegotiation)
                .where(HHNegotiation.candidate_identity_id == identity.id)
                .order_by(HHNegotiation.updated_at.desc(), HHNegotiation.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    return identity, negotiation


async def _set_candidate_sync_state(
    session,
    *,
    candidate_id: int | None,
    sync_status: str,
    sync_error: str | None,
) -> None:
    if candidate_id is None:
        return
    candidate = await session.get(User, candidate_id)
    if candidate is None:
        return
    candidate.hh_sync_status = sync_status
    candidate.hh_sync_error = sync_error
    if sync_status == HHIdentitySyncStatus.SYNCED:
        candidate.hh_synced_at = _utcnow()


async def _refresh_negotiations_for_candidate(
    session,
    *,
    connection: HHConnection,
    vacancy_id: str | None,
) -> None:
    await import_hh_negotiations(
        session,
        connection=connection,
        client=HHApiClient(),
        vacancy_ids={vacancy_id} if vacancy_id else None,
        fetch_resume_details=False,
    )


async def _execute_outbound_candidate_status_job(
    session,
    *,
    job: HHSyncJob,
    connection: HHConnection | None,
) -> dict[str, Any]:
    payload = dict(job.payload_json or {})
    candidate_id = job.candidate_id or payload.get("candidate_id")
    if candidate_id is None:
        raise _pack_terminal_error(
            code=HHSyncFailureCode.IDENTITY_NOT_LINKED,
            message="Candidate id is missing for outbound HH sync",
            retryable=False,
        )

    identity, negotiation = await _load_identity_and_negotiation(session, candidate_id=int(candidate_id))
    if identity is None:
        await _set_candidate_sync_state(
            session,
            candidate_id=int(candidate_id),
            sync_status=HHIdentitySyncStatus.FAILED,
            sync_error=HHSyncFailureCode.IDENTITY_NOT_LINKED,
        )
        await session.commit()
        raise _pack_terminal_error(
            code=HHSyncFailureCode.IDENTITY_NOT_LINKED,
            message="Candidate is not linked to HH identity",
            retryable=False,
        )

    if connection is None and negotiation is not None and negotiation.connection_id is not None:
        connection = await session.get(HHConnection, negotiation.connection_id)
    if connection is None:
        raise _pack_terminal_error(
            code=HHSyncFailureCode.IDENTITY_NOT_LINKED,
            message="HH connection is missing for outbound sync",
            retryable=False,
        )

    try:
        await _refresh_negotiations_for_candidate(
            session,
            connection=connection,
            vacancy_id=identity.external_vacancy_id,
        )
    except HHApiError as exc:
        normalized = normalize_hh_api_error(exc)
        await _set_candidate_sync_state(
            session,
            candidate_id=int(candidate_id),
            sync_status=HHIdentitySyncStatus.FAILED,
            sync_error=normalized.code,
        )
        await session.commit()
        raise RuntimeError(
            json.dumps(
                {
                    "failure_code": normalized.code,
                    "retryable": normalized.retryable,
                    "result": {
                        "code": normalized.code,
                        "message": normalized.message,
                        "status_code": normalized.status_code,
                    },
                }
            )
        ) from exc

    identity, negotiation = await _load_identity_and_negotiation(session, candidate_id=int(candidate_id))
    if negotiation is None:
        await _set_candidate_sync_state(
            session,
            candidate_id=int(candidate_id),
            sync_status=HHIdentitySyncStatus.FAILED,
            sync_error=HHSyncFailureCode.WRONG_STATE,
        )
        await session.commit()
        raise _pack_terminal_error(
            code=HHSyncFailureCode.WRONG_STATE,
            message="HH negotiation is not available after refresh",
            retryable=False,
        )

    intent = str(payload.get("intent") or "").strip()
    actions = list(_iter_actions(negotiation.actions_snapshot if isinstance(negotiation.actions_snapshot, dict) else {}))
    matching_actions = [action for action in actions if _matches_action_intent(action, intent)]
    enabled_actions = [
        action
        for action in matching_actions
        if bool(action.get("enabled", True)) and not bool(action.get("hidden", False))
    ]

    if not matching_actions:
        await _set_candidate_sync_state(
            session,
            candidate_id=int(candidate_id),
            sync_status=HHIdentitySyncStatus.FAILED,
            sync_error=HHSyncFailureCode.ACTION_UNAVAILABLE,
        )
        await session.commit()
        raise _pack_terminal_error(
            code=HHSyncFailureCode.ACTION_UNAVAILABLE,
            message=f"No HH action matches intent {intent}",
            retryable=False,
        )
    if not enabled_actions:
        await _set_candidate_sync_state(
            session,
            candidate_id=int(candidate_id),
            sync_status=HHIdentitySyncStatus.FAILED,
            sync_error=HHSyncFailureCode.WRONG_STATE,
        )
        await session.commit()
        raise _pack_terminal_error(
            code=HHSyncFailureCode.WRONG_STATE,
            message=f"HH action exists for intent {intent} but is disabled",
            retryable=False,
        )

    action = enabled_actions[0]
    try:
        provider_payload = await HHApiClient().execute_negotiation_action(
            decrypt_access_token(connection),
            action_url=str(action.get("url") or "").strip(),
            method=str(action.get("method") or "POST").strip().upper(),
            manager_account_id=connection.manager_account_id,
            arguments=None,
        )
    except HHApiError as exc:
        normalized = normalize_hh_api_error(exc)
        await _set_candidate_sync_state(
            session,
            candidate_id=int(candidate_id),
            sync_status=HHIdentitySyncStatus.FAILED,
            sync_error=normalized.code,
        )
        await session.commit()
        raise RuntimeError(
            json.dumps(
                {
                    "failure_code": normalized.code,
                    "retryable": normalized.retryable,
                    "result": {
                        "code": normalized.code,
                        "message": normalized.message,
                        "status_code": normalized.status_code,
                    },
                }
            )
        ) from exc

    await _refresh_negotiations_for_candidate(
        session,
        connection=connection,
        vacancy_id=identity.external_vacancy_id if identity is not None else None,
    )
    await _set_candidate_sync_state(
        session,
        candidate_id=int(candidate_id),
        sync_status=HHIdentitySyncStatus.SYNCED,
        sync_error=None,
    )
    if identity is not None:
        identity.sync_status = HHIdentitySyncStatus.SYNCED
        identity.sync_error = None
        identity.last_hh_sync_at = _utcnow()

    return {
        "candidate_id": int(candidate_id),
        "intent": intent,
        "action_id": action.get("id"),
        "action_url": action.get("url"),
        "provider_payload": provider_payload,
    }


async def _execute_hh_sync_job(job_id: int) -> None:
    async with async_session() as session:
        job = await session.get(HHSyncJob, job_id)
        if job is None:
            return

        connection_id = job.connection_id
        connection = await session.get(HHConnection, connection_id) if connection_id else None
        payload = dict(job.payload_json or {})

        try:
            if job.job_type == "import_vacancies":
                if connection is None:
                    await _fail_job(
                        job_id,
                        error_message="HH connection is missing",
                        failure_code=HHSyncFailureCode.IDENTITY_NOT_LINKED,
                        retryable=False,
                    )
                    return
                result = await import_hh_vacancies(session, connection=connection, client=HHApiClient())
            elif job.job_type == "import_negotiations":
                if connection is None:
                    await _fail_job(
                        job_id,
                        error_message="HH connection is missing",
                        failure_code=HHSyncFailureCode.IDENTITY_NOT_LINKED,
                        retryable=False,
                    )
                    return
                vacancy_ids = {job.entity_external_id} if job.entity_external_id else None
                result = await import_hh_negotiations(
                    session,
                    connection=connection,
                    client=HHApiClient(),
                    vacancy_ids=vacancy_ids,
                    fetch_resume_details=bool(payload.get("fetch_resume_details", False)),
                )
            elif job.job_type == "sync_candidate_status":
                result = await _execute_outbound_candidate_status_job(
                    session,
                    job=job,
                    connection=connection,
                )
            else:
                raise RuntimeError(f"Unsupported HH sync job type: {job.job_type}")

            if connection is not None:
                connection.last_error = None
            await session.commit()
            if getattr(result, "candidate_ids_touched", None):
                schedule_warm_candidates_ai_outputs(result.candidate_ids_touched, refresh=True)
        except HHApiError as exc:
            normalized = normalize_hh_api_error(exc)
            await session.rollback()
            await _record_connection_failure(
                connection_id=connection_id,
                normalized_error=normalized,
            )
            await _fail_job(
                job_id,
                error_message=normalized.message,
                failure_code=normalized.code,
                retryable=normalized.retryable,
                result_payload={
                    "code": normalized.code,
                    "message": normalized.message,
                    "status_code": normalized.status_code,
                },
                retry_after_seconds=normalized.retry_after_seconds,
            )
            return
        except Exception as exc:
            await session.rollback()
            failure_code = HHSyncFailureCode.PROVIDER_HTTP_ERROR
            retryable = True
            result_payload = None
            error_message = str(exc)
            try:
                parsed = json.loads(str(exc))
                if isinstance(parsed, dict) and "failure_code" in parsed:
                    failure_code = str(parsed.get("failure_code") or failure_code)
                    retryable = bool(parsed.get("retryable", False))
                    result_payload = parsed.get("result") if isinstance(parsed.get("result"), dict) else None
                    error_message = str((result_payload or {}).get("message") or error_message)
            except Exception:
                pass
            await _fail_job(
                job_id,
                error_message=error_message,
                failure_code=failure_code,
                retryable=retryable,
                result_payload=result_payload,
            )
            return

    await _complete_job(
        job_id,
        result_payload=serialize_import_result(result) if hasattr(result, "__dataclass_fields__") else result,
    )


async def process_pending_hh_sync_jobs(*, batch_size: int = 1) -> int:
    claimed = await _claim_hh_sync_jobs(batch_size)
    for job_id in claimed:
        try:
            await _execute_hh_sync_job(job_id)
        except Exception:
            logger.exception("hh.sync.worker.unhandled_failure", extra={"job_id": job_id})
            await _fail_job(
                job_id,
                error_message="Unhandled HH sync worker failure",
                failure_code=HHSyncFailureCode.PROVIDER_HTTP_ERROR,
                retryable=True,
                result_payload={
                    "code": HHSyncFailureCode.PROVIDER_HTTP_ERROR,
                    "message": "Unhandled HH sync worker failure",
                },
            )
    return len(claimed)


__all__ = [
    "enqueue_hh_sync_job",
    "cleanup_hh_sync_jobs",
    "count_hh_sync_jobs_by_status",
    "list_hh_sync_jobs",
    "process_pending_hh_sync_jobs",
    "retry_hh_sync_job",
    "serialize_hh_sync_job",
]
