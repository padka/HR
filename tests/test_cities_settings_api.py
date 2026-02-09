from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.admin_ui.routers import cities as cities_router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(cities_router.router)
    return app


def test_update_city_settings_parses_payload(monkeypatch):
    captured = {}

    async def fake_update_city_settings(city_id: int, **kwargs):
        captured["city_id"] = city_id
        captured.update(kwargs)
        recruiter_id = kwargs["recruiter_ids"][0]
        owner = SimpleNamespace(id=recruiter_id, name="Рекрутер", tz="Europe/Moscow")
        city = SimpleNamespace(
            id=city_id,
            name_plain=kwargs["name"] or "Москва",
            tz=kwargs["tz"] or "Europe/Moscow",
            active=kwargs["active"],
            criteria=kwargs["criteria"],
            experts=kwargs["experts"],
            plan_week=kwargs["plan_week"],
            plan_month=kwargs["plan_month"],
            recruiters=[owner],
        )
        return None, city, owner

    monkeypatch.setattr(
        cities_router,
        "update_city_settings_service",
        fake_update_city_settings,
    )
    app = _build_app()
    with TestClient(app) as client:
        response = client.post(
            "/cities/77/settings",
            json={
                "name": " Москва ",
                "recruiter_ids": ["42"],
                "criteria": " KPI >= 5 ",
                "experts": " Team A ",
                "plan_week": "7",
                "plan_month": "20",
                "tz": "Europe/Moscow",
                "active": "false",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert captured["city_id"] == 77
    assert captured["recruiter_ids"] == [42]
    assert captured["criteria"] == "KPI >= 5"
    assert captured["experts"] == "Team A"
    assert captured["plan_week"] == 7
    assert captured["plan_month"] == 20
    assert captured["tz"] == "Europe/Moscow"
    assert captured["active"] is False


def test_update_city_settings_rejects_invalid_plan_week():
    app = _build_app()
    with TestClient(app) as client:
        response = client.post(
            "/cities/10/settings",
            json={
                "name": "Москва",
                "plan_week": "abc",
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "ok": False,
        "error": {"field": "plan_week", "message": cities_router.PLAN_ERROR_MESSAGE},
    }
