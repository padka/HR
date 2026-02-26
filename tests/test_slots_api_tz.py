import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

os.environ.setdefault("ADMIN_USER", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain import models


async def _async_request(app, method: str, path: str, **kwargs: Dict[str, Any]):
    def _call() -> Any:
        with TestClient(app) as client:
            settings = get_settings()
            if settings.admin_username and settings.admin_password:
                client.auth = (settings.admin_username, settings.admin_password)
            return client.request(method, path, **kwargs)

    return await asyncio.to_thread(_call)


async def _create_recruiter_and_city(name: str, tz: str) -> Dict[str, int]:
    async with async_session() as session:
        recruiter = models.Recruiter(name=f"{name} Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name=f"{name} City", tz=tz, active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)
        return {"recruiter_id": recruiter.id, "city_id": city.id}


@pytest.mark.asyncio
async def test_post_slot_uses_region_timezone_moscow():
    ids = await _create_recruiter_and_city("Moscow", "Europe/Moscow")
    app = create_app()

    response = await _async_request(
        app,
        "post",
        "/slots",
        json={
            "recruiter_id": ids["recruiter_id"],
            "region_id": ids["city_id"],
            "starts_at_local": "2025-10-06T10:00",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["starts_at_utc"].startswith("2025-10-06T07:00:00")

    async with async_session() as session:
        slot = await session.get(models.Slot, payload["id"])
        assert slot is not None
        assert slot.start_utc.astimezone(timezone.utc) == datetime(2025, 10, 6, 7, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_post_slot_uses_region_timezone_novosibirsk():
    ids = await _create_recruiter_and_city("Novosibirsk", "Asia/Novosibirsk")
    app = create_app()

    response = await _async_request(
        app,
        "post",
        "/slots",
        json={
            "recruiter_id": ids["recruiter_id"],
            "region_id": ids["city_id"],
            "starts_at_local": "2025-10-06T10:00",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["starts_at_utc"].startswith("2025-10-06T03:00:00")

    async with async_session() as session:
        slot = await session.get(models.Slot, payload["id"])
        assert slot is not None
        assert slot.start_utc.astimezone(timezone.utc) == datetime(2025, 10, 6, 3, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_post_slot_persists_region_timezones_for_free_slot():
    ids = await _create_recruiter_and_city("Almaty", "Asia/Almaty")
    app = create_app()

    response = await _async_request(
        app,
        "post",
        "/slots",
        json={
            "recruiter_id": ids["recruiter_id"],
            "region_id": ids["city_id"],
            "starts_at_local": "2025-10-06T20:00",
        },
    )
    assert response.status_code == 201
    payload = response.json()

    async with async_session() as session:
        slot = await session.get(models.Slot, payload["id"])
        assert slot is not None
        assert slot.tz_name == "Asia/Almaty"
        assert slot.candidate_tz == "Asia/Almaty"
        assert slot.candidate_city_id == ids["city_id"]


@pytest.mark.asyncio
async def test_get_slot_returns_local_time():
    ids = await _create_recruiter_and_city("LocalView", "Asia/Novosibirsk")
    async with async_session() as session:
        slot = models.Slot(
            recruiter_id=ids["recruiter_id"],
            city_id=ids["city_id"],
            start_utc=datetime(2025, 10, 6, 3, 0, tzinfo=timezone.utc),
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    app = create_app()
    response = await _async_request(app, "get", f"/slots/{slot_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["starts_at_local"].startswith("2025-10-06T10:00:00")


@pytest.mark.asyncio
async def test_post_requires_region_and_valid_timezone():
    ids = await _create_recruiter_and_city("Broken", "Europe/Moscow")
    app = create_app()

    missing_region = await _async_request(
        app,
        "post",
        "/slots",
        json={
            "recruiter_id": ids["recruiter_id"],
            "starts_at_local": "2025-10-06T10:00",
        },
    )
    assert missing_region.status_code == 422

    async with async_session() as session:
        await session.execute(
            update(models.City)
            .where(models.City.id == ids["city_id"])
            .values(tz="Invalid/Zone")
        )
        await session.commit()

    invalid_tz = await _async_request(
        app,
        "post",
        "/slots",
        json={
            "recruiter_id": ids["recruiter_id"],
            "region_id": ids["city_id"],
            "starts_at_local": "2025-10-06T10:00",
        },
    )
    assert invalid_tz.status_code == 422
    assert "timezone" in invalid_tz.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_post_allows_starts_at_utc_for_compatibility():
    ids = await _create_recruiter_and_city("Compat", "Europe/Moscow")
    app = create_app()

    response = await _async_request(
        app,
        "post",
        "/slots",
        json={
            "recruiter_id": ids["recruiter_id"],
            "region_id": ids["city_id"],
            "starts_at_utc": "2025-10-06T07:00:00+00:00",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["starts_at_utc"].startswith("2025-10-06T07:00:00")


@pytest.mark.asyncio
async def test_put_slot_updates_timezones_for_free_slot():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Update TZ Recruiter", tz="Europe/Moscow", active=True)
        city_moscow = models.City(name="Update TZ Moscow", tz="Europe/Moscow", active=True)
        city_almaty = models.City(name="Update TZ Almaty", tz="Asia/Almaty", active=True)
        session.add_all([recruiter, city_moscow, city_almaty])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city_moscow)
        await session.refresh(city_almaty)

        city_moscow.responsible_recruiter_id = recruiter.id
        city_almaty.responsible_recruiter_id = recruiter.id
        await session.commit()

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city_moscow.id,
            candidate_city_id=city_moscow.id,
            tz_name="Europe/Moscow",
            candidate_tz="Europe/Moscow",
            start_utc=datetime(2025, 10, 6, 7, 0, tzinfo=timezone.utc),
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    app = create_app()
    response = await _async_request(
        app,
        "put",
        f"/slots/{slot_id}",
        json={
            "recruiter_id": recruiter.id,
            "region_id": city_almaty.id,
            "starts_at_local": "2025-10-06T20:00",
        },
    )
    assert response.status_code == 200

    async with async_session() as session:
        updated = await session.get(models.Slot, slot_id)
        assert updated is not None
        assert updated.city_id == city_almaty.id
        assert updated.candidate_city_id == city_almaty.id
        assert updated.tz_name == "Asia/Almaty"
        assert updated.candidate_tz == "Asia/Almaty"
