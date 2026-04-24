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


def _smart_service_script_excerpt() -> str:
    return (
        "Smart Service interview script skeleton:\n"
        "1) greeting_and_frame — establish contact, explain call goal, mention that OD is the last practical step before training.\n"
        "2) vacancy_interest_and_candidate_filters — ask whether candidate read the vacancy, what matters in work choice, readiness for active communication, commute, live client interaction.\n"
        "3) company_and_product_pitch — explain that the company improves Yandex Maps profiles for business, mention photo/3D panorama, profile updates, technical optimization, 7+ years of work, and internal teams.\n"
        "4) role_and_work_format — explain territory-based field work, meetings with entrepreneurs, office start of day, 5/2 9:00-18:00, communication-first sales without hard push.\n"
        "5) resilience_to_rejection — ask how candidate reacts to refusals and tempo pressure.\n"
        "6) onboarding_and_support — explain 3-5 day adaptation with mentor and practical training.\n"
        "7) compensation — explain fixed + motivation and high-variable option in plain language, no hidden schemes.\n"
        "8) od_closing_and_confirmation — for recommended candidates offer OD, confirm exact time, route, punctuality, dress code, and ask for a written confirmation message.\n"
        "Tone: spoken Russian, warm but businesslike, concise, no lectures.\n"
    )


