from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from backend.apps.admin_ui.security import Principal, require_admin
from backend.core.db import async_session
from backend.domain.hh_integration.client import HHOAuthTokens
from backend.domain.hh_integration.crypto import HHSecretCipher
from backend.domain.hh_integration.models import HHConnection, HHWebhookDelivery
from backend.domain.hh_integration.oauth import build_hh_authorize_url
from backend.domain.hh_integration.service import get_connection_for_principal
from fastapi.testclient import TestClient


@pytest.fixture
def hh_env(monkeypatch):
    monkeypatch.setenv("HH_INTEGRATION_ENABLED", "1")
    monkeypatch.setenv("HH_CLIENT_ID", "hh-client")
    monkeypatch.setenv("HH_CLIENT_SECRET", "hh-secret")
    monkeypatch.setenv("HH_REDIRECT_URI", "https://crm.example.com/api/integrations/hh/oauth/callback")
    monkeypatch.setenv("HH_WEBHOOK_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("HH_USER_AGENT", "RecruitSmartTest/1.0 (qa@example.com)")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app(monkeypatch, hh_env):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from backend.apps.admin_ui.app import create_app
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    app.dependency_overrides[require_admin] = lambda: Principal(type="admin", id=1)
    try:
        yield app
    finally:
        app.dependency_overrides.pop(require_admin, None)
        settings_module.get_settings.cache_clear()


@pytest.fixture
def admin_api_app(hh_env):
    from backend.apps.admin_api.main import create_app

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app = create_app()
    app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
    return app


class TestHHOAuthHelpers:
    def test_build_hh_authorize_url_includes_required_params(self, hh_env):
        url, state = build_hh_authorize_url(Principal(type="admin", id=7), return_to="/app/system")
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "hh.ru"
        assert parsed.path == "/oauth/authorize"
        assert qs["response_type"] == ["code"]
        assert qs["client_id"] == ["hh-client"]
        assert qs["redirect_uri"] == ["https://crm.example.com/api/integrations/hh/oauth/callback"]
        assert qs["role"] == ["employer"]
        assert qs["force_role"] == ["true"]
        assert qs["skip_choose_account"] == ["true"]
        assert qs["state"] == [state]

    def test_secret_cipher_round_trip(self):
        cipher = HHSecretCipher(secret="test-secret-for-hh")
        encrypted = cipher.encrypt("token-value")
        assert encrypted != "token-value"
        assert cipher.decrypt(encrypted) == "token-value"

    @pytest.mark.asyncio
    async def test_get_connection_for_admin_falls_back_to_sentinel_principal(self):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=-1,
                employer_id="emp-legacy",
                access_token_encrypted=cipher.encrypt("access-legacy"),
                refresh_token_encrypted=cipher.encrypt("refresh-legacy"),
                webhook_url_key="legacy-admin-key",
                profile_payload={},
            )
            session.add(connection)
            await session.commit()

        async with async_session() as session:
            resolved = await get_connection_for_principal(session, Principal(type="admin", id=1))

        assert resolved is not None
        assert resolved.principal_id == -1
        assert resolved.employer_id == "emp-legacy"


