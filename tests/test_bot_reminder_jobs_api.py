from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain import models


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


class _DummyReminderService:
    async def reschedule_active_slots(self) -> dict[str, int]:
        return {"scheduled": 0, "failed": 0}


@pytest.fixture
def reminder_jobs_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = _DummyReminderService()
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


def test_bot_reminder_jobs_degraded_when_db_unavailable(reminder_jobs_app):
    with TestClient(reminder_jobs_app) as client:
        reminder_jobs_app.state.db_available = False
        response = client.get(
            "/api/bot/reminders/jobs?limit=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["degraded"] is True


def test_bot_reminder_jobs_lists_upcoming_jobs(reminder_jobs_app):
    import asyncio
    from datetime import datetime, timedelta, timezone

    def _run(coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    async def _seed() -> int:
        async with async_session() as session:
            recruiter = models.Recruiter(name="R", tz="Europe/Moscow", active=True)
            city = models.City(name="C", tz="Europe/Moscow", active=True)
            session.add_all([recruiter, city])
            await session.commit()
            await session.refresh(recruiter)
            await session.refresh(city)

            slot = models.Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name=city.tz,
                start_utc=datetime.now(timezone.utc) + timedelta(days=3),
                duration_min=60,
                status=models.SlotStatus.BOOKED,
                candidate_tg_id=12345,
                candidate_fio="Candidate",
            )
            session.add(slot)
            await session.commit()
            await session.refresh(slot)

            job = models.SlotReminderJob(
                slot_id=slot.id,
                kind="confirm_2h",
                job_id=f"slot:{slot.id}:confirm_2h",
                scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return int(job.id)

    job_id = _run(_seed())

    with TestClient(reminder_jobs_app) as client:
        response = client.get(
            "/api/bot/reminders/jobs?limit=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["degraded"] is False
    assert any(item["id"] == job_id for item in payload["items"])


def test_bot_reminder_jobs_resync_endpoint(reminder_jobs_app):
    with TestClient(reminder_jobs_app) as client:
        response = client.post(
            "/api/bot/reminders/resync",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["scheduled"] == 0
    assert payload["failed"] == 0

