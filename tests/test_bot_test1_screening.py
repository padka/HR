from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from backend.apps.bot.config import TEST1_QUESTIONS
from backend.apps.bot.defaults import DEFAULT_TEMPLATES
from backend.apps.bot.services import (
    StateManager,
    configure_template_provider,
    finalize_test1,
)
from backend.apps.bot.services import (
    configure as configure_bot_services,
)
from backend.apps.bot.state_store import InMemoryStateStore
from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import (
    CandidateJourneySession,
    CandidateJourneyStepState,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.test1_shared import (
    NEXT_ACTION_ASK_CANDIDATE,
    NEXT_ACTION_SELECT_INTERVIEW_SLOT,
    TEST1_COMPLETED_STEP_KEY,
    TEST1_STEP_KEY,
    build_test1_sequence,
    complete_test1_for_candidate,
    serialize_step_payload,
    to_public_required_next_action,
)
from backend.domain.candidates.test1_shared import (
    Test1DraftState as SharedDraftState,
)
from backend.domain.models import ApplicationEvent
from sqlalchemy import select


class DummyBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.documents: list[tuple[int, object, str | None]] = []

    async def send_message(self, chat_id, text, **_kwargs):
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id, document, caption=None, **_kwargs):
        self.documents.append((chat_id, document, caption))


@pytest.fixture(autouse=True)
def _setup_templates_and_settings_cache():
    configure_template_provider()
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


async def _seed_city_recruiter_and_slots(
    *,
    city_name: str,
    recruiter_name: str,
    slots: int,
) -> models.City:
    async with async_session() as session:
        recruiter = models.Recruiter(
            name=recruiter_name,
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=99901,
        )
        city = models.City(name=city_name, tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        for index in range(slots):
            session.add(
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=datetime.now(UTC) + timedelta(hours=index + 2),
                    status=models.SlotStatus.FREE,
                    duration_min=30,
                    purpose="interview",
                )
            )
        await session.commit()
        return city


async def _fake_tpl(_city_id, key, **_fmt):
    return DEFAULT_TEMPLATES.get(key, "")


async def _load_candidate(telegram_id: int) -> User | None:
    async with async_session() as session:
        return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def _load_event_types(candidate_id: int) -> set[str]:
    async with async_session() as session:
        rows = (
            await session.execute(
                select(ApplicationEvent.event_type).where(ApplicationEvent.candidate_id == candidate_id)
            )
        ).scalars().all()
    return {str(item) for item in rows}


async def _load_application_events(candidate_id: int) -> list[ApplicationEvent]:
    async with async_session() as session:
        rows = (
            await session.execute(
                select(ApplicationEvent)
                .where(ApplicationEvent.candidate_id == candidate_id)
                .order_by(ApplicationEvent.occurred_at.asc(), ApplicationEvent.id.asc())
            )
        ).scalars().all()
    return list(rows)


def _complete_test1_answers() -> dict[str, str]:
    return {
        str(question["id"]): f"Answer {index}"
        for index, question in enumerate(TEST1_QUESTIONS, start=1)
    }


def _shared_draft_state(bot_state: dict[str, Any]) -> SharedDraftState:
    answers = {
        str(key): str(value)
        for key, value in dict(bot_state.get("test1_answers") or {}).items()
    }
    payload = {
        key: value
        for key in (
            "fio",
            "age",
            "status",
            "format_choice",
            "study_mode",
            "study_schedule",
            "study_flex",
            "city_id",
            "city_name",
            "candidate_tz",
        )
        if (value := bot_state.get(key)) is not None
    }
    question_ids = [str(question["id"]) for question in build_test1_sequence(answers)]
    return SharedDraftState(
        answers=answers,
        payload=payload,
        question_ids=question_ids,
        city_id=bot_state.get("city_id"),
        city_name=bot_state.get("city_name"),
        candidate_tz=str(bot_state.get("candidate_tz") or "Europe/Moscow"),
    )


async def _run_shared_completion(
    *,
    bot_state: dict[str, Any],
) -> tuple[Any, int]:
    async with async_session() as session:
        candidate = User(
            fio=str(bot_state.get("fio") or "Shared Candidate"),
            city=str(bot_state.get("city_name") or "") or None,
            source="bot",
        )
        journey_session = CandidateJourneySession(
            candidate_id=0,
            entry_channel="telegram",
            current_step_key=TEST1_STEP_KEY,
            last_surface="telegram_bot",
        )
        session.add(candidate)
        await session.flush()
        journey_session.candidate_id = int(candidate.id)
        session.add(journey_session)
        await session.flush()

        step_state = CandidateJourneyStepState(
            session_id=int(journey_session.id),
            step_key=TEST1_STEP_KEY,
            payload_json=serialize_step_payload(
                draft_state=_shared_draft_state(bot_state),
                source="bot",
                surface="telegram_bot",
            ),
        )
        session.add(step_state)
        await session.flush()

        completion = await complete_test1_for_candidate(
            session=session,
            candidate=candidate,
            journey_session=journey_session,
            step_state=step_state,
            source="bot",
            channel="telegram",
            surface="telegram_bot",
            actor_type="system",
            actor_id="test_bot_test1_screening",
        )
        candidate_id = int(candidate.id)
        await session.commit()
    return completion, candidate_id


