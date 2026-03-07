import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.security import Principal
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
from backend.domain.models import CalendarTask, City, Recruiter, Slot, SlotStatus


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

    async def send_chat_message(self, telegram_id: int, text: str, reply_markup=None) -> BotSendResult:
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
    monkeypatch.setenv("ALLOW_LEGACY_BASIC", "1")
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


async def _async_request_with_principal(
    app,
    principal: Any,
    method: str,
    path: str,
    **kwargs,
) -> Any:
    def _call() -> Any:
        from backend.apps.admin_ui.security import require_principal

        app.dependency_overrides[require_principal] = lambda: principal
        try:
            with TestClient(app) as client:
                client.auth = ("admin", "admin")
                return client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(require_principal, None)

    return await asyncio.to_thread(_call)


async def _create_recruiter(name: str, *, city_name: str) -> int:
    async with async_session() as session:
        city = City(name=city_name, tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name=name, tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        return recruiter.id


async def _create_recruiter_pair_in_city(
    owner_name: str,
    viewer_name: str,
    *,
    city_name: str,
) -> tuple[int, int]:
    async with async_session() as session:
        city = City(name=city_name, tz="Europe/Moscow", active=True)
        owner = Recruiter(name=owner_name, tz="Europe/Moscow", active=True)
        viewer = Recruiter(name=viewer_name, tz="Europe/Moscow", active=True)
        owner.cities.append(city)
        viewer.cities.append(city)
        session.add_all([city, owner, viewer])
        await session.commit()
        await session.refresh(owner)
        await session.refresh(viewer)
        return owner.id, viewer.id


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
async def test_recruiter_can_access_chat_for_scoped_candidate(admin_app) -> None:
    recruiter_id = await _create_recruiter("Scoped Chat Recruiter", city_name="Москва")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90104,
        fio="Scoped Chat Tester",
        city="Москва",
        username="scoped_chat_tester",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=recruiter_id,
    )

    history_response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=recruiter_id),
        "get",
        f"/api/candidates/{candidate.id}/chat",
    )
    assert history_response.status_code == 200
    assert history_response.json()["messages"] == []

    send_response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=recruiter_id),
        "post",
        f"/api/candidates/{candidate.id}/chat",
        json={"text": "Сообщение в пределах scope", "client_request_id": "scoped-req-1"},
    )
    assert send_response.status_code == 200
    payload = send_response.json()
    assert payload["message"]["text"] == "Сообщение в пределах scope"
    assert payload["message"]["direction"] == ChatMessageDirection.OUTBOUND.value


@pytest.mark.asyncio
async def test_recruiter_can_access_chat_for_city_scoped_candidate(admin_app) -> None:
    owner_id, viewer_id = await _create_recruiter_pair_in_city(
        "Chat City Owner Recruiter",
        "Chat City Viewer Recruiter",
        city_name="Томск",
    )
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90108,
        fio="City Scoped Chat Candidate",
        city="Томск",
        username="city_scoped_chat_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=viewer_id),
        "get",
        f"/api/candidates/{candidate.id}/chat",
    )

    assert response.status_code == 200
    assert response.json()["messages"] == []


@pytest.mark.asyncio
async def test_recruiter_cannot_view_foreign_candidate_chat(admin_app) -> None:
    owner_id = await _create_recruiter("Chat Owner Recruiter", city_name="Москва")
    outsider_id = await _create_recruiter("Chat Outsider Recruiter", city_name="Тверь")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90105,
        fio="Foreign Chat Candidate",
        city="Москва",
        username="foreign_chat_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "get",
        f"/api/candidates/{candidate.id}/chat",
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_recruiter_can_view_city_scoped_candidate_detail(admin_app) -> None:
    owner_id, viewer_id = await _create_recruiter_pair_in_city(
        "Detail City Owner Recruiter",
        "Detail City Viewer Recruiter",
        city_name="Воронеж",
    )
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90109,
        fio="City Scoped Detail Candidate",
        city="Воронеж",
        username="city_scoped_detail_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=viewer_id),
        "get",
        f"/api/candidates/{candidate.id}",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == candidate.id
    assert payload["fio"] == "City Scoped Detail Candidate"


