import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
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
        follow_redirects=False,
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
        follow_redirects=False,
    )

    assert response_error.status_code == 400
    assert "Telegram chat ID уже существует" in response_error.text

    async with async_session() as session:
        recruiters = (await session.scalars(select(models.Recruiter))).all()
        assert len(recruiters) == 1
        assert recruiters[0].tg_chat_id == 123456


@pytest.mark.asyncio
async def test_create_recruiter_invalid_chat_id_returns_422(admin_app) -> None:
    payload = {
        "name": "Recruiter Invalid",
        "tz": "Europe/Moscow",
        "telemost": "",
        "tg_chat_id": "12abc",
        "active": "1",
    }

    response = await _async_request(
        admin_app,
        "post",
        "/recruiters/create",
        data=payload,
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "chat_id: только цифры" in response.text


@pytest.mark.asyncio
async def test_create_recruiter_invalid_telemost_returns_422(admin_app) -> None:
    payload = {
        "name": "Recruiter Invalid Link",
        "tz": "Europe/Moscow",
        "telemost": "not-a-url",
        "tg_chat_id": "",
        "active": "1",
    }

    response = await _async_request(
        admin_app,
        "post",
        "/recruiters/create",
        data=payload,
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Ссылка: укажите корректный URL" in response.text


@pytest.mark.asyncio
async def test_update_recruiter_invalid_chat_id_returns_422(admin_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Existing",
            tz="Europe/Moscow",
            active=True,
        )
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    response = await _async_request(
        admin_app,
        "post",
        f"/recruiters/{recruiter_id}/update",
        data={
            "name": "Existing",
            "tz": "Europe/Moscow",
            "telemost": "",
            "tg_chat_id": "tg-123",
            "active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "chat_id: только цифры" in response.text


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
        follow_redirects=False,
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
        follow_redirects=False,
    )

    assert response_ok.status_code == 303

    async with async_session() as session:
        link = await session.scalar(
            select(models.recruiter_city_association.c.city_id)
            .where(models.recruiter_city_association.c.city_id == city_id)
            .where(models.recruiter_city_association.c.recruiter_id == recruiter_id)
        )
        assert link == city_id


@pytest.mark.asyncio
async def test_api_recruiters_includes_city_ids(admin_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(name="API Cities", tz="Europe/Moscow", active=True)
        city = models.City(name="API Сity", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

    response = await _async_request(admin_app, "get", "/api/recruiters")
    assert response.status_code == 200
    payload = response.json()
    found = next((item for item in payload if item.get("id") == recruiter.id), None)
    assert found is not None
    assert found.get("city_ids") == [city.id]


@pytest.mark.asyncio
async def test_api_candidate_detail_includes_report_urls(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=424242,
        fio="API Candidate",
        city="Воронеж",
    )
    await candidate_services.update_candidate_reports(
        candidate.id,
        test1_path="reports/1/test1.txt",
        test2_path=None,
    )

    response = await _async_request(admin_app, "get", f"/api/candidates/{candidate.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == candidate.id
    assert payload["test1_report_url"] == f"/candidates/{candidate.id}/reports/test1"
    assert payload["test2_report_url"] is None
    assert "test_results" in payload
    assert payload.get("telemost_url") is None


@pytest.mark.asyncio
async def test_api_create_recruiter_accepts_multiple_cities(admin_app) -> None:
    async with async_session() as session:
        city_one = models.City(name="Create City 1", tz="Europe/Moscow", active=True)
        city_two = models.City(name="Create City 2", tz="Asia/Novosibirsk", active=True)
        session.add_all([city_one, city_two])
        await session.commit()
        await session.refresh(city_one)
        await session.refresh(city_two)

    payload = {
        "name": "API Creator",
        "tz": "Europe/Moscow",
        "telemost": "",
        "tg_chat_id": 123456789,
        "active": True,
        "city_ids": [city_one.id, city_two.id],
    }

    response = await _async_request(
        admin_app,
        "post",
        "/api/recruiters",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert sorted(data.get("city_ids")) == sorted([city_one.id, city_two.id])
    assert data.get("name") == "API Creator"
    assert response.headers.get("Location") == f"/api/recruiters/{data.get('id')}"

    async with async_session() as session:
        stored = await session.scalar(
            select(models.Recruiter)
            .options(selectinload(models.Recruiter.cities))
            .where(models.Recruiter.id == data["id"])
        )
        assert stored is not None
        assert sorted(city.id for city in stored.cities) == sorted([city_one.id, city_two.id])


@pytest.mark.asyncio
async def test_api_update_recruiter_replaces_city_ids(admin_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(name="Updater", tz="Europe/Moscow", active=True)
        city_a = models.City(name="City A", tz="Europe/Moscow", active=True)
        city_b = models.City(name="City B", tz="Asia/Yekaterinburg", active=True)
        recruiter.cities.append(city_a)
        session.add_all([recruiter, city_a, city_b])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city_a)
        await session.refresh(city_b)
        recruiter_id = recruiter.id

    payload = {
        "name": "Updater",
        "tz": "Europe/Moscow",
        "telemost": "",
        "tg_chat_id": None,
        "active": True,
        "city_ids": [city_b.id],
    }

    response = await _async_request(
        admin_app,
        "put",
        f"/api/recruiters/{recruiter_id}",
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("city_ids") == [city_b.id]

    async with async_session() as session:
        stored = await session.scalar(
            select(models.Recruiter)
            .options(selectinload(models.Recruiter.cities))
            .where(models.Recruiter.id == recruiter_id)
        )
        assert stored is not None
        assert [city.id for city in stored.cities] == [city_b.id]

    # ensure city can be unassigned
    clear_payload = {
        "name": "Updater",
        "tz": "Europe/Moscow",
        "telemost": "",
        "tg_chat_id": None,
        "active": True,
        "city_ids": [],
    }
    response_clear = await _async_request(
        admin_app,
        "put",
        f"/api/recruiters/{recruiter_id}",
        json=clear_payload,
    )
    assert response_clear.status_code == 200
    data_clear = response_clear.json()
    assert data_clear.get("city_ids") == []

    async with async_session() as session:
        stored_clear = await session.scalar(
            select(models.Recruiter)
            .options(selectinload(models.Recruiter.cities))
            .where(models.Recruiter.id == recruiter_id)
        )
        assert stored_clear is not None
        assert stored_clear.cities == []
