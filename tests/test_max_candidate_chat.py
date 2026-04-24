from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import pytest
from backend.apps.admin_ui.services.candidates import api_candidate_detail_payload
from backend.core.db import async_session
from backend.core.messenger.protocol import (
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySession,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    ChatMessage,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.repositories import approve_slot
from fastapi.testclient import TestClient
from sqlalchemy import func, select

BOT_TOKEN = "max-chat-test-token"


class _FakeMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.answers: list[str] = []

    async def configure(self, **kwargs):
        return None

    async def send_message(self, chat_id, text, *, buttons=None, parse_mode=None, correlation_id=None):
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "parse_mode": parse_mode,
                "correlation_id": correlation_id,
            }
        )
        return SendResult(success=True, message_id=f"msg-{len(self.messages)}")

    async def answer_callback(self, callback_id: str, *, message=None, notification=None):
        self.answers.append(callback_id)
        return {"success": True, "notification": notification, "message": message}


def _generate_max_init_data(
    *,
    user_id: int,
    bot_token: str = BOT_TOKEN,
    start_param: str,
    query_id: str = "max-chat-query",
    auth_date: int | None = None,
) -> str:
    payload = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": query_id,
        "user": json.dumps(
            {
                "id": user_id,
                "username": "max_candidate",
                "first_name": "Max",
                "language_code": "ru",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "start_param": start_param,
    }
    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret_key, launch_params.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(payload)


@pytest.fixture
def max_chat_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("MAX_BOT_API_SECRET", "test-max-secret")
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/miniapp")
    monkeypatch.setenv("TEST1_SCREENING_DECISION_ENABLED", "1")
    monkeypatch.setenv("AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED", "1")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    from backend.apps.admin_api.main import create_app

    app = create_app()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings_module.get_settings.cache_clear()


async def _seed_chat_candidate(
    *,
    start_param: str,
    user_id: int,
) -> dict[str, int | str]:
    now = datetime.now(UTC)
    async with async_session() as session:
        next_token_id = int(
            await session.scalar(select(func.coalesce(func.max(CandidateAccessToken.id), 0) + 1))
            or 1
        )
        city = City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="MAX Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        candidate = User(
            fio="MAX Candidate",
            username="max_candidate",
            city=city.name,
            messenger_platform="max",
            source="max",
            candidate_status=CandidateStatus.TEST1_COMPLETED,
            max_user_id=str(user_id),
        )
        session.add(candidate)
        await session.flush()

        first_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(days=1, hours=2),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        second_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(days=1, hours=4),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        session.add_all([first_slot, second_slot])
        await session.flush()

        launch_token = CandidateAccessToken(
            id=next_token_id,
            token_hash=hashlib.sha256(f"token:{start_param}".encode()).hexdigest(),
            candidate_id=candidate.id,
            token_kind=CandidateAccessTokenKind.LAUNCH.value,
            journey_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            launch_channel=CandidateLaunchChannel.MAX.value,
            start_param=start_param,
            provider_user_id=str(user_id),
            expires_at=now + timedelta(hours=1),
        )
        session.add(launch_token)
        await session.commit()
        return {
            "candidate_id": candidate.id,
            "candidate_public_id": candidate.candidate_id,
            "user_id": user_id,
            "start_param": start_param,
            "slot_id": first_slot.id,
            "next_slot_id": second_slot.id,
            "city_id": city.id,
            "recruiter_id": recruiter.id,
        }


