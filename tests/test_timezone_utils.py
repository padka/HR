"""Tests for timezone utilities."""

import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from backend.core.timezone_utils import (
    normalize_to_utc,
    to_local_time,
    format_for_ui,
    ensure_aware,
    parse_timezone,
    get_offset_minutes,
    is_same_moment,
    datetime_range_overlap,
)


def test_parse_timezone():
    """Test timezone parsing with various formats."""
    # Standard format
    tz = parse_timezone("Europe/Moscow")
    assert str(tz) == "Europe/Moscow"

    # Case insensitive
    tz = parse_timezone("europe/moscow")
    assert str(tz) == "Europe/Moscow"

    # With spaces (should convert to underscores)
    tz = parse_timezone("America/New York")
    assert str(tz) == "America/New_York"

    # None defaults to UTC
    tz = parse_timezone(None)
    assert str(tz) == "UTC"

    # Invalid timezone raises
    with pytest.raises(ValueError):
        parse_timezone("Invalid/Timezone")


def test_ensure_aware():
    """Test making naive datetimes aware."""
    # Naive datetime with timezone
    naive = datetime(2025, 11, 26, 15, 0, 0)
    aware = ensure_aware(naive, "Europe/Moscow")
    assert aware.tzinfo is not None
    assert aware.tzname() == "MSK"

    # Naive datetime without timezone (defaults to UTC)
    aware_utc = ensure_aware(naive)
    assert aware_utc.tzinfo == timezone.utc

    # Already aware datetime (no change)
    already_aware = datetime(2025, 11, 26, 15, 0, 0, tzinfo=timezone.utc)
    result = ensure_aware(already_aware)
    assert result is already_aware


def test_normalize_to_utc():
    """Test normalization to UTC."""
    # Naive datetime from Moscow timezone
    naive = datetime(2025, 11, 26, 15, 0, 0)
    utc = normalize_to_utc(naive, "Europe/Moscow")

    assert utc.tzinfo == timezone.utc
    assert utc.hour == 12  # Moscow is UTC+3, so 15:00 MSK = 12:00 UTC

    # Already UTC datetime
    already_utc = datetime(2025, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
    result = normalize_to_utc(already_utc)
    assert result == already_utc

    # Aware datetime in different timezone
    moscow_aware = datetime(2025, 11, 26, 15, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    utc_from_moscow = normalize_to_utc(moscow_aware)
    assert utc_from_moscow.tzinfo == timezone.utc
    assert utc_from_moscow.hour == 12


def test_to_local_time():
    """Test conversion to local timezone."""
    utc_dt = datetime(2025, 11, 26, 12, 0, 0, tzinfo=timezone.utc)

    # Convert to Moscow time
    moscow_dt = to_local_time(utc_dt, "Europe/Moscow")
    assert moscow_dt.hour == 15  # UTC+3
    assert moscow_dt.tzname() == "MSK"

    # Convert to New York time (UTC-5 in winter)
    ny_dt = to_local_time(utc_dt, "America/New_York")
    # Exact hour depends on DST, but should be in EST/EDT
    assert ny_dt.tzname() in ["EST", "EDT"]

    # Naive datetime is treated as UTC
    naive = datetime(2025, 11, 26, 12, 0, 0)
    moscow_from_naive = to_local_time(naive, "Europe/Moscow")
    assert moscow_from_naive.hour == 15


def test_format_for_ui():
    """Test formatting for UI display."""
    utc_dt = datetime(2025, 11, 26, 12, 0, 0, tzinfo=timezone.utc)

    # Default format
    formatted = format_for_ui(utc_dt, "Europe/Moscow")
    assert formatted == "2025-11-26 15:00"

    # With timezone abbreviation
    formatted_tz = format_for_ui(utc_dt, "Europe/Moscow", show_tz=True)
    assert "MSK" in formatted_tz

    # Custom format
    custom = format_for_ui(utc_dt, "Europe/Moscow", format_str="%d.%m.%Y %H:%M")
    assert custom == "26.11.2025 15:00"


def test_get_offset_minutes():
    """Test getting timezone offset in minutes."""
    # Moscow is UTC+3 (no DST)
    offset = get_offset_minutes("Europe/Moscow")
    assert offset == 180  # 3 hours * 60 minutes

    # UTC
    utc_offset = get_offset_minutes("UTC")
    assert utc_offset == 0

    # Test with specific datetime
    winter_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    ny_offset = get_offset_minutes("America/New_York", winter_dt)
    # Should be -300 (UTC-5) in winter
    assert ny_offset == -300


def test_is_same_moment():
    """Test checking if two datetimes are the same moment."""
    utc = datetime(2025, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
    moscow = datetime(2025, 11, 26, 15, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))

    # Same moment in different timezones
    assert is_same_moment(utc, moscow)

    # Different moments
    later = datetime(2025, 11, 26, 13, 0, 0, tzinfo=timezone.utc)
    assert not is_same_moment(utc, later)

    # Naive datetimes (treated as UTC)
    naive1 = datetime(2025, 11, 26, 12, 0, 0)
    naive2 = datetime(2025, 11, 26, 12, 0, 0)
    assert is_same_moment(naive1, naive2)


def test_datetime_range_overlap():
    """Test checking if datetime ranges overlap."""
    base = datetime(2025, 11, 26, 12, 0, 0, tzinfo=timezone.utc)

    # Overlapping ranges
    assert datetime_range_overlap(
        base,
        base + timedelta(hours=2),
        base + timedelta(hours=1),
        base + timedelta(hours=3)
    )

    # Non-overlapping ranges
    assert not datetime_range_overlap(
        base,
        base + timedelta(hours=1),
        base + timedelta(hours=2),
        base + timedelta(hours=3)
    )

    # Adjacent ranges (no overlap)
    assert not datetime_range_overlap(
        base,
        base + timedelta(hours=1),
        base + timedelta(hours=1),
        base + timedelta(hours=2)
    )

    # Completely contained
    assert datetime_range_overlap(
        base,
        base + timedelta(hours=3),
        base + timedelta(hours=1),
        base + timedelta(hours=2)
    )

    # Different timezones
    utc_start = datetime(2025, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
    utc_end = datetime(2025, 11, 26, 14, 0, 0, tzinfo=timezone.utc)
    moscow_start = datetime(2025, 11, 26, 14, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # 11:00 UTC
    moscow_end = datetime(2025, 11, 26, 16, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # 13:00 UTC

    # UTC 12:00-14:00 overlaps with Moscow 14:00-16:00 (UTC 11:00-13:00)
    assert datetime_range_overlap(utc_start, utc_end, moscow_start, moscow_end)


def test_edge_cases():
    """Test edge cases and error handling."""
    # Empty string timezone
    with pytest.raises(ValueError):
        parse_timezone("")

    # Whitespace timezone
    tz = parse_timezone("  Europe/Moscow  ")
    assert str(tz) == "Europe/Moscow"

    # Very old datetime
    old = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    formatted = format_for_ui(old, "Europe/Moscow")
    assert "1970" in formatted

    # Future datetime
    future = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    normalized = normalize_to_utc(future)
    assert normalized.year == 2099


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
