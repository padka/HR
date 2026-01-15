from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.services.candidates import upsert_candidate
from backend.core.db import async_session
from backend.domain.candidates import models as candidate_models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.repositories import reserve_slot


@pytest.mark.asyncio
async def test_manual_candidate_creation_lead_status():
    user = await upsert_candidate(
        telegram_id=None,
        fio="Lead Candidate",
        city="Москва",
        phone="+7 900 000-00-00",
        is_active=True,
    )

    assert user.telegram_id is None
    assert user.candidate_status == CandidateStatus.LEAD
    assert user.source == "manual_call"


@pytest.mark.asyncio
async def test_reserve_slot_by_candidate_id_without_telegram():
    async with async_session() as session:
        city = City(name="Lead City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Lead Recruiter", tz="Europe/Moscow", active=True)
        session.add_all([city, recruiter])
        await session.flush()

        candidate = candidate_models.User(
            telegram_id=None,
            fio="Lead Booker",
            city=city.name,
            is_active=True,
            candidate_status=CandidateStatus.LEAD,
            source="manual_call",
        )
        session.add(candidate)
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(candidate)
        await session.refresh(slot)

    reservation = await reserve_slot(
        slot.id,
        candidate_tg_id=None,
        candidate_fio=candidate.fio,
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        candidate_id=candidate.candidate_id,
        purpose="interview",
    )

    assert reservation.status == "reserved"
    assert reservation.slot is not None
    assert reservation.slot.candidate_id == candidate.candidate_id
    assert reservation.slot.candidate_tg_id is None


@pytest.mark.asyncio
async def test_invite_token_links_telegram_to_lead():
    async with async_session() as session:
        candidate = candidate_models.User(
            telegram_id=None,
            fio="Invite Lead",
            city="Москва",
            is_active=True,
            candidate_status=CandidateStatus.LEAD,
            source="manual_call",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

    invite = await candidate_services.create_candidate_invite_token(candidate.candidate_id)
    bound = await candidate_services.bind_telegram_to_candidate(
        token=invite.token,
        telegram_id=123456789,
        username="invite_lead",
    )

    assert bound is not None
    assert bound.telegram_id == 123456789
    assert bound.telegram_username == "invite_lead"

    async with async_session() as session:
        refreshed = await session.scalar(
            select(candidate_models.User).where(candidate_models.User.candidate_id == candidate.candidate_id)
        )
        token_row = await session.scalar(
            select(candidate_models.CandidateInviteToken).where(
                candidate_models.CandidateInviteToken.id == invite.id
            )
        )

    assert refreshed is not None
    assert refreshed.telegram_id == 123456789
    assert token_row is not None
    assert token_row.used_at is not None


@pytest.mark.asyncio
async def test_invite_token_has_id_and_persists():
    async with async_session() as session:
        candidate = candidate_models.User(
            telegram_id=None,
            fio="Invite Token ID",
            city="Москва",
            is_active=True,
            candidate_status=CandidateStatus.LEAD,
            source="manual_call",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

    invite = await candidate_services.create_candidate_invite_token(candidate.candidate_id)
    assert invite.id is not None

    async with async_session() as session:
        stored = await session.get(candidate_models.CandidateInviteToken, invite.id)
    assert stored is not None
