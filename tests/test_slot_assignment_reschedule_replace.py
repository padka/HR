from datetime import datetime, timedelta, timezone

import pytest

from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User


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
