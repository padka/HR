from types import SimpleNamespace

from backend.apps.bot.handlers.common import (
    _candidate_status_text as handler_candidate_status_text,
)
from backend.apps.bot.services.onboarding_flow import (
    _candidate_status_text as onboarding_candidate_status_text,
)
from backend.domain.candidates.status import CandidateStatus


def test_onboarding_candidate_status_text_prefers_candidate_status_label():
    candidate = SimpleNamespace(
        candidate_status=CandidateStatus.INTERVIEW_SCHEDULED,
        workflow_status="legacy_status",
    )

    assert onboarding_candidate_status_text(candidate, fallback="В работе") == "Назначено собеседование"


def test_handler_candidate_status_text_falls_back_to_workflow_status():
    candidate = SimpleNamespace(candidate_status=None, workflow_status="waiting_review")

    assert handler_candidate_status_text(candidate, fallback="В обработке") == "waiting_review"


def test_candidate_status_text_uses_fallback_when_status_fields_missing():
    candidate = SimpleNamespace(candidate_status=None, workflow_status=None)

    assert onboarding_candidate_status_text(candidate, fallback="В работе") == "В работе"
    assert handler_candidate_status_text(candidate, fallback="В обработке") == "В обработке"
