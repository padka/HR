---
name: integration-smoke
description: Use for RecruitSmart bounded rollout validation batches: py_compile, ruff, focused pytest, OpenAPI drift, frontend typecheck/build, Playwright smoke, PostgreSQL proof retry, and no-runtime-leakage checks.
---

# Integration Smoke

Use this skill after each meaningful MAX pilot milestone.

## Required Checks

Run the subset relevant to the touched scope:

- `python -m py_compile <touched_python_files>`
- `ruff check <touched_python_files>`
- focused `pytest`
- broader impacted `pytest` when runtime or shared flows changed
- `python scripts/check_openapi_drift.py`
- `npm --prefix frontend/app run typecheck` when frontend changed
- `npm --prefix frontend/app run build:verify` when frontend changed
- `npm --prefix frontend/app run test:e2e:smoke` for operator-facing UI changes
- `make test-postgres-proof` when the milestone needs PostgreSQL proof
- targeted `rg` checks proving no browser/SMS/full-MAX rollout leakage

## Rules

- Fix failing checks before proceeding, unless the failure is proven pre-existing and out of the touched semantics.
- Record exact commands and outcomes.
- External blockers must stay explicit and narrow.

## Required Output

- commands run
- result per command
- accepted non-blocking debt, if any
- explicit blocker, if any
