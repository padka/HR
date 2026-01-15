from datetime import date, datetime, timedelta, timezone

import pytest

pytest.importorskip("starlette")
from starlette.requests import Request

from backend.apps.admin_ui.config import register_template_globals
from backend.apps.admin_ui.routers.slots import slots_list
from backend.apps.admin_ui.services.dashboard import (
    dashboard_counts,
    get_waiting_candidates,
    get_upcoming_interviews,
)
from backend.apps.admin_ui.services.slots import api_slots_payload, create_slot, list_slots
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User as CandidateUser
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
        recruiter.cities.append(city)
        inactive_recruiter = models.Recruiter(name="Dormant", tz="Europe/Moscow", active=False)
        inactive_city = models.City(name="Archived City", tz="Europe/Moscow", active=False)
        session.add_all([recruiter, city, inactive_recruiter, inactive_city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        recruiter_id = recruiter.id
        city_id = city.id
        session.expunge_all()  # Detach all objects before closing session

    created = await create_slot(
        recruiter_id=recruiter_id,
        date=str(date.today()),
        time="10:00",
        city_id=city_id,
    )
    assert created is True
    async with async_session() as session:
        future_time = datetime.now(timezone.utc) + timedelta(hours=3)
        canceled_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=future_time,
            status=models.SlotStatus.CANCELED,
        )
        session.add(canceled_slot)
        await session.commit()
        canceled_slot_id = canceled_slot.id

    counts = await dashboard_counts()
    assert counts["recruiters"] == 1
    assert counts["cities"] == 1
    assert counts["slots_total"] == 1
    assert counts["waiting_candidates_total"] == 0
    assert counts["test1_rejections_total"] == 0
    assert counts["test1_rejections_percent"] == 0.0

    async with async_session() as session:
        slot = await session.get(models.Slot, canceled_slot_id)
        await session.delete(slot)
        await session.commit()

    listing = await list_slots(
        recruiter_id=None,
        status=None,
        page=1,
        per_page=10,
        search_query=None,
        city_name=None,
        day=None,
    )
    assert listing["total"] == 1
    assert listing["items"][0].recruiter_id == recruiter_id
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
    assert counts["waiting_candidates_total"] == 0
    assert counts["test1_rejections_breakdown"]["format_not_ready"] == 1


@pytest.mark.asyncio
async def test_slots_list_status_counts_and_api_payload_normalizes_statuses():
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        recruiter_id = recruiter.id
        city_id = city.id
        city_tz = city.tz

        now = datetime.now(timezone.utc)
        session.add_all(
            [
                models.Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=now,
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.PENDING,
                ),
                models.Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=now + timedelta(hours=2),
                    status=models.SlotStatus.BOOKED,
                ),
                models.Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    start_utc=now + timedelta(hours=3),
                    status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
                ),
            ]
        )
        await session.commit()
        session.expunge_all()  # Detach all objects before closing session

    payload = await api_slots_payload(recruiter_id=None, status=None, limit=10)
    assert {item["status"] for item in payload} == {
        "FREE",
        "PENDING",
        "BOOKED",
        "CONFIRMED_BY_CANDIDATE",
    }
    assert all("local_time" in item for item in payload)
    assert all(item.get("tz_name") == city_tz for item in payload)

    register_template_globals()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/slots",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    response = await slots_list(request, recruiter_id=None, status=None, page=1, per_page=10)
    status_counts = response.context["status_counts"]
    assert status_counts == {
        "total": 4,
        "FREE": 1,
        "PENDING": 1,
        "BOOKED": 1,
        "CONFIRMED_BY_CANDIDATE": 1,
    }


@pytest.mark.asyncio
async def test_waiting_candidates_include_manual_availability():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = CandidateUser(
            telegram_id=777001,
            username="manual_candidate",
            fio="Manual Candidate",
            city="Неизвестный",
            is_active=True,
            last_activity=now,
            candidate_status=CandidateStatus.WAITING_SLOT,
            manual_slot_from=now + timedelta(days=1),
            manual_slot_to=now + timedelta(days=1, hours=2),
            manual_slot_comment="После 18:00 (МСК)",
            manual_slot_timezone="Europe/Moscow",
            manual_slot_requested_at=now,
        )
        session.add(user)
        await session.commit()
        candidate_id = user.id

    rows = await get_waiting_candidates(limit=5)
    match = next((row for row in rows if row["id"] == candidate_id), None)
    assert match is not None
    assert match["availability_window"]


@pytest.mark.asyncio
async def test_waiting_candidates_excluded_after_status_moves_forward():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = CandidateUser(
            telegram_id=777555,
            username="waiting_candidate",
            fio="Waiting Candidate",
            city="Москва",
            is_active=True,
            last_activity=now,
            candidate_status=CandidateStatus.WAITING_SLOT,
            manual_slot_comment="Можно завтра после 18:00",
            manual_slot_requested_at=now,
        )
        session.add(user)
        await session.commit()
        candidate_id = user.id

    rows = await get_waiting_candidates(limit=10)
    assert any(row["id"] == candidate_id for row in rows)

    async with async_session() as session:
        db_user = await session.get(CandidateUser, candidate_id)
        db_user.candidate_status = CandidateStatus.INTERVIEW_SCHEDULED
        await session.commit()

    rows = await get_waiting_candidates(limit=10)
    assert all(row["id"] != candidate_id for row in rows)


@pytest.mark.asyncio
async def test_upcoming_interviews_include_profile_and_telemost():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Календарь", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(
            name="Digital Recruiter",
            tz="Europe/Moscow",
            active=True,
            telemost_url="https://telemost.example/room",
        )
        recruiter.cities.append(city)
        candidate = CandidateUser(
            telegram_id=444001,
            username="cal_candidate",
            fio="Календарный Кандидат",
            city="Календарь",
            is_active=True,
            last_activity=now,
        )
        session.add_all([city, recruiter, candidate])
        await session.flush()

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            start_utc=now + timedelta(hours=2),
            status=models.SlotStatus.BOOKED,
            duration_min=45,
            tz_name=city.tz,
        )
        session.add(slot)
        await session.commit()
        candidate_id = candidate.id
        city_name = city.name
        session.expunge_all()  # Detach all objects before closing session

    rows = await get_upcoming_interviews(limit=5)
    assert rows
    interview = rows[0]

    assert interview["candidate_url"] == f"/candidates/{candidate_id}"
    assert interview["telemost_url"] == "https://telemost.example/room"
    assert interview["slot_status_label"] == "Подтверждено"
    assert "Europe/Moscow" in interview["time_range"]
    assert interview["starts_in"]
    assert interview["city_name"] == city_name
