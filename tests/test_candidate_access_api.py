from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import backend.apps.admin_ui.services.candidates.lifecycle_use_cases as lifecycle_use_cases
import pytest
from backend.apps.bot.config import TEST2_QUESTIONS, refresh_questions_bank
from backend.core.db import async_session
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessSessionStatus,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySession,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    TestResult,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import (
    Application,
    ApplicationEvent,
    City,
    Recruiter,
    Slot,
    SlotAssignment,
    SlotAssignmentStatus,
    SlotStatus,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select

BOT_TOKEN = "max-candidate-access-test-token"


def _generate_max_init_data(
    *,
    user_id: int,
    bot_token: str = BOT_TOKEN,
    start_param: str | None = "max_launch_ref",
    query_id: str = "query-1",
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
    }
    if start_param is not None:
        payload["start_param"] = start_param

    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    payload["hash"] = hmac.new(
        secret_key,
        launch_params.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(payload)


@pytest.fixture
def candidate_access_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
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


async def _seed_candidate_access_scenario(
    *,
    start_param: str = "max_launch_ref",
    user_id: int = 710001,
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

        slot_start = now + timedelta(days=1)
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=slot_start,
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        next_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=slot_start + timedelta(hours=2),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        session.add_all([slot, next_slot])
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
            "slot_id": slot.id,
            "next_slot_id": next_slot.id,
            "city_id": city.id,
            "recruiter_id": recruiter.id,
        }


async def _seed_contact_bind_candidate(
    *,
    phone: str = "+7 999 222-33-44",
    user_id: int = 710200,
) -> dict[str, int | str]:
    async with async_session() as session:
        next_application_id = int(
            await session.scalar(select(func.coalesce(func.max(Application.id), 0) + 1))
            or 1
        )
        candidate = User(
            fio="Contact Bind Candidate",
            username="contact_bind_candidate",
            phone=phone,
            city="Москва",
            messenger_platform="max",
            source="max",
            candidate_status=CandidateStatus.TEST1_COMPLETED,
        )
        session.add(candidate)
        await session.flush()

        application = Application(
            id=next_application_id,
            candidate_id=int(candidate.id),
            source="max",
            lifecycle_status="new",
        )
        session.add(application)
        await session.flush()
        await session.commit()
        return {
            "candidate_id": int(candidate.id),
            "application_id": int(application.id),
            "phone": phone,
            "user_id": user_id,
        }


async def _latest_access_session(candidate_id: int) -> CandidateAccessSession | None:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateAccessSession)
            .where(CandidateAccessSession.candidate_id == candidate_id)
            .order_by(CandidateAccessSession.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _load_application_events(candidate_id: int) -> list[ApplicationEvent]:
    async with async_session() as session:
        result = await session.execute(
            select(ApplicationEvent)
            .where(ApplicationEvent.candidate_id == candidate_id)
            .order_by(ApplicationEvent.id.asc())
        )
        return list(result.scalars().all())


async def _load_slot(slot_id: int) -> Slot | None:
    async with async_session() as session:
        return await session.get(Slot, slot_id)


async def _load_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _set_candidate_status(candidate_id: int, status: CandidateStatus) -> None:
    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
        assert candidate is not None
        candidate.candidate_status = status
        await session.commit()


async def _seed_intro_day_slot(
    *,
    candidate_id: int,
    recruiter_id: int,
    city_id: int,
) -> int:
    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
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


async def _count_test1_results(candidate_id: int) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(TestResult.id)).where(
                TestResult.user_id == candidate_id,
                func.upper(TestResult.rating) == "TEST1",
            )
        )
        return int(result.scalar_one() or 0)


async def _add_secondary_booking_option(*, recruiter_name: str = "Новосибирск Recruiter") -> dict[str, int]:
    async with async_session() as session:
        city = City(name="Новосибирск", tz="Asia/Novosibirsk", active=True)
        recruiter = Recruiter(name=recruiter_name, tz="Asia/Novosibirsk", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(UTC) + timedelta(days=2),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Asia/Novosibirsk",
        )
        session.add(slot)
        await session.flush()
        await session.commit()
        return {
            "city_id": int(city.id),
            "recruiter_id": int(recruiter.id),
            "slot_id": int(slot.id),
        }


async def _mutate_access_session(
    candidate_id: int,
    mutator,
) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateAccessSession)
            .where(CandidateAccessSession.candidate_id == candidate_id)
            .order_by(CandidateAccessSession.id.desc())
            .limit(1)
        )
        access_session = result.scalar_one()
        await mutator(session, access_session)
        await session.commit()


