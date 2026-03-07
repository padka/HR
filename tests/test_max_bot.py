"""Tests for the VK Max bot webhook handler (Phase 3).

Covers:
- Webhook endpoint: valid/invalid secret, event routing
- bot_started event handling
- message_created event handling
- message_callback event handling
- Health check endpoint
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_settings(**overrides):
    """Create a mock Settings object with Max bot fields."""
    defaults = {
        "max_bot_enabled": True,
        "max_bot_token": "test_max_token",
        "max_webhook_url": "",
        "max_webhook_secret": "test_secret",
        "environment": "test",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture
def mock_settings():
    settings = _make_settings()
    with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
        yield settings


@pytest.fixture
def client(mock_settings):
    """Create a test client for the Max bot app (skip lifespan)."""
    from backend.apps.max_bot.app import create_app

    app = create_app()
    # Disable lifespan for unit tests
    app.router.lifespan_context = None  # type: ignore
    return TestClient(app, raise_server_exceptions=False)


# ── Health Check ──────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "max_bot"


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

    def test_no_secret_configured(self):
        """When no secret is configured, all requests are accepted."""
        settings = _make_settings(max_webhook_secret="")
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = None  # type: ignore
            no_secret_client = TestClient(app, raise_server_exceptions=False)
            resp = no_secret_client.post(
                "/webhook",
                json={"update_type": "bot_started", "chat_id": 1, "user": {"user_id": 1}},
            )
            assert resp.status_code == 200

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


# ── bot_started ───────────────────────────────────────────────────────────


class TestBotStarted:
    def test_bot_started_sends_welcome(self, client):
        """bot_started event should trigger a welcome message."""
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
            # Adapter should have been called to send welcome
            mock_adapter.send_message.assert_called_once()
            call_args = mock_adapter.send_message.call_args
            assert call_args[0][0] == 456  # chat_id
            assert "Здравствуйте" in call_args[0][1]  # welcome text

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
            mock_registry = MagicMock()
            mock_registry.get.return_value = mock_adapter
            mock_get_reg.return_value = mock_registry

            resp = client.post(
                "/webhook",
                json={
                    "update_type": "message_callback",
                    "callback": {
                        "payload": "confirm_assignment:42",
                        "user": {"user_id": 789},
                    },
                },
                headers={"X-Max-Bot-Api-Secret": "test_secret"},
            )
            assert resp.status_code == 200
            mock_adapter.send_message.assert_called_once()

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


# ── _verify_secret ────────────────────────────────────────────────────────


class TestVerifySecret:
    def test_correct_secret(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret("abc", "abc") is True

    def test_wrong_secret(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret("wrong", "abc") is False

    def test_no_configured_secret(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret(None, "") is True
        assert _verify_secret("anything", "") is True

    def test_none_request_secret(self):
        from backend.apps.max_bot.app import _verify_secret

        assert _verify_secret(None, "expected") is False
