"""Status mapping between RecruiterSmart and hh.ru negotiation statuses."""

from __future__ import annotations

from typing import Dict, Optional

from backend.domain.candidates.status import CandidateStatus

# hh.ru negotiation statuses:
#   "response"   — new response (initial, no action needed)
#   "invitation"  — invited for interview
#   "discard"     — rejected
#   "hired"       — candidate was hired

HH_STATUS_MAPPING: Dict[CandidateStatus, str] = {
    CandidateStatus.INTERVIEW_SCHEDULED: "invitation",
    CandidateStatus.INTERVIEW_CONFIRMED: "invitation",
    CandidateStatus.INTERVIEW_DECLINED: "discard",
    CandidateStatus.TEST2_FAILED: "discard",
    CandidateStatus.INTRO_DAY_DECLINED_INVITATION: "discard",
    CandidateStatus.INTRO_DAY_DECLINED_DAY_OF: "discard",
    CandidateStatus.NOT_HIRED: "discard",
    CandidateStatus.HIRED: "hired",
}


def get_hh_target_status(rs_status: CandidateStatus) -> Optional[str]:
    """Return the hh.ru negotiation status for a given RS status, or None if no sync needed."""
    return HH_STATUS_MAPPING.get(rs_status)


def should_sync_status(rs_status: CandidateStatus) -> bool:
    """Check whether a given RS status triggers hh.ru sync."""
    return rs_status in HH_STATUS_MAPPING


__all__ = [
    "HH_STATUS_MAPPING",
    "get_hh_target_status",
    "should_sync_status",
]
