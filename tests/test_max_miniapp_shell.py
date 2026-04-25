from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _seed_spa_dist(tmp_path: Path) -> Path:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    icons_dir = dist_dir / "icons"
    assets_dir.mkdir(parents=True)
    icons_dir.mkdir()
    (dist_dir / "index.html").write_text(
        '<!doctype html><html><head><link rel="stylesheet" href="/assets/app.css">'
        '</head><body><div id="root"></div><script type="module" src="/assets/app.js"></script></body></html>',
        encoding="utf-8",
    )
    (dist_dir / "manifest.json").write_text(
        '{"name":"RecruitSmart","icons":[{"src":"/icons/icon-192.png","sizes":"192x192","type":"image/png"}]}',
        encoding="utf-8",
    )
    (assets_dir / "app.js").write_text("console.log('miniapp fixture')\n", encoding="utf-8")
    (assets_dir / "app.css").write_text(":root{color-scheme:light;}\n", encoding="utf-8")
    (icons_dir / "icon-192.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return dist_dir


@pytest.fixture
def max_miniapp_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
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
    dist_dir = _seed_spa_dist(tmp_path)
    from backend.apps.admin_api import main as main_module
    from backend.apps.admin_api import max_miniapp as max_miniapp_module

    monkeypatch.setattr(main_module, "SPA_DIST_DIR", dist_dir)
    monkeypatch.setattr(main_module, "SPA_MANIFEST_FILE", dist_dir / "manifest.json")
    monkeypatch.setattr(main_module, "SPA_ICONS_DIR", dist_dir / "icons")
    monkeypatch.setattr(max_miniapp_module, "SPA_DIST_DIR", dist_dir)
    monkeypatch.setattr(max_miniapp_module, "SPA_INDEX_FILE", dist_dir / "index.html")

    app = main_module.create_app()
    try:
        with TestClient(app, base_url="https://example.test") as client:
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
        with TestClient(app, base_url="https://example.test") as client:
            yield client
    finally:
        settings_module.get_settings.cache_clear()


def test_max_miniapp_shell_serves_bootstrap_page(max_miniapp_client: TestClient):
    response = max_miniapp_client.get("/miniapp")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "https://st.max.ru" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    body = response.text
    assert '<div id="root"></div>' in body
    assert '/assets/' in body
    assert 'https://st.max.ru/js/max-web-app.js' not in body
    asset_match = re.search(r'(?:"|href=)(/assets/[^" ]+\.(?:js|css))', body)
    assert asset_match is not None
    asset = max_miniapp_client.get(asset_match.group(1))
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"


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