async def _add_chat_booking_option(
    *,
    city_name: str,
    recruiter_name: str | None,
    slot_count: int = 0,
    tz_name: str = "Europe/Moscow",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    async with async_session() as session:
        city = City(name=city_name, tz=tz_name, active=True)
        session.add(city)
        await session.flush()

        recruiter = None
        if recruiter_name is not None:
            recruiter = Recruiter(name=recruiter_name, tz=tz_name, active=True)
            recruiter.cities.append(city)
            session.add(recruiter)
            await session.flush()

        slot_ids: list[int] = []
        for offset in range(slot_count):
            slot = Slot(
                recruiter_id=recruiter.id if recruiter is not None else None,
                city_id=city.id,
                start_utc=now + timedelta(days=offset + 2, hours=offset + 1),
                duration_min=60,
                status=SlotStatus.FREE,
                purpose="interview",
                tz_name=tz_name,
            )
            session.add(slot)
            await session.flush()
            slot_ids.append(int(slot.id))

        await session.commit()
        return {
            "city_id": int(city.id),
            "city_name": city.name_plain,
            "recruiter_id": int(recruiter.id) if recruiter is not None else None,
            "recruiter_name": recruiter.name if recruiter is not None else None,
            "slot_id": slot_ids[0] if slot_ids else None,
            "next_slot_id": slot_ids[1] if len(slot_ids) > 1 else None,
        }


def _launch_headers(
    client: TestClient,
    *,
    user_id: int,
    start_param: str,
    query_id: str = "launch-query",
) -> tuple[dict[str, str], dict]:
    init_data = _generate_max_init_data(
        user_id=user_id,
        start_param=start_param,
        query_id=query_id,
    )
    response = client.post("/api/max/launch", json={"init_data": init_data})
    assert response.status_code == 200
    payload = response.json()
    return (
        {
            "X-Candidate-Access-Session": payload["session"]["session_id"],
            "X-Max-Init-Data": init_data,
        },
        payload,
    )


def _complete_test1_answers() -> dict[str, str]:
    return {
        "fio": "Иванов Иван Иванович",
        "city": "Москва",
        "age": "23",
        "status": "Ищу работу",
        "notice_period": "Готов выйти в ближайшие 2 дня.",
        "salary": "60 000 – 90 000 ›",
        "format": "Да, готов",
        "sales_exp": "Есть опыт переговоров и работы с клиентами.",
        "about": "Хочу расти и зарабатывать.",
        "skills": "Коммуникация и дисциплина.",
        "expectations": "Прозрачный доход и сильная команда.",
    }


async def _load_journey(candidate_id: int) -> CandidateJourneySession | None:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateJourneySession)
            .where(CandidateJourneySession.candidate_id == candidate_id)
            .order_by(CandidateJourneySession.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _load_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _load_slot(slot_id: int) -> Slot | None:
    async with async_session() as session:
        return await session.get(Slot, slot_id)


async def _set_candidate_status(candidate_id: int, status: CandidateStatus) -> None:
    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
        assert candidate is not None
        candidate.candidate_status = status
        await session.commit()


async def _seed_intro_day_slot(
    *,
    candidate_public_id: str,
    recruiter_id: int,
    city_id: int,
) -> int:
    async with async_session() as session:
        candidate = await session.scalar(select(User).where(User.candidate_id == candidate_public_id))
        assert candidate is not None
        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            candidate_city_id=city_id,
            start_utc=datetime.now(UTC) + timedelta(days=2),
            duration_min=60,
            status=SlotStatus.BOOKED,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=None,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            intro_address="ул. Пример, 1",
            intro_contact="Ирина, +7 999 000-00-00",
        )
        session.add(slot)
        await session.flush()
        await session.commit()
        return int(slot.id)


async def _candidate_chat_messages(candidate_id: int) -> list[ChatMessage]:
    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.candidate_id == candidate_id)
            .order_by(ChatMessage.id.asc())
        )
        return list(result.scalars().all())


