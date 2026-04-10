# Verification Snapshot

## Purpose
Точный verification snapshot для isolated QA audit на 2026-04-06. Файл фиксирует команды, результаты и важные наблюдения без ретроактивной интерпретации.

## Owner
QA / Release Readiness

## Status
Red

## Last Reviewed
2026-04-06

## Source Paths
- `Makefile`
- `frontend/app/package.json`
- `tests/conftest.py`
- `frontend/app/playwright.config.ts`
- `tests/integration/test_notification_broker_redis.py`

## Commands And Results
| Command | Result | Evidence |
| --- | --- | --- |
| `make test` | Red | `1 failed, 110 passed, 2 skipped, 9 warnings in 41.27s` |
| `npm --prefix frontend/app run lint` | Green | exit code `0` |
| `npm --prefix frontend/app run typecheck` | Green | exit code `0` |
| `npm --prefix frontend/app run test` | Green | `17 files, 83 tests passed, duration 3.76s` |
| `npm --prefix frontend/app run build:verify` | Green | build OK, `Bundle budgets: OK`, total JS `1.60 MB`, total CSS `320.0 KB` |
| `npm --prefix frontend/app run test:e2e:smoke` | Green | `11 passed (14.3s)` |
| `cd frontend/app && npx playwright test tests/e2e/critical-flows.spec.ts` | Green | `7 passed (12.1s)` |
| `cd frontend/app && npx playwright test tests/e2e/health.spec.ts` | Green | `1 passed (3.4s)` |
| `.venv/bin/python -m pytest -q tests/test_candidate_portal_api.py` | Green | `17 passed, 11 warnings in 22.45s` |
| `.venv/bin/python -m pytest -q tests/test_max_candidate_flow.py tests/test_max_owner_preflight.py` | Green | `12 passed, 28 warnings in 6.36s` |
| `.venv/bin/python -m pytest -q tests/test_admin_surface_hardening.py tests/test_security_auth_hardening.py tests/test_admin_csrf_policy.py` | Green | `22 passed, 1 warning in 11.01s` |
| `.venv/bin/python -m pytest -q tests/test_candidate_lifecycle_use_cases.py tests/test_candidate_write_contract.py tests/test_workflow_hired.py` | Green | `24 passed, 6 warnings in 10.60s` |
| `.venv/bin/python -m pytest -q tests/test_admin_candidate_schedule_slot.py -k 'blocking_state or repair or conflict or manual_repair or scheduling_conflict or reschedule or kanban_move or assignment_authoritative'` | Green | `16 passed, 17 deselected, 1 warning in 10.58s` |
| `.venv/bin/python -m pytest -q tests/test_admin_candidates_service.py -k 'canonical or scheduling or reconciliation or repair_workflow or blocking_state or state_reconciliation'` | Green | `5 passed, 22 deselected, 1 warning in 4.22s` |
| `.venv/bin/python -m pytest -q tests/test_notification_retry.py tests/test_outbox_deduplication.py tests/test_notification_log_idempotency.py tests/test_broker_production_restrictions.py tests/test_prod_requires_redis.py` | Green | `25 passed, 1 warning in 8.56s` |
| `.venv/bin/python -m pytest -q tests/integration/test_notification_broker_redis.py` | Green | `4 passed, 1 warning in 3.12s` |
| `.venv/bin/python -m pytest -q tests/test_admin_candidate_chat_actions.py -k 'blocking_state or scheduling_conflict or action_not_allowed or repair_inconsistency or portal/restart or max-link or stale or session_version'` | Green | `3 passed, 24 deselected, 1 warning in 3.90s` |
| `.venv/bin/python -m pytest -q tests/test_webapp_booking_api.py tests/test_manual_slot_booking_api.py tests/test_candidate_lead_and_invite.py tests/test_webapp_auth.py` | Green | `30 passed, 6 warnings in 8.65s` |

## Key Red Signal
- `make test` stops on [tests/test_admin_candidate_schedule_slot.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_admin_candidate_schedule_slot.py) with:
  - test: `test_api_slot_propose_assigns_candidate_and_sets_slot_pending`
  - expected: `201`
  - actual: `403`

## Coverage Facts Collected
- backend test files: `171`
- frontend unit/component test files: `17`
- Playwright specs: `13`
- integration test files under `tests/integration`: `2`
- files with mocks/monkeypatch patterns: `98`
- files explicitly referencing key canonical contract fields: `12`

## Important Observations
- `tests/conftest.py` forces the main pytest harness to SQLite and also rewrites `TEST_DATABASE_URL` to the same SQLite URL.
- `frontend/app/playwright.config.ts` runs browser verification against temporary SQLite DB.
- `tests/integration/test_migrations_postgres.py` is therefore not a strong clean-Postgres proof in the current harness.
- Disposable PostgreSQL database creation could not be performed because the available local role does not have `CREATE DATABASE`.
- A direct asynchronous probe to `postgresql+asyncpg://rs:pass@localhost:5432/rs_test` succeeded with `select 1`, but that only proves reachability, not migration/runtime readiness.
- Playwright runtime repeatedly showed expected long-poll traffic for messenger endpoints such as `/api/candidate-chat/threads/updates?timeout=25...`.
- E2E startup on SQLite logs `Automatic schema upgrade skipped: near "ALTER": syntax error`; this is bootstrap noise, not production proof.

## Snapshot Decision
- Backend repo-wide baseline: red
- Frontend repo-wide baseline: green
- Targeted critical-domain suites: mostly green
- Overall isolated QA snapshot: **red / not release-clean**
