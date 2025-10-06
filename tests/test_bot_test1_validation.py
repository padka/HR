from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from backend.apps.bot.city_registry import CityInfo
from backend.apps.bot.config import (
    DEFAULT_TZ,
    FOLLOWUP_STUDY_FLEX,
    FOLLOWUP_STUDY_MODE,
    FOLLOWUP_STUDY_SCHEDULE,
    State,
)
from backend.apps.bot.metrics import get_test1_metrics_snapshot, reset_test1_metrics
from backend.apps.bot.services import (
    begin_interview,
    configure,
    save_test1_answer,
    _handle_test1_rejection,
)
from backend.apps.bot.state_store import InMemoryStateStore, StateManager

USER_ID = 555


@pytest_asyncio.fixture
async def bot_context():
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)
    dummy_bot = SimpleNamespace(
        send_message=AsyncMock(),
        edit_message_text=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )
    configure(dummy_bot, manager)
    await reset_test1_metrics()
    yield manager, dummy_bot
    await manager.clear()
    await manager.close()


@pytest.mark.asyncio
async def test_save_test1_answer_rejects_non_cyrillic_fio(bot_context, monkeypatch):
    manager, _ = bot_context
    await begin_interview(USER_ID)
    state = await manager.get(USER_ID)
    question = state["t1_sequence"][state.get("t1_idx", 0)]

    result = await save_test1_answer(USER_ID, question, "John Doe")

    assert result.status == "invalid"
    assert "кирил" in (result.message or "").lower()


@pytest.mark.asyncio
async def test_city_validation_returns_hints(bot_context, monkeypatch):
    manager, _ = bot_context

    async def fake_list():
        return [CityInfo(id=1, name="Москва", tz="Europe/Moscow")]

    async def fake_find_by_name(name: str):
        return None

    async def fake_find_by_id(city_id: int):
        return None

    monkeypatch.setattr("backend.apps.bot.services.list_candidate_cities", fake_list)
    monkeypatch.setattr("backend.apps.bot.services.find_candidate_city_by_name", fake_find_by_name)
    monkeypatch.setattr("backend.apps.bot.services.find_candidate_city_by_id", fake_find_by_id)

    await begin_interview(USER_ID)

    async def move_to(idx: int):
        def _move(state: State):
            state["t1_idx"] = idx
            state["t1_current_idx"] = idx
            return state, None

        await manager.atomic_update(USER_ID, _move)

    await move_to(1)
    state = await manager.get(USER_ID)
    question = state["t1_sequence"][1]

    result = await save_test1_answer(USER_ID, question, "Лондон")

    assert result.status == "invalid"
    assert "Москва" in result.hints


@pytest.mark.asyncio
async def test_format_not_ready_triggers_rejection(bot_context, monkeypatch):
    manager, dummy_bot = bot_context

    async def fake_tpl(*_args, **_kwargs):
        return "Мы вернёмся, когда формат будет удобен."

    monkeypatch.setattr("backend.apps.bot.services.templates.tpl", fake_tpl)
    monkeypatch.setattr("backend.apps.bot.services.get_bot", lambda: dummy_bot)

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            t1_idx=0,
            t1_current_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=False,
            t1_sequence=[{"id": "format"}],
            fio="Иванов Иван",
            city_name="Москва",
            city_id=1,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={"fio": "Иванов Иван", "city_id": 1, "city_name": "Москва"},
        ),
    )

    result = await save_test1_answer(USER_ID, {"id": "format"}, "Пока не готов")
    assert result.status == "reject"
    assert result.reason == "format_not_ready"

    await _handle_test1_rejection(USER_ID, result)

    snapshot = await get_test1_metrics_snapshot()
    assert snapshot.rejections_total == 1
    assert dummy_bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_study_schedule_branch_and_reject(bot_context, monkeypatch):
    manager, _ = bot_context

    async def move_to(idx: int):
        def _move(state: State):
            state["t1_idx"] = idx
            state["t1_current_idx"] = idx
            return state, None

        await manager.atomic_update(USER_ID, _move)

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            t1_idx=0,
            t1_current_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=False,
            t1_sequence=[FOLLOWUP_STUDY_MODE.copy(), FOLLOWUP_STUDY_SCHEDULE.copy()],
            fio="Иванов Иван",
            city_name="Москва",
            city_id=1,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={"city_id": 1, "city_name": "Москва"},
        ),
    )

    state = await manager.get(USER_ID)
    mode_question = state["t1_sequence"][0]

    result_mode = await save_test1_answer(USER_ID, mode_question, "Очно")
    assert result_mode.status == "ok"

    await move_to(1)
    state = await manager.get(USER_ID)
    schedule_question = state["t1_sequence"][1]

    result_schedule = await save_test1_answer(
        USER_ID,
        schedule_question,
        "Смогу, но нужен запас по времени",
    )
    assert result_schedule.status == "ok"

    state_after = await manager.get(USER_ID)
    ids = [item.get("id") for item in state_after["t1_sequence"]]
    assert FOLLOWUP_STUDY_FLEX["id"] in ids

    flex_index = ids.index(FOLLOWUP_STUDY_FLEX["id"])
    await move_to(flex_index)
    flex_question = state_after["t1_sequence"][flex_index]

    result_flex = await save_test1_answer(USER_ID, flex_question, "Нет, не смогу")
    assert result_flex.status == "reject"
    assert result_flex.reason == "study_flex_declined"


@pytest.mark.asyncio
async def test_study_schedule_hard_response_rejects(bot_context):
    manager, _ = bot_context

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            t1_idx=0,
            t1_current_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=False,
            t1_sequence=[FOLLOWUP_STUDY_MODE.copy(), FOLLOWUP_STUDY_SCHEDULE.copy()],
            fio="Иванов Иван",
            city_name="Москва",
            city_id=1,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={"city_id": 1, "city_name": "Москва"},
        ),
    )

    state = await manager.get(USER_ID)
    schedule_question = state["t1_sequence"][1]

    result_schedule = await save_test1_answer(USER_ID, schedule_question, "Будет сложно")

    assert result_schedule.status == "reject"
    assert result_schedule.reason == "schedule_conflict"


@pytest.mark.asyncio
async def test_format_flexible_request_triggers_clarification(bot_context):
    manager, _ = bot_context

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            t1_idx=0,
            t1_current_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=False,
            t1_sequence=[{"id": "format"}],
            fio="Иванов Иван",
            city_name="Москва",
            city_id=1,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={"fio": "Иванов Иван", "city_id": 1, "city_name": "Москва"},
        ),
    )

    result = await save_test1_answer(USER_ID, {"id": "format"}, "Нужен гибкий график")

    assert result.status == "ok"
    assert result.template_key == "t1_format_clarify"
