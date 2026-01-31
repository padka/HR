from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.apps.admin_ui.routers.reschedule_requests import (
    approve_reschedule_request,
    list_reschedule_requests,
    propose_new_time,
    NewProposalPayload,
)
from backend.apps.admin_ui.security import Principal
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User


async def _seed_requests():
    async with async_session() as session:
        recruiter_one = models.Recruiter(name="R1", tz="Europe/Moscow", active=True)
        recruiter_two = models.Recruiter(name="R2", tz="Europe/Moscow", active=True)
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        recruiter_one.cities.append(city)
        recruiter_two.cities.append(city)
        session.add_all([recruiter_one, recruiter_two, city])
        await session.commit()
        await session.refresh(recruiter_one)
        await session.refresh(recruiter_two)

        user_one = User(fio="Candidate One", city="City")
        user_two = User(fio="Candidate Two", city="City")
        session.add_all([user_one, user_two])
        await session.commit()
        await session.refresh(user_one)
        await session.refresh(user_two)

        start = datetime.now(timezone.utc) + timedelta(days=1)
        slot_one = models.Slot(
            recruiter_id=recruiter_one.id,
            city_id=city.id,
            start_utc=start,
            status=models.SlotStatus.BOOKED,
            candidate_id=user_one.candidate_id,
            candidate_tg_id=111,
            candidate_fio=user_one.fio,
            candidate_tz="Europe/Moscow",
        )
        slot_two = models.Slot(
            recruiter_id=recruiter_two.id,
            city_id=city.id,
            start_utc=start,
            status=models.SlotStatus.BOOKED,
            candidate_id=user_two.candidate_id,
            candidate_tg_id=222,
            candidate_fio=user_two.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add_all([slot_one, slot_two])
        await session.commit()
        await session.refresh(slot_one)
        await session.refresh(slot_two)

        assignment_one = models.SlotAssignment(
            slot_id=slot_one.id,
            recruiter_id=recruiter_one.id,
            candidate_id=user_one.candidate_id,
            candidate_tg_id=111,
            candidate_tz="Europe/Moscow",
            status="reschedule_requested",
        )
        assignment_two = models.SlotAssignment(
            slot_id=slot_two.id,
            recruiter_id=recruiter_two.id,
            candidate_id=user_two.candidate_id,
            candidate_tg_id=222,
            candidate_tz="Europe/Moscow",
            status="reschedule_requested",
        )
        session.add_all([assignment_one, assignment_two])
        await session.commit()
        await session.refresh(assignment_one)
        await session.refresh(assignment_two)

        req_one = models.RescheduleRequest(
            slot_assignment_id=assignment_one.id,
            requested_start_utc=start + timedelta(days=1),
        )
        req_two = models.RescheduleRequest(
            slot_assignment_id=assignment_two.id,
            requested_start_utc=start + timedelta(days=1),
        )
        session.add_all([req_one, req_two])
        await session.commit()
        await session.refresh(req_one)
        await session.refresh(req_two)

        return recruiter_one.id, recruiter_two.id, req_one.id, req_two.id


@pytest.mark.asyncio
async def test_reschedule_list_scopes_by_recruiter():
    recruiter_one_id, recruiter_two_id, req_one_id, req_two_id = await _seed_requests()

    admin_requests = await list_reschedule_requests(Principal(type="admin", id=-1))
    admin_ids = {req.id for req in admin_requests}
    assert admin_ids == {req_one_id, req_two_id}

    recruiter_requests = await list_reschedule_requests(Principal(type="recruiter", id=recruiter_one_id))
    recruiter_ids = {req.id for req in recruiter_requests}
    assert recruiter_ids == {req_one_id}

    other_recruiter_requests = await list_reschedule_requests(Principal(type="recruiter", id=recruiter_two_id))
    other_ids = {req.id for req in other_recruiter_requests}
    assert other_ids == {req_two_id}


@pytest.mark.asyncio
async def test_reschedule_actions_block_unauthorized_recruiter():
    recruiter_one_id, recruiter_two_id, req_one_id, _req_two_id = await _seed_requests()

    with pytest.raises(HTTPException) as exc_info:
        await approve_reschedule_request(req_one_id, Principal(type="recruiter", id=recruiter_two_id))
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await propose_new_time(
            req_one_id,
            payload=NewProposalPayload(
                new_start_utc=datetime.now(timezone.utc) + timedelta(days=2),
                recruiter_comment="nope",
            ),
            principal=Principal(type="recruiter", id=recruiter_two_id),
        )
    assert exc_info.value.status_code == 403
