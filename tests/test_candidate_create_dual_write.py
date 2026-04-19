from __future__ import annotations

import asyncio
from typing import Any

import pytest
from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services.candidates.application_dual_write import (
    CANDIDATE_CREATE_OPERATION_KIND,
    CANDIDATE_CREATE_PRODUCER_FAMILY,
)
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import (
    Application,
    ApplicationEvent,
    ApplicationIdempotencyKey,
    City,
    Recruiter,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app_factory(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("ALLOW_LEGACY_BASIC", "1")
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.helpers.schedule_warm_candidate_ai_outputs",
        lambda *args, **kwargs: None,
    )

    from backend.core import settings as settings_module

    def _factory(*, dual_write_enabled: bool) -> Any:
        if dual_write_enabled:
            monkeypatch.setenv("CANDIDATE_CREATE_DUAL_WRITE_ENABLED", "1")
        else:
            monkeypatch.delenv("CANDIDATE_CREATE_DUAL_WRITE_ENABLED", raising=False)
        settings_module.get_settings.cache_clear()
        return create_app()

    try:
        yield _factory
    finally:
        settings_module.get_settings.cache_clear()


async def _request(app, method: str, path: str, **kwargs) -> Any:
    def _call() -> Any:
        with TestClient(app) as client:
            client.auth = ("admin", "admin")
            headers = dict(kwargs.pop("headers", {}) or {})
            if method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
                if "x-csrf-token" not in {key.lower() for key in headers}:
                    headers["x-csrf-token"] = client.get("/api/csrf").json()["token"]
            if headers:
                kwargs["headers"] = headers
            return client.request(method, path, **kwargs)

    return await asyncio.to_thread(_call)


async def _seed_city_and_recruiter(*, city_name: str, recruiter_name: str) -> tuple[int, int]:
    async with async_session() as session:
        city = City(name=city_name, tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name=recruiter_name, tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        return int(city.id), int(recruiter.id)


async def _count_user_rows(*, fio: str) -> int:
    async with async_session() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(User).where(User.fio == fio)
            )
            or 0
        )


@pytest.mark.asyncio
async def test_api_create_candidate_dual_write_disabled_keeps_legacy_only(admin_app_factory) -> None:
    app = admin_app_factory(dual_write_enabled=False)
    city_id, recruiter_id = await _seed_city_and_recruiter(
        city_name="Legacy Only City",
        recruiter_name="Legacy Only Recruiter",
    )

    response = await _request(
        app,
        "post",
        "/api/candidates",
        json={
            "fio": "Legacy Only Candidate",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
        },
        follow_redirects=False,
    )

    assert response.status_code == 201
    candidate_id = int(response.json()["id"])

    async with async_session() as session:
        applications = (
            await session.execute(
                select(Application).where(Application.candidate_id == candidate_id)
            )
        ).scalars().all()
        events = (
            await session.execute(
                select(ApplicationEvent).where(ApplicationEvent.candidate_id == candidate_id)
            )
        ).scalars().all()
        ledger_rows = (
            await session.execute(
                select(ApplicationIdempotencyKey).where(
                    ApplicationIdempotencyKey.candidate_id == candidate_id
                )
            )
        ).scalars().all()

    assert applications == []
    assert events == []
    assert ledger_rows == []


@pytest.mark.asyncio
async def test_api_create_candidate_dual_write_creates_application_event_and_ledger(
    admin_app_factory,
) -> None:
    app = admin_app_factory(dual_write_enabled=True)
    city_id, recruiter_id = await _seed_city_and_recruiter(
        city_name="Dual Write City",
        recruiter_name="Dual Write Recruiter",
    )

    response = await _request(
        app,
        "post",
        "/api/candidates",
        json={
            "fio": "Dual Write Candidate",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
        },
        headers={"Idempotency-Key": "candidate-create-dual-write-1"},
        follow_redirects=False,
    )

    assert response.status_code == 201
    candidate_id = int(response.json()["id"])

    async with async_session() as session:
        application = await session.scalar(
            select(Application).where(Application.candidate_id == candidate_id)
        )
        events = (
            await session.execute(
                select(ApplicationEvent).where(ApplicationEvent.candidate_id == candidate_id)
            )
        ).scalars().all()
        ledger = await session.scalar(
            select(ApplicationIdempotencyKey).where(
                ApplicationIdempotencyKey.operation_kind == CANDIDATE_CREATE_OPERATION_KIND,
                ApplicationIdempotencyKey.producer_family
                == CANDIDATE_CREATE_PRODUCER_FAMILY,
                ApplicationIdempotencyKey.idempotency_key
                == "candidate-create-dual-write-1",
            )
        )

    assert application is not None
    assert application.requisition_id is None
    assert len(events) == 2
    assert {event.event_type for event in events} == {"candidate.created", "application.created"}
    assert all(event.application_id == application.id for event in events)
    assert ledger is not None
    assert ledger.candidate_id == candidate_id
    assert ledger.application_id == application.id
    candidate_created = next(event for event in events if event.event_type == "candidate.created")
    assert ledger.event_id == candidate_created.event_id
    assert ledger.status == "completed"


