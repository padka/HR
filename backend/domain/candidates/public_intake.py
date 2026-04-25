"""Public browser campaign intake domain service.

The public intake state is intentionally separate from candidate access tokens:
global campaign links do not identify a candidate until a provider verifies them.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.core.db import async_session
from backend.domain.candidates.journey import append_journey_event
from backend.domain.candidates.models import (
    CandidateJourneyEvent,
    CandidateWebCampaign,
    CandidateWebPublicIntake,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.hh_integration.models import CandidateExternalIdentity
from backend.domain.models import City
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

CAMPAIGN_STATUS_ACTIVE = "active"
CAMPAIGN_STATUSES = {"draft", "active", "paused", "expired", "archived"}
INTAKE_STATUS_PENDING = "pending"
INTAKE_STATUS_PROVIDER_STARTED = "provider_started"
INTAKE_STATUS_VERIFIED = "verified"
INTAKE_STATUS_SESSION_ISSUED = "session_issued"
INTAKE_STATUS_CONFLICT = "conflict"
INTAKE_STATUS_EXPIRED = "expired"
INTAKE_STATUS_FAILED = "failed"
INTAKE_STATUSES = {
    INTAKE_STATUS_PENDING,
    INTAKE_STATUS_PROVIDER_STARTED,
    INTAKE_STATUS_VERIFIED,
    INTAKE_STATUS_SESSION_ISSUED,
    INTAKE_STATUS_CONFLICT,
    INTAKE_STATUS_EXPIRED,
    INTAKE_STATUS_FAILED,
}
PUBLIC_PROVIDER_TELEGRAM = "telegram"
PUBLIC_PROVIDER_MAX = "max"
PUBLIC_PROVIDER_HH = "hh"
PUBLIC_PROVIDERS = {PUBLIC_PROVIDER_TELEGRAM, PUBLIC_PROVIDER_MAX, PUBLIC_PROVIDER_HH}


@dataclass(frozen=True)
class PublicIntakeStart:
    intake: CandidateWebPublicIntake
    poll_token: str
    provider_token: str


@dataclass(frozen=True)
class PublicIntakeConsumeResult:
    handled: bool
    status: str
    candidate: User | None = None
    intake_id: int | None = None
    code: str | None = None


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def hash_public_token(raw_token: str) -> str:
    return hashlib.sha256(str(raw_token or "").encode("utf-8")).hexdigest()


def generate_public_token(prefix: str) -> str:
    safe_prefix = "".join(ch for ch in str(prefix or "pub").lower() if ch.isalnum() or ch in {"_", "-"})
    safe_prefix = safe_prefix[:12] or "pub"
    return f"{safe_prefix}_{secrets.token_urlsafe(24).rstrip('=')}"


def normalize_campaign_slug(value: str) -> str:
    return str(value or "").strip().lower()


def normalize_public_provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    if provider in {"tg", "telegram"}:
        return PUBLIC_PROVIDER_TELEGRAM
    if provider in {"vkmax", "vk_max", "max"}:
        return PUBLIC_PROVIDER_MAX
    if provider in {"hh", "hh.ru", "headhunter"}:
        return PUBLIC_PROVIDER_HH
    return provider


def sanitize_allowed_public_providers(value: Any, *, defaults: tuple[str, ...]) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, tuple):
        raw_values = list(value)
    elif isinstance(value, str):
        raw_values = value.split(",")
    else:
        raw_values = list(defaults)
    allowed: list[str] = []
    for item in raw_values:
        provider = normalize_public_provider(str(item or ""))
        if provider in PUBLIC_PROVIDERS and provider not in allowed:
            allowed.append(provider)
    return allowed or list(defaults)


def campaign_is_available(campaign: CandidateWebCampaign, *, now: datetime) -> bool:
    if campaign.status != CAMPAIGN_STATUS_ACTIVE:
        return False
    starts_at = as_utc(campaign.starts_at)
    expires_at = as_utc(campaign.expires_at)
    return (starts_at is None or starts_at <= now) and (expires_at is None or expires_at > now)


async def get_public_campaign_by_slug(
    session: AsyncSession,
    slug: str,
) -> CandidateWebCampaign | None:
    normalized_slug = normalize_campaign_slug(slug)
    if not normalized_slug:
        return None
    return await session.scalar(
        select(CandidateWebCampaign).where(CandidateWebCampaign.slug == normalized_slug).limit(1)
    )


async def create_public_intake(
    session: AsyncSession,
    *,
    campaign: CandidateWebCampaign,
    provider: str,
    utm: dict[str, Any] | None,
    token_ttl_seconds: int,
) -> PublicIntakeStart:
    provider_value = normalize_public_provider(provider)
    if provider_value not in PUBLIC_PROVIDERS:
        raise ValueError("unsupported_provider")
    now = utcnow()
    poll_token = generate_public_token("poll")
    provider_token = generate_public_token(f"pub{provider_value}")
    intake = CandidateWebPublicIntake(
        campaign_id=int(campaign.id),
        poll_token_hash=hash_public_token(poll_token),
        provider_token_hash=hash_public_token(provider_token),
        provider=provider_value,
        status=INTAKE_STATUS_PROVIDER_STARTED,
        utm_json=dict(utm or {}),
        expires_at=now + timedelta(seconds=max(60, int(token_ttl_seconds))),
        metadata_json={"campaign_slug": campaign.slug},
    )
    session.add(intake)
    await session.flush()
    return PublicIntakeStart(intake=intake, poll_token=poll_token, provider_token=provider_token)


async def _load_city_name(session: AsyncSession, city_id: int | None) -> str | None:
    if city_id is None:
        return None
    city = await session.get(City, int(city_id))
    if city is None:
        return None
    return str(city.name or "").strip() or None


async def _candidate_ids_for_hh_resume(
    session: AsyncSession,
    external_resume_id: str,
) -> set[int]:
    rows = (
        await session.scalars(
            select(CandidateExternalIdentity).where(
                CandidateExternalIdentity.source == PUBLIC_PROVIDER_HH,
                CandidateExternalIdentity.external_resume_id == external_resume_id,
            )
        )
    ).all()
    return {int(row.candidate_id) for row in rows if row.candidate_id is not None}


async def _resolve_existing_candidate(
    session: AsyncSession,
    *,
    provider: str,
    provider_user_id: str,
    hh_resume_id: str | None,
) -> tuple[User | None, bool]:
    provider_value = normalize_public_provider(provider)
    candidates: list[User] = []
    if provider_value == PUBLIC_PROVIDER_TELEGRAM:
        telegram_id = int(provider_user_id)
        candidates = (
            await session.scalars(
                select(User).where(
                    or_(User.telegram_id == telegram_id, User.telegram_user_id == telegram_id)
                )
            )
        ).all()
    elif provider_value == PUBLIC_PROVIDER_MAX:
        candidates = (
            await session.scalars(select(User).where(User.max_user_id == provider_user_id))
        ).all()
    elif provider_value == PUBLIC_PROVIDER_HH and hh_resume_id:
        candidate_ids = await _candidate_ids_for_hh_resume(session, hh_resume_id)
        if len(candidate_ids) > 1:
            return None, True
        if candidate_ids:
            candidate = await session.get(User, next(iter(candidate_ids)))
            return candidate, False
    unique = {int(candidate.id): candidate for candidate in candidates}
    if len(unique) > 1:
        return None, True
    if unique:
        return next(iter(unique.values())), False
    return None, False


async def _create_candidate_from_public_intake(
    session: AsyncSession,
    *,
    campaign: CandidateWebCampaign,
    provider: str,
    provider_user_id: str,
    username: str | None,
    display_name: str | None,
) -> User:
    now = utcnow()
    city_name = await _load_city_name(session, campaign.city_id)
    provider_label = normalize_public_provider(provider).upper()
    candidate = User(
        candidate_id=str(uuid.uuid4()),
        fio=(str(display_name or "").strip() or f"WEB кандидат {provider_label}"),
        username=str(username or "").strip() or None,
        city=city_name,
        source="web",
        messenger_platform=normalize_public_provider(provider)
        if normalize_public_provider(provider) in {"telegram", "max"}
        else "web",
        responsible_recruiter_id=campaign.default_recruiter_id,
        candidate_status=CandidateStatus.LEAD,
        last_activity=now,
    )
    session.add(candidate)
    await session.flush()
    return candidate


async def find_or_create_public_candidate(
    session: AsyncSession,
    *,
    intake: CandidateWebPublicIntake,
    provider_user_id: str,
    username: str | None = None,
    display_name: str | None = None,
    hh_resume_id: str | None = None,
) -> tuple[User | None, str]:
    provider = normalize_public_provider(intake.provider)
    campaign = await session.get(CandidateWebCampaign, int(intake.campaign_id))
    if campaign is None:
        intake.status = INTAKE_STATUS_FAILED
        intake.metadata_json = {**dict(intake.metadata_json or {}), "failure_code": "campaign_missing"}
        return None, "campaign_missing"

    candidate, conflict = await _resolve_existing_candidate(
        session,
        provider=provider,
        provider_user_id=provider_user_id,
        hh_resume_id=hh_resume_id,
    )
    if conflict:
        intake.status = INTAKE_STATUS_CONFLICT
        intake.metadata_json = {**dict(intake.metadata_json or {}), "conflict_code": "identity_conflict"}
        return None, "identity_conflict"

    if candidate is None:
        candidate = await _create_candidate_from_public_intake(
            session,
            campaign=campaign,
            provider=provider,
            provider_user_id=provider_user_id,
            username=username,
            display_name=display_name,
        )

    now = utcnow()
    if provider == PUBLIC_PROVIDER_TELEGRAM:
        telegram_id = int(provider_user_id)
        if candidate.telegram_id not in {None, telegram_id} or candidate.telegram_user_id not in {
            None,
            telegram_id,
        }:
            intake.status = INTAKE_STATUS_CONFLICT
            intake.metadata_json = {**dict(intake.metadata_json or {}), "conflict_code": "telegram_conflict"}
            return None, "telegram_conflict"
        candidate.telegram_id = telegram_id
        candidate.telegram_user_id = telegram_id
        candidate.telegram_username = username or candidate.telegram_username
        candidate.username = username or candidate.username
        candidate.telegram_linked_at = candidate.telegram_linked_at or now
        candidate.messenger_platform = "telegram"
    elif provider == PUBLIC_PROVIDER_MAX:
        if candidate.max_user_id not in {None, provider_user_id}:
            intake.status = INTAKE_STATUS_CONFLICT
            intake.metadata_json = {**dict(intake.metadata_json or {}), "conflict_code": "max_conflict"}
            return None, "max_conflict"
        candidate.max_user_id = provider_user_id
        candidate.username = username or candidate.username
        if display_name and (
            not str(candidate.fio or "").strip()
            or str(candidate.fio or "").startswith("WEB кандидат")
            or str(candidate.fio or "").startswith("TG ")
        ):
            candidate.fio = display_name
        candidate.messenger_platform = "max"

    candidate.source = "web"
    candidate.last_activity = now
    intake.candidate_id = int(candidate.id)
    intake.provider_user_id = provider_user_id
    intake.status = INTAKE_STATUS_VERIFIED
    intake.metadata_json = {
        **dict(intake.metadata_json or {}),
        "verified_provider": provider,
        "campaign_slug": campaign.slug,
    }
    existing_event_id = await session.scalar(
        select(CandidateJourneyEvent.id)
        .where(
            CandidateJourneyEvent.candidate_id == int(candidate.id),
            CandidateJourneyEvent.event_key == "candidate_web_public_verified",
        )
        .limit(1)
    )
    if existing_event_id is None:
        append_journey_event(
            candidate,
            event_key="candidate_web_public_verified",
            stage="identity",
            actor_type="candidate",
            summary="Кандидат подтвердил профиль через публичную web-кампанию",
            payload={"provider": provider, "campaign_slug": campaign.slug},
            created_at=now,
        )
    return candidate, "verified"


async def consume_public_intake_provider_token(
    *,
    provider_token: str,
    provider: str,
    provider_user_id: str,
    username: str | None = None,
    display_name: str | None = None,
) -> PublicIntakeConsumeResult:
    token_hash = hash_public_token(str(provider_token or "").strip())
    provider_value = normalize_public_provider(provider)
    provider_user = str(provider_user_id or "").strip()
    if not provider_token or provider_value not in PUBLIC_PROVIDERS or not provider_user:
        return PublicIntakeConsumeResult(handled=False, status=INTAKE_STATUS_FAILED)

    async with async_session() as session:
        async with session.begin():
            intake = await session.scalar(
                select(CandidateWebPublicIntake)
                .where(
                    CandidateWebPublicIntake.provider_token_hash == token_hash,
                    CandidateWebPublicIntake.provider == provider_value,
                )
                .with_for_update()
            )
            if intake is None:
                return PublicIntakeConsumeResult(handled=False, status=INTAKE_STATUS_FAILED)
            now = utcnow()
            if as_utc(intake.expires_at) is not None and as_utc(intake.expires_at) <= now:
                intake.status = INTAKE_STATUS_EXPIRED
                return PublicIntakeConsumeResult(
                    handled=True,
                    status=INTAKE_STATUS_EXPIRED,
                    intake_id=int(intake.id),
                    code="expired",
                )
            if intake.status == INTAKE_STATUS_SESSION_ISSUED and intake.candidate_id is not None:
                candidate = await session.get(User, int(intake.candidate_id))
                return PublicIntakeConsumeResult(
                    handled=True,
                    status=INTAKE_STATUS_SESSION_ISSUED,
                    candidate=candidate,
                    intake_id=int(intake.id),
                )
            candidate, code = await find_or_create_public_candidate(
                session,
                intake=intake,
                provider_user_id=provider_user,
                username=username,
                display_name=display_name,
            )
            return PublicIntakeConsumeResult(
                handled=True,
                status=intake.status,
                candidate=candidate,
                intake_id=int(intake.id),
                code=code,
            )
