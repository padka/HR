import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.services.bot_service import BotSendResult
from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import (
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    User,
)
from backend.domain.candidates.status import CandidateStatus


@pytest.fixture(scope="session", autouse=True)
def configure_backend(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    db_dir = tmp_path_factory.mktemp("data_local")
    db_path = db_dir / "bot.db"
    mp.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    mp.setenv("DATA_DIR", str(db_dir))
    mp.setenv("LOG_FILE", "data/logs/test_app.log")
    mp.delenv("SQL_ECHO", raising=False)

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    import importlib

    db_module = importlib.import_module("backend.core.db")
    importlib.reload(db_module)

    from backend.domain.base import Base

    Base.metadata.create_all(bind=db_module.sync_engine)

    yield

    Base.metadata.drop_all(bind=db_module.sync_engine)
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(db_module.async_engine.dispose())
    loop.close()
    db_module.sync_engine.dispose()
    mp.undo()


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


class DummyBotService:
    """Minimal bot service stub for chat/send retries."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def is_ready(self) -> bool:  # pragma: no cover - compatibility
        return True

    async def send_chat_message(self, telegram_id: int, text: str) -> BotSendResult:
        self.calls.append({"telegram_id": telegram_id, "text": text})
        return BotSendResult(ok=True, status="sent", telegram_message_id=777)


@pytest.fixture
def admin_app(monkeypatch) -> Any:
    bot_stub = DummyBotService()

    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = bot_stub
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("LOG_FILE", "data/logs/test_app.log")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    import importlib

    state_module = importlib.import_module("backend.apps.admin_ui.state")
    app_module = importlib.import_module("backend.apps.admin_ui.app")
    monkeypatch.setattr(state_module, "setup_bot_state", fake_setup)
    monkeypatch.setattr(app_module, "setup_bot_state", fake_setup, raising=False)
    from backend.apps.admin_ui.app import create_app

    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


async def _async_request(app, method: str, path: str, **kwargs) -> Any:
    def _call() -> Any:
        with TestClient(app) as client:
            client.auth = ("admin", "admin")
            return client.request(method, path, **kwargs)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_chat_history_and_send(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90101,
        fio="Chat Tester",
        city="Москва",
        username="chat_tester",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    history_response = await _async_request(admin_app, "get", f"/api/candidates/{candidate.id}/chat")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["messages"] == []

    send_response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/chat",
        json={"text": "Привет!", "client_request_id": "req-1"},
    )
    assert send_response.status_code == 200
    payload = send_response.json()
    assert payload["message"]["text"] == "Привет!"
    assert payload["message"]["direction"] == ChatMessageDirection.OUTBOUND.value


@pytest.mark.asyncio
async def test_chat_retry_marks_as_sent(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90102,
        fio="Retry Tester",
        city="Москва",
        username="retry_tester",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    async with async_session() as session:
        msg = ChatMessage(
            candidate_id=candidate.id,
            telegram_user_id=candidate.telegram_id,
            direction=ChatMessageDirection.OUTBOUND.value,
            channel="telegram",
            text="Не доставлено",
            status=ChatMessageStatus.FAILED.value,
            created_at=datetime.now(timezone.utc),
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        message_id = msg.id

    retry_response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/chat/{message_id}/retry",
    )
    assert retry_response.status_code == 200
    result = retry_response.json()
    assert result["message"]["status"] == ChatMessageStatus.SENT.value


@pytest.mark.asyncio
async def test_candidate_action_updates_status(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90103,
        fio="Action Tester",
        city="Москва",
        username="action_tester",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    action_response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/actions/reject",
    )
    assert action_response.status_code == 200
    data = action_response.json()
    assert data["ok"] is True
    assert data["status"] == CandidateStatus.INTERVIEW_DECLINED.value

    async with async_session() as session:
        refreshed = await session.get(User, candidate.id)
        assert refreshed.candidate_status == CandidateStatus.INTERVIEW_DECLINED
