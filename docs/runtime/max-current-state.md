# MAX Current State

Last Verified: 2026-04-19

## Scope
- Current bounded MAX pilot runtime only.
- Launch/bootstrap, candidate-access miniapp flow, bounded chat path, rollout surface, and shared messaging hooks.

## Purpose
- Freeze what MAX actually does now so parity work starts from live code, not from target-state assumptions.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Runtime Status
- MAX candidate runtime today: `Live / Bounded`
- Telegram is the only production/live candidate messaging runtime today; MAX messaging exists only within a bounded pilot.

## Live Truth
- MAX launch/bootstrap is `Live / Bounded`.
  - `backend/apps/admin_api/main.py` mounts `/api/max/launch`, `/api/max/webhook`, `/miniapp`, and `/api/candidate-access/*`.
  - `backend/apps/admin_api/max_auth.py` validates signed MAX `initData`.
  - `backend/apps/admin_api/max_launch.py` validates `start_param`, loads or creates launch context, and issues/accesses MAX candidate-access sessions.
  - `backend/apps/admin_api/max_webhook.py` and `backend/apps/admin_api/max_candidate_chat.py` now reuse the same bounded global-intake bootstrap for plain bot `/start` without a personal invite when MAX rollout is enabled.
- Identity/session model is `Live / Bounded`.
  - `candidate_access/auth.py` enforces MAX-only access with session id, provider user id, auth method, surface, and session version checks.
  - `max_launch.py` and `max_candidate_chat.py` use `CandidateAccessSession`, `CandidateAccessToken`, `CandidateJourneySession`, and `CandidateJourneySurface`.
- Miniapp path is `Live / Bounded`.
  - `/miniapp` is mounted through `backend/apps/admin_api/max_miniapp.py`.
  - `/api/candidate-access/*` exposes journey, Test 1, booking context, recruiters, slots, manual availability, bookings, and chat handoff.
- Shared Test 1 is `Live / Bounded`.
  - Candidate-access uses shared `materialize_test1_questions`, `merge_test1_answers`, and `complete_test1_for_candidate`.
- Booking and no-slot fallback are `Live / Bounded`.
  - Candidate-access supports booking context, slot listing, create/confirm/reschedule/cancel booking, and manual availability submission.
  - `save_candidate_manual_availability(...)` activates the waiting-slot path and notifies recruiters.
- MAX chat path is `Partial`.
  - `backend/apps/admin_api/max_webhook.py` handles `bot_started`, text, and callbacks.
  - Callback ingress normalizes bounded dialog callback envelopes (`callback_id|id`, `payload|data|value`) and can recover the candidate identity from dialog recipient data when the callback update does not include a top-level `user`.
  - `backend/apps/admin_api/max_candidate_chat.py` provides bounded shared-chat orchestration over candidate-access state.
  - Chat exists, but parity completeness across the full journey is not proven.
- Handoff to chat is `Live / Bounded`.
  - Candidate-access `/chat-handoff` activates MAX chat prompt delivery when a MAX user id exists.
  - Plain bot `/start` and `entry:start_chat` can bootstrap the same shared candidate-access questionnaire path without a personal invite, but still stay inside the bounded MAX rollout gate.
- Operator rollout/invite surface is `Live / Bounded`.
  - `backend/apps/admin_ui/services/max_rollout.py` prepares preview/send/revoke and operator rollout state.

## Bounded / Pilot Only
- MAX is default-off and guarded by adapter/rollout configuration.
- Global `/miniapp` entry is a bounded pilot surface, not a production rollout promise.
- Messaging adapter resolution can choose MAX when a candidate has `max_user_id`, but this does not make MAX a production/live runtime.
- Operator invite/send/revoke is pilot-only.

## Partial
- MAX chat continuity across all non-happy-path branches is `Partial`.
- Shared delivery routing is present, but downstream reminders/outbox remain Telegram-leaning in many paths.
- Operator visibility for MAX progress exists through shared state/read models and rollout snapshots, but end-to-end parity observability is `Partial`.
- Immediate `Test1 -> booking` progression is controlled by shared runtime flags, not MAX-only logic:
  - `TEST1_SCREENING_DECISION_ENABLED`
  - `AUTO_INTERVIEW_OFFER_AFTER_TEST1_ENABLED`

## Missing / Not Proven
- MAX Test 2 candidate-facing flow is `Unknown / Not proven`.
- MAX orientation-day agreement flow is `Unknown / Not proven`.
- MAX meeting-details delivery flow is `Unknown / Not proven`.
- Full reminder/trigger parity in MAX is `Unknown / Not proven`.
- Resume / vacancy / HH link capture as a required explicit MAX journey step is `Unknown / Not proven`.

## Stale Docs To Ignore
- `docs/architecture/core-workflows.md` still frames MAX as future-only in its runtime note; live code and `docs/architecture/supported_channels.md` win.
- `docs/frontend/component-ownership.md` still treats `routes/candidate/*` as a live owned surface; `frontend/app/src/app/main.tsx` does not mount it.

## Evidence
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_api/max_launch.py`
- `backend/apps/admin_api/max_auth.py`
- `backend/apps/admin_api/max_webhook.py`
- `backend/apps/admin_api/max_candidate_chat.py`
- `backend/apps/admin_api/max_miniapp.py`
- `backend/apps/admin_api/candidate_access/router.py`
- `backend/apps/admin_api/candidate_access/services.py`
- `backend/apps/admin_api/candidate_access/auth.py`
- `backend/apps/admin_ui/services/max_rollout.py`
- `backend/core/messenger/registry.py`
- `docs/architecture/runtime-topology.md`
- `docs/architecture/supported_channels.md`
- `docs/frontend/route-map.md`
- `docs/frontend/state-flows.md`
