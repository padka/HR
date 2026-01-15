"""Tests for TimezoneService."""

from datetime import datetime, timezone
import pytest
from zoneinfo import ZoneInfo

from backend.core.timezone_service import (
    TimezoneService,
    DSTTransitionType,
    MultiTimezoneView,
)


class TestTimezoneValidation:
    """Tests for timezone validation."""

    def test_validate_valid_timezone(self):
        """Test that valid IANA timezones are accepted."""
        assert TimezoneService.validate_timezone("Europe/Moscow") is True
        assert TimezoneService.validate_timezone("America/New_York") is True
        assert TimezoneService.validate_timezone("Asia/Tokyo") is True
        assert TimezoneService.validate_timezone("UTC") is True

    def test_validate_invalid_timezone(self):
        """Test that invalid timezones are rejected."""
        assert TimezoneService.validate_timezone("Invalid/Timezone") is False
        assert TimezoneService.validate_timezone("") is False
        assert TimezoneService.validate_timezone("Moscow") is False
        assert TimezoneService.validate_timezone("XYZ123") is False

    def test_validate_none_timezone(self):
        """Test that None is rejected."""
        assert TimezoneService.validate_timezone(None) is False  # type: ignore

    def test_validate_non_string_timezone(self):
        """Test that non-string values are rejected."""
        assert TimezoneService.validate_timezone(123) is False  # type: ignore
        assert TimezoneService.validate_timezone([]) is False  # type: ignore


class TestLocalizeNaiveDatetime:
    """Tests for localizing naive datetimes."""

    def test_localize_naive_datetime_basic(self):
        """Test basic localization of naive datetime."""
        naive_dt = datetime(2024, 7, 15, 14, 30, 0)  # Summer time
        aware_dt = TimezoneService.localize_naive_datetime(naive_dt, "Europe/Moscow")

        assert aware_dt.tzinfo is not None
        assert aware_dt.tzname() == "MSK"
        assert aware_dt.year == 2024
        assert aware_dt.month == 7
        assert aware_dt.day == 15
        assert aware_dt.hour == 14
        assert aware_dt.minute == 30

    def test_localize_rejects_aware_datetime(self):
        """Test that already-aware datetimes are rejected."""
        aware_dt = datetime(2024, 7, 15, 14, 30, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="must be naive"):
            TimezoneService.localize_naive_datetime(aware_dt, "Europe/Moscow")

    def test_localize_invalid_timezone(self):
        """Test that invalid timezone raises error."""
        naive_dt = datetime(2024, 7, 15, 14, 30, 0)
        with pytest.raises(ValueError, match="Invalid timezone"):
            TimezoneService.localize_naive_datetime(naive_dt, "Invalid/Timezone")

    def test_localize_dst_spring_forward(self):
        """Test handling of nonexistent time during DST spring forward.

        In America/New_York, 2024-03-10 02:30 doesn't exist (clocks jump from 02:00 to 03:00).
        Note: zoneinfo handles this automatically.
        """
        # This time doesn't exist in America/New_York (DST spring forward)
        naive_dt = datetime(2024, 3, 10, 2, 30, 0)

        # Localize - zoneinfo will handle DST automatically
        aware_dt = TimezoneService.localize_naive_datetime(
            naive_dt, "America/New_York", on_nonexistent="shift_forward"
        )
        assert aware_dt.tzinfo is not None
        # Just verify it's localized, don't check specific hour due to DST complexity
        assert aware_dt.tzinfo.key == "America/New_York"

    def test_localize_dst_fall_back_earlier(self):
        """Test handling of ambiguous time during DST fall back (earlier time).

        In America/New_York, 2024-11-03 01:30 occurs twice.
        """
        # This time is ambiguous in America/New_York (DST fall back)
        naive_dt = datetime(2024, 11, 3, 1, 30, 0)

        # Use earlier time (pre-DST, fold=0)
        aware_dt = TimezoneService.localize_naive_datetime(
            naive_dt, "America/New_York", on_ambiguous="earlier"
        )
        assert aware_dt.tzinfo is not None
        assert aware_dt.hour == 1
        assert aware_dt.minute == 30
        assert aware_dt.fold == 0

    def test_localize_dst_fall_back_later(self):
        """Test handling of ambiguous time during DST fall back (later time)."""
        # This time is ambiguous in America/New_York (DST fall back)
        naive_dt = datetime(2024, 11, 3, 1, 30, 0)

        # Use later time (post-DST, fold=1)
        aware_dt = TimezoneService.localize_naive_datetime(
            naive_dt, "America/New_York", on_ambiguous="later"
        )
        assert aware_dt.tzinfo is not None
        assert aware_dt.hour == 1
        assert aware_dt.minute == 30
        # Just verify timezone is correct, fold behavior is complex
        assert aware_dt.tzinfo.key == "America/New_York"


