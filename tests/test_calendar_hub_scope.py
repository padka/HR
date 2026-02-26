from __future__ import annotations

import pytest
from backend.apps.admin_ui.calendar_hub import CalendarHub


class _StubWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.accepted = False
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        if self.fail_send:
            raise RuntimeError("send failed")
        self.messages.append(payload)


def _payload(*, recruiter_id: int, city_id: int, extra_extended: dict | None = None) -> dict:
    extended = {
        "event_type": "slot",
        "slot_id": 1001,
        "status": "booked",
        "status_label": "Забронирован",
        "recruiter_id": recruiter_id,
        "recruiter_name": "Recruiter",
        "recruiter_tz": "Europe/Moscow",
        "city_id": city_id,
        "city_name": "Moscow",
        "city_tz": "Europe/Moscow",
        "candidate_id": 501,
        "candidate_name": "Candidate",
        "duration_min": 45,
        "local_start": "2026-02-25T10:00:00+03:00",
        "local_end": "2026-02-25T10:45:00+03:00",
        "local_date": "2026-02-25",
    }
    if extra_extended:
        extended.update(extra_extended)
    return {
        "type": "slot_change",
        "change_type": "updated",
        "slot_id": 1001,
        "recruiter_id": recruiter_id,
        "slot": {
            "id": "slot-1001",
            "title": "Interview",
            "extendedProps": extended,
        },
        "timestamp": "2026-02-25T10:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_recruiter_receives_only_allowed_scope_events() -> None:
    hub = CalendarHub()
    admin_ws = _StubWebSocket()
    recruiter_ws = _StubWebSocket()

    await hub.connect(admin_ws, principal_type="admin", principal_id=1)
    await hub.connect(recruiter_ws, principal_type="recruiter", principal_id=42, city_ids={7})

    blocked = _payload(recruiter_id=77, city_id=9)
    await hub.broadcast(blocked)

    assert len(admin_ws.messages) == 1
    assert len(recruiter_ws.messages) == 0

    by_recruiter = _payload(recruiter_id=42, city_id=9)
    await hub.broadcast(by_recruiter)
    assert len(recruiter_ws.messages) == 1
    assert recruiter_ws.messages[0]["slot"]["extendedProps"]["recruiter_id"] == 42

    by_city = _payload(recruiter_id=77, city_id=7)
    await hub.broadcast(by_city)
    assert len(recruiter_ws.messages) == 2
    assert recruiter_ws.messages[1]["slot"]["extendedProps"]["city_id"] == 7


@pytest.mark.asyncio
async def test_recruiter_payload_is_sanitized() -> None:
    hub = CalendarHub()
    admin_ws = _StubWebSocket()
    recruiter_ws = _StubWebSocket()
    await hub.connect(admin_ws, principal_type="admin", principal_id=1)
    await hub.connect(recruiter_ws, principal_type="recruiter", principal_id=42, city_ids={7})

    payload = _payload(
        recruiter_id=42,
        city_id=7,
        extra_extended={
            "internal_note": "secret",
            "candidate_phone": "+70000000000",
        },
    )
    await hub.broadcast(payload)

    admin_extended = admin_ws.messages[0]["slot"]["extendedProps"]
    recruiter_extended = recruiter_ws.messages[0]["slot"]["extendedProps"]

    assert admin_extended["internal_note"] == "secret"
    assert admin_extended["candidate_phone"] == "+70000000000"
    assert "internal_note" not in recruiter_extended
    assert "candidate_phone" not in recruiter_extended


@pytest.mark.asyncio
async def test_broadcast_removes_stale_websocket_client() -> None:
    hub = CalendarHub()
    healthy = _StubWebSocket()
    stale = _StubWebSocket(fail_send=True)

    await hub.connect(healthy, principal_type="admin", principal_id=1)
    await hub.connect(stale, principal_type="admin", principal_id=2)
    assert hub.client_count == 2

    await hub.broadcast(_payload(recruiter_id=10, city_id=3))
    assert hub.client_count == 1
    assert len(healthy.messages) == 1

