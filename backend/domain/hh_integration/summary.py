"""Read models for HH-linked candidate summaries."""

from __future__ import annotations

from typing import Any

from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    ExternalVacancyBinding,
    HHNegotiation,
    HHResumeSnapshot,
    HHSyncJob,
)
from sqlalchemy import desc, or_, select


def _serialize_hh_action(action: dict[str, Any]) -> dict[str, Any]:
    resulting = action.get("resulting_employer_state")
    return {
        "id": action.get("id"),
        "name": action.get("name"),
        "method": action.get("method"),
        "enabled": bool(action.get("enabled", True)),
        "hidden": bool(action.get("hidden", False)),
        "resulting_employer_state": resulting if isinstance(resulting, dict) else {},
    }


def _resume_title(snapshot_payload: dict[str, Any]) -> str | None:
    for key in ("title", "position", "desired_position"):
        value = snapshot_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resume_updated_at(snapshot_payload: dict[str, Any]) -> str | None:
    value = snapshot_payload.get("updated_at") or snapshot_payload.get("updated")
    return value if isinstance(value, str) and value.strip() else None


async def build_candidate_hh_summary(session, *, candidate_id: int) -> dict[str, Any]:
    identity = (
        await session.execute(
            select(CandidateExternalIdentity).where(
                CandidateExternalIdentity.candidate_id == candidate_id,
                CandidateExternalIdentity.source == "hh",
            )
        )
    ).scalar_one_or_none()
    if identity is None:
        return {"linked": False, "source": "hh"}

    negotiation = (
        await session.execute(
            select(HHNegotiation)
            .where(HHNegotiation.candidate_identity_id == identity.id)
            .order_by(desc(HHNegotiation.updated_at), desc(HHNegotiation.id))
            .limit(1)
        )
    ).scalar_one_or_none()
    vacancy_binding = None
    if identity.external_vacancy_id:
        vacancy_binding = (
            await session.execute(
                select(ExternalVacancyBinding)
                .where(
                    ExternalVacancyBinding.source == "hh",
                    ExternalVacancyBinding.external_vacancy_id == identity.external_vacancy_id,
                )
                .order_by(desc(ExternalVacancyBinding.updated_at), desc(ExternalVacancyBinding.id))
                .limit(1)
            )
        ).scalar_one_or_none()

    resume_snapshot = None
    if identity.external_resume_id:
        resume_snapshot = (
            await session.execute(
                select(HHResumeSnapshot)
                .where(HHResumeSnapshot.external_resume_id == identity.external_resume_id)
                .order_by(desc(HHResumeSnapshot.fetched_at), desc(HHResumeSnapshot.id))
                .limit(1)
            )
        ).scalar_one_or_none()

    action_items: list[dict[str, Any]] = []
    if negotiation and isinstance(negotiation.actions_snapshot, dict):
        actions = negotiation.actions_snapshot.get("actions")
        if isinstance(actions, list):
            action_items = [
                _serialize_hh_action(action)
                for action in actions
                if isinstance(action, dict) and not bool(action.get("hidden", False))
            ]

    connection_id = None
    if negotiation and negotiation.connection_id:
        connection_id = negotiation.connection_id
    elif vacancy_binding and vacancy_binding.connection_id:
        connection_id = vacancy_binding.connection_id

    recent_jobs: list[dict[str, Any]] = []
    if connection_id is not None:
        entity_ids = [
            value
            for value in (
                identity.external_negotiation_id,
                identity.external_vacancy_id,
                identity.external_resume_id,
            )
            if value
        ]
        stmt = select(HHSyncJob).where(HHSyncJob.connection_id == connection_id)
        if entity_ids:
            stmt = stmt.where(
                or_(
                    HHSyncJob.entity_external_id.in_(entity_ids),
                    HHSyncJob.entity_external_id == identity.external_vacancy_id,
                )
            )
        jobs = (
            await session.execute(stmt.order_by(desc(HHSyncJob.id)).limit(5))
        ).scalars().all()
        recent_jobs = [
            {
                "id": job.id,
                "job_type": job.job_type,
                "status": job.status,
                "attempts": job.attempts,
                "last_error": job.last_error,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in jobs
        ]

    resume_payload = resume_snapshot.payload_json if resume_snapshot and isinstance(resume_snapshot.payload_json, dict) else {}
    vacancy_payload = vacancy_binding.payload_snapshot if vacancy_binding and isinstance(vacancy_binding.payload_snapshot, dict) else {}

    return {
        "linked": True,
        "source": "hh",
        "sync_status": identity.sync_status,
        "sync_error": identity.sync_error,
        "last_hh_sync_at": identity.last_hh_sync_at.isoformat() if identity.last_hh_sync_at else None,
        "resume": {
            "id": identity.external_resume_id,
            "url": identity.external_resume_url or (f"https://hh.ru/resume/{identity.external_resume_id}" if identity.external_resume_id else None),
            "title": _resume_title(resume_payload),
            "source_updated_at": _resume_updated_at(resume_payload),
            "fetched_at": resume_snapshot.fetched_at.isoformat() if resume_snapshot and resume_snapshot.fetched_at else None,
        },
        "vacancy": {
            "id": identity.external_vacancy_id,
            "title": vacancy_binding.title_snapshot if vacancy_binding else None,
            "url": vacancy_binding.external_url if vacancy_binding else None,
            "last_hh_sync_at": vacancy_binding.last_hh_sync_at.isoformat()
            if vacancy_binding and vacancy_binding.last_hh_sync_at
            else None,
            "area_name": vacancy_payload.get("area", {}).get("name") if isinstance(vacancy_payload.get("area"), dict) else None,
        },
        "negotiation": {
            "id": identity.external_negotiation_id,
            "collection_name": negotiation.collection_name if negotiation else None,
            "employer_state": negotiation.employer_state if negotiation else None,
            "applicant_state": negotiation.applicant_state if negotiation else None,
            "last_hh_sync_at": negotiation.last_hh_sync_at.isoformat()
            if negotiation and negotiation.last_hh_sync_at
            else None,
        },
        "available_actions": action_items,
        "recent_jobs": recent_jobs,
    }


__all__ = ["build_candidate_hh_summary"]
