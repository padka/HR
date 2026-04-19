---
name: ux-copy-review
description: Use for RecruitSmart operator-facing copy reviews. Covers invite preview text, action labels, empty/error/success states, and removing technical/provider internals from recruiter UI.
---

# UX Copy Review

Use this skill for:

- operator-facing button labels
- preview/result modal copy
- empty/disabled/error/success states
- bounded copy cleanup in recruiter/admin UI

Do not use for:

- marketing copy
- large product redesign
- changing business rules hidden behind copy

## Checklist

- Use one language/grammar consistently for the target UI.
- Prefer short operator wording over technical wording.
- Do not expose raw enums, provider IDs, secrets, or internal URLs.
- Explain state in operator terms: invite issued, delivery failed, launch observed, candidate not bound.
- Keep copy neutral and actionable.
- No PII leakage in preview or result text.

## Required Output

- copy issues found
- bounded changes applied
- any remaining ambiguous wording
