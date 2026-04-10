import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services.candidates import get_candidate_detail
from backend.apps.admin_ui.security import Principal, require_principal
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import TestResult, User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.slot_assignment_service import (
    approve_reschedule,
    begin_reschedule_request,
    create_slot_assignment,
    request_reschedule,
)


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
    monkeypatch.setenv("ALLOW_LEGACY_BASIC", "1")
    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


async def _async_request(app, method: str, path: str, **kwargs) -> Any:
    def _call() -> Any:
        with TestClient(app) as client:
            client.auth = ("admin", "admin")
            headers = dict(kwargs.pop("headers", {}) or {})
            if method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
                header_keys = {key.lower() for key in headers}
                if "x-csrf-token" not in header_keys:
                    csrf = client.get("/api/csrf").json()["token"]
                    headers["x-csrf-token"] = csrf
            if headers:
                kwargs["headers"] = headers
            return client.request(method, path, **kwargs)

    return await asyncio.to_thread(_call)


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
                headers = dict(kwargs.pop("headers", {}) or {})
                if method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
                    header_keys = {key.lower() for key in headers}
                    if "x-csrf-token" not in header_keys:
                        csrf = client.get("/api/csrf").json()["token"]
                        headers["x-csrf-token"] = csrf
                if headers:
                    kwargs["headers"] = headers
                return client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(require_principal, None)

    return await asyncio.to_thread(_call)


