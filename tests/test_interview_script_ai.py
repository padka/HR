from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.ai.llm_script_generator import (
    build_base_risk_flags,
    generate_interview_script,
    merge_with_llm_flags,
    normalize_hh_resume,
)
from backend.core.ai.service import AIService
from backend.core.ai.providers.base import Usage
from backend.core.db import async_session
from backend.domain.candidates.models import User


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def ai_interview_app(monkeypatch):
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


def test_normalize_hh_resume_raw_text_and_json():
    raw = normalize_hh_resume(
        format="raw_text",
        resume_json=None,
        resume_text="Опыт 2 года в продажах. Работал с CRM и клиентами.",
    )
    assert raw["source_format"] == "raw_text"
    assert raw["relevant_experience"] is True

    data = normalize_hh_resume(
        format="json",
        resume_json={
            "title": "Менеджер по продажам",
            "skills": ["CRM", "Переговоры"],
            "experience": [{"title": "Sales", "company": "A"}],
        },
        resume_text=None,
    )
    assert data["source_format"] == "json"
    assert data["headline"] == "Менеджер по продажам"
    assert data["relevant_experience"] is True


def test_base_risk_flags_and_merge_preserve_deterministic_flags():
    base = build_base_risk_flags(
        candidate_profile={
            "age_years": 17,
            "desired_income": "130000",
            "work_status": "только вечер",
        },
        hh_resume_norm={"relevant_experience": False, "source_quality_ok": False},
        office_context={
            "min_age": 18,
            "must_have_experience": True,
            "income_range": {"min": 60000, "max": 100000},
            "schedule_rules": "полный день с утра",
            "address": None,
            "landmarks": None,
        },
    )
    codes = [code for code, _, _ in base]
    assert "AGE_BELOW_MIN" in codes
    assert "NO_RELEVANT_EXPERIENCE" in codes
    assert "INCOME_MISMATCH" in codes
    assert "LOGISTICS_UNCLEAR" in codes

    merged = merge_with_llm_flags(
        base_flags=base,
        llm_flags=[{"code": "INCOME_MISMATCH", "severity": "low", "reason": "", "question": "", "recommended_phrase": ""}],
    )
    merged_codes = {item["code"]: item for item in merged}
    assert "AGE_BELOW_MIN" in merged_codes
    assert merged_codes["INCOME_MISMATCH"]["severity"] in {"medium", "high"}


def test_interview_script_ab_model_selection_is_deterministic():
    service = AIService()

    class _Settings:
        openai_model = "gpt-base"
        ai_interview_script_ft_model = "ft-model-v1"
        ai_interview_script_ab_percent = 50

    service._settings = _Settings()
    first = service._interview_script_model_for_candidate(1001)
    second = service._interview_script_model_for_candidate(1001)
    other = service._interview_script_model_for_candidate(1002)

    assert first == second
    assert first in {"gpt-base", "ft-model-v1"}
    assert other in {"gpt-base", "ft-model-v1"}


@pytest.mark.asyncio
async def test_generate_interview_script_retries_invalid_payload_then_succeeds():
    class FlakyProvider:
        name = "fake"

        def __init__(self) -> None:
            self.calls = 0

        async def generate_json(
            self,
            *,
            model: str,
            system_prompt: str,
            user_prompt: str,
            timeout_seconds: int,
            max_tokens: int,
        ):
            self.calls += 1
            if self.calls == 1:
                return {"bad": "payload"}, Usage(tokens_in=1, tokens_out=1)
            return (
                {
                    "risk_flags": [],
                    "highlights": ["A"],
                    "checks": ["B"],
                    "objections": [{"topic": "t", "candidate_says": "x", "recruiter_answer": "y"}],
                    "script_blocks": [
                        {
                            "id": "one",
                            "title": "one",
                            "goal": "one",
                            "recruiter_text": "one",
                            "candidate_questions": ["q1"],
                            "if_answers": [{"pattern": "p", "hint": "h"}],
                        },
                        {
                            "id": "two",
                            "title": "two",
                            "goal": "two",
                            "recruiter_text": "two",
                            "candidate_questions": ["q2"],
                            "if_answers": [{"pattern": "p", "hint": "h"}],
                        },
                        {
                            "id": "three",
                            "title": "three",
                            "goal": "three",
                            "recruiter_text": "three",
                            "candidate_questions": ["q3"],
                            "if_answers": [{"pattern": "p", "hint": "h"}],
                        },
                    ],
                    "cta_templates": [{"type": "slot", "text": "go"}],
                },
                Usage(tokens_in=11, tokens_out=12),
            )

    provider = FlakyProvider()
    result = await generate_interview_script(
        candidate_profile={"age_years": 17},
        hh_resume={"relevant_experience": False, "source_quality_ok": False},
        office_context={"min_age": 18, "address": None, "landmarks": None, "must_have_experience": True},
        rag_context=[],
        provider=provider,
        model="gpt-5-mini",
        timeout_seconds=10,
        max_tokens=900,
        retries=1,
    )
    assert provider.calls == 2
    risk_codes = {flag["code"] for flag in result.payload["risk_flags"]}
    assert "AGE_BELOW_MIN" in risk_codes


def test_interview_script_generate_cache_and_refresh(ai_interview_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Interview Candidate",
                phone=None,
                city="E2E City",
                telegram_id=913001,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_interview_app) as client:
        first = client.get(f"/api/ai/candidates/{candidate_id}/interview-script", auth=("admin", "admin"))
        assert first.status_code == 200
        p1 = first.json()
        assert p1["ok"] is True
        assert p1["cached"] is False
        assert p1["prompt_version"] == "interview_script_v1"
        assert isinstance(p1.get("script"), dict)
        assert "script_blocks" in p1["script"]

        second = client.get(f"/api/ai/candidates/{candidate_id}/interview-script", auth=("admin", "admin"))
        assert second.status_code == 200
        p2 = second.json()
        assert p2["ok"] is True
        assert p2["cached"] is True
        assert p2["input_hash"] == p1["input_hash"]

        refresh = client.post(
            f"/api/ai/candidates/{candidate_id}/interview-script/refresh",
            auth=("admin", "admin"),
            headers={"x-csrf-token": _csrf(client)},
        )
        assert refresh.status_code == 200
        p3 = refresh.json()
        assert p3["ok"] is True
        assert p3["cached"] is False


def test_interview_script_hh_resume_upsert(ai_interview_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Resume Candidate",
                phone=None,
                city="E2E City",
                telegram_id=913002,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_interview_app) as client:
        token = _csrf(client)
        raw_resp = client.put(
            f"/api/ai/candidates/{candidate_id}/hh-resume",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"format": "raw_text", "resume_text": "2 года продаж и переговоров"},
        )
        assert raw_resp.status_code == 200
        raw_payload = raw_resp.json()
        assert raw_payload["ok"] is True
        assert raw_payload["normalized_resume"]["source_format"] == "raw_text"
        assert raw_payload["content_hash"]

        json_resp = client.put(
            f"/api/ai/candidates/{candidate_id}/hh-resume",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={
                "format": "json",
                "resume_json": {
                    "title": "Менеджер",
                    "skills": ["CRM"],
                    "experience": [{"title": "Sales", "company": "A"}],
                },
            },
        )
        assert json_resp.status_code == 200
        payload = json_resp.json()
        assert payload["ok"] is True
        assert payload["normalized_resume"]["source_format"] == "json"
