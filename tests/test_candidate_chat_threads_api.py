import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.security import Principal, require_principal
from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import ChatMessage, ChatMessageDirection, ChatMessageStatus
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter


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


async def _async_request_with_principal(
    app,
    principal: Principal,
    method: str,
    path: str,
    **kwargs,
) -> Any:
    def _call() -> Any:
        app.dependency_overrides[require_principal] = lambda: principal
        try:
            with TestClient(app) as client:
                client.auth = ("admin", "admin")
                return client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(require_principal, None)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_candidate_chat_threads_count_unread_and_mark_read(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Чатовый город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Chat Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)

        recruiter_id = recruiter.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=79990010001,
        fio="Chat Candidate",
        city="Чатовый город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        session.add_all(
            [
                ChatMessage(
                    candidate_id=candidate.id,
                    telegram_user_id=candidate.telegram_id,
                    direction=ChatMessageDirection.INBOUND.value,
                    channel="telegram",
                    text="Добрый день",
                    status=ChatMessageStatus.RECEIVED.value,
                    created_at=now - timedelta(minutes=5),
                ),
                ChatMessage(
                    candidate_id=candidate.id,
                    telegram_user_id=candidate.telegram_id,
                    direction=ChatMessageDirection.INBOUND.value,
                    channel="telegram",
                    text="Хочу перенести время",
                    status=ChatMessageStatus.RECEIVED.value,
                    created_at=now - timedelta(minutes=1),
                ),
            ]
        )
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)
    list_response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads",
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    thread = next(item for item in payload["threads"] if item["candidate_id"] == candidate.id)
    assert thread["unread_count"] == 2
    assert thread["last_message"]["direction"] == "inbound"

    mark_response = await _async_request_with_principal(
        admin_app,
        principal,
        "post",
        f"/api/candidate-chat/threads/{candidate.id}/read",
    )
    assert mark_response.status_code == 200
    assert mark_response.json()["ok"] is True

    list_after = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads",
    )
    assert list_after.status_code == 200
    payload_after = list_after.json()
    thread_after = next(item for item in payload_after["threads"] if item["candidate_id"] == candidate.id)
    assert thread_after["unread_count"] == 0


@pytest.mark.asyncio
async def test_candidate_chat_threads_updates_returns_new_activity(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Апдейт город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Update Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=79990010002,
        fio="Update Candidate",
        city="Апдейт город",
        initial_status=CandidateStatus.WAITING_SLOT,
        responsible_recruiter_id=recruiter_id,
    )

    message_time = datetime.now(timezone.utc) - timedelta(seconds=2)
    async with async_session() as session:
        session.add(
            ChatMessage(
                candidate_id=candidate.id,
                telegram_user_id=candidate.telegram_id,
                direction=ChatMessageDirection.INBOUND.value,
                channel="telegram",
                text="Есть ли время завтра?",
                status=ChatMessageStatus.RECEIVED.value,
                created_at=message_time,
            )
        )
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)
    since = quote((message_time - timedelta(minutes=1)).isoformat(), safe="")
    response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        f"/api/candidate-chat/threads/updates?since={since}&timeout=5",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] is True
    thread = next(item for item in payload["threads"] if item["candidate_id"] == candidate.id)
    assert thread["last_message"]["text"] == "Есть ли время завтра?"
