from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.domain.candidates.models import ChatMessage, User
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
            "slot_id": slot.id,
        }


async def _load_candidate(candidate_id: int) -> User | None:
    async with async_session() as session:
        return await session.get(User, candidate_id)


async def _load_slot(slot_id: int) -> Slot | None:
    async with async_session() as session:
        return await session.get(Slot, slot_id)


async def _load_messages(candidate_id: int) -> list[ChatMessage]:
    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.candidate_id == candidate_id)
        )
        return list(result.scalars().all())


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
        response = client.post("/api/candidate/session/exchange", json={"token": portal_token})

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
        response = client.post("/api/candidate/session/exchange", json={"token": launch_token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["id"] == candidate_id
    assert payload["journey"]["session_id"] == journey_id
    assert payload["journey"]["entry_channel"] == "max"
    assert payload["candidate"]["fio"] == "MAX Launch Tester"


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
