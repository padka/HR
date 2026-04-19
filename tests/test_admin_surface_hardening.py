from __future__ import annotations

import pytest
from backend.apps.admin_ui import security as security_module
from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.routers import metrics as metrics_router
from backend.core import settings as settings_module
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.websockets import WebSocketDisconnect


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def _build_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enable_legacy_assignments: bool = False,
    environment: str = "test",
):
    async def fake_setup(app):
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("ALLOW_DEV_AUTOADMIN", "0")
    monkeypatch.setenv("ENABLE_LEGACY_ASSIGNMENTS_API", "1" if enable_legacy_assignments else "0")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdef0123456789abcd")
    monkeypatch.setenv("BOT_CALLBACK_SECRET", "test-bot-callback-secret-0123456789abcdef012")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    return app


def test_legacy_assignments_routes_disabled_by_default(monkeypatch):
    app = _build_app(monkeypatch, enable_legacy_assignments=False)
    with TestClient(app) as client:
        response = client.post("/api/v1/assignments/1/confirm")
    assert response.status_code == 404


def test_legacy_assignments_routes_return_410_deprecation(monkeypatch):
    app = _build_app(monkeypatch, enable_legacy_assignments=True)
    with TestClient(app) as client:
        # Login first (legacy routes still require auth)
        login = client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin", "redirect_to": "/"},
            follow_redirects=False,
        )
        assert login.status_code in {302, 303}

        # Confirm endpoint returns 410 Gone with deprecation notice
        resp_confirm = client.post("/api/v1/assignments/1/confirm")
        assert resp_confirm.status_code == 410
        body = resp_confirm.json()
        assert body["deprecated"] is True
        assert "slot-assignments" in body["message"]

        # Reschedule endpoint returns 410 Gone with deprecation notice
        resp_reschedule = client.post("/api/v1/assignments/1/request-reschedule")
        assert resp_reschedule.status_code == 410
        body = resp_reschedule.json()
        assert body["deprecated"] is True


def test_calendar_ws_requires_authenticated_session(monkeypatch):
    app = _build_app(monkeypatch, enable_legacy_assignments=False)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/calendar"):
                pass
    assert exc_info.value.code == 1008


def test_calendar_ws_accepts_authenticated_session(monkeypatch):
    app = _build_app(monkeypatch, enable_legacy_assignments=False)
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin", "redirect_to": "/"},
            follow_redirects=False,
        )
        assert login.status_code in {302, 303}

        with client.websocket_connect("/ws/calendar") as websocket:
            websocket.send_text("ping")
            assert websocket.receive_text() == "pong"


# ---------------------------------------------------------------------------
# Security regression: metrics endpoint
# ---------------------------------------------------------------------------


def test_metrics_returns_404_in_production_mode(monkeypatch):
    monkeypatch.delenv("METRICS_ENABLED", raising=False)
    monkeypatch.setattr(
        metrics_router,
        "get_settings",
        lambda: type("Settings", (), {"environment": "production"})(),
    )
    assert metrics_router._metrics_enabled() is False


def test_metrics_forbidden_without_auth_or_allowlist(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "1")
    monkeypatch.setenv("METRICS_IP_ALLOWLIST", "192.168.99.99")  # not testclient
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 403


def test_notification_metrics_forbidden_without_auth_or_allowlist(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "1")
    monkeypatch.setenv("METRICS_IP_ALLOWLIST", "192.168.99.99")  # not testclient
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/metrics/notifications")
    assert resp.status_code == 403


def test_metrics_allowed_for_authenticated_user(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "1")
    monkeypatch.setenv("METRICS_IP_ALLOWLIST", "192.168.99.99")  # not testclient
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin", "redirect_to": "/"},
            follow_redirects=False,
        )
        resp = client.get("/metrics")
    assert resp.status_code == 200


