from __future__ import annotations

from types import SimpleNamespace

import pytest
from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services.bot_service import (
    BotSendResult,
    BotService,
    IntegrationSwitch,
)
from backend.apps.bot.state_store import build_state_manager
from backend.core.db import async_session
from backend.core.messenger.protocol import InlineButton
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import ChatMessage, ChatMessageStatus, User
from backend.domain.candidates.status import CandidateStatus
from fastapi.testclient import TestClient
from sqlalchemy import select


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password, "redirect_to": "/"},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}


@pytest.mark.asyncio
async def test_bot_service_switch_blocks_dispatch(monkeypatch):
    state_manager = build_state_manager(redis_url=None, ttl_seconds=60)

    async def fake_start_test2(_user_id: int) -> None:
        return None

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.bot_service.start_test2",
        fake_start_test2,
    )

    switch = IntegrationSwitch(initial=True)
    service = BotService(
        state_manager=state_manager,
        enabled=True,
        configured=True,
        integration_switch=switch,
        required=False,
    )

    switch.set(False)

    result: BotSendResult = await service.send_test2(
        candidate_id=101,
        candidate_tz="Europe/Moscow",
        candidate_city=1,
        candidate_name="Тест",
    )

    assert result.status == "skipped:disabled"

    await state_manager.clear()
    await state_manager.close()


@pytest.mark.asyncio
async def test_bot_service_send_test2_logs_failed_max_delivery_when_required(monkeypatch):
    state_manager = build_state_manager(redis_url=None, ttl_seconds=60)
    candidate = await candidate_services.create_or_update_user(
        telegram_id=901150,
        fio="MAX Test2 Failure Candidate",
        city="Москва",
        username="max_test2_failure",
        initial_status=CandidateStatus.INTERVIEW_CONFIRMED,
    )
    async with async_session() as session:
        persisted = await session.get(User, candidate.id)
        assert persisted is not None
        persisted.telegram_id = None
        persisted.telegram_user_id = None
        persisted.max_user_id = "129613758"
        await session.commit()

    class _FailedAdapter:
        async def send_message(self, *_args, **_kwargs):
            return SimpleNamespace(
                success=False,
                error="HTTP 403: error.dialog.suspended",
                message_id=None,
            )

    async def _fake_mark_max_candidate_test2_ready(*_args, **_kwargs):
        return None

    async def _fake_ensure_max_adapter(**_kwargs):
        return _FailedAdapter()

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.bot_service.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.bot_service.mark_max_candidate_test2_ready",
        _fake_mark_max_candidate_test2_ready,
    )

    service = BotService(
        state_manager=state_manager,
        enabled=True,
        configured=True,
        integration_switch=IntegrationSwitch(initial=True),
        required=False,
    )

    result = await service.send_test2(
        candidate_id=0,
        candidate_tz="Europe/Moscow",
        candidate_city=1,
        candidate_name="MAX Test2 Failure Candidate",
        required=True,
        candidate_public_id=candidate.candidate_id,
        max_user_id="129613758",
    )

    assert result.ok is False
    assert result.status == "skipped:error"
    assert "error.dialog.suspended" in str(result.error)

    async with async_session() as session:
        message = await session.scalar(
            select(ChatMessage)
            .where(
                ChatMessage.candidate_id == candidate.id,
                ChatMessage.channel == "max",
                ChatMessage.status == ChatMessageStatus.FAILED.value,
            )
            .order_by(ChatMessage.id.desc())
        )
    assert message is not None
    assert message.error == "HTTP 403: error.dialog.suspended"
    assert message.client_request_id == "max:test2:129613758:none:failed"

    await state_manager.clear()
    await state_manager.close()


@pytest.mark.asyncio
async def test_bot_service_send_test2_prefers_candidate_public_id_and_uses_callback_only_for_max(monkeypatch):
    state_manager = build_state_manager(redis_url=None, ttl_seconds=60)
    stale_max_user_id = "129613759-old"
    primary_max_user_id = "129613759-primary"
    older_candidate = await candidate_services.create_or_update_user(
        telegram_id=901151,
        fio="MAX Public Id Older",
        city="Москва",
        username="max_public_id_older",
        initial_status=CandidateStatus.INTERVIEW_DECLINED,
    )
    primary_candidate = await candidate_services.create_or_update_user(
        telegram_id=901152,
        fio="MAX Public Id Primary",
        city="Москва",
        username="max_public_id_primary",
        initial_status=CandidateStatus.INTERVIEW_CONFIRMED,
    )
    async with async_session() as session:
        older_persisted = await session.get(User, older_candidate.id)
        assert older_persisted is not None
        older_persisted.telegram_id = None
        older_persisted.telegram_user_id = None
        older_persisted.max_user_id = stale_max_user_id

        primary_persisted = await session.get(User, primary_candidate.id)
        assert primary_persisted is not None
        primary_persisted.telegram_id = None
        primary_persisted.telegram_user_id = None
        primary_persisted.max_user_id = primary_max_user_id
        await session.commit()

    observed: dict[str, object] = {}

    class _SuccessfulAdapter:
        async def send_message(self, chat_id, text, *, buttons=None, **_kwargs):
            observed["chat_id"] = chat_id
            observed["text"] = text
            observed["buttons"] = buttons
            return SimpleNamespace(success=True, error=None, message_id="mid.test2")

    async def _fake_mark_max_candidate_test2_ready(_session, *, candidate, **_kwargs):
        observed["candidate_id"] = candidate.id
        return None

    async def _fake_ensure_max_adapter(**_kwargs):
        return _SuccessfulAdapter()

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.bot_service.ensure_max_adapter",
        _fake_ensure_max_adapter,
    )
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.bot_service.mark_max_candidate_test2_ready",
        _fake_mark_max_candidate_test2_ready,
    )

    service = BotService(
        state_manager=state_manager,
        enabled=True,
        configured=True,
        integration_switch=IntegrationSwitch(initial=True),
        required=False,
    )

    result = await service.send_test2(
        candidate_id=0,
        candidate_tz="Europe/Moscow",
        candidate_city=1,
        candidate_name="MAX Public Id Primary",
        required=True,
        slot_id=2308,
        candidate_public_id=primary_candidate.candidate_id,
        max_user_id=stale_max_user_id,
    )

    assert result.ok is True
    assert result.status == "sent_test2"
    assert observed["candidate_id"] == primary_candidate.id
    assert observed["chat_id"] == primary_max_user_id
    assert isinstance(observed["buttons"], list)
    assert observed["buttons"] == [[InlineButton(text="Пройти в чате", callback_data="test2:start", kind="callback")]]

    await state_manager.clear()
    await state_manager.close()


