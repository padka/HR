from datetime import datetime, timezone

import pytest

from backend.apps.admin_ui.utils import local_naive_to_utc, utc_to_local_naive


@pytest.mark.parametrize(
    "tz_name,local_hour,expected_hour",
    [
        ("Europe/Moscow", 10, 7),
        ("Asia/Novosibirsk", 10, 3),
    ],
)
def test_local_to_utc_conversion(tz_name: str, local_hour: int, expected_hour: int) -> None:
    local_dt = datetime(2025, 10, 6, local_hour, 0)
    utc_dt = local_naive_to_utc(local_dt, tz_name)
    assert utc_dt.tzinfo is not None
    assert utc_dt.astimezone(timezone.utc) == datetime(2025, 10, 6, expected_hour, 0, tzinfo=timezone.utc)
    # Reverse conversion should restore the local time without tzinfo
    back_local = utc_to_local_naive(utc_dt, tz_name)
    assert back_local == datetime(2025, 10, 6, local_hour, 0)