async def _seed_inactive_duplicate_max_candidate(*, user_id: int) -> int:
    async with async_session() as session:
        candidate = User(
            fio="MAX Duplicate Candidate",
            username="max_duplicate",
            city="Москва",
            messenger_platform="max",
            source="max",
            candidate_status=CandidateStatus.WAITING_SLOT,
            max_user_id=str(user_id),
            is_active=False,
            last_activity=datetime.now(UTC) - timedelta(days=2),
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return int(candidate.id)


async def _seed_recovery_gap_duplicate_max_candidate(*, user_id: int) -> dict[str, int]:
    now = datetime.now(UTC)
    async with async_session() as session:
        next_access_session_id = int(
            await session.scalar(select(func.coalesce(func.max(CandidateAccessSession.id), 0) + 1))
            or 1
        )
        stale_candidate = User(
            fio="MAX Stale Candidate",
            username="max_stale",
            city="Москва",
            messenger_platform="max",
            source="max",
            candidate_status=CandidateStatus.WAITING_SLOT,
            max_user_id=str(user_id),
            is_active=False,
            last_activity=now - timedelta(days=2),
        )
        session.add(stale_candidate)
        await session.flush()

        stale_journey = CandidateJourneySession(
            candidate_id=int(stale_candidate.id),
            journey_key="candidate_portal",
            journey_version="v1",
            entry_channel=CandidateLaunchChannel.MAX.value,
            current_step_key="booking",
            last_surface=CandidateJourneySurface.MAX_CHAT.value,
            last_auth_method=CandidateAccessAuthMethod.ADMIN_INVITE.value,
            status="active",
            session_version=1,
            last_activity_at=now - timedelta(hours=1),
            payload_json={
                "candidate_access": {
                    "active_surface": "max_chat",
                    "chat_cursor": {
                        "version": 1,
                        "surface": "max_chat",
                        "state": "manual_time_input",
                        "booking_id": None,
                        "updated_at": (now - timedelta(hours=1)).isoformat(),
                    },
                }
            },
        )
        session.add(stale_journey)
        await session.flush()

        session.add(
            CandidateAccessSession(
                id=next_access_session_id,
                candidate_id=int(stale_candidate.id),
                application_id=None,
                journey_session_id=int(stale_journey.id),
                journey_surface=CandidateJourneySurface.MAX_CHAT.value,
                auth_method=CandidateAccessAuthMethod.ADMIN_INVITE.value,
                launch_channel=CandidateLaunchChannel.MAX.value,
                provider_session_id=f"stale-gap:{user_id}",
                provider_user_id=str(user_id),
                session_version_snapshot=1,
                status="active",
                issued_at=now - timedelta(hours=1),
                last_seen_at=now - timedelta(hours=1),
                refreshed_at=now - timedelta(hours=1),
                expires_at=now + timedelta(hours=6),
                correlation_id=f"stale-gap-{user_id}",
                metadata_json={"seeded": "stale_gap_duplicate"},
            )
        )

        active_candidate = User(
            fio="MAX Active Candidate",
            username="max_active",
            city="Москва",
            messenger_platform="max",
            source="max",
            candidate_status=None,
            max_user_id=str(user_id),
            is_active=True,
            last_activity=now,
        )
        session.add(active_candidate)
        await session.flush()

        active_journey = CandidateJourneySession(
            candidate_id=int(active_candidate.id),
            journey_key="candidate_portal",
            journey_version="v1",
            entry_channel=CandidateLaunchChannel.MAX.value,
            current_step_key="test1",
            last_surface=CandidateJourneySurface.MAX_CHAT.value,
            last_auth_method=CandidateAccessAuthMethod.ADMIN_INVITE.value,
            status="active",
            session_version=1,
            last_activity_at=now,
            payload_json={
                "candidate_access": {
                    "active_surface": "max_chat",
                    "chat_cursor": {
                        "version": 1,
                        "surface": "max_chat",
                        "state": "test1_answering",
                        "booking_id": None,
                        "updated_at": now.isoformat(),
                    },
                }
            },
        )
        session.add(active_journey)
        await session.commit()
        return {
            "active_candidate_id": int(active_candidate.id),
            "active_journey_id": int(active_journey.id),
            "stale_candidate_id": int(stale_candidate.id),
        }


def _complete_chat_test1(client: TestClient, *, headers: dict[str, str]) -> None:
    save = client.post(
        "/api/candidate-access/test1/answers",
        headers=headers,
        json={"answers": _complete_test1_answers()},
    )
    assert save.status_code == 200
    complete = client.post("/api/candidate-access/test1/complete", headers=headers)
    assert complete.status_code == 200


def _callback_payloads(message: dict[str, object]) -> list[str]:
    payloads: list[str] = []
    for row in list(message.get("buttons") or []):
        for button in list(row):
            callback_data = getattr(button, "callback_data", None)
            if callback_data:
                payloads.append(str(callback_data))
    return payloads


def _last_prompt(adapter: _FakeMaxAdapter) -> dict[str, object]:
    assert adapter.messages
    return adapter.messages[-1]


async def _approve_slot_for_test(slot_id: int) -> Slot | None:
    return await approve_slot(int(slot_id))


def _post_max_callback(
    client: TestClient,
    *,
    user_id: int,
    callback_id: str,
    payload: str,
):
    return client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_callback",
            "timestamp": int(time.time()),
            "user": {"user_id": str(user_id)},
            "callback": {"callback_id": callback_id, "payload": payload},
        },
    )


