from datetime import date, datetime, timedelta, timezone

import pytest

pytest.importorskip("starlette")
from starlette.requests import Request
from starlette.datastructures import URL

from backend.apps.admin_ui.config import register_template_globals
from backend.apps.admin_ui.routers import dashboard
from backend.apps.admin_ui.routers.slots import slots_list
from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.slots import api_slots_payload, create_slot, list_slots
from backend.core.db import async_session
from backend.domain import models
from backend.apps.bot.metrics import (
    record_test1_completion,
    record_test1_rejection,
    reset_test1_metrics,
)


class _DummySettings:
    def __init__(self) -> None:
        self.timezone = "Europe/Moscow"
        self.bot_integration_enabled = True


class _DummyState:
    bot_integration_switch = None
    bot_service = None


class _DummyURL:
    def __init__(self, path: str) -> None:
        self._path = path

    def make_absolute_url(self, base_url: URL) -> URL:
        return base_url.replace(path=self._path)


class _DummyRouter:
    def url_path_for(self, name: str, **path_params):
        if name == "static":
            path = path_params.get("path", "")
            return _DummyURL(f"/static/{path}")
        raise KeyError(name)


@pytest.mark.asyncio
async def test_dashboard_and_slot_listing():
    await reset_test1_metrics()
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="UI City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

    created, _ = await create_slot(
        recruiter_id=recruiter.id,
        date=str(date.today()),
        time="10:00",
        city_id=city.id,
    )
    assert created is True

    counts = await dashboard_counts()
    assert counts["recruiters"] == 1
    assert counts["cities"] == 1
    assert counts["slots_total"] == 1
    assert counts["test1_rejections_total"] == 0
    assert counts["test1_rejections_percent"] == 0.0

    listing = await list_slots(
        recruiter_id=None,
        status=None,
        page=1,
        per_page=10,
    )
    assert listing["total"] == 1
    assert listing["items"][0].recruiter_id == recruiter.id
    assert listing["status_counts"] == {"FREE": 1, "CONFIRMED_BY_CANDIDATE": 0}


@pytest.mark.asyncio
async def test_dashboard_reports_test1_metrics():
    await reset_test1_metrics()
    await record_test1_rejection("format_not_ready")
    await record_test1_completion()

    counts = await dashboard_counts()
    assert counts["test1_rejections_total"] == 1
    assert counts["test1_total_seen"] == 2
    assert counts["test1_rejections_percent"] == 50.0
    assert counts["test1_rejections_breakdown"]["format_not_ready"] == 1


@pytest.mark.asyncio
async def test_slots_list_status_counts_and_api_payload_normalizes_statuses():
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

        now = datetime.now(timezone.utc)
        session.add_all(
            [
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now,
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.PENDING,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=2),
                    status=models.SlotStatus.BOOKED,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=3),
                    status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
                ),
            ]
        )
        await session.commit()

    payload = await api_slots_payload(recruiter_id=None, status=None, limit=10)
    assert {item["status"] for item in payload} == {
        "FREE",
        "PENDING",
        "BOOKED",
        "CONFIRMED_BY_CANDIDATE",
    }

    register_template_globals()
    dummy_router = _DummyRouter()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/slots",
        "headers": [],
        "query_string": b"",
        "router": dummy_router,
        "app": type("App", (), {"state": _DummyState(), "router": dummy_router})(),
    }
    request = Request(scope)
    response = await slots_list(request, recruiter_id=None, status=None, page=1, per_page=10)
    status_counts = response.context["status_counts"]
    assert status_counts == {
        "total": 4,
        "FREE": 1,
        "PENDING": 1,
        "BOOKED": 1,
        "CONFIRMED_BY_CANDIDATE": 1,
    }


@pytest.mark.asyncio
async def test_dashboard_index_provides_json_serializable_context(monkeypatch):
    async def fake_dashboard_counts():
        return {"recruiters": 0, "cities": 0, "slots_total": 0}

    async def fake_weekly_kpis():
        return {
            "timezone": "Europe/Moscow",
            "current": {
                "week_start": "2024-10-07",
                "week_end": "2024-10-14",
                "label": "07.10.2024 — 13.10.2024",
                "metrics": [],
            },
            "previous": {
                "week_start": "2024-09-30",
                "week_end": "2024-10-07",
                "label": "30.09.2024 — 06.10.2024",
                "metrics": {},
                "computed_at": None,
            },
        }

    async def fake_calendar_snapshot(*args, **kwargs):
        return {
            "timezone": "Europe/Moscow",
            "selected_date": None,
            "selected_label": "нет данных",
            "selected_human": "",
            "days": [],
            "events": [],
            "events_total": 0,
            "status_summary": {
                "CONFIRMED_BY_CANDIDATE": 0,
                "BOOKED": 0,
                "PENDING": 0,
                "CANCELED": 0,
            },
            "meta": "Нет назначенных интервью",
            "updated_label": "",
        }

    monkeypatch.setattr(dashboard, "dashboard_counts", fake_dashboard_counts)
    monkeypatch.setattr(dashboard, "get_weekly_kpis", fake_weekly_kpis)
    monkeypatch.setattr(dashboard, "dashboard_calendar_snapshot", fake_calendar_snapshot)
    monkeypatch.setattr(dashboard, "get_settings", lambda: _DummySettings())

    dummy_router = _DummyRouter()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "router": dummy_router,
        "app": type("App", (), {"state": _DummyState(), "router": dummy_router})(),
    }
    request = Request(scope)

    response = await dashboard.index(request)

    assert isinstance(response.context["weekly_kpis"], dict)
    assert isinstance(response.context["calendar"], dict)

    import json

    json.dumps(response.context["weekly_kpis"])
    json.dumps(response.context["calendar"])
