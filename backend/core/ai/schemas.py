from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high"]


class RiskItem(BaseModel):
    key: str = Field(min_length=1)
    severity: Severity = "medium"
    label: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class NextActionItem(BaseModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    cta: Optional[str] = None


class CandidateSummaryV1(BaseModel):
    tldr: str = Field(min_length=1)
    risks: list[RiskItem] = Field(default_factory=list)
    next_actions: list[NextActionItem] = Field(default_factory=list)
    notes: Optional[str] = None


class DraftItem(BaseModel):
    text: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ChatReplyDraftsV1(BaseModel):
    drafts: list[DraftItem] = Field(min_length=1)
    used_context: dict = Field(default_factory=dict)


class DashboardInsightV1(BaseModel):
    tldr: str = Field(min_length=1)
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

