import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.security import Principal, require_principal
from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import ChatMessage, ChatMessageDirection, ChatMessageStatus
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app(monkeypatch) -> Any:
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


async def _async_request_with_principal(
    app,
    principal: Principal,
    method: str,
    path: str,
    **kwargs,
) -> Any:
    def _call() -> Any:
        app.dependency_overrides[require_principal] = lambda: principal
        try:
            with TestClient(app) as client:
                client.auth = ("admin", "admin")
                return client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(require_principal, None)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_candidate_chat_threads_count_unread_and_mark_read(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Чатовый город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Chat Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)

        recruiter_id = recruiter.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=79990010001,
        fio="Chat Candidate",
        city="Чатовый город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        session.add_all(
            [
                ChatMessage(
                    candidate_id=candidate.id,
                    telegram_user_id=candidate.telegram_id,
                    direction=ChatMessageDirection.INBOUND.value,
                    channel="telegram",
                    text="Добрый день",
                    status=ChatMessageStatus.RECEIVED.value,
                    created_at=now - timedelta(minutes=5),
                ),
                ChatMessage(
                    candidate_id=candidate.id,
                    telegram_user_id=candidate.telegram_id,
                    direction=ChatMessageDirection.INBOUND.value,
                    channel="telegram",
                    text="Хочу перенести время",
                    status=ChatMessageStatus.RECEIVED.value,
                    created_at=now - timedelta(minutes=1),
                ),
            ]
        )
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)
    list_response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads",
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    thread = next(item for item in payload["threads"] if item["candidate_id"] == candidate.id)
    assert thread["unread_count"] == 2
    assert thread["last_message"]["direction"] == "inbound"

    mark_response = await _async_request_with_principal(
        admin_app,
        principal,
        "post",
        f"/api/candidate-chat/threads/{candidate.id}/read",
    )
    assert mark_response.status_code == 200
    assert mark_response.json()["ok"] is True

    list_after = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads",
    )
    assert list_after.status_code == 200
    payload_after = list_after.json()
    thread_after = next(item for item in payload_after["threads"] if item["candidate_id"] == candidate.id)
    assert thread_after["unread_count"] == 0


@pytest.mark.asyncio
async def test_candidate_chat_mark_read_is_idempotent(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Идемпотентный город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Idempotent Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=79990010011,
        fio="Idempotent Candidate",
        city="Идемпотентный город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )

    principal = Principal(type="recruiter", id=recruiter_id)
    path = f"/api/candidate-chat/threads/{candidate.id}/read"

    first = await _async_request_with_principal(admin_app, principal, "post", path)
    second = await _async_request_with_principal(admin_app, principal, "post", path)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["ok"] is True
    assert second.json()["ok"] is True


@pytest.mark.asyncio
async def test_candidate_chat_threads_empty_payload_is_stable(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Пустой город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Empty Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=recruiter_id),
        "get",
        "/api/candidate-chat/threads",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["threads"] == []
    assert payload["latest_event_at"] is None


@pytest.mark.asyncio
async def test_candidate_chat_threads_updates_returns_new_activity(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Апдейт город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Update Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=79990010002,
        fio="Update Candidate",
        city="Апдейт город",
        initial_status=CandidateStatus.WAITING_SLOT,
        responsible_recruiter_id=recruiter_id,
    )

    message_time = datetime.now(timezone.utc) - timedelta(seconds=2)
    async with async_session() as session:
        session.add(
            ChatMessage(
                candidate_id=candidate.id,
                telegram_user_id=candidate.telegram_id,
                direction=ChatMessageDirection.INBOUND.value,
                channel="telegram",
                text="Есть ли время завтра?",
                status=ChatMessageStatus.RECEIVED.value,
                created_at=message_time,
            )
        )
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)
    since = quote((message_time - timedelta(minutes=1)).isoformat(), safe="")
    response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        f"/api/candidate-chat/threads/updates?since={since}&timeout=5",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] is True
    thread = next(item for item in payload["threads"] if item["candidate_id"] == candidate.id)
    assert thread["last_message"]["text"] == "Есть ли время завтра?"