def _smart_service_script_exemplar_excerpt() -> str:
    return (
        "Quality exemplar for the final conversation_script:\n"
        "- The recruiter speaks as one continuous live conversation, not as a checklist.\n"
        "- Good opening sounds like: 'Здравствуйте. Рад познакомиться. Коротко объясню, как пройдёт разговор, задам несколько вопросов и, если мы подходим друг другу, предложу следующий этап.'\n"
        "- Good transitions sound natural: 'Тогда коротко расскажу, чем мы занимаемся', 'Теперь про сам формат работы', 'По деньгам объясню коротко и честно', 'Если по базовым критериям всё ок, двигаемся дальше'.\n"
        "- The script may use short paragraphs for readability, but must avoid bullets, numbered lists, dry headings and mechanical checklists.\n"
        "- Regulations and office rules are the source of truth; exemplars are style guides only.\n"
    )


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
        "You are Attila Recruiting Recruiter Copilot.\n"
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
        '  "notes": "string|null",\n'
        '  "scorecard": {"final_score":0-100|null,"objective_score":0-100|null,"semantic_score":0-100|null,"recommendation":"od_recommended|clarify_before_od|not_recommended","metrics":[{"key":"resume_substance|answer_substance|client_communication_inference|interest_for_role","label":"string","score":0-30,"weight":0-30,"status":"met|not_met|unknown","evidence":"string"}],"blockers":[{"key":"string","label":"string","evidence":"string"}],"missing_data":[{"key":"string","label":"string","evidence":"string"}]} | null\n'
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
        "- Use candidate_profile.start_readiness when present.\n"
        "- Use candidate_profile.work_experience / skills / motivation / expectations when present.\n"
        "- Use resume_context when present; it contains normalized resume data.\n"
        "- Use candidate_profile.signals.* as deterministic hints derived from answers.\n"
        "- Field format readiness and real start readiness are critical factors for fit.\n"
        "- Depth and usefulness of free-text answers should improve confidence when the candidate explains experience and reasoning clearly.\n"
        "- Treat age 23-35 only as a soft positive signal. It is never a hard blocker by itself.\n"
        "- Consider customer-facing jobs (e.g. barista/office-manager) as relevant 'experience with people' if supported by test answers.\n"
        "- Communication: you MAY infer likely communication skills from customer-facing roles and signals.people_interaction.\n"
        "  Be explicit that it's an inference and propose 1-2 short validation questions.\n"
        "- If interview_notes.present=true, use interview_notes.fields as additional evidence.\n"
        "- Strengths/weaknesses based on test answers (if present) and scores.\n"
        "- If chat.recent is present, assess recruiter communication quality and suggest concrete improvements.\n"
        "- Criteria checklist: assess objective criteria from regulations (met/not_met/unknown) with short evidence.\n"
        "- Concrete next steps for the recruiter.\n"
        "- scorecard: fill only the semantic source data for downstream hybrid scoring.\n"
        "  Use exactly 4 metrics with keys: resume_substance, answer_substance, client_communication_inference, interest_for_role.\n"
        "  score must be weighted points inside the metric weight, not percent.\n"
        "  blockers: include only strong semantic blockers justified by context.\n"
        "  missing_data: include facts missing for a confident recommendation.\n"
        "Notes:\n"
        "- If referencing test answers, prefer pointing to question_index (e.g. \"TEST2 Q3\") instead of quoting.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def candidate_coach_prompts(*, context: dict, allow_pii: bool = False) -> tuple[str, str]:
    system = (
        "You are Attila Recruiting Recruiter Coach.\n"
        "Task kind: candidate_coach_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Use concise Russian.\n"
        "- Recommendations must be actionable for recruiter in current workflow stage.\n"
        "- Use city_profile.criteria and knowledge_base.excerpts as primary policy source.\n"
        "- Use summary_scorecard as the source of truth for overall recommendation and score.\n"
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
        "- Relevance score/level: MUST align with summary_scorecard.final_score and summary_scorecard.recommendation.\n"
        "- Strengths: include evidence from test answers/signals (e.g., customer-facing experience).\n"
        "- Risks: include no-show / stall / criteria gap risks.\n"
        "- Interview questions: 4-6 short, concrete questions aligned with interview script and current uncertainties.\n"
        "- next_best_action: one explicit next step for recruiter.\n"
        "- message_drafts: 2-3 ready-to-send recruiter messages with reason.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def candidate_facts_prompts(*, context: dict, allow_pii: bool = False) -> tuple[str, str]:
    system = (
        "You are Attila Recruiting Candidate Facts Extractor.\n"
        "Task kind: candidate_facts_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Extract only structured facts already supported by the context.\n"
        "- Do not make screening or hiring decisions.\n"
        "- Mark ambiguity explicitly when the answer is conditional, vague or missing.\n"
        "- prefill_ready_keys should contain only fields with confident value and no ambiguity.\n"
        "JSON schema:\n"
        "{\n"
        '  "summary": "string",\n'
        '  "facts": [{"key":"string","label":"string","value":"string","confidence":"high|medium|low","source":"string","confirmed":true|false,"ambiguity_note":"string|null"}],\n'
        '  "confirmed_keys": ["string"],\n'
        '  "ambiguous_keys": ["string"],\n'
        '  "prefill_ready_keys": ["string"],\n'
        '  "clarification_question": "string|null"\n'
        "}\n"
    )
    user = (
        "Extract recruiter-usable facts from candidate context.\n"
        "Target facts:\n"
        "- city / relocation\n"
        "- desired_income\n"
        "- start_readiness\n"
        "- field_format_readiness\n"
        "- work_status\n"
        "- work_experience\n"
        "- motivation\n"
        "- skills\n"
        "- hh_resume presence or signal when it materially helps\n"
        "Guidelines:\n"
        "- summary should explain what can already be reused in Test 1 and what still needs clarification.\n"
        "- clarification_question should be exactly one short question, only if there is a real ambiguity.\n"
        "- Never invent facts that are not present in test answers, resume context or deterministic candidate_profile.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def recruiter_next_best_action_prompts(*, context: dict, allow_pii: bool = False) -> tuple[str, str]:
    system = (
        "You are Attila Recruiting Recruiter Copilot.\n"
        "Task kind: recruiter_next_best_action_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- This is advisory-only output. Do not change candidate state.\n"
        "- The recommendation must fit the current workflow stage and canonical business rules.\n"
        "- recommended_action must be concrete, short and operational.\n"
        "- playbook must help a recruiter move the candidate one step closer to the next agreed milestone.\n"
        "JSON schema:\n"
        "{\n"
        '  "summary": "string",\n'
        '  "ai_confidence": "high|medium|low",\n'
        '  "recommended_action": {"key":"string","label":"string","rationale":"string","cta":"string|null"} | null,\n'
        '  "reasons": [{"key":"string","label":"string","evidence":"string"}],\n'
        '  "risks": [{"key":"string","severity":"low|medium|high","label":"string","explanation":"string"}],\n'
        '  "interview_focus": ["string"],\n'
        '  "outreach_goal": "string",\n'
        '  "playbook": {"what_to_write":"string","what_to_offer":"string","likely_objection":"string","best_cta":"string"} | null,\n'
        '  "feedback_state": "pending|accepted|dismissed|edited"\n'
        "}\n"
    )
    user = (
        "Produce the next-best-action for a recruiter.\n"
        "Guidelines:\n"
        "- Use candidate status, slots.upcoming, chat timing, summary_scorecard and summary_fit.\n"
        "- If a slot is pending recruiter approval, bias to approve or clarify quickly.\n"
        "- If candidate is waiting for slot, bias to propose concrete time options.\n"
        "- If interview is already scheduled, focus on confirmation / preparation.\n"
        "- If there are blockers or missing_data in summary_scorecard, explain what to clarify before moving ahead.\n"
        "- interview_focus should contain 3-5 short questions/themes for the next recruiter touchpoint.\n"
        "- Keep language concise and recruiter-facing.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def candidate_contact_draft_prompts(*, context: dict, mode: str, allow_pii: bool = False) -> tuple[str, str]:
    style_excerpt = _style_guide_excerpt()
    system = (
        "You are Attila Recruiting Recruiter Copilot.\n"
        "Task kind: candidate_contact_draft_v1.\n"
        "Rules:\n"
        "- Output MUST be a single JSON object (no markdown).\n"
        f"{_pii_rule(allow_pii=allow_pii)}"
        "- Drafts must be channel-aware for current recruiter messaging surfaces (Telegram or MAX).\n"
        "- Drafts must fit the current candidate stage: unfinished Test1, slot selection, slot confirmation, re-engagement after interview.\n"
        "- No promises that violate current business state.\n"
        "- Every draft must include one clear CTA.\n"
    )
    if style_excerpt:
        system += f"\nStyle guide excerpt:\n{style_excerpt}\n"
    system += (
        "JSON schema:\n"
        "{\n"
        '  "analysis": "string|null",\n'
        '  "intent_key": "string",\n'
        '  "recommended_channel": "string",\n'
        '  "drafts": [{"text":"string","reason":"string"}],\n'
        '  "used_context": {"safe_text_used": true|false, "stage":"string"}\n'
        "}\n"
    )
    user = (
        f"Generate 2-3 recruiter contact drafts in mode={mode} (short|neutral|supportive).\n"
        "The drafts should move the candidate one step forward in the funnel without changing system state.\n"
        "Use candidate status, slot state, recent candidate message, summary_scorecard and next_best_action context.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user


def interview_script_prompts(
    *,
    candidate_state: dict[str, Any],
    stage_strategy: dict[str, Any],
    candidate_profile: dict[str, Any],
    hh_resume_normalized: dict[str, Any],
    office_context: dict[str, Any],
    scorecard: dict[str, Any],
    rag_context: list[dict[str, Any]],
    base_risk_hints: list[dict[str, Any]],
) -> tuple[str, str]:
    system = (
        "You are Attila Recruiting Interview Script Generator.\n"
        "Task kind: interview_script_v2.\n"
        "Hard rules:\n"
        "- Output MUST be a single valid JSON object.\n"
        "- Follow the exact schema keys and do not add extra keys.\n"
        "- Do not use markdown.\n"
        "- Do not invent candidate facts.\n"
        "- If data is missing, explicitly mark uncertainty in wording.\n"
        "- conversation_script is the primary recruiter-facing result.\n"
        "- conversation_script MUST be a cohesive spoken script in Russian that a recruiter can read almost verbatim.\n"
        "- conversation_script MUST NOT be a checklist, bullet list, numbered list, heading set, or fragmented memo.\n"
        "- Use only short readable paragraphs separated by blank lines when needed.\n"
        "- Keep recruiter text concise and practical.\n"
        "- Prioritize correct stage logic, logistics clarity, objection handling, and next-step conversion.\n"
        "- Use provided RAG excerpts as internal policy source.\n"
        "- Never include secrets.\n"
        "- PII policy: input is redacted, keep output neutral and safe.\n"
        "Quality rules:\n"
        "- Treat regulations and retrieved policy excerpts as the highest-priority source of truth.\n"
        "- Treat the Smart Service script skeleton and exemplars as style/flow guidance, not text to copy.\n"
        "- Adapt the script to the candidate's current funnel stage and avoid repeating already known facts without reason.\n"
        "- Use risk_flags with actionable question + recommended_phrase.\n"
        "- script_blocks are an internal execution plan and may stay compact, but conversation_script must sound natural.\n"
        "- script_blocks must be executable in real call flow.\n"
        "- Include dynamic branches in if_answers.\n"
        "- cta_templates must move candidate to next concrete step.\n"
        "- Return script_blocks in this exact order and ids: greeting_and_frame, vacancy_interest_and_candidate_filters, company_and_product_pitch, role_and_work_format, resilience_to_rejection, onboarding_and_support, compensation, od_closing_and_confirmation.\n"
        f"{_smart_service_script_excerpt()}"
        f"{_smart_service_script_exemplar_excerpt()}"
        "JSON schema:\n"
        "{\n"
        '  "stage_label": "string",\n'
        '  "call_goal": "string",\n'
        '  "conversation_script": "string",\n'
        '  "risk_flags": [{"code":"string","severity":"low|medium|high","reason":"string","question":"string","recommended_phrase":"string"}],\n'
        '  "highlights": ["string"],\n'
        '  "checks": ["string"],\n'
        '  "objections": [{"topic":"string","candidate_says":"string","recruiter_answer":"string"}],\n'
        '  "script_blocks": [{"id":"string","title":"string","goal":"string","recruiter_text":"string","candidate_questions":["string"],"if_answers":[{"pattern":"string","hint":"string"}]}],\n'
        '  "cta_templates": [{"type":"string","text":"string"}]\n'
        "}\n"
    )
    user = (
        "Generate Interview Script JSON for this candidate.\n\n"
        "candidate_state:\n"
        f"{_json_block(candidate_state)}\n\n"
        "stage_strategy:\n"
        f"{_json_block(stage_strategy)}\n\n"
        "candidate_profile:\n"
        f"{_json_block(candidate_profile)}\n\n"
        "hh_resume_normalized:\n"
        f"{_json_block(hh_resume_normalized)}\n\n"
        "office_context:\n"
        f"{_json_block(office_context)}\n\n"
        "scorecard:\n"
        f"{_json_block(scorecard)}\n\n"
        "rag_context:\n"
        f"{_json_block(rag_context)}\n\n"
        "base_risk_hints:\n"
        f"{_json_block(base_risk_hints)}\n\n"
        "Constraints:\n"
        "1) Keep script aligned to office/city logistics and vacancy rules.\n"
        "2) Mention only facts present in input.\n"
        "3) Cover objections likely for this candidate profile.\n"
        "4) This script is for Smart Service vacancy only; keep the Yandex Maps sales context.\n"
        "5) conversation_script must read like one live recruiter conversation from greeting to close.\n"
        "6) Do not output bullets, numbering, dry section headers, or checklist phrasing inside conversation_script.\n"
        "7) If scorecard.recommendation=od_recommended, close towards OD confirmation.\n"
        "8) If scorecard.recommendation=clarify_before_od, keep OD conditional and naturally weave clarifying questions into the dialogue.\n"
        "9) If scorecard.recommendation=not_recommended, do not offer OD and use soft closure/escalation CTA only.\n"
        "10) If candidate_state/stage_strategy indicate a later funnel stage, do not regenerate a cold first-screening call from scratch.\n"
        "11) Keep output compact but complete.\n"
        "12) Return valid JSON only.\n"
    )
    return system, user


def candidate_coach_drafts_prompts(*, context: dict, mode: str, allow_pii: bool = False) -> tuple[str, str]:
    style_excerpt = _style_guide_excerpt()
    system = (
        "You are Attila Recruiting Recruiter Coach.\n"
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
        "You are Attila Recruiting Recruiter Copilot.\n"
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
        "You are Attila Recruiting Ops & Analytics Copilot.\n"
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
        "You are Attila Recruiting Recruiter Copilot.\n"
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
        "You are Attila Recruiting Recruiter Copilot.\n"
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
        "- 5-8 bullet points of what you can do in Attila Recruiting (screening, regulations, script, next steps, message drafts);\n"
        "- list the titles from knowledge_base.documents.\n"
        "If the question is about conducting an interview, propose exact questions and phrasing aligned with the company script.\n"
        "Context (JSON):\n"
        f"{_json_block(context)}\n"
    )
    return system, user
