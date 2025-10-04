from datetime import datetime, timezone

from backend.apps.admin_ui.utils import recruiter_time_to_utc


def test_recruiter_time_to_utc_handles_ambiguous_time():
    dt_utc = recruiter_time_to_utc("2024-10-27", "02:30", "Europe/Berlin")
    assert dt_utc == datetime(2024, 10, 27, 0, 30, tzinfo=timezone.utc)


def test_recruiter_time_to_utc_rejects_nonexistent_time():
    dt_utc = recruiter_time_to_utc("2024-03-31", "02:30", "Europe/Berlin")
    assert dt_utc is None
