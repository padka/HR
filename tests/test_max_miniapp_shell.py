from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def max_miniapp_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "test-max-token")
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "test-max-bot")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/miniapp")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    from backend.apps.admin_api.main import create_app

    app = create_app()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings_module.get_settings.cache_clear()


@pytest.fixture
def max_miniapp_disabled_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "0")
    monkeypatch.setenv("MAX_BOT_TOKEN", "test-max-token")
    monkeypatch.setenv("MAX_PUBLIC_BOT_NAME", "test-max-bot")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/miniapp")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    from backend.apps.admin_api.main import create_app

    app = create_app()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings_module.get_settings.cache_clear()


def test_max_miniapp_shell_serves_bootstrap_page(max_miniapp_client: TestClient):
    response = max_miniapp_client.get("/miniapp")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    body = response.text
    assert '<div id="root"></div>' in body
    assert '/assets/' in body
    assert 'https://st.max.ru/js/max-web-app.js' not in body


def test_max_miniapp_shell_serves_manifest_and_icons(max_miniapp_client: TestClient):
    manifest = max_miniapp_client.get("/manifest.json")
    icon = max_miniapp_client.get("/icons/icon-192.png")

    assert manifest.status_code == 200
    assert "json" in manifest.headers["content-type"]
    assert '"icons"' in manifest.text
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/png")


def test_max_miniapp_shell_returns_404_when_adapter_disabled(
    max_miniapp_disabled_client: TestClient,
):
    response = max_miniapp_disabled_client.get("/miniapp")

    assert response.status_code == 404
    assert response.json()["detail"] == "MAX mini-app shell is disabled."