async def _bump_journey_session_version(candidate_id: int) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateJourneySession)
            .where(CandidateJourneySession.candidate_id == candidate_id)
            .order_by(CandidateJourneySession.id.desc())
            .limit(1)
        )
        journey_session = result.scalar_one()
        journey_session.session_version = int(journey_session.session_version or 1) + 1
        await session.commit()


async def _attach_slot_assignment(
    *,
    slot_id: int,
    recruiter_id: int,
    candidate_public_id: str,
    status: str = SlotAssignmentStatus.OFFERED,
) -> int:
    async with async_session() as session:
        assignment = SlotAssignment(
            slot_id=slot_id,
            recruiter_id=recruiter_id,
            candidate_id=candidate_public_id,
            candidate_tg_id=None,
            candidate_tz="Europe/Moscow",
            origin="candidate_access_test",
            status=status,
        )
        session.add(assignment)
        await session.flush()
        await session.commit()
        return int(assignment.id)


async def _seed_assignment_owned_candidate_scheduling(
    *,
    candidate_id: int,
    recruiter_id: int,
    city_id: int,
) -> int:
    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
        assert candidate is not None

        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            candidate_city_id=city_id,
            start_utc=datetime.now(UTC) + timedelta(days=1, hours=3),
            duration_min=60,
            status=SlotStatus.PENDING,
            purpose="interview",
            tz_name="Europe/Moscow",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=None,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.flush()

        session.add(
            SlotAssignment(
                slot_id=slot.id,
                recruiter_id=recruiter_id,
                candidate_id=candidate.candidate_id,
                candidate_tg_id=None,
                candidate_tz="Europe/Moscow",
                origin="candidate_access_test",
                status=SlotAssignmentStatus.OFFERED,
            )
        )
        await session.commit()
        return int(slot.id)


def _launch_headers(
    client: TestClient,
    *,
    user_id: int,
    start_param: str,
    query_id: str = "query-1",
) -> tuple[dict[str, str], dict]:
    init_data = _generate_max_init_data(
        user_id=user_id,
        start_param=start_param,
        query_id=query_id,
    )
    launch_response = client.post("/api/max/launch", json={"init_data": init_data})
    assert launch_response.status_code == 200
    payload = launch_response.json()
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


def _complete_candidate_test1(
    client: TestClient,
    *,
    headers: dict[str, str],
    answers: dict[str, str] | None = None,
) -> dict:
    questions = client.get("/api/candidate-access/test1", headers=headers)
    assert questions.status_code == 200
    payload = questions.json()
    assert payload["is_completed"] is False
    assert payload["questions"]

    save_response = client.post(
        "/api/candidate-access/test1/answers",
        headers=headers,
        json={"answers": answers or _complete_test1_answers()},
    )
    assert save_response.status_code == 200

    complete_response = client.post("/api/candidate-access/test1/complete", headers=headers)
    assert complete_response.status_code == 200
    return complete_response.json()


def test_candidate_access_me_accepts_valid_max_session(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario())
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == seeded["user_id"]
    assert payload["candidate_id"] == seeded["candidate_id"]
    assert payload["full_name"] == "MAX Candidate"
    assert payload["city_id"] == seeded["city_id"]

    events = asyncio.run(_load_application_events(seeded["candidate_id"]))
    assert len(events) == 1
    assert events[0].event_type == "candidate.access_link.launched"