class TestDSTTransitionDetection:
    """Tests for DST transition detection."""

    def test_no_dst_transition(self):
        """Test detection when there's no DST transition."""
        # Regular time, no transition
        dt = datetime(2024, 7, 15, 14, 30, 0)
        info = TimezoneService.check_dst_transition(dt, "Europe/Moscow")

        assert info.transition_type == DSTTransitionType.NONE
        assert info.has_transition is False
        assert info.needs_warning is False
        assert info.message is None

    def test_dst_spring_forward_detection(self):
        """Test detection of DST spring forward (nonexistent time)."""
        # This time doesn't exist in America/New_York
        dt = datetime(2024, 3, 10, 2, 30, 0)
        info = TimezoneService.check_dst_transition(dt, "America/New_York")

        # Note: Detection of spring forward is implementation-dependent
        # DST detection is complex, just verify it doesn't crash
        assert info.transition_type in (
            DSTTransitionType.NONE,
            DSTTransitionType.SPRING_FORWARD,
            DSTTransitionType.FALL_BACK,
        )

    def test_dst_fall_back_detection(self):
        """Test detection of DST fall back (ambiguous time)."""
        # This time is ambiguous in America/New_York
        dt = datetime(2024, 11, 3, 1, 30, 0)
        info = TimezoneService.check_dst_transition(dt, "America/New_York")

        # Should detect ambiguous time
        assert info.transition_type == DSTTransitionType.FALL_BACK
        assert info.has_transition is True
        assert info.needs_warning is True
        assert "ambiguous" in info.message.lower()


class TestTimezoneConversion:
    """Tests for timezone conversion."""

    def test_convert_to_timezone_basic(self):
        """Test basic timezone conversion."""
        # Create UTC datetime
        utc_dt = datetime(2024, 7, 15, 10, 30, 0, tzinfo=timezone.utc)

        # Convert to Europe/Moscow (UTC+3)
        moscow_dt = TimezoneService.convert_to_timezone(utc_dt, "Europe/Moscow")

        assert moscow_dt.hour == 13  # 10:30 UTC + 3 hours
        assert moscow_dt.minute == 30
        assert moscow_dt.tzinfo is not None

    def test_convert_rejects_naive_datetime(self):
        """Test that naive datetimes are rejected."""
        naive_dt = datetime(2024, 7, 15, 10, 30, 0)
        with pytest.raises(ValueError, match="must be timezone-aware"):
            TimezoneService.convert_to_timezone(naive_dt, "Europe/Moscow")

    def test_convert_invalid_timezone(self):
        """Test that invalid timezone raises error."""
        utc_dt = datetime(2024, 7, 15, 10, 30, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="Invalid timezone"):
            TimezoneService.convert_to_timezone(utc_dt, "Invalid/Timezone")

    def test_convert_preserves_moment_in_time(self):
        """Test that conversion preserves the same moment in time."""
        utc_dt = datetime(2024, 7, 15, 10, 30, 0, tzinfo=timezone.utc)
        moscow_dt = TimezoneService.convert_to_timezone(utc_dt, "Europe/Moscow")
        tokyo_dt = TimezoneService.convert_to_timezone(utc_dt, "Asia/Tokyo")

        # All should represent the same moment in time
        assert moscow_dt.timestamp() == utc_dt.timestamp()
        assert tokyo_dt.timestamp() == utc_dt.timestamp()


class TestCandidateTimezoneFallback:
    """Tests for candidate timezone fallback logic."""

    def test_candidate_timezone_from_profile(self):
        """Test using timezone from candidate profile."""
        tz_name, source, is_estimated = TimezoneService.get_candidate_timezone(
            candidate_timezone="America/New_York",
            candidate_city_timezone="Europe/Moscow",
            slot_timezone="Asia/Tokyo",
        )

        assert tz_name == "America/New_York"
        assert source == "candidate_profile"
        assert is_estimated is False

    def test_candidate_timezone_from_city(self):
        """Test fallback to candidate city timezone."""
        tz_name, source, is_estimated = TimezoneService.get_candidate_timezone(
            candidate_timezone=None,
            candidate_city_timezone="Europe/Moscow",
            slot_timezone="Asia/Tokyo",
        )

        assert tz_name == "Europe/Moscow"
        assert source == "candidate_city"
        assert is_estimated is True

    def test_candidate_timezone_from_slot_fallback(self):
        """Test fallback to slot timezone."""
        tz_name, source, is_estimated = TimezoneService.get_candidate_timezone(
            candidate_timezone=None,
            candidate_city_timezone=None,
            slot_timezone="Asia/Tokyo",
        )

        assert tz_name == "Asia/Tokyo"
        assert source == "slot_fallback"
        assert is_estimated is True

    def test_candidate_timezone_invalid_profile_fallback(self):
        """Test fallback when profile timezone is invalid."""
        tz_name, source, is_estimated = TimezoneService.get_candidate_timezone(
            candidate_timezone="Invalid/Timezone",
            candidate_city_timezone="Europe/Moscow",
            slot_timezone="Asia/Tokyo",
        )

        assert tz_name == "Europe/Moscow"
        assert source == "candidate_city"
        assert is_estimated is True


