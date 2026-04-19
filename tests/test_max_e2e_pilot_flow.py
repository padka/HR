from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import pytest
from backend.apps.admin_api.candidate_access.auth import (
    CANDIDATE_ACCESS_SESSION_HEADER,
    MAX_INIT_DATA_HEADER,
)
from backend.apps.admin_ui.security import Principal
from backend.apps.admin_ui.services.candidates import (
    api_candidate_detail_payload,
    list_candidates,
)
from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySession,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import Application
from fastapi.testclient import TestClient
from sqlalchemy import func, select

BOT_TOKEN = "max-e2e-test-token"


def _generate_max_init_data(
    *,
    user_id: int,
    bot_token: str = BOT_TOKEN,
    start_param: str,
    query_id: str = "max-e2e-query",
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


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


@pytest.fixture
def max_api_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_INTEGRATION_ENABLED", "0")
    monkeypatch.setenv("MAX_ADAPTER_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/max")
    monkeypatch.setenv("TEST1_SCREENING_DECISION_ENABLED", "1")
    monkeypatch.setenv("AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED", "1")
    monkeypatch.setenv(
        "SESSION_SECRET",
        "test-session-secret-0123456789abcdef0123456789abcd",
    )
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")

    from backend.apps.admin_api.main import create_app

    settings_module.get_settings.cache_clear()
    app = create_app()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings_module.get_settings.cache_clear()


async def _next_sqlite_pk(session, model_cls) -> int | None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return None
    next_id = await session.scalar(select(func.coalesce(func.max(model_cls.id), 0) + 1))
    return int(next_id or 1)


async def _seed_max_candidate_context(
    *,
    user_id: int,
    start_param: str,
    stage_step: str,
    candidate_status: CandidateStatus,
    application_status: str,
    slot_offsets_hours: tuple[int, ...] = (),
    link_telegram: bool = True,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(
            name=f"MAX Recruiter {user_id}",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=user_id + 5000,
        )
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        candidate = User(
            fio=f"MAX Candidate {user_id}",
            city=city.name,
            source="max",
            messenger_platform="max",
            max_user_id=str(user_id),
            telegram_id=user_id if link_telegram else None,
            telegram_user_id=user_id if link_telegram else None,
            username=f"max_candidate_{user_id}",
            candidate_status=candidate_status,
        )
        session.add(candidate)
        await session.flush()

        application = Application(
            id=await _next_sqlite_pk(session, Application),
            candidate_id=candidate.id,
            source="max",
            lifecycle_status=application_status,
            recruiter_id=recruiter.id,
        )
        session.add(application)
        await session.flush()

        journey_session = CandidateJourneySession(
            candidate_id=candidate.id,
            application_id=application.id,
            entry_channel=CandidateLaunchChannel.MAX.value,
            current_step_key=stage_step,
            last_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            last_auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            last_activity_at=now,
        )
        session.add(journey_session)
        await session.flush()

        launch_token = CandidateAccessToken(
            id=await _next_sqlite_pk(session, CandidateAccessToken),
            token_hash=hashlib.sha256(f"token:{start_param}".encode()).hexdigest(),
            candidate_id=candidate.id,
            application_id=application.id,
            journey_session_id=journey_session.id,
            token_kind=CandidateAccessTokenKind.LAUNCH.value,
            journey_surface=CandidateJourneySurface.MAX_MINIAPP.value,
            auth_method=CandidateAccessAuthMethod.MAX_INIT_DATA.value,
            launch_channel=CandidateLaunchChannel.MAX.value,
            start_param=start_param,
            provider_user_id=str(user_id),
            expires_at=now + timedelta(hours=1),
        )
        session.add(launch_token)
        await session.flush()

        slot_ids: list[int] = []
        for offset_hours in slot_offsets_hours:
            slot = models.Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=now + timedelta(hours=offset_hours),
                duration_min=60,
                status=models.SlotStatus.FREE,
                purpose="interview",
                tz_name="Europe/Moscow",
            )
            session.add(slot)
            await session.flush()
            slot_ids.append(int(slot.id))

        await session.commit()
        return {
            "candidate_id": int(candidate.id),
            "candidate_public_id": candidate.candidate_id,
            "telegram_id": user_id if link_telegram else None,
            "provider_user_id": user_id,
            "application_id": int(application.id),
            "city_id": int(city.id),
            "city_name": city.name,
            "recruiter_id": int(recruiter.id),
            "journey_session_id": int(journey_session.id),
            "slot_ids": slot_ids,
            "start_param": start_param,
        }


def _launch_candidate_access(
    client: TestClient,
    *,
    user_id: int,
    start_param: str,
    query_id: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    init_data = _generate_max_init_data(
        user_id=user_id,
        start_param=start_param,
        query_id=query_id,
    )
    response = client.post("/api/max/launch", json={"init_data": init_data})
    assert response.status_code == 200
    payload = response.json()
    headers = {
        CANDIDATE_ACCESS_SESSION_HEADER: payload["session"]["session_id"],
        MAX_INIT_DATA_HEADER: init_data,
    }
    return headers, payload


async def _load_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _load_slot(slot_id: int) -> models.Slot | None:
    async with async_session() as session:
        return await session.get(models.Slot, slot_id)


async def _load_access_session(candidate_id: int) -> CandidateAccessSession | None:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateAccessSession)
            .where(CandidateAccessSession.candidate_id == candidate_id)
            .order_by(CandidateAccessSession.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _complete_test1_answers() -> dict[str, str]:
    return {
        "fio": "Иванов Иван Иванович",
        "city": "MAX City",
        "age": "24",
        "status": "Ищу работу",
        "notice_period": "Готов выйти в ближайшие 2 дня.",
        "salary": "60 000 – 90 000 ›",
        "format": "Да, готов",
        "sales_exp": "Есть опыт переговоров и работы с клиентами.",
        "about": "Хочу расти и зарабатывать.",
        "skills": "Коммуникация и дисциплина.",
        "expectations": "Прозрачный доход и сильная команда.",
    }


def _complete_test1_over_http(
    client: TestClient,
    *,
    headers: dict[str, str],
    city_name: str,
) -> dict[str, Any]:
    questions_response = client.get("/api/candidate-access/test1", headers=headers)
    assert questions_response.status_code == 200
    assert questions_response.json()["journey_step"] == "test1"

    answers = _complete_test1_answers()
    answers["city"] = city_name
    save_response = client.post(
        "/api/candidate-access/test1/answers",
        headers=headers,
        json={"answers": answers},
    )
    assert save_response.status_code == 200, save_response.text

    complete_response = client.post("/api/candidate-access/test1/complete", headers=headers)
    assert complete_response.status_code == 200
    return complete_response.json()


@pytest.mark.asyncio
async def test_max_e2e_pilot_flow_tracks_launch_test1_screening_and_slots_over_http(
    max_api_client,
):
    context = await _seed_max_candidate_context(
        user_id=711001,
        start_param="max-e2e-test1-screening",
        stage_step="test1",
        candidate_status=CandidateStatus.INVITED,
        application_status="test1_pending",
        slot_offsets_hours=(24, 30),
    )

    headers, launch_payload = _launch_candidate_access(
        max_api_client,
        user_id=int(context["telegram_id"]),
        start_param=str(context["start_param"]),
        query_id="max-e2e-test1-screening-query",
    )

    assert launch_payload["candidate"]["application_id"] == context["application_id"]
    assert "provider" not in launch_payload
    assert "start_param" not in launch_payload

    me_response = max_api_client.get("/api/candidate-access/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["status"] == CandidateStatus.INVITED.value

    test1_journey = max_api_client.get("/api/candidate-access/journey", headers=headers)
    assert test1_journey.status_code == 200
    assert test1_journey.json()["session"]["current_step_key"] == "test1"
    assert test1_journey.json()["active_booking"] is None

    test1_payload = _complete_test1_over_http(
        max_api_client,
        headers=headers,
        city_name=str(context["city_name"]),
    )
    assert test1_payload["is_completed"] is True
    assert test1_payload["journey_step"] == "booking"
    assert test1_payload["screening_decision"]["outcome"] == "invite_to_interview"
    assert test1_payload["screening_decision"]["required_next_action"] == "select_interview_slot"
    assert test1_payload["interview_offer"] is not None
    assert test1_payload["interview_offer"]["application_id"] == context["application_id"]

    waiting_slot_me = max_api_client.get("/api/candidate-access/me", headers=headers)
    assert waiting_slot_me.status_code == 200
    assert waiting_slot_me.json()["status"] == CandidateStatus.WAITING_SLOT.value

    slots_response = max_api_client.get(
        "/api/candidate-access/slots",
        headers=headers,
        params={"city_id": context["city_id"]},
    )
    assert slots_response.status_code == 200
    slot_ids = {item["slot_id"] for item in slots_response.json()}
    assert set(context["slot_ids"]).issubset(slot_ids)

    access_session = await _load_access_session(int(context["candidate_id"]))
    assert access_session is not None
    assert access_session.application_id == context["application_id"]


@pytest.mark.asyncio
async def test_max_e2e_pilot_flow_books_and_confirms_via_candidate_access_http(
    max_api_client,
):
    context = await _seed_max_candidate_context(
        user_id=711002,
        start_param="max-e2e-confirm",
        stage_step="test1",
        candidate_status=CandidateStatus.INVITED,
        application_status="test1_pending",
        slot_offsets_hours=(24, 48),
    )
    first_slot_id = int(context["slot_ids"][0])

    headers, _ = _launch_candidate_access(
        max_api_client,
        user_id=int(context["telegram_id"]),
        start_param=str(context["start_param"]),
        query_id="max-e2e-confirm-query",
    )
    complete_payload = _complete_test1_over_http(
        max_api_client,
        headers=headers,
        city_name=str(context["city_name"]),
    )
    assert complete_payload["screening_decision"]["outcome"] == "invite_to_interview"

    slots_response = max_api_client.get(
        "/api/candidate-access/slots",
        headers=headers,
        params={"city_id": context["city_id"]},
    )
    assert slots_response.status_code == 200
    assert first_slot_id in {item["slot_id"] for item in slots_response.json()}

    booking_response = max_api_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": first_slot_id},
    )
    assert booking_response.status_code == 201
    assert booking_response.json()["slot_id"] == first_slot_id
    assert booking_response.json()["status"] == models.SlotStatus.PENDING

    pending_journey = max_api_client.get("/api/candidate-access/journey", headers=headers)
    assert pending_journey.status_code == 200
    assert pending_journey.json()["active_booking"]["booking_id"] == first_slot_id
    assert pending_journey.json()["active_booking"]["status"] == models.SlotStatus.PENDING

    confirm_response = max_api_client.post(
        f"/api/candidate-access/bookings/{first_slot_id}/confirm",
        headers=headers,
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == models.SlotStatus.CONFIRMED_BY_CANDIDATE

    confirmed_journey = max_api_client.get("/api/candidate-access/journey", headers=headers)
    assert confirmed_journey.status_code == 200
    assert (
        confirmed_journey.json()["active_booking"]["status"]
        == models.SlotStatus.CONFIRMED_BY_CANDIDATE
    )

    slot = await _load_slot(first_slot_id)
    candidate = await _load_candidate(int(context["candidate_id"]))
    assert slot is not None
    assert candidate is not None
    assert slot.status == models.SlotStatus.CONFIRMED_BY_CANDIDATE
    assert slot.candidate_id == context["candidate_public_id"]
    assert slot.candidate_tg_id == int(context["telegram_id"])
    assert candidate.candidate_status == CandidateStatus.INTERVIEW_CONFIRMED


@pytest.mark.asyncio
async def test_max_e2e_pilot_flow_reschedules_and_cancels_via_candidate_access_http(
    max_api_client,
):
    context = await _seed_max_candidate_context(
        user_id=711003,
        start_param="max-e2e-reschedule-cancel",
        stage_step="test1",
        candidate_status=CandidateStatus.INVITED,
        application_status="test1_pending",
        slot_offsets_hours=(24, 36, 48),
    )
    original_slot_id = int(context["slot_ids"][0])
    replacement_slot_id = int(context["slot_ids"][1])

    headers, _ = _launch_candidate_access(
        max_api_client,
        user_id=int(context["telegram_id"]),
        start_param=str(context["start_param"]),
        query_id="max-e2e-reschedule-cancel-query",
    )
    complete_payload = _complete_test1_over_http(
        max_api_client,
        headers=headers,
        city_name=str(context["city_name"]),
    )
    assert complete_payload["journey_step"] == "booking"

    booking_response = max_api_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": original_slot_id},
    )
    assert booking_response.status_code == 201

    reschedule_response = max_api_client.post(
        f"/api/candidate-access/bookings/{original_slot_id}/reschedule",
        headers=headers,
        json={"new_slot_id": replacement_slot_id},
    )
    assert reschedule_response.status_code == 200
    assert reschedule_response.json()["slot_id"] == replacement_slot_id
    assert reschedule_response.json()["status"] == models.SlotStatus.PENDING

    rescheduled_journey = max_api_client.get("/api/candidate-access/journey", headers=headers)
    assert rescheduled_journey.status_code == 200
    assert rescheduled_journey.json()["active_booking"]["booking_id"] == replacement_slot_id
    assert rescheduled_journey.json()["active_booking"]["status"] == models.SlotStatus.PENDING

    cancel_response = max_api_client.post(
        f"/api/candidate-access/bookings/{replacement_slot_id}/cancel",
        headers=headers,
        json={"reason": "candidate_changed_plan"},
    )
    assert cancel_response.status_code == 204

    empty_journey = max_api_client.get("/api/candidate-access/journey", headers=headers)
    assert empty_journey.status_code == 200
    assert empty_journey.json()["active_booking"] is None

    original_slot = await _load_slot(original_slot_id)
    replacement_slot = await _load_slot(replacement_slot_id)
    assert original_slot is not None
    assert replacement_slot is not None
    assert original_slot.status == models.SlotStatus.FREE
    assert original_slot.candidate_id is None
    assert replacement_slot.status == models.SlotStatus.FREE
    assert replacement_slot.candidate_id is None
    assert replacement_slot.candidate_tg_id is None


@pytest.mark.asyncio
async def test_max_e2e_pilot_flow_confirms_without_seeded_telegram_identity(
    max_api_client,
):
    context = await _seed_max_candidate_context(
        user_id=711004,
        start_param="max-e2e-no-telegram-link",
        stage_step="test1",
        candidate_status=CandidateStatus.INVITED,
        application_status="test1_pending",
        slot_offsets_hours=(24,),
        link_telegram=False,
    )
    first_slot_id = int(context["slot_ids"][0])

    headers, _ = _launch_candidate_access(
        max_api_client,
        user_id=int(context["provider_user_id"]),
        start_param=str(context["start_param"]),
        query_id="max-e2e-no-telegram-link-query",
    )
    complete_payload = _complete_test1_over_http(
        max_api_client,
        headers=headers,
        city_name=str(context["city_name"]),
    )
    assert complete_payload["journey_step"] == "booking"

    booking_response = max_api_client.post(
        "/api/candidate-access/bookings",
        headers=headers,
        json={"slot_id": first_slot_id},
    )
    assert booking_response.status_code == 201

    confirm_response = max_api_client.post(
        f"/api/candidate-access/bookings/{first_slot_id}/confirm",
        headers=headers,
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == models.SlotStatus.CONFIRMED_BY_CANDIDATE

    slot = await _load_slot(first_slot_id)
    candidate = await _load_candidate(int(context["candidate_id"]))
    assert slot is not None
    assert candidate is not None
    assert slot.status == models.SlotStatus.CONFIRMED_BY_CANDIDATE
    assert slot.candidate_id == context["candidate_public_id"]
    assert slot.candidate_tg_id is None
    assert candidate.candidate_status == CandidateStatus.INTERVIEW_CONFIRMED


@pytest.mark.asyncio
async def test_max_e2e_manual_availability_is_visible_to_admin_operator_views(
    max_api_client,
):
    context = await _seed_max_candidate_context(
        user_id=711005,
        start_param="max-e2e-manual-availability-admin",
        stage_step="test1",
        candidate_status=CandidateStatus.INVITED,
        application_status="test1_pending",
        slot_offsets_hours=(),
    )

    headers, _ = _launch_candidate_access(
        max_api_client,
        user_id=int(context["telegram_id"]),
        start_param=str(context["start_param"]),
        query_id="max-e2e-manual-availability-admin-query",
    )
    complete_payload = _complete_test1_over_http(
        max_api_client,
        headers=headers,
        city_name=str(context["city_name"]),
    )
    assert complete_payload["journey_step"] == "booking"
    assert complete_payload["screening_decision"]["required_next_action"] == "select_interview_slot"

    slots_response = max_api_client.get(
        "/api/candidate-access/slots",
        headers=headers,
        params={"city_id": context["city_id"]},
    )
    assert slots_response.status_code == 200
    assert slots_response.json() == []

    manual_response = max_api_client.post(
        "/api/candidate-access/manual-availability",
        headers=headers,
        json={
            "note": "Могу завтра после 18:00 по Москве",
            "timezone_label": "Europe/Moscow",
        },
    )
    assert manual_response.status_code == 200
    assert manual_response.json()["status"] == "submitted"

    candidate = await _load_candidate(int(context["candidate_id"]))
    assert candidate is not None
    assert candidate.lifecycle_state == "active"
    assert candidate.candidate_status == CandidateStatus.WAITING_SLOT
    assert candidate.messenger_platform == "max"

    detail = await api_candidate_detail_payload(int(context["candidate_id"]))
    assert detail is not None
    assert detail["linked_channels"]["max"] is True
    assert detail["max"]["linked"] is True
    assert detail["channel_health"]["preferred_channel"] == "max"
    assert detail["candidate_status_slug"] == CandidateStatus.WAITING_SLOT.value
    assert detail["pending_slot_request"]["requested"] is True
    assert detail["pending_slot_request"]["source"] == "manual_slot_availability"
    assert detail["pending_slot_request"]["candidate_comment"] == "Могу завтра после 18:00 по Москве"

    payload = await list_candidates(
        page=1,
        per_page=20,
        search=None,
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        statuses=[CandidateStatus.WAITING_SLOT.value],
        principal=Principal(type="admin", id=-1),
    )
    cards = payload.get("views", {}).get("candidates", [])
    card = next((item for item in cards if item.get("id") == int(context["candidate_id"])), None)
    assert card is not None
    assert card["linked_channels"]["max"] is True
    assert card["preferred_channel"] == "max"
    assert card["candidate_next_action"]["worklist_bucket"] in {
        "incoming",
        "awaiting_recruiter",
    }
    assert card["pending_slot_request"]["requested"] is True
    assert card["pending_slot_request"]["source"] == "manual_slot_availability"