def test_candidate_access_chat_handoff_sends_first_question(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_chat_candidate(start_param="handoff-chat", user_id=730001))
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    answer = max_chat_client.post(
        "/api/candidate-access/test1/answers",
        headers=headers,
        json={"answers": {"fio": "Иванов Иван Иванович"}},
    )
    assert answer.status_code == 200

    response = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "surface": "max_chat", "handoff_sent": True}
    assert adapter.messages
    assert "Продолжим здесь." in str(adapter.messages[0]["text"])
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.last_surface == "max_chat"
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "test1_answering"


def test_max_webhook_message_created_advances_test1_in_chat_mode(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_chat_candidate(start_param="webhook-chat", user_id=730002))
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200
    adapter.messages.clear()

    response = max_chat_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_created",
            "timestamp": 10,
            "message": {
                "sender": {"user_id": str(seeded["user_id"]), "username": "candidate_max"},
                "body": {"mid": "mid-chat-1", "text": "Иванов Иван Иванович"},
            },
        },
    )

    assert response.status_code == 200
    assert adapter.messages
    assert "Шаг 2 из" in str(adapter.messages[0]["text"])
    history = asyncio.run(_candidate_chat_messages(int(seeded["candidate_id"])))
    assert any(message.direction == "inbound" for message in history)
    assert any(message.direction == "outbound" for message in history)


def test_max_webhook_message_created_advances_test1_with_duplicate_max_identity(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_chat_candidate(start_param="webhook-chat-dup", user_id=730012))
    asyncio.run(_seed_inactive_duplicate_max_candidate(user_id=int(seeded["user_id"])))
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
        query_id="launch-query-dup",
    )
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200
    adapter.messages.clear()

    response = max_chat_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_created",
            "timestamp": 12,
            "message": {
                "sender": {"user_id": str(seeded["user_id"]), "username": "candidate_max"},
                "body": {"mid": "mid-chat-dup-1", "text": "Иванов Иван Иванович"},
            },
        },
    )

    assert response.status_code == 200
    assert adapter.messages
    assert "Шаг 2 из" in str(adapter.messages[0]["text"])
    history = asyncio.run(_candidate_chat_messages(int(seeded["candidate_id"])))
    assert any(message.direction == "inbound" for message in history)
    assert any(message.direction == "outbound" and message.channel == "max" for message in history)


