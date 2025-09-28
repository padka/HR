import importlib
import json
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture()
def bot_module(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:TEST")
    import backend.core.settings as settings_module
    settings_module.get_settings.cache_clear()
    if "bot" in sys.modules:
        bot_mod = importlib.reload(sys.modules["bot"])
    else:
        bot_mod = importlib.import_module("bot")
    return bot_mod


@pytest.mark.asyncio
async def test_finalize_and_pick_slot_without_files(monkeypatch, bot_module):
    bot = bot_module
    user_id = 12345

    fake_user = SimpleNamespace(id=42, telegram_id=user_id, fio="Имя", city="Москва")
    monkeypatch.setattr(bot.candidate_services, "create_or_update_user", AsyncMock(return_value=fake_user))
    save_mock = AsyncMock()
    monkeypatch.setattr(bot.candidate_services, "save_survey_response", save_mock)
    load_mock = AsyncMock()
    monkeypatch.setattr(bot.candidate_services, "load_survey_summary", load_mock)
    monkeypatch.setattr(bot.candidate_services, "get_user_by_telegram_id", AsyncMock(return_value=fake_user))

    tpl_mock = AsyncMock(return_value="text")
    monkeypatch.setattr(bot, "tpl", tpl_mock)
    monkeypatch.setattr(bot, "_show_recruiter_menu", AsyncMock())
    monkeypatch.setattr(bot.bot, "send_message", AsyncMock())
    send_document_mock = AsyncMock()
    monkeypatch.setattr(bot.bot, "send_document", send_document_mock)

    monkeypatch.setattr("builtins.open", MagicMock(side_effect=AssertionError("file operations are not expected")))

    bot.user_data[user_id] = {
        "t1_sequence": [
            {"id": "fio", "prompt": "ФИО"},
            {"id": "city", "prompt": "Город"},
        ],
        "test1_answers": {"fio": "Имя", "city": "Москва"},
        "fio": "Имя",
        "city_name": "Москва",
        "city_id": 1,
        "candidate_tz": "Europe/Moscow",
    }

    await bot.finalize_test1(user_id)

    assert save_mock.await_count == 1
    save_args = save_mock.await_args
    assert save_args.args[0] == fake_user.id
    payload = save_args.args[1]
    assert payload["meta"]["fio"] == "Имя"
    assert bot.user_data[user_id]["candidate_db_id"] == fake_user.id

    survey_payload = {
        "meta": payload["meta"],
        "questions": payload["questions"],
        "summary_text": payload["summary_text"],
    }
    fake_response = SimpleNamespace(
        answers_json=json.dumps(survey_payload, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
    )
    load_mock.return_value = fake_response

    slot_obj = SimpleNamespace(
        id=7,
        recruiter_id=9,
        candidate_fio="Имя",
        start_utc=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(bot, "reserve_slot", AsyncMock(return_value=slot_obj))
    recruiter = SimpleNamespace(tz="Europe/Moscow", tg_chat_id=555)
    monkeypatch.setattr(bot, "get_recruiter", AsyncMock(return_value=recruiter))
    monkeypatch.setattr(bot, "kb_approve", lambda slot_id: "kb")

    message = SimpleNamespace(
        edit_text=AsyncMock(),
        edit_reply_markup=AsyncMock(),
    )
    callback = SimpleNamespace(
        data="pick_slot:9:7",
        from_user=SimpleNamespace(id=user_id),
        message=message,
        answer=AsyncMock(),
    )

    await bot.pick_slot(callback)

    assert load_mock.await_count == 1
    assert send_document_mock.await_count == 1
    doc_call = send_document_mock.await_args
    document = doc_call.kwargs["document"]
    from aiogram.types import BufferedInputFile  # imported lazily for test clarity

    assert isinstance(document, BufferedInputFile)
    assert document.filename.endswith(".txt")
    assert callback.answer.await_count >= 1

    bot.user_data.pop(user_id, None)
