# Safe Change Map

Last Verified: 2026-04-19

## Scope
- Risk map for future MAX parity work.

## Purpose
- Prevent Telegram regressions and accidental scope expansion before parity implementation starts.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Low Risk
- Why:
  - Documentation, execution maps, and status labeling do not change runtime behavior.
  - Local MAX pilot UI clarity updates can stay presentation-only if contracts and API behavior stay unchanged.
- Safe to change:
  - `docs/runtime/*`
  - `docs/program/*`
  - `docs/exec-plans/*`
  - non-behavioral copy in bounded MAX surfaces
  - UI-only labels/help text that do not alter candidate state, actions, or routing
- Do not touch without more preparation:
  - any API contract
  - any scheduler/outbox code
  - any Telegram handler behavior
- Telegram regression watchout:
  - low risk becomes medium/high risk immediately if copy changes are coupled to branch logic or callback payload changes.

## Medium Risk
- Why:
  - These areas are within bounded MAX scope or shared operator presentation, but they depend on shared semantics and existing contracts.
- Safe to change with narrow scope:
  - MAX candidate-access UX/state handling inside existing bounded scope
  - operator visibility improvements that reuse current state-contract outputs
  - chat-handoff semantics where contracts and statuses do not change
- Do not touch without more preparation:
  - scheduling ownership rules
  - shared lifecycle/status definitions
  - reminder triggering rules
- Telegram regression watchout:
  - operator visibility work can drift into lifecycle reinterpretation and change recruiter actions or queue ordering.

## High Risk
- Why:
  - These areas own side effects, shared statuses, scheduling integrity, retries, and channel delivery.
- Dangerous areas:
  - `backend/apps/bot/handlers/*`
  - `backend/apps/bot/services/notification_flow.py`
  - `backend/apps/bot/reminders.py`
  - shared status transitions and write intents
  - scheduling write paths and assignment ownership checks
  - channel identity/bootstrap
  - any path still using `candidate_tg_id` as critical glue
- Do not touch without separate preparation:
  - Telegram runtime behavior
  - backend contracts
  - reminder pipeline semantics
  - deep scheduling ownership migration
- Telegram regression watchout:
  - booking, reminder, and outbox paths still rely on Telegram-linked identifiers and slot-linked delivery assumptions
  - changing adapter resolution or delivery preference logic can silently shift live candidate delivery away from Telegram

## Telegram Regression Watchouts
- `backend/apps/bot/services/notification_flow.py` is heavily Telegram-coupled.
- `backend/apps/bot/reminders.py` rebuilds reminder jobs from Telegram-linked slot state.
- `backend/apps/bot/handlers/common.py`, `test1_flow.py`, and `slot_flow.py` jointly define live Telegram candidate behavior.
- `backend/domain/slot_service.py` and downstream repository flows remain sensitive because Telegram-linked booking is still a core path.

## Evidence
- `backend/apps/bot/handlers/common.py`
- `backend/apps/bot/services/test1_flow.py`
- `backend/apps/bot/services/slot_flow.py`
- `backend/apps/bot/services/notification_flow.py`
- `backend/apps/bot/reminders.py`
- `backend/domain/candidates/state_contract.py`
- `backend/domain/candidates/write_contract.py`
- `backend/apps/admin_api/candidate_access/services.py`
- `backend/core/messenger/registry.py`
