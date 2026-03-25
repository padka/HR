from __future__ import annotations

import asyncio
import importlib

import pytest
from backend.apps.admin_ui.security import Principal
from backend.core.ai.candidate_scorecard import build_candidate_scorecard
from backend.core.ai.context import build_candidate_ai_context
from backend.core.ai.redaction import redact_text
from backend.core.db import async_session
from backend.domain.candidates.models import QuestionAnswer, TestResult, User
from backend.domain.models import City, Recruiter, recruiter_city_association
from fastapi.testclient import TestClient


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def ai_app(monkeypatch):
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


def test_ai_redaction_masks_phone_email_urls_and_known_names():
    raw = (
        "Иван Иванов, мой телефон +7 900 000-00-00, почта test@example.com.\n"
        "Ссылка: https://example.com и @some_user. id 1234567"
    )
    result = redact_text(raw, candidate_fio="Иван Иванов", recruiter_name="Петр Петров")
    assert result.safe_to_send is True
    assert "Иван" not in result.text
    assert "Иванов" not in result.text
    assert "test@example.com" not in result.text
    assert "https://example.com" not in result.text
    assert "@some_user" not in result.text
    assert "900" not in result.text
    assert "1234567" not in result.text
    assert "PHONE" in result.text
    assert "EMAIL" in result.text
    assert "URL" in result.text
    assert "USERNAME" in result.text
    assert "ID" in result.text


def test_ai_redaction_allows_numeric_answers():
    r1 = redact_text("27")
    assert r1.safe_to_send is True
    assert r1.text == "27"

    r2 = redact_text("60 000 – 90 000 ›")
    assert r2.safe_to_send is True
    assert "60" in r2.text


