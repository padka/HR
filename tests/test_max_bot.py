"""Tests for the VK Max bot webhook handler (Phase 3).

Covers:
- Webhook endpoint: valid/invalid secret, event routing
- bot_started event handling
- message_created event handling
- message_callback event handling
- Health check endpoint
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import backend.core.messenger.registry as registry_mod
import pytest
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.registry import MessengerRegistry
from fastapi.testclient import TestClient


def _make_settings(**overrides):
    """Create a mock Settings object with Max bot fields."""
    defaults = {
        "max_bot_enabled": True,
        "max_bot_allow_public_entry": False,
        "max_bot_token": "test_max_token",
        "max_webhook_url": "",
        "max_webhook_secret": "test_secret",
        "redis_url": "",
        "environment": "test",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


@pytest.fixture
def mock_settings():
    settings = _make_settings()
    with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
        yield settings


class _FakeMaxAdapter:
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.answered_callbacks: list[dict[str, object]] = []

    async def send_message(
        self,
        chat_id,
        text,
        *,
        buttons=None,
        parse_mode=None,
        correlation_id=None,
    ):
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "parse_mode": parse_mode,
                "correlation_id": correlation_id,
            }
        )
        return MagicMock(success=True, message_id=f"mid_{len(self.sent_messages)}")

    async def answer_callback(self, callback_id: str, notification: str = "Принято"):
        self.answered_callbacks.append(
            {
                "callback_id": callback_id,
                "notification": notification,
            }
        )
        return MagicMock(success=True)

    async def list_subscriptions(self):
        return []

    async def delete_subscription(self, url: str):
        return MagicMock(success=True)

    async def create_subscription(self, *, url: str, update_types, secret=None):
        return MagicMock(success=True)

    async def close(self):
        return None


@pytest.fixture(autouse=True)
def _isolated_max_registry():
    registry = MessengerRegistry()
    adapter = _FakeMaxAdapter()
    registry.register(adapter)
    previous = registry_mod._registry
    registry_mod._registry = registry
    try:
        yield adapter
    finally:
        registry_mod._registry = previous


@pytest.fixture
def client(mock_settings):
    """Create a test client for the Max bot app (skip lifespan)."""
    import backend.apps.max_bot.app as max_app
    from backend.apps.max_bot.app import create_app

    app = create_app()
    # Disable lifespan for unit tests
    app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
    max_app._reset_dedupe_state()
    max_app._set_subscription_status(status="not_configured", action="pending")
    return TestClient(app, raise_server_exceptions=False)


# ── Health Check ──────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "max_bot"
        assert data["public_entry_enabled"] is False
        assert data["browser_portal_fallback_allowed"] is True
        assert data["telegram_business_fallback_allowed"] is False
        assert data["dedupe_ready"] is True
        assert data["dedupe_mode"] == "memory"
        assert data["readiness_blockers"] == []

    def test_health_reports_public_entry_flag(self):
        settings = _make_settings(max_bot_allow_public_entry=True)
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json()["public_entry_enabled"] is True

    def test_health_disabled_when_feature_flag_off(self):
        settings = _make_settings(max_bot_enabled=False, environment="production", max_webhook_secret="", redis_url="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/health")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "disabled"
        assert payload["runtime_ready"] is True
        assert payload["readiness_blockers"] == []
        assert payload["dedupe_mode"] == "disabled"

    def test_health_reports_webhook_url_blocker_outside_dev_test(self):
        settings = _make_settings(environment="staging", max_webhook_url="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/health")

        assert resp.status_code == 503
        payload = resp.json()
        assert payload["status"] == "blocked"
        assert "max_webhook_url_missing" in payload["readiness_blockers"]

    def test_health_blocked_when_secret_missing_outside_dev_test(self):
        settings = _make_settings(environment="staging", max_webhook_secret="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "blocked"
        assert data["webhook_secret_error"] == "max_webhook_secret_missing"

    def test_health_blocked_when_dedupe_unavailable_outside_dev_test(self):
        settings = _make_settings(environment="staging", redis_url="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/health")

        assert resp.status_code == 503
        payload = resp.json()
        assert payload["status"] == "blocked"
        assert payload["dedupe_ready"] is False
        assert payload["dedupe_mode"] == "unavailable"
        assert payload["dedupe_error"] == "max_webhook_dedupe_redis_missing"
        assert "max_webhook_dedupe_redis_missing" in payload["readiness_blockers"]


# ── Webhook Security ─────────────────────────────────────────────────────


class TestWebhookSecurity:
    def test_valid_secret(self, client):
        resp = client.post(
            "/webhook",
            json={"update_type": "bot_started", "chat_id": 123, "user": {"user_id": 123}},
            headers={"X-Max-Bot-Api-Secret": "test_secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_invalid_secret(self, client):
        resp = client.post(
            "/webhook",
            json={"update_type": "bot_started"},
            headers={"X-Max-Bot-Api-Secret": "wrong_secret"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "invalid_secret"

    def test_missing_secret(self, client):
        resp = client.post(
            "/webhook",
            json={"update_type": "bot_started"},
        )
        assert resp.status_code == 403

    def test_no_secret_configured_allowed_in_test(self):
        """Development/test may bypass webhook secret when explicitly unset."""
        settings = _make_settings(max_webhook_secret="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            with TestClient(app, raise_server_exceptions=False) as no_secret_client:
                resp = no_secret_client.post(
                    "/webhook",
                    json={"update_type": "bot_started", "chat_id": 1, "user": {"user_id": 1}},
                )
            assert resp.status_code == 200

    def test_no_secret_configured_rejected_outside_dev_test(self):
        settings = _make_settings(environment="staging", max_webhook_secret="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            with TestClient(app, raise_server_exceptions=False) as no_secret_client:
                resp = no_secret_client.post(
                    "/webhook",
                    json={"update_type": "bot_started", "chat_id": 1, "user": {"user_id": 1}},
                )

        assert resp.status_code == 503
        assert resp.json()["error"] == "max_webhook_secret_missing"

    def test_invalid_json(self, client):
        resp = client.post(
            "/webhook",
            content=b"not json",
            headers={
                "X-Max-Bot-Api-Secret": "test_secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400


# ── Event Routing ─────────────────────────────────────────────────────────


class TestEventRouting:
    def test_unknown_event_type(self, client):
        resp = client.post(
            "/webhook",
            json={"update_type": "unknown_event"},
            headers={"X-Max-Bot-Api-Secret": "test_secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_duplicate_message_created_with_message_id_is_deduped(self, client):
        payload = {
            "update_type": "message_created",
            "message": {
                "message_id": "mx-mid-1",
                "sender": {"user_id": 456, "name": "Тест Кандидат"},
                "body": {"text": "resume"},
            },
        }
        with patch("backend.apps.max_bot.app.process_text_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = []

            first = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            second = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["duplicate"] is True
        mock_process.assert_awaited_once()


# ── Subscription Reconciliation ───────────────────────────────────────────


class TestWebhookSubscriptionReconciliation:
    @pytest.mark.asyncio
    async def test_reconcile_prunes_stale_subscriptions(self, mock_settings):
        mock_settings.max_webhook_url = "https://new.example/webhook"
        mock_settings.max_webhook_secret = "test_secret"

        from backend.apps.max_bot.app import _reconcile_webhook_subscription

        with patch("backend.apps.max_bot.app._get_max_adapter") as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_adapter.list_subscriptions.return_value = [
                {"url": "https://new.example/webhook", "update_types": ["bot_started", "message_created", "message_callback"]},
                {"url": "https://old.example/webhook", "update_types": ["bot_started", "message_created", "message_callback"]},
            ]
            mock_adapter.delete_subscription.return_value = MagicMock(success=True)
            mock_get_adapter.return_value = mock_adapter

            await _reconcile_webhook_subscription(mock_settings)

            mock_adapter.delete_subscription.assert_awaited_once_with(url="https://old.example/webhook")
            mock_adapter.create_subscription.assert_not_awaited()


# ── bot_started ───────────────────────────────────────────────────────────


class TestBotStarted:
    def test_bot_started_starts_public_onboarding_without_payload(self, client):
        with patch("backend.core.messenger.registry.get_registry") as mock_get_reg:
            mock_adapter = AsyncMock()
            mock_adapter.send_message.return_value = MagicMock(success=True)
            mock_registry = MagicMock()
            mock_registry.get.return_value = mock_adapter
            mock_get_reg.return_value = mock_registry

            resp = client.post(
                "/webhook",
                json={
                    "update_type": "bot_started",
                    "chat_id": 456,
                    "user": {"user_id": 456, "name": "Тест Кандидат"},
                },
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            assert resp.status_code == 200
            assert mock_adapter.send_message.await_count >= 2
            intro_args = mock_adapter.send_message.await_args_list[-2].args
            prompt_args = mock_adapter.send_message.await_args_list[-1].args
            assert intro_args[0] == 456
            assert "пройти первичную анкету" in intro_args[1].lower()
            assert prompt_args[0] == 456
            assert "фио" in prompt_args[1].lower()

    def test_bot_started_uses_payload_field(self, client):
        with patch("backend.apps.max_bot.app.process_bot_started", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = []
            resp = client.post(
                "/webhook",
                json={
                    "update_type": "bot_started",
                    "chat_id": 456,
                    "payload": "invite-123",
                    "user": {"user_id": 456, "name": "Тест Кандидат"},
                },
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            assert resp.status_code == 200
            mock_process.assert_awaited_once()
            assert mock_process.await_args.kwargs["start_payload"] == "invite-123"

    def test_bot_started_no_user_id(self, client):
        """bot_started without user_id should be handled gracefully."""
        resp = client.post(
            "/webhook",
            json={"update_type": "bot_started", "user": {}},
            headers={"X-Max-Bot-Api-Secret": "test_secret"},
        )
        assert resp.status_code == 200


# ── message_callback ──────────────────────────────────────────────────────


class TestMessageCallback:
    def test_callback_responds(self, client):
        """message_callback should send an acknowledgment."""
        with patch("backend.core.messenger.registry.get_registry") as mock_get_reg:
            mock_adapter = AsyncMock()
            mock_adapter.send_message.return_value = MagicMock(success=True)
            mock_adapter.answer_callback.return_value = MagicMock(success=True)
            mock_registry = MagicMock()
            mock_registry.get.return_value = mock_adapter
            mock_get_reg.return_value = mock_registry

            resp = client.post(
                "/webhook",
                json={
                    "update_type": "message_callback",
                    "callback": {
                        "callback_id": "cb_1",
                        "payload": "confirm_assignment:42",
                        "user": {"user_id": 789},
                    },
                },
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            assert resp.status_code == 200
            mock_adapter.send_message.assert_called_once()
            mock_adapter.answer_callback.assert_awaited_once_with("cb_1", notification="Принято")

    def test_callback_empty_payload(self, client):
        """Callback with empty payload should not crash."""
        resp = client.post(
            "/webhook",
            json={
                "update_type": "message_callback",
                "callback": {"payload": "", "user": {"user_id": 789}},
            },
            headers={"X-Max-Bot-Api-Secret": "test_secret"},
        )
        assert resp.status_code == 200

    def test_duplicate_callback_body_is_deduped(self, client):
        payload = {
            "update_type": "message_callback",
            "callback": {
                "callback_id": "cb_dup",
                "payload": "maxflow:start",
                "user": {"user_id": 789},
            },
        }
        first = client.post(
            "/webhook",
            json=payload,
            headers={"X-Max-Bot-Api-Secret": "test_secret"},
        )
        second = client.post(
            "/webhook",
            json=payload,
            headers={"X-Max-Bot-Api-Secret": "test_secret"},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["duplicate"] is True


# ── _verify_secret ────────────────────────────────────────────────────────


class TestVerifySecret:
    def test_correct_secret(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret("abc", "abc") is True

    def test_wrong_secret(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret("wrong", "abc") is False

    def test_no_configured_secret_allowed_explicitly(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret(None, "", allow_unset=True) is True
        assert _verify_secret("anything", "", allow_unset=True) is True

    def test_no_configured_secret_rejected_by_default(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret(None, "") is False
        assert _verify_secret("anything", "") is False

    def test_none_request_secret(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret(None, "expected") is False


class TestWebhookDedupe:
    def test_duplicate_delivery_short_circuits(self, client):
        payload = {
            "update_type": "unknown_event",
            "timestamp": 1,
        }
        headers = {"X-Max-Bot-Api-Secret": "test_secret"}

        first = client.post("/webhook", json=payload, headers=headers)
        second = client.post("/webhook", json=payload, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json().get("duplicate") is None
        assert second.json()["duplicate"] is True

    def test_duplicate_message_created_without_message_id_is_deduped(self, client):
        payload = {
            "update_type": "message_created",
            "timestamp": 1712345678,
            "message": {
                "body": {"text": "resume"},
                "sender": {"user_id": "mx-user-1", "name": "Max Candidate"},
            },
        }
        with patch("backend.apps.max_bot.app.process_text_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = []

            first = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            second = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["duplicate"] is True
        mock_process.assert_awaited_once()

    def test_transportless_message_created_without_message_id_is_not_deduped(self, client):
        payload = {
            "update_type": "message_created",
            "message": {
                "body": {"text": "resume"},
                "sender": {"user_id": "mx-user-1", "name": "Max Candidate"},
            },
        }
        with patch("backend.apps.max_bot.app.process_text_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = []

            first = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            second = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["ok"] is True
        assert second.json()["ok"] is True
        assert second.json().get("duplicate") is None
        assert mock_process.await_count == 2

    def test_webhook_rejected_when_dedupe_unavailable_outside_dev_test(self):
        settings = _make_settings(environment="staging", redis_url="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            import backend.apps.max_bot.app as max_app
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
            max_app._reset_dedupe_state()
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/webhook",
                    json={"update_type": "bot_started", "chat_id": 1, "user": {"user_id": 1}},
                    headers={"X-Max-Bot-Api-Secret": "test_secret"},
                )

        assert response.status_code == 503
        assert response.json()["error"] == "dedupe_unavailable"


class TestWebhookFailureSemantics:
    def test_failed_handler_returns_500_and_is_not_marked_processed(self, client):
        payload = {
            "update_type": "bot_started",
            "chat_id": 456,
            "user": {"user_id": 456, "name": "Тест Кандидат"},
        }
        with patch("backend.apps.max_bot.candidate_flow._send_outbound", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = RuntimeError("boom")

            first = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            second = client.post(
                "/webhook",
                json=payload,
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )

        assert first.status_code == 500
        assert second.status_code == 500
        assert first.json()["error"] == "handler_failed"
        assert second.json()["error"] == "handler_failed"
        assert mock_send.await_count == 2
