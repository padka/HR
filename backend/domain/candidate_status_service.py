"""Domain service for candidate status transitions.

This service is the single point of truth for changing a candidate's status.
It does not depend on transport layers (HTTP/Telegram/UI).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union

from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus, can_transition


class CandidateStatusTransitionError(Exception):
    """Raised when a status transition is invalid."""


StatusLike = Union[CandidateStatus, str, None]


class CandidateStatusService:
    """Validate and apply candidate status transitions."""

    def __init__(self):
        self._now = lambda: datetime.now(timezone.utc)

    def _normalize(self, status: StatusLike) -> Optional[CandidateStatus]:
        if status is None:
            return None
        if isinstance(status, CandidateStatus):
            return status
        return CandidateStatus(status)

    async def _apply(
        self,
        candidate: User,
        new_status: StatusLike,
        *,
        force: bool = False,
    ) -> bool:
        target = self._normalize(new_status)
        current = candidate.candidate_status

        if target == current:
            return False

        if not force:
            if target is None:
                raise CandidateStatusTransitionError("Cannot clear status via advance/rollback")
            if not can_transition(current, target):
                raise CandidateStatusTransitionError(
                    f"Invalid status transition {current!r} -> {target!r}"
                )

        candidate.candidate_status = target
        candidate.status_changed_at = self._now()
        return True

    async def advance(self, candidate: User, new_status: StatusLike, *, reason: Optional[str] = None) -> bool:
        """Advance to a permitted next status."""
        return await self._apply(candidate, new_status, force=False)

    async def rollback(self, candidate: User, new_status: StatusLike, *, reason: Optional[str] = None) -> bool:
        """Rollback using the same transition validation rules."""
        return await self._apply(candidate, new_status, force=False)

    async def force(self, candidate: User, new_status: StatusLike, *, reason: str) -> bool:
        """Force status change regardless of the transition graph."""
        if not reason:
            raise CandidateStatusTransitionError("Force transition requires reason")
        return await self._apply(candidate, new_status, force=True)


__all__ = ["CandidateStatusService", "CandidateStatusTransitionError"]