@pytest.mark.asyncio
async def test_ai_context_builder_excludes_pii_fields():
    async with async_session() as session:
        user = User(
            fio="Sensitive Name",
            phone="+79991234567",
            telegram_id=555123,
            telegram_username="sensitive_user",
            username="legacy_username",
            city="E2E City",
            source="bot",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        candidate_id = int(user.id)

    ctx = await build_candidate_ai_context(candidate_id, principal=Principal(type="admin", id=-1))

    # Explicit exclusions
    assert "fio" not in ctx.get("candidate", {})
    assert "phone" not in ctx.get("candidate", {})
    assert "telegram_id" not in ctx.get("candidate", {})
    assert "telegram_username" not in ctx.get("candidate", {})
    assert "username" not in ctx.get("candidate", {})

    # Ensure raw values aren't present anywhere in serialized context
    import json

    raw_dump = json.dumps(ctx, ensure_ascii=False)
    assert "Sensitive Name" not in raw_dump
    assert "+79991234567" not in raw_dump
    assert "555123" not in raw_dump
    assert "sensitive_user" not in raw_dump


@pytest.mark.asyncio
async def test_ai_context_redacts_question_answers():
    async with async_session() as session:
        user = User(
            fio="Sensitive Name",
            phone="+79991234567",
            telegram_id=555123,
            telegram_username="sensitive_user",
            city="E2E City",
            source="bot",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        tr = TestResult(
            user_id=user.id,
            raw_score=0,
            final_score=0.0,
            rating="TEST1",
            total_time=10,
            source="bot",
        )
        session.add(tr)
        await session.commit()
        await session.refresh(tr)

        qa = QuestionAnswer(
            test_result_id=tr.id,
            question_index=0,
            question_text="Напишите ваш телефон и почту",
            correct_answer=None,
            user_answer="Мой телефон +7 900 000-00-00, почта test@example.com",
            attempts_count=1,
            time_spent=2,
            is_correct=False,
            overtime=False,
        )
        session.add(qa)
        await session.commit()

        candidate_id = int(user.id)

    ctx = await build_candidate_ai_context(candidate_id, principal=Principal(type="admin", id=-1))
    import json

    raw_dump = json.dumps(ctx, ensure_ascii=False)
    assert "+7 900 000-00-00" not in raw_dump
    assert "test@example.com" not in raw_dump
    assert "Sensitive Name" not in raw_dump
    assert "PHONE" in raw_dump
    assert "EMAIL" in raw_dump


@pytest.mark.asyncio
async def test_ai_context_extracts_age_and_desired_income():
    async with async_session() as session:
        user = User(
            fio="Sensitive Name",
            phone=None,
            telegram_id=555124,
            telegram_username="sensitive_user2",
            city="E2E City",
            source="bot",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        tr = TestResult(
            user_id=user.id,
            raw_score=0,
            final_score=0.0,
            rating="TEST1",
            total_time=10,
            source="bot",
        )
        session.add(tr)
        await session.commit()
        await session.refresh(tr)

        session.add_all(
            [
                QuestionAnswer(
                    test_result_id=tr.id,
                    question_index=2,
                    question_text="3‰ Сколько вам полных лет?",
                    correct_answer=None,
                    user_answer="27",
                    attempts_count=1,
                    time_spent=1,
                    is_correct=True,
                    overtime=False,
                ),
                QuestionAnswer(
                    test_result_id=tr.id,
                    question_index=4,
                    question_text="5‰ Желаемый уровень дохода в первые 3 месяца?",
                    correct_answer=None,
                    user_answer="60 000 – 90 000 ›",
                    attempts_count=1,
                    time_spent=1,
                    is_correct=True,
                    overtime=False,
                ),
            ]
        )
        await session.commit()
        candidate_id = int(user.id)

    ctx = await build_candidate_ai_context(candidate_id, principal=Principal(type="admin", id=-1))
    profile = ctx.get("candidate_profile") or {}
    assert profile.get("age_years") == 27
    assert "60" in str(profile.get("desired_income") or "")


@pytest.mark.asyncio
async def test_ai_context_derives_customer_facing_signals_from_experience():
    async with async_session() as session:
        user = User(
            fio="Signals Candidate",
            phone=None,
            telegram_id=555125,
            city="E2E City",
            source="bot",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        tr = TestResult(
            user_id=user.id,
            raw_score=10,
            final_score=10.0,
            rating="TEST1",
            total_time=20,
            source="bot",
        )
        session.add(tr)
        await session.commit()
        await session.refresh(tr)

        session.add(
            QuestionAnswer(
                test_result_id=tr.id,
                question_index=7,
                question_text="Опишите ваш опыт в продажах/переговорах или смежных областях",
                correct_answer=None,
                user_answer="3 года работала бариста, затем офис-менеджером.",
                attempts_count=1,
                time_spent=1,
                is_correct=True,
                overtime=False,
            )
        )
        await session.commit()
        candidate_id = int(user.id)

    ctx = await build_candidate_ai_context(candidate_id, principal=Principal(type="admin", id=-1))
    signals = (ctx.get("candidate_profile") or {}).get("signals") or {}
    people = signals.get("people_interaction") or {}
    comm = signals.get("communication") or {}
    assert people.get("level") == "high"
    assert "бариста" in str(people.get("evidence") or "").lower()
    assert comm.get("level") in {"medium", "high"}


@pytest.mark.asyncio
async def test_ai_context_extracts_field_format_answer_from_test1():
    async with async_session() as session:
        user = User(
            fio="Field Format Candidate",
            phone=None,
            telegram_id=555126,
            city="E2E City",
            source="bot",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        tr = TestResult(
            user_id=user.id,
            raw_score=10,
            final_score=10.0,
            rating="TEST1",
            total_time=20,
            source="bot",
        )
        session.add(tr)
        await session.commit()
        await session.refresh(tr)

        session.add(
            QuestionAnswer(
                test_result_id=tr.id,
                question_index=4,
                question_text="Готовы ли вы к полевому формату работы и выездам по городу?",
                correct_answer=None,
                user_answer="Да, без проблем",
                attempts_count=1,
                time_spent=1,
                is_correct=True,
                overtime=False,
            )
        )
        await session.commit()
        candidate_id = int(user.id)

    ctx = await build_candidate_ai_context(candidate_id, principal=Principal(type="admin", id=-1))
    profile = ctx.get("candidate_profile") or {}
    assert profile.get("field_format_readiness") == "Да, без проблем"


@pytest.mark.asyncio
async def test_ai_context_scoping_blocks_other_recruiter():
    from fastapi import HTTPException

    async with async_session() as session:
        city1 = City(name="City One", tz="Europe/Moscow", active=True)
        city2 = City(name="City Two", tz="Europe/Moscow", active=True)
        r1 = Recruiter(name="R1", tz="Europe/Moscow", active=True)
        r2 = Recruiter(name="R2", tz="Europe/Moscow", active=True)
        session.add_all([city1, city2, r1, r2])
        await session.commit()
        await session.refresh(city1)
        await session.refresh(city2)
        await session.refresh(r1)
        await session.refresh(r2)

        await session.execute(
            recruiter_city_association.insert().values(recruiter_id=r1.id, city_id=city1.id)
        )
        await session.commit()

        user = User(
            fio="Scoped Candidate",
            phone=None,
            city=city2.name,
            responsible_recruiter_id=r2.id,
            telegram_id=777001,
            source="bot",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        candidate_id = int(user.id)

    with pytest.raises(HTTPException) as exc:
        await build_candidate_ai_context(candidate_id, principal=Principal(type="recruiter", id=r1.id))
    assert exc.value.status_code == 404


def test_candidate_scorecard_caps_final_score_on_hard_blocker():
    state = build_candidate_scorecard(
        context={
            "candidate_profile": {
                "work_experience": "3 года в продажах и переговорах, много встреч с клиентами",
                "motivation": "Интересен доход, развитие и общение с предпринимателями",
                "skills": "переговоры, продажи",
                "expectations": "Хочу зарабатывать и расти",
                "signals": {
                    "people_interaction": {"level": "high"},
                    "communication": {"level": "high"},
                },
            },
            "tests": {"latest": {"TEST1": {"final_score": 3.0}}},
            "interview_notes": {"fields": {}},
        },
        resume_context={
            "headline": "Менеджер по продажам",
            "summary": "Работал с клиентами и выездными встречами",
            "skills": ["CRM", "переговоры"],
            "employment_items": [{"company": "A", "title": "Sales manager"}],
            "relevant_experience": True,
        },
        llm_scorecard={
            "metrics": [
                {"key": "resume_substance", "score": 30, "status": "met", "evidence": "ok"},
                {"key": "answer_substance", "score": 25, "status": "met", "evidence": "ok"},
                {"key": "client_communication_inference", "score": 25, "status": "met", "evidence": "ok"},
                {"key": "interest_for_role", "score": 20, "status": "met", "evidence": "ok"},
            ]
        },
    )
    assert state.objective_score == 80
    assert state.semantic_score == 100
    assert state.final_score == 49
    assert state.recommendation == "not_recommended"
    assert any(item["key"] == "test_gate_failed" for item in state.blockers)


def test_candidate_scorecard_marks_positive_field_format_answer_as_met():
    state = build_candidate_scorecard(
        context={
            "candidate_profile": {
                "field_format_readiness": "Да, подходит",
                "work_experience": "Есть опыт общения с клиентами",
                "motivation": "Интересен доход и развитие",
                "signals": {
                    "people_interaction": {"level": "high"},
                    "communication": {"level": "high"},
                },
            },
            "tests": {"latest": {"TEST1": {"final_score": 4.7}}},
            "interview_notes": {"fields": {}},
        },
        resume_context={
            "headline": "Менеджер",
            "summary": "Работал с клиентами",
            "skills": ["переговоры"],
            "employment_items": [],
            "relevant_experience": True,
        },
        llm_scorecard=None,
    )
    metric = next(item for item in state.metrics if item["key"] == "field_format_readiness")
    assert metric["status"] == "met"
    assert metric["score"] == 20
    assert not any(item["key"] == "field_format_readiness" for item in state.missing_data)
    assert not any(item["key"] == "field_format_refusal" for item in state.blockers)


def test_candidate_scorecard_marks_conditional_field_format_answer_as_unknown_not_risk():
    state = build_candidate_scorecard(
        context={
            "candidate_profile": {
                "field_format_readiness": "Готов, если условия устраивают",
                "work_experience": "Есть опыт общения с клиентами",
                "motivation": "Интересен доход",
                "signals": {
                    "people_interaction": {"level": "high"},
                    "communication": {"level": "high"},
                },
            },
            "tests": {"latest": {"TEST1": {"final_score": 4.5}}},
            "interview_notes": {"fields": {}},
        },
        resume_context={
            "headline": "Менеджер",
            "summary": "Работал с клиентами",
            "skills": ["переговоры"],
            "employment_items": [],
            "relevant_experience": True,
        },
        llm_scorecard=None,
    )
    metric = next(item for item in state.metrics if item["key"] == "field_format_readiness")
    assert metric["status"] == "unknown"
    assert any(item["key"] == "field_format_readiness" for item in state.missing_data)
    assert not any(item["key"] == "field_format_refusal" for item in state.blockers)


def test_ai_summary_cache_reuse_by_input_hash(ai_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Cache Candidate",
                phone=None,
                city="E2E City",
                telegram_id=888001,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_app) as client:
        r1 = client.get(
            f"/api/ai/candidates/{candidate_id}/summary",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )
        assert r1.status_code == 200
        p1 = r1.json()
        assert p1["ok"] is True
        assert p1["cached"] is False
        assert "summary" in p1

        r2 = client.get(
            f"/api/ai/candidates/{candidate_id}/summary",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )
        assert r2.status_code == 200
        p2 = r2.json()
        assert p2["ok"] is True
        assert p2["cached"] is True
        assert p2["input_hash"] == p1["input_hash"]


def test_ai_summary_and_coach_share_canonical_score(ai_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Score Candidate",
                phone=None,
                city="E2E City",
                telegram_id=888101,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            tr = TestResult(
                user_id=user.id,
                raw_score=7,
                final_score=4.5,
                rating="TEST1",
                total_time=120,
                source="bot",
            )
            session.add(tr)
            await session.commit()
            await session.refresh(tr)

            session.add(
                QuestionAnswer(
                    test_result_id=tr.id,
                    question_index=7,
                    question_text="Опишите ваш опыт",
                    correct_answer=None,
                    user_answer="2 года работал в продажах и много общался с клиентами",
                    attempts_count=1,
                    time_spent=30,
                    is_correct=True,
                    overtime=False,
                )
            )
            await session.commit()
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_app) as client:
        summary_resp = client.get(f"/api/ai/candidates/{candidate_id}/summary", auth=("admin", "admin"))
        coach_resp = client.get(f"/api/ai/candidates/{candidate_id}/coach", auth=("admin", "admin"))

    assert summary_resp.status_code == 200
    assert coach_resp.status_code == 200
    summary_payload = summary_resp.json()["summary"]
    coach_payload = coach_resp.json()["coach"]
    scorecard = summary_payload["scorecard"]
    assert scorecard["final_score"] == summary_payload["fit"]["score"]
    assert summary_payload["fit"]["level"] == coach_payload["relevance_level"]
    assert coach_payload["relevance_score"] == scorecard["final_score"]
    assert len(scorecard["metrics"]) >= 5


def test_ai_resume_upsert_changes_summary_input_hash(ai_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Resume Candidate",
                phone=None,
                city="E2E City",
                telegram_id=888102,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_app) as client:
        initial = client.get(f"/api/ai/candidates/{candidate_id}/summary", auth=("admin", "admin"))
        assert initial.status_code == 200
        initial_hash = initial.json()["input_hash"]

        upsert = client.put(
            f"/api/ai/candidates/{candidate_id}/hh-resume",
            auth=("admin", "admin"),
            headers={"x-csrf-token": _csrf(client)},
            json={
                "format": "raw_text",
                "resume_text": "3 года в продажах, переговоры с клиентами, выездные встречи, CRM",
            },
        )
        assert upsert.status_code == 200

        updated = client.get(f"/api/ai/candidates/{candidate_id}/summary", auth=("admin", "admin"))
        assert updated.status_code == 200
        assert updated.json()["input_hash"] != initial_hash


def test_ai_summary_uses_local_fallback_when_provider_not_needed(ai_app, monkeypatch):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Fallback Summary Candidate",
                phone=None,
                city="E2E City",
                telegram_id=888103,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    async def _fail_generate_json(*_args, **_kwargs):
        raise AssertionError("provider must not be called on initial summary load")

    monkeypatch.setattr("backend.core.ai.providers.fake.FakeProvider.generate_json", _fail_generate_json)

    candidate_id = _run(_seed())
    with TestClient(ai_app) as client:
        response = client.get(f"/api/ai/candidates/{candidate_id}/summary", auth=("admin", "admin"))

    assert response.status_code == 200
    payload = response.json()["summary"]
    assert payload["scorecard"]["final_score"] is not None
    assert payload["fit"]["score"] == payload["scorecard"]["final_score"]


def test_ai_disabled_returns_ai_disabled_error(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        return _DummyIntegration()

    monkeypatch.setenv("AI_ENABLED", "0")
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

    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Disabled Candidate",
                phone=None,
                city="E2E City",
                telegram_id=999001,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(app) as client:
        resp = client.get(
            f"/api/ai/candidates/{candidate_id}/summary",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )
    assert resp.status_code == 501
    payload = resp.json()
    assert payload["ok"] is False
    assert payload["error"] == "ai_disabled"


def test_ai_city_recommendations_cache_reuse(ai_app):
    async def _seed() -> int:
        async with async_session() as session:
            city = City(name="Reco City", tz="Europe/Moscow", active=True, criteria="Опыт продаж, грамотная речь")
            session.add(city)
            await session.commit()
            await session.refresh(city)

            # Candidates for the same city (PII not used in AI context)
            u1 = User(fio="Cand One", city=city.name, telegram_id=111001, source="bot")
            u2 = User(fio="Cand Two", city=city.name, telegram_id=111002, source="bot")
            session.add_all([u1, u2])
            await session.commit()
            await session.refresh(u1)
            await session.refresh(u2)

            return int(city.id)

    city_id = _run(_seed())

    with TestClient(ai_app) as client:
        r1 = client.get(
            f"/api/ai/cities/{city_id}/candidates/recommendations?limit=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )
        assert r1.status_code == 200
        p1 = r1.json()
        assert p1["ok"] is True
        assert p1["cached"] is False
        assert "recommended" in p1

        r2 = client.get(
            f"/api/ai/cities/{city_id}/candidates/recommendations?limit=10",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )
        assert r2.status_code == 200
        p2 = r2.json()
        assert p2["ok"] is True
        assert p2["cached"] is True
        assert p2["input_hash"] == p1["input_hash"]


def test_ai_candidate_coach_cache_reuse(ai_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Coach Candidate",
                phone=None,
                city="E2E City",
                telegram_id=911001,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_app) as client:
        r1 = client.get(
            f"/api/ai/candidates/{candidate_id}/coach",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )
        assert r1.status_code == 200
        p1 = r1.json()
        assert p1["ok"] is True
        assert p1["cached"] is False
        assert "coach" in p1
        assert "relevance_score" in p1["coach"]

        r2 = client.get(
            f"/api/ai/candidates/{candidate_id}/coach",
            auth=("admin", "admin"),
            headers={"Accept": "application/json"},
        )
        assert r2.status_code == 200
        p2 = r2.json()
        assert p2["ok"] is True
        assert p2["cached"] is True
        assert p2["input_hash"] == p1["input_hash"]


def test_ai_candidate_coach_drafts_modes_and_invalid(ai_app):
    async def _seed() -> int:
        async with async_session() as session:
            user = User(
                fio="Coach Draft Candidate",
                phone=None,
                city="E2E City",
                telegram_id=911002,
                source="bot",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return int(user.id)

    candidate_id = _run(_seed())

    with TestClient(ai_app) as client:
        for mode in ("short", "neutral", "supportive"):
            headers = {"x-csrf-token": _csrf(client)}
            resp = client.post(
                f"/api/ai/candidates/{candidate_id}/coach/drafts",
                auth=("admin", "admin"),
                headers=headers,
                json={"mode": mode},
            )
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["ok"] is True
            assert payload["drafts"]

        bad = client.post(
            f"/api/ai/candidates/{candidate_id}/coach/drafts",
            auth=("admin", "admin"),
            headers={"x-csrf-token": _csrf(client)},
            json={"mode": "invalid"},
        )
        assert bad.status_code == 400
