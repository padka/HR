import asyncio
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.core.sanitizers import sanitize_plain_text
from backend.domain import models


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def cities_admin_app(monkeypatch) -> Any:
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
async def test_create_city_invalid_timezone_returns_422(cities_admin_app) -> None:
    response = await _async_request(
        cities_admin_app,
        "post",
        "/cities/create",
        data={"name": "Invalid City", "tz": "Invalid/Zone"},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "идентификатор часового пояса" in response.text


@pytest.mark.asyncio
async def test_create_city_accepts_valid_iana_timezone(cities_admin_app) -> None:
    response = await _async_request(
        cities_admin_app,
        "post",
        "/cities/create",
        data={"name": "New York", "tz": "America/New_York"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    async with async_session() as session:
        city = await session.scalar(select(models.City).where(models.City.name == "New York"))
        assert city is not None
        assert city.tz == "America/New_York"


@pytest.mark.asyncio
async def test_city_plan_validation_rejects_negative(cities_admin_app) -> None:
    async with async_session() as session:
        city = models.City(name="Negative City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    response = await _async_request(
        cities_admin_app,
        "post",
        f"/cities/{city_id}/settings",
        json={"plan_week": -1, "plan_month": 10, "templates": {}},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload.get("ok") is False
    error: Dict[str, str] = payload.get("error", {})
    assert error.get("field") == "plan_week"
    assert "Введите целое неотрицательное число" in error.get("message", "")


@pytest.mark.asyncio
async def test_city_plan_validation_rejects_fractional(cities_admin_app) -> None:
    async with async_session() as session:
        city = models.City(name="Fractional City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    response = await _async_request(
        cities_admin_app,
        "post",
        f"/cities/{city_id}/settings",
        json={"plan_week": "7.5", "plan_month": None, "templates": {}},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload.get("ok") is False
    error: Dict[str, str] = payload.get("error", {})
    assert error.get("field") == "plan_week"
    assert "Введите целое неотрицательное число" in error.get("message", "")


@pytest.mark.asyncio
async def test_city_plan_update_returns_normalized_payload(cities_admin_app) -> None:
    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Owner",
            tz="Europe/Moscow",
            active=True,
        )
        city = models.City(name="Payload City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        payload = {
            "criteria": "Some criteria",
            "experts": "",
            "plan_week": "08",
            "plan_month": 16,
            "templates": {},
            "responsible_recruiter_id": recruiter.id,
        }

    response = await _async_request(
        cities_admin_app,
        "post",
        f"/cities/{city.id}/settings",
        json=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    city_info = data.get("city")
    assert city_info is not None
    assert city_info.get("plan_week") == 8
    assert city_info.get("plan_month") == 16
    assert city_info.get("criteria") == "Some criteria"
    assert city_info.get("responsible_recruiter_id") == recruiter.id
    responsible = city_info.get("responsible_recruiter") or {}
    assert responsible.get("id") == recruiter.id
    assert responsible.get("name") == "Owner"


@pytest.mark.asyncio
async def test_city_name_is_sanitized_for_storage_and_api(cities_admin_app) -> None:
    raw_name = "Test<script>alert(1)</script>"
    response = await _async_request(
        cities_admin_app,
        "post",
        "/cities/create",
        data={"name": raw_name, "tz": "Europe/Moscow"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    expected_sanitized = sanitize_plain_text(raw_name)
    async with async_session() as session:
        city = await session.scalar(select(models.City).where(models.City.name == expected_sanitized))
        assert city is not None
        assert city.name == expected_sanitized
        assert city.name_plain == raw_name
        assert str(city.display_name) == expected_sanitized

    payload = await _async_request(cities_admin_app, "get", "/api/cities")
    assert payload.status_code == 200
    cities = payload.json()
    sanitized_entry = next((item for item in cities if item["name"] == raw_name), None)
    assert sanitized_entry is not None
    assert sanitized_entry["name_html"] == expected_sanitized
