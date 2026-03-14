from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, OutboxNotification, Recruiter, Slot, SlotAssignment, SlotReminderJob, SlotStatus


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


async def _seed_recruiter_city(*, city_name: str, recruiter_name: str) -> tuple[int, int]:
    async with async_session() as session:
        city = City(name=city_name, tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name=recruiter_name, tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        return int(city.id), int(recruiter.id)


def _request(app, method: str, path: str, **kwargs):
    with TestClient(app) as client:
        client.auth = ("admin", "admin")
        return client.request(method, path, **kwargs)


@pytest.mark.asyncio
async def test_manual_booking_creates_silent_candidate_without_outbox(admin_app) -> None:
    city_id, recruiter_id = await _seed_recruiter_city(
        city_name="Silent City",
        recruiter_name="Silent Recruiter",
    )

    response = await asyncio.to_thread(
        _request,
        admin_app,
        "post",
        "/api/slots/manual-bookings",
        json={
            "fio": "Manual Silent Candidate",
            "phone": "+79990001122",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
            "date": "2031-05-20",
            "time": "11:30",
            "comment": "Назначен после прозвона",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["manual_mode"] is True

    async with async_session() as session:
        user = await session.get(User, int(payload["candidate_id"]))
        assert user is not None
        assert user.fio == "Manual Silent Candidate"
        assert user.source == "manual_silent"
        assert user.telegram_id is None
        assert user.responsible_recruiter_id == recruiter_id
        assert user.candidate_status == CandidateStatus.INTERVIEW_SCHEDULED

        outbox_count = await session.scalar(select(func.count()).select_from(OutboxNotification))
        reminder_count = await session.scalar(select(func.count()).select_from(SlotReminderJob))
        assert outbox_count == 0
        assert reminder_count == 0


@pytest.mark.asyncio
async def test_manual_booking_can_bind_existing_free_slot_without_telegram(admin_app) -> None:
    city_id, recruiter_id = await _seed_recruiter_city(
        city_name="Silent Free Slot City",
        recruiter_name="Silent Free Slot Recruiter",
    )

    async with async_session() as session:
        user = User(
            fio="Existing Silent Candidate",
            city="Silent Free Slot City",
            source="manual_silent",
            telegram_id=None,
            candidate_status=CandidateStatus.TEST1_COMPLETED,
        )
        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            candidate_city_id=city_id,
            purpose="interview",
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            capacity=1,
            status=SlotStatus.FREE,
        )
        session.add_all([user, slot])
        await session.commit()
        await session.refresh(user)
        await session.refresh(slot)
        candidate_id = int(user.id)
        slot_id = int(slot.id)

    response = await asyncio.to_thread(
        _request,
        admin_app,
        "post",
        "/api/slots/manual-bookings",
        json={
            "candidate_id": candidate_id,
            "slot_id": slot_id,
            "city_id": city_id,
            "recruiter_id": recruiter_id,
            "date": "2031-05-21",
            "time": "14:00",
            "comment": "Привязка к свободному слоту без бота",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert int(payload["slot_id"]) == slot_id

    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        user = await session.get(User, candidate_id)
        assignment = await session.scalar(select(SlotAssignment).where(SlotAssignment.slot_id == slot_id))
        outbox_count = await session.scalar(select(func.count()).select_from(OutboxNotification))
        reminder_count = await session.scalar(select(func.count()).select_from(SlotReminderJob))

        assert slot is not None
        assert user is not None
        assert slot.status == SlotStatus.BOOKED
        assert slot.candidate_tg_id is None
        assert user.candidate_status == CandidateStatus.INTERVIEW_SCHEDULED
        assert assignment is not None
        assert assignment.origin == "manual_silent"
        assert outbox_count == 0
        assert reminder_count == 0
