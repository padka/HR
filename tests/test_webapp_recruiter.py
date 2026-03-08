"""Tests for Recruiter Mini App API endpoints."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.apps.admin_api.main import create_app
from backend.apps.admin_api.webapp.recruiter_routers import (
    DashboardResponse,
    IncomingResponse,
    get_recruiter_webapp_auth,
    router,
)
from backend.apps.admin_ui.services.bot_service import BotSendResult
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import ChatMessage, InterviewNote, User
from backend.domain.candidates.status import CandidateStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create a FastAPI app with overridden auth for testing."""
    return create_app()


class DummyBotService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_chat_message(self, telegram_id: int, text: str, reply_markup=None) -> BotSendResult:
        self.calls.append({"telegram_id": telegram_id, "text": text})
        return BotSendResult(ok=True, status="sent", telegram_message_id=4321)


@pytest.fixture
def recruiter_and_candidate():
    """Create a recruiter and candidate in the DB, return (recruiter_id, candidate_id)."""
    from backend.core.db import async_session

    async def _create():
        async with async_session() as session:
            rec = models.Recruiter(
                name="Тест Рекрутер",
                tz="Europe/Moscow",
                active=True,
                tg_chat_id=111222333,
            )
            session.add(rec)
            await session.flush()

            candidate = User(
                fio="Иван Тестов",
                city="Москва",
                phone="+79001234567",
                telegram_id=999888777,
                candidate_status=CandidateStatus.TEST1_COMPLETED,
                is_active=True,
                responsible_recruiter_id=rec.id,
            )
            session.add(candidate)
            await session.commit()
            return rec.id, candidate.id

    return asyncio.get_event_loop().run_until_complete(_create())


@pytest.fixture
def recruiter_access_matrix():
    """Create owned and city-routed candidates for recruiter access checks."""
    async def _create():
        async with async_session() as session:
            city = models.City(name="Москва", tz="Europe/Moscow", active=True)

            rec_allowed = models.Recruiter(
                name="Разрешённый Рекрутер",
                tz="Europe/Moscow",
                active=True,
                tg_chat_id=333222111,
            )
            rec_blocked = models.Recruiter(
                name="Чужой Рекрутер",
                tz="Europe/Moscow",
                active=True,
                tg_chat_id=444555666,
            )
            rec_allowed.cities.append(city)
            session.add_all([city, rec_allowed, rec_blocked])
            await session.flush()

            city_routed_candidate = User(
                fio="Городской Кандидат",
                city="Москва",
                phone="+79005554433",
                telegram_id=111000999,
                candidate_status=CandidateStatus.WAITING_SLOT,
                is_active=True,
                responsible_recruiter_id=None,
            )
            foreign_candidate = User(
                fio="Чужой Кандидат",
                city="Москва",
                phone="+79007776655",
                telegram_id=222111000,
                candidate_status=CandidateStatus.TEST1_COMPLETED,
                is_active=True,
                responsible_recruiter_id=rec_blocked.id,
            )
            session.add_all([city_routed_candidate, foreign_candidate])
            await session.commit()
            return {
                "allowed_recruiter_id": rec_allowed.id,
                "blocked_recruiter_id": rec_blocked.id,
                "city_routed_candidate_id": city_routed_candidate.id,
                "other_recruiter_candidate_id": foreign_candidate.id,
            }

    return asyncio.get_event_loop().run_until_complete(_create())


def _make_auth_override(recruiter_id: int):
    """Build an auth dependency override that returns a fixed recruiter."""

    async def override():
        from backend.core.db import async_session
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(
                select(models.Recruiter).where(models.Recruiter.id == recruiter_id)
            )
            recruiter = result.scalar_one()
            session.expunge(recruiter)

        from backend.apps.admin_api.webapp.auth import TelegramUser

        tg_user = TelegramUser(user_id=111222333, first_name="Test", auth_date=0)
        return {"tg_user": tg_user, "recruiter": recruiter}

    return override


# ---------------------------------------------------------------------------
# Smoke: routes exist
# ---------------------------------------------------------------------------


def test_recruiter_webapp_routes_exist():
    """All recruiter webapp routes are registered."""
    app = create_app()
    routes = [r.path for r in app.routes]
    assert any("/api/webapp/recruiter/dashboard" in r for r in routes)
    assert any("/api/webapp/recruiter/incoming" in r for r in routes)
    assert any("/api/webapp/recruiter/candidates" in r for r in routes)


# ---------------------------------------------------------------------------
# Endpoint: dashboard
# ---------------------------------------------------------------------------


