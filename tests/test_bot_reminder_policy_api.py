from __future__ import annotations

from fastapi.testclient import TestClient

from backend.apps.admin_ui.app import create_app
from backend.core.settings import get_settings
from backend.core.content_updates import KIND_REMINDERS_CHANGED


def _configure_auth(client: TestClient) -> None:
    settings = get_settings()
    client.auth = (
        settings.admin_username or "admin",
        settings.admin_password or "admin",
    )


def test_bot_reminder_policy_api_roundtrip(monkeypatch) -> None:
    published: list[tuple[str, object]] = []

    async def _fake_publish(kind: str, payload=None, **_kwargs):
        published.append((kind, payload))
        return True

    monkeypatch.setattr(
        "backend.apps.admin_ui.state._build_bot",
        lambda settings: (None, False),
    )
    monkeypatch.setattr(
        "backend.apps.admin_ui.routers.api.publish_content_update",
        _fake_publish,
    )

    app = create_app()
    with TestClient(app) as client:
        _configure_auth(client)

        get_resp = client.get("/api/bot/reminder-policy")
        assert get_resp.status_code == 200
        initial = get_resp.json()
        assert "policy" in initial
        assert initial["policy"]["interview"]["confirm_6h"]["offset_hours"] == 6.0

        update_resp = client.put(
            "/api/bot/reminder-policy",
            json={
                "policy": {
                    "interview": {
                        "confirm_6h": {"enabled": False, "offset_hours": 4},
                        "confirm_3h": {"enabled": True, "offset_hours": 2.5},
                        "confirm_2h": {"enabled": True, "offset_hours": 1.5},
                    },
                    "intro_day": {
                        "intro_remind_3h": {"enabled": True, "offset_hours": 2},
                    },
                    "min_time_before_immediate_hours": 1.0,
                }
            },
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["ok"] is True
        assert updated["policy"]["interview"]["confirm_6h"]["enabled"] is False
        assert updated["policy"]["interview"]["confirm_3h"]["offset_hours"] == 2.5
        assert updated["policy"]["min_time_before_immediate_hours"] == 1.0
        assert any(kind == KIND_REMINDERS_CHANGED for kind, _payload in published)

        verify_resp = client.get("/api/bot/reminder-policy")
        assert verify_resp.status_code == 200
        verified = verify_resp.json()
        assert verified["policy"]["interview"]["confirm_6h"]["enabled"] is False
        assert verified["policy"]["interview"]["confirm_2h"]["offset_hours"] == 1.5
