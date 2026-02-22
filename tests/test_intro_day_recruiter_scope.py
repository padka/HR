import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.security import Principal, require_principal
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.status import CandidateStatus


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def recruiter_scoped_app(monkeypatch) -> Any:
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


async def _request_with_recruiter_principal(
    app,
    recruiter_id: int,
    method: str,
    path: str,
    **kwargs,
):
    def _call() -> Any:
        app.dependency_overrides[require_principal] = lambda: Principal(type="recruiter", id=recruiter_id)
        try:
            with TestClient(app) as client:
                return client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(require_principal, None)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_recruiter_can_schedule_intro_day_for_self_even_if_city_has_other_default(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990001,
        fio="Шеншин Михаил Алексеевич",
        city="Москва",
        username="shenshin_test",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        primary = models.Recruiter(name="Primary Recruiter", tz="Europe/Moscow", active=True)
        actor = models.Recruiter(name="Actor Recruiter", tz="Europe/Moscow", active=True)
        primary.cities.append(city)
        actor.cities.append(city)
        session.add_all([city, primary, actor])
        await session.flush()
        city.responsible_recruiter_id = primary.id
        await session.commit()
        await session.refresh(actor)

        actor_id = actor.id

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        actor_id,
        "post",
        f"/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-23",
            "time": "10:00",
            "custom_message": "Тестовое приглашение",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("ok") is True

    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot)
            .where(models.Slot.candidate_tg_id == candidate.telegram_id)
            .order_by(models.Slot.id.desc())
        )
        assert slot is not None
        assert slot.recruiter_id == actor_id
        assert (slot.purpose or "").lower() == "intro_day"


@pytest.mark.asyncio
async def test_recruiter_can_schedule_intro_day_via_api_without_recruiter_id(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990002,
        fio="Шеншин Михаил Алексеевич",
        city="Москва",
        username="shenshin_test_api",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        primary = models.Recruiter(name="Primary Recruiter API", tz="Europe/Moscow", active=True)
        actor = models.Recruiter(name="Actor Recruiter API", tz="Europe/Moscow", active=True)
        primary.cities.append(city)
        actor.cities.append(city)
        session.add_all([city, primary, actor])
        await session.flush()
        city.responsible_recruiter_id = primary.id
        await session.commit()
        await session.refresh(actor)
        actor_id = actor.id

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        actor_id,
        "post",
        f"/api/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-23",
            "time": "10:00",
            "custom_message": "Тестовое приглашение",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("ok") is True

    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot)
            .where(models.Slot.candidate_tg_id == candidate.telegram_id)
            .order_by(models.Slot.id.desc())
        )
        assert slot is not None
        assert slot.recruiter_id == actor_id
        assert (slot.purpose or "").lower() == "intro_day"
