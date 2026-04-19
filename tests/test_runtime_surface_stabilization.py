from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.apps.admin_ui.app import create_app
from backend.core import settings as settings_module
from fastapi.testclient import TestClient


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
    environment: str = "test",
    allow_destructive_admin_actions: bool | None = None,
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
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv(
        "BOT_CALLBACK_SECRET",
        "test-bot-callback-secret-0123456789abcdef012",
    )
    if allow_destructive_admin_actions is None:
        monkeypatch.delenv("ALLOW_DESTRUCTIVE_ADMIN_ACTIONS", raising=False)
    else:
        monkeypatch.setenv(
            "ALLOW_DESTRUCTIVE_ADMIN_ACTIONS",
            "1" if allow_destructive_admin_actions else "0",
        )

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    return create_app()


def _login(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin", "redirect_to": "/"},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}


def _csrf(client: TestClient) -> str:
    response = client.get("/api/csrf")
    assert response.status_code == 200
    token = (response.json() or {}).get("token")
    assert isinstance(token, str) and token
    return token


def test_legacy_resend_test2_get_returns_410_without_candidate_lookup(monkeypatch):
    app = _build_app(monkeypatch)
    with TestClient(app) as client:
        _login(client)
        response = client.get(
            "/candidates/999999/resend-test2",
            headers={"accept": "application/json"},
        )

    assert response.status_code == 410
    payload = response.json()
    assert payload["deprecated"] is True
    assert "actions/resend_test2" in payload["message"]


def test_candidate_bulk_delete_requires_csrf(monkeypatch):
    app = _build_app(monkeypatch, allow_destructive_admin_actions=True)
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/candidates/delete-all",
            json={"confirmation": "DELETE ALL CANDIDATES"},
            headers={"accept": "application/json"},
        )

    assert response.status_code == 403


def test_candidate_bulk_delete_disabled_by_default_in_staging(monkeypatch):
    app = _build_app(monkeypatch, environment="staging")
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/candidates/delete-all",
            json={"confirmation": "DELETE ALL CANDIDATES"},
            headers={
                "accept": "application/json",
                "x-csrf-token": _csrf(client),
            },
        )

    assert response.status_code == 403
    assert response.json()["ok"] is False


def test_candidate_bulk_delete_requires_confirmation(monkeypatch):
    async def fail_if_called():
        raise AssertionError("delete_all_candidates should not run without typed confirmation")

    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.candidates.delete_all_candidates",
        fail_if_called,
    )
    app = _build_app(monkeypatch, allow_destructive_admin_actions=True)

    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/candidates/delete-all",
            json={"confirmation": "WRONG"},
            headers={
                "accept": "application/json",
                "x-csrf-token": _csrf(client),
            },
        )

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_candidate_bulk_delete_succeeds_with_confirmation(monkeypatch):
    async def fake_delete_all_candidates():
        return 7

    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.candidates.delete_all_candidates",
        fake_delete_all_candidates,
    )
    app = _build_app(monkeypatch, allow_destructive_admin_actions=True)

    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/candidates/delete-all",
            json={"confirmation": "DELETE ALL CANDIDATES"},
            headers={
                "accept": "application/json",
                "x-csrf-token": _csrf(client),
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "deleted": 7}


def test_slots_bulk_delete_disabled_by_default_in_staging(monkeypatch):
    app = _build_app(monkeypatch, environment="staging")
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/slots/delete_all",
            json={"confirmation": "DELETE ALL SLOTS", "force": False},
            headers={"x-csrf-token": _csrf(client)},
        )

    assert response.status_code == 403
    assert response.json()["ok"] is False


def test_slots_bulk_delete_requires_confirmation(monkeypatch):
    async def fail_if_called(*, force: bool = False, principal=None):
        raise AssertionError("delete_all_slots should not run without typed confirmation")

    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.slots.delete_all_slots",
        fail_if_called,
    )
    app = _build_app(monkeypatch, allow_destructive_admin_actions=True)

    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/slots/delete_all",
            json={"confirmation": "WRONG", "force": False},
            headers={"x-csrf-token": _csrf(client)},
        )

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_slots_bulk_delete_succeeds_with_confirmation(monkeypatch):
    async def fake_delete_all_slots(*, force: bool = False, principal=None):
        assert force is True
        return 5, 1

    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.slots.delete_all_slots",
        fake_delete_all_slots,
    )
    app = _build_app(monkeypatch, allow_destructive_admin_actions=True)

    with TestClient(app) as client:
        _login(client)
        response = client.post(
            "/slots/delete_all",
            json={"confirmation": "DELETE ALL SLOTS", "force": True},
            headers={"x-csrf-token": _csrf(client)},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "deleted": 5, "remaining": 1}


def test_max_bot_runtime_is_not_advertised_as_default_compose_service():
    repo_root = Path(__file__).resolve().parents[1]
    compose_text = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")
    max_bot_entrypoint = (repo_root / "max_bot.py").read_text(encoding="utf-8")

    assert "max_bot:" in compose_text
    assert "profiles:" in compose_text
    assert "- max" in compose_text
    assert "backend.apps.max_bot.app" not in max_bot_entrypoint
    assert "disabled in the supported RecruitSmart runtime" in max_bot_entrypoint


def test_max_bot_main_stays_disabled_by_default(monkeypatch, capsys):
    import max_bot

    monkeypatch.delenv("MAX_ADAPTER_ENABLED", raising=False)
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MAX_PUBLIC_BOT_NAME", raising=False)
    monkeypatch.delenv("MAX_MINIAPP_URL", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        max_bot.main()

    assert exc_info.value.code == 1
    assert "disabled in the supported RecruitSmart runtime" in capsys.readouterr().err


def test_max_bot_main_fails_clear_when_enabled_without_token(monkeypatch, capsys):
    import max_bot

    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MAX_PUBLIC_BOT_NAME", raising=False)
    monkeypatch.delenv("MAX_MINIAPP_URL", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        max_bot.main()

    assert exc_info.value.code == 1
    assert "MAX_BOT_TOKEN" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_run_max_adapter_shell_bootstraps_bounded_adapter(monkeypatch):
    from backend.core.messenger.bootstrap import run_max_adapter_shell

    calls: dict[str, object] = {}

    async def fake_bootstrap_max_adapter_shell(*, config=None, settings=None):
        calls["config"] = config
        calls["settings"] = settings

    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token")
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "rs_max_bot")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    monkeypatch.setitem(
        sys.modules,
        "backend.core.messenger.max_adapter",
        SimpleNamespace(bootstrap_max_adapter_shell=fake_bootstrap_max_adapter_shell),
    )

    await run_max_adapter_shell()

    config = calls["config"]
    assert config is not None
    assert getattr(config, "enabled", None) is True
    assert getattr(config, "bot_token", None) == "max-token"
    assert getattr(config, "public_bot_name", None) == "rs_max_bot"
    assert getattr(config, "miniapp_url", None) == "https://example.test/max"


@pytest.mark.asyncio
async def test_run_max_adapter_shell_requires_token_when_enabled(monkeypatch):
    from backend.core.messenger.bootstrap import (
        MaxRuntimeDisabledError,
        run_max_adapter_shell,
    )

    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MAX_PUBLIC_BOT_NAME", raising=False)
    monkeypatch.delenv("MAX_MINIAPP_URL", raising=False)

    with pytest.raises(MaxRuntimeDisabledError, match="MAX_BOT_TOKEN"):
        await run_max_adapter_shell()
