"""AI prompt templates for all LLM-powered features.

Each ``*_prompts()`` function returns ``(system_prompt, user_prompt)`` ready
for the AI provider.  Prompts are in Russian to match the target audience.

Functions:
- ``candidate_summary_prompts()`` — candidate assessment prompt.
- ``chat_reply_drafts_prompts()`` — recruiter reply suggestions.
- ``dashboard_insight_prompts()`` — dashboard analytics insight.
- ``city_candidate_recommendations_prompts()`` — candidate ranking for a city.
- ``agent_chat_reply_prompts()`` — Copilot (internal AI chat) prompt.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _json_block(data: Any) -> str:
    """Serialize data to a pretty-printed JSON string for prompt embedding."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def _pii_rule(*, allow_pii: bool) -> str:
    if allow_pii:
        return (
            "- You MAY include personal data from context when it helps (names, phones, usernames).\n"
            "- Do NOT invent personal data that is not present in the context.\n"
            "- Never output secrets (API keys, tokens, passwords).\n"
        )
    return "- Do NOT include any personal data (PII). Never output names, phones, Telegram IDs, links.\n"


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


def candidate_summary_prompts(*, context: dict, allow_pii: bool = False) -> tuple[str, str]:
    system = (
        "You are RecruitSmart Recruiter Copilot.\n"
        "Task kind: candidate_summary_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Use concise Russian.\n"
        "- Keep output compact (cost-effective):\n"
        "  - strengths/weaknesses/risks/next_actions: max 5 items each.\n"
        "  - evidence/explanation/rationale strings: max 180 characters.\n"
        "- If information is missing, say so explicitly.\n"
        "- Use ONLY the provided context. Do not invent facts.\n"
        "JSON schema:\n"
        "{\n"
        '  "tldr": "string",\n'
        '  "fit": {"score": 0-100|null, "level":"high|medium|low|unknown", "rationale":"string", "criteria_used": true|false} | null,\n'
        '  "vacancy_fit": {"score": 0-100|null, "level":"high|medium|low|unknown", "summary":"string", "evidence": [{"factor":"string","assessment":"positive|negative|neutral|unknown","detail":"string"}], "criteria_source":"city_criteria|kb_regulations|both|none"} | null,\n'
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
        "- TL;DR MUST mention: city, current status, test results, and (if present) age + desired income.\n"
        "- vacancy_fit: REQUIRED. Assess how well the candidate fits the vacancy.\n"
        "  - Use city_profile.criteria as the primary evaluation framework.\n"
        "  - Cross-reference with knowledge_base.excerpts (internal regulations/requirements).\n"
        "  - evidence: list 3-6 specific factors (age, income, experience, test scores, motivation, etc.)\n"
        "    with assessment (positive/negative/neutral/unknown) and concrete detail from candidate data.\n"
        "  - criteria_source: indicate whether you used city_criteria, kb_regulations, both, or none.\n"
        "  - If no criteria available, set level=unknown, summary='Критерии города не указаны', score=null.\n"
        "- Fit to the city's vacancy criteria (use city_profile.criteria if present).\n"
        "- If knowledge_base.excerpts are present, treat them as internal regulations and follow them.\n"
        "- Use candidate_profile.age_years and candidate_profile.desired_income when present.\n"
        "- Use candidate_profile.work_experience / skills / motivation / expectations when present.\n"
        "- Use candidate_profile.signals.* as deterministic hints derived from answers.\n"
        "- Consider customer-facing jobs (e.g. barista/office-manager) as relevant 'experience with people' if supported by test answers.\n"
        "- Communication: you MAY infer likely communication skills from customer-facing roles and signals.people_interaction.\n"
        "  Be explicit that it's an inference and propose 1-2 short validation questions.\n"
        "- If interview_notes.present=true, use interview_notes.fields as additional evidence.\n"
        "- Strengths/weaknesses based on test answers (if present) and scores.\n"
        "- If chat.recent is present, assess recruiter communication quality and suggest concrete improvements.\n"
        "- Criteria checklist: assess objective criteria from regulations (met/not_met/unknown) with short evidence.\n"
        "- Concrete next steps for the recruiter.\n"
        "Notes:\n"
        "- If referencing test answers, prefer pointing to question_index (e.g. \"TEST2 Q3\") instead of quoting.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def candidate_coach_prompts(*, context: dict, allow_pii: bool = False) -> tuple[str, str]:
    system = (
        "You are RecruitSmart Recruiter Coach.\n"
        "Task kind: candidate_coach_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Use concise Russian.\n"
        "- Recommendations must be actionable for recruiter in current workflow stage.\n"
        "- Use city_profile.criteria and knowledge_base.excerpts as primary policy source.\n"
        "- Never invent facts not present in context.\n"
        "JSON schema:\n"
        "{\n"
        '  "relevance_score": 0-100|null,\n'
        '  "relevance_level": "high|medium|low|unknown",\n'
        '  "rationale": "string",\n'
        '  "criteria_used": true|false,\n'
        '  "strengths": [{"key":"string","label":"string","evidence":"string"}],\n'
        '  "risks": [{"key":"string","severity":"low|medium|high","label":"string","explanation":"string"}],\n'
        '  "interview_questions": ["string"],\n'
        '  "next_best_action": "string",\n'
        '  "message_drafts": [{"text":"string","reason":"string"}]\n'
        "}\n"
    )
    user = (
        "Produce a recruiter coaching payload for current candidate.\n"
        "Guidelines:\n"
        "- Relevance score/level: evaluate against city criteria + test data + interaction history.\n"
        "- Strengths: include evidence from test answers/signals (e.g., customer-facing experience).\n"
        "- Risks: include no-show / stall / criteria gap risks.\n"
        "- Interview questions: 4-6 short, concrete questions aligned with interview script and current uncertainties.\n"
        "- next_best_action: one explicit next step for recruiter.\n"
        "- message_drafts: 2-3 ready-to-send recruiter messages with reason.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def candidate_coach_drafts_prompts(*, context: dict, mode: str, allow_pii: bool = False) -> tuple[str, str]:
    style_excerpt = _style_guide_excerpt()
    system = (
        "You are RecruitSmart Recruiter Coach.\n"
        "Task kind: candidate_coach_drafts_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Return exactly schema fields below.\n"
        "- Keep drafts practical for Telegram communication.\n"
    )
    if style_excerpt:
        system += f"\nStyle guide excerpt:\n{style_excerpt}\n"
    system += (
        "JSON schema:\n"
        "{\n"
        '  "analysis": "string|null",\n'
        '  "drafts": [{"text":"string","reason":"string"}],\n'
        '  "used_context": {"safe_text_used": true|false}\n'
        "}\n"
    )
    user = (
        f"Generate 2-3 recruiter message drafts in mode={mode} (short|neutral|supportive).\n"
        "Use candidate status, last inbound message and city criteria.\n"
        "Each reason should explain why this draft improves conversion.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def chat_reply_drafts_prompts(*, context: dict, mode: str, allow_pii: bool = False) -> tuple[str, str]:
    style_excerpt = _style_guide_excerpt()
    system = (
        "You are RecruitSmart Recruiter Copilot.\n"
        "Task kind: chat_reply_drafts_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Use polite Russian (вы), short lines, 3-4 blocks max.\n"
        "- Follow Telegram message style: clear, structured, action-oriented.\n"
        "- Use chat.recent (if present) to understand the conversation and candidate objections.\n"
        "- Drafts MUST be recruiter-ready: no placeholders like {Имя} unless candidate.fio is present.\n"
        "- Each draft MUST include a clear call-to-action (ask a question or propose options).\n"
        "- Use the message style guide excerpt below as requirements.\n"
    )
    if style_excerpt:
        system += f"\nStyle guide excerpt:\n{style_excerpt}\n"
    system += (
        "JSON schema:\n"
        "{\n"
        '  "analysis": "string|null",\n'
        '  "drafts": [{"text":"string","reason":"string"}],\n'
        '  "used_context": {"safe_text_used": true|false}\n'
        "}\n"
    )
    user = (
        f"Generate 2-3 reply drafts for the recruiter AND a short analysis.\n"
        f"Mode: {mode} (short|neutral|supportive).\n"
        "Analysis requirements:\n"
        "- Describe what is happening in the chat (recruiter -> candidate, candidate responsiveness).\n"
        "- If candidate is silent, propose a follow-up strategy.\n"
        "- If candidate asks to reschedule, prioritize agreeing on a specific time window.\n"
        "Draft requirements:\n"
        "- Each draft.reason MUST explain the goal and why this message helps.\n"
        "- Prefer referencing concrete next steps (slot, test, intro day) based on candidate status and slots.\n"
        "- If knowledge_base.excerpts are present, follow internal regulations and the interview script style.\n"
        "Context (JSON):\n"
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


def agent_chat_reply_prompts(*, context: dict, allow_pii: bool = False) -> tuple[str, str]:
    system = (
        "You are RecruitSmart Recruiter Copilot.\n"
        "Task kind: agent_chat_reply_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Use Russian.\n"
        "- You are a strict but helpful senior recruiter + sales coach.\n"
        "- knowledge_base.state and knowledge_base.documents describe what is loaded.\n"
        "- If knowledge_base.state.active_documents_total > 0, you MUST NOT say that regulations are missing.\n"
        "- Prefer citing provided knowledge_base.excerpts. If excerpts are empty, say \"не нашел релевантный фрагмент\" and suggest how to уточнить запрос.\n"
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
        "If the question is about what you can help with (capabilities), answer with:\n"
        "- 5-8 bullet points of what you can do in RecruitSmart (screening, regulations, script, next steps, message drafts);\n"
        "- list the titles from knowledge_base.documents.\n"
        "If the question is about conducting an interview, propose exact questions and phrasing aligned with the company script.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user
