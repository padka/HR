"""Pydantic schemas for AI provider JSON responses.

All schemas are intentionally permissive (defaults on every field) because
LLM output is non-deterministic.  The frontend gracefully handles empty values.

Schemas
-------
- ``CandidateSummaryV1`` – full candidate assessment returned by ``/api/ai/candidates/<id>/summary``
- ``ChatReplyDraftsV1`` – suggested reply drafts for recruiter chat
- ``DashboardInsightV1`` – aggregated dashboard insight text
- ``CityCandidateRecommendationsV1`` – ranked candidate list for a city
- ``AgentChatReplyV1`` – Copilot (internal AI chat) reply
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high"]
FitLevel = Literal["high", "medium", "low", "unknown"]
Confidence = Literal["high", "medium", "low"]
CriterionStatus = Literal["met", "not_met", "unknown"]
ScorecardRecommendation = Literal["od_recommended", "clarify_before_od", "not_recommended"]
FeedbackState = Literal["pending", "accepted", "dismissed", "edited"]


class RiskItem(BaseModel):
    """A single risk factor identified for a candidate."""

    key: str = ""
    severity: Severity = "medium"
    label: str = ""
    explanation: str = ""


class NextActionItem(BaseModel):
    """A recommended next action for the recruiter."""

    key: str = ""
    label: str = ""
    rationale: str = ""
    cta: str | None = None


class FitAssessment(BaseModel):
    """Overall candidate fit assessment (0-100 score + qualitative level)."""

    score: int | None = Field(default=None, ge=0, le=100)
    level: FitLevel = "unknown"
    rationale: str = Field(default="")
    criteria_used: bool = False


class EvidenceItem(BaseModel):
    """A strength or weakness evidence item with supporting text."""

    key: str = ""
    label: str = ""
    evidence: str = ""


class CriterionChecklistItem(BaseModel):
    """One criterion from the city/KB checklist with met/not_met status."""

    key: str = ""
    status: CriterionStatus = "unknown"
    label: str = ""
    evidence: str = ""


class ScorecardMetricItem(BaseModel):
    key: str = ""
    label: str = ""
    score: int | None = Field(default=None, ge=0, le=100)
    weight: int | None = Field(default=None, ge=0, le=100)
    status: CriterionStatus = "unknown"
    evidence: str = ""


class ScorecardFlagItem(BaseModel):
    key: str = ""
    label: str = ""
    evidence: str = ""


class CandidateScorecard(BaseModel):
    final_score: int | None = Field(default=None, ge=0, le=100)
    objective_score: int | None = Field(default=None, ge=0, le=100)
    semantic_score: int | None = Field(default=None, ge=0, le=100)
    recommendation: ScorecardRecommendation = "clarify_before_od"
    metrics: list[ScorecardMetricItem] = Field(default_factory=list)
    blockers: list[ScorecardFlagItem] = Field(default_factory=list)
    missing_data: list[ScorecardFlagItem] = Field(default_factory=list)


VacancyFitAssessment = Literal["positive", "negative", "neutral", "unknown"]
CriteriaSource = Literal["city_criteria", "kb_regulations", "both", "none"]


class VacancyFitEvidence(BaseModel):
    """Single factor in the vacancy fit assessment."""

    factor: str = ""
    assessment: VacancyFitAssessment = "unknown"
    detail: str = ""


class VacancyFit(BaseModel):
    """Vacancy-specific fit assessment using city criteria and/or KB regulations."""

    score: int | None = Field(default=None, ge=0, le=100)
    level: FitLevel = "unknown"
    summary: str = ""
    evidence: list[VacancyFitEvidence] = Field(default_factory=list)
    criteria_source: CriteriaSource = "none"


class CandidateSummaryV1(BaseModel):
    """Full AI-generated candidate summary.

    Returned by ``GET /api/ai/candidates/{id}/summary`` and
    ``POST /api/ai/candidates/{id}/summary/refresh``.
    """

    tldr: str = Field(min_length=1)
    fit: FitAssessment | None = None
    vacancy_fit: VacancyFit | None = None
    strengths: list[EvidenceItem] = Field(default_factory=list)
    weaknesses: list[EvidenceItem] = Field(default_factory=list)
    criteria_checklist: list[CriterionChecklistItem] = Field(default_factory=list)
    test_insights: str | None = None
    risks: list[RiskItem] = Field(default_factory=list)
    next_actions: list[NextActionItem] = Field(default_factory=list)
    notes: str | None = None
    scorecard: CandidateScorecard | None = None


class DraftItem(BaseModel):
    """A single draft reply for the recruiter."""

    text: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ChatReplyDraftsV1(BaseModel):
    """Suggested reply drafts for the recruiter's chat with a candidate.

    Returned by ``POST /api/ai/candidates/{id}/chat/drafts``.
    """

    analysis: str | None = None
    drafts: list[DraftItem] = Field(min_length=1)
    used_context: dict = Field(default_factory=dict)


class DashboardInsightV1(BaseModel):
    """Dashboard AI insight with anomalies and recommendations.

    Returned by ``POST /api/ai/dashboard/insights``.
    """

    tldr: str = Field(min_length=1)
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class CandidateRecommendationItem(BaseModel):
    """One recommended candidate within a city ranking."""

    candidate_id: int = Field(ge=1)
    fit_score: int | None = Field(default=None, ge=0, le=100)
    fit_level: FitLevel = "unknown"
    reason: str = ""
    suggested_next_step: str | None = None


class CityCandidateRecommendationsV1(BaseModel):
    """AI-ranked candidate recommendations for a city.

    Returned by ``GET/POST /api/ai/cities/{id}/candidates/recommendations``.
    """

    criteria_used: bool = False
    recommended: list[CandidateRecommendationItem] = Field(default_factory=list)
    notes: str | None = None


class KBSourceItem(BaseModel):
    """A Knowledge Base source reference used in an AI answer."""

    document_id: int = Field(ge=1)
    title: str = ""
    chunk_index: int = Field(ge=0)


class AgentChatReplyV1(BaseModel):
    """Copilot (internal AI agent) chat reply.

    Returned by ``POST /api/ai/chat/message``.
    """

    answer: str = Field(min_length=1)
    confidence: Confidence = "medium"
    kb_sources: list[KBSourceItem] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class CandidateCoachV1(BaseModel):
    relevance_score: int | None = Field(default=None, ge=0, le=100)
    relevance_level: FitLevel = "unknown"
    rationale: str = ""
    criteria_used: bool = False
    strengths: list[EvidenceItem] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    next_best_action: str = ""
    message_drafts: list[DraftItem] = Field(default_factory=list)


class CandidateFactItem(BaseModel):
    key: str = ""
    label: str = ""
    value: str = ""
    confidence: Confidence = "medium"
    source: str = ""
    confirmed: bool = True
    ambiguity_note: str | None = None


class CandidateFactsV1(BaseModel):
    summary: str = ""
    facts: list[CandidateFactItem] = Field(default_factory=list)
    confirmed_keys: list[str] = Field(default_factory=list)
    ambiguous_keys: list[str] = Field(default_factory=list)
    prefill_ready_keys: list[str] = Field(default_factory=list)
    clarification_question: str | None = None


class RecruiterPlaybookV1(BaseModel):
    what_to_write: str = ""
    what_to_offer: str = ""
    likely_objection: str = ""
    best_cta: str = ""


class RecruiterNextBestActionV1(BaseModel):
    summary: str = ""
    ai_confidence: Confidence = "medium"
    recommended_action: NextActionItem | None = None
    reasons: list[EvidenceItem] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    outreach_goal: str = ""
    playbook: RecruiterPlaybookV1 | None = None
    feedback_state: FeedbackState = "pending"


class CandidateContactDraftsV1(BaseModel):
    analysis: str | None = None
    intent_key: str = ""
    recommended_channel: str = ""
    drafts: list[DraftItem] = Field(min_length=1)
    used_context: dict = Field(default_factory=dict)


class InterviewScriptIfAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(min_length=1, max_length=200)
    hint: str = Field(min_length=1, max_length=400)


class InterviewScriptBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=300)
    recruiter_text: str = Field(min_length=1, max_length=1200)
    candidate_questions: list[str] = Field(default_factory=list, max_length=12)
    if_answers: list[InterviewScriptIfAnswer] = Field(default_factory=list, max_length=12)


class InterviewScriptRiskFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    severity: Severity = "medium"
    reason: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=300)
    recommended_phrase: str = Field(min_length=1, max_length=500)


class InterviewScriptObjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=120)
    candidate_says: str = Field(min_length=1, max_length=300)
    recruiter_answer: str = Field(min_length=1, max_length=500)


class InterviewScriptCTA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)


class InterviewScriptBriefing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(default="", max_length=240)
    focus_areas: list[str] = Field(default_factory=list, max_length=6)
    key_flags: list[str] = Field(default_factory=list, max_length=6)


class InterviewScriptOpening(BaseModel):
    model_config = ConfigDict(extra="forbid")

    greeting: str = Field(default="", max_length=800)
    icebreakers: list[str] = Field(default_factory=list, max_length=6)


InterviewScriptQuestionType = Literal["personalized", "standard"]


class InterviewScriptQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)
    type: InterviewScriptQuestionType = "standard"
    source: str | None = Field(default=None, max_length=80)
    why: str = Field(min_length=1, max_length=500)
    good_answer: str = Field(min_length=1, max_length=500)
    red_flags: str = Field(min_length=1, max_length=500)
    estimated_minutes: int = Field(default=3, ge=1, le=15)


InterviewScriptOverallRecommendation = Literal["recommend", "doubt", "not_recommend"]


class InterviewScriptScorecardItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=64)
    rating: int | None = Field(default=None, ge=1, le=5)
    skipped: bool = False
    notes: str | None = Field(default=None, max_length=4000)


class InterviewScriptScorecardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_questions: int = Field(default=0, ge=0, le=30)
    total_questions: int = Field(default=0, ge=0, le=30)
    average_rating: float | None = Field(default=None, ge=1, le=5)
    overall_recommendation: InterviewScriptOverallRecommendation = "doubt"
    final_comment: str | None = Field(default=None, max_length=5000)
    timer_elapsed_sec: int = Field(default=0, ge=0, le=86400)
    items: list[InterviewScriptScorecardItem] = Field(default_factory=list, max_length=24)


class InterviewScriptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_label: str = Field(default="", max_length=120)
    call_goal: str = Field(default="", max_length=240)
    conversation_script: str = Field(min_length=1, max_length=12000)
    risk_flags: list[InterviewScriptRiskFlag] = Field(default_factory=list, max_length=20)
    highlights: list[str] = Field(default_factory=list, max_length=12)
    checks: list[str] = Field(default_factory=list, max_length=20)
    objections: list[InterviewScriptObjection] = Field(default_factory=list, max_length=12)
    script_blocks: list[InterviewScriptBlock] = Field(min_length=3, max_length=12)
    cta_templates: list[InterviewScriptCTA] = Field(default_factory=list, max_length=10)
    briefing: InterviewScriptBriefing | None = None
    opening: InterviewScriptOpening | None = None
    questions: list[InterviewScriptQuestion] = Field(default_factory=list, max_length=12)
    closing_checklist: list[str] = Field(default_factory=list, max_length=12)
    closing_phrase: str = Field(default="", max_length=800)


InterviewScriptOutcome = Literal["od_assigned", "showed_up", "no_show", "decline", "unknown"]


class InterviewScriptFeedbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    helped: bool | None = None
    edited: bool = False
    quick_reasons: list[str] = Field(default_factory=list, max_length=12)
    final_script: InterviewScriptPayload | None = None
    outcome: InterviewScriptOutcome = "unknown"
    outcome_reason: str | None = Field(default=None, max_length=500)
    scorecard: InterviewScriptScorecardPayload | None = None
    idempotency_key: str = Field(min_length=8, max_length=64)