@pytest.mark.asyncio
async def test_api_create_candidate_dual_write_reuses_same_key_without_telegram(
    admin_app_factory,
) -> None:
    app = admin_app_factory(dual_write_enabled=True)
    city_id, recruiter_id = await _seed_city_and_recruiter(
        city_name="Dual Write Reuse City",
        recruiter_name="Dual Write Reuse Recruiter",
    )
    payload = {
        "fio": "Dual Write Reuse Candidate",
        "city_id": city_id,
        "recruiter_id": recruiter_id,
    }
    headers = {"Idempotency-Key": "candidate-create-reuse-no-telegram"}

    first = await _request(
        app,
        "post",
        "/api/candidates",
        json=payload,
        headers=headers,
        follow_redirects=False,
    )
    second = await _request(
        app,
        "post",
        "/api/candidates",
        json=payload,
        headers=headers,
        follow_redirects=False,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert int(second.json()["id"]) == int(first.json()["id"])
    assert await _count_user_rows(fio="Dual Write Reuse Candidate") == 1

    async with async_session() as session:
        candidate_id = int(first.json()["id"])
        application_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.candidate_id == candidate_id)
            )
            or 0
        )
        event_count = int(
            await session.scalar(
                select(func.count())
                .select_from(ApplicationEvent)
                .where(ApplicationEvent.candidate_id == candidate_id)
            )
            or 0
        )

    assert application_count == 1
    assert event_count == 2


@pytest.mark.asyncio
async def test_api_create_candidate_dual_write_reuses_same_key_with_telegram(
    admin_app_factory,
) -> None:
    app = admin_app_factory(dual_write_enabled=True)
    city_id, recruiter_id = await _seed_city_and_recruiter(
        city_name="Dual Write Telegram City",
        recruiter_name="Dual Write Telegram Recruiter",
    )
    payload = {
        "fio": "Dual Write Telegram Candidate",
        "city_id": city_id,
        "recruiter_id": recruiter_id,
        "telegram_id": 79991239901,
    }
    headers = {"Idempotency-Key": "candidate-create-reuse-telegram"}

    first = await _request(
        app,
        "post",
        "/api/candidates",
        json=payload,
        headers=headers,
        follow_redirects=False,
    )
    second = await _request(
        app,
        "post",
        "/api/candidates",
        json=payload,
        headers=headers,
        follow_redirects=False,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert int(second.json()["id"]) == int(first.json()["id"])

    async with async_session() as session:
        candidate_id = int(first.json()["id"])
        user = await session.get(User, candidate_id)
        application_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.candidate_id == candidate_id)
            )
            or 0
        )
        event_count = int(
            await session.scalar(
                select(func.count())
                .select_from(ApplicationEvent)
                .where(ApplicationEvent.candidate_id == candidate_id)
            )
            or 0
        )

    assert user is not None
    assert user.telegram_id == 79991239901
    assert application_count == 1
    assert event_count == 2


@pytest.mark.asyncio
async def test_api_create_candidate_dual_write_conflicts_on_same_key_new_payload(
    admin_app_factory,
) -> None:
    app = admin_app_factory(dual_write_enabled=True)
    city_id, recruiter_id = await _seed_city_and_recruiter(
        city_name="Dual Write Conflict City",
        recruiter_name="Dual Write Conflict Recruiter",
    )
    headers = {"Idempotency-Key": "candidate-create-conflict"}

    first = await _request(
        app,
        "post",
        "/api/candidates",
        json={
            "fio": "Dual Write Conflict Candidate A",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
        },
        headers=headers,
        follow_redirects=False,
    )
    second = await _request(
        app,
        "post",
        "/api/candidates",
        json={
            "fio": "Dual Write Conflict Candidate B",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
        },
        headers=headers,
        follow_redirects=False,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"] == "idempotency_conflict"
    assert await _count_user_rows(fio="Dual Write Conflict Candidate A") == 1
    assert await _count_user_rows(fio="Dual Write Conflict Candidate B") == 0
