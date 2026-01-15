"""Timezone service for handling timezone conversions and DST transitions.

This service provides robust timezone handling with DST awareness:
- Converts naive datetimes to aware datetimes with proper DST handling
- Provides multi-timezone views (slot TZ, recruiter TZ, candidate TZ, UTC)
- Detects DST transitions and provides warnings
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from enum import Enum
from typing import Literal, Optional
from zoneinfo import ZoneInfo, available_timezones


class DSTTransitionType(Enum):
    """Type of DST transition."""

    NONE = "none"  # No DST transition
    SPRING_FORWARD = "spring_forward"  # Nonexistent time (clocks jump forward)
    FALL_BACK = "fall_back"  # Ambiguous time (clocks jump backward)


@dataclass
class DSTTransitionInfo:
    """Information about DST transition at a specific time."""

    transition_type: DSTTransitionType
    has_transition: bool
    message: Optional[str] = None

    @property
    def needs_warning(self) -> bool:
        """Whether this transition requires a warning to the user."""
        return self.has_transition and self.transition_type != DSTTransitionType.NONE


@dataclass
class MultiTimezoneView:
    """Multi-timezone representation of a single datetime.

    Provides the same moment in time across multiple timezones:
    - UTC (canonical)
    - Slot timezone (where the slot is scheduled)
    - Recruiter timezone (recruiter's local time)
    - Candidate timezone (candidate's local time, with fallback)
    """

    utc: datetime
    slot_tz_name: str
    slot_local: datetime
    recruiter_tz_name: str
    recruiter_local: datetime
    candidate_tz_name: str
    candidate_local: datetime
    candidate_tz_source: Literal["candidate_profile", "candidate_city", "slot_fallback"]
    candidate_tz_is_estimated: bool

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "utc": self.utc.isoformat(),
            "slot": {
                "timezone": self.slot_tz_name,
                "local_time": self.slot_local.isoformat(),
            },
            "recruiter": {
                "timezone": self.recruiter_tz_name,
                "local_time": self.recruiter_local.isoformat(),
            },
            "candidate": {
                "timezone": self.candidate_tz_name,
                "local_time": self.candidate_local.isoformat(),
                "source": self.candidate_tz_source,
                "is_estimated": self.candidate_tz_is_estimated,
            },
        }


class TimezoneService:
    """Service for handling timezone conversions and DST transitions."""

    @staticmethod
    def validate_timezone(tz_name: str) -> bool:
        """Validate that a timezone name is valid IANA timezone.

        Args:
            tz_name: IANA timezone name (e.g., "Europe/Moscow")

        Returns:
            True if valid, False otherwise
        """
        if not tz_name or not isinstance(tz_name, str):
            return False

        # Check against available timezones
        return tz_name in available_timezones()

    @staticmethod
    def localize_naive_datetime(
        naive_dt: datetime,
        tz_name: str,
        *,
        on_nonexistent: Literal["raise", "shift_forward", "shift_backward"] = "shift_forward",
        on_ambiguous: Literal["raise", "earlier", "later"] = "earlier",
    ) -> datetime:
        """Convert naive datetime to timezone-aware datetime with DST handling.

        Args:
            naive_dt: Naive datetime to localize
            tz_name: IANA timezone name
            on_nonexistent: How to handle nonexistent times (DST spring forward):
                - "raise": Raise exception
                - "shift_forward": Shift to next valid time
                - "shift_backward": Shift to previous valid time
            on_ambiguous: How to handle ambiguous times (DST fall back):
                - "raise": Raise exception
                - "earlier": Use earlier time (pre-DST)
                - "later": Use later time (post-DST)

        Returns:
            Timezone-aware datetime

        Raises:
            ValueError: If timezone is invalid or datetime is already aware
        """
        if naive_dt.tzinfo is not None:
            raise ValueError("Datetime must be naive (tzinfo=None)")

        if not TimezoneService.validate_timezone(tz_name):
            raise ValueError(f"Invalid timezone: {tz_name}")

        tz = ZoneInfo(tz_name)

        # Try to localize - this will raise if nonexistent/ambiguous
        try:
            return naive_dt.replace(tzinfo=tz)
        except Exception:
            # Handle DST edge cases
            # For nonexistent times (spring forward), shift forward by 1 hour
            if on_nonexistent == "shift_forward":
                from datetime import timedelta

                return (naive_dt + timedelta(hours=1)).replace(tzinfo=tz)
            elif on_nonexistent == "shift_backward":
                from datetime import timedelta

                return (naive_dt - timedelta(hours=1)).replace(tzinfo=tz)

            # For ambiguous times (fall back), use fold parameter
            if on_ambiguous == "earlier":
                return naive_dt.replace(tzinfo=tz, fold=0)
            elif on_ambiguous == "later":
                return naive_dt.replace(tzinfo=tz, fold=1)

            raise

    @staticmethod
    def check_dst_transition(dt: datetime, tz_name: str) -> DSTTransitionInfo:
        """Check if datetime is near a DST transition.

        Args:
            dt: Datetime to check (can be naive or aware)
            tz_name: IANA timezone name

        Returns:
            DSTTransitionInfo with transition details
        """
        if not TimezoneService.validate_timezone(tz_name):
            return DSTTransitionInfo(
                transition_type=DSTTransitionType.NONE,
                has_transition=False,
                message=None,
            )

        tz = ZoneInfo(tz_name)

        # Convert to naive if aware
        if dt.tzinfo is not None:
            naive_dt = dt.replace(tzinfo=None)
        else:
            naive_dt = dt

        # Try to detect DST transition by checking fold behavior
        try:
            # Try localizing with fold=0 and fold=1
            dt_early = naive_dt.replace(tzinfo=tz, fold=0)
            dt_late = naive_dt.replace(tzinfo=tz, fold=1)

            # If UTC offsets differ, it's an ambiguous time (fall back)
            if dt_early.utcoffset() != dt_late.utcoffset():
                return DSTTransitionInfo(
                    transition_type=DSTTransitionType.FALL_BACK,
                    has_transition=True,
                    message=(
                        f"Ambiguous time due to DST fall back in {tz_name}. "
                        f"This time occurs twice."
                    ),
                )

            # Check if time is nonexistent (spring forward)
            # We do this by checking if converting back gives us the same time
            utc_time = dt_early.astimezone(dt_timezone.utc)
            back_to_local = utc_time.astimezone(tz)
            if back_to_local.replace(tzinfo=None) != naive_dt:
                return DSTTransitionInfo(
                    transition_type=DSTTransitionType.SPRING_FORWARD,
                    has_transition=True,
                    message=(
                        f"Nonexistent time due to DST spring forward in {tz_name}. "
                        f"Clocks jump forward at this time."
                    ),
                )

        except Exception:
            # If we can't determine, assume no transition
            pass

        return DSTTransitionInfo(
            transition_type=DSTTransitionType.NONE,
            has_transition=False,
            message=None,
        )

    @staticmethod
    def convert_to_timezone(dt: datetime, target_tz_name: str) -> datetime:
        """Convert datetime to target timezone.

        Args:
            dt: Source datetime (must be timezone-aware)
            target_tz_name: Target IANA timezone name

        Returns:
            Datetime in target timezone

        Raises:
            ValueError: If datetime is naive or timezone is invalid
        """
        if dt.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")

        if not TimezoneService.validate_timezone(target_tz_name):
            raise ValueError(f"Invalid timezone: {target_tz_name}")

        target_tz = ZoneInfo(target_tz_name)
        return dt.astimezone(target_tz)

    @staticmethod
    def get_candidate_timezone(
        *,
        candidate_timezone: Optional[str],
        candidate_city_timezone: Optional[str],
        slot_timezone: str,
    ) -> tuple[str, Literal["candidate_profile", "candidate_city", "slot_fallback"], bool]:
        """Determine candidate timezone with fallback logic.

        Priority:
        1. Candidate's profile timezone
        2. Candidate's city timezone
        3. Slot timezone (fallback)

        Args:
            candidate_timezone: Timezone from candidate profile
            candidate_city_timezone: Timezone from candidate's city
            slot_timezone: Slot timezone (fallback)

        Returns:
            Tuple of (timezone_name, source, is_estimated)
        """
        # Try candidate profile timezone first
        if candidate_timezone and TimezoneService.validate_timezone(candidate_timezone):
            return (candidate_timezone, "candidate_profile", False)

        # Try candidate city timezone
        if candidate_city_timezone and TimezoneService.validate_timezone(candidate_city_timezone):
            return (candidate_city_timezone, "candidate_city", True)

        # Fallback to slot timezone
        return (slot_timezone, "slot_fallback", True)

    @staticmethod
    def create_multi_timezone_view(
        utc_datetime: datetime,
        *,
        slot_tz: str,
        recruiter_tz: str,
        candidate_tz: Optional[str] = None,
        candidate_city_tz: Optional[str] = None,
    ) -> MultiTimezoneView:
        """Create multi-timezone view of a datetime.

        Args:
            utc_datetime: UTC datetime (must be timezone-aware)
            slot_tz: Slot timezone
            recruiter_tz: Recruiter timezone
            candidate_tz: Candidate profile timezone (optional)
            candidate_city_tz: Candidate city timezone (optional)

        Returns:
            MultiTimezoneView with all timezone representations

        Raises:
            ValueError: If datetime is naive or timezones are invalid
        """
        if utc_datetime.tzinfo is None:
            raise ValueError("UTC datetime must be timezone-aware")

        # Ensure it's actually in UTC
        utc_dt = utc_datetime.astimezone(dt_timezone.utc)

        # Convert to slot timezone
        slot_local = TimezoneService.convert_to_timezone(utc_dt, slot_tz)

        # Convert to recruiter timezone
        recruiter_local = TimezoneService.convert_to_timezone(utc_dt, recruiter_tz)

        # Determine candidate timezone with fallback
        candidate_tz_name, candidate_tz_source, candidate_tz_is_estimated = (
            TimezoneService.get_candidate_timezone(
                candidate_timezone=candidate_tz,
                candidate_city_timezone=candidate_city_tz,
                slot_timezone=slot_tz,
            )
        )
        candidate_local = TimezoneService.convert_to_timezone(utc_dt, candidate_tz_name)

        return MultiTimezoneView(
            utc=utc_dt,
            slot_tz_name=slot_tz,
            slot_local=slot_local,
            recruiter_tz_name=recruiter_tz,
            recruiter_local=recruiter_local,
            candidate_tz_name=candidate_tz_name,
            candidate_local=candidate_local,
            candidate_tz_source=candidate_tz_source,
            candidate_tz_is_estimated=candidate_tz_is_estimated,
        )


__all__ = [
    "TimezoneService",
    "MultiTimezoneView",
    "DSTTransitionInfo",
    "DSTTransitionType",
]
