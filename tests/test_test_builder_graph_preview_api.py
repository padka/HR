from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.tests.models import AnswerOption, Question, Test


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

        q_status = Question(
            test_id=test.id,
            title="Статус",
            text="На данный момент вы учитесь / работаете?",
            key="status",
            payload=None,
            type="single_choice",
            order=0,
            is_active=True,
        )
        q_format = Question(
            test_id=test.id,
            title="Формат",
            text="Готовы работать в гибридном формате?",
            key="format",
            payload=None,
            type="single_choice",
            order=1,
            is_active=True,
        )
        q_about = Question(
            test_id=test.id,
            title="О себе",
            text="Что вас мотивирует?",
            key="about",
            payload={"placeholder": "Например: рост и доход"},
            type="text",
            order=2,
            is_active=True,
        )
        session.add_all([q_status, q_format, q_about])
        await session.commit()
        await session.refresh(q_status)
        await session.refresh(q_format)
        await session.refresh(q_about)

        status_options = ["Учусь", "Работаю", "Ищу работу", "Предприниматель", "Другое"]
        format_options = ["Да, готов", "Нужен гибкий график", "Пока не готов"]

        for idx, text in enumerate(status_options):
            session.add(
                AnswerOption(
                    question_id=q_status.id,
                    text=text,
                    is_correct=False,
                    points=0.0,
                    sort_order=idx,
                )
            )
        for idx, text in enumerate(format_options):
            session.add(
                AnswerOption(
                    question_id=q_format.id,
                    text=text,
                    is_correct=False,
                    points=0.0,
                    sort_order=idx,
                )
            )

        await session.commit()
        return [int(q_status.id), int(q_format.id), int(q_about.id)]


def _edge(
    source: str,
    target: str,
    *,
    when: str | None = None,
    fallback: bool = False,
    action: str = "next",
    reason: str | None = None,
    template_key: str | None = None,
) -> dict:
    data: dict[str, object] = {"action": action}
    if when is not None:
        data["when"] = when
        data["match"] = "equals"
    if fallback:
        data["fallback"] = True
    if reason:
        data["reason"] = reason
    if template_key:
        data["template_key"] = template_key
    return {
        "id": f"e_{source}_{target}_{when or ('fallback' if fallback else 'default')}",
        "source": source,
        "target": target,
        "data": data,
    }


def _status_branch_graph(status_qid: int, about_qid: int) -> dict:
    nodes = [
        {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {"label": "Start"}},
        {
            "id": f"q_{status_qid}",
            "type": "question",
            "position": {"x": 0, "y": 120},
            "data": {"question_id": status_qid},
        },
        {
            "id": "vq_study_mode",
            "type": "question",
            "position": {"x": -320, "y": 280},
            "data": {
                "key": "study_mode",
                "prompt": "Учитесь очно или заочно?",
                "options": ["Очно", "Заочно"],
            },
        },
        {
            "id": "vq_study_schedule",
            "type": "question",
            "position": {"x": -320, "y": 440},
            "data": {
                "key": "study_schedule",
                "prompt": "Сможете совмещать график 5/2 с 9:00 до 18:00?",
                "options": ["Да, смогу", "Нет, не смогу"],
            },
        },
        {
            "id": "vq_notice",
            "type": "question",
            "position": {"x": 220, "y": 420},
            "data": {
                "key": "notice_period",
                "prompt": "Сколько времени потребуется, чтобы завершить текущие дела и приступить к обучению?",
                "placeholder": "Например: 1-2 дня",
            },
        },
        {
            "id": f"q_{about_qid}",
            "type": "question",
            "position": {"x": 220, "y": 620},
            "data": {"question_id": about_qid},
        },
        {"id": "end", "type": "end", "position": {"x": 220, "y": 780}, "data": {"label": "End"}},
    ]

    edges = [
        _edge("start", f"q_{status_qid}", fallback=True),
        _edge(f"q_{status_qid}", "vq_study_mode", when="Учусь"),
        _edge(f"q_{status_qid}", "vq_notice", when="Работаю"),
        _edge(f"q_{status_qid}", "vq_notice", when="Ищу работу"),
        _edge(f"q_{status_qid}", "vq_notice", when="Предприниматель"),
        _edge(f"q_{status_qid}", "vq_notice", fallback=True),
        _edge("vq_study_mode", "vq_study_schedule", when="Очно"),
        _edge("vq_study_mode", "vq_notice", when="Заочно"),
        _edge("vq_study_mode", "vq_notice", fallback=True),
        _edge("vq_study_schedule", "vq_notice", when="Да, смогу"),
        # По требованию: не блокируем здесь никого, всех пропускаем дальше
        _edge("vq_study_schedule", "vq_notice", fallback=True),
        _edge("vq_notice", f"q_{about_qid}", fallback=True),
        _edge(f"q_{about_qid}", "end", fallback=True),
    ]

    return {"schema": "xyflow_v1", "nodes": nodes, "edges": edges}


