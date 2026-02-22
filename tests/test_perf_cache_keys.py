from __future__ import annotations

from datetime import date

from backend.apps.admin_ui.perf.cache import keys
from backend.apps.admin_ui.security import Principal


def test_dashboard_keys_are_scoped_by_principal():
    a1 = Principal(type="admin", id=1)
    a2 = Principal(type="admin", id=2)

    assert keys.dashboard_counts(principal=a1).value != keys.dashboard_counts(principal=a2).value
    assert keys.dashboard_incoming(principal=a1, limit=6).value != keys.dashboard_incoming(principal=a2, limit=6).value


def test_calendar_key_normalizes_statuses_order_and_case():
    k1 = keys.calendar_events(
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 16),
        recruiter_id=10,
        city_id=None,
        statuses=["Free", "BOOKED"],
        tz_name="Europe/Moscow",
        include_canceled=False,
    ).value
    k2 = keys.calendar_events(
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 16),
        recruiter_id=10,
        city_id=None,
        statuses=["booked", "free"],
        tz_name="Europe/Moscow",
        include_canceled=False,
    ).value
    assert k1 == k2

