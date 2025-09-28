from datetime import datetime, timedelta, timezone

import pytest
from aiogram.fsm.storage.memory import MemoryStorage

from backend.apps.bot.state_manager import ReminderMeta, StateManager


@pytest.mark.asyncio
async def test_load_save_and_update_state():
    storage = MemoryStorage()
    manager = StateManager(storage)
    manager.set_bot_id(1)

    assert await manager.load_state(10) == {}

    await manager.save_state(10, {"foo": "bar"})
    assert await manager.load_state(10) == {"foo": "bar"}

    updated = await manager.update_state(10, foo="baz", extra=1)
    assert updated["foo"] == "baz"
    assert updated["extra"] == 1

    await manager.clear_state(10)
    assert await manager.load_state(10) == {}


@pytest.mark.asyncio
async def test_schedule_and_cancel_reminders():
    storage = MemoryStorage()
    manager = StateManager(storage)
    manager.set_bot_id(2)

    base = datetime.now(timezone.utc)
    await manager.schedule_reminder(
        slot_id=1,
        candidate_id=2,
        notify_at=base + timedelta(seconds=1),
        kind="demo",
    )

    # Not yet due
    assert await manager.pop_due_reminders(now=base) == []

    # Due reminders are returned once
    due = await manager.pop_due_reminders(now=base + timedelta(seconds=2))
    assert len(due) == 1
    assert isinstance(due[0], ReminderMeta)
    assert due[0].slot_id == 1

    # Subsequent calls empty
    assert await manager.pop_due_reminders(now=base + timedelta(seconds=3)) == []

    await manager.schedule_reminder(
        slot_id=3,
        candidate_id=4,
        notify_at=base + timedelta(seconds=1),
        kind="demo",
    )
    await manager.cancel_reminder(slot_id=3, candidate_id=4, kind="demo")
    assert await manager.pop_due_reminders(now=base + timedelta(seconds=3)) == []


@pytest.mark.asyncio
async def test_state_persists_with_shared_storage():
    storage = MemoryStorage()

    manager1 = StateManager(storage)
    manager1.set_bot_id(5)
    await manager1.save_state(42, {"foo": "bar"})
    future = datetime.now(timezone.utc) + timedelta(seconds=1)
    await manager1.schedule_reminder(
        slot_id=9,
        candidate_id=42,
        notify_at=future,
        kind="demo",
    )

    # "Restart" with a new manager using the same storage instance
    manager2 = StateManager(storage)
    manager2.set_bot_id(5)

    assert await manager2.load_state(42) == {"foo": "bar"}
    due = await manager2.pop_due_reminders(now=future + timedelta(seconds=1))
    assert len(due) == 1
    assert due[0].candidate_id == 42