def test_candidate_access_journey_returns_session_envelope(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="journey_ref", user_id=710002))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
        query_id="journey-query",
    )

    response = candidate_access_client.get("/api/candidate-access/journey", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["candidate_id"] == seeded["candidate_id"]
    assert payload["session"]["journey_key"] == "candidate_portal"
    assert payload["session"]["journey_version"] == "v1"
    assert payload["session"]["current_step_key"] == "profile"
    assert payload["session"]["last_surface"] == "max_miniapp"
    assert payload["session"]["last_auth_method"] == "max_init_data"
    assert payload["session"]["session_version"] >= 1
    assert payload["active_booking"] is None


def test_candidate_access_test1_returns_questionnaire(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="test1_ref", user_id=710020))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    response = candidate_access_client.get("/api/candidate-access/test1", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    question_ids = [item["id"] for item in payload["questions"]]
    assert question_ids[:3] == ["fio", "city", "age"]
    assert payload["draft_answers"] == {}
    assert payload["is_completed"] is False


def test_candidate_access_test1_answers_persist_draft(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="test1_answers_ref", user_id=710021))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    response = candidate_access_client.post(
        "/api/candidate-access/test1/answers",
        headers=headers,
        json={"answers": {"fio": "Иванов Иван Иванович", "city": "Москва", "age": "23"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["journey_step"] == "test1"
    assert payload["draft_answers"]["fio"] == "Иванов Иван Иванович"
    assert payload["draft_answers"]["city"] == "Москва"
    assert payload["draft_answers"]["age"] == "23"
    assert payload["is_completed"] is False

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.fio == "Иванов Иван Иванович"
    assert candidate.city == "Москва"

    journey = candidate_access_client.get("/api/candidate-access/journey", headers=headers)
    assert journey.status_code == 200
    assert journey.json()["session"]["current_step_key"] == "test1"


def test_candidate_access_test1_complete_returns_screening_decision_and_offer(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="test1_complete_ref", user_id=710022))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    payload = _complete_candidate_test1(candidate_access_client, headers=headers)

    assert payload["is_completed"] is True
    assert payload["journey_step"] == "booking"
    assert payload["screening_decision"]["outcome"] == "invite_to_interview"
    assert payload["screening_decision"]["required_next_action"] == "select_interview_slot"
    assert payload["required_next_action"] == "select_interview_slot"
    assert payload["interview_offer"] is not None
    assert payload["interview_offer"]["candidate_id"] == seeded["candidate_id"]
    assert payload["interview_offer"]["application_id"] is None


def test_candidate_access_test1_complete_is_idempotent(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="test1_idempotent_ref", user_id=710023))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    first = _complete_candidate_test1(candidate_access_client, headers=headers)
    second = candidate_access_client.post("/api/candidate-access/test1/complete", headers=headers)

    assert second.status_code == 200
    assert second.json()["is_completed"] is True
    assert second.json()["screening_decision"] == first["screening_decision"]
    assert second.json()["interview_offer"] == first["interview_offer"]


def test_candidate_access_test1_can_be_restarted_and_completed_again(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="test1_restart_ref", user_id=710123))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    first = _complete_candidate_test1(candidate_access_client, headers=headers)
    assert first["is_completed"] is True
    first_me = candidate_access_client.get("/api/candidate-access/me", headers=headers)
    assert first_me.status_code == 200

    restart = asyncio.run(
        lifecycle_use_cases.execute_restart_test1(
            int(seeded["candidate_id"]),
            principal=None,
            action_key="restart_test1",
            reason="candidate_reapplied",
        )
    )
    assert restart.ok is True
    assert restart.status == CandidateStatus.INVITED.value

    stale_me = candidate_access_client.get("/api/candidate-access/me", headers=headers)
    assert stale_me.status_code == 409
    assert stale_me.json()["detail"]["code"] == "stale_session_version"

    new_headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
        query_id="query-2",
    )
    questionnaire = candidate_access_client.get("/api/candidate-access/test1", headers=new_headers)
    assert questionnaire.status_code == 200
    assert questionnaire.json()["is_completed"] is False

    second = _complete_candidate_test1(candidate_access_client, headers=new_headers)
    assert second["is_completed"] is True
    assert asyncio.run(_count_test1_results(int(seeded["candidate_id"]))) == 2

    detail = asyncio.run(lifecycle_use_cases.get_candidate_detail(int(seeded["candidate_id"]), principal=None))
    assert detail is not None
    assert detail["test_sections_map"]["test1"]["history"]
    assert len(detail["test_sections_map"]["test1"]["history"]) == 2


def test_candidate_access_test1_complete_can_require_clarification(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="test1_clarify_ref", user_id=710024))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    answers = _complete_test1_answers()
    answers["format"] = "Нужен гибкий график"

    payload = _complete_candidate_test1(candidate_access_client, headers=headers, answers=answers)

    assert payload["is_completed"] is True
    assert payload["journey_step"] == "test1_completed"
    assert payload["screening_decision"]["outcome"] == "ask_clarification"
    assert payload["screening_decision"]["required_next_action"] == "ask_candidate"
    assert payload["interview_offer"] is None


def test_candidate_access_slots_require_screening_invite(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="slots_gate_ref", user_id=710025))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    response = candidate_access_client.get(
        "/api/candidate-access/slots",
        headers=headers,
        params={"city_id": seeded["city_id"]},
    )

    assert response.status_code == 409
    assert "test1 screening" in response.json()["detail"].lower()


