from __future__ import annotations

import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

import backend.core.messenger.registry as registry_mod
from backend.core import settings as settings_module
from backend.core.messenger.protocol import MessengerPlatform, MessengerProtocol, SendResult
from backend.core.messenger.registry import MessengerRegistry
from backend.core.db import async_session
from backend.domain.candidates.services import create_candidate_invite_token
from backend.domain.candidates.models import TestResult, User
from backend.domain.candidates.portal_service import (
    get_candidate_portal_questions,
    invalidate_max_bot_profile_probe_cache,
    sign_candidate_portal_token,
)
from backend.domain.models import City


class _FakeMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def configure(self, **kwargs):
        return None

    async def get_bot_profile(self) -> dict[str, object]:
        return {
            "user": {
                "id": 312260558067,
                "name": "Attila MAX Bot",
            }
        }

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
def client(monkeypatch):
    settings_module.get_settings.cache_clear()
    invalidate_max_bot_profile_probe_cache()
    monkeypatch.setenv("MAX_BOT_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_max_token")
    monkeypatch.setenv("MAX_BOT_LINK_BASE", "https://max.ru/recruitsmartbot")
    monkeypatch.setenv("CRM_PUBLIC_URL", "https://crm.example.test")
    monkeypatch.setenv("CANDIDATE_PORTAL_PUBLIC_URL", "https://crm.example.test")
    settings = SimpleNamespace(
        max_bot_enabled=True,
        max_bot_token="test_max_token",
        max_webhook_url="",
        max_webhook_secret="test_secret",
        environment="test",
        max_bot_link_base="https://max.ru/recruitsmartbot",
        crm_public_url="https://crm.example.test",
        candidate_portal_public_url="https://crm.example.test",
    )
    from unittest.mock import patch

    try:
        with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
            from backend.apps.max_bot.app import create_app

            app = create_app()
            app.router.lifespan_context = None  # type: ignore[assignment]
            yield TestClient(app, raise_server_exceptions=False)
    finally:
        invalidate_max_bot_profile_probe_cache()
        settings_module.get_settings.cache_clear()


