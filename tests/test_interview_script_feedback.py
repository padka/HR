from __future__ import annotations

import asyncio
import importlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.core.db import async_session
from backend.domain.ai.models import AIInterviewScriptFeedback
from backend.domain.candidates.models import User


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def ai_feedback_app(monkeypatch):
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
    state_module = importlib.reload(importlib.import_module("backend.apps.admin_ui.state"))
    importlib.reload(importlib.import_module("backend.apps.admin_ui.security"))
    importlib.reload(importlib.import_module("backend.apps.admin_ui.routers.auth"))
    importlib.reload(importlib.import_module("backend.apps.admin_ui.routers.api_misc"))
    importlib.reload(importlib.import_module("backend.apps.admin_ui.routers.ai"))
    app_module = importlib.reload(importlib.import_module("backend.apps.admin_ui.app"))
    monkeypatch.setattr(state_module, "setup_bot_state", fake_setup)
    monkeypatch.setattr(app_module, "setup_bot_state", fake_setup)
    app = app_module.create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _csrf(client: TestClient) -> str:
    resp = client.get("/api/csrf", auth=("admin", "admin"))
    assert resp.status_code == 200
    token = resp.json().get("token")
    assert token
    return str(token)


def test_interview_script_feedback_persists_and_idempotent(ai_feedback_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Feedback Candidate",
                phone=None,
                city="E2E City",
                telegram_id=913101,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_feedback_app) as client:
        token = _csrf(client)
        script_resp = client.get(f"/api/ai/candidates/{candidate_id}/interview-script", auth=("admin", "admin"))
        assert script_resp.status_code == 200
        script_payload = script_resp.json().get("script") or {}

        idem = f"idem-{uuid.uuid4().hex[:24]}"
        feedback_payload = {
            "helped": True,
            "edited": True,
            "quick_reasons": ["слишком длинно"],
            "final_script": script_payload,
            "outcome": "od_assigned",
            "outcome_reason": "кандидат согласовал слот",
            "scorecard": {
                "completed_questions": 4,
                "total_questions": 5,
                "average_rating": 4.25,
                "overall_recommendation": "recommend",
                "final_comment": "Кандидат уверенно отвечает на уточняющие вопросы.",
                "timer_elapsed_sec": 1280,
                "items": [
                    {
                        "question_id": "q1",
                        "rating": 4,
                        "skipped": False,
                        "notes": "Есть конкретные примеры.",
                    }
                ],
            },
            "idempotency_key": idem,
        }

        first = client.post(
            f"/api/ai/candidates/{candidate_id}/interview-script/feedback",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json=feedback_payload,
        )
        assert first.status_code == 200
        p1 = first.json()
        assert p1["ok"] is True
        assert p1["created"] is True
        feedback_id = int(p1["feedback_id"])

        second = client.post(
            f"/api/ai/candidates/{candidate_id}/interview-script/feedback",
            auth=("admin", "admin"),
            headers={"x-csrf-token": _csrf(client)},
            json=feedback_payload,
        )
        assert second.status_code == 200
        p2 = second.json()
        assert p2["ok"] is True
        assert p2["created"] is False
        assert int(p2["feedback_id"]) == feedback_id

    async def _assert_db() -> None:
        async with async_session() as session:
            total = await session.scalar(
                select(func.count(AIInterviewScriptFeedback.id)).where(
                    AIInterviewScriptFeedback.candidate_id == candidate_id
                )
            )
            assert int(total or 0) == 1
            row = await session.scalar(
                select(AIInterviewScriptFeedback).where(AIInterviewScriptFeedback.id == feedback_id)
            )
            assert row is not None
            assert row.output_final_json is not None
            assert row.labels_json.get("outcome") == "od_assigned"
            assert row.labels_json.get("scorecard", {}).get("average_rating") == 4.25

    _run(_assert_db())


def test_interview_script_feedback_requires_csrf_and_valid_payload(ai_feedback_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Feedback Candidate 2",
                phone=None,
                city="E2E City",
                telegram_id=913102,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_feedback_app) as client:
        token = _csrf(client)
        invalid = client.post(
            f"/api/ai/candidates/{candidate_id}/interview-script/feedback",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"helped": True},
        )
        assert invalid.status_code == 400