async def _create_reschedule_assignment(
    *,
    telegram_id: int,
    fio: str,
    city_name: str,
    recruiter_name: str,
    start_utc: datetime,
) -> tuple[User, int, str]:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=telegram_id,
        fio=fio,
        city=city_name,
        initial_status=CandidateStatus.SLOT_PENDING,
    )

    async with async_session() as session:
        city = models.City(name=city_name, tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name=recruiter_name, tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=start_utc,
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    offer = await create_slot_assignment(
        slot_id=slot_id,
        candidate_id=candidate.candidate_id,
        candidate_tg_id=candidate.telegram_id,
        candidate_tz="Europe/Moscow",
        created_by="admin",
    )
    assert offer.ok is True
    return candidate, int(offer.payload["slot_assignment_id"]), str(offer.payload["reschedule_token"])


def _to_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@pytest.mark.asyncio
async def test_schedule_slot_conflict_returns_validation_error(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777001,
        fio="API Кандидат",
        city="Москва",
        username="api_candidate",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        # Create a BOOKED slot that conflicts with the time we'll try to schedule
        # Use timezone-aware UTC datetime to ensure proper conflict detection
        conflict_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2024, 7, 5, 9, 0, tzinfo=timezone.utc),  # 09:00 UTC = 12:00 Moscow
            duration_min=60,
            status=models.SlotStatus.BOOKED,  # Already booked - creates conflict
            candidate_tg_id=999999,  # Different candidate
            candidate_fio="Другой кандидат",
            candidate_tz="Europe/Moscow",
        )
        session.add(conflict_slot)
        await session.commit()
        recruiter_id = recruiter.id
        city_id = city.id

    response = await _async_request(
        admin_app,
        "post",
        f"/candidates/{candidate.id}/schedule-slot",
        data={
            "recruiter_id": recruiter_id,
            "city_id": city_id,
            "date": "2024-07-05",
            "time": "12:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_api_create_candidate_create_only_without_datetime(admin_app) -> None:
    async with async_session() as session:
        city = models.City(name="Новосибирск", tz="Asia/Novosibirsk", active=True)
        recruiter = models.Recruiter(name="CreateOnly Recruiter 1", tz="Asia/Novosibirsk", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        city_id = city.id
        recruiter_id = recruiter.id

    response = await _async_request(
        admin_app,
        "post",
        "/api/candidates",
        json={
            "fio": "Create Only Candidate",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
        },
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["slot_scheduled"] is False
    created_id = int(payload["id"])

    async with async_session() as session:
        user = await session.get(User, created_id)
        assert user is not None
        assert user.fio == "Create Only Candidate"
        assert user.responsible_recruiter_id == recruiter_id
        assert user.manual_slot_from is None
        assert user.manual_slot_to is None


@pytest.mark.asyncio
async def test_api_create_candidate_with_datetime_without_telegram_keeps_candidate(admin_app) -> None:
    async with async_session() as session:
        city = models.City(name="Омск", tz="Asia/Omsk", active=True)
        recruiter = models.Recruiter(name="CreateOnly Recruiter 2", tz="Asia/Omsk", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        city_id = city.id
        recruiter_id = recruiter.id

    response = await _async_request(
        admin_app,
        "post",
        "/api/candidates",
        json={
            "fio": "Create With Datetime Candidate",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
            "interview_date": "2031-06-01",
            "interview_time": "14:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["slot_scheduled"] is False
    created_id = int(payload["id"])

    async with async_session() as session:
        user = await session.get(User, created_id)
        assert user is not None
        assert user.fio == "Create With Datetime Candidate"
        assert user.manual_slot_from is None
        assert user.manual_slot_to is None
        slot = await session.scalar(select(models.Slot).where(models.Slot.candidate_fio == user.fio))
        assert slot is None


@pytest.mark.asyncio
async def test_api_create_candidate_with_telegram_id(admin_app) -> None:
    async with async_session() as session:
        city = models.City(name="Томск", tz="Asia/Tomsk", active=True)
        recruiter = models.Recruiter(name="CreateOnly Recruiter 3", tz="Asia/Tomsk", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        city_id = city.id
        recruiter_id = recruiter.id

    response = await _async_request(
        admin_app,
        "post",
        "/api/candidates",
        json={
            "fio": "Create With Telegram Candidate",
            "city_id": city_id,
            "recruiter_id": recruiter_id,
            "telegram_id": 79991234001,
        },
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["slot_scheduled"] is False
    created_id = int(payload["id"])

    async with async_session() as session:
        user = await session.get(User, created_id)
        assert user is not None
        assert user.telegram_id == 79991234001


@pytest.mark.asyncio
async def test_api_delete_candidate_removes_user(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=79991239991,
        fio="Candidate To Delete",
        city="Москва",
        username="candidate_to_delete",
        initial_status=CandidateStatus.LEAD,
    )

    response = await _async_request(
        admin_app,
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
async def test_api_candidates_list_includes_views_for_kanban_and_calendar(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=79991239992,
        fio="Candidate Views Contract",
        city="Москва",
        username="candidate_views_contract",
        initial_status=CandidateStatus.LEAD,
    )
    assert candidate is not None

    list_response = await _async_request(
        admin_app,
        "get",
        "/api/candidates?page=1&per_page=20&pipeline=interview",
        follow_redirects=False,
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert isinstance(list_payload.get("views"), dict)
    assert isinstance(list_payload["views"].get("kanban", {}).get("columns"), list)
    assert isinstance(list_payload.get("pipeline_options"), list)

    calendar_response = await _async_request(
        admin_app,
        "get",
        "/api/candidates?page=1&per_page=20&pipeline=interview&calendar_mode=day&date_from=2026-02-25&date_to=2026-03-10",
        follow_redirects=False,
    )
    assert calendar_response.status_code == 200
    calendar_payload = calendar_response.json()
    assert isinstance(calendar_payload.get("views"), dict)
    assert isinstance(calendar_payload["views"].get("calendar", {}).get("days"), list)


@pytest.mark.asyncio
async def test_api_candidates_list_accepts_canonical_state_filter(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=79991239993,
        fio="Candidate Canonical API Filter",
        city="Москва",
        username="candidate_canonical_api_filter",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )
    assert candidate is not None

    response = await _async_request(
        admin_app,
        "get",
        "/api/candidates?page=1&per_page=20&pipeline=main&state=kanban:test2_completed&search=Candidate%20Canonical%20API%20Filter",
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["filters"]["state"] == ["kanban:test2_completed"]
    assert any(
        option.get("value") == "kanban:test2_completed"
        for option in payload["filters"].get("state_options", [])
    )
    assert payload["views"].get("candidates")
    assert all(
        card.get("operational_summary") is not None
        for card in payload["views"].get("candidates", [])
    )


@pytest.mark.asyncio
async def test_schedule_slot_reuses_active_reschedule_assignment(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777002,
        fio="API Кандидат 2",
        city="Москва",
        username="api_candidate2",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter 2", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2031, 7, 5, 9, 0, tzinfo=timezone.utc),
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        slot_id = slot.id
        recruiter_id = recruiter.id
        city_id = city.id

    # Offer the initial slot via SlotAssignment, then request reschedule.
    offer = await create_slot_assignment(
        slot_id=slot_id,
        candidate_id=candidate.candidate_id,
        candidate_tg_id=candidate.telegram_id,
        candidate_tz="Europe/Moscow",
        created_by="admin",
    )
    assert offer.ok is True
    assignment_id = int(offer.payload["slot_assignment_id"])
    reschedule_token = str(offer.payload["reschedule_token"])

    res = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
        requested_start_utc=datetime(2031, 7, 6, 9, 0, tzinfo=timezone.utc),
        requested_tz="Europe/Moscow",
        comment="need another time",
    )
    assert res.ok is True

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-slot",
        json={
            "recruiter_id": recruiter_id,
            "city_id": city_id,
            "date": "2031-07-06",
            "time": "12:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending_offer"
    assert int(payload.get("slot_assignment_id") or 0) == assignment_id


@pytest.mark.asyncio
async def test_begin_reschedule_request_marks_assignment_before_datetime_submission() -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777004,
        fio="API Кандидат 4",
        city="Москва",
        username="api_candidate4",
        initial_status=CandidateStatus.SLOT_PENDING,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter 4", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2031, 7, 8, 9, 0, tzinfo=timezone.utc),
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    offer = await create_slot_assignment(
        slot_id=slot_id,
        candidate_id=candidate.candidate_id,
        candidate_tg_id=candidate.telegram_id,
        candidate_tz="Europe/Moscow",
        created_by="admin",
    )
    assert offer.ok is True
    assignment_id = int(offer.payload["slot_assignment_id"])
    reschedule_token = str(offer.payload["reschedule_token"])

    begin = await begin_reschedule_request(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
    )
    assert begin.ok is True
    assert begin.status == "reschedule_pending_input"

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.RESCHEDULE_REQUESTED
        assert assignment.reschedule_requested_at is not None

    res = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
        requested_start_utc=datetime(2031, 7, 9, 12, 0, tzinfo=timezone.utc),
        requested_tz="Europe/Moscow",
        comment="Удобнее позже",
    )
    assert res.ok is True

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.RESCHEDULE_REQUESTED
        request = await session.scalar(
            select(models.RescheduleRequest).where(
                models.RescheduleRequest.slot_assignment_id == assignment_id,
                models.RescheduleRequest.status == models.RescheduleRequestStatus.PENDING,
            )
        )
        assert request is not None
        assert request.candidate_comment == "Удобнее позже"


@pytest.mark.asyncio
async def test_request_reschedule_accepts_exact_slot_choice() -> None:
    candidate, assignment_id, reschedule_token = await _create_reschedule_assignment(
        telegram_id=777005,
        fio="API Кандидат 5",
        city_name="Казань",
        recruiter_name="API Recruiter 5",
        start_utc=datetime(2031, 7, 10, 9, 0, tzinfo=timezone.utc),
    )

    result = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
        requested_start_utc=datetime(2031, 7, 11, 11, 0, tzinfo=timezone.utc),
        requested_tz="Europe/Moscow",
        comment=None,
    )

    assert result.ok is True

    async with async_session() as session:
        request = await session.scalar(
            select(models.RescheduleRequest).where(
                models.RescheduleRequest.slot_assignment_id == assignment_id,
                models.RescheduleRequest.status == models.RescheduleRequestStatus.PENDING,
            )
        )
        assert request is not None
        assert _to_aware_utc(request.requested_start_utc) == datetime(2031, 7, 11, 11, 0, tzinfo=timezone.utc)
        assert request.requested_end_utc is None
        assert request.candidate_comment is None


@pytest.mark.asyncio
async def test_request_reschedule_accepts_availability_window_and_blocks_direct_approve() -> None:
    candidate, assignment_id, reschedule_token = await _create_reschedule_assignment(
        telegram_id=777006,
        fio="API Кандидат 6",
        city_name="Самара",
        recruiter_name="API Recruiter 6",
        start_utc=datetime(2031, 7, 12, 9, 0, tzinfo=timezone.utc),
    )

    result = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
        requested_start_utc=datetime(2031, 7, 13, 9, 0, tzinfo=timezone.utc),
        requested_end_utc=datetime(2031, 7, 13, 12, 0, tzinfo=timezone.utc),
        requested_tz="Europe/Moscow",
        comment=None,
    )

    assert result.ok is True

    async with async_session() as session:
        request = await session.scalar(
            select(models.RescheduleRequest).where(
                models.RescheduleRequest.slot_assignment_id == assignment_id,
                models.RescheduleRequest.status == models.RescheduleRequestStatus.PENDING,
            )
        )
        assert request is not None
        assert _to_aware_utc(request.requested_start_utc) == datetime(2031, 7, 13, 9, 0, tzinfo=timezone.utc)
        assert _to_aware_utc(request.requested_end_utc) == datetime(2031, 7, 13, 12, 0, tzinfo=timezone.utc)

    approve = await approve_reschedule(
        assignment_id=assignment_id,
        decided_by_id=1,
        decided_by_type="admin",
    )
    assert approve.ok is False
    assert approve.status_code == 409
    assert "точного времени" in (approve.message or "")


@pytest.mark.asyncio
async def test_request_reschedule_accepts_free_text_without_datetime() -> None:
    candidate, assignment_id, reschedule_token = await _create_reschedule_assignment(
        telegram_id=777007,
        fio="API Кандидат 7",
        city_name="Уфа",
        recruiter_name="API Recruiter 7",
        start_utc=datetime(2031, 7, 14, 9, 0, tzinfo=timezone.utc),
    )

    result = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
        requested_start_utc=None,
        requested_tz="Europe/Moscow",
        comment="Мне удобно после 18:00 в любой день на следующей неделе",
    )

    assert result.ok is True

    async with async_session() as session:
        request = await session.scalar(
            select(models.RescheduleRequest).where(
                models.RescheduleRequest.slot_assignment_id == assignment_id,
                models.RescheduleRequest.status == models.RescheduleRequestStatus.PENDING,
            )
        )
        assert request is not None
        assert request.requested_start_utc is None
        assert request.requested_end_utc is None
        assert request.candidate_comment == "Мне удобно после 18:00 в любой день на следующей неделе"


@pytest.mark.asyncio
async def test_schedule_slot_assigns_existing_free_slot(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777003,
        fio="API Кандидат 3",
        city="Москва",
        username="api_candidate3",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter 3", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        free_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=3),
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(free_slot)
        await session.commit()
        await session.refresh(free_slot)
        slot_id = free_slot.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-slot",
        json={"slot_id": slot_id},
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending_offer"
    assert int(payload.get("slot_assignment_id") or 0) > 0
    assert int(payload.get("slot_id") or 0) == slot_id

    async with async_session() as session:
        db_slot = await session.get(models.Slot, slot_id)
        db_user = await session.get(User, candidate.id)
        assignment = await session.scalar(
            select(models.SlotAssignment).where(models.SlotAssignment.slot_id == slot_id)
        )

    assert db_slot is not None
    assert db_slot.status == models.SlotStatus.PENDING
    assert db_slot.candidate_id == candidate.candidate_id
    assert db_slot.candidate_tg_id == candidate.telegram_id
    assert db_user is not None
    assert db_user.candidate_status == CandidateStatus.SLOT_PENDING
    assert assignment is not None
    assert assignment.status == models.SlotAssignmentStatus.OFFERED


@pytest.mark.asyncio
async def test_schedule_slot_manual_uses_recruiter_timezone_for_input(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777117,
        fio="API Кандидат TZ",
        city="Алматы",
        username="api_candidate_tz",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        recruiter = models.Recruiter(name="API Recruiter TZ", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        recruiter_id = recruiter.id
        city_id = city.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-slot",
        json={
            "recruiter_id": recruiter_id,
            "city_id": city_id,
            "date": "2032-01-15",
            "time": "14:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending_offer"

    expected_utc = datetime(2032, 1, 15, 14, 0, tzinfo=ZoneInfo("Europe/Moscow")).astimezone(timezone.utc)

    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot)
            .where(models.Slot.candidate_tg_id == candidate.telegram_id)
            .order_by(models.Slot.id.desc())
        )

    assert slot is not None
    assert slot.start_utc == expected_utc
    assert slot.candidate_tz == "Asia/Almaty"
    assert slot.tz_name == "Asia/Almaty"
    assert slot.start_utc.astimezone(ZoneInfo("Europe/Moscow")).hour == 14
    assert slot.start_utc.astimezone(ZoneInfo("Asia/Almaty")).hour != 14


@pytest.mark.asyncio
async def test_schedule_slot_replaces_existing_active_assignment(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777005,
        fio="API Кандидат 5",
        city="Москва",
        username="api_candidate5",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter 5", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        old_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=3, hours=1),
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        new_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=3, hours=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add_all([old_slot, new_slot])
        await session.commit()
        await session.refresh(old_slot)
        await session.refresh(new_slot)
        old_slot_id = old_slot.id
        new_slot_id = new_slot.id

    initial_offer = await create_slot_assignment(
        slot_id=old_slot_id,
        candidate_id=candidate.candidate_id,
        candidate_tg_id=candidate.telegram_id,
        candidate_tz="Europe/Moscow",
        created_by="admin",
    )
    assert initial_offer.ok is True
    old_assignment_id = int(initial_offer.payload["slot_assignment_id"])

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-slot",
        json={"slot_id": new_slot_id},
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending_offer"
    assert int(payload.get("slot_id") or 0) == new_slot_id

    async with async_session() as session:
        old_slot_db = await session.get(models.Slot, old_slot_id)
        new_slot_db = await session.get(models.Slot, new_slot_id)
        old_assignment = await session.get(models.SlotAssignment, old_assignment_id)
        active_assignments = (
            await session.execute(
                select(models.SlotAssignment).where(
                    models.SlotAssignment.candidate_id == candidate.candidate_id,
                    models.SlotAssignment.status.in_(
                        (
                            models.SlotAssignmentStatus.OFFERED,
                            models.SlotAssignmentStatus.CONFIRMED,
                            models.SlotAssignmentStatus.RESCHEDULE_REQUESTED,
                            models.SlotAssignmentStatus.RESCHEDULE_CONFIRMED,
                        )
                    ),
                )
            )
        ).scalars().all()

    assert old_slot_db is not None
    assert old_slot_db.status == models.SlotStatus.FREE
    assert old_slot_db.candidate_id is None
    assert old_slot_db.candidate_tg_id is None
    assert new_slot_db is not None
    assert new_slot_db.status == models.SlotStatus.PENDING
    assert new_slot_db.candidate_id == candidate.candidate_id
    assert new_slot_db.candidate_tg_id == candidate.telegram_id
    assert old_assignment is not None
    assert old_assignment.status == models.SlotAssignmentStatus.CANCELLED
    assert len(active_assignments) == 1
    assert active_assignments[0].slot_id == new_slot_id


@pytest.mark.asyncio
async def test_available_slots_endpoint_filters_by_candidate_city(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777004,
        fio="API Кандидат 4",
        city="Москва",
        username="api_candidate4",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )

    async with async_session() as session:
        city_msk = models.City(name="Москва", tz="Europe/Moscow", active=True)
        city_spb = models.City(name="Санкт-Петербург", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="API Recruiter 4", tz="Europe/Moscow", active=True)
        recruiter.cities.extend([city_msk, city_spb])
        session.add_all([city_msk, city_spb, recruiter])
        await session.commit()
        await session.refresh(city_msk)
        await session.refresh(city_spb)
        await session.refresh(recruiter)

        session.add_all(
            [
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city_msk.id,
                    tz_name=city_msk.tz,
                    start_utc=datetime.now(timezone.utc) + timedelta(days=2, hours=1),
                    duration_min=60,
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city_spb.id,
                    tz_name=city_spb.tz,
                    start_utc=datetime.now(timezone.utc) + timedelta(days=2, hours=2),
                    duration_min=60,
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city_msk.id,
                    tz_name=city_msk.tz,
                    start_utc=datetime.now(timezone.utc) + timedelta(days=2, hours=3),
                    duration_min=60,
                    status=models.SlotStatus.BOOKED,
                ),
            ]
        )
        await session.commit()

    response = await _async_request(
        admin_app,
        "get",
        f"/api/candidates/{candidate.id}/available-slots?limit=20",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert int(payload.get("candidate_city_id") or 0) > 0
    items = payload.get("items") or []
    assert len(items) == 1
    assert items[0]["city_name"] == "Москва"


@pytest.mark.asyncio
async def test_api_slot_propose_assigns_candidate_and_sets_slot_pending(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777110,
        fio="API Propose Candidate",
        city="Алматы",
        username="api_propose_candidate",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        recruiter = models.Recruiter(name="Almaty Recruiter", tz="Asia/Almaty", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/slots/{slot_id}/propose",
        json={"candidate_id": candidate.candidate_id},
        follow_redirects=False,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending_offer"
    assert int(payload["slot_id"]) == slot_id
    assert int(payload["slot_assignment_id"]) > 0

    async with async_session() as session:
        db_slot = await session.get(models.Slot, slot_id)
        db_user = await session.get(User, candidate.id)
        assignment = await session.scalar(
            select(models.SlotAssignment).where(models.SlotAssignment.slot_id == slot_id)
        )

    assert db_slot is not None
    assert db_slot.status == models.SlotStatus.PENDING
    assert db_slot.candidate_id == candidate.candidate_id
    assert db_slot.candidate_tg_id == candidate.telegram_id
    assert db_user is not None
    assert db_user.candidate_status == CandidateStatus.SLOT_PENDING
    assert assignment is not None
    assert assignment.status == models.SlotAssignmentStatus.OFFERED


@pytest.mark.asyncio
async def test_api_slot_propose_returns_slot_not_free(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777111,
        fio="API Propose Busy Slot Candidate",
        city="Алматы",
        username="api_propose_busy",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        recruiter = models.Recruiter(name="Almaty Recruiter Busy", tz="Asia/Almaty", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/slots/{slot_id}/propose",
        json={"candidate_id": candidate.candidate_id},
        follow_redirects=False,
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "slot_not_free"


@pytest.mark.asyncio
async def test_api_slot_propose_uses_telegram_user_id_fallback(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777112,
        fio="API Telegram User Id Fallback",
        city="Алматы",
        username="api_tg_fallback",
        initial_status=CandidateStatus.WAITING_SLOT,
    )
    fallback_tg_id = 88800112
    async with async_session() as session:
        user = await session.get(User, candidate.id)
        assert user is not None
        user.telegram_user_id = fallback_tg_id
        user.telegram_id = None
        await session.commit()

        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        recruiter = models.Recruiter(name="Almaty Recruiter Fallback", tz="Asia/Almaty", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=3),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/slots/{slot_id}/propose",
        json={"candidate_id": candidate.candidate_id},
        follow_redirects=False,
    )

    assert response.status_code == 201
    async with async_session() as session:
        db_slot = await session.get(models.Slot, slot_id)
    assert db_slot is not None
    assert db_slot.candidate_tg_id == fallback_tg_id


@pytest.mark.asyncio
async def test_api_schedule_slot_returns_candidate_telegram_missing_when_no_identifiers(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777113,
        fio="API No Telegram Candidate",
        city="Алматы",
        username="api_no_tg",
        initial_status=CandidateStatus.WAITING_SLOT,
    )
    async with async_session() as session:
        user = await session.get(User, candidate.id)
        assert user is not None
        user.telegram_user_id = None
        user.telegram_id = None
        await session.commit()

        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        recruiter = models.Recruiter(name="Almaty Recruiter NoTG", tz="Asia/Almaty", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=4),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-slot",
        json={"slot_id": slot_id},
        follow_redirects=False,
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "candidate_telegram_missing"


@pytest.mark.asyncio
async def test_api_slot_propose_recruiter_scope_blocks_foreign_slot(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777114,
        fio="API Scoped Candidate",
        city="Алматы",
        username="api_scoped",
        initial_status=CandidateStatus.WAITING_SLOT,
    )
    async with async_session() as session:
        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        owner = models.Recruiter(name="Owner Recruiter", tz="Asia/Almaty", active=True)
        outsider = models.Recruiter(name="Outsider Recruiter", tz="Asia/Almaty", active=True)
        owner.cities.append(city)
        outsider.cities.append(city)
        session.add_all([city, owner, outsider])
        await session.commit()
        await session.refresh(owner)
        await session.refresh(outsider)

        slot = models.Slot(
            recruiter_id=owner.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        outsider_id = outsider.id

    response = await _async_request_with_principal(
        admin_app,
        Principal(type="recruiter", id=outsider_id),
        "post",
        f"/api/slots/{slot_id}/propose",
        json={"candidate_id": candidate.candidate_id},
        follow_redirects=False,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_schedule_intro_day_cancels_active_interview_slot_and_assignment(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777115,
        fio="Алматы Кандидат ОД",
        city="Алматы",
        username="api_intro_day_cleanup",
        initial_status=CandidateStatus.INTERVIEW_CONFIRMED,
    )

    async with async_session() as session:
        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        recruiter = models.Recruiter(name="Алматы Рекрутер", tz="Asia/Almaty", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        interview_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2032, 3, 1, 9, 0, tzinfo=timezone.utc),
            duration_min=60,
            status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz=city.tz,
        )
        session.add(interview_slot)
        await session.commit()
        await session.refresh(interview_slot)
        interview_start_utc = interview_slot.start_utc

        assignment = models.SlotAssignment(
            slot_id=interview_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz=city.tz,
            status=models.SlotAssignmentStatus.CONFIRMED,
            offered_at=datetime.now(timezone.utc) - timedelta(days=1),
            confirmed_at=datetime.now(timezone.utc) - timedelta(hours=12),
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        assignment_id = assignment.id
        recruiter_id = recruiter.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2032-03-02",
            "time": "11:00",
            "recruiter_id": recruiter_id,
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    intro_slot_id = int(payload["slot_id"])

    async with async_session() as session:
        intro_slot = await session.get(models.Slot, intro_slot_id)
        removed_interview_slot = await session.scalar(
            select(models.Slot).where(
                models.Slot.recruiter_id == recruiter_id,
                models.Slot.start_utc == interview_start_utc,
                models.Slot.purpose == "interview",
            )
        )
        updated_assignment = await session.get(models.SlotAssignment, assignment_id)

    assert removed_interview_slot is None
    assert intro_slot is not None
    assert intro_slot.purpose == "intro_day"
    assert intro_slot.status == models.SlotStatus.BOOKED
    assert updated_assignment is None

    slots_response = await _async_request(
        admin_app,
        "get",
        "/api/slots?limit=200",
        follow_redirects=False,
    )
    assert slots_response.status_code == 200
    rows = slots_response.json()
    candidate_rows = [row for row in rows if str(row.get("candidate_tg_id") or "") == str(candidate.telegram_id)]
    assert any((row.get("purpose") or "interview") == "intro_day" for row in candidate_rows)
    assert not any(
        (row.get("purpose") or "interview") == "interview"
        and str(row.get("status") or "").upper() in {"PENDING", "BOOKED", "CONFIRMED", "CONFIRMED_BY_CANDIDATE"}
        for row in candidate_rows
    )


@pytest.mark.asyncio
async def test_schedule_slot_blocked_when_intro_day_active(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777116,
        fio="Кандидат с ОД",
        city="Москва",
        username="api_intro_day_active",
        initial_status=CandidateStatus.INTRO_DAY_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Москва Рекрутер", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        intro_day_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="intro_day",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz=city.tz,
            candidate_city_id=city.id,
        )
        interview_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([intro_day_slot, interview_slot])
        await session.commit()
        await session.refresh(interview_slot)
        interview_slot_id = interview_slot.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/schedule-slot",
        json={"slot_id": interview_slot_id},
        follow_redirects=False,
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "candidate_has_active_assignment"
    assert "активная встреча" in (payload.get("message") or "").lower()

    async with async_session() as session:
        unchanged = await session.get(models.Slot, interview_slot_id)
    assert unchanged is not None
    assert unchanged.status == models.SlotStatus.FREE
    assert unchanged.candidate_tg_id is None


@pytest.mark.asyncio
async def test_api_kanban_move_accepts_canonical_target_column(admin_app, monkeypatch) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777117,
        fio="Кандидат канбан move",
        city="Москва",
        username="kanban_move_ok",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )
    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Kanban Move Recruiter", tg_chat_id=77711777, tz="Europe/Moscow")
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        interview_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
            purpose="interview",
        )
        session.add(interview_slot)
        await session.commit()

    async def _fake_set_slot_outcome(*_args, **_kwargs):
        return True, "Исход сохранён.", "success", None

    async def _legacy_should_not_run(*_args, **_kwargs):
        raise AssertionError("legacy update_candidate_status should not be used")

    monkeypatch.setattr("backend.apps.admin_ui.services.slots.set_slot_outcome", _fake_set_slot_outcome)
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.write_intents.update_candidate_status",
        _legacy_should_not_run,
    )

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/kanban-status",
        json={"target_column": "test2_sent"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "test2_sent"
    assert payload["intent"]["target_column"] == "test2_sent"
    assert payload["intent"]["intent_key"] == "send_to_test2"
    assert payload["candidate_state"]["operational_summary"]["kanban_column"] == "test2_sent"

    async with async_session() as session:
        refreshed = await session.get(User, candidate.id)
    assert refreshed is not None
    assert refreshed.candidate_status == CandidateStatus.TEST2_SENT


@pytest.mark.asyncio
async def test_api_kanban_move_test2_completed_uses_dedicated_use_case(admin_app, monkeypatch) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777121,
        fio="Кандидат канбан test2 completed",
        city="Москва",
        username="kanban_move_test2_completed",
        initial_status=CandidateStatus.TEST2_SENT,
    )
    async with async_session() as session:
        session.add(
            TestResult(
                user_id=candidate.id,
                raw_score=999,
                final_score=100.0,
                rating="TEST2",
                source="admin_test",
                total_time=120,
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    async def _legacy_should_not_run(*_args, **_kwargs):
        raise AssertionError("legacy update_candidate_status should not be used")

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.write_intents.update_candidate_status",
        _legacy_should_not_run,
    )

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/kanban-status",
        json={"target_column": "test2_completed"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == CandidateStatus.TEST2_COMPLETED.value
    assert payload["candidate_state"]["candidate_status_slug"] == CandidateStatus.TEST2_COMPLETED.value


@pytest.mark.asyncio
async def test_api_kanban_move_supports_legacy_target_status_compatibility(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777118,
        fio="Кандидат канбан compatibility",
        city="Москва",
        username="kanban_move_compatibility",
        initial_status=CandidateStatus.TEST2_SENT,
    )

    async with async_session() as session:
        session.add(
            TestResult(
                user_id=candidate.id,
                raw_score=999,
                final_score=100.0,
                rating="TEST2",
                source="admin_test",
                total_time=120,
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/kanban-status",
        json={"target_status": "test2_completed"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"]["compatibility_source"] == "legacy_target_status"
    assert payload["status"] == CandidateStatus.TEST2_COMPLETED.value


@pytest.mark.asyncio
async def test_api_kanban_move_rejects_unsupported_column_without_scheduling(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777119,
        fio="Кандидат канбан unsupported",
        city="Москва",
        username="kanban_move_unsupported",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/kanban-status",
        json={"target_column": "slot_pending"},
        follow_redirects=False,
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "unsupported_kanban_move"
    assert payload["intent"]["target_column"] == "slot_pending"
    assert payload["candidate_state"]["operational_summary"]["kanban_column"] == "incoming"
    assert payload["blocking_state"] == {
        "code": "unsupported_kanban_move",
        "category": "kanban_constraint",
        "severity": "error",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
        "issue_codes": [],
    }


@pytest.mark.asyncio
async def test_api_kanban_move_rejects_missing_interview_scheduling_with_blocking_state(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777122,
        fio="Кандидат канбан missing interview scheduling",
        city="Москва",
        username="kanban_move_missing_interview",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/kanban-status",
        json={"target_column": "interview_confirmed"},
        follow_redirects=False,
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "missing_interview_scheduling"
    assert payload["candidate_state"]["candidate_status_slug"] == CandidateStatus.WAITING_SLOT.value
    assert payload["blocking_state"] == {
        "code": "missing_interview_scheduling",
        "category": "scheduling",
        "severity": "warning",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": False,
        "issue_codes": [],
    }


@pytest.mark.asyncio
async def test_api_kanban_move_blocks_on_persisted_scheduling_conflict(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777123,
        fio="Кандидат канбан persisted conflict",
        city="Москва",
        username="kanban_move_persisted_conflict",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Kanban Persisted Conflict Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        stale_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        target_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([stale_slot, target_slot])
        await session.commit()
        await session.refresh(target_slot)

        session.add(
            models.SlotAssignment(
                slot_id=target_slot.id,
                recruiter_id=recruiter.id,
                candidate_id=candidate.candidate_id,
                candidate_tg_id=candidate.telegram_id,
                candidate_tz="Europe/Moscow",
                status=models.SlotAssignmentStatus.CONFIRMED,
                confirmed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/kanban-status",
        json={"target_column": "interview_confirmed"},
        follow_redirects=False,
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "scheduling_conflict"
    assert payload["intent"]["target_column"] == "interview_confirmed"
    assert payload["intent"]["resolution"] == "blocked_by_reconciliation"
    assert payload["candidate_state"]["operational_summary"]["has_scheduling_conflict"] is True
    assert payload["blocking_state"] == {
        "code": "scheduling_conflict",
        "category": "scheduling",
        "severity": "warning",
        "retryable": False,
        "recoverable": True,
        "manual_resolution_required": True,
        "issue_codes": ["scheduling_split_brain"],
    }


@pytest.mark.asyncio
async def test_api_manual_repair_resolve_to_assignment_clears_kanban_blocker(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777223,
        fio="Кандидат manual repair resolve",
        city="Москва",
        username="manual_repair_resolve",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Manual Repair Resolve Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        first_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        second_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add_all([first_slot, second_slot])
        await session.commit()
        await session.refresh(first_slot)
        await session.refresh(second_slot)

        first_assignment = models.SlotAssignment(
            slot_id=first_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=None,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        second_assignment = models.SlotAssignment(
            slot_id=second_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=None,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add_all([first_assignment, second_assignment])
        await session.commit()
        await session.refresh(first_assignment)
        await session.refresh(second_assignment)

        first_assignment_id = first_assignment.id
        second_assignment_id = second_assignment.id

    detail_before = await get_candidate_detail(candidate.id, principal=Principal(type="admin", id=-1))
    assert detail_before is not None
    assert detail_before["operational_summary"]["has_scheduling_conflict"] is True
    assert detail_before["candidate_next_action"]["primary_action"]["type"] == "repair_inconsistency"
    assert detail_before["scheduling_summary"]["repair_workflow"]["conflict_class"] == "multiple_active_assignments"

    repair_response = await _async_request(
        admin_app,
        "post",
        f"/api/slot-assignments/{first_assignment_id}/repair",
        json={
            "action": "resolve_to_active_assignment",
            "chosen_assignment_id": second_assignment_id,
            "confirmations": [
                "selected_assignment_is_canonical",
                "cancel_non_selected_active_assignments",
            ],
            "note": "keep latest offer",
        },
    )

    assert repair_response.status_code == 200
    repair_payload = repair_response.json()
    assert repair_payload["ok"] is True
    assert repair_payload["selected_assignment_id"] == second_assignment_id
    assert repair_payload["repair_workflow"]["policy"] == "not_needed"

    detail_after = await get_candidate_detail(candidate.id, principal=Principal(type="admin", id=-1))
    assert detail_after is not None
    assert detail_after["operational_summary"]["has_scheduling_conflict"] is False
    assert detail_after["scheduling_summary"]["repairability"] == "not_needed"


@pytest.mark.asyncio
async def test_api_manual_repair_denies_cross_owner_duplicate_assignments_with_structured_failure(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777224,
        fio="Кандидат manual repair deny",
        city="Москва",
        username="manual_repair_deny",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        first_recruiter = models.Recruiter(name="Manual Repair Deny Recruiter 1", tz="Europe/Moscow", active=True)
        second_recruiter = models.Recruiter(name="Manual Repair Deny Recruiter 2", tz="Europe/Moscow", active=True)
        first_recruiter.cities.append(city)
        second_recruiter.cities.append(city)
        session.add_all([city, first_recruiter, second_recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(first_recruiter)
        await session.refresh(second_recruiter)

        first_slot = models.Slot(
            recruiter_id=first_recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        second_slot = models.Slot(
            recruiter_id=second_recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add_all([first_slot, second_slot])
        await session.commit()
        await session.refresh(first_slot)
        await session.refresh(second_slot)

        first_assignment = models.SlotAssignment(
            slot_id=first_slot.id,
            recruiter_id=first_recruiter.id,
            candidate_id=None,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        second_assignment = models.SlotAssignment(
            slot_id=second_slot.id,
            recruiter_id=second_recruiter.id,
            candidate_id=None,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add_all([first_assignment, second_assignment])
        await session.commit()
        await session.refresh(first_assignment)
        await session.refresh(second_assignment)

        first_assignment_id = first_assignment.id
        second_assignment_id = second_assignment.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/slot-assignments/{first_assignment_id}/repair",
        json={
            "action": "resolve_to_active_assignment",
            "chosen_assignment_id": second_assignment_id,
            "confirmations": [
                "selected_assignment_is_canonical",
                "cancel_non_selected_active_assignments",
            ],
        },
    )

    assert response.status_code == 409
    payload = response.json()["detail"]
    assert payload["error"] == "repair_not_allowed"
    assert payload["failure_reason"]["code"] == "repair_not_allowed"
    assert payload["repair_workflow"]["conflict_class"] == "multiple_active_assignments"
    assert payload["repair_workflow"]["allowed_actions"] == []
    assert payload["repair_workflow"]["conflict_classes"][0]["supported"] is False


@pytest.mark.asyncio
async def test_api_slot_assignment_repair_restores_persisted_scheduling_conflict(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777124,
        fio="Кандидат repair api",
        city="Москва",
        username="repair_api_candidate",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Repair API Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        stale_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        target_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([stale_slot, target_slot])
        await session.commit()
        await session.refresh(stale_slot)
        await session.refresh(target_slot)

        assignment = models.SlotAssignment(
            slot_id=target_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.CONFIRMED,
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        stale_slot_id = stale_slot.id
        target_slot_id = target_slot.id
        assignment_id = assignment.id

    response = await _async_request(
        admin_app,
        "post",
        f"/api/slot-assignments/{assignment_id}/repair",
        json={"action": "assignment_authoritative"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "repaired"
    assert payload["released_slot_ids"] == [stale_slot_id]
    assert payload["integrity_state"] == "consistent"
    assert payload["repairability"] == "not_needed"
    assert payload["result_state"]["scheduling_summary"]["integrity_state"] == "consistent"
    assert payload["repair_workflow"]["policy"] == "not_needed"

    async with async_session() as session:
        stale_slot = await session.get(models.Slot, stale_slot_id)
        target_slot = await session.get(models.Slot, target_slot_id)
        assignment = await session.get(models.SlotAssignment, assignment_id)
        assert stale_slot is not None
        assert stale_slot.status == models.SlotStatus.FREE
        assert target_slot is not None
        assert target_slot.status == models.SlotStatus.BOOKED
        assert target_slot.candidate_id == candidate.candidate_id
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.CONFIRMED


@pytest.mark.asyncio
async def test_api_kanban_move_rejects_invalid_target_status(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777120,
        fio="Кандидат канбан invalid",
        city="Москва",
        username="kanban_move_invalid",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    response = await _async_request(
        admin_app,
        "post",
        f"/api/candidates/{candidate.id}/kanban-status",
        json={"target_status": "hired"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "invalid_kanban_column"
