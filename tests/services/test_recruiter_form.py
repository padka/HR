import asyncio
from typing import Dict, Iterable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain import models


def _patch_bot_setup(monkeypatch):
    from backend.core import settings as settings_module

    class DummyReminderService:
        def start(self) -> None:
            return None

        async def shutdown(self) -> None:
            return None

        async def sync_jobs(self) -> None:
            return None

        async def schedule_for_slot(self, *_args, **_kwargs):
            return None

        async def cancel_for_slot(self, *_args, **_kwargs):
            return None

        def stats(self):
            return {"total": 0, "reminders": 0, "confirm_prompts": 0}

    class DummyIntegration:
        def __init__(self, reminder_service):
            self.reminder_service = reminder_service
            self.state_manager = None
            self.bot = None
            self.bot_service = None
            self.integration_switch = None

        async def shutdown(self) -> None:
            await self.reminder_service.shutdown()

    async def fake_setup_bot_state(app):
        reminder = DummyReminderService()
        integration = DummyIntegration(reminder)
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = reminder
        return integration

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup_bot_state)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup_bot_state)


async def _form_request(app, method: str, path: str, *, data: Iterable[tuple[str, str]]):
    def _call():
        with TestClient(app) as client:
            client.auth = ("admin", "secret")
            payload: Dict[str, object] = {}
            for key, value in data:
                if key in payload:
                    existing = payload[key]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        payload[key] = [existing, value]
                else:
                    payload[key] = value
            return client.request(method, path, data=payload, follow_redirects=False)

    response = await asyncio.to_thread(_call)
    return response


@pytest.mark.asyncio
async def test_recruiter_create_form_accepts_optional_fields(monkeypatch):
    _patch_bot_setup(monkeypatch)
    app = create_app()

    async with async_session() as session:
        city = models.City(name="Form City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

    response = await _form_request(
        app,
        "post",
        "/recruiters/create",
        data=[
            ("name", "Анна"),
            ("tz", "Europe/Berlin"),
            ("telemost", ""),
            ("tg_chat_id", ""),
            ("active", "1"),
        ],
    )
    assert response.status_code == 303

    async with async_session() as session:
        recruiter = await session.scalar(select(models.Recruiter).where(models.Recruiter.name == "Анна"))
        assert recruiter is not None
        assert recruiter.tz == "Europe/Berlin"
        assert recruiter.telemost_url is None
        assert recruiter.tg_chat_id is None
        assert recruiter.active is True


@pytest.mark.asyncio
async def test_recruiter_create_form_handles_invalid_timezone(monkeypatch):
    _patch_bot_setup(monkeypatch)
    app = create_app()

    response = await _form_request(
        app,
        "post",
        "/recruiters/create",
        data=[
            ("name", "Мария"),
            ("tz", "Mars/Olympus"),
            ("telemost", ""),
            ("tg_chat_id", ""),
        ],
    )
    assert response.status_code == 400
    body = response.text
    assert "корректный часовой пояс" in body

    async with async_session() as session:
        recruiter = await session.scalar(select(models.Recruiter).where(models.Recruiter.name == "Мария"))
        assert recruiter is None


@pytest.mark.asyncio
async def test_recruiter_create_form_parses_checkbox_and_cities(monkeypatch):
    _patch_bot_setup(monkeypatch)
    app = create_app()

    async with async_session() as session:
        city_a = models.City(name="Alpha", tz="Europe/Moscow", active=True)
        city_b = models.City(name="Beta", tz="Europe/Samara", active=True)
        session.add_all([city_a, city_b])
        await session.commit()
        await session.refresh(city_a)
        await session.refresh(city_b)
        city_a_id = city_a.id
        city_b_id = city_b.id

    response = await _form_request(
        app,
        "post",
        "/recruiters/create",
        data=[
            ("name", "Иван"),
            ("tz", "Europe/Moscow"),
            ("telemost", "https://telemost.example.com"),
            ("tg_chat_id", "123456"),
            ("cities", str(city_a_id)),
            ("cities", str(city_b_id)),
        ],
    )
    assert response.status_code == 303

    async with async_session() as session:
        recruiter = await session.scalar(select(models.Recruiter).where(models.Recruiter.name == "Иван"))
        assert recruiter is not None
        assert recruiter.active is False
        cities = await session.scalars(
            select(models.City).where(models.City.id.in_([city_a_id, city_b_id]))
        )
        linked = {c.responsible_recruiter_id for c in cities}
        assert linked == {recruiter.id}
