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

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high"]
FitLevel = Literal["high", "medium", "low", "unknown"]
Confidence = Literal["high", "medium", "low"]
CriterionStatus = Literal["met", "not_met", "unknown"]


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