def test_notification_metrics_allowed_for_authenticated_user(monkeypatch):
    class _StubNotificationService:
        class _Metrics:
            outbox_queue_depth = 0
            poll_skipped_total = 0
            poll_skipped_reasons = {}
            poll_backoff_total = 0
            poll_backoff_reasons = {}
            rate_limit_wait_total = 0
            rate_limit_wait_seconds = 0.0
            notifications_sent_total = {"candidate_rejection": 1}
            notifications_failed_total = {}
            poll_staleness_seconds = 0.0

        async def health_snapshot(self):
            return {
                "started": True,
                "loop_enabled": True,
                "broker_backend": "memory",
                "broker_kind": "InMemoryNotificationBroker",
                "scheduler_job": False,
                "watchdog_running": False,
                "circuit_open": False,
                "seconds_since_poll": None,
                "metrics": {},
            }

        async def metrics_snapshot(self):
            return self._Metrics()

        async def broker_ping(self):
            return True

    monkeypatch.setenv("METRICS_ENABLED", "1")
    monkeypatch.setenv("METRICS_IP_ALLOWLIST", "192.168.99.99")  # not testclient
    app = _build_app(monkeypatch)
    app.state.notification_service = _StubNotificationService()
    with TestClient(app) as client:
        client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin", "redirect_to": "/"},
            follow_redirects=False,
        )
        resp = client.get("/metrics/notifications")
    assert resp.status_code == 200


def test_bot_health_requires_authenticated_admin(monkeypatch):
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/health/bot")
    assert resp.status_code == 401


def test_notification_health_requires_authenticated_admin(monkeypatch):
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/health/notifications")
    assert resp.status_code == 401


def test_candidate_portal_routes_return_410(monkeypatch):
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        root_resp = client.get("/candidate")
        nested_resp = client.get("/candidate/start")
    assert root_resp.status_code == 410
    assert "unsupported" in root_resp.text.lower()
    assert nested_resp.status_code == 410
    assert "unsupported" in nested_resp.text.lower()


def test_openapi_does_not_advertise_candidate_portal_or_legacy_mutating_get(monkeypatch):
    app = _build_app(monkeypatch)
    schema = app.openapi()
    assert not any(path.startswith("/api/candidate/") for path in schema["paths"])
    assert "/candidates/{candidate_id}/resend-test2" not in schema["paths"]


def test_templates_list_route_registered_once(monkeypatch):
    app = _build_app(monkeypatch)
    matching_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/templates/list"
        and "GET" in getattr(route, "methods", set())
    ]
    assert len(matching_routes) == 1


# ---------------------------------------------------------------------------
# Security regression: token-based slot-assignments without token
# ---------------------------------------------------------------------------


def test_slot_assignments_confirm_requires_token(monkeypatch):
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        # POST without action token should fail
        resp = client.post(
            "/api/slot-assignments/999/confirm",
            json={"token": "", "candidate_tg_id": 123},
        )
    assert resp.status_code in {400, 403, 404, 422}


def test_slot_assignments_reschedule_requires_token(monkeypatch):
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        resp = client.post(
            "/api/slot-assignments/999/request-reschedule",
            json={"token": "", "candidate_tg_id": 123},
        )
    assert resp.status_code in {400, 403, 404, 422}


# ---------------------------------------------------------------------------
# Security regression: protected admin routes require auth
# ---------------------------------------------------------------------------


_PROTECTED_ROUTES = [
    ("GET", "/api/dashboard/summary"),
    ("GET", "/api/slots?limit=1"),
    ("GET", "/api/candidates?per_page=1"),
    ("GET", "/api/cities"),
    ("GET", "/api/recruiters"),
]


@pytest.mark.parametrize("method,path", _PROTECTED_ROUTES)
def test_protected_routes_require_auth(monkeypatch, method, path):
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        resp = client.request(method, path)
    assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}, expected 401"


# ---------------------------------------------------------------------------
# Security regression: dev bypass flags are locked
# ---------------------------------------------------------------------------


def test_dev_autoadmin_rejected_in_production(monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_AUTOADMIN", "1")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/api/cities",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("localhost", 80),
        }
    )
    settings = type("Settings", (), {"environment": "production"})()
    assert security_module._allow_dev_autoadmin(request, settings) is False


def test_legacy_basic_rejected_in_production(monkeypatch):
    monkeypatch.setenv("ALLOW_LEGACY_BASIC", "1")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/api/cities",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("localhost", 80),
        }
    )
    settings = type("Settings", (), {"environment": "production", "allow_legacy_basic": True})()
    assert security_module._allow_legacy_basic(request, settings) is False
