from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import time

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.domain import analytics
from backend.domain.candidates.models import CandidateJourneyEvent, ChatMessage, TestResult, User
from backend.domain.candidates.portal_service import (
    bump_candidate_portal_session_version,
    ensure_candidate_portal_session,
    get_candidate_portal_questions,
    sign_candidate_portal_hh_entry_token,
    sign_candidate_portal_max_launch_token,
    sign_candidate_portal_token,
)
from backend.domain.candidates.services import create_candidate_invite_token
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.slot_assignment_service import create_slot_assignment
from backend.apps.admin_ui.routers.candidate_portal import PORTAL_RESUME_COOKIE


def _configure_env(monkeypatch) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="candidate-portal-"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SESSION_SECRET", "candidate-portal-secret-0123456789abcdef012345")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_dir/'app.db'}")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "")
    monkeypatch.setenv("NOTIFICATION_BROKER", "memory")
    monkeypatch.setenv("BOT_ENABLED", "0")
    monkeypatch.setenv("BOT_AUTOSTART", "0")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("CRM_PUBLIC_URL", "https://crm.example.test")
    monkeypatch.setenv("CANDIDATE_PORTAL_PUBLIC_URL", "https://crm.example.test")
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_max_token")
    monkeypatch.setenv("MAX_WEBAPP_AUTH_MAX_AGE_SECONDS", "900")


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


async def _fake_setup_bot_state(app):
    app.state.bot = None
    app.state.state_manager = None
    app.state.bot_service = None
    app.state.bot_integration_switch = None
    app.state.reminder_service = None
    app.state.notification_service = None
    app.state.notification_broker_available = False
    return _DummyIntegration()


async def _seed_candidate_portal_flow() -> dict[str, int | str]:
    async with async_session() as session:
        city = City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Portal Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        candidate = User(
            fio="TG 700101",
            telegram_id=700101,
            telegram_user_id=700101,
            city=None,
            phone=None,
            desired_position="Менеджер по работе с клиентами",
            hh_vacancy_id="12345",
            source="telegram",
        )
        session.add(candidate)
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=candidate.last_activity + timedelta(days=1, hours=2),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        return {
            "candidate_id": candidate.id,
            "candidate_uuid": candidate.candidate_id,
            "city_id": city.id,
            "recruiter_id": recruiter.id,
            "slot_id": slot.id,
        }


async def _load_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _load_slot(slot_id: int) -> Slot | None:
    async with async_session() as session:
        return await session.get(Slot, slot_id)


async def _bind_candidate_max_user(candidate_id: int, max_user_id: str) -> None:
    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
        assert candidate is not None
        candidate.max_user_id = max_user_id
        candidate.messenger_platform = "max"
        await session.commit()


async def _load_messages(candidate_id: int) -> list[ChatMessage]:
    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.candidate_id == candidate_id)
        )
        return list(result.scalars().all())


async def _load_journey_events(candidate_id: int) -> list[CandidateJourneyEvent]:
    async with async_session() as session:
        result = await session.execute(
            select(CandidateJourneyEvent)
            .where(CandidateJourneyEvent.candidate_id == candidate_id)
            .order_by(CandidateJourneyEvent.created_at.desc(), CandidateJourneyEvent.id.desc())
        )
        return list(result.scalars().all())


async def _count_test_results(candidate_id: int, rating: str) -> int:
    async with async_session() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(
                    TestResult
                )
                .where(
                    TestResult.user_id == candidate_id,
                    TestResult.rating == rating,
                )
            )
            or 0
        )


def _build_answers() -> dict[str, str]:
    answers = {
        "age": "27",
        "status": "Работаю",
        "salary": "90 000 – 120 000 ›",
        "format": "Да, готов",
        "sales_exp": "Два года работал с клиентами и проводил переговоры.",
        "about": "Хочу расти и отвечать за результат.",
        "skills": "Коммуникация, настойчивость, дисциплина.",
        "expectations": "Прозрачный доход и сильная команда.",
    }
    for question in get_candidate_portal_questions():
        if question["id"] not in answers:
            answers[question["id"]] = question.get("options", ["Да"])[0] if question.get("options") else "Тестовый ответ"
    return answers


def _exchange_candidate_portal_session(
    client: TestClient,
    *,
    candidate_uuid: str,
    entry_channel: str = "admin",
    source_channel: str = "admin",
) -> dict[str, object]:
    token = sign_candidate_portal_token(
        candidate_uuid=candidate_uuid,
        entry_channel=entry_channel,
        source_channel=source_channel,
    )
    response = client.post("/api/candidate/session/exchange", json={"token": token})
    assert response.status_code == 200
    return response.json()


def _complete_candidate_profile_and_screening(
    client: TestClient,
    *,
    city_id: int,
) -> None:
    profile = client.post(
        "/api/candidate/profile",
        json={
            "fio": "Иванов Иван Иванович",
            "phone": "+7 999 111-22-33",
            "city_id": city_id,
        },
    )
    assert profile.status_code == 200
    screening = client.post(
        "/api/candidate/screening/complete",
        json={"answers": _build_answers()},
    )
    assert screening.status_code == 200


async def _seed_free_interview_slot(
    *,
    recruiter_id: int,
    city_id: int,
    days_offset: int = 2,
) -> int:
    async with async_session() as session:
        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            start_utc=datetime.now(timezone.utc) + timedelta(days=days_offset, hours=1),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
            tz_name="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        return int(slot.id)


