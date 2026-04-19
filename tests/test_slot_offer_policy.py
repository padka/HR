from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.domain.slot_offer_policy import (
    InterviewOfferMode,
    OfferableSlot,
    select_interview_offer_plan,
)


def _slot(
    slot_id: int,
    *,
    start_in_hours: int,
    recruiter_id: int,
    city_id: int = 1,
    status: str = "free",
    purpose: str = "interview",
) -> OfferableSlot:
    return OfferableSlot(
        slot_id=slot_id,
        start_utc=datetime.now(UTC) + timedelta(hours=start_in_hours),
        duration_min=30,
        recruiter_id=recruiter_id,
        city_id=city_id,
        purpose=purpose,
        status=status,
    )


def test_returns_single_recommended_slot_when_only_one_clear_fit_exists() -> None:
    plan = select_interview_offer_plan(
        [
            _slot(1, start_in_hours=2, recruiter_id=10),
            _slot(2, start_in_hours=1, recruiter_id=20),
        ],
        candidate_tz="Europe/Moscow",
        city_id=1,
        recruiter_id=10,
    )

    assert plan.mode == InterviewOfferMode.SINGLE
    assert plan.recommended_slot_id == 1
    assert len(plan.options) == 1
    assert plan.options[0].is_recommended is True


def test_returns_shortlist_for_comparable_slots() -> None:
    plan = select_interview_offer_plan(
        [
            _slot(1, start_in_hours=1, recruiter_id=10),
            _slot(2, start_in_hours=2, recruiter_id=11),
            _slot(3, start_in_hours=3, recruiter_id=12),
            _slot(4, start_in_hours=4, recruiter_id=13),
        ],
        candidate_tz="Europe/Moscow",
        city_id=1,
    )

    assert plan.mode == InterviewOfferMode.SHORTLIST
    assert len(plan.options) == 3
    assert plan.options[0].is_recommended is True
    assert [option.slot_id for option in plan.options] == [1, 2, 3]


def test_returns_fallback_when_no_offerable_slots_exist() -> None:
    plan = select_interview_offer_plan(
        [
            _slot(1, start_in_hours=-1, recruiter_id=10),
            _slot(2, start_in_hours=2, recruiter_id=11, status="pending"),
        ],
        candidate_tz="Europe/Moscow",
        city_id=1,
    )

    assert plan.mode == InterviewOfferMode.FALLBACK
    assert plan.recommended_slot_id is None
    assert plan.fallback_reason == "no_offerable_slots"


def test_payload_is_channel_agnostic() -> None:
    plan = select_interview_offer_plan(
        [_slot(1, start_in_hours=2, recruiter_id=10)],
        candidate_tz="Europe/Moscow",
        city_id=1,
    )

    payload_text = str(plan.payload)
    assert "telegram" not in payload_text.lower()
    assert "keyboard" not in payload_text.lower()
    assert "callback" not in payload_text.lower()