async def _seed_city(name: str) -> int:
    async with async_session() as session:
        city = City(name=name, tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        return int(city.id)


async def _seed_candidate(
    candidate_uuid: str,
    *,
    fio: str | None = "Иванов Иван Иванович",
    phone: str | None = "+79991112233",
    city: str | None = "Москва Existing",
    max_user_id: str | None = None,
) -> int:
    async with async_session() as session:
        candidate = User(
            candidate_id=candidate_uuid,
            fio=fio,
            phone=phone,
            city=city,
            source="seed",
            max_user_id=max_user_id,
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


async def _load_candidates_by_max(max_user_id: str) -> list[User]:
    async with async_session() as session:
        candidates = (
            await session.scalars(
                select(User)
                .where(User.max_user_id == max_user_id)
                .order_by(User.id.asc())
            )
        ).all()
        for candidate in candidates:
            session.expunge(candidate)
        return list(candidates)


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


async def _count_candidates_by_uuid(candidate_uuid: str) -> int:
    async with async_session() as session:
        return int(
            await session.scalar(select(func.count()).select_from(User).where(User.candidate_id == candidate_uuid))
            or 0
        )


def _post_bot_started(client: TestClient, *, max_user_id: str, start_payload: str | None = None):
    body = {
        "update_type": "bot_started",
        "chat_id": max_user_id,
        "user": {"user_id": max_user_id, "name": "Max Candidate"},
    }
    if start_payload:
        body["payload"] = start_payload
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
    candidate_uuid = str(uuid4())
    asyncio.run(_seed_candidate(candidate_uuid, fio=f"MAX {candidate_uuid[:8]}", phone=None, city=None))
    invite = asyncio.run(create_candidate_invite_token(candidate_uuid, channel="max"))
    max_user_id = f"77{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id, start_payload=invite.token)
    assert response.status_code == 200
    assert "пройти первичную анкету" in str(_isolated_registry.calls[-2]["text"]).lower()
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
    assert "личный кабинет" in str(last_call["text"]).lower() or "продолжить" in str(last_call["text"]).lower()
    buttons = last_call["buttons"] or []
    assert buttons
    assert buttons[0][0].url
    assert buttons[0][0].kind == "web_app"
    mini_app_url = str(buttons[0][0].url)
    assert "startapp=" in mini_app_url
    launch_token = parse_qs(urlparse(mini_app_url).query).get("startapp", [""])[0]
    assert launch_token.startswith("mx1")
    assert "." not in launch_token
    if len(buttons) > 1:
        assert buttons[1][0].url
        assert "start=" in str(buttons[1][0].url)


def test_max_bot_started_links_existing_candidate_by_payload(client: TestClient, _isolated_registry: _FakeMaxAdapter):
    candidate_uuid = str(uuid4())
    asyncio.run(_seed_candidate(candidate_uuid))
    invite = asyncio.run(create_candidate_invite_token(candidate_uuid, channel="max"))
    max_user_id = f"88{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id, start_payload=invite.token)
    assert response.status_code == 200

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == max_user_id
    assert candidate.messenger_platform == "max"


def test_max_bot_started_links_candidate_by_portal_token(client: TestClient, _isolated_registry: _FakeMaxAdapter):
    candidate_uuid = str(uuid4())
    asyncio.run(_seed_candidate(candidate_uuid))
    portal_token = sign_candidate_portal_token(
        candidate_uuid=candidate_uuid,
        entry_channel="max",
        source_channel="max_app",
    )
    max_user_id = f"77{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id, start_payload=portal_token)
    assert response.status_code == 200

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == max_user_id
    assert candidate.messenger_platform == "max"


def test_max_without_invite_starts_public_onboarding(client: TestClient, _isolated_registry: _FakeMaxAdapter):
    max_user_id = f"99{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id)
    assert response.status_code == 200
    assert "пройти первичную анкету" in str(_isolated_registry.calls[-2]["text"]).lower()
    assert "фио" in str(_isolated_registry.calls[-1]["text"]).lower()

    candidate = asyncio.run(_load_candidate_by_max(max_user_id))
    assert candidate is not None
    assert candidate.messenger_platform == "max"
    assert candidate.source == "max_bot_public"


def test_max_with_invalid_invite_still_rejects_link(client: TestClient, _isolated_registry: _FakeMaxAdapter):
    max_user_id = f"66{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id, start_payload="broken-token")
    assert response.status_code == 200
    assert "недействительна" in str(_isolated_registry.calls[-1]["text"]).lower()

    candidate = asyncio.run(_load_candidate_by_max(max_user_id))
    assert candidate is None


def test_max_same_invite_same_user_is_idempotent(client: TestClient, _isolated_registry: _FakeMaxAdapter):
    candidate_uuid = str(uuid4())
    asyncio.run(_seed_candidate(candidate_uuid))
    invite = asyncio.run(create_candidate_invite_token(candidate_uuid, channel="max"))
    max_user_id = f"55{uuid4().hex[:10]}"

    first = _post_bot_started(client, max_user_id=max_user_id, start_payload=invite.token)
    second = _post_bot_started(client, max_user_id=max_user_id, start_payload=invite.token)

    assert first.status_code == 200
    assert second.status_code == 200

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == max_user_id
    assert asyncio.run(_count_candidates_by_uuid(candidate_uuid)) == 1


def test_max_same_invite_different_user_conflicts_without_duplicate_rows(
    client: TestClient,
    _isolated_registry: _FakeMaxAdapter,
):
    candidate_uuid = str(uuid4())
    asyncio.run(_seed_candidate(candidate_uuid))
    invite = asyncio.run(create_candidate_invite_token(candidate_uuid, channel="max"))
    first_user_id = f"44{uuid4().hex[:10]}"
    second_user_id = f"45{uuid4().hex[:10]}"

    assert _post_bot_started(client, max_user_id=first_user_id, start_payload=invite.token).status_code == 200
    response = _post_bot_started(client, max_user_id=second_user_id, start_payload=invite.token)

    assert response.status_code == 200
    assert "уже привязана" in str(_isolated_registry.calls[-1]["text"]).lower()

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == first_user_id
    assert asyncio.run(_count_candidates_by_uuid(candidate_uuid)) == 1
    assert asyncio.run(_load_candidate_by_max(second_user_id)) is None


def test_max_link_does_not_silently_override_telegram_preferred_channel(
    client: TestClient,
    _isolated_registry: _FakeMaxAdapter,
):
    candidate_uuid = str(uuid4())

    async def _seed_telegram_candidate() -> None:
        async with async_session() as session:
            candidate = User(
                candidate_id=candidate_uuid,
                fio="TG linked",
                phone="+79991112233",
                city="Москва",
                source="seed",
                telegram_id=123456789,
                telegram_user_id=123456789,
                telegram_username="tg_linked",
                messenger_platform="telegram",
            )
            session.add(candidate)
            await session.commit()

    asyncio.run(_seed_telegram_candidate())
    invite = asyncio.run(create_candidate_invite_token(candidate_uuid, channel="max"))
    max_user_id = f"33{uuid4().hex[:10]}"

    response = _post_bot_started(client, max_user_id=max_user_id, start_payload=invite.token)
    assert response.status_code == 200

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == max_user_id
    assert candidate.messenger_platform == "telegram"


def test_max_same_user_cannot_claim_another_candidate_invite(
    client: TestClient,
    _isolated_registry: _FakeMaxAdapter,
):
    first_candidate_uuid = str(uuid4())
    second_candidate_uuid = str(uuid4())
    asyncio.run(_seed_candidate(first_candidate_uuid))
    asyncio.run(_seed_candidate(second_candidate_uuid))
    first_invite = asyncio.run(create_candidate_invite_token(first_candidate_uuid, channel="max"))
    second_invite = asyncio.run(create_candidate_invite_token(second_candidate_uuid, channel="max"))
    max_user_id = f"22{uuid4().hex[:10]}"

    assert _post_bot_started(client, max_user_id=max_user_id, start_payload=first_invite.token).status_code == 200
    response = _post_bot_started(client, max_user_id=max_user_id, start_payload=second_invite.token)

    assert response.status_code == 200
    assert "уже связан с другой анкетой" in str(_isolated_registry.calls[-1]["text"]).lower()

    first_candidate = asyncio.run(_load_candidate_by_uuid(first_candidate_uuid))
    second_candidate = asyncio.run(_load_candidate_by_uuid(second_candidate_uuid))
    assert first_candidate is not None
    assert second_candidate is not None
    assert first_candidate.max_user_id == max_user_id
    assert second_candidate.max_user_id is None


def test_max_duplicate_owners_block_start_and_resume_with_explicit_ambiguity(
    client: TestClient,
    _isolated_registry: _FakeMaxAdapter,
):
    max_user_id = f"11{uuid4().hex[:10]}"
    asyncio.run(_seed_candidate(str(uuid4()), max_user_id=max_user_id))
    asyncio.run(_seed_candidate(str(uuid4()), max_user_id=max_user_id))

    started = _post_bot_started(client, max_user_id=max_user_id)
    resumed = _post_callback(client, max_user_id=max_user_id, payload="maxflow:start")

    assert started.status_code == 200
    assert resumed.status_code == 200
    assert "нельзя продолжить автоматически" in str(_isolated_registry.calls[-1]["text"]).lower()
    assert len(asyncio.run(_load_candidates_by_max(max_user_id))) == 2
