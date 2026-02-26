import asyncio

import pytest
from backend.apps.admin_ui.app import create_app
from backend.core import settings as settings_module
from backend.core.auth import verify_password as verify_auth_password
from backend.core.db import async_session
from backend.core.passwords import hash_password
from backend.domain import models
from backend.domain.auth_account import AuthAccount
from fastapi.testclient import TestClient
from sqlalchemy import select


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def profile_settings_app(monkeypatch):
    async def fake_setup(app):
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass-123")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


async def _create_recruiter_account(*, username: str, password: str) -> int:
    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(
            name="Recruiter Alpha",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=79900011,
            telemost_url="https://telemost.yandex.ru/j/alpha-room",
        )
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        account = AuthAccount(
            username=username,
            password_hash=hash_password(password),
            principal_type="recruiter",
            principal_id=recruiter.id,
            is_active=True,
        )
        session.add(account)
        await session.commit()
        return recruiter.id


async def _get_recruiter_state(recruiter_id: int) -> dict[str, str | int | bool | None]:
    async with async_session() as session:
        recruiter = await session.get(models.Recruiter, recruiter_id)
        assert recruiter is not None
        return {
            "name": recruiter.name,
            "tz": recruiter.tz,
            "telemost_url": recruiter.telemost_url,
            "tg_chat_id": recruiter.tg_chat_id,
        }


async def _get_recruiter_account(username: str) -> AuthAccount | None:
    async with async_session() as session:
        return await session.scalar(
            select(AuthAccount).where(
                AuthAccount.username == username,
                AuthAccount.is_active.is_(True),
            )
        )


def _login(client: TestClient, *, username: str, password: str, expected_status: int = 303) -> None:
    response = client.post(
        "/auth/login",
        data={
            "username": username,
            "password": password,
            "redirect_to": "/app/profile",
        },
        follow_redirects=False,
    )
    assert response.status_code == expected_status


def _csrf(client: TestClient) -> str:
    response = client.get("/api/csrf")
    assert response.status_code == 200
    token = response.json().get("token")
    assert token
    return str(token)


def test_recruiter_can_update_profile_settings(profile_settings_app):
    username = "recruiter_settings"
    password = "RecruiterPass123!"
    recruiter_id = asyncio.run(_create_recruiter_account(username=username, password=password))

    with TestClient(profile_settings_app) as client:
        _login(client, username=username, password=password)
        token = _csrf(client)
        response = client.patch(
            "/api/profile/settings",
            json={
                "name": "Мария Иванова",
                "tz": "Asia/Novosibirsk",
                "telemost_url": "telemost.yandex.ru/j/new-room",
            },
            headers={"x-csrf-token": token},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["recruiter"]["name"] == "Мария Иванова"
        assert payload["recruiter"]["tz"] == "Asia/Novosibirsk"
        assert payload["recruiter"]["telemost_url"] == "https://telemost.yandex.ru/j/new-room"

        profile = client.get("/api/profile")
        assert profile.status_code == 200
        profile_payload = profile.json()
        assert profile_payload["recruiter"]["name"] == "Мария Иванова"
        assert profile_payload["recruiter"]["tz"] == "Asia/Novosibirsk"
        assert profile_payload["recruiter"]["telemost_url"] == "https://telemost.yandex.ru/j/new-room"

    persisted = asyncio.run(_get_recruiter_state(recruiter_id))
    assert persisted["name"] == "Мария Иванова"
    assert persisted["tz"] == "Asia/Novosibirsk"
    assert persisted["telemost_url"] == "https://telemost.yandex.ru/j/new-room"


def test_recruiter_profile_settings_reject_invalid_telemost_url(profile_settings_app):
    username = "recruiter_invalid_url"
    password = "RecruiterPass123!"
    asyncio.run(_create_recruiter_account(username=username, password=password))

    with TestClient(profile_settings_app) as client:
        _login(client, username=username, password=password)
        token = _csrf(client)
        response = client.patch(
            "/api/profile/settings",
            json={
                "name": "Мария Иванова",
                "tz": "Europe/Moscow",
                "telemost_url": "ftp://invalid.example.com/room",
            },
            headers={"x-csrf-token": token},
        )
        assert response.status_code == 400
        message = response.json()["detail"]["message"]
        assert "http/https" in message


def test_recruiter_can_change_password(profile_settings_app):
    username = "recruiter_password"
    current_password = "RecruiterPass123!"
    new_password = "RecruiterPass456!"
    asyncio.run(_create_recruiter_account(username=username, password=current_password))

    with TestClient(profile_settings_app) as client:
        _login(client, username=username, password=current_password)
        token = _csrf(client)
        response = client.post(
            "/api/profile/change-password",
            json={
                "current_password": current_password,
                "new_password": new_password,
            },
            headers={"x-csrf-token": token},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

        _login(client, username=username, password=current_password, expected_status=401)
        _login(client, username=username, password=new_password)

    account = asyncio.run(_get_recruiter_account(username))
    assert account is not None
    assert verify_auth_password(new_password, account.password_hash)
    assert not verify_auth_password(current_password, account.password_hash)


def test_recruiter_change_password_requires_valid_current_password(profile_settings_app):
    username = "recruiter_wrong_current"
    current_password = "RecruiterPass123!"
    asyncio.run(_create_recruiter_account(username=username, password=current_password))

    with TestClient(profile_settings_app) as client:
        _login(client, username=username, password=current_password)
        token = _csrf(client)
        response = client.post(
            "/api/profile/change-password",
            json={
                "current_password": "WrongPassword999!",
                "new_password": "RecruiterPass456!",
            },
            headers={"x-csrf-token": token},
        )
        assert response.status_code == 400
        message = response.json()["detail"]["message"]
        assert "неверно" in message.lower()


def test_profile_mutations_forbidden_for_admin(profile_settings_app):
    with TestClient(profile_settings_app) as client:
        _login(client, username="admin", password="admin-pass-123")
        token = _csrf(client)

        settings_response = client.patch(
            "/api/profile/settings",
            json={
                "name": "Admin User",
                "tz": "Europe/Moscow",
                "telemost_url": "https://telemost.yandex.ru/j/admin-room",
            },
            headers={"x-csrf-token": token},
        )
        assert settings_response.status_code == 403

        password_response = client.post(
            "/api/profile/change-password",
            json={
                "current_password": "admin-pass-123",
                "new_password": "AdminNewPass123!",
            },
            headers={"x-csrf-token": token},
        )
        assert password_response.status_code == 403