@pytest.mark.asyncio
async def test_candidate_chat_threads_can_be_archived_and_restored(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Архивный город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Archive Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=79990010003,
        fio="Archive Candidate",
        city="Архивный город",
        initial_status=CandidateStatus.WAITING_SLOT,
        responsible_recruiter_id=recruiter_id,
    )

    async with async_session() as session:
        session.add(
            ChatMessage(
                candidate_id=candidate.id,
                telegram_user_id=candidate.telegram_id,
                direction=ChatMessageDirection.INBOUND.value,
                channel="telegram",
                text="Уберите чат из активных",
                status=ChatMessageStatus.RECEIVED.value,
                created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)
    archive_response = await _async_request_with_principal(
        admin_app,
        principal,
        "post",
        f"/api/candidate-chat/threads/{candidate.id}/archive",
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["archived"] is True

    inbox_response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads",
    )
    assert inbox_response.status_code == 200
    assert all(item["candidate_id"] != candidate.id for item in inbox_response.json()["threads"])

    archive_list_response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads?folder=archive",
    )
    assert archive_list_response.status_code == 200
    archived_thread = next(item for item in archive_list_response.json()["threads"] if item["candidate_id"] == candidate.id)
    assert archived_thread["is_archived"] is True

    restore_response = await _async_request_with_principal(
        admin_app,
        principal,
        "post",
        f"/api/candidate-chat/threads/{candidate.id}/unarchive",
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["archived"] is False

    restored_inbox = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads",
    )
    assert restored_inbox.status_code == 200
    restored_thread = next(item for item in restored_inbox.json()["threads"] if item["candidate_id"] == candidate.id)
    assert restored_thread["is_archived"] is False


@pytest.mark.asyncio
async def test_candidate_chat_threads_search_filters_by_name_and_text(admin_app) -> None:
    """Search should match candidate fio and last message text."""
    async with async_session() as session:
        city = City(name="Поисковый город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Search Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    alice = await candidate_services.create_or_update_user(
        telegram_id=79990020001,
        fio="Алиса Смирнова",
        city="Поисковый город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )
    bob = await candidate_services.create_or_update_user(
        telegram_id=79990020002,
        fio="Борис Кузнецов",
        city="Поисковый город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        session.add_all([
            ChatMessage(
                candidate_id=alice.id,
                telegram_user_id=alice.telegram_id,
                direction=ChatMessageDirection.INBOUND.value,
                channel="telegram",
                text="Готова выйти на стажировку",
                status=ChatMessageStatus.RECEIVED.value,
                created_at=now - timedelta(minutes=2),
            ),
            ChatMessage(
                candidate_id=bob.id,
                telegram_user_id=bob.telegram_id,
                direction=ChatMessageDirection.INBOUND.value,
                channel="telegram",
                text="Добрый день",
                status=ChatMessageStatus.RECEIVED.value,
                created_at=now - timedelta(minutes=1),
            ),
        ])
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)

    # Search by name: only Alice
    resp = await _async_request_with_principal(
        admin_app, principal, "get",
        "/api/candidate-chat/threads?search=Алиса",
    )
    assert resp.status_code == 200
    threads = resp.json()["threads"]
    assert len(threads) == 1
    assert threads[0]["candidate_id"] == alice.id

    # Search by last message text: only Alice ("стажировку")
    resp = await _async_request_with_principal(
        admin_app, principal, "get",
        f"/api/candidate-chat/threads?search={quote('стажировку', safe='')}",
    )
    assert resp.status_code == 200
    threads = resp.json()["threads"]
    assert len(threads) == 1
    assert threads[0]["candidate_id"] == alice.id

    # Search with no match
    resp = await _async_request_with_principal(
        admin_app, principal, "get",
        f"/api/candidate-chat/threads?search={quote('несуществующий', safe='')}",
    )
    assert resp.status_code == 200
    assert resp.json()["threads"] == []