def _reject_graph(status_qid: int, about_qid: int) -> dict:
    graph = _status_branch_graph(status_qid, about_qid)
    graph["edges"].append(
        _edge(
            f"q_{status_qid}",
            "end",
            when="Другое",
            action="reject",
            reason="Нет релевантного статуса для сценария.",
            template_key="t1_schedule_reject",
        )
    )
    return graph


def _preview(client: TestClient, token: str, graph: dict, answers: list[str]) -> dict:
    resp = client.post(
        "/api/test-builder/graph/preview",
        auth=("admin", "admin"),
        headers={"x-csrf-token": token},
        json={"test_id": "test1", "graph": graph, "answers": answers},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ok"] is True
    return payload


def test_graph_preview_starts_from_status_question(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _status_branch_graph(qids[0], qids[2])

    with TestClient(admin_app) as client:
        token = _csrf(client)
        payload = _preview(client, token, graph, [])

    assert payload["halted"] is False
    assert payload["done"] is False
    assert payload["next_question"]["key"] == "status"


def test_graph_preview_branches_study_flow(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _status_branch_graph(qids[0], qids[2])

    with TestClient(admin_app) as client:
        token = _csrf(client)
        payload = _preview(client, token, graph, ["Учусь", "Очно"])

    assert payload["halted"] is False
    assert payload["done"] is False
    assert payload["next_question"]["key"] == "study_schedule"


def test_graph_preview_study_schedule_is_not_blocking(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _status_branch_graph(qids[0], qids[2])

    with TestClient(admin_app) as client:
        token = _csrf(client)
        payload = _preview(client, token, graph, ["Учусь", "Очно", "Нет, не смогу"])

    assert payload["halted"] is False
    assert payload["done"] is False
    assert payload["next_question"]["key"] == "notice_period"


def test_graph_preview_working_branch_goes_to_notice_period(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _status_branch_graph(qids[0], qids[2])

    with TestClient(admin_app) as client:
        token = _csrf(client)
        payload = _preview(client, token, graph, ["Работаю"])

    assert payload["halted"] is False
    assert payload["next_question"]["key"] == "notice_period"


def test_graph_preview_supports_reject_edge(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _reject_graph(qids[0], qids[2])

    with TestClient(admin_app) as client:
        token = _csrf(client)
        payload = _preview(client, token, graph, ["Другое"])

    assert payload["halted"] is True
    assert payload["halt_reason"] == "reject"
    last_step = payload["steps"][-1]
    assert last_step["status"] == "reject"
    assert last_step["reaction"]["template_key"] == "t1_schedule_reject"


def test_graph_preview_marks_invalid_option(admin_app):
    qids = _run(_seed_test1_questions())
    graph = _status_branch_graph(qids[0], qids[2])

    with TestClient(admin_app) as client:
        token = _csrf(client)
        payload = _preview(client, token, graph, ["Неверный вариант"])

    assert payload["halted"] is True
    assert payload["halt_reason"] == "invalid"
    assert payload["steps"][0]["status"] == "invalid"
    assert payload["next_question"]["key"] == "status"