def test_candidate_access_slots_lists_interview_slots(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="slots_ref", user_id=710003))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    response = candidate_access_client.get(
        "/api/candidate-access/slots",
        headers=headers,
        params={"city_id": seeded["city_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    slot_ids = {entry["slot_id"] for entry in payload}
    assert seeded["slot_id"] in slot_ids
    assert seeded["next_slot_id"] in slot_ids


def test_candidate_access_lists_booking_cities_and_recruiters(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="cities_ref", user_id=710203))
    secondary = asyncio.run(_add_secondary_booking_option())
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    cities = candidate_access_client.get("/api/candidate-access/cities", headers=headers)
    assert cities.status_code == 200
    city_payload = cities.json()
    assert any(item["city_id"] == seeded["city_id"] and item["available_slots"] >= 2 for item in city_payload)
    assert any(item["city_id"] == secondary["city_id"] and item["available_recruiters"] >= 1 for item in city_payload)

    recruiters = candidate_access_client.get(
        "/api/candidate-access/recruiters",
        headers=headers,
        params={"city_id": seeded["city_id"]},
    )
    assert recruiters.status_code == 200
    recruiter_payload = recruiters.json()
    assert recruiter_payload
    assert recruiter_payload[0]["city_id"] == seeded["city_id"]
    assert recruiter_payload[0]["available_slots"] >= 1
    assert recruiter_payload[0]["recruiter_name"] == "MAX Recruiter"

    secondary_recruiters = candidate_access_client.get(
        "/api/candidate-access/recruiters",
        headers=headers,
        params={"city_id": secondary["city_id"]},
    )
    assert secondary_recruiters.status_code == 200
    secondary_payload = secondary_recruiters.json()
    assert secondary_payload
    assert all(item["city_id"] == secondary["city_id"] for item in secondary_payload)
    assert all(item["available_slots"] >= 1 for item in secondary_payload)


def test_candidate_access_booking_context_prefills_from_test1_and_persists_selection(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="context_ref", user_id=710204))
    secondary = asyncio.run(_add_secondary_booking_option())
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    prefill = candidate_access_client.get("/api/candidate-access/booking-context", headers=headers)
    assert prefill.status_code == 200
    assert prefill.json()["city_id"] == seeded["city_id"]
    assert prefill.json()["is_explicit"] is False

    saved = candidate_access_client.post(
        "/api/candidate-access/booking-context",
        headers=headers,
        json={"city_id": secondary["city_id"], "recruiter_id": secondary["recruiter_id"]},
    )
    assert saved.status_code == 200
    assert saved.json()["city_id"] == secondary["city_id"]
    assert saved.json()["recruiter_id"] == secondary["recruiter_id"]
    assert saved.json()["is_explicit"] is True

    restored = candidate_access_client.get("/api/candidate-access/booking-context", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["city_id"] == secondary["city_id"]
    assert restored.json()["recruiter_id"] == secondary["recruiter_id"]


def test_candidate_access_slots_require_explicit_city_filter(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="slots_city_ref", user_id=710205))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    response = candidate_access_client.get("/api/candidate-access/slots", headers=headers)

    assert response.status_code == 409
    assert "choose a city" in response.json()["detail"].lower()


def test_candidate_access_slots_lists_interview_slots_for_city_and_recruiter(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="slots_ref", user_id=710003))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    context = candidate_access_client.post(
        "/api/candidate-access/booking-context",
        headers=headers,
        json={"city_id": seeded["city_id"], "recruiter_id": seeded["recruiter_id"]},
    )
    assert context.status_code == 200
    assert context.json()["city_id"] == seeded["city_id"]
    assert context.json()["recruiter_id"] == seeded["recruiter_id"]

    response = candidate_access_client.get(
        "/api/candidate-access/slots",
        headers=headers,
        params={"city_id": seeded["city_id"], "recruiter_id": seeded["recruiter_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert {entry["slot_id"] for entry in payload} == {seeded["slot_id"], seeded["next_slot_id"]}
    assert all(entry["city_id"] == seeded["city_id"] for entry in payload)
    assert all(entry["recruiter_id"] == seeded["recruiter_id"] for entry in payload)


def test_candidate_access_manual_availability_activates_draft_and_updates_journey(
    candidate_access_client,
    monkeypatch: pytest.MonkeyPatch,
):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="manual_availability_ref", user_id=710206))

    async def _mark_candidate_draft() -> None:
        async with async_session() as session:
            candidate = await session.get(User, int(seeded["candidate_id"]))
            assert candidate is not None
            candidate.lifecycle_state = "draft"
            await session.commit()

    asyncio.run(_mark_candidate_draft())
    monkeypatch.setattr(
        "backend.apps.admin_api.candidate_access.services.notify_recruiters_manual_availability",
        AsyncMock(return_value=True),
    )

    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    response = candidate_access_client.post(
        "/api/candidate-access/manual-availability",
        headers=headers,
        json={
            "note": "Удобно по будням после 18:00",
            "timezone_label": "Europe/Moscow",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "submitted"
    assert payload["recruiters_notified"] is True

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.lifecycle_state == "active"
    assert candidate.manual_slot_comment == "Удобно по будням после 18:00"
    assert candidate.manual_slot_response_at is not None
    assert candidate.candidate_status == CandidateStatus.WAITING_SLOT

    journey = candidate_access_client.get("/api/candidate-access/journey", headers=headers)
    assert journey.status_code == 200
    journey_payload = journey.json()
    assert journey_payload["status_card"]["title"] == "Пожелания по времени отправлены"
    assert journey_payload["primary_action"]["kind"] == "chat"


def test_candidate_access_me_exposes_test1_completed_status(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="me_status_ref", user_id=710103))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == CandidateStatus.TEST1_COMPLETED


def test_candidate_access_booking_creates_pending_booking(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="booking_ref", user_id=710004))
    secondary = asyncio.run(_add_secondary_booking_option())
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    context = candidate_access_client.post(
        "/api/candidate-access/booking-context",
        headers=headers,
        json={"city_id": secondary["city_id"], "recruiter_id": secondary["recruiter_id"]},
    )
    assert context.status_code == 200

    response = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": secondary["slot_id"]},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["slot_id"] == secondary["slot_id"]
    assert payload["candidate_id"] == seeded["candidate_id"]
    assert payload["status"] == SlotStatus.PENDING

    slot = asyncio.run(_load_slot(int(secondary["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING
    assert slot.candidate_id == seeded["candidate_public_id"]
    assert slot.candidate_tg_id is None

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.city == "Новосибирск"
    assert candidate.responsible_recruiter_id == secondary["recruiter_id"]


def test_candidate_access_journey_returns_active_booking_after_booking_created(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="journey_booking_ref", user_id=710104))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    booking = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )
    assert booking.status_code == 201

    response = candidate_access_client.get("/api/candidate-access/journey", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["status"] == CandidateStatus.SLOT_PENDING
    assert payload["active_booking"] is not None
    assert payload["active_booking"]["booking_id"] == seeded["slot_id"]
    assert payload["active_booking"]["status"] == SlotStatus.PENDING


def test_candidate_access_booking_blocks_assignment_owned_scheduling(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="assignment_booking_ref", user_id=710105))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    asyncio.run(
        _seed_assignment_owned_candidate_scheduling(
            candidate_id=int(seeded["candidate_id"]),
            recruiter_id=int(seeded["recruiter_id"]),
            city_id=int(seeded["city_id"]),
        )
    )

    response = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )

    assert response.status_code == 409
    assert "slotassignment" in response.json()["detail"].lower()

    free_slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert free_slot is not None
    assert free_slot.status == SlotStatus.FREE


def test_candidate_access_confirm_confirms_owned_booking(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="confirm_ref", user_id=710005))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    booking = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )
    assert booking.status_code == 201

    response = candidate_access_client.post(
        f"/api/candidate-access/bookings/{seeded['slot_id']}/confirm",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == SlotStatus.CONFIRMED_BY_CANDIDATE

    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE


def test_candidate_access_confirm_blocks_assignment_owned_scheduling(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="assignment_confirm_ref", user_id=710106))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    booking = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )
    assert booking.status_code == 201
    asyncio.run(
        _attach_slot_assignment(
            slot_id=int(seeded["slot_id"]),
            recruiter_id=int(seeded["recruiter_id"]),
            candidate_public_id=str(seeded["candidate_public_id"]),
        )
    )

    response = candidate_access_client.post(
        f"/api/candidate-access/bookings/{seeded['slot_id']}/confirm",
        headers=headers,
    )

    assert response.status_code == 409
    assert "slotassignment" in response.json()["detail"].lower()

    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING


def test_candidate_access_reschedule_moves_owned_booking(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="reschedule_ref", user_id=710006))
    secondary = asyncio.run(_add_secondary_booking_option())
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    context = candidate_access_client.post(
        "/api/candidate-access/booking-context",
        headers=headers,
        json={"city_id": seeded["city_id"], "recruiter_id": seeded["recruiter_id"]},
    )
    assert context.status_code == 200
    booking = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )
    assert booking.status_code == 201

    switched_context = candidate_access_client.post(
        "/api/candidate-access/booking-context",
        headers=headers,
        json={"city_id": secondary["city_id"], "recruiter_id": secondary["recruiter_id"]},
    )
    assert switched_context.status_code == 200

    response = candidate_access_client.post(
        f"/api/candidate-access/bookings/{seeded['slot_id']}/reschedule",
        headers=headers,
        json={"new_slot_id": secondary["slot_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["slot_id"] == secondary["slot_id"]
    assert payload["status"] == SlotStatus.PENDING

    old_slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    new_slot = asyncio.run(_load_slot(int(secondary["slot_id"])))
    assert old_slot is not None
    assert new_slot is not None
    assert old_slot.status == SlotStatus.FREE
    assert old_slot.candidate_id is None
    assert new_slot.status == SlotStatus.PENDING
    assert new_slot.candidate_id == seeded["candidate_public_id"]

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.city == "Новосибирск"
    assert candidate.responsible_recruiter_id == secondary["recruiter_id"]


def test_candidate_access_reschedule_blocks_assignment_owned_scheduling(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="assignment_reschedule_ref", user_id=710107))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    booking = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )
    assert booking.status_code == 201
    asyncio.run(
        _attach_slot_assignment(
            slot_id=int(seeded["slot_id"]),
            recruiter_id=int(seeded["recruiter_id"]),
            candidate_public_id=str(seeded["candidate_public_id"]),
        )
    )

    response = candidate_access_client.post(
        f"/api/candidate-access/bookings/{seeded['slot_id']}/reschedule",
        headers=headers,
        json={"new_slot_id": seeded["next_slot_id"]},
    )

    assert response.status_code == 409
    assert "slotassignment" in response.json()["detail"].lower()

    old_slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    new_slot = asyncio.run(_load_slot(int(seeded["next_slot_id"])))
    assert old_slot is not None
    assert new_slot is not None
    assert old_slot.status == SlotStatus.PENDING
    assert old_slot.candidate_id == seeded["candidate_public_id"]
    assert new_slot.status == SlotStatus.FREE
    assert new_slot.candidate_id is None


def test_candidate_access_cancel_releases_owned_booking(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="cancel_ref", user_id=710007))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    booking = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )
    assert booking.status_code == 201

    response = candidate_access_client.post(
        f"/api/candidate-access/bookings/{seeded['slot_id']}/cancel",
        headers=headers,
        json={"reason": "changed_mind"},
    )

    assert response.status_code == 204
    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.FREE
    assert slot.candidate_id is None
    assert slot.candidate_tg_id is None