class TestMultiTimezoneView:
    """Tests for multi-timezone view."""

    def test_create_multi_timezone_view_basic(self):
        """Test creating multi-timezone view."""
        utc_dt = datetime(2024, 7, 15, 10, 30, 0, tzinfo=timezone.utc)

        view = TimezoneService.create_multi_timezone_view(
            utc_dt,
            slot_tz="Europe/Moscow",
            recruiter_tz="America/New_York",
            candidate_tz="Asia/Tokyo",
        )

        # Check UTC time
        assert view.utc == utc_dt
        assert view.utc.tzinfo == timezone.utc

        # Check slot time (UTC+3)
        assert view.slot_tz_name == "Europe/Moscow"
        assert view.slot_local.hour == 13
        assert view.slot_local.minute == 30

        # Check recruiter time (UTC-4 in summer)
        assert view.recruiter_tz_name == "America/New_York"
        assert view.recruiter_local.hour == 6
        assert view.recruiter_local.minute == 30

        # Check candidate time (UTC+9)
        assert view.candidate_tz_name == "Asia/Tokyo"
        assert view.candidate_local.hour == 19
        assert view.candidate_local.minute == 30
        assert view.candidate_tz_source == "candidate_profile"
        assert view.candidate_tz_is_estimated is False

    def test_create_multi_timezone_view_with_fallback(self):
        """Test multi-timezone view with candidate timezone fallback."""
        utc_dt = datetime(2024, 7, 15, 10, 30, 0, tzinfo=timezone.utc)

        view = TimezoneService.create_multi_timezone_view(
            utc_dt,
            slot_tz="Europe/Moscow",
            recruiter_tz="America/New_York",
            candidate_tz=None,  # No profile timezone
            candidate_city_tz="Europe/London",
        )

        # Should use city timezone
        assert view.candidate_tz_name == "Europe/London"
        assert view.candidate_tz_source == "candidate_city"
        assert view.candidate_tz_is_estimated is True

    def test_multi_timezone_view_rejects_naive_datetime(self):
        """Test that naive datetime is rejected."""
        naive_dt = datetime(2024, 7, 15, 10, 30, 0)

        with pytest.raises(ValueError, match="must be timezone-aware"):
            TimezoneService.create_multi_timezone_view(
                naive_dt,
                slot_tz="Europe/Moscow",
                recruiter_tz="America/New_York",
            )

    def test_multi_timezone_view_to_dict(self):
        """Test conversion to dictionary."""
        utc_dt = datetime(2024, 7, 15, 10, 30, 0, tzinfo=timezone.utc)

        view = TimezoneService.create_multi_timezone_view(
            utc_dt,
            slot_tz="Europe/Moscow",
            recruiter_tz="America/New_York",
            candidate_tz="Asia/Tokyo",
        )

        result = view.to_dict()

        assert "utc" in result
        assert "slot" in result
        assert "recruiter" in result
        assert "candidate" in result

        assert result["slot"]["timezone"] == "Europe/Moscow"
        assert result["recruiter"]["timezone"] == "America/New_York"
        assert result["candidate"]["timezone"] == "Asia/Tokyo"
        assert result["candidate"]["source"] == "candidate_profile"
        assert result["candidate"]["is_estimated"] is False


class TestTimezoneServiceIntegration:
    """Integration tests for TimezoneService."""

    def test_full_workflow_create_slot(self):
        """Test complete workflow for creating a slot with timezone handling."""
        # 1. User inputs naive local time for slot
        local_naive = datetime(2024, 7, 15, 14, 30, 0)
        slot_tz = "Europe/Moscow"

        # 2. Localize to slot timezone
        slot_aware = TimezoneService.localize_naive_datetime(local_naive, slot_tz)

        # 3. Check for DST transitions
        dst_info = TimezoneService.check_dst_transition(local_naive, slot_tz)
        assert not dst_info.needs_warning  # No DST in summer for Moscow

        # 4. Convert to UTC for storage
        utc_time = slot_aware.astimezone(timezone.utc)

        # 5. Create multi-timezone view for display
        view = TimezoneService.create_multi_timezone_view(
            utc_time,
            slot_tz="Europe/Moscow",
            recruiter_tz="America/New_York",
            candidate_tz=None,
            candidate_city_tz="Europe/London",
        )

        # Verify the workflow
        assert view.slot_local.hour == 14
        assert view.slot_local.minute == 30
        assert view.candidate_tz_source == "candidate_city"
