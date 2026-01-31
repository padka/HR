from datetime import date, datetime, timedelta, timezone

import pytest

from backend.apps.admin_ui.services.dashboard import (
    dashboard_counts,
    get_recruiter_leaderboard,
)
from backend.apps.admin_ui.services.slots import api_slots_payload, create_slot, list_slots
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.apps.bot.metrics import (
    record_test1_completion,
    record_test1_rejection,
    reset_test1_metrics,
)


@pytest.mark.asyncio
async def test_dashboard_and_slot_listing():
    await reset_test1_metrics()
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="UI City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

    target_day = date.today() + timedelta(days=1)
    created = await create_slot(
        recruiter_id=recruiter.id,
        date=str(target_day),
        time="10:00",
        city_id=city.id,
    )
    assert created is True

    counts = await dashboard_counts()
    assert counts["recruiters"] == 1
    assert counts["cities"] == 1
    assert counts["slots_total"] == 1
    assert counts["test1_rejections_total"] == 0
    assert counts["test1_rejections_percent"] == 0.0

    listing = await list_slots(
        recruiter_id=None,
        status=None,
        page=1,
        per_page=10,
    )
    assert listing["total"] == 1
    assert listing["items"][0].recruiter_id == recruiter.id
    assert listing["status_counts"] == {"FREE": 1, "CONFIRMED_BY_CANDIDATE": 0}


@pytest.mark.asyncio
async def test_dashboard_reports_test1_metrics():
    await reset_test1_metrics()
    await record_test1_rejection("format_not_ready")
    await record_test1_completion()

    counts = await dashboard_counts()
    assert counts["test1_rejections_total"] == 1
    assert counts["test1_total_seen"] == 2
    assert counts["test1_rejections_percent"] == 50.0
    assert counts["test1_rejections_breakdown"]["format_not_ready"] == 1


@pytest.mark.asyncio
async def test_slots_list_status_counts_and_api_payload_normalizes_statuses():
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

        now = datetime.now(timezone.utc)
        session.add_all(
            [
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now,
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.PENDING,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=2),
                    status=models.SlotStatus.BOOKED,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=3),
                    status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
                ),
            ]
        )
        await session.commit()

    payload = await api_slots_payload(recruiter_id=None, status=None, limit=10)
    assert {item["status"] for item in payload} == {
        "FREE",
        "PENDING",
        "BOOKED",
        "CONFIRMED_BY_CANDIDATE",
    }

    # slots_list now redirects to SPA, test status_counts via list_slots service
    listing = await list_slots(recruiter_id=None, status=None, page=1, per_page=10)
    assert listing["total"] == 4
    assert listing["status_counts"]["FREE"] == 1
    assert listing["status_counts"]["PENDING"] == 1
    assert listing["status_counts"]["BOOKED"] == 1
    assert listing["status_counts"]["CONFIRMED_BY_CANDIDATE"] == 1


@pytest.mark.asyncio
async def test_recruiter_leaderboard_scores_and_ranking():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        recruiter_a = models.Recruiter(name="Alpha", tz="Europe/Moscow", active=True)
        recruiter_b = models.Recruiter(name="Beta", tz="Europe/Moscow", active=True)
        session.add_all([recruiter_a, recruiter_b])
        await session.commit()
        await session.refresh(recruiter_a)
        await session.refresh(recruiter_b)

        base_time = now - timedelta(days=1)

        def _user(name: str, recruiter_id: int, status: CandidateStatus) -> User:
            return User(
                fio=name,
                responsible_recruiter_id=recruiter_id,
                candidate_status=status,
                status_changed_at=base_time,
                last_activity=base_time,
                city="Moscow",
            )

        users = [
            _user("A1", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A2", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A3", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A4", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A5", recruiter_a.id, CandidateStatus.INTRO_DAY_SCHEDULED),
            _user("A6", recruiter_a.id, CandidateStatus.HIRED),
            _user("A7", recruiter_a.id, CandidateStatus.HIRED),
            _user("A8", recruiter_a.id, CandidateStatus.NOT_HIRED),
            _user("A9", recruiter_a.id, CandidateStatus.TEST2_FAILED),
            _user("A10", recruiter_a.id, CandidateStatus.WAITING_SLOT),
            _user("B1", recruiter_b.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("B2", recruiter_b.id, CandidateStatus.WAITING_SLOT),
            _user("B3", recruiter_b.id, CandidateStatus.WAITING_SLOT),
            _user("B4", recruiter_b.id, CandidateStatus.NOT_HIRED),
            _user("B5", recruiter_b.id, CandidateStatus.TEST2_FAILED),
        ]
        session.add_all(users)

        slots = []
        for idx in range(6):
            status = models.SlotStatus.BOOKED if idx < 3 else models.SlotStatus.CONFIRMED_BY_CANDIDATE
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_a.id,
                    start_utc=now - timedelta(hours=idx + 1),
                    status=status,
                )
            )
        for idx in range(2):
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_a.id,
                    start_utc=now - timedelta(hours=idx + 10),
                    status=models.SlotStatus.PENDING,
                )
            )
        for idx in range(2):
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_a.id,
                    start_utc=now - timedelta(hours=idx + 20),
                    status=models.SlotStatus.FREE,
                )
            )
        slots.append(
            models.Slot(
                recruiter_id=recruiter_b.id,
                start_utc=now - timedelta(hours=2),
                status=models.SlotStatus.BOOKED,
            )
        )
        for idx in range(4):
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_b.id,
                    start_utc=now - timedelta(hours=idx + 6),
                    status=models.SlotStatus.FREE,
                )
            )
        session.add_all(slots)
        await session.commit()

    payload = await get_recruiter_leaderboard(
        date_from=now - timedelta(days=7),
        date_to=now,
    )
    items = payload["items"]
    assert len(items) == 2

    item_a = next(item for item in items if item["recruiter_id"] == recruiter_a.id)
    item_b = next(item for item in items if item["recruiter_id"] == recruiter_b.id)

    assert item_a["candidates_total"] == 10
    assert item_a["slots_booked"] == 6
    assert item_a["fill_rate"] == 60.0
    assert item_a["conversion_interview"] == 70.0
    assert item_a["score"] >= item_b["score"]
    assert item_a["rank"] == 1
