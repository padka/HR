"""Shared candidate-access API boundary for external candidate surfaces."""

from .auth import CandidateAccessPrincipal, get_max_candidate_access_principal
from .router import router

__all__ = [
    "CandidateAccessPrincipal",
    "get_max_candidate_access_principal",
    "router",
]
