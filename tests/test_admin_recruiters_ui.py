import asyncio
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain import models


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
    return create_app()


async def _async_request(app, method: str, path: str, **kwargs) -> Any:
    def _call() -> Any:
        with TestClient(app) as client:
            client.auth = ("admin", "admin")
            return client.request(method, path, **kwargs)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_create_recruiter_duplicate_chat_id_returns_validation_message(admin_app) -> None:
    first_payload = {
        "name": "Recruiter One",
        "tz": "Europe/Moscow",
        "telemost": "",
        "tg_chat_id": "123456",
        "active": "1",
    }

    response_ok = await _async_request(
        admin_app,
        "post",
        "/recruiters/create",
        data=first_payload,
        allow_redirects=False,
    )
    assert response_ok.status_code == 303

    second_payload = {
        "name": "Recruiter Duplicate",
        "tz": "Europe/Moscow",
        "telemost": "",
        "tg_chat_id": "123456",
        "active": "1",
    }

    response_error = await _async_request(
        admin_app,
        "post",
        "/recruiters/create",
        data=second_payload,
        allow_redirects=False,
    )

    assert response_error.status_code == 400
    assert "Telegram chat ID уже существует" in response_error.text

    async with async_session() as session:
        recruiters = (await session.scalars(select(models.Recruiter))).all()
        assert len(recruiters) == 1
        assert recruiters[0].tg_chat_id == 123456


@pytest.mark.asyncio
async def test_update_recruiter_duplicate_chat_id_returns_validation_message(admin_app) -> None:
    async with async_session() as session:
        recruiter_one = models.Recruiter(
            name="First",
            tz="Europe/Moscow",
            tg_chat_id=999000,
            active=True,
        )
        recruiter_two = models.Recruiter(
            name="Second",
            tz="Europe/Moscow",
            tg_chat_id=888000,
            active=True,
        )
        session.add_all([recruiter_one, recruiter_two])
        await session.commit()
        await session.refresh(recruiter_one)
        await session.refresh(recruiter_two)
        recruiter_two_id = recruiter_two.id

    update_payload: Dict[str, Optional[str]] = {
        "name": "Second",
        "tz": "Europe/Moscow",
        "telemost": "",
        "tg_chat_id": "999000",
        "active": "1",
    }

    response_error = await _async_request(
        admin_app,
        "post",
        f"/recruiters/{recruiter_two_id}/update",
        data=update_payload,
        allow_redirects=False,
    )

    assert response_error.status_code == 400
    assert "Telegram chat ID уже существует" in response_error.text

    async with async_session() as session:
        updated_two = await session.get(models.Recruiter, recruiter_two_id)
        assert updated_two is not None
        assert updated_two.tg_chat_id == 888000


@pytest.mark.asyncio
async def test_update_recruiter_single_city_checkbox_value(admin_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Cityless",
            tz="Europe/Moscow",
            active=True,
        )
        city = models.City(name="Test City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        recruiter_id = recruiter.id
        city_id = city.id

    response_ok = await _async_request(
        admin_app,
        "post",
        f"/recruiters/{recruiter_id}/update",
        data={
            "name": "Cityless",
            "tz": "Europe/Moscow",
            "telemost": "",
            "tg_chat_id": "",
            "active": "1",
            "cities": str(city_id),
        },
        allow_redirects=False,
    )

    assert response_ok.status_code == 303

    async with async_session() as session:
        updated_city = await session.get(models.City, city_id)
        assert updated_city is not None
        assert updated_city.responsible_recruiter_id == recruiter_id
