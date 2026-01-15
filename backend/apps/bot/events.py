"""Custom event payloads for bot handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InterviewSuccessEvent:
    candidate_id: int
    candidate_name: str
    candidate_tz: str
    city_id: Optional[int]
    city_name: Optional[str]
    slot_id: Optional[int] = None
    required: bool = False
