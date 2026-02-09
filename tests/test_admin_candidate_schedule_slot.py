import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.status import CandidateStatus
from backend.domain.slot_assignment_service import create_slot_assignment, request_reschedule


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app(monkeypatch) -> Any:
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


async def _async_request(app, method: str, path: str, **kwargs) -> Any:
    def _call() -> Any:
        with TestClient(app) as client:
            client.auth = ("admin", "admin")
            return client.request(method, path, **kwargs)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_schedule_slot_conflict_returns_validation_error(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777001,
        fio="API Кандидат",
        city="Москва",
        username="api_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        # Create a BOOKED slot that conflicts with the time we'll try to schedule
        # Use timezone-aware UTC datetime to ensure proper conflict detection
        conflict_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2024, 7, 5, 9, 0, tzinfo=timezone.utc),  # 09:00 UTC = 12:00 Moscow
            duration_min=60,
            status=models.SlotStatus.BOOKED,  # Already booked - creates conflict
            candidate_tg_id=999999,  # Different candidate
            candidate_fio="Другой кандидат",
            candidate_tz="Europe/Moscow",
        )
        session.add(conflict_slot)
        await session.commit()
        recruiter_id = recruiter.id
        city_id = city.id

    response = await _async_request(
        admin_app,
        "post",
        f"/candidates/{candidate.id}/schedule-slot",
        data={
            "recruiter_id": recruiter_id,
            "city_id": city_id,
            "date": "2024-07-05",
            "time": "12:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_schedule_slot_reuses_active_reschedule_assignment(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777002,
        fio="API Кандидат 2",
        city="Москва",
        username="api_candidate2",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter 2", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2031, 7, 5, 9, 0, tzinfo=timezone.utc),
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        slot_id = slot.id
        recruiter_id = recruiter.id
        city_id = city.id

    # Offer the initial slot via SlotAssignment, then request reschedule.
    offer = await create_slot_assignment(
        slot_id=slot_id,
        candidate_id=candidate.candidate_id,
        candidate_tg_id=candidate.telegram_id,
        candidate_tz="Europe/Moscow",
        created_by="admin",
    )
    assert offer.ok is True
    assignment_id = int(offer.payload["slot_assignment_id"])
    reschedule_token = str(offer.payload["reschedule_token"])

    res = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
        requested_start_utc=datetime(2031, 7, 6, 9, 0, tzinfo=timezone.utc),
        requested_tz="Europe/Moscow",
        comment="need another time",
    )
    assert res.ok is True

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-slot",
        json={
            "recruiter_id": recruiter_id,
            "city_id": city_id,
            "date": "2031-07-06",
            "time": "12:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending_offer"
    assert int(payload.get("slot_assignment_id") or 0) == assignment_id
