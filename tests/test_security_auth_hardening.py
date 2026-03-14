from __future__ import annotations

import asyncio

import pytest
from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.security import ADMIN_PRINCIPAL_ID, SESSION_KEY
from backend.core.db import async_session
from backend.domain.models import Recruiter
from fastapi.testclient import TestClient
from starlette.requests import Request


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


def test_legacy_admin_session_is_normalized(monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdef0123456789abcd")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    try:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "scheme": "http",
                "path": "/api/profile",
                "headers": [],
                "client": ("127.0.0.1", 12345),
                "server": ("localhost", 80),
                "session": {SESSION_KEY: {"type": "admin", "id": -1}},
            }
        )
        import backend.apps.admin_ui.security as security_module

        principal = asyncio.run(security_module._resolve_current_principal(request))
        assert principal.type == "admin"
        assert principal.id == ADMIN_PRINCIPAL_ID
    finally:
        settings_module.get_settings.cache_clear()


def test_local_session_wins_over_conflicting_bearer(monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-0123456789abcdef0123456789abcd")
    from backend.core import settings as settings_module
    from backend.core.auth import create_access_token

    settings_module.get_settings.cache_clear()
    try:
        async def _seed_recruiter() -> int:
            async with async_session() as session:
                recruiter = Recruiter(name="Session Recruiter", tz="Europe/Moscow", active=True)
                session.add(recruiter)
                await session.commit()
                await session.refresh(recruiter)
                return recruiter.id

        recruiter_id = asyncio.run(_seed_recruiter())
        admin_token = create_access_token({"sub": "admin"})
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "scheme": "http",
                "path": "/api/profile",
                "headers": [(b"authorization", f"Bearer {admin_token}".encode("utf-8"))],
                "client": ("127.0.0.1", 12345),
                "server": ("localhost", 80),
                "session": {
                    SESSION_KEY: {"type": "recruiter", "id": recruiter_id},
                    "username": "mikhail",
                },
            }
        )
        import backend.apps.admin_ui.security as security_module

        principal = asyncio.run(security_module._resolve_current_principal(request, token=admin_token))
        assert principal.type == "recruiter"
        assert principal.id == recruiter_id
    finally:
        settings_module.get_settings.cache_clear()