def _build_max_webapp_data(
    *,
    user_id: str,
    bot_token: str = "test_max_token",
    auth_date: int | None = None,
    start_param: str = "mx1-launch-token",
) -> str:
    user_json = json.dumps(
        {
            "id": user_id,
            "username": "maxcandidate",
            "first_name": "Max",
            "language_code": "ru",
        }
    )
    params = {
        "user": user_json,
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "max-query-id",
        "start_param": start_param,
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
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


def test_candidate_portal_exchange_creates_session_from_telegram_token(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    with TestClient(app) as client:
        token = sign_candidate_portal_token(
            telegram_id=79990001122,
            entry_channel="telegram",
            source_channel="telegram",
        )
        response = client.post("/api/candidate/session/exchange", json={"token": token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["journey"]["current_step"] == "profile"
    assert payload["candidate"]["fio"] == "TG 79990001122"
    assert payload["journey"]["current_step_label"] == "Профиль"
    assert payload["journey"]["entry_channel"] == "telegram"
    assert payload["candidate"]["vacancy_label"] == "Вакансия уточняется"


def test_candidate_portal_exchange_accepts_signed_portal_token(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    async def _seed_candidate() -> tuple[str, int]:
        async with async_session() as session:
            candidate = User(
                fio="MAX Invite Tester",
                telegram_id=700201,
                telegram_user_id=700201,
                city="Москва",
                phone="+79990000000",
                source="max_bot",
                messenger_platform="max",
                max_user_id="mx-signed-700201",
            )
            session.add(candidate)
            await session.flush()
            candidate_pk = int(candidate.id)
            candidate_uuid = str(candidate.candidate_id)
            await session.commit()
        return candidate_uuid, candidate_pk

    candidate_uuid, candidate_id = asyncio.run(_seed_candidate())
    portal_token = sign_candidate_portal_token(
        candidate_uuid=candidate_uuid,
        entry_channel="max",
        source_channel="max_app",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/candidate/session/exchange",
            json={
                "token": portal_token,
                "max_webapp_data": _build_max_webapp_data(user_id="mx-signed-700201"),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["id"] == candidate_id
    assert payload["company"]["name"] == "SMART SERVICE"
    assert "анкет" in payload["company"]["summary"].lower()
    assert payload["journey"]["entry_channel"] == "max"
    assert payload["candidate"]["fio"] == "MAX Invite Tester"


def test_candidate_portal_exchange_accepts_max_safe_launch_token(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    async def _seed_candidate() -> tuple[str, int, int, int]:
        async with async_session() as session:
            candidate = User(
                fio="MAX Launch Tester",
                telegram_id=700211,
                telegram_user_id=700211,
                city="Москва",
                phone="+79990000002",
                source="max_bot",
                messenger_platform="max",
                max_user_id="mx-launch-700211",
            )
            session.add(candidate)
            await session.flush()
            portal_journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            await session.commit()
            return (
                str(candidate.candidate_id),
                int(candidate.id),
                int(portal_journey.id),
                int(portal_journey.session_version or 1),
            )

    candidate_uuid, candidate_id, journey_id, session_version = asyncio.run(_seed_candidate())
    launch_token = sign_candidate_portal_max_launch_token(
        candidate_uuid=candidate_uuid,
        journey_session_id=journey_id,
        session_version=session_version,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/candidate/session/exchange",
            json={
                "token": launch_token,
                "max_webapp_data": _build_max_webapp_data(user_id="mx-launch-700211"),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["id"] == candidate_id
    assert payload["journey"]["session_id"] == journey_id
    assert payload["journey"]["entry_channel"] == "max"
    assert payload["candidate"]["fio"] == "MAX Launch Tester"


def test_candidate_portal_exchange_rejects_max_launch_without_webapp_data(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    async def _seed_candidate() -> tuple[str, int, int, int]:
        async with async_session() as session:
            candidate = User(
                fio="MAX Missing WebAppData",
                telegram_id=700212,
                telegram_user_id=700212,
                city="Москва",
                phone="+79990000003",
                source="max_bot",
                messenger_platform="max",
                max_user_id="mx-launch-700212",
            )
            session.add(candidate)
            await session.flush()
            portal_journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            await session.commit()
            return (
                str(candidate.candidate_id),
                int(candidate.id),
                int(portal_journey.id),
                int(portal_journey.session_version or 1),
            )

    candidate_uuid, _, journey_id, session_version = asyncio.run(_seed_candidate())
    launch_token = sign_candidate_portal_max_launch_token(
        candidate_uuid=candidate_uuid,
        journey_session_id=journey_id,
        session_version=session_version,
    )

    with TestClient(app) as client:
        response = client.post("/api/candidate/session/exchange", json={"token": launch_token})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "max_webapp_auth_required"


def test_candidate_portal_exchange_rejects_max_launch_with_identity_mismatch(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    async def _seed_candidate() -> tuple[str, int, int, int]:
        async with async_session() as session:
            candidate = User(
                fio="MAX Identity Mismatch",
                telegram_id=700213,
                telegram_user_id=700213,
                city="Москва",
                phone="+79990000004",
                source="max_bot",
                messenger_platform="max",
                max_user_id="mx-launch-700213",
            )
            session.add(candidate)
            await session.flush()
            portal_journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            await session.commit()
            return (
                str(candidate.candidate_id),
                int(candidate.id),
                int(portal_journey.id),
                int(portal_journey.session_version or 1),
            )

    candidate_uuid, _, journey_id, session_version = asyncio.run(_seed_candidate())
    launch_token = sign_candidate_portal_max_launch_token(
        candidate_uuid=candidate_uuid,
        journey_session_id=journey_id,
        session_version=session_version,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/candidate/session/exchange",
            json={
                "token": launch_token,
                "max_webapp_data": _build_max_webapp_data(user_id="mx-other-user"),
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "max_identity_mismatch"


def test_candidate_portal_exchange_rejects_stale_max_webapp_data(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    async def _seed_candidate() -> tuple[str, int, int, int]:
        async with async_session() as session:
            candidate = User(
                fio="MAX Stale WebAppData",
                telegram_id=700214,
                telegram_user_id=700214,
                city="Москва",
                phone="+79990000005",
                source="max_bot",
                messenger_platform="max",
                max_user_id="mx-launch-700214",
            )
            session.add(candidate)
            await session.flush()
            portal_journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            await session.commit()
            return (
                str(candidate.candidate_id),
                int(candidate.id),
                int(portal_journey.id),
                int(portal_journey.session_version or 1),
            )

    candidate_uuid, _, journey_id, session_version = asyncio.run(_seed_candidate())
    launch_token = sign_candidate_portal_max_launch_token(
        candidate_uuid=candidate_uuid,
        journey_session_id=journey_id,
        session_version=session_version,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/candidate/session/exchange",
            json={
                "token": launch_token,
                "max_webapp_data": _build_max_webapp_data(
                    user_id="mx-launch-700214",
                    auth_date=int(time.time()) - 7200,
                ),
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "max_webapp_data_invalid"


def test_candidate_portal_exchange_rejects_raw_invite_token(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    async def _seed_invite() -> str:
        async with async_session() as session:
            candidate = User(
                fio="Legacy Invite Tester",
                telegram_id=700202,
                telegram_user_id=700202,
                city="Москва",
                phone="+79990000001",
                source="max_bot",
                messenger_platform="max",
            )
            session.add(candidate)
            await session.flush()
            candidate_uuid = candidate.candidate_id
            await session.commit()
        invite = await create_candidate_invite_token(candidate_uuid)
        return invite.token

    invite_token = asyncio.run(_seed_invite())

    with TestClient(app) as client:
        response = client.post("/api/candidate/session/exchange", json={"token": invite_token})

    assert response.status_code == 401
    assert "недейств" in response.json()["detail"]["message"].lower()


def test_candidate_portal_journey_can_be_restored_from_header_token(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="web",
            source_channel="portal",
        )
        client.cookies.clear()

        response = client.get(
            "/api/candidate/journey",
            headers={"x-candidate-portal-token": token},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["id"] == seeded["candidate_id"]
    assert payload["journey"]["current_step"] == "profile"
    assert payload["dashboard"]["primary_action"]["key"] == "complete_profile"
    assert payload["journey"]["inbox"]["conversation_id"] == f"candidate:{seeded['candidate_id']}"
    assert payload["journey"]["channel_options"]["web"]["enabled"] is True
    assert payload["resources"]["faq"]


def test_candidate_entry_gateway_resolves_web_and_records_selection(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())

        async def _build_entry_token() -> tuple[str, int]:
            async with async_session() as session:
                candidate = await session.get(User, int(seeded["candidate_id"]))
                assert candidate is not None
                journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
                await session.commit()
                return (
                    sign_candidate_portal_hh_entry_token(
                        candidate_uuid=str(seeded["candidate_uuid"]),
                        journey_session_id=int(journey.id),
                        session_version=int(journey.session_version or 1),
                    ),
                    int(journey.id),
                )

        entry_token, journey_id = asyncio.run(_build_entry_token())
        resolve = client.get(f"/api/candidate/entry/resolve?entry={entry_token}")
        assert resolve.status_code == 200
        resolve_payload = resolve.json()
        assert resolve_payload["candidate"]["id"] == seeded["candidate_id"]
        assert resolve_payload["options"]["web"]["enabled"] is True
        assert resolve_payload["suggested_channel"] == "web"

        select_response = client.post(
            "/api/candidate/entry/select",
            json={"entry_token": entry_token, "channel": "web"},
        )

    assert select_response.status_code == 200
    select_payload = select_response.json()
    assert select_payload["channel"] == "web"
    assert select_payload["recorded"] is True
    assert select_payload["launch"]["type"] == "cabinet"
    assert "candidate/start" in str(select_payload["launch"]["url"])

    async def _load_payload() -> dict[str, object]:
        async with async_session() as session:
            candidate = await session.get(User, int(seeded["candidate_id"]))
            assert candidate is not None
            journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
            assert journey is not None
            return dict(journey.payload_json or {})

    payload_meta = asyncio.run(_load_payload())
    assert payload_meta["entry_source"] == "hh"
    assert payload_meta["last_entry_channel"] == "web"
    assert "web" in payload_meta["available_channels_snapshot"]


def test_candidate_entry_select_accepts_query_and_form_fallback(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())

        async def _build_entry_token() -> str:
            async with async_session() as session:
                candidate = await session.get(User, int(seeded["candidate_id"]))
                assert candidate is not None
                journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
                await session.commit()
                return sign_candidate_portal_hh_entry_token(
                    candidate_uuid=str(seeded["candidate_uuid"]),
                    journey_session_id=int(journey.id),
                    session_version=int(journey.session_version or 1),
                )

        entry_token = asyncio.run(_build_entry_token())

        select_response = client.post(
            f"/api/candidate/entry/select?entry={entry_token}&channel=web",
            data={"entry_token": entry_token, "channel": "web"},
        )

    assert select_response.status_code == 200
    select_payload = select_response.json()
    assert select_payload["channel"] == "web"
    assert select_payload["recorded"] is True
    assert "candidate/start" in str(select_payload["launch"]["url"])


def test_candidate_entry_gateway_remains_valid_after_portal_session_version_bump(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())

        async def _build_legacy_entry_token() -> str:
            async with async_session() as session:
                candidate = await session.get(User, int(seeded["candidate_id"]))
                assert candidate is not None
                journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
                token = sign_candidate_portal_hh_entry_token(
                    candidate_uuid=str(seeded["candidate_uuid"]),
                    journey_session_id=int(journey.id),
                    session_version=int(journey.session_version or 1),
                )
                await session.commit()
                return token

        entry_token = asyncio.run(_build_legacy_entry_token())

        async def _bump_version() -> None:
            async with async_session() as session:
                await bump_candidate_portal_session_version(
                    session,
                    candidate_id=int(seeded["candidate_id"]),
                )
                await session.commit()

        asyncio.run(_bump_version())

        resolve = client.get(f"/api/candidate/entry/resolve?entry={entry_token}")
        assert resolve.status_code == 200
        resolve_payload = resolve.json()
        assert resolve_payload["candidate"]["id"] == seeded["candidate_id"]
        assert resolve_payload["options"]["web"]["enabled"] is True

        select_response = client.post(
            "/api/candidate/entry/select",
            json={"entry_token": entry_token, "channel": "web"},
        )

    assert select_response.status_code == 200
    select_payload = select_response.json()
    assert select_payload["channel"] == "web"
    assert "candidate/start" in str(select_payload["launch"]["url"])


def test_candidate_portal_journey_can_be_restored_from_resume_cookie_after_browser_restart(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="web",
            source_channel="portal",
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
    assert payload["candidate"]["id"] == seeded["candidate_id"]
    assert payload["journey"]["current_step"] == "profile"


def test_candidate_portal_entry_switch_updates_last_entry_channel_inside_cabinet(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200

        switch = client.post("/api/candidate/entry/switch", json={"channel": "web"})

    assert switch.status_code == 200
    switch_payload = switch.json()
    assert switch_payload["channel"] == "web"
    assert switch_payload["recorded"] is True
    assert switch_payload["delivery_status"]["source"] == "cabinet"

    async def _load_payload() -> dict[str, object]:
        async with async_session() as session:
            candidate = await session.get(User, int(seeded["candidate_id"]))
            assert candidate is not None
            journey = await ensure_candidate_portal_session(session, candidate, entry_channel="web")
            assert journey is not None
            return dict(journey.payload_json or {})

    payload_meta = asyncio.run(_load_payload())
    assert payload_meta["entry_source"] == "cabinet"
    assert payload_meta["last_entry_channel"] == "web"
    assert "web" in payload_meta["available_channels_snapshot"]


def test_candidate_portal_journey_returns_recoverable_state_without_bootstrap(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    with TestClient(app) as client:
        client.cookies.clear()
        response = client.get("/api/candidate/journey")

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["state"] == "recoverable"
    assert detail["code"] == "portal_session_expired"


def test_candidate_portal_resume_cookie_is_cleared_after_version_mismatch(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
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


def test_candidate_portal_end_to_end_flow(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200
        exchange_payload = exchange.json()
        assert exchange_payload["journey"]["current_step"] == "profile"
        assert exchange_payload["journey"]["current_step_label"] == "Профиль"
        assert exchange_payload["candidate"]["vacancy_label"] == "Менеджер по работе с клиентами"
        assert exchange_payload["dashboard"]["primary_action"]["key"] == "complete_profile"
        assert exchange_payload["tests"]["items"][0]["key"] == "screening"
        assert exchange_payload["resources"]["documents"]

        profile = client.post(
            "/api/candidate/profile",
            json={
                "fio": "Иванов Иван Иванович",
                "phone": "+7 999 111-22-33",
                "city_id": seeded["city_id"],
            },
        )
        assert profile.status_code == 200
        assert profile.json()["journey"]["current_step"] == "screening"

        screening = client.post(
            "/api/candidate/screening/complete",
            json={"answers": _build_answers()},
        )
        assert screening.status_code == 200
        assert screening.json()["journey"]["current_step"] in {"slot_selection", "status"}

        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": seeded["slot_id"]},
        )
        assert reserve.status_code == 200
        reserve_payload = reserve.json()
        assert reserve_payload["journey"]["slots"]["active"]["status"] == SlotStatus.PENDING
        assert reserve_payload["journey"]["next_step_at"] == reserve_payload["journey"]["slots"]["active"]["start_utc"]
        assert reserve_payload["journey"]["next_step_timezone"] == "Europe/Moscow"

        confirm = client.post("/api/candidate/slots/confirm")
        assert confirm.status_code == 200
        assert confirm.json()["journey"]["slots"]["active"]["status"] == SlotStatus.CONFIRMED_BY_CANDIDATE

        message = client.post(
            "/api/candidate/messages",
            json={"text": "Нужен пропуск на проходной."},
        )
        assert message.status_code == 200
        message_payload = message.json()
        assert any(item["text"] == "Нужен пропуск на проходной." for item in message_payload["journey"]["messages"])
        latest_message = message_payload["journey"]["messages"][-1]
        assert latest_message["conversation_id"] == f"candidate:{seeded['candidate_id']}"
        assert latest_message["origin_channel"] == "web"
        assert latest_message["author_role"] == "candidate"
        assert message_payload["feedback"]["items"]

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.fio == "Иванов Иван Иванович"
    assert candidate.phone == "+79991112233"
    assert candidate.candidate_status == CandidateStatus.INTERVIEW_CONFIRMED

    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE
    assert slot.candidate_id == candidate.candidate_id

    messages = asyncio.run(_load_messages(int(seeded["candidate_id"])))
    assert any(row.text == "Нужен пропуск на проходной." for row in messages)

    journey_events = asyncio.run(_load_journey_events(int(seeded["candidate_id"])))
    event_keys = [event.event_key for event in journey_events]
    assert "portal_entered" in event_keys
    assert "screening_started" in event_keys
    assert "screening_completed" in event_keys


def test_candidate_portal_max_session_can_complete_slot_confirmation_flow(monkeypatch):
    _configure_env(monkeypatch)
    monkeypatch.setenv("MAX_BOT_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_LINK_BASE", "https://max.ru/recruitsmartbot")
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded: dict[str, int | str] = {}

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        asyncio.run(_bind_candidate_max_user(int(seeded["candidate_id"]), "mx-flow-700301"))
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="max",
            source_channel="max_app",
        )
        exchange = client.post(
            "/api/candidate/session/exchange",
            json={
                "token": token,
                "max_webapp_data": _build_max_webapp_data(user_id="mx-flow-700301"),
            },
        )
        assert exchange.status_code == 200
        assert exchange.json()["journey"]["entry_channel"] == "max"

        profile = client.post(
            "/api/candidate/profile",
            json={
                "fio": "Иванов Иван Иванович",
                "phone": "+7 999 111-22-33",
                "city_id": seeded["city_id"],
            },
        )
        assert profile.status_code == 200

        screening = client.post(
            "/api/candidate/screening/complete",
            json={"answers": _build_answers()},
        )
        assert screening.status_code == 200
        assert screening.json()["journey"]["entry_channel"] == "max"

        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": seeded["slot_id"]},
        )
        assert reserve.status_code == 200
        reserve_payload = reserve.json()
        assert reserve_payload["journey"]["entry_channel"] == "max"
        assert reserve_payload["journey"]["slots"]["active"]["status"] == SlotStatus.PENDING

        confirm = client.post("/api/candidate/slots/confirm")
        assert confirm.status_code == 200
        confirm_payload = confirm.json()
        assert confirm_payload["journey"]["entry_channel"] == "max"
        assert confirm_payload["journey"]["slots"]["active"]["status"] == SlotStatus.CONFIRMED_BY_CANDIDATE

    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.INTERVIEW_CONFIRMED

    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE


def test_candidate_portal_screening_repeat_is_blocked_for_existing_progress(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded = asyncio.run(_seed_candidate_portal_flow())

    with TestClient(app) as client:
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200

        profile = client.post(
            "/api/candidate/profile",
            json={
                "fio": "Иванов Иван Иванович",
                "phone": "+7 999 111-22-33",
                "city_id": seeded["city_id"],
            },
        )
        assert profile.status_code == 200

        first = client.post(
            "/api/candidate/screening/complete",
            json={"answers": _build_answers()},
        )
        assert first.status_code == 200

        second = client.post(
            "/api/candidate/screening/complete",
            json={"answers": _build_answers()},
        )

    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "candidate_screening_locked"
    assert detail["state"] == "blocked"
    assert detail["meta"]["current_step"] in {"slot_selection", "status"}
    assert detail["meta"]["status"] in {
        CandidateStatus.TEST1_COMPLETED.value,
        CandidateStatus.WAITING_SLOT.value,
    }
    assert "активность" in detail["message"].lower()
    assert asyncio.run(_count_test_results(int(seeded["candidate_id"]), "TEST1")) == 1

    journey_events = asyncio.run(_load_journey_events(int(seeded["candidate_id"])))
    assert any(event.event_key == "screening_reentry_blocked" for event in journey_events)


def test_candidate_portal_screening_repeat_is_blocked_for_intro_day_candidate(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    async def _seed_intro_candidate() -> dict[str, int | str]:
        async with async_session() as session:
            city = City(name="Москва", tz="Europe/Moscow", active=True)
            recruiter = Recruiter(name="Portal Intro Recruiter", tz="Europe/Moscow", active=True)
            recruiter.cities.append(city)
            session.add_all([city, recruiter])
            await session.flush()
            candidate = User(
                fio="Иванов Иван Иванович",
                telegram_id=700102,
                telegram_user_id=700102,
                city="Москва",
                phone="+79991112233",
                desired_position="Менеджер по работе с клиентами",
                source="telegram",
                candidate_status=CandidateStatus.INTRO_DAY_SCHEDULED,
            )
            session.add(candidate)
            await session.flush()
            slot = Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=candidate.last_activity + timedelta(days=1),
                duration_min=60,
                status=SlotStatus.PENDING,
                purpose="intro_day",
                tz_name="Europe/Moscow",
                candidate_id=candidate.candidate_id,
                candidate_tg_id=int(candidate.telegram_id or candidate.telegram_user_id or 0),
                candidate_fio=candidate.fio,
                candidate_tz="Europe/Moscow",
                candidate_city_id=city.id,
            )
            session.add(slot)
            await session.commit()
            return {
                "candidate_uuid": str(candidate.candidate_id),
                "candidate_id": int(candidate.id),
            }

    seeded = asyncio.run(_seed_intro_candidate())

    with TestClient(app) as client:
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200

        screening = client.post(
            "/api/candidate/screening/complete",
            json={"answers": _build_answers()},
        )

    assert screening.status_code == 409
    detail = screening.json()["detail"]
    assert detail["code"] == "candidate_screening_locked"
    assert detail["meta"]["status"] == CandidateStatus.INTRO_DAY_SCHEDULED.value
    assert detail["meta"]["active_slot_purpose"] == "intro_day"
    assert detail["meta"]["current_step"] == "status"


def test_candidate_portal_history_contains_candidate_facing_items(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded = asyncio.run(_seed_candidate_portal_flow())

    with TestClient(app) as client:
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        exchange = client.post("/api/candidate/session/exchange", json={"token": token})
        assert exchange.status_code == 200
        profile = client.post(
            "/api/candidate/profile",
            json={
                "fio": "Иванов Иван Иванович",
                "phone": "+7 999 111-22-33",
                "city_id": seeded["city_id"],
            },
        )
        assert profile.status_code == 200
        screening = client.post("/api/candidate/screening/complete", json={"answers": _build_answers()})
        assert screening.status_code == 200
        journey = client.get("/api/candidate/journey")

    assert journey.status_code == 200
    history_items = journey.json()["history"]["items"]
    assert history_items
    titles = [item["title"] for item in history_items]
    assert "Открыт кабинет кандидата" in titles
    assert "Анкета завершена" in titles or "Тест 1 завершён" in titles


def test_candidate_portal_slot_reserve_blocked_when_assignment_owns_scheduling(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded = asyncio.run(_seed_candidate_portal_flow())
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None

    offer = asyncio.run(
        create_slot_assignment(
            slot_id=int(seeded["slot_id"]),
            candidate_id=str(seeded["candidate_uuid"]),
            candidate_tg_id=int(candidate.telegram_id or candidate.telegram_user_id or 0),
            candidate_tz="Europe/Moscow",
            created_by="portal-test",
        )
    )
    assert offer.ok is True

    with TestClient(app) as client:
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


def test_candidate_portal_max_session_blocks_assignment_owned_slot_reservation(monkeypatch):
    _configure_env(monkeypatch)
    monkeypatch.setenv("MAX_BOT_ENABLED", "1")
    monkeypatch.setenv("MAX_BOT_LINK_BASE", "https://max.ru/recruitsmartbot")
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded = asyncio.run(_seed_candidate_portal_flow())
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None

    offer = asyncio.run(
        create_slot_assignment(
            slot_id=int(seeded["slot_id"]),
            candidate_id=str(seeded["candidate_uuid"]),
            candidate_tg_id=int(candidate.telegram_id or candidate.telegram_user_id or 0),
            candidate_tz="Europe/Moscow",
            created_by="portal-test-max",
        )
    )
    assert offer.ok is True

    with TestClient(app) as client:
        asyncio.run(_bind_candidate_max_user(int(seeded["candidate_id"]), "mx-flow-700302"))
        token = sign_candidate_portal_token(
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="max",
            source_channel="max_app",
        )
        exchange = client.post(
            "/api/candidate/session/exchange",
            json={
                "token": token,
                "max_webapp_data": _build_max_webapp_data(user_id="mx-flow-700302"),
            },
        )
        assert exchange.status_code == 200
        assert exchange.json()["journey"]["entry_channel"] == "max"

        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": int(seeded["slot_id"])},
        )

    assert reserve.status_code == 409
    assert "управляется через предложение времени" in reserve.json()["detail"]["message"].lower()


def test_candidate_portal_slot_mutations_expose_blocked_assignment_owned_state(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()
    seeded = asyncio.run(_seed_candidate_portal_flow())
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert candidate is not None

    replacement_slot_id = asyncio.run(
        _seed_free_interview_slot(
            recruiter_id=int(seeded["recruiter_id"]),
            city_id=int(seeded["city_id"]),
            days_offset=3,
        )
    )

    offer = asyncio.run(
        create_slot_assignment(
            slot_id=int(seeded["slot_id"]),
            candidate_id=str(seeded["candidate_uuid"]),
            candidate_tg_id=int(candidate.telegram_id or candidate.telegram_user_id or 0),
            candidate_tz="Europe/Moscow",
            created_by="portal-test-mutations",
        )
    )
    assert offer.ok is True

    with TestClient(app) as client:
        _exchange_candidate_portal_session(
            client,
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )

        confirm = client.post("/api/candidate/slots/confirm")
        cancel = client.post("/api/candidate/slots/cancel")
        reschedule = client.post(
            "/api/candidate/slots/reschedule",
            json={"new_slot_id": replacement_slot_id},
        )

    for response in (confirm, cancel, reschedule):
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "candidate_schedule_assignment_owned"
        assert detail["state"] == "blocked"
        assert detail["meta"]["assignment_owned"] is True


def test_candidate_portal_slot_confirm_is_idempotent_for_repeat_action(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    app = app_module.create_app()

    with TestClient(app) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        _exchange_candidate_portal_session(
            client,
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        _complete_candidate_profile_and_screening(client, city_id=int(seeded["city_id"]))

        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": int(seeded["slot_id"])},
        )
        assert reserve.status_code == 200

        first_confirm = client.post("/api/candidate/slots/confirm")
        second_confirm = client.post("/api/candidate/slots/confirm")

    assert first_confirm.status_code == 200
    assert second_confirm.status_code == 200
    assert first_confirm.json()["journey"]["slots"]["active"]["status"] == SlotStatus.CONFIRMED_BY_CANDIDATE
    assert second_confirm.json()["journey"]["slots"]["active"]["status"] == SlotStatus.CONFIRMED_BY_CANDIDATE

    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.INTERVIEW_CONFIRMED


def test_candidate_portal_slot_cancel_rolls_back_on_post_release_failure(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)

    async def _failing_log_slot_canceled(*args, **kwargs):
        raise RuntimeError("forced analytics failure after cancel")

    monkeypatch.setattr("backend.domain.candidates.portal_service.analytics.log_slot_canceled", _failing_log_slot_canceled)
    app = app_module.create_app()

    with TestClient(app, raise_server_exceptions=False) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        _exchange_candidate_portal_session(
            client,
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        _complete_candidate_profile_and_screening(client, city_id=int(seeded["city_id"]))
        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": int(seeded["slot_id"])},
        )
        assert reserve.status_code == 200

        cancel = client.post("/api/candidate/slots/cancel")

    assert cancel.status_code == 500
    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING
    assert candidate is not None
    assert slot.candidate_id == candidate.candidate_id
    assert candidate.candidate_status == CandidateStatus.SLOT_PENDING


def test_candidate_portal_slot_confirm_rolls_back_on_post_confirm_failure(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)

    async def _failing_log_funnel_event(event, *args, **kwargs):
        if event == analytics.FunnelEvent.SLOT_CONFIRMED:
            raise RuntimeError("forced analytics failure after confirm")
        return None

    monkeypatch.setattr("backend.domain.candidates.portal_service.analytics.log_funnel_event", _failing_log_funnel_event)
    app = app_module.create_app()

    with TestClient(app, raise_server_exceptions=False) as client:
        seeded = asyncio.run(_seed_candidate_portal_flow())
        _exchange_candidate_portal_session(
            client,
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        _complete_candidate_profile_and_screening(client, city_id=int(seeded["city_id"]))
        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": int(seeded["slot_id"])},
        )
        assert reserve.status_code == 200

        confirm = client.post("/api/candidate/slots/confirm")

    assert confirm.status_code == 500
    slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert slot is not None
    assert slot.status == SlotStatus.PENDING
    assert candidate is not None
    assert candidate.candidate_status == CandidateStatus.SLOT_PENDING


def test_candidate_portal_slot_reschedule_rolls_back_on_post_release_failure(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)

    async def _failing_log_slot_rescheduled(*args, **kwargs):
        raise RuntimeError("forced analytics failure after reschedule")

    monkeypatch.setattr("backend.domain.candidates.portal_service.analytics.log_slot_rescheduled", _failing_log_slot_rescheduled)
    app = app_module.create_app()
    seeded = asyncio.run(_seed_candidate_portal_flow())
    replacement_slot_id = asyncio.run(
        _seed_free_interview_slot(
            recruiter_id=int(seeded["recruiter_id"]),
            city_id=int(seeded["city_id"]),
            days_offset=4,
        )
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        _exchange_candidate_portal_session(
            client,
            candidate_uuid=str(seeded["candidate_uuid"]),
            entry_channel="admin",
            source_channel="admin",
        )
        _complete_candidate_profile_and_screening(client, city_id=int(seeded["city_id"]))
        reserve = client.post(
            "/api/candidate/slots/reserve",
            json={"slot_id": int(seeded["slot_id"])},
        )
        assert reserve.status_code == 200

        reschedule = client.post(
            "/api/candidate/slots/reschedule",
            json={"new_slot_id": replacement_slot_id},
        )

    assert reschedule.status_code == 500
    old_slot = asyncio.run(_load_slot(int(seeded["slot_id"])))
    replacement_slot = asyncio.run(_load_slot(replacement_slot_id))
    candidate = asyncio.run(_load_candidate(int(seeded["candidate_id"])))
    assert old_slot is not None
    assert old_slot.status == SlotStatus.PENDING
    assert candidate is not None
    assert old_slot.candidate_id == candidate.candidate_id
    assert replacement_slot is not None
    assert replacement_slot.status == SlotStatus.FREE
    assert replacement_slot.candidate_id is None
    assert candidate.candidate_status == CandidateStatus.SLOT_PENDING


def test_candidate_shared_access_challenge_and_verify_bootstraps_session(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module
    from backend.apps.admin_ui.services import candidate_shared_access as shared_access_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)
    delivered: dict[str, str] = {}

    async def _fake_deliver(session, *, candidate, code: str):
        delivered["code"] = code
        return "hh"

    monkeypatch.setattr(shared_access_module, "deliver_candidate_shared_access_code", _fake_deliver)
    app = app_module.create_app()

    async def _seed_candidate() -> dict[str, int | str]:
        async with async_session() as session:
            city = City(name="Сочи", tz="Europe/Moscow", active=True)
            session.add(city)
            await session.flush()
            candidate = User(
                fio="Шеншин Михаил Алексеевич",
                city="Сочи",
                phone="+79990001122",
                desired_position="Вакансия уточняется",
                messenger_platform="telegram",
                telegram_id=700707,
                telegram_user_id=700707,
                source="hh",
            )
            session.add(candidate)
            await session.commit()
            return {"candidate_id": int(candidate.id), "candidate_uuid": str(candidate.candidate_id)}

    seeded = asyncio.run(_seed_candidate())

    with TestClient(app) as client:
        challenge = client.post(
            "/api/candidate/access/challenge",
            json={"phone": "+7 999 000 11 22"},
        )
        assert challenge.status_code == 200
        challenge_payload = challenge.json()
        assert challenge_payload["ok"] is True
        assert challenge_payload["challenge_token"]
        assert delivered["code"]

        verify = client.post(
            "/api/candidate/access/verify",
            json={
                "challenge_token": challenge_payload["challenge_token"],
                "code": delivered["code"],
            },
        )

        assert verify.status_code == 200
        verify_payload = verify.json()
        assert verify_payload["candidate"]["id"] == seeded["candidate_id"]
        assert verify_payload["journey"]["entry_channel"] == "web"
        assert verify_payload["journey"]["channel_options"]["web"]["enabled"] is True

        journey = client.get("/api/candidate/journey")
        assert journey.status_code == 200
        assert journey.json()["candidate"]["id"] == seeded["candidate_id"]

    journey_events = asyncio.run(_load_journey_events(int(seeded["candidate_id"])))
    assert any(event.event_key == "shared_access_verified" for event in journey_events)


def test_candidate_shared_access_verify_rejects_invalid_code(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module
    from backend.apps.admin_ui.services import candidate_shared_access as shared_access_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)

    async def _fake_deliver(session, *, candidate, code: str):
        return "hh"

    monkeypatch.setattr(shared_access_module, "deliver_candidate_shared_access_code", _fake_deliver)
    app = app_module.create_app()

    async def _seed_candidate() -> None:
        async with async_session() as session:
            candidate = User(
                fio="Portal Shared Candidate",
                city="Москва",
                phone="+79990002233",
                desired_position="Вакансия уточняется",
                source="hh",
            )
            session.add(candidate)
            await session.commit()

    asyncio.run(_seed_candidate())

    with TestClient(app) as client:
        challenge = client.post(
            "/api/candidate/access/challenge",
            json={"phone": "+7 999 000 22 33"},
        )
        assert challenge.status_code == 200
        challenge_token = challenge.json()["challenge_token"]

        verify = client.post(
            "/api/candidate/access/verify",
            json={"challenge_token": challenge_token, "code": "000000"},
        )

    assert verify.status_code == 401
    assert verify.json()["detail"]["code"] == "candidate_shared_access_code_invalid"


def test_candidate_shared_access_challenge_hides_unknown_or_ambiguous_phone(monkeypatch):
    _configure_env(monkeypatch)
    settings_module.get_settings.cache_clear()
    from backend.apps.admin_ui import app as app_module
    from backend.apps.admin_ui.services import candidate_shared_access as shared_access_module

    monkeypatch.setattr(app_module, "setup_bot_state", _fake_setup_bot_state)

    async def _fake_deliver(session, *, candidate, code: str):
        return "hh"

    monkeypatch.setattr(shared_access_module, "deliver_candidate_shared_access_code", _fake_deliver)
    app = app_module.create_app()

    async def _seed_candidates() -> None:
        async with async_session() as session:
            session.add_all(
                [
                    User(fio="Known Candidate", city="Москва", phone="+79990003344", source="hh"),
                    User(fio="Ambiguous One", city="Москва", phone="+79990004455", source="hh"),
                    User(fio="Ambiguous Two", city="Москва", phone="+79990004455", source="hh"),
                ]
            )
            await session.commit()

    asyncio.run(_seed_candidates())

    with TestClient(app) as client:
        known = client.post("/api/candidate/access/challenge", json={"phone": "+7 999 000 33 44"})
        unknown = client.post("/api/candidate/access/challenge", json={"phone": "+7 999 000 55 66"})
        ambiguous = client.post("/api/candidate/access/challenge", json={"phone": "+7 999 000 44 55"})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert ambiguous.status_code == 200
    assert known.json()["message"] == unknown.json()["message"] == ambiguous.json()["message"]
    assert known.json()["delivery_hint"] == unknown.json()["delivery_hint"] == ambiguous.json()["delivery_hint"]
