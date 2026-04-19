# MAX Parity Program Brief

Last Verified: 2026-04-19

## Scope
- Program brief for bringing MAX to candidate-journey parity with Telegram.

## Purpose
- Keep future work focused on shipping parity instead of redesign drift or MAX-specific logic forks.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Runtime Status
- Program objective: `Target`

## Why This Program Exists
- RecruitSmart already has a production/live candidate channel in Telegram.
- MAX is present in the repo as a bounded pilot, but not yet parity-complete.
- Future execution needs a shared, stable operating frame so agents and engineers stop re-opening the runtime from scratch.

## Business Goal
- Bring MAX to full required candidate-journey parity with Telegram.
- Preserve Telegram as the canonical production/live candidate messaging runtime.
- Avoid creating a separate MAX-only product logic branch.

## Canonical Runtime Truth
- Telegram is canonical runtime truth.
- Telegram is the only production/live candidate messaging runtime today; MAX messaging exists only within a bounded pilot.
- MAX already has bounded launch, miniapp, candidate-access, chat, and rollout surfaces in live code, but these do not equal production rollout.

## MAX Parity Goal
- MAX must support the full required candidate journey:
  - bootstrap and identity binding
  - Test 1
  - resume / vacancy / HH link capture
  - booking
  - no-slot fallback
  - incoming/operator handoff
  - recruiter chat
  - reminders / trigger notifications
  - Test 2
  - orientation-day agreement
  - meeting-details delivery
  - re-entry/resume behavior
  - continuous candidate/operator clarity

## Success Criteria
- MAX supports the required candidate journey with shared semantics.
- Telegram remains stable and regression-free.
- Shared candidate lifecycle and next-action semantics remain canonical.
- Recruiter/operator visibility remains coherent across channels.
- Future parity work no longer requires another large repo audit before execution.

## Non-Goals
- Broad design cleanup.
- Backend-heavy rewrite by default.
- Restoring legacy candidate portal runtime.
- Full MAX rollout beyond bounded milestone scope.
- SMS/voice rollout.

## Constraints
- Do not fork business logic for MAX.
- Do not break Telegram runtime behavior.
- Do not treat miniapp as the only acceptable MAX shape.
- Use shared contracts and shared semantics first.
- Mark anything unproven from live code as `Unknown / Not proven`.

## Allowed Redesign
- Redesign is allowed only when it improves parity, candidate clarity, operator clarity, or workflow continuity.
- Shell-level UX differences are allowed when shared meaning and next-step semantics remain aligned.

## Redesign Must Not Distract From
- Phase-1 runtime parity work.
- Shared semantic stabilization.
- Safe handoff between candidate and recruiter.
- Reminder, booking, and status integrity.

## Evidence / Source Inputs
- `AGENTS.md`
- `docs/runtime/telegram-runtime-truth.md`
- `docs/runtime/max-current-state.md`
- `docs/runtime/channel-parity-matrix.md`
- `docs/runtime/shared-semantic-contract.md`
- `docs/architecture/supported_channels.md`
- `docs/frontend/state-flows.md`
- `backend/domain/candidates/state_contract.py`
