from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.security import Principal, require_principal
from backend.core.db import async_session
from backend.domain.models import City, MessageTemplate, recruiter_city_association


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


async def _request_with_principal(app, principal: Principal, method: str, path: str, **kwargs):
    def _call():
        app.dependency_overrides[require_principal] = lambda: principal
        try:
            with TestClient(app) as client:
                client.auth = ("admin", "admin")
                return client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(require_principal, None)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_recruiter_template_list_is_city_scoped_and_global_read_only(admin_app) -> None:
    async with async_session() as session:
        city_allowed = City(name="RBAC City Allowed", tz="Europe/Moscow", active=True)
        city_blocked = City(name="RBAC City Blocked", tz="Europe/Moscow", active=True)
        session.add_all([city_allowed, city_blocked])
        await session.flush()
        await session.execute(
            recruiter_city_association.insert().values(recruiter_id=501, city_id=city_allowed.id)
        )
        session.add_all(
            [
                MessageTemplate(
                    key="slot_proposal_candidate",
                    locale="ru",
                    channel="tg",
                    city_id=None,
                    body_md="Глобальный шаблон",
                    version=1,
                    is_active=True,
                    updated_by="admin",
                ),
                MessageTemplate(
                    key="slot_proposal_candidate",
                    locale="ru",
                    channel="tg",
                    city_id=city_allowed.id,
                    body_md="Городской шаблон",
                    version=1,
                    is_active=True,
                    updated_by="admin",
                ),
                MessageTemplate(
                    key="slot_proposal_candidate",
                    locale="ru",
                    channel="tg",
                    city_id=city_blocked.id,
                    body_md="Чужой городской шаблон",
                    version=1,
                    is_active=True,
                    updated_by="admin",
                ),
                MessageTemplate(
                    key="recruiter_candidate_confirmed_notice",
                    locale="ru",
                    channel="tg",
                    city_id=city_allowed.id,
                    body_md="System only",
                    version=1,
                    is_active=True,
                    updated_by="admin",
                ),
            ]
        )
        await session.commit()

    recruiter = Principal(type="recruiter", id=501)
    response = await _request_with_principal(admin_app, recruiter, "get", "/api/message-templates")
    assert response.status_code == 200
    payload = response.json()
    keys = {(item["key"], item.get("city_id")) for item in payload["templates"]}
    assert ("slot_proposal_candidate", None) in keys
    assert ("slot_proposal_candidate", city_allowed.id) in keys
    assert ("slot_proposal_candidate", city_blocked.id) not in keys
    assert ("recruiter_candidate_confirmed_notice", city_allowed.id) not in keys

    global_template = next(item for item in payload["templates"] if item["key"] == "slot_proposal_candidate" and item.get("city_id") is None)
    city_template = next(item for item in payload["templates"] if item["key"] == "slot_proposal_candidate" and item.get("city_id") == city_allowed.id)
    assert global_template["can_edit"] is False
    assert city_template["can_edit"] is True


@pytest.mark.asyncio
async def test_recruiter_cannot_create_global_or_system_template(admin_app) -> None:
    async with async_session() as session:
        city = City(name="RBAC Create City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.flush()
        await session.execute(
            recruiter_city_association.insert().values(recruiter_id=777, city_id=city.id)
        )
        await session.commit()
        city_id = int(city.id)

    recruiter = Principal(type="recruiter", id=777)

    def _csrf_token() -> str:
        with TestClient(admin_app) as client:
            client.auth = ("admin", "admin")
            return client.get("/api/csrf").json()["token"]

    token = await asyncio.to_thread(_csrf_token)

    allowed = await _request_with_principal(
        admin_app,
        recruiter,
        "post",
        "/api/message-templates",
        headers={"x-csrf-token": token},
        json={
            "key": "slot_proposal_candidate",
            "locale": "ru",
            "channel": "tg",
            "city_id": city_id,
            "body": "Новый городской шаблон для кандидата",
            "is_active": True,
        },
    )
    assert allowed.status_code == 201
    assert allowed.json()["ok"] is True

    denied_global = await _request_with_principal(
        admin_app,
        recruiter,
        "post",
        "/api/message-templates",
        headers={"x-csrf-token": token},
        json={
            "key": "slot_proposal_candidate",
            "locale": "ru",
            "channel": "tg",
            "city_id": None,
            "body": "Попытка создать глобальный шаблон",
            "is_active": True,
        },
    )
    assert denied_global.status_code == 403

    denied_system = await _request_with_principal(
        admin_app,
        recruiter,
        "post",
        "/api/message-templates",
        headers={"x-csrf-token": token},
        json={
            "key": "recruiter_candidate_confirmed_notice",
            "locale": "ru",
            "channel": "tg",
            "city_id": city_id,
            "body": "Попытка править system template",
            "is_active": True,
        },
    )
    assert denied_system.status_code == 403
