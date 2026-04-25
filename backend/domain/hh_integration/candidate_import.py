"""Candidate-side HH OAuth resume import helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.core.ai.llm_script_generator import (
    hash_resume_content,
    normalize_hh_resume,
)
from backend.domain.ai.models import CandidateHHResume
from backend.domain.candidates.models import User, normalize_candidate_phone
from backend.domain.hh_integration.contracts import HHIdentitySyncStatus
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    HHResumeSnapshot,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CandidateHHIdentityConflict(RuntimeError):
    """The HH resume is already linked to another candidate."""


@dataclass(frozen=True)
class CandidateHHImportResult:
    verified: bool
    resume_imported: bool
    resume_id: str | None
    resume_url: str | None
    title: str | None
    city: str | None
    phone_imported: bool
    contact_available: bool
    sync_status: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_hh_datetime(value: Any) -> datetime | None:
    text = _string(value)
    if not text:
        return None
    normalized = text
    if len(text) >= 5 and text[-5] in {"+", "-"} and text[-3] != ":":
        normalized = f"{text[:-2]}:{text[-2:]}"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _resume_id(payload: dict[str, Any]) -> str | None:
    return _string(payload.get("id"))


def _resume_url(payload: dict[str, Any]) -> str | None:
    return _string(payload.get("alternate_url")) or _string(payload.get("url"))


def _resume_title(payload: dict[str, Any]) -> str | None:
    for key in ("title", "position", "desired_position", "headline"):
        value = _string(payload.get(key))
        if value:
            return value[:120]
    return None


def _resume_city(payload: dict[str, Any]) -> str | None:
    area = payload.get("area")
    if isinstance(area, dict):
        return _string(area.get("name"))
    return None


def _resume_full_name(payload: dict[str, Any]) -> str | None:
    full_name = _string(payload.get("full_name"))
    if full_name:
        return full_name[:160]
    parts = [
        _string(payload.get("last_name")),
        _string(payload.get("first_name")),
        _string(payload.get("middle_name")),
    ]
    text = " ".join(part for part in parts if part)
    return text[:160] if text else None


def _resume_phone(payload: dict[str, Any]) -> str | None:
    for key in ("phone", "contact_phone"):
        phone = normalize_candidate_phone(payload.get(key))
        if phone:
            return phone
    phones = payload.get("phones")
    if isinstance(phones, list):
        for item in phones:
            if not isinstance(item, dict):
                continue
            phone = normalize_candidate_phone(
                item.get("formatted") or item.get("number") or item.get("value")
            )
            if phone:
                return phone
    contacts = payload.get("contact")
    if isinstance(contacts, list):
        for item in contacts:
            if not isinstance(item, dict):
                continue
            phone = normalize_candidate_phone(
                item.get("formatted") or item.get("number") or item.get("value")
            )
            if phone:
                return phone
    return None


def _is_placeholder_name(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return normalized in {
        "browser candidate",
        "candidate",
        "кандидат",
    } or normalized.startswith(("hh candidate", "кандидат "))


async def is_candidate_hh_verified(session: AsyncSession, candidate_id: int) -> bool:
    candidate = await session.get(User, int(candidate_id))
    if candidate is None:
        return False
    if _string(candidate.hh_resume_id):
        return True
    identity = await session.scalar(
        select(CandidateExternalIdentity).where(
            CandidateExternalIdentity.candidate_id == int(candidate_id),
            CandidateExternalIdentity.source == "hh",
        )
    )
    if identity is None:
        return False
    return identity.sync_status not in {
        HHIdentitySyncStatus.FAILED,
        HHIdentitySyncStatus.CONFLICTED,
    }


def candidate_has_hh_contact(candidate: User) -> bool:
    return bool(_string(candidate.phone_normalized) or _string(candidate.phone))


async def _assert_resume_not_linked_to_other_candidate(
    session: AsyncSession,
    *,
    candidate_id: int,
    resume_id: str | None,
) -> None:
    if not resume_id:
        return
    existing_identity = await session.scalar(
        select(CandidateExternalIdentity)
        .where(
            CandidateExternalIdentity.source == "hh",
            CandidateExternalIdentity.external_resume_id == resume_id,
            CandidateExternalIdentity.candidate_id != int(candidate_id),
        )
        .limit(1)
    )
    if existing_identity is not None:
        raise CandidateHHIdentityConflict("hh_resume_linked_to_another_candidate")

    existing_snapshot = await session.scalar(
        select(HHResumeSnapshot)
        .where(
            HHResumeSnapshot.external_resume_id == resume_id,
            HHResumeSnapshot.candidate_id.is_not(None),
            HHResumeSnapshot.candidate_id != int(candidate_id),
        )
        .limit(1)
    )
    if existing_snapshot is not None:
        raise CandidateHHIdentityConflict("hh_resume_snapshot_belongs_to_another_candidate")


async def upsert_candidate_hh_identity(
    session: AsyncSession,
    *,
    candidate: User,
    me_payload: dict[str, Any] | None,
    resume_payload: dict[str, Any] | None = None,
) -> CandidateHHImportResult:
    now = _utcnow()
    resume_payload = resume_payload if isinstance(resume_payload, dict) else None
    resume_id = _resume_id(resume_payload or {})
    resume_url = _resume_url(resume_payload or {})
    title = _resume_title(resume_payload or {})
    city = _resume_city(resume_payload or {})
    full_name = _resume_full_name(resume_payload or {})
    phone = _resume_phone(resume_payload or {})
    await _assert_resume_not_linked_to_other_candidate(
        session,
        candidate_id=int(candidate.id),
        resume_id=resume_id,
    )

    identity = await session.scalar(
        select(CandidateExternalIdentity).where(
            CandidateExternalIdentity.candidate_id == int(candidate.id),
            CandidateExternalIdentity.source == "hh",
        )
    )
    if identity is None:
        identity = CandidateExternalIdentity(
            candidate_id=int(candidate.id),
            source="hh",
            payload_snapshot={},
        )
        session.add(identity)

    identity.external_resume_id = resume_id or identity.external_resume_id
    identity.external_resume_url = resume_url or identity.external_resume_url
    identity.sync_status = HHIdentitySyncStatus.SYNCED if resume_id else HHIdentitySyncStatus.LINKED
    identity.sync_error = None
    identity.last_hh_sync_at = now
    identity.payload_snapshot = {
        "verified_by": "candidate_oauth",
        "has_resume": bool(resume_id),
        "me_id": _string((me_payload or {}).get("id")),
    }

    phone_imported = False
    if full_name and _is_placeholder_name(candidate.fio):
        candidate.fio = full_name
    if city and not _string(candidate.city):
        candidate.city = city
    if title and not _string(candidate.desired_position):
        candidate.desired_position = title
    if phone and not candidate_has_hh_contact(candidate):
        candidate.phone = phone
        phone_imported = True

    candidate.hh_resume_id = resume_id or candidate.hh_resume_id
    candidate.hh_synced_at = now
    candidate.hh_sync_status = "success" if resume_id else "no_resume"
    candidate.hh_sync_error = None
    candidate.last_activity = now

    if resume_id and resume_payload is not None:
        content_hash = hash_resume_content(
            format="json",
            resume_json=resume_payload,
            resume_text=None,
        )
        snapshot = await session.scalar(
            select(HHResumeSnapshot).where(HHResumeSnapshot.external_resume_id == resume_id)
        )
        if snapshot is None:
            snapshot = HHResumeSnapshot(
                candidate_id=int(candidate.id),
                external_resume_id=resume_id,
            )
            session.add(snapshot)
        snapshot.candidate_id = int(candidate.id)
        snapshot.source_updated_at = _parse_hh_datetime(
            resume_payload.get("updated_at") or resume_payload.get("created_at")
        )
        snapshot.content_hash = content_hash
        snapshot.payload_json = resume_payload
        snapshot.fetched_at = now

        normalized = normalize_hh_resume(
            format="json",
            resume_json=resume_payload,
            resume_text=None,
        )
        candidate_resume = await session.scalar(
            select(CandidateHHResume).where(CandidateHHResume.candidate_id == int(candidate.id))
        )
        if candidate_resume is None:
            candidate_resume = CandidateHHResume(candidate_id=int(candidate.id))
            session.add(candidate_resume)
        candidate_resume.format = "json"
        candidate_resume.resume_json = resume_payload
        candidate_resume.resume_text = None
        candidate_resume.normalized_json = normalized
        candidate_resume.content_hash = content_hash
        candidate_resume.source_quality_ok = bool(normalized.get("source_quality_ok", True))
        candidate_resume.updated_at = now

    await session.flush()
    return CandidateHHImportResult(
        verified=True,
        resume_imported=bool(resume_id),
        resume_id=resume_id,
        resume_url=resume_url,
        title=title,
        city=city,
        phone_imported=phone_imported,
        contact_available=candidate_has_hh_contact(candidate),
        sync_status=str(candidate.hh_sync_status or identity.sync_status),
    )


__all__ = [
    "CandidateHHIdentityConflict",
    "CandidateHHImportResult",
    "candidate_has_hh_contact",
    "is_candidate_hh_verified",
    "upsert_candidate_hh_identity",
]