class TestHHOAuthRoutes:
    @pytest.mark.asyncio
    async def test_oauth_callback_persists_encrypted_connection(self, admin_app):
        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.exchange_authorization_code.return_value = HHOAuthTokens(
                    access_token="access-123",
                    refresh_token="refresh-456",
                    token_type="Bearer",
                    expires_in=3600,
                )
                mock_client.get_me.return_value = {
                    "id": "mgr-user-1",
                    "first_name": "Ирина",
                    "last_name": "Петрова",
                    "employer": {"id": "emp-1", "name": "Acme"},
                    "manager": {"id": "mgr-1"},
                }
                mock_client.get_manager_accounts.return_value = {
                    "current_account_id": "acc-42",
                    "primary_account_id": "acc-42",
                    "items": [{"id": "acc-42"}],
                    "is_primary_account_blocked": False,
                }
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    auth_resp = client.get("/api/integrations/hh/oauth/authorize")
                    assert auth_resp.status_code == 200
                    state = auth_resp.json()["state"]
                    return client.get(
                        "/api/integrations/hh/oauth/callback",
                        params={"code": "code-123", "state": state},
                    )

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["connection"]["employer_id"] == "emp-1"
        assert body["connection"]["manager_account_id"] == "acc-42"
        assert body["connection"]["webhook_url"].startswith("https://api.example.com/api/hh-integration/webhooks/")

        async with async_session() as session:
            from sqlalchemy import select

            row = await session.execute(select(HHConnection))
            connection = row.scalar_one()
            cipher = HHSecretCipher()
            assert connection.principal_type == "admin"
            assert connection.principal_id == 1
            assert cipher.decrypt(connection.access_token_encrypted) == "access-123"
            assert cipher.decrypt(connection.refresh_token_encrypted) == "refresh-456"

    @pytest.mark.asyncio
    async def test_compat_callback_path_redirects_to_return_to(self, admin_app):
        state = build_hh_authorize_url(
            Principal(type="admin", id=1),
            return_to="/app/system",
        )[1]

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.exchange_authorization_code.return_value = HHOAuthTokens(
                    access_token="access-123",
                    refresh_token="refresh-456",
                    token_type="Bearer",
                    expires_in=3600,
                )
                mock_client.get_me.return_value = {
                    "id": "mgr-user-1",
                    "first_name": "Ирина",
                    "last_name": "Петрова",
                    "employer": {"id": "emp-1", "name": "Acme"},
                    "manager": {"id": "mgr-1"},
                }
                mock_client.get_manager_accounts.return_value = {
                    "current_account_id": "acc-42",
                    "primary_account_id": "acc-42",
                    "items": [{"id": "acc-42"}],
                    "is_primary_account_blocked": False,
                }
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app, follow_redirects=False) as client:
                    return client.get(
                        "/rest/oauth2-credential/callback",
                        params={"code": "code-compat", "state": state},
                    )

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/app/system?hh=connected"

    @pytest.mark.asyncio
    async def test_refresh_tokens_route_updates_connection(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                access_token_encrypted=cipher.encrypt("old-access"),
                refresh_token_encrypted=cipher.encrypt("old-refresh"),
                webhook_url_key="refresh-key",
                profile_payload={},
            )
            session.add(connection)
            await session.commit()

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.refresh_access_token.return_value = HHOAuthTokens(
                    access_token="new-access",
                    refresh_token="new-refresh",
                    token_type="Bearer",
                    expires_in=7200,
                )
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    return client.post("/api/integrations/hh/oauth/refresh")

        resp = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        async with async_session() as session:
            from sqlalchemy import select

            row = await session.execute(select(HHConnection))
            connection = row.scalar_one()
            assert cipher.decrypt(connection.access_token_encrypted) == "new-access"
            assert cipher.decrypt(connection.refresh_token_encrypted) == "new-refresh"

    @pytest.mark.asyncio
    async def test_register_webhooks_route_uses_public_webhook_url(self, admin_app):
        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                manager_account_id="acc-42",
                access_token_encrypted=cipher.encrypt("access-123"),
                refresh_token_encrypted=cipher.encrypt("refresh-456"),
                webhook_url_key="register-key",
                profile_payload={},
            )
            session.add(connection)
            await session.commit()

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.create_webhook_subscription.return_value = {"id": "sub-1"}
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    response = client.post("/api/integrations/hh/webhooks/register")
                return response, mock_client

        resp, mock_client = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["webhook_url"] == "https://api.example.com/api/hh-integration/webhooks/register-key"
        mock_client.create_webhook_subscription.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_webhooks_route_derives_base_url_from_redirect_uri(self, admin_app, monkeypatch):
        from backend.core import settings as settings_module

        monkeypatch.delenv("HH_WEBHOOK_BASE_URL", raising=False)
        settings_module.get_settings.cache_clear()

        cipher = HHSecretCipher()
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                manager_account_id="acc-42",
                access_token_encrypted=cipher.encrypt("access-123"),
                refresh_token_encrypted=cipher.encrypt("refresh-456"),
                webhook_url_key="derived-key",
                profile_payload={},
            )
            session.add(connection)
            await session.commit()

        def _call():
            with patch("backend.apps.admin_ui.routers.hh_integration.HHApiClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.create_webhook_subscription.return_value = {"id": "sub-1"}
                mock_client_cls.return_value = mock_client
                with TestClient(admin_app) as client:
                    response = client.post("/api/integrations/hh/webhooks/register")
                return response, mock_client

        resp, mock_client = await asyncio.to_thread(_call)
        assert resp.status_code == 200
        body = resp.json()
        assert body["webhook_url"] == "https://crm.example.com/api/hh-integration/webhooks/derived-key"
        mock_client.create_webhook_subscription.assert_awaited_once()


class TestHHWebhookReceiver:
    @pytest.mark.asyncio
    async def test_webhook_receiver_is_idempotent(self, admin_api_app):
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                access_token_encrypted="enc-access",
                refresh_token_encrypted="enc-refresh",
                webhook_url_key="hh-webhook-key",
                profile_payload={},
            )
            session.add(connection)
            await session.commit()

        payload = {
            "id": "delivery-1",
            "subscription_id": "sub-1",
            "action_type": "NEW_RESPONSE_OR_INVITATION_VACANCY",
            "payload": {
                "topic_id": "topic-1",
                "resume_id": "resume-1",
                "vacancy_id": "vac-1",
                "employer_id": "emp-1",
                "chat_id": "chat-1",
                "response_date": "2026-03-07T12:00:00+0300",
            },
        }

        def _call_twice():
            with TestClient(admin_api_app, raise_server_exceptions=False) as client:
                first = client.post("/api/hh-integration/webhooks/hh-webhook-key", json=payload)
                second = client.post("/api/hh-integration/webhooks/hh-webhook-key", json=payload)
                return first, second

        first, second = await asyncio.to_thread(_call_twice)
        assert first.status_code == 202
        assert second.status_code == 409
        assert first.json()["duplicate"] is False
        assert second.json()["duplicate"] is True

        async with async_session() as session:
            from sqlalchemy import select

            rows = await session.execute(select(HHWebhookDelivery))
            deliveries = rows.scalars().all()
            assert len(deliveries) == 1
            assert deliveries[0].delivery_id == "delivery-1"
            assert deliveries[0].action_type == "NEW_RESPONSE_OR_INVITATION_VACANCY"

    @pytest.mark.asyncio
    async def test_webhook_receiver_is_available_via_admin_ui_domain(self, admin_app):
        async with async_session() as session:
            connection = HHConnection(
                principal_type="admin",
                principal_id=1,
                employer_id="emp-1",
                access_token_encrypted="enc-access",
                refresh_token_encrypted="enc-refresh",
                webhook_url_key="hh-webhook-ui-key",
                profile_payload={},
            )
            session.add(connection)
            await session.commit()

        payload = {
            "id": "delivery-ui-1",
            "subscription_id": "sub-1",
            "action_type": "NEW_RESPONSE_OR_INVITATION_VACANCY",
            "payload": {"topic_id": "topic-1"},
        }

        def _call():
            with TestClient(admin_app) as client:
                return client.post("/api/hh-integration/webhooks/hh-webhook-ui-key", json=payload)

        response = await asyncio.to_thread(_call)
        assert response.status_code == 202
        assert response.json()["ok"] is True
