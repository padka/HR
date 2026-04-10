from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User
from backend.domain.slot_assignment_service import (
    approve_reschedule,
    create_slot_assignment,
    request_reschedule,
)


@pytest.mark.asyncio
async def test_confirm_assignment_replaces_existing_slot_during_reschedule():
    """Regression: reschedule negotiation must not block when candidate already has a slot."""
    from backend.apps.admin_ui.routers.slot_assignments_api import (
        ActionPayload,
        confirm_assignment,
    )

    now = datetime.now(timezone.utc)
    candidate_tg_id = 123456

    async with async_session() as session:
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Recruiter", tz="Europe/Moscow", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        candidate = User(
            fio="Candidate",
            city="City",
            telegram_id=candidate_tg_id,
            username="candidate",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        old_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.BOOKED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate_tg_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        new_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(days=2),
            duration_min=30,
            status=models.SlotStatus.FREE,
        )
        session.add_all([old_slot, new_slot])
        await session.commit()
        await session.refresh(old_slot)
        await session.refresh(new_slot)

        assignment = models.SlotAssignment(
            slot_id=new_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate_tg_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        token_value = "test-token"
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

    result = await confirm_assignment(
        assignment.id,
        ActionPayload(action_token=token_value, candidate_tg_id=candidate_tg_id),
    )
    assert result["ok"] is True

    async with async_session() as session:
        old_slot_db = await session.get(models.Slot, old_slot.id)
        new_slot_db = await session.get(models.Slot, new_slot.id)

        assert old_slot_db is not None
        assert old_slot_db.status == models.SlotStatus.FREE
        assert old_slot_db.candidate_id is None
        assert old_slot_db.candidate_tg_id is None

        assert new_slot_db is not None
        assert new_slot_db.status == models.SlotStatus.BOOKED
        assert new_slot_db.candidate_id == candidate.candidate_id
        assert new_slot_db.candidate_tg_id == candidate_tg_id


@pytest.mark.asyncio
async def test_approve_reschedule_syncs_old_and_new_slots():
    now = datetime.now(timezone.utc)
    candidate_tg_id = 123457

    async with async_session() as session:
        city = models.City(name="Reschedule City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Reschedule Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Reschedule Candidate",
            city="Reschedule City",
            telegram_id=candidate_tg_id,
            telegram_user_id=candidate_tg_id,
            username="reschedule_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        old_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add(old_slot)
        await session.commit()
        await session.refresh(old_slot)

        old_slot_id = int(old_slot.id)
        candidate_uuid = str(candidate.candidate_id)

    offer = await create_slot_assignment(
        slot_id=old_slot_id,
        candidate_id=candidate_uuid,
        candidate_tg_id=candidate_tg_id,
        candidate_tz="Europe/Moscow",
        created_by="test",
    )
    assert offer.ok is True

    assignment_id = int(offer.payload["slot_assignment_id"])
    reschedule_token = str(offer.payload["reschedule_token"])
    requested_start_utc = now + timedelta(days=2, hours=3)

    request = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate_tg_id,
        requested_start_utc=requested_start_utc,
        requested_tz="Europe/Moscow",
    )
    assert request.ok is True

    approve = await approve_reschedule(
        assignment_id=assignment_id,
        decided_by_id=1,
        decided_by_type="admin",
        comment="confirmed exact slot",
    )
    assert approve.ok is True

    new_slot_id = int(approve.payload["slot_id"])
    assert new_slot_id != old_slot_id

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        old_slot_db = await session.get(models.Slot, old_slot_id)
        new_slot_db = await session.get(models.Slot, new_slot_id)
        request_db = await session.scalar(
            select(models.RescheduleRequest).where(
                models.RescheduleRequest.slot_assignment_id == assignment_id
            )
        )

    assert assignment is not None
    assert assignment.slot_id == new_slot_id
    assert assignment.status == models.SlotAssignmentStatus.RESCHEDULE_CONFIRMED

    assert old_slot_db is not None
    assert old_slot_db.status == models.SlotStatus.FREE
    assert old_slot_db.candidate_id is None
    assert old_slot_db.candidate_tg_id is None

    assert new_slot_db is not None
    assert new_slot_db.status == models.SlotStatus.BOOKED
    assert new_slot_db.candidate_id == candidate_uuid
    assert new_slot_db.candidate_tg_id == candidate_tg_id
    assert new_slot_db.start_utc == requested_start_utc

    assert request_db is not None
    assert request_db.status == models.RescheduleRequestStatus.APPROVED
    assert request_db.alternative_slot_id == new_slot_id
