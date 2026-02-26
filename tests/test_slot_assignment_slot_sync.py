from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.routers.slot_assignments_api import ActionPayload, confirm_assignment
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User
from backend.domain.slot_assignment_service import create_slot_assignment


@pytest.mark.asyncio
async def test_create_slot_assignment_syncs_slot_candidate_binding():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Sync City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Sync Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Тест Слота",
            city="Sync City",
            telegram_id=710001,
            username="sync_candidate",
        )
        slot = models.Slot(
            recruiter_id=1,
            city_id=1,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.FREE,
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        slot.recruiter_id = recruiter.id
        slot.city_id = city.id
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        slot_id = slot.id
        candidate_id = candidate.candidate_id
        candidate_tg_id = candidate.telegram_id
        candidate_fio = candidate.fio

    result = await create_slot_assignment(
        slot_id=slot_id,
        candidate_id=candidate_id,
        created_by="test",
    )
    assert result.ok is True

    async with async_session() as session:
        slot = await session.get(models.Slot, slot_id)
        assert slot is not None
        assert slot.status == models.SlotStatus.PENDING
        assert slot.candidate_id == candidate_id
        assert slot.candidate_tg_id == candidate_tg_id
        assert slot.candidate_fio == candidate_fio


@pytest.mark.asyncio
async def test_confirm_assignment_accepts_telegram_user_id_and_updates_slot():
    now = datetime.now(timezone.utc)
    telegram_id = 720001
    telegram_user_id = 720002

    async with async_session() as session:
        city = models.City(name="Confirm City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Confirm Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Подтвержденный Кандидат",
            city="Confirm City",
            telegram_id=telegram_id,
            telegram_user_id=telegram_user_id,
            username="confirm_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        token_value = "sync-confirm-token"
        session.add(
            models.ActionToken(
                token=token_value,
                action="slot_assignment_confirm",
                entity_id=str(assignment.id),
                expires_at=now + timedelta(hours=2),
                created_at=now,
            )
        )
        await session.commit()

        assignment_id = assignment.id
        slot_id = slot.id
        candidate_uuid = candidate.candidate_id

    result = await confirm_assignment(
        assignment_id,
        ActionPayload(action_token=token_value, candidate_tg_id=telegram_user_id),
    )
    assert result["ok"] is True

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        slot = await session.get(models.Slot, slot_id)
        candidate = await session.scalar(
            select(User).where(User.candidate_id == candidate_uuid)
        )
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.CONFIRMED
        assert assignment.candidate_tg_id == telegram_user_id
        assert slot is not None
        assert slot.status == models.SlotStatus.BOOKED
        assert slot.candidate_tg_id == telegram_user_id
        assert slot.candidate_id == candidate_uuid
        assert candidate is not None
        assert candidate.responsible_recruiter_id == recruiter.id