def _event_contract(events: list[ApplicationEvent]) -> list[dict[str, Any]]:
    relevant_event_types = {
        "assessment.completed",
        "screening.decision_made",
        "application.status_changed",
    }
    contract: list[dict[str, Any]] = []
    for event in events:
        if event.event_type not in relevant_event_types:
            continue
        metadata = dict(event.metadata_json or {})
        contract.append(
            {
                "event_type": event.event_type,
                "status_from": event.status_from,
                "status_to": event.status_to,
                "reason_code": metadata.get("reason_code"),
                "required_next_action": to_public_required_next_action(
                    metadata.get("required_next_action")
                )
                if metadata.get("required_next_action")
                else None,
                "decision_outcome": metadata.get("decision_outcome"),
                "strictness": metadata.get("strictness"),
            }
        )
    return sorted(
        contract,
        key=lambda item: (
            str(item["event_type"]),
            str(item["status_to"] or ""),
            str(item["reason_code"] or ""),
        ),
    )


@pytest.mark.asyncio
async def test_finalize_test1_keeps_legacy_flow_when_screening_flags_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST1_SCREENING_DECISION_ENABLED", raising=False)
    monkeypatch.delenv("AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED", raising=False)
    city = await _seed_city_recruiter_and_slots(
        city_name="Тула",
        recruiter_name="Legacy Recruiter",
        slots=1,
    )

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    user_id = 66001
    await state_manager.set(
        user_id,
        {
            "fio": "Legacy Candidate",
            "city_name": city.name,
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
            "test1_answers": {TEST1_QUESTIONS[0]["id"]: "Answer"},
            "t1_sequence": list(TEST1_QUESTIONS),
        },
    )

    bot = DummyBot()
    configure_bot_services(bot, state_manager)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow._render_tpl", _fake_tpl)
    monkeypatch.setattr(
        "backend.domain.candidates.test1_shared.evaluate_test1_screening_decision",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("screening decision should stay disabled")),
    )
    show_menu = AsyncMock(return_value=True)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow.show_recruiter_menu", show_menu)

    await finalize_test1(user_id)

    candidate = await _load_candidate(user_id)
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.WAITING_SLOT
    show_menu.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_test1_manual_review_keeps_candidate_in_test1_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST1_SCREENING_DECISION_ENABLED", "1")
    monkeypatch.delenv("AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED", raising=False)
    city = await _seed_city_recruiter_and_slots(
        city_name="Самара",
        recruiter_name="Review Recruiter",
        slots=1,
    )

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    user_id = 66002
    bot_state = {
        "fio": "Clarify Candidate",
        "city_name": city.name,
        "city_id": city.id,
        "candidate_tz": "Europe/Moscow",
        "format_choice": "Нужен гибкий график",
        "test1_answers": {TEST1_QUESTIONS[0]["id"]: "Answer"},
        "t1_sequence": list(TEST1_QUESTIONS),
    }
    await state_manager.set(user_id, bot_state)

    bot = DummyBot()
    configure_bot_services(bot, state_manager)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow._render_tpl", _fake_tpl)
    show_menu = AsyncMock(return_value=True)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow.show_recruiter_menu", show_menu)

    shared_completion, _ = await _run_shared_completion(bot_state=bot_state)

    await finalize_test1(user_id)

    candidate = await _load_candidate(user_id)
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.TEST1_COMPLETED
    assert shared_completion.required_next_action == NEXT_ACTION_ASK_CANDIDATE
    assert shared_completion.screening_decision is not None
    assert shared_completion.screening_decision["outcome"] == "ask_clarification"
    assert show_menu.await_count == 0
    combined = "\n".join(text for _, text in bot.messages)
    assert "уточнить" in combined.lower()


