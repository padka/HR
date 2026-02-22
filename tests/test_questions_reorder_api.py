from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.tests.models import Question, Test


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture
def questions_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        app.state.notification_service = None
        app.state.notification_broker_available = False
        return _DummyIntegration()

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


async def _seed_test1_questions() -> list[int]:
    async with async_session() as session:
        test = Test(slug="test1", title="Анкета")
        session.add(test)
        await session.commit()
        await session.refresh(test)

        q1 = Question(
            test_id=test.id,
            title="Q1",
            text="Q1",
            key="q1",
            payload=None,
            type="text",
            order=0,
            is_active=True,
        )
        q2 = Question(
            test_id=test.id,
            title="Q2",
            text="Q2",
            key="q2",
            payload=None,
            type="text",
            order=1,
            is_active=True,
        )
        q3 = Question(
            test_id=test.id,
            title="Q3",
            text="Q3",
            key="q3",
            payload=None,
            type="text",
            order=2,
            is_active=True,
        )
        session.add_all([q1, q2, q3])
        await session.commit()
        await session.refresh(q1)
        await session.refresh(q2)
        await session.refresh(q3)
        return [int(q1.id), int(q2.id), int(q3.id)]


def test_questions_reorder_updates_order_and_listing(questions_app):
    qids = _run(_seed_test1_questions())
    with TestClient(questions_app) as client:
        token = _csrf(client)
        resp = client.post(
            "/api/questions/reorder",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"test_id": "test1", "order": [qids[2], qids[1], qids[0]]},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        listed = client.get("/api/questions", auth=("admin", "admin"))
        assert listed.status_code == 200
        groups = listed.json()
        test1 = next((g for g in groups if g.get("test_id") == "test1"), None)
        assert test1 is not None
        got_ids = [int(q["id"]) for q in test1["questions"]]
        assert got_ids == [qids[2], qids[1], qids[0]]


def test_questions_reorder_rejects_partial_payload(questions_app):
    qids = _run(_seed_test1_questions())
    with TestClient(questions_app) as client:
        token = _csrf(client)
        resp = client.post(
            "/api/questions/reorder",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"test_id": "test1", "order": [qids[0], qids[1]]},
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["ok"] is False
        assert payload["error"] == "order_mismatch"


def test_questions_reorder_rejects_duplicate_ids(questions_app):
    qids = _run(_seed_test1_questions())
    with TestClient(questions_app) as client:
        token = _csrf(client)
        resp = client.post(
            "/api/questions/reorder",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"test_id": "test1", "order": [qids[0], qids[0], qids[1], qids[2]]},
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["ok"] is False
        assert payload["error"] == "duplicate_ids"

