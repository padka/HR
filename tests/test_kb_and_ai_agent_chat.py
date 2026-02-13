from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def ai_kb_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("AI_ENABLED", "1")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


def _csrf(client: TestClient) -> str:
    resp = client.get("/api/csrf", auth=("admin", "admin"))
    assert resp.status_code == 200
    token = (resp.json() or {}).get("token") or ""
    assert token
    return str(token)


def test_kb_document_create_and_agent_chat_returns_excerpts(ai_kb_app):
    with TestClient(ai_kb_app) as client:
        token = _csrf(client)
        doc_text = (
            "Объективные причины отказа: нарушение дресс-кода; "
            "несоответствие базовым критериям; отсутствие подтверждений.\n"
            "Недопустимые причины: субъективные формулировки без фактов."
        )
        created = client.post(
            "/api/kb/documents",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"title": "Регламент", "content_text": doc_text},
        )
        assert created.status_code == 200
        doc_id = int(created.json()["document_id"])

        listed = client.get("/api/kb/documents", auth=("admin", "admin"))
        assert listed.status_code == 200
        items = listed.json().get("items") or []
        assert any(int(it.get("id") or 0) == doc_id for it in items)

        fetched = client.get(f"/api/kb/documents/{doc_id}", auth=("admin", "admin"))
        assert fetched.status_code == 200
        assert fetched.json()["document"]["content_text"] == doc_text

        token = _csrf(client)
        chat = client.post(
            "/api/ai/chat/message",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"text": "Какие объективные причины отказа допустимы?"},
        )
        assert chat.status_code == 200
        payload = chat.json()
        assert payload["ok"] is True
        excerpts = payload.get("kb_excerpts_used") or []
        assert excerpts, "Expected KB excerpts to be returned for a matching query"
        assert any("причины отказа" in str(ex.get("excerpt") or "").lower() for ex in excerpts)

