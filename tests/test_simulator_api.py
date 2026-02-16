from __future__ import annotations

import pytest
from backend.apps.admin_ui.app import create_app
from fastapi.testclient import TestClient


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def simulator_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("SIMULATOR_ENABLED", "1")
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


@pytest.fixture
def disabled_simulator_app(monkeypatch):
    async def fake_setup(app) -> _DummyIntegration:
        return _DummyIntegration()

    monkeypatch.setenv("SIMULATOR_ENABLED", "0")
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


@pytest.mark.parametrize(
    ("scenario", "expected_status"),
    [
        ("happy_path", "completed"),
        ("reschedule_loop", "completed"),
        ("decline_path", "completed"),
        ("intro_day_missing_feedback", "failed"),
    ],
)
def test_simulator_run_and_report(simulator_app, scenario: str, expected_status: str):
    with TestClient(simulator_app) as client:
        csrf = client.get("/api/csrf", auth=("admin", "admin"))
        assert csrf.status_code == 200
        token = csrf.json().get("token")
        assert token

        created = client.post(
            "/api/simulator/runs",
            auth=("admin", "admin"),
            headers={"x-csrf-token": token},
            json={"scenario": scenario},
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload["ok"] is True
        run = payload["run"]
        run_id = int(run["id"])
        assert run["scenario"] == scenario
        assert run["status"] == expected_status
        assert run["summary"]["total_steps"] == len(run["steps"])

        fetched = client.get(f"/api/simulator/runs/{run_id}", auth=("admin", "admin"))
        assert fetched.status_code == 200
        run_payload = fetched.json()["run"]
        assert run_payload["id"] == run_id
        assert run_payload["status"] == expected_status

        report = client.get(f"/api/simulator/runs/{run_id}/report", auth=("admin", "admin"))
        assert report.status_code == 200
        report_payload = report.json()["report"]
        assert report_payload["summary"]["final_status"] == expected_status
        assert isinstance(report_payload["steps"], list)


def test_simulator_disabled_returns_404(disabled_simulator_app):
    with TestClient(disabled_simulator_app) as client:
        response = client.get("/api/simulator/runs/1", auth=("admin", "admin"))
        assert response.status_code == 404
        payload = response.json()
        assert payload.get("detail", {}).get("message") == "Simulator disabled"