def test_dashboard_returns_kpis(app, recruiter_and_candidate):
    rec_id, _ = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.get("/api/webapp/recruiter/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "waiting_candidates_total" in data
    assert "scheduled_today" in data
    assert "free_slots" in data
    assert "recruiter_name" in data

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Endpoint: incoming
# ---------------------------------------------------------------------------


def test_incoming_returns_candidates(app, recruiter_and_candidate):
    rec_id, _ = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.get("/api/webapp/recruiter/incoming")
    assert resp.status_code == 200
    data = resp.json()
    assert "candidates" in data
    assert "total" in data
    assert isinstance(data["candidates"], list)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Endpoint: candidate detail
# ---------------------------------------------------------------------------


def test_candidate_detail(app, recruiter_and_candidate):
    rec_id, cand_id = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.get(f"/api/webapp/recruiter/candidates/{cand_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == cand_id
    assert data["fio"] == "Иван Тестов"
    assert data["city"] == "Москва"
    assert data["status"] == "test1_completed"
    assert isinstance(data["transitions"], list)
    assert len(data["transitions"]) > 0  # test1_completed has transitions

    app.dependency_overrides.clear()


def test_candidate_detail_not_found(app, recruiter_and_candidate):
    rec_id, _ = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.get("/api/webapp/recruiter/candidates/999999")
    assert resp.status_code == 404

    app.dependency_overrides.clear()


def test_candidate_detail_allows_unowned_candidate_from_recruiter_city(app, recruiter_access_matrix):
    rec_id = recruiter_access_matrix["allowed_recruiter_id"]
    cand_id = recruiter_access_matrix["city_routed_candidate_id"]
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.get(f"/api/webapp/recruiter/candidates/{cand_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == cand_id

    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path_template", "payload"),
    [
        ("GET", "/api/webapp/recruiter/candidates/{candidate_id}", None),
        ("POST", "/api/webapp/recruiter/candidates/{candidate_id}/status", {"status": "waiting_slot"}),
        ("POST", "/api/webapp/recruiter/candidates/{candidate_id}/message", {"text": "Привет"}),
        ("POST", "/api/webapp/recruiter/candidates/{candidate_id}/notes", {"text": "internal note"}),
    ],
)
def test_recruiter_cannot_access_other_recruiters_candidate(
    app,
    recruiter_access_matrix,
    method,
    path_template,
    payload,
):
    rec_id = recruiter_access_matrix["allowed_recruiter_id"]
    cand_id = recruiter_access_matrix["other_recruiter_candidate_id"]
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    path = path_template.format(candidate_id=cand_id)
    if method == "GET":
        resp = client.get(path)
    else:
        resp = client.post(path, json=payload)

    assert resp.status_code == 404

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Endpoint: status update
# ---------------------------------------------------------------------------


def test_status_update_valid(app, recruiter_and_candidate):
    rec_id, cand_id = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.post(
        f"/api/webapp/recruiter/candidates/{cand_id}/status",
        json={"status": "waiting_slot"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "обновлён" in data["message"].lower() or "обновлён" in data["message"]

    app.dependency_overrides.clear()


def test_status_update_invalid_status(app, recruiter_and_candidate):
    rec_id, cand_id = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.post(
        f"/api/webapp/recruiter/candidates/{cand_id}/status",
        json={"status": "nonexistent_status"},
    )
    assert resp.status_code == 400

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Endpoint: notes
# ---------------------------------------------------------------------------


def test_send_message_persists_candidate_chat(app, recruiter_and_candidate):
    rec_id, cand_id = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)
    bot_stub = DummyBotService()
    app.state.bot_service = bot_stub

    client = TestClient(app)
    resp = client.post(
        f"/api/webapp/recruiter/candidates/{cand_id}/message",
        json={"text": "Напишите, пожалуйста, когда вам удобно."},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert bot_stub.calls == [
        {
            "telegram_id": 999888777,
            "text": "Напишите, пожалуйста, когда вам удобно.",
        }
    ]

    async def _load_messages():
        async with async_session() as session:
            return (
                await session.execute(
                    select(ChatMessage).where(ChatMessage.candidate_id == cand_id)
                )
            ).scalars().all()

    messages = asyncio.get_event_loop().run_until_complete(_load_messages())
    assert len(messages) == 1
    assert messages[0].text == "Напишите, пожалуйста, когда вам удобно."
    assert messages[0].author_label == "Тест Рекрутер"

    app.dependency_overrides.clear()


def test_save_note(app, recruiter_and_candidate):
    rec_id, cand_id = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.post(
        f"/api/webapp/recruiter/candidates/{cand_id}/notes",
        json={"text": "Хороший кандидат, быстро отвечает на вопросы."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True

    async def _load_note():
        async with async_session() as session:
            return (
                await session.execute(
                    select(InterviewNote).where(InterviewNote.user_id == cand_id)
                )
            ).scalar_one_or_none()

    note = asyncio.get_event_loop().run_until_complete(_load_note())
    assert note is not None
    quick_notes = list((note.data or {}).get("recruiter_quick_notes") or [])
    assert quick_notes
    assert quick_notes[-1]["text"] == "Хороший кандидат, быстро отвечает на вопросы."
    assert quick_notes[-1]["author"] == "Тест Рекрутер"

    app.dependency_overrides.clear()


def test_save_note_not_found(app, recruiter_and_candidate):
    rec_id, _ = recruiter_and_candidate
    app.dependency_overrides[get_recruiter_webapp_auth] = _make_auth_override(rec_id)

    client = TestClient(app)
    resp = client.post(
        "/api/webapp/recruiter/candidates/999999/notes",
        json={"text": "test note"},
    )
    assert resp.status_code == 404

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth: unauthenticated returns 401/422
# ---------------------------------------------------------------------------


def test_dashboard_no_auth_returns_error():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/webapp/recruiter/dashboard")
    # Without X-Telegram-Init-Data header, should get 422 (missing header)
    assert resp.status_code in (401, 422)