def test_max_webhook_message_created_recovers_when_latest_access_session_belongs_to_stale_duplicate(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_recovery_gap_duplicate_max_candidate(user_id=730013))
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)

    response = max_chat_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_created",
            "timestamp": 13,
            "message": {
                "sender": {"user_id": "730013", "username": "candidate_max"},
                "body": {"mid": "mid-chat-gap-1", "text": "Иванов Иван Иванович"},
            },
        },
    )

    assert response.status_code == 200
    assert adapter.messages
    assert "Шаг 2 из" in str(adapter.messages[0]["text"])
    history = asyncio.run(_candidate_chat_messages(int(seeded["active_candidate_id"])))
    assert any(message.direction == "inbound" for message in history)
    assert any(message.direction == "outbound" and message.channel == "max" for message in history)
    journey = asyncio.run(_load_journey(int(seeded["active_candidate_id"])))
    assert journey is not None
    assert journey.last_access_session_id is not None

def test_max_webhook_message_created_auto_handoff_bootstraps_prompt_without_callback(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_chat_candidate(start_param="implicit-chat", user_id=730009))
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
        query_id="implicit-chat-query",
    )
    _complete_chat_test1(max_chat_client, headers=headers)
    adapter.messages.clear()

    response = max_chat_client.post(
        "/api/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "test-max-secret"},
        json={
            "update_type": "message_created",
            "timestamp": 11,
            "message": {
                "sender": {"user_id": str(seeded["user_id"]), "username": "candidate_max"},
                "body": {"mid": "mid-implicit-1", "text": "Привет"},
            },
        },
    )

    assert response.status_code == 200
    prompt = _last_prompt(adapter)
    assert "Продолжим здесь." in str(prompt["text"])
    assert "Выберите рекрутёра" in str(prompt["text"])
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.last_surface == CandidateJourneySurface.MAX_CHAT.value
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "booking_recruiter"
    history = asyncio.run(_candidate_chat_messages(int(seeded["candidate_id"])))
    assert any(message.direction == "inbound" for message in history)
    assert any(message.direction == "outbound" and message.channel == "max" for message in history)


