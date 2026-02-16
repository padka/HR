from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter, Slot, SlotAssignment


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.mark.asyncio
async def _seed_intro_day_assignment(
    *,
    fio: str,
    rejection_reason: str | None = None,
    candidate_status: CandidateStatus | None = None,
):
    async with async_session() as session:
        city = City(name=f"DET City {fio[:6]}", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name=f"DET Recruiter {fio[:6]}", tz="Europe/Moscow", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        user = User(
            fio=fio,
            telegram_id=None,
            telegram_username=None,
            city=city.name,
            source="bot",
            rejection_reason=rejection_reason,
            candidate_status=candidate_status,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        now = datetime.now(timezone.utc)
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=now + timedelta(days=1),
            duration_min=60,
            capacity=1,
            status="confirmed",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=user.candidate_id,
            candidate_tg_id=None,
            candidate_tz="Europe/Moscow",
            status="confirmed",
            offered_at=now - timedelta(days=2),
            confirmed_at=now - timedelta(days=1),
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        return {
            "user_id": int(user.id),
            "city_id": int(city.id),
            "recruiter_id": int(recruiter.id),
            "slot_id": int(slot.id),
            "assignment_id": int(assignment.id),
        }


def test_detailization_autocreates_and_lists_rows():
    seed = _run(
        _seed_intro_day_assignment(
            fio="DET Candidate Autocreate",
            rejection_reason=None,
            candidate_status=CandidateStatus.NOT_HIRED,
        )
    )
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/detailization", auth=("admin", "admin"))
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        items = payload["items"]
        row = next((it for it in items if it["candidate"]["id"] == seed["user_id"]), None)
        assert row is not None
        assert row["candidate"]["name"] == "DET Candidate Autocreate"
        assert row["recruiter"]["id"] == seed["recruiter_id"]
        assert row["city"]["id"] == seed["city_id"]
        assert row["is_attached"] is False


def test_detailization_excludes_criteria_mismatch():
    seed = _run(
        _seed_intro_day_assignment(
            fio="DET Candidate CriteriaMismatch",
            rejection_reason="Не подходит по критериям",
            candidate_status=CandidateStatus.NOT_HIRED,
        )
    )
    app = create_app()
    with TestClient(app) as client:
        payload = client.get("/api/detailization", auth=("admin", "admin")).json()
        items = payload["items"]
        assert not any(it["candidate"]["id"] == seed["user_id"] for it in items)


def test_detailization_excludes_no_show():
    seed = _run(
        _seed_intro_day_assignment(
            fio="DET Candidate NoShow",
            rejection_reason="Кандидат не пришел на ознакомительный день",
            candidate_status=CandidateStatus.NOT_HIRED,
        )
    )
    app = create_app()
    with TestClient(app) as client:
        payload = client.get("/api/detailization", auth=("admin", "admin")).json()
        items = payload["items"]
        assert not any(it["candidate"]["id"] == seed["user_id"] for it in items)


def test_detailization_patch_updates_manual_fields():
    seed = _run(
        _seed_intro_day_assignment(
            fio="DET Candidate Patch",
            rejection_reason=None,
            candidate_status=CandidateStatus.HIRED,
        )
    )
    app = create_app()
    with TestClient(app) as client:
        # Ensure entry exists
        payload = client.get("/api/detailization", auth=("admin", "admin")).json()
        row = next((it for it in payload["items"] if it["candidate"]["id"] == seed["user_id"]), None)
        assert row is not None
        entry_id = int(row["id"])

        csrf = client.get("/api/csrf", auth=("admin", "admin"))
        token = csrf.json()["token"]
        patched = client.patch(
            f"/api/detailization/{entry_id}",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"column_9": "C9", "expert_name": "Эксперт ФИО", "is_attached": True},
        )
        assert patched.status_code == 200
        assert patched.json()["ok"] is True

        payload2 = client.get("/api/detailization", auth=("admin", "admin")).json()
        row2 = next((it for it in payload2["items"] if it["candidate"]["id"] == seed["user_id"]), None)
        assert row2 is not None
        assert row2["column_9"] == "C9"
        assert row2["expert_name"] == "Эксперт ФИО"
        assert row2["is_attached"] is True

