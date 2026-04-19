from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from backend.core.db import async_session
from backend.domain.models import Slot, SlotStatus
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class InterviewOfferMode(str, Enum):
    SINGLE = "single"
    SHORTLIST = "shortlist"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class InterviewOfferOption:
    slot_id: int
    start_utc: datetime
    duration_min: int
    recruiter_id: int
    city_id: int | None
    score: float
    reason: str
    is_recommended: bool = False


@dataclass(frozen=True, slots=True)
class OfferableSlot:
    slot_id: int
    start_utc: datetime
    duration_min: int
    recruiter_id: int
    city_id: int | None
    purpose: str
    status: str


@dataclass(frozen=True, slots=True)
class InterviewOfferPlan:
    mode: InterviewOfferMode
    recommended_slot_id: int | None
    options: tuple[InterviewOfferOption, ...] = ()
    fallback_reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    policy_version: str = "v1"


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _option_reason(*, recruiter_match: bool) -> str:
    if recruiter_match:
        return "preferred_recruiter_earliest"
    return "earliest_city_match"


def _score_slot(
    slot: OfferableSlot,
    *,
    recruiter_id: int | None,
    now: datetime,
) -> tuple[float, bool]:
    start_utc = _ensure_aware_utc(slot.start_utc)
    minutes_until = max((start_utc - now).total_seconds() / 60.0, 0.0)
    recruiter_match = recruiter_id is not None and slot.recruiter_id == recruiter_id
    score = (1000.0 if recruiter_match else 0.0) - (minutes_until / 1440.0)
    return score, recruiter_match


def select_interview_offer_plan(
    slots: Sequence[OfferableSlot],
    *,
    candidate_tz: str,
    city_id: int,
    recruiter_id: int | None = None,
    purpose: str = "interview",
    max_options: int = 3,
    now: datetime | None = None,
) -> InterviewOfferPlan:
    resolved_now = _ensure_aware_utc(now or datetime.now(UTC))
    filtered: list[tuple[OfferableSlot, float, bool]] = []
    normalized_purpose = (purpose or "interview").strip().lower()

    for slot in slots:
        start_utc = _ensure_aware_utc(slot.start_utc)
        if (slot.status or "").strip().lower() != SlotStatus.FREE:
            continue
        if (slot.purpose or "").strip().lower() != normalized_purpose:
            continue
        if slot.city_id != city_id:
            continue
        if start_utc <= resolved_now:
            continue
        score, recruiter_match = _score_slot(
            slot,
            recruiter_id=recruiter_id,
            now=resolved_now,
        )
        filtered.append((slot, score, recruiter_match))

    if not filtered:
        return InterviewOfferPlan(
            mode=InterviewOfferMode.FALLBACK,
            recommended_slot_id=None,
            fallback_reason="no_offerable_slots",
            payload={
                "policy_version": "v1",
                "mode": InterviewOfferMode.FALLBACK.value,
                "recommended_slot_id": None,
                "options": [],
                "fallback_reason": "no_offerable_slots",
                "candidate_tz": candidate_tz,
                "city_id": city_id,
                "purpose": normalized_purpose,
            },
        )

    filtered.sort(
        key=lambda item: (
            -int(item[2]),
            _ensure_aware_utc(item[0].start_utc),
            int(item[0].slot_id),
        )
    )
    top_items = filtered[: max(1, max_options)]

    def _build_option(
        item: tuple[OfferableSlot, float, bool],
        *,
        recommended: bool,
    ) -> InterviewOfferOption:
        slot, score, recruiter_match = item
        return InterviewOfferOption(
            slot_id=int(slot.slot_id),
            start_utc=_ensure_aware_utc(slot.start_utc),
            duration_min=int(slot.duration_min),
            recruiter_id=int(slot.recruiter_id),
            city_id=int(slot.city_id) if slot.city_id is not None else None,
            score=score,
            reason=_option_reason(recruiter_match=recruiter_match),
            is_recommended=recommended,
        )

    recommended_item = top_items[0]
    second_item = top_items[1] if len(top_items) > 1 else None
    use_single = second_item is None or (
        recommended_item[2] and not second_item[2]
    )

    if use_single:
        option = _build_option(recommended_item, recommended=True)
        options = (option,)
        mode = InterviewOfferMode.SINGLE
    else:
        options = tuple(
            _build_option(item, recommended=index == 0)
            for index, item in enumerate(top_items[:max_options])
        )
        mode = InterviewOfferMode.SHORTLIST

    return InterviewOfferPlan(
        mode=mode,
        recommended_slot_id=options[0].slot_id if options else None,
        options=options,
        fallback_reason=None,
        payload={
            "policy_version": "v1",
            "mode": mode.value,
            "recommended_slot_id": options[0].slot_id if options else None,
            "options": [
                {
                    "slot_id": option.slot_id,
                    "start_utc": option.start_utc.isoformat(),
                    "duration_min": option.duration_min,
                    "recruiter_id": option.recruiter_id,
                    "city_id": option.city_id,
                    "score": option.score,
                    "reason": option.reason,
                    "is_recommended": option.is_recommended,
                }
                for option in options
            ],
            "fallback_reason": None,
            "candidate_tz": candidate_tz,
            "city_id": city_id,
            "purpose": normalized_purpose,
        },
    )


async def build_interview_offer_plan(
    *,
    candidate_id: int,
    application_id: int | None,
    city_id: int,
    candidate_tz: str,
    recruiter_id: int | None = None,
    purpose: str = "interview",
    max_options: int = 3,
    now: datetime | None = None,
) -> InterviewOfferPlan:
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Slot)
                .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                .where(Slot.city_id == city_id)
            )
        ).scalars().all()

    offerable_slots = tuple(
        OfferableSlot(
            slot_id=int(slot.id),
            start_utc=_ensure_aware_utc(slot.start_utc),
            duration_min=int(slot.duration_min),
            recruiter_id=int(slot.recruiter_id),
            city_id=int(slot.city_id) if slot.city_id is not None else None,
            purpose=str(slot.purpose or "interview"),
            status=str(slot.status or SlotStatus.FREE),
        )
        for slot in rows
    )
    plan = select_interview_offer_plan(
        offerable_slots,
        candidate_tz=candidate_tz,
        city_id=city_id,
        recruiter_id=recruiter_id,
        purpose=purpose,
        max_options=max_options,
        now=now,
    )
    payload = dict(plan.payload)
    payload["candidate_id"] = candidate_id
    payload["application_id"] = application_id
    return InterviewOfferPlan(
        mode=plan.mode,
        recommended_slot_id=plan.recommended_slot_id,
        options=plan.options,
        fallback_reason=plan.fallback_reason,
        payload=payload,
        policy_version=plan.policy_version,
    )


__all__ = [
    "InterviewOfferMode",
    "InterviewOfferOption",
    "InterviewOfferPlan",
    "OfferableSlot",
    "build_interview_offer_plan",
    "select_interview_offer_plan",
]
