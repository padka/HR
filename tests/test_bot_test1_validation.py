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
    get_questions_bank_version,
)
from backend.apps.bot.metrics import get_test1_metrics_snapshot, reset_test1_metrics
from backend.apps.bot.services import (
    Test1AnswerResult as BotTest1AnswerResult,
    begin_interview,
    configure,
    handle_test1_answer,
    save_test1_answer,
    send_test1_question,
    _handle_test1_rejection,
    _resolve_test1_options,
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
        return [
            CityInfo(
                id=1,
                name_plain="Москва",
                display_name="Москва",
                tz="Europe/Moscow",
            )
        ]

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

    monkeypatch.setattr("backend.apps.bot.services._render_tpl", fake_tpl)
    monkeypatch.setattr("backend.apps.bot.services.get_bot", lambda: dummy_bot)

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            questions_bank_version=1,
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
            questions_bank_version=get_questions_bank_version(),
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
            questions_bank_version=get_questions_bank_version(),
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


@pytest.mark.asyncio
async def test_resolve_test1_options_uses_display_name(monkeypatch):
    cities = [
        CityInfo(
            id=10,
            name_plain="Новосибирск",
            display_name="Новосибирск",
            tz="Asia/Novosibirsk",
        )
    ]

    async def fake_list():
        return cities

    monkeypatch.setattr("backend.apps.bot.services.list_candidate_cities", fake_list)

    result = await _resolve_test1_options({"id": "city"})
    assert result is not None
    assert result[0]["label"] == "Новосибирск"
    assert result[0]["value"] == "Новосибирск"
    assert result[0]["city_id"] == 10
    assert result[0]["tz"] == "Asia/Novosibirsk"


@pytest.mark.asyncio
async def test_send_test1_question_uses_display_name_in_buttons(bot_context, monkeypatch):
    manager, dummy_bot = bot_context

    dummy_bot.send_message.reset_mock()

    city = CityInfo(
        id=5,
        name_plain="Санкт-Петербург",
        display_name="Санкт-Петербург",
        tz="Europe/Moscow",
    )

    async def fake_list():
        return [city]

    async def fake_tpl(*_args, **_kwargs):
        return "1/5"

    monkeypatch.setattr("backend.apps.bot.services.list_candidate_cities", fake_list)
    monkeypatch.setattr("backend.apps.bot.services._render_tpl", fake_tpl)

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            questions_bank_version=get_questions_bank_version(),
            t1_idx=0,
            t1_current_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=True,
            t1_sequence=[{"id": "city", "prompt": "Ваш город?"}],
            fio="",
            city_name="",
            city_id=None,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={},
        ),
    )

    await send_test1_question(USER_ID)

    assert dummy_bot.send_message.await_count == 1
    _, kwargs = dummy_bot.send_message.await_args_list[0]
    markup = kwargs.get("reply_markup")
    assert markup is not None
    button = markup.inline_keyboard[0][0]
    assert button.text == "Санкт-Петербург"

    state = await manager.get(USER_ID)
    stored_question = state["t1_sequence"][0]
    options = stored_question.get("options")
    assert options is not None
    assert options[0]["label"] == "Санкт-Петербург"
    assert options[0]["value"] == "Санкт-Петербург"


@pytest.mark.asyncio
async def test_send_test1_question_resyncs_sequence_on_bank_version_change(bot_context, monkeypatch):
    manager, dummy_bot = bot_context

    dummy_bot.send_message.reset_mock()

    async def fake_tpl(*_args, **_kwargs):
        return ""

    monkeypatch.setattr("backend.apps.bot.services._render_tpl", fake_tpl)
    monkeypatch.setattr("backend.apps.bot.services.get_questions_bank_version", lambda: 2)
    monkeypatch.setattr(
        "backend.apps.bot.services.TEST1_QUESTIONS",
        [{"id": "fio", "prompt": "NEW PROMPT", "placeholder": "x"}],
    )

    await manager.set(
        USER_ID,
        State(
            flow="interview",
            questions_bank_version=get_questions_bank_version(),
            t1_idx=0,
            t1_current_idx=0,
            test1_answers={},
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=True,
            t1_sequence=[{"id": "fio", "prompt": "OLD PROMPT", "placeholder": "x"}],
            fio="",
            city_name="",
            city_id=None,
            candidate_tz=DEFAULT_TZ,
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
            test1_payload={},
        ),
    )

    await send_test1_question(USER_ID)

    assert dummy_bot.send_message.await_count == 1
    args, _kwargs = dummy_bot.send_message.await_args_list[0]
    assert "NEW PROMPT" in args[1]

    state = await manager.get(USER_ID)
    assert state.get("questions_bank_version") == 2
    assert state["t1_sequence"][0]["prompt"] == "NEW PROMPT"


