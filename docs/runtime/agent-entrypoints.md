# Agent Entrypoints

Last Verified: 2026-04-19

## Scope
- Fast orientation map for future agent runs on MAX parity work.

## Purpose
- Let the next agent find runtime truth and high-risk seams without repeating a full repo audit.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Read First
- `AGENTS.md`
- `docs/runtime/telegram-runtime-truth.md`
- `docs/runtime/max-current-state.md`
- `docs/runtime/channel-parity-matrix.md`
- `docs/runtime/shared-semantic-contract.md`
- `docs/runtime/safe-change-map.md`
- `docs/program/max-parity-program-brief.md`
- `docs/exec-plans/max-parity-phase-1.md`

## Runtime Truth
- Telegram runtime truth:
  - `backend/apps/bot/handlers/common.py`
  - `backend/apps/bot/services/test1_flow.py`
  - `backend/apps/bot/services/slot_flow.py`
  - `backend/apps/bot/services/test2_flow.py`
  - `backend/apps/bot/reminders.py`
- MAX runtime truth:
  - `backend/apps/admin_api/main.py`
  - `backend/apps/admin_api/max_launch.py`
  - `backend/apps/admin_api/max_webhook.py`
  - `backend/apps/admin_api/max_candidate_chat.py`
  - `backend/apps/admin_api/candidate_access/router.py`
  - `backend/apps/admin_api/candidate_access/services.py`

## Shared Semantics
- `backend/domain/candidates/state_contract.py`
- `backend/domain/candidates/actions.py`
- `backend/domain/candidates/write_contract.py`
- `backend/domain/candidates/test1_shared.py`

## Scheduling
- `backend/apps/admin_api/candidate_access/services.py`
- `backend/domain/slot_service.py`
- `backend/domain/slot_assignment_service.py`
- `backend/domain/candidates/scheduling_integrity.py`

## Reminders / Messaging
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services/notification_flow.py`
- `backend/core/messenger/registry.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/max_rollout.py`

## Operator Surfaces
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/candidates/helpers.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `frontend/app/src/app/routes/app/*`

## Candidate Surfaces
- MAX candidate surface:
  - `frontend/app/src/app/routes/miniapp/index.tsx`
  - `backend/apps/admin_api/max_miniapp.py`
  - `backend/apps/admin_api/candidate_access/router.py`
- Telegram candidate surface:
  - `backend/apps/bot/*`
- Recruiter Telegram miniapp:
  - `frontend/app/src/app/routes/tg-app/*`
  - `backend/apps/admin_api/webapp/*`

## Stale Docs Watchlist
- `docs/frontend/component-ownership.md`
  - still references `frontend/app/src/app/routes/candidate/*` as a live owned surface
- `docs/architecture/core-workflows.md`
  - runtime scope note still frames MAX as future-only
- any document that treats `/candidate*` as current mounted candidate runtime

## Do Not Confuse
- `/tg-app/*` is recruiter miniapp runtime, not candidate channel runtime.
- `frontend/app/src/app/routes/candidate/*` exists in the tree, but it is not mounted in `frontend/app/src/app/main.tsx`.
- `/miniapp` is the current bounded candidate-facing MAX route.
- Telegram is the only production/live candidate messaging runtime today; MAX messaging exists only within a bounded pilot.

## Do Not Start Here
- Do not start from stale candidate portal files.
- Do not start from archive docs when live code and canonical docs already answer the question.
- Do not start from redesign ideas before phase-1 parity scope is stabilized.

## Unknowns
- Resume / vacancy / HH link capture contract is still `Unknown / Not proven`.
- Full MAX Test 2, orientation-day, and meeting-details parity is still `Unknown / Not proven`.