@pytest.mark.asyncio
async def test_candidate_chat_threads_updates_respects_search_and_unread(admin_app) -> None:
    """/threads/updates must filter by search and unread_only, same as /threads."""
    async with async_session() as session:
        city = City(name="Фильтр город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Filter Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    cand_a = await candidate_services.create_or_update_user(
        telegram_id=79990030001,
        fio="Виктория Иванова",
        city="Фильтр город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )
    cand_b = await candidate_services.create_or_update_user(
        telegram_id=79990030002,
        fio="Георгий Попов",
        city="Фильтр город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        session.add_all([
            ChatMessage(
                candidate_id=cand_a.id,
                telegram_user_id=cand_a.telegram_id,
                direction=ChatMessageDirection.INBOUND.value,
                channel="telegram",
                text="Вопрос по зарплате",
                status=ChatMessageStatus.RECEIVED.value,
                created_at=now - timedelta(minutes=2),
            ),
            ChatMessage(
                candidate_id=cand_b.id,
                telegram_user_id=cand_b.telegram_id,
                direction=ChatMessageDirection.OUTBOUND.value,
                channel="telegram",
                text="Ждём вашего ответа",
                status=ChatMessageStatus.SENT.value,
                created_at=now - timedelta(minutes=1),
            ),
        ])
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)
    since = quote((now - timedelta(hours=1)).isoformat(), safe="")

    # updates with search: only Виктория
    resp = await _async_request_with_principal(
        admin_app, principal, "get",
        f"/api/candidate-chat/threads/updates?since={since}&timeout=5"
        f"&search={quote('Виктория', safe='')}",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["updated"] is True
    assert len(payload["threads"]) == 1
    assert payload["threads"][0]["candidate_id"] == cand_a.id

    # updates with unread_only: only cand_a (inbound = unread), not cand_b (outbound)
    resp = await _async_request_with_principal(
        admin_app, principal, "get",
        f"/api/candidate-chat/threads/updates?since={since}&timeout=5&unread_only=true",
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["updated"] is True
    cand_ids = {t["candidate_id"] for t in payload["threads"]}
    assert cand_a.id in cand_ids
    assert cand_b.id not in cand_ids

    # Consistency: /threads and /threads/updates return the same set for same filters
    search_q = quote("зарплате", safe="")
    initial = await _async_request_with_principal(
        admin_app, principal, "get",
        f"/api/candidate-chat/threads?search={search_q}",
    )
    updates = await _async_request_with_principal(
        admin_app, principal, "get",
        f"/api/candidate-chat/threads/updates?since={since}&timeout=5&search={search_q}",
    )
    initial_ids = {t["candidate_id"] for t in initial.json()["threads"]}
    updates_ids = {t["candidate_id"] for t in updates.json()["threads"]}
    assert initial_ids == updates_ids


@pytest.mark.asyncio
async def test_candidate_chat_threads_prioritize_operational_buckets(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Приоритет город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Priority Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    overdue_candidate = await candidate_services.create_or_update_user(
        telegram_id=79990040001,
        fio="Просроченный Кандидат",
        city="Приоритет город",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=recruiter_id,
    )
    blocked_candidate = await candidate_services.create_or_update_user(
        telegram_id=79990040002,
        fio="Кандидат На Подтверждении",
        city="Приоритет город",
        initial_status=CandidateStatus.SLOT_PENDING,
        responsible_recruiter_id=recruiter_id,
    )
    waiting_candidate = await candidate_services.create_or_update_user(
        telegram_id=79990040003,
        fio="Ждём Ответа",
        city="Приоритет город",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=recruiter_id,
    )
    system_candidate = await candidate_services.create_or_update_user(
        telegram_id=79990040004,
        fio="Системный Кандидат",
        city="Приоритет город",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=recruiter_id,
    )
    terminal_candidate = await candidate_services.create_or_update_user(
        telegram_id=79990040005,
        fio="Терминальный Кандидат",
        city="Приоритет город",
        initial_status=CandidateStatus.INTERVIEW_DECLINED,
        responsible_recruiter_id=recruiter_id,
    )

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        session.add_all(
            [
                ChatMessage(
                    candidate_id=overdue_candidate.id,
                    telegram_user_id=overdue_candidate.telegram_id,
                    direction=ChatMessageDirection.INBOUND.value,
                    channel="telegram",
                    text="Вы мне ответите?",
                    status=ChatMessageStatus.RECEIVED.value,
                    created_at=now - timedelta(hours=8),
                ),
                ChatMessage(
                    candidate_id=blocked_candidate.id,
                    telegram_user_id=blocked_candidate.telegram_id,
                    direction=ChatMessageDirection.OUTBOUND.value,
                    channel="telegram",
                    text="Подтвердите слот, пожалуйста",
                    status=ChatMessageStatus.SENT.value,
                    author_label="Рекрутер",
                    created_at=now - timedelta(hours=2),
                ),
                ChatMessage(
                    candidate_id=waiting_candidate.id,
                    telegram_user_id=waiting_candidate.telegram_id,
                    direction=ChatMessageDirection.OUTBOUND.value,
                    channel="telegram",
                    text="Жду ваше подтверждение",
                    status=ChatMessageStatus.SENT.value,
                    author_label="Рекрутер",
                    created_at=now - timedelta(hours=1),
                ),
                ChatMessage(
                    candidate_id=system_candidate.id,
                    telegram_user_id=system_candidate.telegram_id,
                    direction=ChatMessageDirection.OUTBOUND.value,
                    channel="telegram",
                    text="Автоматическое напоминание",
                    status=ChatMessageStatus.SENT.value,
                    author_label="bot",
                    created_at=now - timedelta(minutes=10),
                ),
                ChatMessage(
                    candidate_id=terminal_candidate.id,
                    telegram_user_id=terminal_candidate.telegram_id,
                    direction=ChatMessageDirection.OUTBOUND.value,
                    channel="telegram",
                    text="Фиксируем отказ",
                    status=ChatMessageStatus.SENT.value,
                    author_label="Рекрутер",
                    created_at=now - timedelta(minutes=5),
                ),
            ]
        )
        await session.commit()

    principal = Principal(type="recruiter", id=recruiter_id)
    inbox_response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads?folder=inbox",
    )
    assert inbox_response.status_code == 200
    inbox_threads = inbox_response.json()["threads"]
    inbox_ids = [int(item["candidate_id"]) for item in inbox_threads]
    assert inbox_ids[:3] == [overdue_candidate.id, blocked_candidate.id, waiting_candidate.id]
    assert system_candidate.id not in inbox_ids
    assert terminal_candidate.id not in inbox_ids
    assert inbox_threads[0]["priority_bucket"] == "overdue"
    assert inbox_threads[1]["priority_bucket"] == "blocked"
    assert inbox_threads[2]["priority_bucket"] == "waiting_candidate"

    all_response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        "/api/candidate-chat/threads?folder=all",
    )
    assert all_response.status_code == 200
    all_threads = {int(item["candidate_id"]): item for item in all_response.json()["threads"]}
    assert all_threads[system_candidate.id]["priority_bucket"] == "system"
    assert all_threads[terminal_candidate.id]["priority_bucket"] == "terminal"


@pytest.mark.asyncio
async def test_candidate_chat_workspace_roundtrip_and_scope(admin_app) -> None:
    async with async_session() as session:
        city = City(name="Workspace город", tz="Europe/Moscow", active=True)
        foreign_city = City(name="Чужой город", tz="Europe/Moscow", active=True)
        owner = Recruiter(name="Workspace Owner", tz="Europe/Moscow", active=True)
        outsider = Recruiter(name="Workspace Outsider", tz="Europe/Moscow", active=True)
        owner.cities.append(city)
        outsider.cities.append(foreign_city)
        session.add_all([city, foreign_city, owner, outsider])
        await session.commit()
        await session.refresh(owner)
        await session.refresh(outsider)
        owner_id = owner.id
        outsider_id = outsider.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=79990050001,
        fio="Workspace Candidate",
        city="Workspace город",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=owner_id,
    )

    due_at = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    principal = Principal(type="recruiter", id=owner_id)
    update_response = await _async_request_with_principal(
        admin_app,
        principal,
        "put",
        f"/api/candidate-chat/threads/{candidate.id}/workspace",
        json={
            "shared_note": "Перезвонить после 16:00",
            "agreements": ["Любит утренние слоты", "Ждём резюме"],
            "follow_up_due_at": due_at,
        },
    )
    assert update_response.status_code == 200
    workspace = update_response.json()
    assert workspace["shared_note"] == "Перезвонить после 16:00"
    assert workspace["agreements"] == ["Любит утренние слоты", "Ждём резюме"]
    assert workspace["follow_up_due_at"] is not None
    assert workspace["updated_by"] == "Рекрутер"

    get_response = await _async_request_with_principal(
        admin_app,
        principal,
        "get",
        f"/api/candidate-chat/threads/{candidate.id}/workspace",
    )
    assert get_response.status_code == 200
    assert get_response.json()["agreements"] == ["Любит утренние слоты", "Ждём резюме"]

    forbidden_response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "get",
        f"/api/candidate-chat/threads/{candidate.id}/workspace",
    )
    assert forbidden_response.status_code == 404
