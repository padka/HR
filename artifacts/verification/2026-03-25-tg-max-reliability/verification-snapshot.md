# Verification Snapshot

## Purpose
Authoritative verification snapshot for the Telegram/MAX reliability hardening sprint tranche. This file records the exact commands, outcomes, and residual observations after closing delivery, linking/session, and operator-surface changes.

## Owner
Platform Engineering / QA

## Status
Green

## Last Reviewed
2026-03-25

## Source Paths
- `Makefile`
- `frontend/app/package.json`
- `backend/apps/admin_ui/routers/api_misc.py`
- `backend/apps/admin_ui/services/messenger_health.py`
- `backend/apps/admin_ui/services/notifications_ops.py`
- `backend/apps/max_bot/candidate_flow.py`
- `backend/domain/candidates/services.py`
- `backend/domain/candidates/portal_service.py`
- `backend/migrations/versions/0098_tg_max_reliability_foundation.py`

## Related Diagrams
- `docs/architecture/core-workflows.md`
- `docs/architecture/runtime-topology.md`
- `docs/security/auth-and-token-model.md`
- `docs/runbooks/broker-degradation.md`
- `artifacts/verification/2026-03-25-tg-max-reliability/regression-register.md`

## Change Policy
Update only after a new full release-gate rerun. If the command set changes, update canonical QA/security/runtime docs first, then this snapshot.

## Commands And Results
| Command | Result | Evidence |
| --- | --- | --- |
| `make test` | Green | `931 passed, 2 skipped, 114 warnings in 275.12s (0:04:35)` |
| `make test-cov` | Green | `931 passed, 2 skipped, 116 warnings in 325.65s (0:05:25)`; total coverage `59%` |
| `npm --prefix frontend/app run lint` | Green | exit code `0` |
| `npm --prefix frontend/app run typecheck` | Green | exit code `0` |
| `npm --prefix frontend/app run test` | Green | `16 files, 58 tests passed` |
| `npm --prefix frontend/app run build:verify` | Green | production build OK; `Bundle budgets: OK` |
| `npm --prefix frontend/app run test:e2e:smoke` | Green | `11 passed (14.6s)` |
| `npm --prefix frontend/app run test:e2e` | Green | `57 passed (1.0m)` |

## Targeted Regression Evidence
- `pytest -q tests/test_admin_candidate_chat_actions.py::test_generate_max_link tests/test_admin_notifications_feed_api.py::test_notifications_retry_and_cancel_endpoints tests/test_outbox_notifications.py::test_retry_outbox_notification_requeues_dead_letter_and_keeps_channel_degraded tests/test_candidate_lead_and_invite.py::test_max_invite_unique_active_constraint_per_candidate`
  - Result: `4 passed, 1 warning in 3.78s`
- `pytest -q tests/test_rate_limiting.py tests/test_interview_script_feedback.py tests/test_ai_copilot.py::test_ai_candidate_coach_drafts_modes_and_invalid`
  - Result: `10 passed, 1 warning in 6.95s`

## Tranche Evidence
- Candidate channel-health payload now exposes invite metadata without raw invite tokens.
- Audit log entries for MAX invite issuance/rotation no longer store raw invite tokens.
- Explicit retry no longer auto-clears degraded channel state; channel recovery is performed separately through `POST /api/system/messenger-health/{channel}/recover`.
- Single active MAX invite invariant is enforced both in runtime flow and at the DB level via partial unique index + migration backfill.
- Portal header recovery remains bound to `journey_session_id + session_version`; stale sessions fail closed.

## Observations
- An initial parallel attempt to run full Playwright together with smoke caused a local port-18000 bind conflict. The authoritative browser evidence is the subsequent sequential rerun listed above.
- Backend suites still emit existing non-blocking warnings:
  - Pydantic protected namespace warning for `model_custom_emoji_id`
  - Python 3.12+ sqlite datetime adapter deprecation
  - isolated `ResourceWarning` reports on sqlite connections in tests
- Full e2e still logs long-poll `candidate-chat/threads/updates` requests around 25 seconds. This matches the current messenger polling contract and did not cause failures.

## Gate Decision
- Release Gate v2: green for the Telegram/MAX reliability tranche.
- Known red tests: none.
- Open release blockers: none.