def test_candidate_access_cancel_blocks_assignment_owned_scheduling(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="assignment_cancel_ref", user_id=710108))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)
    booking = candidate_access_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": seeded["slot_id"]},
    )
    assert booking.status_code == 201
    asyncio.run(
        _attach_slot_assignment(
            slot_id=int(seeded["slot_id"]),
            recruiter_id=int(seeded["recruiter_id"]),
            candidate_public_id=str(seeded["candidate_public_id"]),
        )
    )

    response = candidate_access_client.post(
        f"/api/candidate-access/bookings/{seeded['slot_id']}/cancel",
        headers=headers,
        json={"reason": "managed_elsewhere"},
    )

    assert response.status_code == 409
    assert "slotassignment" in response.json()["detail"].lower()

    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING
    assert slot.candidate_id == seeded["candidate_public_id"]


def test_candidate_access_rejects_invalid_init_data(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="invalid_ref", user_id=710008))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    headers["X-Max-Init-Data"] = "not-a-valid-init-data"

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_init_data"


def test_candidate_access_rejects_provider_user_id_mismatch(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="identity_ref", user_id=710009))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
        query_id="identity-query",
    )
    headers["X-Max-Init-Data"] = _generate_max_init_data(
        user_id=710099,
        start_param=str(seeded["start_param"]),
        query_id="identity-query",
    )

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "identity_mismatch"


def test_candidate_access_rejects_provider_session_mismatch(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="provider_ref", user_id=710010))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
        query_id="provider-query",
    )
    headers["X-Max-Init-Data"] = _generate_max_init_data(
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
        query_id="other-query",
    )

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "provider_session_mismatch"


def test_candidate_access_rejects_expired_session(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="expired_ref", user_id=710011))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    asyncio.run(
        _mutate_access_session(
            int(seeded["candidate_id"]),
            lambda _session, access_session: _expire_access_session(access_session),
        )
    )

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "candidate_access_session_expired"


def test_candidate_access_rejects_revoked_session(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="revoked_ref", user_id=710012))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    asyncio.run(
        _mutate_access_session(
            int(seeded["candidate_id"]),
            lambda _session, access_session: _revoke_access_session(access_session),
        )
    )

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "candidate_access_session_revoked"


