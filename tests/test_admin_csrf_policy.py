from __future__ import annotations

from types import SimpleNamespace

from backend.apps.admin_ui.security import _is_csrf_dev_bypass_allowed


def _request(hostname: str):
    return SimpleNamespace(url=SimpleNamespace(hostname=hostname))


def _settings(environment: str):
    return SimpleNamespace(environment=environment)


def test_csrf_bypass_allows_localhost_only_outside_production(monkeypatch):
    monkeypatch.delenv("CSRF_DEV_ALLOWLIST", raising=False)

    assert _is_csrf_dev_bypass_allowed(_request("localhost"), _settings("development")) is True
    assert _is_csrf_dev_bypass_allowed(_request("127.0.0.1"), _settings("test")) is True
    assert _is_csrf_dev_bypass_allowed(_request("localhost"), _settings("production")) is False
    assert _is_csrf_dev_bypass_allowed(_request("preview.example"), _settings("development")) is False


def test_csrf_bypass_allows_explicit_allowlist(monkeypatch):
    monkeypatch.setenv("CSRF_DEV_ALLOWLIST", "dev.crm.local, preview.crm.local")

    assert _is_csrf_dev_bypass_allowed(_request("dev.crm.local"), _settings("development")) is True
    assert _is_csrf_dev_bypass_allowed(_request("preview.crm.local"), _settings("development")) is True
    assert _is_csrf_dev_bypass_allowed(_request("remote.example"), _settings("development")) is False
    assert _is_csrf_dev_bypass_allowed(_request("dev.crm.local"), _settings("staging")) is False
