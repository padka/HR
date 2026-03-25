from __future__ import annotations

import asyncio
import importlib

import pytest
from fastapi.testclient import TestClient

from backend.core.ai.llm_script_generator import (
    SMART_SERVICE_BLOCK_ORDER,
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
                    "stage_label": "Первичный скрининг",
                    "call_goal": "Понять базовую релевантность кандидата и перейти к следующему этапу.",
                    "conversation_script": "- Вступление\n- Уточнить опыт\n- Закрыть на следующий шаг",
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
        candidate_state={"status": "test1_completed"},
        candidate_profile={"age_years": 17},
        hh_resume={"relevant_experience": False, "source_quality_ok": False},
        office_context={"min_age": 18, "address": None, "landmarks": None, "must_have_experience": True},
        scorecard={"recommendation": "clarify_before_od"},
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
    assert result.payload["conversation_script"]
    assert not result.payload["conversation_script"].lstrip().startswith("-")
    assert [block["id"] for block in result.payload["script_blocks"]] == SMART_SERVICE_BLOCK_ORDER


@pytest.mark.asyncio
async def test_generate_interview_script_suppresses_od_cta_for_not_recommended():
    class Provider:
        name = "fake"

        async def generate_json(
            self,
            *,
            model: str,
            system_prompt: str,
            user_prompt: str,
            timeout_seconds: int,
            max_tokens: int,
        ):
            return (
                {
                    "stage_label": "Финальная сверка",
                    "call_goal": "Понять, можно ли двигаться дальше.",
                    "conversation_script": "1. Поблагодарить\n2. Предложить ознакомительный день",
                    "risk_flags": [],
                    "highlights": ["A"],
                    "checks": ["B"],
                    "objections": [{"topic": "t", "candidate_says": "x", "recruiter_answer": "y"}],
                    "script_blocks": [],
                    "cta_templates": [{"type": "slot_confirm", "text": "Подтверждаю слот на ознакомительный день."}],
                },
                Usage(tokens_in=5, tokens_out=5),
            )

    result = await generate_interview_script(
        candidate_state={"status": "not_hired"},
        candidate_profile={},
        hh_resume={},
        office_context={},
        scorecard={"recommendation": "not_recommended"},
        rag_context=[],
        provider=Provider(),
        model="gpt-5-mini",
        timeout_seconds=10,
        max_tokens=900,
        retries=0,
    )
    closing_block = next(block for block in result.payload["script_blocks"] if block["id"] == "od_closing_and_confirmation")
    assert "ознаком" not in closing_block["recruiter_text"].lower()
    assert not any("ознаком" in item["text"].lower() for item in result.payload["cta_templates"])
    assert "ознаком" not in result.payload["conversation_script"].lower()


@pytest.mark.asyncio
async def test_generate_interview_script_uses_stage_aware_confirmation_flow():
    class Provider:
        name = "fake"

        async def generate_json(
            self,
            *,
            model: str,
            system_prompt: str,
            user_prompt: str,
            timeout_seconds: int,
            max_tokens: int,
        ):
            return (
                {
                    "stage_label": "Подтверждение собеседования",
                    "call_goal": "Подтвердить участие во встрече.",
                    "conversation_script": "",
                    "risk_flags": [],
                    "highlights": ["A"],
                    "checks": ["B"],
                    "objections": [],
                    "script_blocks": [
                        {
                            "id": "greeting_and_frame",
                            "title": "one",
                            "goal": "one",
                            "recruiter_text": "Здравствуйте. Проверяю, что время интервью вам подходит.",
                            "candidate_questions": ["Сможете быть на связи в назначённое время?"],
                            "if_answers": [],
                        }
                    ],
                    "cta_templates": [{"type": "confirm", "text": "Подтверждаю встречу и отправляю детали."}],
                },
                Usage(tokens_in=5, tokens_out=5),
            )

    result = await generate_interview_script(
        candidate_state={"status": "interview_confirmed", "upcoming_slot_purpose": "interview"},
        candidate_profile={},
        hh_resume={},
        office_context={"city": "Москва"},
        scorecard={"recommendation": "clarify_before_od"},
        rag_context=[],
        provider=Provider(),
        model="gpt-5-mini",
        timeout_seconds=10,
        max_tokens=900,
        retries=0,
    )
    assert result.payload["stage_label"] == "Подтверждение собеседования"
    assert "назначённое время" in result.payload["conversation_script"].lower()
    assert "ознакомительный день" not in result.payload["conversation_script"].lower()


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
        assert p1["prompt_version"] == "interview_script_v2"
        assert isinstance(p1.get("script"), dict)
        assert p1["script"]["conversation_script"]
        assert "script_blocks" in p1["script"]
        assert p1["script"]["briefing"]["goal"]
        assert p1["script"]["opening"]["greeting"]
        assert p1["script"]["questions"]
        assert p1["script"]["closing_checklist"]

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


def test_interview_script_route_uses_local_fallback_on_initial_load(ai_interview_app, monkeypatch):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Fallback Script Candidate",
                phone=None,
                city="E2E City",
                telegram_id=913099,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    async def _fail_generate_json(*_args, **_kwargs):
        raise AssertionError("provider must not be called on initial script load")

    monkeypatch.setattr("backend.core.ai.providers.fake.FakeProvider.generate_json", _fail_generate_json)
    candidate_id = _run(_seed())

    with TestClient(ai_interview_app) as client:
        response = client.get(f"/api/ai/candidates/{candidate_id}/interview-script", auth=("admin", "admin"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "local-fallback"
    assert payload["script"]["conversation_script"]
    assert [block["id"] for block in payload["script"]["script_blocks"]] == SMART_SERVICE_BLOCK_ORDER
