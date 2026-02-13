from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high"]
FitLevel = Literal["high", "medium", "low", "unknown"]
Confidence = Literal["high", "medium", "low"]
CriterionStatus = Literal["met", "not_met", "unknown"]


class RiskItem(BaseModel):
    # Keep permissive: LLM output can be inconsistent.
    key: str = ""
    severity: Severity = "medium"
    label: str = ""
    explanation: str = ""


class NextActionItem(BaseModel):
    # Keep permissive: LLM output can be inconsistent.
    key: str = ""
    label: str = ""
    rationale: str = ""
    cta: str | None = None


class FitAssessment(BaseModel):
    score: int | None = Field(default=None, ge=0, le=100)
    level: FitLevel = "unknown"
    rationale: str = Field(default="")
    criteria_used: bool = False


class EvidenceItem(BaseModel):
    # Keep these fields permissive: LLM output can be inconsistent.
    # Frontend will gracefully handle empty values.
    key: str = ""
    label: str = ""
    evidence: str = ""


class CriterionChecklistItem(BaseModel):
    # Keep permissive: LLM output can be inconsistent.
    key: str = ""
    status: CriterionStatus = "unknown"
    label: str = ""
    evidence: str = ""


class CandidateSummaryV1(BaseModel):
    tldr: str = Field(min_length=1)
    fit: FitAssessment | None = None
    strengths: list[EvidenceItem] = Field(default_factory=list)
    weaknesses: list[EvidenceItem] = Field(default_factory=list)
    criteria_checklist: list[CriterionChecklistItem] = Field(default_factory=list)
    test_insights: str | None = None
    risks: list[RiskItem] = Field(default_factory=list)
    next_actions: list[NextActionItem] = Field(default_factory=list)
    notes: str | None = None


class DraftItem(BaseModel):
    text: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ChatReplyDraftsV1(BaseModel):
    analysis: str | None = None
    drafts: list[DraftItem] = Field(min_length=1)
    used_context: dict = Field(default_factory=dict)


class DashboardInsightV1(BaseModel):
    tldr: str = Field(min_length=1)
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class CandidateRecommendationItem(BaseModel):
    candidate_id: int = Field(ge=1)
    fit_score: int | None = Field(default=None, ge=0, le=100)
    fit_level: FitLevel = "unknown"
    reason: str = ""
    suggested_next_step: str | None = None


class CityCandidateRecommendationsV1(BaseModel):
    criteria_used: bool = False
    recommended: list[CandidateRecommendationItem] = Field(default_factory=list)
    notes: str | None = None


class KBSourceItem(BaseModel):
    document_id: int = Field(ge=1)
    title: str = ""
    chunk_index: int = Field(ge=0)


class AgentChatReplyV1(BaseModel):
    answer: str = Field(min_length=1)
    confidence: Confidence = "medium"
    kb_sources: list[KBSourceItem] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
