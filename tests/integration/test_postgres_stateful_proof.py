from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import backend.core.messenger.registry as registry_mod
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.routers.candidate_portal import PORTAL_RESUME_COOKIE
from backend.apps.admin_ui.security import Principal
from backend.apps.admin_ui.services.candidates import get_candidate_detail
from backend.core import settings as settings_module
from backend.core.db import async_session, sync_engine
from backend.core.messenger.protocol import (
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.core.messenger.registry import MessengerRegistry
from backend.domain import models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.max_owner_preflight import collect_max_owner_preflight_report
from backend.domain.candidates.models import (
    CandidateInviteToken,
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    User,
)
from backend.domain.candidates.portal_service import (
    bump_candidate_portal_session_version,
    ensure_candidate_portal_session,
    sign_candidate_portal_token,
)
from backend.domain.candidates.services import create_candidate_invite_token
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City
from backend.domain.repositories import add_outbox_notification, claim_outbox_item_by_id
from backend.domain.slot_assignment_service import (
    confirm_slot_assignment,
    create_slot_assignment,
    request_reschedule,
)


pytestmark = [pytest.mark.integration, pytest.mark.postgres_proof]


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


class _DummyBotService:
    async def send_chat_message(self, telegram_id: int, text: str, reply_markup=None):
        return None


class _FakeMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def configure(self, **kwargs):
        return None

    async def get_bot_profile(self) -> dict[str, object]:
        return {"user": {"id": 312260558067, "name": "Attila MAX Bot"}}

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


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


@pytest.fixture(autouse=True)
def _require_postgres_backend() -> None:
    if str(os.getenv("TEST_USE_POSTGRES", "")).strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("postgres_proof runs only in the explicit PostgreSQL tranche")
    if sync_engine.url.get_backend_name() != "postgresql":
        pytest.skip("postgres_proof requires TEST_USE_POSTGRES=1 with a PostgreSQL DATABASE_URL")


@pytest.fixture
def admin_app(monkeypatch):
    bot_stub = _DummyBotService()

    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = bot_stub
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        app.state.notification_service = None
        app.state.notification_broker_available = False
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("ALLOW_LEGACY_BASIC", "1")
    monkeypatch.setenv("SESSION_SECRET", "postgres-proof-session-secret-0123456789abcdef")
    monkeypatch.setenv("MAX_BOT_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_max_token")
    monkeypatch.setenv("MAX_BOT_LINK_BASE", "https://max.ru/recruitsmartbot")
    monkeypatch.setenv("CRM_PUBLIC_URL", "https://crm.example.test")
    monkeypatch.setenv("CANDIDATE_PORTAL_PUBLIC_URL", "https://crm.example.test")
    settings_module.get_settings.cache_clear()
    from backend.domain.candidates.portal_service import invalidate_max_bot_profile_probe_cache

    invalidate_max_bot_profile_probe_cache()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        invalidate_max_bot_profile_probe_cache()
        settings_module.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    reg = MessengerRegistry()
    adapter = _FakeMaxAdapter()
    reg.register(adapter)
    monkeypatch.setattr(registry_mod, "_registry", reg)
    return adapter


@pytest.fixture
def max_client(monkeypatch, _isolated_registry):
    settings_module.get_settings.cache_clear()
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

    async def _noop_bootstrap_messenger_adapters(**kwargs):
        return None

    try:
        with patch("backend.core.messenger.bootstrap.bootstrap_messenger_adapters", _noop_bootstrap_messenger_adapters):
            with patch("backend.apps.max_bot.app.get_settings", return_value=settings):
                from backend.apps.max_bot.app import create_app as create_max_app

                app = create_max_app()
                app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment]
                yield TestClient(app, raise_server_exceptions=False)
    finally:
        settings_module.get_settings.cache_clear()


async def _async_request(app, method: str, path: str, **kwargs):
    def _call():
        with TestClient(app) as client:
            client.auth = ("admin", "admin")
            headers = dict(kwargs.pop("headers", {}) or {})
            if method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
                if "x-csrf-token" not in {key.lower() for key in headers}:
                    headers["x-csrf-token"] = client.get("/api/csrf").json()["token"]
            if headers:
                kwargs["headers"] = headers
            return client.request(method, path, **kwargs)

    return await asyncio.to_thread(_call)


