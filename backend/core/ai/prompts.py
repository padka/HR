from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _json_block(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


@lru_cache
def _style_guide_excerpt() -> str:
    """Load a short excerpt of the bot style guide to align reply drafts."""
    try:
        backend_dir = Path(__file__).resolve().parents[2]
        path = backend_dir / "apps" / "bot" / "MessageStyleGuide.md"
        text = path.read_text(encoding="utf-8")
        # Keep prompts small/cost-effective; we only need high-level rules.
        return (text or "").strip()[:1400]
    except Exception:
        return ""


def candidate_summary_prompts(*, context: dict) -> tuple[str, str]:
    system = (
        "You are RecruitSmart Recruiter Copilot.\n"
        "Task kind: candidate_summary_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        "- Do NOT include any personal data (PII). Never output names, phones, Telegram IDs, links.\n"
        "- Use concise Russian.\n"
        "- If information is missing, say so explicitly.\n"
        "- Use ONLY the provided context. Do not invent facts.\n"
        "JSON schema:\n"
        "{\n"
        '  "tldr": "string",\n'
        '  "fit": {"score": 0-100|null, "level":"high|medium|low|unknown", "rationale":"string", "criteria_used": true|false} | null,\n'
        '  "strengths": [{"key":"string","label":"string","evidence":"string"}],\n'
        '  "weaknesses": [{"key":"string","label":"string","evidence":"string"}],\n'
        '  "criteria_checklist": [{"key":"string","status":"met|not_met|unknown","label":"string","evidence":"string"}],\n'
        '  "test_insights": "string|null",\n'
        '  "risks": [{"key":"string","severity":"low|medium|high","label":"string","explanation":"string"}],\n'
        '  "next_actions": [{"key":"string","label":"string","rationale":"string","cta":"string|null"}],\n'
        '  "notes": "string|null"\n'
        "}\n"
    )
    user = (
        "Analyze the candidate context and produce recruiter-facing summary.\n"
        "Focus on:\n"
        "- Fit to the city's vacancy criteria (use city_profile.criteria if present).\n"
        "- If knowledge_base.excerpts are present, treat them as internal regulations and follow them.\n"
        "- Use candidate_profile.age_years and candidate_profile.desired_income when present.\n"
        "- If interview_notes.present=true, use interview_notes.fields as additional evidence.\n"
        "- Strengths/weaknesses based on test answers (if present) and scores.\n"
        "- Criteria checklist: assess objective criteria from regulations (met/not_met/unknown) with short evidence.\n"
        "- Concrete next steps for the recruiter.\n"
        "Notes:\n"
        "- If referencing test answers, prefer pointing to question_index (e.g. \"TEST2 Q3\") instead of quoting.\n"
        "Context (anonymized JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def chat_reply_drafts_prompts(*, context: dict, mode: str) -> tuple[str, str]:
    style_excerpt = _style_guide_excerpt()
    system = (
        "You are RecruitSmart Recruiter Copilot.\n"
        "Task kind: chat_reply_drafts_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        "- Do NOT include any personal data (PII). Never output names, phones, Telegram IDs, links.\n"
        "- Use polite Russian (вы), short lines, 3-4 blocks max.\n"
        "- Follow Telegram message style: clear, structured, action-oriented.\n"
        "- Use the message style guide excerpt below as requirements.\n"
    )
    if style_excerpt:
        system += f"\nStyle guide excerpt:\n{style_excerpt}\n"
    system += (
        "JSON schema:\n"
        "{\n"
        '  "drafts": [{"text":"string","reason":"string"}],\n'
        '  "used_context": {"safe_text_used": true|false}\n'
        "}\n"
    )
    user = (
        f"Generate 2-3 reply drafts for the recruiter.\n"
        f"Mode: {mode} (short|neutral|supportive).\n"
        "Context (anonymized JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def dashboard_insight_prompts(*, context: dict) -> tuple[str, str]:
    system = (
        "You are RecruitSmart Ops & Analytics Copilot.\n"
        "Task kind: dashboard_insight_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        "- Do NOT include any personal data (PII). Only aggregated metrics.\n"
        "- Use concise Russian, management-friendly.\n"
        "JSON schema:\n"
        "{\n"
        '  "tldr": "string",\n'
        '  "anomalies": ["string"],\n'
        '  "recommendations": ["string"]\n'
        "}\n"
    )
    user = (
        "Summarize performance and bottlenecks.\n"
        "Aggregated context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def city_candidate_recommendations_prompts(*, context: dict) -> tuple[str, str]:
    system = (
        "You are RecruitSmart Recruiter Copilot.\n"
        "Task kind: city_candidate_recommendations_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        "- Do NOT include any personal data (PII). Never output names, phones, Telegram IDs, links.\n"
        "- Use concise Russian.\n"
        "- Rank candidates by fit to city criteria and readiness to move forward.\n"
        "JSON schema:\n"
        "{\n"
        '  "criteria_used": true|false,\n'
        '  "recommended": [{"candidate_id": 123, "fit_score": 0-100|null, "fit_level":"high|medium|low|unknown", "reason":"string", "suggested_next_step":"string|null"}],\n'
        '  "notes": "string|null"\n'
        "}\n"
    )
    user = (
        "Select the best candidates for recruiter review.\n"
        "Use city.criteria and knowledge_base.excerpts as the evaluation framework.\n"
        "Return up to 10 recommended candidates.\n"
        "Context (anonymized JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def agent_chat_reply_prompts(*, context: dict) -> tuple[str, str]:
    system = (
        "You are RecruitSmart Recruiter Copilot.\n"
        "Task kind: agent_chat_reply_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        "- Do NOT include any personal data (PII). Never output names, phones, Telegram IDs, links.\n"
        "- Use Russian.\n"
        "- Prefer citing provided knowledge_base excerpts. If the KB doesn't cover the question, say so.\n"
        "JSON schema:\n"
        "{\n"
        '  "answer": "string",\n'
        '  "confidence": "high|medium|low",\n'
        '  "kb_sources": [{"document_id": 1, "title":"string", "chunk_index": 0}],\n'
        '  "follow_ups": ["string"]\n'
        "}\n"
    )
    user = (
        "Answer the recruiter question using internal regulations.\n"
        "Context (anonymized JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user