@pytest.mark.asyncio
async def test_finalize_test1_auto_offer_renders_slot_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST1_SCREENING_DECISION_ENABLED", "1")
    monkeypatch.setenv("AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED", "1")
    city = await _seed_city_recruiter_and_slots(
        city_name="Ижевск-2",
        recruiter_name="Offer Recruiter",
        slots=2,
    )

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    user_id = 66003
    bot_state = {
        "fio": "Offer Candidate",
        "city_name": city.name,
        "city_id": city.id,
        "candidate_tz": "Europe/Moscow",
        "test1_answers": _complete_test1_answers(),
        "t1_sequence": list(TEST1_QUESTIONS),
    }
    await state_manager.set(user_id, bot_state)

    bot = DummyBot()
    configure_bot_services(bot, state_manager)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow._render_tpl", _fake_tpl)
    show_menu = AsyncMock(return_value=True)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow.show_recruiter_menu", show_menu)

    shared_completion, _ = await _run_shared_completion(bot_state=bot_state)

    await finalize_test1(user_id)

    candidate = await _load_candidate(user_id)
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.WAITING_SLOT
    assert shared_completion.required_next_action == NEXT_ACTION_SELECT_INTERVIEW_SLOT
    assert shared_completion.interview_offer is not None
    assert shared_completion.current_step_key == "booking"
    assert show_menu.await_count == 1
    combined = "\n".join(text for _, text in bot.messages)
    assert "подобрали" in combined.lower()


@pytest.mark.asyncio
async def test_finalize_test1_auto_offer_without_slots_falls_back_to_manual_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST1_SCREENING_DECISION_ENABLED", "1")
    monkeypatch.setenv("AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED", "1")
    city = await _seed_city_recruiter_and_slots(
        city_name="Томск-2",
        recruiter_name="Fallback Recruiter",
        slots=0,
    )

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    user_id = 66005
    bot_state = {
        "fio": "Fallback Candidate",
        "city_name": city.name,
        "city_id": city.id,
        "candidate_tz": "Europe/Moscow",
        "test1_answers": _complete_test1_answers(),
        "t1_sequence": list(TEST1_QUESTIONS),
    }
    await state_manager.set(user_id, bot_state)

    bot = DummyBot()
    configure_bot_services(bot, state_manager)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow._render_tpl", _fake_tpl)
    manual_prompt = AsyncMock(return_value=True)
    show_menu = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "backend.apps.bot.services.test1_flow.send_manual_scheduling_prompt",
        manual_prompt,
    )
    monkeypatch.setattr("backend.apps.bot.services.test1_flow.show_recruiter_menu", show_menu)

    shared_completion, _ = await _run_shared_completion(bot_state=bot_state)

    await finalize_test1(user_id)

    candidate = await _load_candidate(user_id)
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.WAITING_SLOT
    assert shared_completion.required_next_action == NEXT_ACTION_SELECT_INTERVIEW_SLOT
    assert shared_completion.interview_offer is not None
    assert shared_completion.current_step_key == "booking"
    manual_prompt.assert_awaited_once()
    assert show_menu.await_count == 0


@pytest.mark.asyncio
async def test_finalize_test1_dual_write_emits_application_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST1_SCREENING_DECISION_ENABLED", "1")
    monkeypatch.delenv("AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED", raising=False)
    monkeypatch.setenv("CANDIDATE_STATUS_DUAL_WRITE_ENABLED", "1")
    city = await _seed_city_recruiter_and_slots(
        city_name="Пермь-2",
        recruiter_name="Dual Write Recruiter",
        slots=0,
    )

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    user_id = 66004
    bot_state = {
        "fio": "Dual Write Candidate",
        "city_name": city.name,
        "city_id": city.id,
        "candidate_tz": "Europe/Moscow",
        "test1_answers": _complete_test1_answers(),
        "t1_sequence": list(TEST1_QUESTIONS),
    }
    await state_manager.set(user_id, bot_state)

    bot = DummyBot()
    configure_bot_services(bot, state_manager)
    monkeypatch.setattr("backend.apps.bot.services.test1_flow._render_tpl", _fake_tpl)
    monkeypatch.setattr(
        "backend.apps.bot.services.test1_flow.send_manual_scheduling_prompt",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "backend.apps.bot.services.test1_flow.show_recruiter_menu",
        AsyncMock(return_value=True),
    )

    shared_completion, shared_candidate_id = await _run_shared_completion(bot_state=bot_state)

    await finalize_test1(user_id)

    candidate = await _load_candidate(user_id)
    assert candidate is not None
    event_types = await _load_event_types(candidate.id)
    bot_events = await _load_application_events(candidate.id)
    shared_events = await _load_application_events(shared_candidate_id)
    assert shared_completion.required_next_action == NEXT_ACTION_SELECT_INTERVIEW_SLOT
    assert shared_completion.current_step_key == TEST1_COMPLETED_STEP_KEY
    assert "assessment.completed" in event_types
    assert "screening.decision_made" in event_types
    assert "application.status_changed" in event_types
    assert _event_contract(bot_events) == _event_contract(shared_events)
    screening_events = [event for event in bot_events if event.event_type == "screening.decision_made"]
    assert len(screening_events) == 1
    assert screening_events[0].metadata_json["reason_code"] == "assessment_complete_ready_for_interview"
    assert to_public_required_next_action(
        screening_events[0].metadata_json["required_next_action"]
    ) == NEXT_ACTION_SELECT_INTERVIEW_SLOT
