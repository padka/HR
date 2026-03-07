"""Queue and worker helpers for HH integration sync jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.core.db import async_session
from backend.domain.hh_integration.client import HHApiClient, HHApiError
from backend.domain.hh_integration.contracts import HHSyncDirection, HHSyncJobStatus
from backend.domain.hh_integration.importer import (
    import_hh_negotiations,
    import_hh_vacancies,
    serialize_import_result,
)
from backend.domain.hh_integration.models import HHConnection, HHSyncJob
from sqlalchemy import and_, or_, select

logger = logging.getLogger(__name__)

_JOB_RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))
_RUNNING_STALE_AFTER = timedelta(minutes=15)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def serialize_hh_sync_job(job: HHSyncJob) -> dict[str, object]:
    return {
        "id": job.id,
        "connection_id": job.connection_id,
        "job_type": job.job_type,
        "direction": job.direction,
        "entity_type": job.entity_type,
        "entity_external_id": job.entity_external_id,
        "status": job.status,
        "attempts": job.attempts,
        "payload": dict(job.payload_json or {}),
        "last_error": job.last_error,
        "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


async def enqueue_hh_sync_job(
    session,
    *,
    connection: HHConnection,
    job_type: str,
    entity_type: str | None = None,
    entity_external_id: str | None = None,
    payload_json: dict | None = None,
    direction: str = HHSyncDirection.INBOUND,
) -> tuple[HHSyncJob, bool]:
    payload = dict(payload_json or {})
    signature = [
        HHSyncJob.connection_id == connection.id,
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
        connection_id=connection.id,
        job_type=job_type,
        direction=direction,
        entity_type=entity_type,
        entity_external_id=entity_external_id,
        status=HHSyncJobStatus.PENDING,
        idempotency_key=uuid4().hex,
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
            job.status = HHSyncJobStatus.DONE
            job.last_error = None
            job.next_retry_at = None
            job.finished_at = _utcnow()


async def _fail_job(job_id: int, *, error_message: str) -> None:
    async with async_session() as session:
        async with session.begin():
            job = await session.get(HHSyncJob, job_id, with_for_update=True)
            if job is None:
                return
            attempts = max(int(job.attempts or 0), 1)
            job.last_error = error_message
            job.finished_at = _utcnow()
            if attempts >= len(_JOB_RETRY_DELAYS) + 1:
                job.status = HHSyncJobStatus.DEAD
                job.next_retry_at = None
            else:
                job.status = HHSyncJobStatus.PENDING
                job.next_retry_at = _utcnow() + _JOB_RETRY_DELAYS[min(attempts - 1, len(_JOB_RETRY_DELAYS) - 1)]


async def _execute_hh_sync_job(job_id: int) -> None:
    async with async_session() as session:
        job = await session.get(HHSyncJob, job_id)
        if job is None:
            return
        connection = await session.get(HHConnection, job.connection_id) if job.connection_id else None
        if connection is None:
            await _fail_job(job_id, error_message="HH connection is missing")
            return

        client = HHApiClient()
        payload = dict(job.payload_json or {})
        try:
            if job.job_type == "import_vacancies":
                result = await import_hh_vacancies(session, connection=connection, client=client)
            elif job.job_type == "import_negotiations":
                vacancy_ids = {job.entity_external_id} if job.entity_external_id else None
                result = await import_hh_negotiations(
                    session,
                    connection=connection,
                    client=client,
                    vacancy_ids=vacancy_ids,
                    fetch_resume_details=bool(payload.get("fetch_resume_details", False)),
                )
            else:
                raise RuntimeError(f"Unsupported HH sync job type: {job.job_type}")
            connection.last_error = None
            await session.commit()
        except HHApiError as exc:
            async with session.begin():
                connection.last_error = str(exc)
            await _fail_job(job_id, error_message=str(exc))
            return
        except Exception as exc:
            await _fail_job(job_id, error_message=str(exc))
            return

    await _complete_job(job_id, result_payload=serialize_import_result(result))


async def process_pending_hh_sync_jobs(*, batch_size: int = 1) -> int:
    claimed = await _claim_hh_sync_jobs(batch_size)
    for job_id in claimed:
        try:
            await _execute_hh_sync_job(job_id)
        except Exception:
            logger.exception("hh.sync.worker.unhandled_failure", extra={"job_id": job_id})
            await _fail_job(job_id, error_message="Unhandled HH sync worker failure")
    return len(claimed)


__all__ = [
    "enqueue_hh_sync_job",
    "list_hh_sync_jobs",
    "process_pending_hh_sync_jobs",
    "retry_hh_sync_job",
    "serialize_hh_sync_job",
]