async def _load_chat_messages(candidate_id: int) -> list[ChatMessage]:
    async with async_session() as session:
        rows = await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.candidate_id == candidate_id)
            .order_by(ChatMessage.id.asc())
        )
        return list(rows.all())


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


async def _count_candidates_by_uuid(candidate_uuid: str) -> int:
    async with async_session() as session:
        return int(
            await session.scalar(select(func.count()).select_from(User).where(User.candidate_id == candidate_uuid))
            or 0
        )


async def _load_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _load_slot(slot_id: int) -> models.Slot | None:
    async with async_session() as session:
        return await session.get(models.Slot, slot_id)


async def _create_recruiter(name: str, *, city_name: str) -> int:
    async with async_session() as session:
        city = models.City(name=city_name, tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name=name, tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        return recruiter.id


def _to_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _post_text(client: TestClient, *, max_user_id: str, text: str, start_payload: str | None = None):
    body = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": max_user_id, "name": "Max Candidate"},
            "body": {"text": text},
        },
    }
    if start_payload:
        body["payload"] = start_payload
    return client.post(
        "/webhook",
        json=body,
        headers={"X-Max-Bot-Api-Secret": "test_secret"},
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


async def _seed_portal_flow(
    *,
    city_name: str,
    recruiter_name: str,
    telegram_id: int,
    fio: str,
) -> dict[str, int | str]:
    async with async_session() as session:
        city = City(name=city_name, tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name=recruiter_name, tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        candidate = User(
            fio=fio,
            telegram_id=telegram_id,
            telegram_user_id=telegram_id,
            city=None,
            phone=None,
            desired_position="Менеджер по работе с клиентами",
            hh_vacancy_id="12345",
            source="telegram",
        )
        session.add(candidate)
        await session.flush()

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        return {
            "candidate_id": int(candidate.id),
            "candidate_uuid": str(candidate.candidate_id),
            "slot_id": int(slot.id),
        }


@pytest.mark.asyncio
async def test_postgres_slot_propose_assigns_pending_offer(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=880110,
        fio="PG Propose Candidate",
        city="Алматы",
        username="pg_propose_candidate",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        city = models.City(name="Алматы", tz="Asia/Almaty", active=True)
        recruiter = models.Recruiter(name="PG Recruiter", tz="Asia/Almaty", active=True)
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
async def test_postgres_confirm_then_request_reschedule_preserves_assignment_integrity() -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=880120,
        fio="PG Confirm Reschedule Candidate",
        city="Казань",
        username="pg_confirm_reschedule",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        city = models.City(name="Казань", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="PG Kazan Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2032, 7, 10, 9, 0, tzinfo=timezone.utc),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
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
        created_by="postgres-proof",
    )
    assert offer.ok is True

    assignment_id = int(offer.payload["slot_assignment_id"])
    confirm_token = str(offer.payload["confirm_token"])
    reschedule_token = str(offer.payload["reschedule_token"])

    confirm = await confirm_slot_assignment(
        assignment_id=assignment_id,
        action_token=confirm_token,
        candidate_tg_id=candidate.telegram_id,
    )
    assert confirm.ok is True
    assert confirm.status == "confirmed"

    reschedule = await request_reschedule(
        assignment_id=assignment_id,
        action_token=reschedule_token,
        candidate_tg_id=candidate.telegram_id,
        requested_start_utc=datetime(2032, 7, 11, 11, 0, tzinfo=timezone.utc),
        requested_end_utc=datetime(2032, 7, 11, 13, 0, tzinfo=timezone.utc),
        requested_tz="Europe/Moscow",
        comment=None,
    )
    assert reschedule.ok is True

    async with async_session() as session:
        slot = await session.get(models.Slot, slot_id)
        assignment = await session.get(models.SlotAssignment, assignment_id)
        request = await session.scalar(
            select(models.RescheduleRequest).where(
                models.RescheduleRequest.slot_assignment_id == assignment_id,
                models.RescheduleRequest.status == models.RescheduleRequestStatus.PENDING,
            )
        )

    assert slot is not None
    assert slot.status == models.SlotStatus.BOOKED
    assert slot.candidate_id == candidate.candidate_id
    assert assignment is not None
    assert assignment.status == models.SlotAssignmentStatus.RESCHEDULE_REQUESTED
    assert assignment.status_before_reschedule == models.SlotAssignmentStatus.CONFIRMED
    assert request is not None
    assert _to_aware_utc(request.requested_start_utc) == datetime(2032, 7, 11, 11, 0, tzinfo=timezone.utc)
    assert _to_aware_utc(request.requested_end_utc) == datetime(2032, 7, 11, 13, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_postgres_assignment_authoritative_repair_releases_stale_slot(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=880130,
        fio="PG Repair Candidate",
        city="Москва",
        username="pg_repair_candidate",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="PG Repair Recruiter", tz="Europe/Moscow", active=True)
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

    detail_before = await get_candidate_detail(candidate.id, principal=Principal(type="admin", id=-1))
    assert detail_before is not None
    assert detail_before["scheduling_summary"]["integrity_state"] == "needs_manual_repair"
    assert detail_before["scheduling_summary"]["write_owner"] == "slot_assignment"

    response = await _async_request(
        admin_app,
        "post",
        f"/api/slot-assignments/{assignment_id}/repair",
        json={"action": "assignment_authoritative"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "repaired"
    assert payload["released_slot_ids"] == [stale_slot_id]
    assert payload["integrity_state"] == "consistent"

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


def test_postgres_max_duplicate_owner_ambiguity_fails_closed(
    max_client: TestClient,
    _isolated_registry: _FakeMaxAdapter,
) -> None:
    first_uuid = str(uuid4())
    second_uuid = str(uuid4())

    async def _seed() -> tuple[int, int]:
        async with async_session() as session:
            first = User(
                candidate_id=first_uuid,
                fio="MAX duplicate owner 1",
                phone="+79991112233",
                city="Москва Existing",
                source="seed",
                messenger_platform="max",
                max_user_id="mx-duplicate",
            )
            second = User(
                candidate_id=second_uuid,
                fio="MAX duplicate owner 2",
                phone="+79991112234",
                city="Москва Existing",
                source="seed",
                messenger_platform="telegram",
                max_user_id=" mx-duplicate ",
            )
            session.add_all([first, second])
            await session.commit()
            await session.refresh(first)
            await session.refresh(second)
            return int(first.id), int(second.id)

    first_id, second_id = asyncio.run(_seed())

    response = _post_text(
        max_client,
        max_user_id="mx-duplicate",
        text="Это сообщение не должно пройти из-за ambiguity",
    )

    assert response.status_code == 200
    assert "ошибки привязки" in str(_isolated_registry.calls[-1]["text"]).lower()
    assert asyncio.run(_load_chat_messages(first_id)) == []
    assert asyncio.run(_load_chat_messages(second_id)) == []
    assert asyncio.run(_load_candidate_by_max("mx-duplicate")) is not None


def test_postgres_portal_resume_cookie_version_mismatch_requires_new_link(admin_app) -> None:
    seeded: dict[str, int | str] = {}

    async def _seed_portal_flow() -> dict[str, int | str]:
        async with async_session() as session:
            city = City(name="Portal PG City", tz="Europe/Moscow", active=True)
            recruiter = models.Recruiter(name="Portal PG Recruiter", tz="Europe/Moscow", active=True)
            recruiter.cities.append(city)
            session.add_all([city, recruiter])
            await session.flush()

            candidate = User(
                fio="Portal PG Candidate",
                telegram_id=880140,
                telegram_user_id=880140,
                city=None,
                phone=None,
                desired_position="Менеджер по работе с клиентами",
                hh_vacancy_id="12345",
                source="telegram",
            )
            session.add(candidate)
            await session.flush()

            slot = models.Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=datetime.now(timezone.utc) + timedelta(days=1),
                duration_min=60,
                status=models.SlotStatus.FREE,
                purpose="interview",
                tz_name="Europe/Moscow",
            )
            session.add(slot)
            await session.commit()
            return {
                "candidate_id": int(candidate.id),
                "candidate_uuid": str(candidate.candidate_id),
            }

    with TestClient(admin_app) as client:
        seeded = asyncio.run(_seed_portal_flow())
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="web",
            source_channel="portal",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200

        resume_cookie = client.cookies.get(PORTAL_RESUME_COOKIE)
        assert resume_cookie

        async def _bump_version() -> None:
            async with async_session() as session:
                async with session.begin():
                    await bump_candidate_portal_session_version(
                        session,
                        candidate_id=int(seeded["candidate_id"]),
                    )

        asyncio.run(_bump_version())
        client.cookies.clear()
        client.cookies.set(PORTAL_RESUME_COOKIE, resume_cookie)

        response = client.get("/api/candidate/journey")

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["state"] == "needs_new_link"
    assert detail["code"] == "portal_session_version_mismatch"

    async def _load_journey_version() -> int:
        async with async_session() as session:
            candidate = await session.get(User, int(seeded["candidate_id"]))
            assert candidate is not None
            journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
            assert journey is not None
            return int(journey.session_version or 1)

    assert asyncio.run(_load_journey_version()) >= 2


@pytest.mark.asyncio
async def test_postgres_manual_repair_denies_cross_owner_duplicate_assignments(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=880150,
        fio="PG Manual Repair Deny",
        city="Москва",
        username="pg_manual_repair_deny",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        first_recruiter = models.Recruiter(name="PG Manual Deny Recruiter 1", tz="Europe/Moscow", active=True)
        second_recruiter = models.Recruiter(name="PG Manual Deny Recruiter 2", tz="Europe/Moscow", active=True)
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
        follow_redirects=False,
    )

    assert repair_response.status_code == 409
    payload = repair_response.json()["detail"]
    assert payload["error"] == "repair_not_allowed"
    assert payload["failure_reason"]["code"] == "repair_not_allowed"
    assert payload["repair_workflow"]["conflict_class"] == "multiple_active_assignments"
    assert payload["repair_workflow"]["allowed_actions"] == []


@pytest.mark.asyncio
async def test_postgres_kanban_move_blocks_on_persisted_scheduling_conflict(admin_app) -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=880160,
        fio="PG Kanban Persisted Conflict",
        city="Москва",
        username="pg_kanban_conflict",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="PG Kanban Conflict Recruiter", tz="Europe/Moscow", active=True)
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
    assert payload["intent"]["resolution"] == "blocked_by_reconciliation"
    assert payload["blocking_state"]["manual_resolution_required"] is True
    assert payload["blocking_state"]["issue_codes"] == ["scheduling_split_brain"]


def test_postgres_max_same_invite_same_user_is_idempotent(
    max_client: TestClient,
    _isolated_registry: _FakeMaxAdapter,
) -> None:
    candidate_uuid = str(uuid4())

    async def _seed_candidate_only() -> None:
        async with async_session() as session:
            candidate = User(
                candidate_id=candidate_uuid,
                fio="MAX Invite Candidate",
                phone="+79991112233",
                city="Москва Existing",
                source="seed",
            )
            session.add(candidate)
            await session.commit()

    asyncio.run(_seed_candidate_only())
    invite = asyncio.run(create_candidate_invite_token(candidate_uuid, channel="max"))
    max_user_id = f"55{uuid4().hex[:10]}"

    first = _post_bot_started(max_client, max_user_id=max_user_id, start_payload=invite.token)
    second = _post_bot_started(max_client, max_user_id=max_user_id, start_payload=invite.token)

    assert first.status_code == 200
    assert second.status_code == 200

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == max_user_id
    assert asyncio.run(_count_candidates_by_uuid(candidate_uuid)) == 1


def test_postgres_max_same_invite_different_user_conflicts_without_duplicate_rows(
    max_client: TestClient,
    _isolated_registry: _FakeMaxAdapter,
) -> None:
    candidate_uuid = str(uuid4())

    async def _seed_candidate_only() -> None:
        async with async_session() as session:
            candidate = User(
                candidate_id=candidate_uuid,
                fio="MAX Conflict Candidate",
                phone="+79991112233",
                city="Москва Existing",
                source="seed",
            )
            session.add(candidate)
            await session.commit()

    asyncio.run(_seed_candidate_only())
    invite = asyncio.run(create_candidate_invite_token(candidate_uuid, channel="max"))
    first_user_id = f"44{uuid4().hex[:10]}"
    second_user_id = f"45{uuid4().hex[:10]}"

    assert _post_bot_started(max_client, max_user_id=first_user_id, start_payload=invite.token).status_code == 200
    response = _post_bot_started(max_client, max_user_id=second_user_id, start_payload=invite.token)

    assert response.status_code == 200
    assert "уже привязана" in str(_isolated_registry.calls[-1]["text"]).lower()

    candidate = asyncio.run(_load_candidate_by_uuid(candidate_uuid))
    assert candidate is not None
    assert candidate.max_user_id == first_user_id
    assert asyncio.run(_count_candidates_by_uuid(candidate_uuid)) == 1


def test_postgres_restart_candidate_portal_creates_new_active_journey(admin_app) -> None:
    candidate = asyncio.run(
        candidate_services.create_or_update_user(
            telegram_id=880180,
            fio="PG Portal Restart",
            city="Москва",
            username="pg_portal_restart",
            initial_status=CandidateStatus.TEST1_COMPLETED,
        )
    )

    first_link = asyncio.run(
        _async_request(
            admin_app,
            "post",
            f"/api/candidates/{candidate.id}/channels/max-link",
            follow_redirects=False,
        )
    )
    assert first_link.status_code == 200
    first_payload = first_link.json()

    restart_response = asyncio.run(
        _async_request(
            admin_app,
            "post",
            f"/api/candidates/{candidate.id}/portal/restart",
            follow_redirects=False,
        )
    )
    assert restart_response.status_code == 200
    payload = restart_response.json()
    assert payload["journey"]["restarted"] is True
    assert payload["journey"]["id"] != first_payload["journey"]["id"]
    assert payload["invite"]["rotated"] is True

    async def _load_state() -> tuple[list[CandidateJourneySession], User | None]:
        async with async_session() as session:
            journeys = (
                await session.scalars(
                    select(CandidateJourneySession)
                    .where(CandidateJourneySession.candidate_id == candidate.id)
                    .order_by(CandidateJourneySession.id.asc())
                )
            ).all()
            refreshed_candidate = await session.get(User, candidate.id)
            return list(journeys), refreshed_candidate

    journeys, refreshed_candidate = asyncio.run(_load_state())
    assert len(journeys) >= 2
    assert journeys[-1].status == "active"
    assert journeys[0].status == "abandoned"
    assert refreshed_candidate is not None
    assert refreshed_candidate.candidate_status == CandidateStatus.LEAD


def test_postgres_restart_candidate_portal_blocks_confirmed_interview(admin_app) -> None:
    recruiter_id = asyncio.run(_create_recruiter("PG Restart Slot Recruiter", city_name="Самара"))
    candidate = asyncio.run(
        candidate_services.create_or_update_user(
            telegram_id=880181,
            fio="PG Portal Restart Blocked",
            city="Самара",
            username="pg_portal_restart_blocked",
            initial_status=CandidateStatus.TEST1_COMPLETED,
        )
    )

    async def _seed_confirmed_slot() -> None:
        async with async_session() as session:
            city = await session.scalar(select(City).where(City.name == "Самара"))
            assert city is not None
            slot = models.Slot(
                recruiter_id=recruiter_id,
                city_id=city.id,
                start_utc=datetime.now(timezone.utc) + timedelta(days=1),
                duration_min=60,
                status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
                purpose="interview",
                candidate_id=candidate.candidate_id,
                candidate_tg_id=candidate.telegram_id,
                candidate_fio=candidate.fio,
                candidate_tz="Europe/Moscow",
                candidate_city_id=city.id,
                tz_name="Europe/Moscow",
            )
            session.add(slot)
            await session.commit()

    asyncio.run(_seed_confirmed_slot())
    response = asyncio.run(
        _async_request(
            admin_app,
            "post",
            f"/api/candidates/{candidate.id}/portal/restart",
            follow_redirects=False,
        )
    )

    assert response.status_code == 409
    assert "подтверждено собеседование" in response.json()["detail"]["message"].lower()


def test_postgres_candidate_portal_journey_restores_from_resume_cookie_after_browser_restart(admin_app) -> None:
    seeded = asyncio.run(
        _seed_portal_flow(
            city_name="Portal Restore City",
            recruiter_name="Portal Restore Recruiter",
            telegram_id=880190,
            fio="Portal Restore Candidate",
        )
    )

    with TestClient(admin_app) as client:
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200

        resume_cookie = client.cookies.get(PORTAL_RESUME_COOKIE)
        assert resume_cookie
        client.cookies.clear()
        client.cookies.set(PORTAL_RESUME_COOKIE, resume_cookie)

        response = client.get("/api/candidate/journey")

    assert response.status_code == 200
    payload = response.json()
    assert payload["journey"]["current_step"] == "profile"
    assert payload["candidate"]["fio"] == "Portal Restore Candidate"


def test_postgres_candidate_portal_slot_reserve_blocked_when_assignment_owns_scheduling(admin_app) -> None:
    seeded = asyncio.run(
        _seed_portal_flow(
            city_name="Portal Assignment City",
            recruiter_name="Portal Assignment Recruiter",
            telegram_id=880191,
            fio="Portal Assignment Candidate",
        )
    )
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None

    offer = asyncio.run(
        create_slot_assignment(
            slot_id=int(seeded["slot_id"]),
            candidate_id=str(seeded["candidate_uuid"]),
            candidate_tg_id=int(candidate.telegram_id or candidate.telegram_user_id or 0),
            candidate_tz="Europe/Moscow",
            created_by="postgres-proof",
        )
    )
    assert offer.ok is True

    with TestClient(admin_app) as client:
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200

        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": int(seeded["slot_id"])},
        )

    assert reserve.status_code == 409
    assert "управляется через предложение времени" in reserve.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_postgres_max_owner_preflight_classifies_safe_auto_cleanup_duplicate_group() -> None:
    async with async_session() as session:
        primary = User(
            candidate_id=str(uuid4()),
            fio="MAX safe primary",
            phone="+79990000010",
            city="Москва",
            source="max_bot_public",
            messenger_platform="max",
            max_user_id="mx-safe-owner",
            last_activity=datetime.now(timezone.utc),
        )
        secondary = User(
            candidate_id=str(uuid4()),
            fio="MAX safe secondary",
            phone="+79990000011",
            city="Москва",
            source="seed",
            messenger_platform="telegram",
            max_user_id=" mx-safe-owner ",
            last_activity=datetime.now(timezone.utc),
        )
        blank_owner = User(
            candidate_id=str(uuid4()),
            fio="MAX blank owner",
            phone="+79990000012",
            city="Москва",
            source="seed",
            messenger_platform="telegram",
            max_user_id="   ",
            last_activity=datetime.now(timezone.utc),
        )
        session.add_all([primary, secondary, blank_owner])
        await session.commit()
        await session.refresh(primary)
        await session.refresh(blank_owner)

        session.add(
            ChatMessage(
                candidate_id=primary.id,
                direction=ChatMessageDirection.INBOUND.value,
                channel="max",
                text="MAX message",
                status=ChatMessageStatus.RECEIVED.value,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            CandidateInviteToken(
                candidate_id=str(primary.candidate_id),
                token=f"mx_{uuid4().hex}",
                channel="max",
                status="used",
                used_by_external_id="mx-safe-owner",
                used_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            CandidateJourneySession(
                candidate_id=primary.id,
                entry_channel="max",
                status=CandidateJourneySessionStatus.ACTIVE.value,
                current_step_key="screening",
                started_at=datetime.now(timezone.utc),
                last_activity_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

        report = await collect_max_owner_preflight_report(session, sample_limit=20)

    assert report.ready_for_unique_index is False
    group = next(item for item in report.duplicate_groups if item.normalized_max_user_id == "mx-safe-owner")
    assert group.cleanup_bucket == "safe_auto_cleanup"
    assert group.authoritative_candidate_pk == primary.id
    assert "single_authoritative_record" in group.reason_codes
    blank_anomaly = next(item for item in report.whitespace_anomalies if item.record.candidate_pk == blank_owner.id)
    assert blank_anomaly.cleanup_bucket == "safe_auto_cleanup"
    assert report.blast_radius.ownership_conflicts == 0


@pytest.mark.asyncio
async def test_postgres_max_owner_preflight_marks_manual_review_for_conflicting_evidence() -> None:
    async with async_session() as session:
        left = User(
            candidate_id=str(uuid4()),
            fio="MAX manual left",
            phone="+79990000013",
            city="Москва",
            source="seed",
            messenger_platform="max",
            max_user_id="mx-manual",
            last_activity=datetime.now(timezone.utc),
        )
        right = User(
            candidate_id=str(uuid4()),
            fio="MAX manual right",
            phone="+79990000014",
            city="Москва",
            source="seed",
            messenger_platform="max",
            max_user_id="mx-manual",
            last_activity=datetime.now(timezone.utc),
        )
        mismatch = User(
            candidate_id=str(uuid4()),
            fio="MAX mismatch",
            phone="+79990000015",
            city="Москва",
            source="seed",
            messenger_platform="telegram",
            max_user_id=" mx-mismatch ",
            last_activity=datetime.now(timezone.utc),
        )
        session.add_all([left, right, mismatch])
        await session.commit()
        await session.refresh(mismatch)

        session.add_all(
            [
                ChatMessage(
                    candidate_id=left.id,
                    direction=ChatMessageDirection.INBOUND.value,
                    channel="max",
                    text="MAX message",
                    status=ChatMessageStatus.RECEIVED.value,
                    created_at=datetime.now(timezone.utc),
                ),
                ChatMessage(
                    candidate_id=right.id,
                    direction=ChatMessageDirection.OUTBOUND.value,
                    channel="max",
                    text="MAX reply",
                    status=ChatMessageStatus.RECEIVED.value,
                    created_at=datetime.now(timezone.utc),
                ),
                CandidateInviteToken(
                    candidate_id=str(right.candidate_id),
                    token=f"mx_{uuid4().hex}",
                    channel="max",
                    status="used",
                    used_by_external_id="mx-manual",
                    used_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                ),
                CandidateInviteToken(
                    candidate_id=str(mismatch.candidate_id),
                    token=f"mx_{uuid4().hex}",
                    channel="max",
                    status="used",
                    used_by_external_id="mx-other-owner",
                    used_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                ),
            ]
        )
        await session.commit()

        report = await collect_max_owner_preflight_report(session, sample_limit=20)

    group = next(item for item in report.duplicate_groups if item.normalized_max_user_id == "mx-manual")
    assert group.cleanup_bucket == "manual_review_only"
    assert "multiple_records_have_max_evidence" in group.reason_codes
    mismatch_anomaly = next(item for item in report.whitespace_anomalies if item.record.candidate_pk == mismatch.id)
    assert mismatch_anomaly.cleanup_bucket == "manual_review_only"
    assert "invite_used_by_mismatch" in mismatch_anomaly.reason_codes
    assert any(item.conflict_kind == "invite_used_by_mismatch" for item in report.ownership_conflicts)


@pytest.mark.asyncio
async def test_postgres_outbox_claim_is_single_consumer() -> None:
    async with async_session() as session:
        city = City(name="Outbox PG City", tz="UTC", active=True)
        recruiter = models.Recruiter(name="Outbox PG Recruiter", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=987654321,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot.id,
        candidate_tg_id=slot.candidate_tg_id,
        payload={"reminder_kind": "confirm_2h"},
    )

    first = await claim_outbox_item_by_id(entry.id)
    second = await claim_outbox_item_by_id(entry.id)

    assert first is not None
    assert first.id == entry.id
    assert second is None
