import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.security import Principal, require_principal
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain import models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.status import CandidateStatus


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def recruiter_scoped_app(monkeypatch) -> Any:
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


async def _request_with_recruiter_principal(
    app,
    recruiter_id: int,
    method: str,
    path: str,
    **kwargs,
):
    def _call() -> Any:
        app.dependency_overrides[require_principal] = lambda: Principal(type="recruiter", id=recruiter_id)
        try:
            with TestClient(app) as client:
                headers = dict(kwargs.pop("headers", {}) or {})
                if method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
                    header_keys = {key.lower() for key in headers}
                    if "x-csrf-token" not in header_keys:
                        csrf = client.get("/api/csrf")
                        assert csrf.status_code == 200
                        token = (csrf.json() or {}).get("token") or ""
                        assert token
                        headers["x-csrf-token"] = str(token)
                if headers:
                    kwargs["headers"] = headers
                return client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.pop(require_principal, None)

    return await asyncio.to_thread(_call)


@pytest.mark.asyncio
async def test_recruiter_can_schedule_intro_day_for_self_even_if_city_has_other_default(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990001,
        fio="Шеншин Михаил Алексеевич",
        city="Москва",
        username="shenshin_test",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        primary = models.Recruiter(name="Primary Recruiter", tz="Europe/Moscow", active=True)
        actor = models.Recruiter(name="Actor Recruiter", tz="Europe/Moscow", active=True)
        primary.cities.append(city)
        actor.cities.append(city)
        session.add_all([city, primary, actor])
        await session.flush()
        city.responsible_recruiter_id = primary.id
        await session.commit()
        await session.refresh(actor)

        actor_id = actor.id

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        actor_id,
        "post",
        f"/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-23",
            "time": "10:00",
            "custom_message": "Тестовое приглашение",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("ok") is True

    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot)
            .where(models.Slot.candidate_tg_id == candidate.telegram_id)
            .order_by(models.Slot.id.desc())
        )
        assert slot is not None
        assert slot.recruiter_id == actor_id
        assert (slot.purpose or "").lower() == "intro_day"


@pytest.mark.asyncio
async def test_recruiter_can_schedule_intro_day_via_api_without_recruiter_id(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990002,
        fio="Шеншин Михаил Алексеевич",
        city="Москва",
        username="shenshin_test_api",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        primary = models.Recruiter(name="Primary Recruiter API", tz="Europe/Moscow", active=True)
        actor = models.Recruiter(name="Actor Recruiter API", tz="Europe/Moscow", active=True)
        primary.cities.append(city)
        actor.cities.append(city)
        session.add_all([city, primary, actor])
        await session.flush()
        city.responsible_recruiter_id = primary.id
        await session.commit()
        await session.refresh(actor)
        actor_id = actor.id

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        actor_id,
        "post",
        f"/api/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-23",
            "time": "10:00",
            "custom_message": "Тестовое приглашение",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("ok") is True

    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot)
            .where(models.Slot.candidate_tg_id == candidate.telegram_id)
            .order_by(models.Slot.id.desc())
        )
        assert slot is not None
        assert slot.recruiter_id == actor_id
        assert (slot.purpose or "").lower() == "intro_day"


