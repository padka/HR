# MAX Parity Phase 1

Last Verified: 2026-04-19

## Scope
- Milestone 1 execution plan only.

## Purpose
- Give the next implementation run a self-contained, bounded execution plan for the first parity milestone without widening into redesign, reminders, or post-interview flows.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Runtime Status
- Phase-1 plan target: `Target`

## Objective
- Bring MAX to parity for:
  - bootstrap
  - identity binding
  - Test 1
  - booking
  - no-slot fallback
  - operator handoff

## In Scope
- MAX launch/bootstrap truth and edge cases.
- Candidate-access identity/session continuity for bounded MAX surfaces.
- Shared Test 1 parity between Telegram and MAX.
- MAX booking path and no-slot fallback within existing bounded contracts.
- Operator handoff visibility and chat entry continuity for phase-1 stages.

## Out of Scope
- Reminder refactor.
- Test 2 parity.
- Orientation-day parity.
- Broad redesign.
- Deep scheduling refactor.
- Backend contract redesign.

## Assumptions
- Telegram remains the canonical production/live candidate messaging runtime.
- MAX phase-1 work must reuse shared contracts rather than introducing MAX-only business semantics.
- Resume / vacancy / HH link capture remains `Unknown / Not proven` and should not be silently invented inside phase 1.

## Dependencies
- `docs/runtime/telegram-runtime-truth.md`
- `docs/runtime/max-current-state.md`
- `docs/runtime/channel-parity-matrix.md`
- `docs/runtime/shared-semantic-contract.md`
- `docs/runtime/safe-change-map.md`
- `backend/apps/admin_api/max_launch.py`
- `backend/apps/admin_api/candidate_access/services.py`
- `backend/apps/admin_api/max_candidate_chat.py`
- `backend/domain/candidates/test1_shared.py`
- `backend/domain/candidates/state_contract.py`

## Risk Areas
- High:
  - identity/session continuity
  - scheduling write rules
  - channel delivery routing
  - Telegram-coupled downstream behavior
- Medium:
  - operator visibility for phase-1 stages
  - bounded chat-handoff continuity
- Low:
  - docs and execution maps
  - non-behavioral UI clarification

## Execution Steps
1. Confirm runtime truth for bootstrap, identity, Test 1, booking, no-slot fallback, and handoff using the new runtime docs plus live code entrypoints.
2. Freeze phase-1 parity assumptions for each stage and explicitly record any remaining `Unknown / Not proven` items before touching implementation.
3. Trace shared versus Telegram-coupled code paths:
   - shared: `backend/domain/candidates/test1_shared.py`, `backend/domain/candidates/state_contract.py`
   - MAX bounded: `backend/apps/admin_api/max_launch.py`, `backend/apps/admin_api/candidate_access/services.py`, `backend/apps/admin_api/max_candidate_chat.py`
   - Telegram-coupled seams to avoid widening into: `backend/apps/bot/services/notification_flow.py`, `backend/apps/bot/reminders.py`, slot-linked Telegram delivery assumptions
4. Define narrow implementation slices:
   - bootstrap/identity continuity
   - shared Test 1 completion parity
   - booking/no-slot parity under existing candidate-access rules
   - operator handoff visibility and MAX chat continuity for phase-1 stages
5. Validate each slice without widening into out-of-scope stages.
6. Stop immediately if any slice requires reminder rewrite, Test 2 work, orientation-day work, backend contract redesign, or deep scheduling ownership migration.

## Validation Plan
- Docs-pack validation for this batch:
  - Markdown sanity readback
  - `git diff --stat`
  - `git diff -- docs/runtime docs/program docs/exec-plans AGENTS.md`
- Verified repo commands for future implementation runs:
  - `python -m pytest ...`
  - `make openapi-check`
  - `npm --prefix frontend/app run lint`
  - `npm --prefix frontend/app run typecheck`
  - `npm --prefix frontend/app run test`
  - `npm --prefix frontend/app run build:verify`
  - `npm --prefix frontend/app run test:e2e:smoke`
- Commands intentionally not asserted here:
  - any validation command not verified in `Makefile` or `frontend/app/package.json` should be treated as `Not verified in repo`

## Open Questions
- Resume / vacancy / HH link capture contract remains `Unknown / Not proven`.
- Exact MAX shell split for some edge-case handoff/re-entry paths remains `Partial`.
- Operator-facing acceptance criteria for MAX phase-1 states may need one tighter UI/read-model checklist before implementation.

## Stop Conditions
- Proposed work changes Telegram runtime behavior.
- Proposed work changes backend contracts.
- Proposed work requires reminder pipeline rewrite.
- Proposed work requires deep scheduling ownership migration.
- Proposed work spills into Test 2, orientation-day, or broad redesign.

## Definition of Done
- MAX phase-1 stages reach parity-equivalent shared semantics with Telegram.
- Telegram behavior remains unchanged.
- Shared state/next-action semantics remain canonical.
- Operator surfaces can understand candidate progress and next step for phase-1 states.
- Remaining non-phase-1 gaps are explicitly left for later milestones, not half-implemented.

## Evidence / Starting Points
- `docs/runtime/telegram-runtime-truth.md`
- `docs/runtime/max-current-state.md`
- `docs/runtime/channel-parity-matrix.md`
- `backend/apps/admin_api/max_launch.py`
- `backend/apps/admin_api/candidate_access/router.py`
- `backend/apps/admin_api/candidate_access/services.py`
- `backend/apps/admin_api/max_candidate_chat.py`
- `backend/apps/admin_api/max_webhook.py`
- `backend/domain/candidates/test1_shared.py`
- `backend/domain/candidates/state_contract.py`