def test_max_chat_booking_callbacks_cover_city_recruiter_slot_confirm_reschedule_and_cancel(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_chat_candidate(start_param="booking-chat", user_id=730003))
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)
    monkeypatch.setattr("backend.apps.admin_api.max_webhook.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_chat_test1(max_chat_client, headers=headers)
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200
    recruiter_prompt = _last_prompt(adapter)
    assert "Выберите рекрутёра" in str(recruiter_prompt["text"])
    recruiter_payloads = _callback_payloads(recruiter_prompt)
    assert f"recruiter:pick:{seeded['recruiter_id']}" in recruiter_payloads
    assert "booking:change_city" not in recruiter_payloads
    assert "booking:manual_time" not in recruiter_payloads
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.last_surface == CandidateJourneySurface.MAX_CHAT.value
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "booking_recruiter"

    adapter.messages.clear()
    recruiter_pick = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-recruiter",
        payload=f"recruiter:pick:{seeded['recruiter_id']}",
    )
    assert recruiter_pick.status_code == 200
    assert adapter.answers[-1] == "cb-recruiter"
    slot_prompt = _last_prompt(adapter)
    assert "Ближайшие варианты:" in str(slot_prompt["text"])
    slot_payloads = _callback_payloads(slot_prompt)
    assert f"slot:book:{seeded['slot_id']}" in slot_payloads
    assert f"slot:book:{seeded['next_slot_id']}" in slot_payloads
    button_texts = [str(getattr(button, "text", "") or "") for row in list(slot_prompt.get("buttons") or []) for button in row]
    assert any(text.startswith("Выбрать ") and ":" in text for text in button_texts)
    assert not any(text.endswith("07:20") or text.endswith("08:20") for text in button_texts)
    assert "booking:change_recruiter" not in slot_payloads
    assert "booking:change_city" not in slot_payloads
    assert "booking:manual_time" not in slot_payloads
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "booking_selecting"

    adapter.messages.clear()
    book = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-book",
        payload=f"slot:book:{seeded['slot_id']}",
    )
    assert book.status_code == 200
    assert adapter.answers[-1] == "cb-book"
    booking_prompt = _last_prompt(adapter)
    assert "отправлен рекрутёру на согласование" in str(booking_prompt["text"]).lower()
    assert _callback_payloads(booking_prompt) == []
    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "booking_pending"
    assert journey.payload_json["candidate_access"]["chat_cursor"]["booking_id"] == int(seeded["slot_id"])

    asyncio.run(_approve_slot_for_test(int(seeded["slot_id"])))

    adapter.messages.clear()
    confirm = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-confirm",
        payload=f"slot:confirm:{seeded['slot_id']}",
    )
    assert confirm.status_code == 200
    assert adapter.answers[-1] == "cb-confirm"
    confirmed_prompt = _last_prompt(adapter)
    assert "встречу подтвердили" in str(confirmed_prompt["text"]).lower()
    assert "mini app внутри MAX" in str(confirmed_prompt["text"])
    assert _callback_payloads(confirmed_prompt) == []
    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE

    adapter.messages.clear()
    reschedule = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-reschedule",
        payload=f"slot:reschedule:{seeded['slot_id']}",
    )
    assert reschedule.status_code == 200
    assert adapter.answers[-1] == "cb-reschedule"
    reschedule_prompt = _last_prompt(adapter)
    assert "Выберите новый слот ниже." in str(reschedule_prompt["text"])
    assert (
        f"slot:reschedule_pick:{seeded['slot_id']}:{seeded['next_slot_id']}"
        in _callback_payloads(reschedule_prompt)
    )
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "booking_rescheduling"
    assert journey.payload_json["candidate_access"]["chat_cursor"]["booking_id"] == int(seeded["slot_id"])

    adapter.messages.clear()
    pick = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-pick",
        payload=f"slot:reschedule_pick:{seeded['slot_id']}:{seeded['next_slot_id']}",
    )
    assert pick.status_code == 200
    assert "отправлен рекрутёру на согласование" in str(_last_prompt(adapter)["text"]).lower()
    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    next_slot = asyncio.run(_load_slot(int(seeded["next_slot_id"])))
    assert slot is not None and next_slot is not None
    assert slot.status == SlotStatus.FREE
    assert next_slot.status == SlotStatus.PENDING
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "booking_pending"
    assert journey.payload_json["candidate_access"]["chat_cursor"]["booking_id"] == int(seeded["next_slot_id"])

    adapter.messages.clear()
    cancel = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-cancel",
        payload=f"slot:cancel:{seeded['next_slot_id']}",
    )
    assert cancel.status_code == 200
    assert "Запись отменили" in str(_last_prompt(adapter)["text"])
    next_slot = asyncio.run(_load_slot(int(seeded["next_slot_id"])))
    assert next_slot is not None
    assert next_slot.status == SlotStatus.FREE
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "completed"


def test_max_chat_city_pick_without_recruiters_switches_to_manual_time_input(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_chat_candidate(start_param="no-recruiter-chat", user_id=730004))
    empty_city = asyncio.run(
        _add_chat_booking_option(
            city_name="Тула",
            recruiter_name=None,
        )
    )
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)
    monkeypatch.setattr("backend.apps.admin_api.max_webhook.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_chat_test1(max_chat_client, headers=headers)
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200

    adapter.messages.clear()
    change_city = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-change-city",
        payload="booking:change_city",
    )
    assert change_city.status_code == 200
    city_prompt = _last_prompt(adapter)
    assert f"city:pick:{empty_city['city_id']}" in _callback_payloads(city_prompt)

    adapter.messages.clear()
    empty_city_pick = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-empty-city",
        payload=f"city:pick:{empty_city['city_id']}",
    )
    assert empty_city_pick.status_code == 200
    assert adapter.answers[-1] == "cb-empty-city"
    fallback_prompt = _last_prompt(adapter)
    assert "напишите, пожалуйста, когда вам удобно пройти интервью" in str(fallback_prompt["text"]).lower()
    assert "другой город" not in str(fallback_prompt["text"]).lower()
    assert _callback_payloads(fallback_prompt) == []
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "manual_time_input"
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.manual_slot_requested_at is not None


