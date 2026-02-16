from __future__ import annotations

import pytest
from backend.apps.admin_ui.app import create_app
from fastapi.testclient import TestClient


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def secure_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("ACCESS_TOKEN_TTL_HOURS", "12")
    monkeypatch.setenv("AUTH_BRUTE_FORCE_ENABLED", "1")

    # Speed up brute-force test window locally
    import backend.apps.admin_ui.routers.auth as auth_router

    monkeypatch.setattr(auth_router, "_BRUTE_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(auth_router, "_BRUTE_LOCK_SECONDS", 60)
    monkeypatch.setattr(auth_router, "_BRUTE_WINDOW_SECONDS", 300)
    auth_router._LOGIN_FAILURES.clear()
    auth_router._LOGIN_LOCK_UNTIL.clear()

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        auth_router._LOGIN_FAILURES.clear()
        auth_router._LOGIN_LOCK_UNTIL.clear()
        settings_module.get_settings.cache_clear()


def test_security_headers_present(secure_app):
    with TestClient(secure_app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in (resp.headers.get("Permissions-Policy") or "")
    assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"


def test_auth_token_bruteforce_lock(secure_app):
    with TestClient(secure_app) as client:
        for _ in range(3):
            fail = client.post(
                "/auth/token",
                data={"username": "admin", "password": "wrong"},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            assert fail.status_code == 401

        blocked = client.post(
            "/auth/token",
            data={"username": "admin", "password": "wrong"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers

        still_blocked = client.post(
            "/auth/token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert still_blocked.status_code == 429
