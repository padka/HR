
from typing import Dict, List

# Defined contexts for different template categories
# These lists are used for validation and UI hints.

COMMON_VARIABLES = ["candidate_name", "candidate_fio", "city_name"]

TEMPLATE_CONTEXTS: Dict[str, List[str]] = {
    "interview": COMMON_VARIABLES + [
        "dt_local", 
        "join_link", 
        "recruiter_name", 
        "recruiter_contact",
        "interview_dt_hint"
    ],
    "rejection": COMMON_VARIABLES + ["rejection_reason"],
    "intro_day": COMMON_VARIABLES + [
        "slot_datetime_local", 
        "intro_address", 
        "intro_contact", 
        "city_address", 
        "dt_local"
    ],
    "reminder": COMMON_VARIABLES + [
        "dt_local", 
        "join_link", 
        "slot_datetime_local"
    ],
    "other": COMMON_VARIABLES + [
        "dt_local",
        "slot_datetime_local"
    ]
}

def get_context_variables(template_key: str) -> List[str]:
    """Return list of variables allowed/expected for a given template key."""
    key = template_key.lower()
    if "intro" in key:
        return TEMPLATE_CONTEXTS["intro_day"]
    if "interview" in key or "reschedule" in key or "invite" in key:
        return TEMPLATE_CONTEXTS["interview"]
    if "remind" in key or "confirm" in key:
        return TEMPLATE_CONTEXTS["reminder"]
    if "reject" in key or "fail" in key:
        return TEMPLATE_CONTEXTS["rejection"]
    return TEMPLATE_CONTEXTS["other"]
