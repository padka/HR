from __future__ import annotations

import types
from typing import Optional

import pytest

from backend.apps.bot.handlers import common


class DummyMessage:
    def __init__(self, user_id: Optional[int] = 1) -> None:
        if user_id is None:
            self.from_user = None
        else:
            self.from_user = types.SimpleNamespace(id=user_id)
        self.text = "hello"

    async def reply(self, *args, **kwargs):  # pragma: no cover - not used in tests
        raise AssertionError("reply should not be called in these tests")


class DummyStateManager:
    def __init__(self, state, *, exc: Optional[Exception] = None) -> None:
        self._state = state
        self._exc = exc
        self.calls = 0

    async def get(self, user_id: int):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return self._state


@pytest.mark.asyncio
async def test_free_text_ignores_when_state_missing(monkeypatch):
    manager = DummyStateManager(state=None)
    monkeypatch.setattr(common.services, "get_state_manager", lambda: manager)

    async def fake_handle_test1(message):  # pragma: no cover - defensive
        raise AssertionError("handle_test1_answer should not be called")

    send_called = False

    async def fake_send_welcome(user_id: int) -> None:  # pragma: no cover
        nonlocal send_called
        send_called = True

    monkeypatch.setattr(common.services, "send_welcome", fake_send_welcome)
    monkeypatch.setattr(common.services, "handle_test1_answer", fake_handle_test1)

    message = DummyMessage(user_id=42)

    await common.free_text(message)

    assert manager.calls == 1
    assert send_called is False


@pytest.mark.asyncio
async def test_free_text_ignores_messages_without_user(monkeypatch):
    manager = DummyStateManager(state={"flow": "interview", "t1_idx": 0})
    monkeypatch.setattr(common.services, "get_state_manager", lambda: manager)

    send_called = False

    async def fake_send_welcome(user_id: int) -> None:
        nonlocal send_called
        send_called = True

    async def fake_handle_test1(message):  # pragma: no cover - defensive
        raise AssertionError("handle_test1_answer should not be called")

    monkeypatch.setattr(common.services, "send_welcome", fake_send_welcome)
    monkeypatch.setattr(common.services, "handle_test1_answer", fake_handle_test1)

    message = DummyMessage(user_id=None)

    await common.free_text(message)

    assert manager.calls == 0
    assert send_called is False


@pytest.mark.asyncio
async def test_free_text_delegates_to_test1_handler(monkeypatch):
    manager = DummyStateManager(state={"flow": "interview", "t1_idx": 0})
    monkeypatch.setattr(common.services, "get_state_manager", lambda: manager)

    async def fake_handle(message):
        fake_handle.called = True

    fake_handle.called = False

    monkeypatch.setattr(common.services, "handle_test1_answer", fake_handle)

    message = DummyMessage(user_id=7)

    await common.free_text(message)

    assert manager.calls == 1
    assert fake_handle.called is True


@pytest.mark.asyncio
async def test_free_text_handles_state_errors(monkeypatch):
    manager = DummyStateManager(state=None, exc=RuntimeError("boom"))
    monkeypatch.setattr(common.services, "get_state_manager", lambda: manager)

    called = {}

    async def fake_handle_test1(message):  # pragma: no cover - defensive
        raise AssertionError("handle_test1_answer should not be called")

    send_called = False

    async def fake_send_welcome(user_id: int) -> None:  # pragma: no cover
        nonlocal send_called
        send_called = True

    monkeypatch.setattr(common.services, "send_welcome", fake_send_welcome)
    monkeypatch.setattr(common.services, "handle_test1_answer", fake_handle_test1)

    message = DummyMessage(user_id=5)

    await common.free_text(message)

    assert manager.calls == 1
    assert send_called is False
