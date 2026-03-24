---
name: recruiter-crm-domain-check
description: Validate RecruitSmart candidate lifecycle, recruiter workflow, slot scheduling, messaging, analytics, and admin usability changes against recruiting-domain invariants before editing business logic.
---

# Recruiter CRM Domain Check

Use this skill for:

- candidate lifecycle changes
- recruiter workflow changes
- slot or schedule logic
- messaging or automation affecting candidates
- analytics or KPI logic tied to operations
- admin UI changes that affect next actions or operational clarity

Do not use for:

- generic infrastructure work
- docs-only changes
- visual polish that does not alter workflow

## Checklist

- Candidate status transitions are explicit and traceable.
- Scheduling and slot assignment are deterministic.
- Next actions are clear to recruiters.
- Side effects are idempotent where practical.
- Retries will not duplicate external actions.
- Analytics remain reproducible.
- Silent fallbacks do not hide critical failures.
- Candidate, recruiter, slot, office, and city data integrity is preserved.
- Operational events or logs make the workflow auditable.
- AI-assisted behavior is constrained by business rules.

## Output

Return:

- domain integrity assessment
- ambiguous or unsafe states
- workflow consequences
- required regression coverage
- explicit next-step recommendation
