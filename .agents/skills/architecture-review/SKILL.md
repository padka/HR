---
name: architecture-review
description: Review RecruitSmart changes before medium/high-risk implementation. Use to map modules, boundaries, side effects, rollback surface, data flow, and migration impact before editing code or config.
---

# Architecture Review

Use this skill before:

- auth or session changes
- scheduling, slot assignment, or status transitions
- webhooks, retries, queueing, or external side effects
- migrations or schema-adjacent changes
- refactors touching shared backend/frontend boundaries
- new integrations or new candidate-facing flows

Do not use for:

- docs-only work
- copy or styling changes
- trivial one-line fixes with no new side effects

## Process

1. Identify the exact files and modules.
2. Map direct callers, dependents, and shared boundaries.
3. List persistence, external calls, and side effects.
4. Identify idempotency requirements and rollback surface.
5. Flag migration, compatibility, or data-shape implications.
6. Recommend the smallest safe implementation path.

## Output

Return:

- architecture map
- risky assumptions
- files to inspect next
- minimal safe plan
- explicit no-go areas