@pytest.mark.asyncio
async def test_candidates_route_uses_city_intro_day_template_when_custom_message_empty(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990021,
        fio="Шеншин Михаил Алексеевич",
        city="Волгоград",
        username="intro_city_template_web",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(
            name="Волгоград",
            tz="Europe/Moscow",
            active=True,
            intro_address="Волгоград, пр. Ленина, 1",
            contact_name="Ольга",
            contact_phone="+79990000000",
        )
        recruiter = models.Recruiter(name="City Template Recruiter Web", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()
        now = datetime.now(timezone.utc)
        session.add(
            models.MessageTemplate(
                key="intro_day_invitation",
                locale="ru",
                channel="tg",
                city_id=city.id,
                body_md="Здравствуйте, [Имя]! Ждём вас [Дата] в [Время]. Адрес: {intro_address}. Контакт: {intro_contact}.",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-23",
            "time": "10:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json().get("ok") is True

    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot)
            .where(models.Slot.candidate_tg_id == candidate.telegram_id)
            .where(models.Slot.purpose == "intro_day")
            .order_by(models.Slot.id.desc())
        )
        assert slot is not None
        outbox = await session.scalar(
            select(models.OutboxNotification)
            .where(models.OutboxNotification.booking_id == slot.id)
            .where(models.OutboxNotification.type == "intro_day_invitation")
            .order_by(models.OutboxNotification.id.desc())
        )

    assert outbox is not None
    assert (outbox.payload_json or {})["custom_message"] == (
        "Здравствуйте, Михаил! Ждём вас 23.02 в 10:00. Адрес: Волгоград, пр. Ленина, 1. "
        "Контакт: Ольга, +79990000000."
    )


@pytest.mark.asyncio
async def test_api_route_uses_city_intro_day_template_when_custom_message_empty(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990022,
        fio="Шеншин Михаил Алексеевич",
        city="Волгоград",
        username="intro_city_template_api",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(
            name="Волгоград",
            tz="Europe/Moscow",
            active=True,
            intro_address="Волгоград, пр. Ленина, 1",
            contact_name="Ольга",
            contact_phone="+79990000000",
        )
        recruiter = models.Recruiter(name="City Template Recruiter API", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()
        now = datetime.now(timezone.utc)
        session.add(
            models.MessageTemplate(
                key="intro_day_invitation",
                locale="ru",
                channel="tg",
                city_id=city.id,
                body_md="Здравствуйте, [Имя]! Ждём вас [Дата] в [Время]. Адрес: {intro_address}. Контакт: {intro_contact}.",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/api/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-23",
            "time": "10:00",
        },
    )

    assert response.status_code == 200
    assert response.json().get("ok") is True

    async with async_session() as session:
        slot = await session.scalar(
            select(models.Slot)
            .where(models.Slot.candidate_tg_id == candidate.telegram_id)
            .where(models.Slot.purpose == "intro_day")
            .order_by(models.Slot.id.desc())
        )
        assert slot is not None
        outbox = await session.scalar(
            select(models.OutboxNotification)
            .where(models.OutboxNotification.booking_id == slot.id)
            .where(models.OutboxNotification.type == "intro_day_invitation")
            .order_by(models.OutboxNotification.id.desc())
        )

    assert outbox is not None
    assert (outbox.payload_json or {})["custom_message"] == (
        "Здравствуйте, Михаил! Ждём вас 23.02 в 10:00. Адрес: Волгоград, пр. Ленина, 1. "
        "Контакт: Ольга, +79990000000."
    )


@pytest.mark.asyncio
async def test_recruiter_can_schedule_intro_day_twice_same_time_via_candidates_route(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990003,
        fio="Тест Повтор",
        city="Москва",
        username="intro_repeat_web",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Repeat Recruiter Web", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    payload = {
        "date": "2026-02-23",
        "time": "10:00",
        "custom_message": "Тестовое приглашение",
    }
    first = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/candidates/{candidate.id}/schedule-intro-day",
        json=payload,
        follow_redirects=False,
    )
    second = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/candidates/{candidate.id}/schedule-intro-day",
        json=payload,
        follow_redirects=False,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json().get("ok") is True
    assert second.json().get("ok") is True

    async with async_session() as session:
        slots = (
            await session.execute(
                select(models.Slot)
                .where(models.Slot.candidate_tg_id == candidate.telegram_id)
                .where(models.Slot.recruiter_id == recruiter_id)
                .where(models.Slot.purpose == "intro_day")
            )
        ).scalars().all()
    assert len(slots) == 2


@pytest.mark.asyncio
async def test_recruiter_can_schedule_intro_day_twice_same_time_via_api_route(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990004,
        fio="Тест Повтор API",
        city="Москва",
        username="intro_repeat_api",
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Repeat Recruiter API", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    payload = {
        "date": "2026-02-23",
        "time": "10:00",
        "custom_message": "Тестовое приглашение",
    }
    first = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/api/candidates/{candidate.id}/schedule-intro-day",
        json=payload,
    )
    second = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/api/candidates/{candidate.id}/schedule-intro-day",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json().get("ok") is True
    assert second.json().get("ok") is True

    async with async_session() as session:
        slots = (
            await session.execute(
                select(models.Slot)
                .where(models.Slot.candidate_tg_id == candidate.telegram_id)
                .where(models.Slot.recruiter_id == recruiter_id)
                .where(models.Slot.purpose == "intro_day")
            )
        ).scalars().all()
    assert len(slots) == 2


@pytest.mark.asyncio
async def test_schedule_intro_day_cancels_active_interview_slot_via_candidates_route(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990005,
        fio="Тест Отмена Собеса Web",
        city="Москва",
        username="intro_cancel_web",
        initial_status=CandidateStatus.INTERVIEW_CONFIRMED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Cancel Recruiter Web", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()
        interview_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="interview",
            tz_name="Europe/Moscow",
            start_utc=datetime(2026, 2, 24, 9, 0, tzinfo=timezone.utc),
            duration_min=30,
            status=models.SlotStatus.CONFIRMED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(interview_slot)
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id
        interview_start_utc = interview_slot.start_utc

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-25",
            "time": "10:00",
            "custom_message": "Назначаем ОД",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json().get("ok") is True

    async with async_session() as session:
        old_slot = await session.scalar(
            select(models.Slot).where(
                models.Slot.recruiter_id == recruiter_id,
                models.Slot.start_utc == interview_start_utc,
                models.Slot.purpose == "interview",
            )
        )
        assert old_slot is None
        refreshed_candidate = await session.get(User, candidate.id)
        assert refreshed_candidate is not None
        assert refreshed_candidate.candidate_status == CandidateStatus.INTRO_DAY_SCHEDULED


@pytest.mark.asyncio
async def test_schedule_intro_day_cancels_active_interview_slot_via_api_route(
    recruiter_scoped_app,
) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=990006,
        fio="Тест Отмена Собеса API",
        city="Москва",
        username="intro_cancel_api",
        initial_status=CandidateStatus.INTERVIEW_CONFIRMED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Cancel Recruiter API", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()
        interview_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="interview",
            tz_name="Europe/Moscow",
            start_utc=datetime(2026, 2, 24, 11, 0, tzinfo=timezone.utc),
            duration_min=30,
            status=models.SlotStatus.BOOKED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(interview_slot)
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id
        interview_start_utc = interview_slot.start_utc

    response = await _request_with_recruiter_principal(
        recruiter_scoped_app,
        recruiter_id,
        "post",
        f"/api/candidates/{candidate.id}/schedule-intro-day",
        json={
            "date": "2026-02-25",
            "time": "12:00",
            "custom_message": "Назначаем ОД API",
        },
    )

    assert response.status_code == 200
    assert response.json().get("ok") is True

    async with async_session() as session:
        old_slot = await session.scalar(
            select(models.Slot).where(
                models.Slot.recruiter_id == recruiter_id,
                models.Slot.start_utc == interview_start_utc,
                models.Slot.purpose == "interview",
            )
        )
        assert old_slot is None
        refreshed_candidate = await session.get(User, candidate.id)
        assert refreshed_candidate is not None
        assert refreshed_candidate.candidate_status == CandidateStatus.INTRO_DAY_SCHEDULED