def test_max_chat_reschedule_without_free_slots_offers_change_recruiter_and_manual_time(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = asyncio.run(_seed_chat_candidate(start_param="no-slot-chat", user_id=730005))
    single_option = asyncio.run(
        _add_chat_booking_option(
            city_name="Воронеж",
            recruiter_name="Воронеж Recruiter",
            slot_count=1,
        )
    )
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)
    monkeypatch.setattr("backend.apps.admin_api.max_webhook.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_chat_test1(max_chat_client, headers=headers)
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200

    adapter.messages.clear()
    change_city = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-single-change-city",
        payload="booking:change_city",
    )
    assert change_city.status_code == 200
    city_prompt = _last_prompt(adapter)
    assert f"city:pick:{single_option['city_id']}" in _callback_payloads(city_prompt)

    adapter.messages.clear()
    city_pick = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-single-city",
        payload=f"city:pick:{single_option['city_id']}",
    )
    assert city_pick.status_code == 200
    recruiter_prompt = _last_prompt(adapter)
    assert f"recruiter:pick:{single_option['recruiter_id']}" in _callback_payloads(recruiter_prompt)

    adapter.messages.clear()
    recruiter_pick = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-single-recruiter",
        payload=f"recruiter:pick:{single_option['recruiter_id']}",
    )
    assert recruiter_pick.status_code == 200
    slot_prompt = _last_prompt(adapter)
    assert f"slot:book:{single_option['slot_id']}" in _callback_payloads(slot_prompt)

    adapter.messages.clear()
    book = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-single-book",
        payload=f"slot:book:{single_option['slot_id']}",
    )
    assert book.status_code == 200
    slot = asyncio.run(_load_slot(int(single_option["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING

    adapter.messages.clear()
    reschedule = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-no-slots",
        payload=f"slot:reschedule:{single_option['slot_id']}",
    )
    assert reschedule.status_code == 200
    assert adapter.answers[-1] == "cb-no-slots"
    fallback_prompt = _last_prompt(adapter)
    assert "когда вам удобно пройти интервью" in str(fallback_prompt["text"]).lower()
    assert single_option["city_name"] in str(fallback_prompt["text"])
    assert _callback_payloads(fallback_prompt) == []
    journey = asyncio.run(_load_journey(int(seeded["candidate_id"])))
    assert journey is not None
    assert journey.payload_json["candidate_access"]["chat_cursor"]["state"] == "manual_time_input"


@pytest.mark.asyncio
async def test_max_chat_booking_confirm_is_visible_in_admin_operator_views(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = await _seed_chat_candidate(start_param="booking-admin-visibility", user_id=730006)
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)
    monkeypatch.setattr("backend.apps.admin_api.max_webhook.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_chat_test1(max_chat_client, headers=headers)
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200

    _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-admin-recruiter",
        payload=f"recruiter:pick:{seeded['recruiter_id']}",
    )
    _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-admin-book",
        payload=f"slot:book:{seeded['slot_id']}",
    )
    await _approve_slot_for_test(int(seeded["slot_id"]))
    confirm = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-admin-confirm",
        payload=f"slot:confirm:{seeded['slot_id']}",
    )
    assert confirm.status_code == 200

    detail = await api_candidate_detail_payload(int(seeded["candidate_id"]))
    assert detail is not None
    assert detail["linked_channels"]["max"] is True
    assert detail["channel_health"]["preferred_channel"] == "max"
    assert detail["candidate_status_slug"] == CandidateStatus.INTERVIEW_CONFIRMED.value
    assert detail["scheduling_summary"]["active"] is True
    assert detail["candidate_next_action"]["worklist_bucket"] in {
        "today",
        "awaiting_candidate",
        "awaiting_recruiter",
        "incoming",
    }


@pytest.mark.asyncio
async def test_max_chat_handoff_for_confirmed_booking_hides_confirm_action(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = await _seed_chat_candidate(start_param="booking-confirmed-chat", user_id=730014)
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)
    monkeypatch.setattr("backend.apps.admin_api.max_webhook.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_chat_test1(max_chat_client, headers=headers)
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200

    adapter.messages.clear()
    recruiter_pick = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-confirmed-recruiter",
        payload=f"recruiter:pick:{seeded['recruiter_id']}",
    )
    assert recruiter_pick.status_code == 200

    adapter.messages.clear()
    book = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-confirmed-book",
        payload=f"slot:book:{seeded['slot_id']}",
    )
    assert book.status_code == 200
    await _approve_slot_for_test(int(seeded["slot_id"]))

    adapter.messages.clear()
    confirm = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-confirmed-slot",
        payload=f"slot:confirm:{seeded['slot_id']}",
    )
    assert confirm.status_code == 200

    adapter.messages.clear()
    handoff_again = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff_again.status_code == 200
    prompt = _last_prompt(adapter)
    assert "встречу подтвердили" in str(prompt["text"]).lower()
    assert "mini app внутри MAX" in str(prompt["text"])
    assert _callback_payloads(prompt) == []