@pytest.mark.asyncio
async def test_recruiter_cannot_view_foreign_candidate_detail(admin_app) -> None:
    owner_id = await _create_recruiter("Detail Owner Recruiter", city_name="Москва")
    outsider_id = await _create_recruiter("Detail Outsider Recruiter", city_name="Омск")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90110,
        fio="Foreign Detail Candidate",
        city="Москва",
        username="foreign_detail_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "get",
        f"/api/candidates/{candidate.id}",
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_recruiter_cannot_send_chat_to_foreign_candidate(admin_app) -> None:
    owner_id = await _create_recruiter("Chat Send Owner Recruiter", city_name="Москва")
    outsider_id = await _create_recruiter("Chat Send Outsider Recruiter", city_name="Казань")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90106,
        fio="Foreign Send Candidate",
        city="Москва",
        username="foreign_send_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "post",
        f"/api/candidates/{candidate.id}/chat",
        json={"text": "Чужое сообщение", "client_request_id": "foreign-send-1"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_recruiter_cannot_retry_foreign_candidate_chat(admin_app) -> None:
    owner_id = await _create_recruiter("Chat Retry Owner Recruiter", city_name="Москва")
    outsider_id = await _create_recruiter("Chat Retry Outsider Recruiter", city_name="Самара")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90107,
        fio="Foreign Retry Candidate",
        city="Москва",
        username="foreign_retry_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    async with async_session() as session:
        msg = ChatMessage(
            candidate_id=candidate.id,
            telegram_user_id=candidate.telegram_id,
            direction=ChatMessageDirection.OUTBOUND.value,
            channel="telegram",
            text="Чужой ретрай",
            status=ChatMessageStatus.FAILED.value,
            created_at=datetime.now(timezone.utc),
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        message_id = msg.id

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "post",
        f"/api/candidates/{candidate.id}/chat/{message_id}/retry",
    )

    assert response.status_code == 404


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


@pytest.mark.asyncio
async def test_recruiter_can_execute_action_for_city_scoped_candidate(admin_app) -> None:
    owner_id, viewer_id = await _create_recruiter_pair_in_city(
        "Action City Owner Recruiter",
        "Action City Viewer Recruiter",
        city_name="Тюмень",
    )
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90111,
        fio="City Scoped Action Candidate",
        city="Тюмень",
        username="city_scoped_action_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=viewer_id),
        "post",
        f"/api/candidates/{candidate.id}/actions/reject",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == CandidateStatus.INTERVIEW_DECLINED.value


@pytest.mark.asyncio
async def test_recruiter_cannot_execute_action_for_foreign_candidate(admin_app) -> None:
    owner_id = await _create_recruiter("Action Owner Recruiter", city_name="Москва")
    outsider_id = await _create_recruiter("Action Outsider Recruiter", city_name="Пермь")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90112,
        fio="Foreign Action Candidate",
        city="Москва",
        username="foreign_action_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "post",
        f"/api/candidates/{candidate.id}/actions/reject",
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_recruiter_can_delete_owned_candidate(admin_app) -> None:
    recruiter_id = await _create_recruiter("Delete Owned Recruiter", city_name="Ярославль")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90113,
        fio="Owned Delete Candidate",
        city="Ярославль",
        username="owned_delete_candidate",
        initial_status=CandidateStatus.LEAD,
        responsible_recruiter_id=recruiter_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=recruiter_id),
        "delete",
        f"/api/candidates/{candidate.id}",
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["id"] == candidate.id

    async with async_session() as session:
        deleted_user = await session.get(User, candidate.id)
        assert deleted_user is None


@pytest.mark.asyncio
async def test_recruiter_cannot_delete_foreign_candidate(admin_app) -> None:
    owner_id = await _create_recruiter("Delete Owner Recruiter", city_name="Москва")
    outsider_id = await _create_recruiter("Delete Outsider Recruiter", city_name="Сочи")
    candidate = await candidate_services.create_or_update_user(
        telegram_id=90114,
        fio="Foreign Delete Candidate",
        city="Москва",
        username="foreign_delete_candidate",
        initial_status=CandidateStatus.LEAD,
        responsible_recruiter_id=owner_id,
    )

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "delete",
        f"/api/candidates/{candidate.id}",
        follow_redirects=False,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_calendar_tasks_crud_and_events(admin_app) -> None:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    async with async_session() as session:
        recruiter = Recruiter(name="Calendar Recruiter", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    create_response = await _async_request(
        admin_app,
        "post",
        "/api/calendar/tasks",
        json={
            "title": "Сверить список кандидатов",
            "description": "Проверить подтверждения за день",
            "start": now.isoformat(),
            "end": (now + timedelta(minutes=45)).isoformat(),
            "recruiter_id": recruiter_id,
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["ok"] is True
    task_id = int(create_payload["task"]["id"])

    start_date = (now.date() - timedelta(days=1)).isoformat()
    end_date = (now.date() + timedelta(days=2)).isoformat()
    events_response = await _async_request(
        admin_app,
        "get",
        f"/api/calendar/events?start={start_date}&end={end_date}&recruiter_id={recruiter_id}&include_tasks=true",
    )
    assert events_response.status_code == 200
    events_payload = events_response.json()
    task_events = [
        event
        for event in events_payload.get("events", [])
        if event.get("extendedProps", {}).get("event_type") == "task"
        and event.get("extendedProps", {}).get("task_id") == task_id
    ]
    assert len(task_events) == 1

    update_response = await _async_request(
        admin_app,
        "patch",
        f"/api/calendar/tasks/{task_id}",
        json={"is_done": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["task"]["is_done"] is True

    delete_response = await _async_request(
        admin_app,
        "delete",
        f"/api/calendar/tasks/{task_id}",
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True

    async with async_session() as session:
        task = await session.get(CalendarTask, task_id)
        assert task is None


@pytest.mark.asyncio
async def test_calendar_confirmed_filter_includes_preconfirmed_slots(admin_app) -> None:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    async with async_session() as session:
        recruiter = Recruiter(name="Filter Recruiter", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()

        candidate = User(
            telegram_id=775501,
            telegram_user_id=775501,
            fio="Кандидат Фильтра",
            city="Москва",
        )
        session.add(candidate)
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=SlotStatus.CONFIRMED_BY_CANDIDATE,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_id=candidate.candidate_id,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()

        recruiter_id = recruiter.id

    start_date = now.date().isoformat()
    end_date = (now.date() + timedelta(days=3)).isoformat()
    response = await _async_request(
        admin_app,
        "get",
        f"/api/calendar/events?start={start_date}&end={end_date}&recruiter_id={recruiter_id}&status=confirmed",
    )
    assert response.status_code == 200
    payload = response.json()

    matched = [
        event
        for event in payload.get("events", [])
        if event.get("extendedProps", {}).get("status") == SlotStatus.CONFIRMED_BY_CANDIDATE
    ]
    assert len(matched) == 1
    assert matched[0]["extendedProps"]["status_label"] == "Предв. подтверждён"