def test_integration_switch_tracks_source_and_reason():
    switch = IntegrationSwitch(initial=True)
    assert switch.source == "operator"
    assert switch.reason is None

    switch.set(False, source="runtime", reason="telegram_unauthorized")
    assert switch.is_enabled() is False
    assert switch.source == "runtime"
    assert switch.reason == "telegram_unauthorized"


def test_api_integration_toggle(monkeypatch):
    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )

    app = create_app()

    from backend.core.settings import get_settings
    settings = get_settings()

    with TestClient(app) as client:
        _login(
            client,
            settings.admin_username or "admin",
            settings.admin_password or "admin",
        )

        status_initial = client.get("/api/bot/integration").json()
        assert status_initial["runtime_enabled"] in {True, False}
        assert status_initial["switch_source"] == "operator"
        assert status_initial["switch_reason"] is None

        response = client.post("/api/bot/integration", json={"enabled": False})
        assert response.status_code == 200
        payload = response.json()
        assert payload["runtime_enabled"] is False
        assert payload["switch_source"] == "operator"
        assert payload["switch_reason"] is None

        status_after = client.get("/api/bot/integration").json()
        assert status_after["runtime_enabled"] is False
        assert status_after["switch_source"] == "operator"
        assert status_after["switch_reason"] is None

        health = client.get("/health/bot").json()
        assert health["status"] == "disabled"
        assert health["runtime"]["switch_enabled"] is False
        assert health["runtime"]["switch_source"] == "operator"
        assert health["runtime"]["switch_reason"] is None
        assert health["telegram"]["ok"] is False


def test_runtime_disable_reflected_in_health(monkeypatch):
    monkeypatch.setenv("BOT_ENABLED", "1")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "1")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )

    app = create_app()

    class _FatalNotificationService:
        async def health_snapshot(self):
            return {
                "started": True,
                "loop_enabled": True,
                "broker_backend": "memory",
                "broker_kind": "InMemoryNotificationBroker",
                "scheduler_job": True,
                "watchdog_running": True,
                "circuit_open": False,
                "seconds_since_poll": 1.0,
                "fatal_error_code": "telegram_unauthorized",
                "fatal_error_at": "2026-01-01T00:00:00+00:00",
                "last_delivery_error": "telegram_unauthorized",
                "metrics": {"outbox_queue_depth": 0},
            }

        async def broker_ping(self):
            return True

    from backend.core.settings import get_settings

    settings = get_settings()
    with TestClient(app) as client:
        _login(
            client,
            settings.admin_username or "admin",
            settings.admin_password or "admin",
        )
        app.state.notification_service = _FatalNotificationService()
        app.state.bot_integration_switch.set(
            False,
            source="runtime",
            reason="telegram_unauthorized",
        )

        bot_health = client.get("/health/bot")
        assert bot_health.status_code == 200
        bot_payload = bot_health.json()
        assert bot_payload["status"] == "error"
        assert bot_payload["runtime"]["switch_source"] == "runtime"
        assert bot_payload["runtime"]["switch_reason"] == "telegram_unauthorized"

        notifications_health = client.get("/health/notifications")
        assert notifications_health.status_code == 503
        notifications_payload = notifications_health.json()
        assert notifications_payload["notifications"]["fatal_error_code"] == "telegram_unauthorized"
    settings_module.get_settings.cache_clear()


def test_disabled_bot_health_endpoints_return_200(monkeypatch):
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    app = create_app()

    settings = settings_module.get_settings()
    with TestClient(app) as client:
        _login(
            client,
            settings.admin_username or "admin",
            settings.admin_password or "admin",
        )

        bot_health = client.get("/health/bot")
        assert bot_health.status_code == 200
        bot_payload = bot_health.json()
        assert bot_payload["status"] == "disabled"
        assert bot_payload["runtime"]["disabled_by"] == "config"

        notifications_health = client.get("/health/notifications")
        assert notifications_health.status_code == 200
        notifications_payload = notifications_health.json()
        assert notifications_payload["status"] == "disabled"
        assert notifications_payload["notifications"]["status"] == "disabled"
    settings_module.get_settings.cache_clear()
