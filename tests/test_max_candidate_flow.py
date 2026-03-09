from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

import backend.core.messenger.registry as registry_mod
from backend.core.messenger.protocol import MessengerPlatform, MessengerProtocol, SendResult
from backend.core.messenger.registry import MessengerRegistry
from backend.core.db import async_session
from backend.domain.candidates.models import TestResult, User
from backend.domain.candidates.portal_service import get_candidate_portal_questions
from backend.domain.models import City


class _FakeMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def configure(self, **kwargs):
        return None

    async def send_message(
        self,
        chat_id,
        text,
        *,
        buttons=None,
        parse_mode=None,
        correlation_id=None,
    ) -> SendResult:
        self.calls.append(
            {
                "chat_id": str(chat_id),
                "text": text,
                "buttons": buttons,
                "parse_mode": parse_mode,
            }
        )
        return SendResult(success=True, message_id=f"mid_{len(self.calls)}")


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    reg = MessengerRegistry()
    adapter = _FakeMaxAdapter()
    reg.register(adapter)
    monkeypatch.setattr(registry_mod, "_registry", reg)
    return adapter


@pytest.fixture
def client():
    settings = SimpleNamespace(
        max_bot_enabled=True,
        max_bot_token="test_max_token",
        max_webhook_url="",
        max_webhook_secret="test_secret",
        environment="test",
    )
    from unittest.mock import patch

    with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
        from backend.apps.max_bot.app import create_app

        app = create_app()
        app.router.lifespan_context = None  # type: ignore[assignment]
        yield TestClient(app, raise_server_exceptions=False)


async def _seed_city(name: str) -> int:
    async with async_session() as session:
        city = City(name=name, tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        return int(city.id)


async def _seed_candidate(candidate_uuid: str) -> int:
    async with async_session() as session:
        candidate = User(
            candidate_id=candidate_uuid,
            fio="Иванов Иван Иванович",
            phone="+79991112233",
            city="Москва Existing",
            source="seed",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return int(candidate.id)


async def _load_candidate_by_max(max_user_id: str) -> User | None:
    async with async_session() as session:
        candidate = await session.scalar(select(User).where(User.max_user_id == max_user_id))
        if candidate:
            session.expunge(candidate)
        return candidate


async def _load_candidate_by_uuid(candidate_uuid: str) -> User | None:
    async with async_session() as session:
        candidate = await session.scalar(select(User).where(User.candidate_id == candidate_uuid))
        if candidate:
            session.expunge(candidate)
        return candidate


async def _load_latest_test1(candidate_id: int) -> TestResult | None:
    async with async_session() as session:
        row = await session.scalar(
            select(TestResult)
            .where(TestResult.user_id == candidate_id, TestResult.rating == "TEST1")
            .order_by(TestResult.id.desc())
            .limit(1)
        )
        if row:
            session.expunge(row)
        return row


def _post_bot_started(client: TestClient, *, max_user_id: str, start_payload: str | None = None):
    body = {
        "update_type": "bot_started",
        "chat_id": max_user_id,
        "user": {"user_id": max_user_id, "name": "Max Candidate"},
    }
    if start_payload:
        body["start_payload"] = start_payload
    return client.post(
        "/webhook",
        json=body,
        headers={"X-Max-Bot-Api-Secret": "test_secret"},
    )


def _post_callback(client: TestClient, *, max_user_id: str, payload: str):
    return client.post(
        "/webhook",
        json={
            "update_type": "message_callback",
            "callback": {
                "payload": payload,
                "user": {"user_id": max_user_id},
            },
        },
        headers={"X-Max-Bot-Api-Secret": "test_secret"},
    )


def _post_text(client: TestClient, *, max_user_id: str, text: str):
    return client.post(
        "/webhook",
        json={
            "update_type": "message_created",
            "message": {
                "sender": {"user_id": max_user_id, "name": "Max Candidate"},
                "body": {"text": text},
            },
        },
        headers={"X-Max-Bot-Api-Secret": "test_secret"},
    )


def _screening_answer(question: dict[str, object]) -> tuple[str, bool]:
    qid = str(question["id"])
    options = list(question.get("options") or [])
    if options:
        return f"callback:{qid}:0", True
    if qid == "age":
        return "27", False
    return "Тестовый ответ кандидата", False


def test_max_flow_completes_profile_and_screening(client: TestClient, _isolated_registry: _FakeMaxAdapter):
    city_name = f"Москва MAX {uuid4().hex[:6]}"
    asyncio.run(_seed_city(city_name))
    max_user_id = f"77{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id)
    assert response.status_code == 200
    assert "пройти первичную анкету" in str(_isolated_registry.calls[-1]["text"]).lower()

    response = _post_callback(client, max_user_id=max_user_id, payload="maxflow:start")
    assert response.status_code == 200
    assert "фио" in str(_isolated_registry.calls[-1]["text"]).lower()

    assert _post_text(client, max_user_id=max_user_id, text="Иванов Иван Иванович").status_code == 200
    assert "телефон" in str(_isolated_registry.calls[-1]["text"]).lower()

    assert _post_text(client, max_user_id=max_user_id, text="+7 (999) 111-22-33").status_code == 200
    assert "город" in str(_isolated_registry.calls[-1]["text"]).lower()

    assert _post_text(client, max_user_id=max_user_id, text=city_name).status_code == 200
    assert "контакты сохранены" in str(_isolated_registry.calls[-2]["text"]).lower()
    assert "вопрос" in str(_isolated_registry.calls[-1]["text"]).lower()

    for question in get_candidate_portal_questions():
        answer, is_callback = _screening_answer(question)
        if is_callback:
            _, qid, option_idx = answer.split(":")
            response = _post_callback(client, max_user_id=max_user_id, payload=f"mxq:{qid}:{option_idx}")
        else:
            response = _post_text(client, max_user_id=max_user_id, text=answer)
        assert response.status_code == 200

    candidate = asyncio.run(_load_candidate_by_max(max_user_id))
    assert candidate is not None
    assert candidate.fio == "Иванов Иван Иванович"
    assert candidate.phone == "+79991112233"
    assert candidate.city == city_name
    assert candidate.messenger_platform == "max"
    assert candidate.candidate_status is not None
    assert candidate.candidate_status.value == "waiting_slot"

    test1 = asyncio.run(_load_latest_test1(candidate.id))
    assert test1 is not None
    assert test1.source == "max_bot"

    last_call = _isolated_registry.calls[-1]
    assert "кабинете кандидата" in str(last_call["text"]).lower() or "продолжить" in str(last_call["text"]).lower()
    buttons = last_call["buttons"] or []
    assert buttons
    assert buttons[0][0].url


def test_max_bot_started_links_existing_candidate_by_payload(client: TestClient, _isolated_registry: _FakeMaxAdapter):
    candidate_uuid = str(uuid4())
    asyncio.run(_seed_candidate(candidate_uuid))
    max_user_id = f"88{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id, start_payload=candidate_uuid)
    assert response.status_code == 200

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == max_user_id
    assert candidate.messenger_platform == "max"
