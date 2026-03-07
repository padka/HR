"""Import services for direct HH integration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.domain.candidates.models import User
from backend.domain.hh_integration.client import HHApiClient, HHApiError
from backend.domain.hh_integration.contracts import HHIdentitySyncStatus
from backend.domain.hh_integration.models import (
    CandidateExternalIdentity,
    ExternalVacancyBinding,
    HHConnection,
    HHNegotiation,
    HHResumeSnapshot,
)
from backend.domain.hh_integration.service import decrypt_access_token
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

_NON_DIGIT_RE = re.compile(r"\D+")
_COLLECTION_QUERY_KEEP = {"vacancy_id", "status", "has_updates"}
_COLLECTION_PATH_SKIP_PREFIXES = (
    "/negotiations/vacancy_visitors",
    "/negotiations/relevant_responses",
    "/negotiations/phone_calls",
    "/negotiations/by_location",
)


@dataclass(frozen=True)
class HHVacancyImportResult:
    total_seen: int
    created: int
    updated: int


@dataclass(frozen=True)
class HHNegotiationImportResult:
    collections_seen: int
    negotiations_seen: int
    negotiations_created: int
    negotiations_updated: int
    candidates_created: int
    candidates_linked: int
    resumes_upserted: int


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


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_phone(value: Any) -> str | None:
    text = _string(value)
    if not text:
        return None
    digits = _NON_DIGIT_RE.sub("", text)
    return digits or None


def _resume_snippet(item: dict[str, Any]) -> dict[str, Any]:
    resume = item.get("resume")
    return resume if isinstance(resume, dict) else {}


def _extract_resume_id(item: dict[str, Any], resume_payload: dict[str, Any]) -> str | None:
    for source in (_resume_snippet(item), resume_payload, item):
        value = _string(source.get("id")) if isinstance(source, dict) else None
        if value:
            return value
    return None


def _extract_vacancy_id(item: dict[str, Any]) -> str | None:
    vacancy = item.get("vacancy")
    if isinstance(vacancy, dict):
        value = _string(vacancy.get("id"))
        if value:
            return value
    return _string(item.get("vacancy_id"))


def _extract_vacancy_id_from_collection_url(collection_url: str) -> str | None:
    parts = urlsplit(collection_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    return _string(query.get("vacancy_id"))


def _extract_resume_url(item: dict[str, Any], resume_payload: dict[str, Any]) -> str | None:
    snippet = _resume_snippet(item)
    for source in (resume_payload, snippet):
        for key in ("alternate_url", "url"):
            value = _string(source.get(key)) if isinstance(source, dict) else None
            if value:
                return value
    return None


def _extract_fio(item: dict[str, Any], resume_payload: dict[str, Any], *, resume_id: str | None) -> str:
    candidates: list[dict[str, Any]] = [resume_payload, _resume_snippet(item), item]
    for source in candidates:
        if not isinstance(source, dict):
            continue
        full_name = _string(source.get("full_name"))
        if full_name:
            return full_name
        parts = [
            _string(source.get("last_name")),
            _string(source.get("first_name")),
            _string(source.get("middle_name")),
        ]
        text = " ".join(part for part in parts if part)
        if text:
            return text
    return f"HH candidate {resume_id or 'unknown'}"


def _extract_city(item: dict[str, Any], resume_payload: dict[str, Any]) -> str | None:
    for source in (resume_payload, _resume_snippet(item)):
        if not isinstance(source, dict):
            continue
        area = source.get("area")
        if isinstance(area, dict):
            name = _string(area.get("name"))
            if name:
                return name
    return None


def _extract_position(item: dict[str, Any], resume_payload: dict[str, Any]) -> str | None:
    for source in (resume_payload, _resume_snippet(item)):
        if not isinstance(source, dict):
            continue
        value = _string(source.get("title"))
        if value:
            return value
    return None


def _extract_phone(item: dict[str, Any], resume_payload: dict[str, Any]) -> str | None:
    for source in (resume_payload, _resume_snippet(item)):
        if not isinstance(source, dict):
            continue
        for key in ("phone", "contact_phone"):
            phone = _normalize_phone(source.get(key))
            if phone:
                return phone
        phones = source.get("phones")
        if isinstance(phones, list):
            for phone_item in phones:
                if isinstance(phone_item, dict):
                    phone = _normalize_phone(
                        phone_item.get("formatted")
                        or phone_item.get("number")
                        or phone_item.get("value")
                    )
                    if phone:
                        return phone
    return None


def _extract_collection_refs(payload: dict[str, Any]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []

    def normalize_collection_url(raw_url: str) -> str:
        parts = urlsplit(raw_url)
        if any(parts.path.startswith(prefix) for prefix in _COLLECTION_PATH_SKIP_PREFIXES):
            return ""
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        filtered = {key: value for key, value in query.items() if key in _COLLECTION_QUERY_KEEP}
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(sorted(filtered.items())),
                parts.fragment,
            )
        )

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        counters = node.get("counters")
        if isinstance(counters, dict):
            total = counters.get("total")
            try:
                if total is not None and int(total) <= 0:
                    return
            except (TypeError, ValueError):
                pass
        collection_id = _string(node.get("id"))
        collection_url = _string(node.get("url"))
        if collection_id and collection_url and "/negotiations/" in collection_url:
            normalized_url = normalize_collection_url(collection_url)
            if normalized_url:
                refs.append((collection_id, normalized_url))
        for value in node.values():
            if isinstance(value, (list, dict)):
                walk(value)

    for key in ("collections", "generated_collections"):
        walk(payload.get(key))

    seen_urls: set[str] = set()
    unique: list[tuple[str, str]] = []
    for collection_id, collection_url in refs:
        if collection_url in seen_urls:
            continue
        seen_urls.add(collection_url)
        unique.append((collection_id, collection_url))
    return unique


async def _find_candidate_by_phone(session: AsyncSession, phone: str | None) -> User | None:
    if not phone:
        return None
    result = await session.execute(select(User).where(User.phone.is_not(None)))
    for user in result.scalars():
        if _normalize_phone(user.phone) == phone:
            return user
    return None


async def _find_candidate_for_resume(
    session: AsyncSession,
    *,
    resume_id: str | None,
    negotiation_id: str | None,
    normalized_phone: str | None,
) -> User | None:
    filters = []
    if resume_id:
        filters.append(CandidateExternalIdentity.external_resume_id == resume_id)
        filters.append(User.hh_resume_id == resume_id)
    if negotiation_id:
        filters.append(CandidateExternalIdentity.external_negotiation_id == negotiation_id)
        filters.append(User.hh_negotiation_id == negotiation_id)

    if filters:
        identity_result = await session.execute(
            select(User)
            .join(CandidateExternalIdentity, CandidateExternalIdentity.candidate_id == User.id, isouter=True)
            .where(or_(*filters))
            .limit(1)
        )
        candidate = identity_result.scalar_one_or_none()
        if candidate is not None:
            return candidate

    return await _find_candidate_by_phone(session, normalized_phone)


async def _upsert_candidate_identity(
    session: AsyncSession,
    *,
    candidate: User,
    connection: HHConnection,
    resume_id: str | None,
    negotiation_id: str | None,
    vacancy_id: str | None,
    resume_url: str | None,
    payload_snapshot: dict[str, Any],
) -> CandidateExternalIdentity:
    result = await session.execute(
        select(CandidateExternalIdentity).where(
            CandidateExternalIdentity.candidate_id == candidate.id,
            CandidateExternalIdentity.source == "hh",
        )
    )
    identity = result.scalar_one_or_none()
    if identity is None:
        identity = CandidateExternalIdentity(candidate_id=candidate.id, source="hh", payload_snapshot={})
        session.add(identity)

    identity.external_resume_id = resume_id or identity.external_resume_id
    identity.external_negotiation_id = negotiation_id or identity.external_negotiation_id
    identity.external_vacancy_id = vacancy_id or identity.external_vacancy_id
    identity.external_employer_id = connection.employer_id
    identity.external_manager_id = connection.manager_id
    identity.external_resume_url = resume_url or identity.external_resume_url
    identity.sync_status = HHIdentitySyncStatus.SYNCED
    identity.sync_error = None
    identity.last_hh_sync_at = _utcnow()
    identity.payload_snapshot = payload_snapshot
    await session.flush()
    return identity


async def import_hh_vacancies(
    session: AsyncSession,
    *,
    connection: HHConnection,
    client: HHApiClient,
    page_size: int = 50,
    max_pages: int = 10,
) -> HHVacancyImportResult:
    if not connection.employer_id:
        raise ValueError("HH connection does not have employer_id")

    access_token = decrypt_access_token(connection)
    total_seen = created = updated = 0
    page = 0
    now = _utcnow()

    while page < max_pages:
        payload = await client.list_vacancies(
            access_token,
            employer_id=connection.employer_id,
            manager_account_id=connection.manager_account_id,
            page=page,
            per_page=page_size,
        )
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            break
        total_seen += len(items)
        for item in items:
            if not isinstance(item, dict):
                continue
            external_vacancy_id = _string(item.get("id"))
            if not external_vacancy_id:
                continue
            result = await session.execute(
                select(ExternalVacancyBinding).where(
                    ExternalVacancyBinding.source == "hh",
                    ExternalVacancyBinding.external_vacancy_id == external_vacancy_id,
                )
            )
            binding = result.scalar_one_or_none()
            if binding is None:
                binding = ExternalVacancyBinding(
                    vacancy_id=None,
                    connection_id=connection.id,
                    source="hh",
                    external_vacancy_id=external_vacancy_id,
                )
                session.add(binding)
                created += 1
            else:
                updated += 1

            binding.connection_id = connection.id
            binding.external_employer_id = connection.employer_id
            binding.external_manager_account_id = connection.manager_account_id
            binding.external_url = _string(item.get("alternate_url")) or _string(item.get("url"))
            binding.title_snapshot = _string(item.get("name"))
            binding.payload_snapshot = item
            binding.last_hh_sync_at = now

        pages = int(payload.get("pages") or 0)
        page += 1
        if pages and page >= pages:
            break

    connection.last_sync_at = now
    connection.last_error = None
    await session.flush()
    return HHVacancyImportResult(total_seen=total_seen, created=created, updated=updated)


async def import_hh_negotiations(
    session: AsyncSession,
    *,
    connection: HHConnection,
    client: HHApiClient,
    vacancy_ids: set[str] | None = None,
    page_size: int = 20,
    max_pages_per_collection: int = 5,
    fetch_resume_details: bool = True,
) -> HHNegotiationImportResult:
    access_token = decrypt_access_token(connection)
    vacancy_bindings = (
        await session.execute(
            select(ExternalVacancyBinding).where(
                ExternalVacancyBinding.source == "hh",
                ExternalVacancyBinding.connection_id == connection.id,
                ExternalVacancyBinding.external_vacancy_id.is_not(None),
            )
        )
    ).scalars().all()
    if vacancy_ids:
        vacancy_bindings = [
            binding
            for binding in vacancy_bindings
            if _string(binding.external_vacancy_id) in vacancy_ids
        ]
    collections: list[tuple[str, str]] = []
    seen_collection_urls: set[str] = set()
    resume_payload_cache: dict[str, dict[str, Any]] = {}
    for binding in vacancy_bindings:
        vacancy_id = _string(binding.external_vacancy_id)
        if not vacancy_id:
            continue
        collections_payload = await client.list_negotiation_collections(
            access_token,
            manager_account_id=connection.manager_account_id,
            vacancy_id=vacancy_id,
            with_generated_collections=True,
        )
        for collection in _extract_collection_refs(collections_payload):
            if collection[1] in seen_collection_urls:
                continue
            seen_collection_urls.add(collection[1])
            collections.append(collection)
    now = _utcnow()

    negotiations_seen = 0
    negotiations_created = 0
    negotiations_updated = 0
    candidates_created = 0
    candidates_linked = 0
    resumes_upserted = 0

    for collection_id, collection_url in collections:
        collection_vacancy_id = _extract_vacancy_id_from_collection_url(collection_url)
        page = 0
        while page < max_pages_per_collection:
            payload = await client.list_negotiations_collection(
                access_token,
                collection_url=collection_url,
                manager_account_id=connection.manager_account_id,
                page=page,
                per_page=page_size,
            )
            items = payload.get("items")
            if not isinstance(items, list) or not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue
                negotiations_seen += 1
                negotiation_id = _string(item.get("id"))
                if not negotiation_id:
                    continue

                resume_payload: dict[str, Any] = {}
                if fetch_resume_details:
                    resume_info = _resume_snippet(item)
                    resume_id = _string(resume_info.get("id"))
                    resume_url = _string(resume_info.get("url"))
                    if resume_id or resume_url:
                        cache_key = resume_url or f"resume:{resume_id}"
                        if cache_key in resume_payload_cache:
                            resume_payload = resume_payload_cache[cache_key]
                        else:
                            try:
                                resume_payload = await client.get_resume(
                                    access_token,
                                    resume_id=resume_id,
                                    resume_url=resume_url,
                                    manager_account_id=connection.manager_account_id,
                                )
                            except HHApiError:
                                resume_payload = {}
                            resume_payload_cache[cache_key] = resume_payload

                resume_id = _extract_resume_id(item, resume_payload)
                vacancy_id = _extract_vacancy_id(item) or collection_vacancy_id
                normalized_phone = _extract_phone(item, resume_payload)
                candidate = await _find_candidate_for_resume(
                    session,
                    resume_id=resume_id,
                    negotiation_id=negotiation_id,
                    normalized_phone=normalized_phone,
                )
                if candidate is None:
                    candidate = User(
                        fio=_extract_fio(item, resume_payload, resume_id=resume_id),
                        phone=normalized_phone,
                        city=_extract_city(item, resume_payload),
                        desired_position=_extract_position(item, resume_payload),
                        source="hh",
                        hh_resume_id=resume_id,
                        hh_negotiation_id=negotiation_id,
                        hh_vacancy_id=vacancy_id,
                        hh_synced_at=now,
                        hh_sync_status=HHIdentitySyncStatus.SYNCED,
                    )
                    session.add(candidate)
                    await session.flush()
                    candidates_created += 1
                else:
                    candidate.hh_resume_id = resume_id or candidate.hh_resume_id
                    candidate.hh_negotiation_id = negotiation_id or candidate.hh_negotiation_id
                    candidate.hh_vacancy_id = vacancy_id or candidate.hh_vacancy_id
                    candidate.hh_synced_at = now
                    candidate.hh_sync_status = HHIdentitySyncStatus.SYNCED
                    candidate.hh_sync_error = None
                    candidates_linked += 1

                identity = await _upsert_candidate_identity(
                    session,
                    candidate=candidate,
                    connection=connection,
                    resume_id=resume_id,
                    negotiation_id=negotiation_id,
                    vacancy_id=vacancy_id,
                    resume_url=_extract_resume_url(item, resume_payload),
                    payload_snapshot={"negotiation": item, "resume": resume_payload},
                )

                result = await session.execute(
                    select(HHNegotiation).where(HHNegotiation.external_negotiation_id == negotiation_id)
                )
                record = result.scalar_one_or_none()
                if record is None:
                    record = HHNegotiation(
                        connection_id=connection.id,
                        candidate_identity_id=identity.id,
                        external_negotiation_id=negotiation_id,
                    )
                    session.add(record)
                    negotiations_created += 1
                else:
                    negotiations_updated += 1

                record.connection_id = connection.id
                record.candidate_identity_id = identity.id
                record.external_resume_id = resume_id
                record.external_vacancy_id = vacancy_id
                record.external_employer_id = connection.employer_id
                record.external_manager_id = connection.manager_id
                record.collection_name = collection_id
                state = item.get("state") if isinstance(item.get("state"), dict) else {}
                record.employer_state = _string(state.get("id")) or _string(item.get("employer_state"))
                record.applicant_state = _string(item.get("applicant_state"))
                record.actions_snapshot = {"actions": item.get("actions") or []}
                record.payload_snapshot = item
                record.last_hh_sync_at = now

                if resume_id and resume_payload:
                    result = await session.execute(
                        select(HHResumeSnapshot).where(HHResumeSnapshot.external_resume_id == resume_id)
                    )
                    snapshot = result.scalar_one_or_none()
                    if snapshot is None:
                        snapshot = HHResumeSnapshot(
                            candidate_id=candidate.id,
                            external_resume_id=resume_id,
                        )
                        session.add(snapshot)
                    snapshot.candidate_id = candidate.id
                    snapshot.source_updated_at = _parse_hh_datetime(
                        resume_payload.get("updated_at") or resume_payload.get("created_at")
                    )
                    snapshot.content_hash = _payload_hash(resume_payload)
                    snapshot.payload_json = resume_payload
                    snapshot.fetched_at = now
                    resumes_upserted += 1

            pages = int(payload.get("pages") or 0)
            page += 1
            if pages and page >= pages:
                break

    connection.last_sync_at = now
    connection.last_error = None
    await session.flush()
    return HHNegotiationImportResult(
        collections_seen=len(collections),
        negotiations_seen=negotiations_seen,
        negotiations_created=negotiations_created,
        negotiations_updated=negotiations_updated,
        candidates_created=candidates_created,
        candidates_linked=candidates_linked,
        resumes_upserted=resumes_upserted,
    )


def serialize_import_result(result: HHVacancyImportResult | HHNegotiationImportResult) -> dict[str, Any]:
    return asdict(result)
