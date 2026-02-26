from __future__ import annotations

from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.routers import metrics as metrics_router
from backend.core.settings import get_settings


def test_metrics_endpoint_disabled(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "0")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/metrics")
        assert resp.status_code == 404


def test_metrics_endpoint_enabled(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "1")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        # A couple of core metrics should be present.
        assert "http_requests_total" in resp.text
        assert "http_request_duration_seconds" in resp.text
        assert "db_pool_acquire_seconds_bucket" in resp.text
        assert "http_db_queries_per_request_bucket" in resp.text
        assert "http_db_query_time_seconds_bucket" in resp.text


def test_metrics_endpoint_rejects_non_allowlisted_ip_without_auth(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "1")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("METRICS_IP_ALLOWLIST", "127.0.0.1,::1")
    monkeypatch.setenv("ALLOW_DEV_AUTOADMIN", "0")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/metrics", headers={"X-Forwarded-For": "203.0.113.10"})
        assert resp.status_code == 403


def test_metrics_default_disabled_in_production(monkeypatch):
    monkeypatch.delenv("METRICS_ENABLED", raising=False)
    monkeypatch.setattr(
        metrics_router,
        "get_settings",
        lambda: type("Settings", (), {"environment": "production"})(),
    )
    assert metrics_router._metrics_enabled() is False
