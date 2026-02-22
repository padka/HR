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
def admin_app(monkeypatch):
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

        questions: list[Question] = []
        for idx in range(3):
            q = Question(
                test_id=test.id,
                title=f"Q{idx+1}",
                text=f"Q{idx+1}",
                key=f"q{idx+1}",
                payload=None,
                type="text",
                order=idx,
                is_active=True,
            )
            questions.append(q)
        session.add_all(questions)
        await session.commit()
        for q in questions:
            await session.refresh(q)
        return [int(q.id) for q in questions]


def _linear_graph(question_ids: list[int]) -> dict:
    nodes = [{"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {"label": "Start"}}]
    edges = []
    y = 120
    prev = "start"
    for qid in question_ids:
        node_id = f"q_{qid}"
        nodes.append(
            {"id": node_id, "type": "question", "position": {"x": 0, "y": y}, "data": {"question_id": qid}}
        )
        edges.append({"id": f"e_{prev}_{node_id}", "source": prev, "target": node_id})
        prev = node_id
        y += 120
    nodes.append({"id": "end", "type": "end", "position": {"x": 0, "y": y}, "data": {"label": "End"}})
    edges.append({"id": f"e_{prev}_end", "source": prev, "target": "end"})
    return {"schema": "xyflow_v1", "nodes": nodes, "edges": edges}


def test_test_builder_graph_get_returns_default_linear_graph(admin_app):
    qids = _run(_seed_test1_questions())
    with TestClient(admin_app) as client:
        resp = client.get("/api/test-builder/graph", params={"test_id": "test1"}, auth=("admin", "admin"))
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        graph = payload["graph"]
        assert isinstance(graph, dict)
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        assert len(nodes) == len(qids) + 2
        assert len(edges) == len(qids) + 1


def test_test_builder_graph_apply_reorders_questions(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _linear_graph(list(reversed(qids)))
    with TestClient(admin_app) as client:
        token = _csrf(client)
        resp = client.post(
            "/api/test-builder/graph/apply",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"test_id": "test1", "graph": graph},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        listed = client.get("/api/questions", auth=("admin", "admin"))
        assert listed.status_code == 200
        groups = listed.json()
        test1 = next((g for g in groups if g.get("test_id") == "test1"), None)
        assert test1 is not None
        got_ids = [int(q["id"]) for q in test1["questions"]]
        assert got_ids == list(reversed(qids))


def test_test_builder_graph_apply_rejects_non_linear(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _linear_graph(qids)
    # Add extra outgoing edge from start to create a branch.
    graph["edges"].append({"id": "e_start_branch", "source": "start", "target": f"q_{qids[1]}"})
    with TestClient(admin_app) as client:
        token = _csrf(client)
        resp = client.post(
            "/api/test-builder/graph/apply",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"test_id": "test1", "graph": graph},
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["ok"] is False
        assert payload["error"] in {"graph_not_linear", "invalid_graph"}

