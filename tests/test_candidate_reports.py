import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.apps.bot import services
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.domain.candidates import services as candidate_services


@pytest.mark.asyncio
async def test_finalize_test1_generates_report(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)

    async def dummy_send(*_args, **_kwargs):
        return None

    dummy_bot = SimpleNamespace(
        send_message=dummy_send,
        send_document=dummy_send,
    )
    services.configure(dummy_bot, manager)

    user_id = 555555
    state = {
        "flow": "interview",
        "fio": "Тест Пользователь",
        "city_name": "Москва",
        "test1_answers": {q["id"]: "Ответ" for q in services.TEST1_QUESTIONS},
        "test1_duration": 180,
        "t1_sequence": list(services.TEST1_QUESTIONS),
    }
    await manager.set(user_id, state)

    try:
        await services.finalize_test1(user_id)

        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        assert candidate is not None
        assert candidate.test1_report_url
        report_path = Path(services.REPORTS_DIR) / str(candidate.id) / "test1.txt"
        assert report_path.exists()
    finally:
        await manager.clear()
        await manager.close()


@pytest.mark.asyncio
async def test_finalize_test2_generates_report(monkeypatch):
    store = InMemoryStateStore(ttl_seconds=60)
    manager = StateManager(store)

    async def dummy_send(*_args, **_kwargs):
        return None

    dummy_bot = SimpleNamespace(send_message=dummy_send)
    services.configure(dummy_bot, manager)

    user_id = 666666
    attempts = {}
    for idx, question in enumerate(services.TEST2_QUESTIONS):
        correct = question.get("correct", 0)
        attempts[idx] = {
            "answers": [
                {
                    "answer": correct,
                    "time": datetime.now().isoformat(),
                    "overtime": False,
                }
            ],
            "is_correct": True,
        }
    await manager.set(
        user_id,
        {
            "flow": "intro",
            "t2_attempts": attempts,
            "city_name": "Санкт-Петербург",
            "fio": "Тест Тестов",
        },
    )

    try:
        await services.finalize_test2(user_id)

        candidate = await candidate_services.get_user_by_telegram_id(user_id)
        assert candidate is not None
        assert candidate.test2_report_url
        report_path = Path(services.REPORTS_DIR) / str(candidate.id) / "test2.txt"
        assert report_path.exists()
    finally:
        await manager.clear()
        await manager.close()
