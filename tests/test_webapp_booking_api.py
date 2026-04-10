from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import (
    City,
    Recruiter,
    Slot,
    SlotAssignment,
    SlotAssignmentStatus,
    SlotStatus,
)


BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _generate_valid_init_data(*, user_id: int, bot_token: str, username: str = "webapp_user", first_name: str = "Web") -> str:
    auth_date = int(time.time())
    user_json = json.dumps(
        {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "language_code": "ru",
        }
    )
    params = {
        "user": user_json,
        "auth_date": str(auth_date),
        "query_id": f"query_{user_id}",
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    params["hash"] = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return urlencode(params)


@pytest.fixture
def webapp_client(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("REDIS_URL", "")

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    from backend.apps.admin_api.main import create_app

    app = create_app()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings_module.get_settings.cache_clear()


async def _seed_webapp_scenario(*, telegram_id: int, existing_active_interview: bool = False) -> dict[str, int]:
    async with async_session() as session:
        city = City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="WebApp Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        candidate = User(
            fio="Кандидат WebApp",
            telegram_id=telegram_id,
            telegram_user_id=telegram_id,
            username="webapp_candidate",
            telegram_username="webapp_candidate",
            city=city.name,
            candidate_status=CandidateStatus.TEST1_COMPLETED,
            source="webapp",
        )
        session.add(candidate)
        await session.flush()

        start = datetime.now(timezone.utc) + timedelta(days=1)
        free_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=start,
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        session.add(free_slot)
        await session.flush()

        existing_slot_id = 0
        if existing_active_interview:
            existing = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=start + timedelta(hours=2),
                duration_min=60,
                status=SlotStatus.BOOKED,
                purpose="interview",
                tz_name="Europe/Moscow",
                candidate_id=candidate.candidate_id,
                candidate_tg_id=telegram_id,
                candidate_fio=candidate.fio,
                candidate_tz="Europe/Moscow",
            )
            session.add(existing)
            await session.flush()
            existing_slot_id = existing.id

        await session.commit()
        return {
            "candidate_id": candidate.id,
            "telegram_id": telegram_id,
            "slot_id": free_slot.id,
            "city_id": city.id,
            "recruiter_id": recruiter.id,
            "existing_slot_id": existing_slot_id,
        }


async def _load_slot(slot_id: int) -> Slot | None:
    async with async_session() as session:
        return await session.get(Slot, slot_id)


async def _load_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


def _webapp_headers(*, telegram_id: int) -> dict[str, str]:
    return {
        "X-Telegram-Init-Data": _generate_valid_init_data(user_id=telegram_id, bot_token=BOT_TOKEN),
    }


def test_webapp_me_accepts_valid_init_data(webapp_client):
    seeded = asyncio.run(_seed_webapp_scenario(telegram_id=700001))

    response = webapp_client.get(
        "/api/webapp/me",
        headers=_webapp_headers(telegram_id=seeded["telegram_id"]),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == seeded["telegram_id"]
    assert payload["candidate_id"] == seeded["candidate_id"]
    assert payload["city_id"] == seeded["city_id"]


def test_webapp_booking_uses_domain_reservation_and_updates_status(webapp_client):
    seeded = asyncio.run(_seed_webapp_scenario(telegram_id=700002))

    response = webapp_client.post(
        "/api/webapp/booking",
        json={"slot_id": seeded["slot_id"]},
        headers=_webapp_headers(telegram_id=seeded["telegram_id"]),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["slot_id"] == seeded["slot_id"]
    assert payload["status"] == SlotStatus.PENDING

    slot = asyncio.run(_load_slot(seeded["slot_id"]))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING
    assert slot.candidate_tg_id == seeded["telegram_id"]

    candidate = asyncio.run(_load_candidate(seeded["candidate_id"]))
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.SLOT_PENDING
    assert candidate.responsible_recruiter_id == seeded["recruiter_id"]


def test_webapp_booking_duplicate_candidate_returns_business_conflict(webapp_client):
    seeded = asyncio.run(_seed_webapp_scenario(telegram_id=700003, existing_active_interview=True))

    response = webapp_client.post(
        "/api/webapp/booking",
        json={"slot_id": seeded["slot_id"]},
        headers=_webapp_headers(telegram_id=seeded["telegram_id"]),
    )

    assert response.status_code == 409
    assert "active interview booking" in response.json()["detail"].lower()

    free_slot = asyncio.run(_load_slot(seeded["slot_id"]))
    assert free_slot is not None
    assert free_slot.status == SlotStatus.FREE


def test_webapp_booking_blocks_assignment_owned_scheduling(webapp_client):
    seeded = asyncio.run(_seed_webapp_scenario(telegram_id=700004))

    async def _seed_assignment_owned_scheduling() -> None:
        async with async_session() as session:
            candidate = await session.get(User, seeded["candidate_id"])
            slot = Slot(
                recruiter_id=seeded["recruiter_id"],
                city_id=seeded["city_id"],
                start_utc=datetime.now(timezone.utc) + timedelta(days=1, hours=3),
                duration_min=60,
                status=SlotStatus.PENDING,
                purpose="interview",
                tz_name="Europe/Moscow",
                candidate_id=candidate.candidate_id,
                candidate_tg_id=seeded["telegram_id"],
                candidate_fio=candidate.fio,
                candidate_tz="Europe/Moscow",
                candidate_city_id=seeded["city_id"],
            )
            session.add(slot)
            await session.flush()
            session.add(
                SlotAssignment(
                    slot_id=slot.id,
                    recruiter_id=seeded["recruiter_id"],
                    candidate_id=candidate.candidate_id,
                    candidate_tg_id=seeded["telegram_id"],
                    candidate_tz="Europe/Moscow",
                    status=SlotAssignmentStatus.OFFERED,
                )
            )
            await session.commit()

    asyncio.run(_seed_assignment_owned_scheduling())

    response = webapp_client.post(
        "/api/webapp/booking",
        json={"slot_id": seeded["slot_id"]},
        headers=_webapp_headers(telegram_id=seeded["telegram_id"]),
    )

    assert response.status_code == 409
    assert "slotassignment" in response.json()["detail"].lower()

    free_slot = asyncio.run(_load_slot(seeded["slot_id"]))
    assert free_slot is not None
    assert free_slot.status == SlotStatus.FREE