@pytest.mark.asyncio
async def test_handle_test1_answer_advances_on_success(bot_context, monkeypatch):
    manager, dummy_bot = bot_context

    state = State(
        flow="interview",
        t1_idx=0,
        t1_current_idx=0,
        test1_answers={},
        t1_last_prompt_id=99,
        t1_last_question_text="Вопрос",
        t1_requires_free_text=True,
        t1_sequence=[{"id": "fio", "prompt": "Ваше ФИО?"}, {"id": "city", "prompt": "Город"}],
        fio="",
        city_name="",
        city_id=None,
        candidate_tz=DEFAULT_TZ,
        t2_attempts={},
        picked_recruiter_id=None,
        picked_slot_id=None,
        test1_payload={},
    )
    await manager.set(USER_ID, state)

    async def fake_save(_user_id, _question, _answer):
        return BotTest1AnswerResult(status="ok")

    send_mock = AsyncMock()
    finalize_mock = AsyncMock()

    monkeypatch.setattr("backend.apps.bot.services.save_test1_answer", fake_save)
    monkeypatch.setattr("backend.apps.bot.services.send_test1_question", send_mock)
    monkeypatch.setattr("backend.apps.bot.services.finalize_test1", finalize_mock)
    monkeypatch.setattr(
        "backend.apps.bot.services._resolve_followup_message",
        AsyncMock(return_value=None),
    )

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=USER_ID),
        text="Иванов Иван",
        reply_to_message=SimpleNamespace(message_id=99),
    )
    message.reply = AsyncMock()
    message.answer = AsyncMock()

    dummy_bot.edit_message_text.reset_mock()

    await handle_test1_answer(message)

    assert message.reply.await_count == 0
    assert message.answer.await_count == 0
    assert send_mock.await_count == 1
    assert finalize_mock.await_count == 0

    updated = await manager.get(USER_ID)
    assert updated["t1_idx"] == 1
    assert dummy_bot.edit_message_text.await_count == 1


@pytest.mark.asyncio
async def test_handle_test1_answer_accepts_text_without_reply(bot_context, monkeypatch):
    manager, _ = bot_context

    state = State(
        flow="interview",
        t1_idx=0,
        t1_current_idx=0,
        test1_answers={},
        t1_last_prompt_id=123,
        t1_last_question_text="Вопрос",
        t1_requires_free_text=True,
        t1_sequence=[{"id": "fio", "prompt": "Ваше ФИО?"}, {"id": "city", "prompt": "Город?"}],
        fio="",
        city_name="",
        city_id=None,
        candidate_tz=DEFAULT_TZ,
        t2_attempts={},
        picked_recruiter_id=None,
        picked_slot_id=None,
        test1_payload={},
        t1_last_hint_sent=False,
    )
    await manager.set(USER_ID, state)

    async def fake_save(*_args, **_kwargs):
        return BotTest1AnswerResult(status="ok")

    send_mock = AsyncMock()
    monkeypatch.setattr("backend.apps.bot.services.save_test1_answer", fake_save)
    monkeypatch.setattr("backend.apps.bot.services.send_test1_question", send_mock)
    monkeypatch.setattr(
        "backend.apps.bot.services._resolve_followup_message",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "backend.apps.bot.services.candidate_services.is_chat_mode_active",
        AsyncMock(return_value=False),
    )

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=USER_ID),
        text="Просто текст",
        caption=None,
        reply_to_message=None,
    )
    message.reply = AsyncMock()
    message.answer = AsyncMock()

    await handle_test1_answer(message)

    assert message.reply.await_count == 0
    assert send_mock.await_count == 1


@pytest.mark.asyncio
async def test_handle_test1_answer_hint_sent_once(bot_context, monkeypatch):
    manager, _ = bot_context

    state = State(
        flow="interview",
        t1_idx=0,
        t1_current_idx=0,
        test1_answers={},
        t1_last_prompt_id=321,
        t1_last_question_text="Вопрос",
        t1_requires_free_text=True,
        t1_sequence=[{"id": "fio", "prompt": "Ваше ФИО?"}],
        fio="",
        city_name="",
        city_id=None,
        candidate_tz=DEFAULT_TZ,
        t2_attempts={},
        picked_recruiter_id=None,
        picked_slot_id=None,
        test1_payload={},
        t1_last_hint_sent=False,
    )
    await manager.set(USER_ID, state)

    monkeypatch.setattr(
        "backend.apps.bot.services.candidate_services.is_chat_mode_active",
        AsyncMock(return_value=False),
    )

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=USER_ID),
        text="",
        caption="",
        reply_to_message=None,
    )
    message.reply = AsyncMock()
    message.answer = AsyncMock()

    await handle_test1_answer(message)
    await handle_test1_answer(message)

    assert message.reply.await_count == 1
    assert message.answer.await_count == 0


@pytest.mark.asyncio
async def test_handle_test1_answer_ignored_in_chat_mode(bot_context, monkeypatch):
    manager, _ = bot_context

    state = State(
        flow="interview",
        t1_idx=0,
        t1_current_idx=0,
        test1_answers={},
        t1_last_prompt_id=11,
        t1_last_question_text="",
        t1_requires_free_text=True,
        t1_sequence=[{"id": "fio", "prompt": "Ваше ФИО?"}],
        fio="",
        city_name="",
        city_id=None,
        candidate_tz=DEFAULT_TZ,
        t2_attempts={},
        picked_recruiter_id=None,
        picked_slot_id=None,
        test1_payload={},
    )
    await manager.set(USER_ID, state)

    async def fake_save(*_args, **_kwargs):  # pragma: no cover - should not run
        raise AssertionError("save_test1_answer should not be called")

    monkeypatch.setattr("backend.apps.bot.services.save_test1_answer", fake_save)
    monkeypatch.setattr(
        "backend.apps.bot.services.candidate_services.is_chat_mode_active",
        AsyncMock(return_value=True),
    )

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=USER_ID),
        text="Ответ",
        caption=None,
        reply_to_message=None,
    )
    message.reply = AsyncMock()
    message.answer = AsyncMock()

    await handle_test1_answer(message)

    assert message.reply.await_count == 0
    assert message.answer.await_count == 0