def test_candidate_access_rejects_stale_session_version(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="stale_ref", user_id=710013))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    asyncio.run(_bump_journey_session_version(int(seeded["candidate_id"])))

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_session_version"


def test_candidate_access_rejects_numeric_db_session_id_as_credential(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="numeric_ref", user_id=710014))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    access_session = asyncio.run(_latest_access_session(int(seeded["candidate_id"])))
    assert access_session is not None
    headers["X-Candidate-Access-Session"] = str(access_session.id)

    response = candidate_access_client.get("/api/candidate-access/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "candidate_access_session_not_found"


def test_candidate_access_contact_binds_candidate_and_allows_relaunch(candidate_access_client):
    seeded = asyncio.run(_seed_contact_bind_candidate())
    init_data = _generate_max_init_data(
        user_id=int(seeded["user_id"]),
        start_param=None,
        query_id="contact-bind-query",
    )

    bind_response = candidate_access_client.post(
        "/api/candidate-access/contact",
        json={"phone": seeded["phone"]},
        headers={"X-Max-Init-Data": init_data},
    )

    assert bind_response.status_code == 200
    bind_payload = bind_response.json()
    assert bind_payload["status"] == "bound"
    assert bind_payload["start_param"]

    launch_response = candidate_access_client.post(
        "/api/max/launch",
        json={
            "init_data": _generate_max_init_data(
                user_id=int(seeded["user_id"]),
                start_param=bind_payload["start_param"],
                query_id="contact-bind-launch",
            ),
            "start_param": bind_payload["start_param"],
        },
    )

    assert launch_response.status_code == 200
    launch_payload = launch_response.json()
    assert launch_payload["binding"]["status"] == "bound"
    assert launch_payload["candidate"]["id"] == int(seeded["candidate_id"])


def test_candidate_access_contact_requires_manual_review_when_phone_not_found(candidate_access_client):
    init_data = _generate_max_init_data(
        user_id=710201,
        start_param=None,
        query_id="contact-bind-not-found",
    )

    response = candidate_access_client.post(
        "/api/candidate-access/contact",
        json={"phone": "+7 999 000-00-01"},
        headers={"X-Max-Init-Data": init_data},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual_review_required"
    assert payload["start_param"] is None


def test_candidate_access_contact_requires_manual_review_when_phone_matches_multiple_candidates(candidate_access_client):
    asyncio.run(_seed_contact_bind_candidate(phone="+7 999 222-33-55", user_id=710202))
    asyncio.run(_seed_contact_bind_candidate(phone="+7 999 222-33-55", user_id=710203))
    init_data = _generate_max_init_data(
        user_id=710204,
        start_param=None,
        query_id="contact-bind-multiple",
    )

    response = candidate_access_client.post(
        "/api/candidate-access/contact",
        json={"phone": "+7 999 222-33-55"},
        headers={"X-Max-Init-Data": init_data},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual_review_required"
    assert payload["start_param"] is None


def test_candidate_access_contact_requires_manual_review_for_identity_mismatch(candidate_access_client):
    seeded = asyncio.run(_seed_contact_bind_candidate(phone="+7 999 222-33-66", user_id=710205))

    async def _bind_other_max_identity() -> None:
        async with async_session() as session:
            candidate = await session.get(User, int(seeded["candidate_id"]))
            assert candidate is not None
            candidate.max_user_id = "other-max-user"
            await session.commit()

    asyncio.run(_bind_other_max_identity())
    init_data = _generate_max_init_data(
        user_id=710206,
        start_param=None,
        query_id="contact-bind-identity-mismatch",
    )

    response = candidate_access_client.post(
        "/api/candidate-access/contact",
        json={"phone": seeded["phone"]},
        headers={"X-Max-Init-Data": init_data},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual_review_required"
    assert payload["start_param"] is None


def test_candidate_access_contact_requires_manual_review_for_ambiguous_application_context(candidate_access_client):
    seeded = asyncio.run(_seed_contact_bind_candidate(phone="+7 999 222-33-77", user_id=710207))

    async def _add_second_active_application() -> None:
        async with async_session() as session:
            next_application_id = int(
                await session.scalar(select(func.coalesce(func.max(Application.id), 0) + 1))
                or 1
            )
            application = Application(
                id=next_application_id,
                candidate_id=int(seeded["candidate_id"]),
                source="max",
                lifecycle_status="test1_pending",
            )
            session.add(application)
            await session.commit()

    asyncio.run(_add_second_active_application())
    init_data = _generate_max_init_data(
        user_id=710208,
        start_param=None,
        query_id="contact-bind-ambiguous-application",
    )

    response = candidate_access_client.post(
        "/api/candidate-access/contact",
        json={"phone": seeded["phone"]},
        headers={"X-Max-Init-Data": init_data},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual_review_required"
    assert payload["start_param"] is None


def test_candidate_access_manual_availability_returns_degraded_notification_flag_on_notifier_failure(
    candidate_access_client,
    monkeypatch: pytest.MonkeyPatch,
):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="manual_availability_notify_fail", user_id=710209))

    async def _mark_candidate_draft() -> None:
        async with async_session() as session:
            candidate = await session.get(User, int(seeded["candidate_id"]))
            assert candidate is not None
            candidate.lifecycle_state = "draft"
            await session.commit()

    asyncio.run(_mark_candidate_draft())
    monkeypatch.setattr(
        "backend.apps.admin_api.candidate_access.services.notify_recruiters_manual_availability",
        AsyncMock(side_effect=RuntimeError("max notify down")),
    )

    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )
    _complete_candidate_test1(candidate_access_client, headers=headers)

    response = candidate_access_client.post(
        "/api/candidate-access/manual-availability",
        headers=headers,
        json={
            "note": "Удобно завтра после 19:00",
            "timezone_label": "Europe/Moscow",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "submitted"
    assert payload["recruiters_notified"] is False

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.lifecycle_state == "active"
    assert candidate.candidate_status == CandidateStatus.WAITING_SLOT


def test_candidate_access_test2_loads_and_completes_for_max_candidate(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="phase2-test2", user_id=710210))
    asyncio.run(_set_candidate_status(int(seeded["candidate_id"]), CandidateStatus.TEST2_SENT))
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    initial = candidate_access_client.get("/api/candidate-access/test2", headers=headers)

    assert initial.status_code == 200
    payload = initial.json()
    assert payload["is_completed"] is False
    assert payload["current_question_index"] == 0
    assert payload["questions"]

    refresh_questions_bank()
    total_questions = int(payload["total_questions"])
    response_payload = payload
    for _ in range(total_questions):
        question_index = int(response_payload["current_question_index"])
        answer_index = int(TEST2_QUESTIONS[question_index]["correct"])
        response = candidate_access_client.post(
            "/api/candidate-access/test2/answers",
            headers=headers,
            json={"question_index": question_index, "answer_index": answer_index},
        )
        assert response.status_code == 200
        response_payload = response.json()

    completed_payload = response_payload
    assert completed_payload["is_completed"] is True
    assert completed_payload["required_next_action"] in {"wait_intro_day_invitation", "await_manual_review"}

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.candidate_status in {CandidateStatus.TEST2_COMPLETED, CandidateStatus.TEST2_FAILED}


def test_candidate_access_intro_day_loads_and_confirms_for_max_candidate(candidate_access_client):
    seeded = asyncio.run(_seed_candidate_access_scenario(start_param="phase2-intro-day", user_id=710211))
    asyncio.run(_set_candidate_status(int(seeded["candidate_id"]), CandidateStatus.INTRO_DAY_SCHEDULED))
    slot_id = asyncio.run(
        _seed_intro_day_slot(
            candidate_id=int(seeded["candidate_id"]),
            recruiter_id=int(seeded["recruiter_id"]),
            city_id=int(seeded["city_id"]),
        )
    )
    headers, _ = _launch_headers(
        candidate_access_client,
        user_id=int(seeded["user_id"]),
        start_param=str(seeded["start_param"]),
    )

    initial = candidate_access_client.get("/api/candidate-access/intro-day", headers=headers)

    assert initial.status_code == 200
    payload = initial.json()
    assert payload["booking_id"] == slot_id
    assert payload["address"] == "ул. Пример, 1"
    assert "Ирина" in str(payload["contact_name"] or payload["intro_contact"])

    confirmed = candidate_access_client.post("/api/candidate-access/intro-day/confirm", headers=headers)

    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()
    assert confirmed_payload["booking_id"] == slot_id
    assert confirmed_payload["status"] in {"confirmed", "confirmed_by_candidate"}

async def _expire_access_session(access_session: CandidateAccessSession) -> None:
    access_session.status = CandidateAccessSessionStatus.ACTIVE.value
    access_session.expires_at = datetime.now(UTC) - timedelta(minutes=1)


async def _revoke_access_session(access_session: CandidateAccessSession) -> None:
    access_session.status = CandidateAccessSessionStatus.REVOKED.value
    access_session.revoked_at = datetime.now(UTC)
