import asyncio
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates import services as candidate_services


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
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        conflict_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2024, 7, 5, 9, 0),  # stored as naive UTC
            duration_min=60,
            status=models.SlotStatus.FREE,
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