@pytest.mark.asyncio
async def test_max_chat_test2_start_callback_uses_shared_test2_state(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = await _seed_chat_candidate(start_param="test2-chat", user_id=730007)
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)
    monkeypatch.setattr("backend.apps.admin_api.max_webhook.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    await _set_candidate_status(int(seeded["candidate_id"]), CandidateStatus.TEST2_SENT)
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200

    callback = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-test2-start",
        payload="test2:start",
    )
    assert callback.status_code == 200
    prompt = _last_prompt(adapter)
    assert "Тест 2" in str(prompt["text"])
    assert any(payload.startswith("test2:0:") for payload in _callback_payloads(prompt))


@pytest.mark.asyncio
async def test_max_chat_attendance_yes_callback_confirms_intro_day(
    monkeypatch: pytest.MonkeyPatch,
    max_chat_client: TestClient,
):
    seeded = await _seed_chat_candidate(start_param="intro-day-chat", user_id=730008)
    adapter = _FakeMaxAdapter()

    async def _fake_adapter(*, settings=None):
        return adapter

    monkeypatch.setattr("backend.apps.admin_api.max_candidate_chat.ensure_max_adapter", _fake_adapter)
    monkeypatch.setattr("backend.apps.admin_api.max_webhook.ensure_max_adapter", _fake_adapter)

    headers, _ = _launch_headers(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    await _set_candidate_status(int(seeded["candidate_id"]), CandidateStatus.INTRO_DAY_SCHEDULED)
    slot_id = await _seed_intro_day_slot(
        candidate_public_id=str(seeded["candidate_public_id"]),
        recruiter_id=int(seeded["recruiter_id"]),
        city_id=int(seeded["city_id"]),
    )
    handoff = max_chat_client.post("/api/candidate-access/chat-handoff", headers=headers)
    assert handoff.status_code == 200

    callback = _post_max_callback(
        max_chat_client,
        user_id=int(seeded["user_id"]),
        callback_id="cb-intro-yes",
        payload=f"att_yes:{slot_id}",
    )
    assert callback.status_code == 200
    prompt = _last_prompt(adapter)
    assert "участие подтверждено" in str(prompt["text"]).lower()

    slot = await _load_slot(slot_id)
    assert slot is not None
    assert str(slot.status).lower() in {"confirmed", "confirmed_by_candidate"}

    detail = await api_candidate_detail_payload(int(seeded["candidate_id"]))
    assert detail is not None
    assert detail["linked_channels"]["max"] is True
    assert detail["channel_health"]["preferred_channel"] == "max"
    assert detail["candidate_status_slug"] in {
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY.value,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF.value,
        CandidateStatus.INTERVIEW_CONFIRMED.value,
    }
