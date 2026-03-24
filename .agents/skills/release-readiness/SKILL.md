---
name: release-readiness
description: Final pre-merge review for RecruitSmart code or config changes. Use to check tests, lint, build, observability, rollback, migrations, and minimal-diff quality before declaring work done.
---

# Release Readiness

Use this skill as the final gate before merge or handoff.

Do not use for:

- brainstorming
- partial design
- early architecture exploration

## Checklist

- Relevant tests were run.
- Frontend lint/typecheck/build gates were run when applicable.
- Backend tests were run when backend behavior changed.
- Smoke or Playwright checks were run for routing, shell, portal, or critical user flows.
- Logging and observability are adequate.
- Env/config docs are updated when behavior changed.
- Migrations, if any, are safe and reversible.
- Rollback path is clear.
- Diff is minimal and understandable.
- Remaining risks are explicit.

## Output

Return:

- ready / not ready
- validation commands and results
- open risks
- follow-up work, if any
