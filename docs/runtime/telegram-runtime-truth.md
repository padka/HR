# Telegram Runtime Truth

Last Verified: 2026-04-19

## Scope
- Production/live candidate messaging runtime in Telegram.
- Candidate bootstrap, Test 1, booking, no-slot fallback, operator handoff, recruiter chat, reminders, and Test 2.
- Only current runtime truth from live code and canonical docs.

## Purpose
- Freeze what Telegram actually does today so MAX parity work does not rediscover or accidentally regress the canonical channel.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Runtime Status
- Telegram candidate messaging runtime: `Live / Full`
- Telegram is the only production/live candidate messaging runtime today; MAX messaging exists only within a bounded pilot.

## Live Truth
- Bootstrap and identity binding are `Live / Full`.
  - `backend/apps/bot/handlers/common.py` handles `/start` and `/invite`.
  - `/start <payload>` and `/invite <token>` call `bind_telegram_to_candidate(...)`.
  - Plain `/start` calls `services.begin_interview(...)`.
- Candidate identity persistence is `Live / Full`.
  - Free-text flow and downstream services resolve the candidate from Telegram identity.
  - `cmd_start` logs funnel bootstrap with `channel=telegram`.
- Test 1 is `Live / Full`.
  - Telegram bot flow is stateful in `backend/apps/bot/services/test1_flow.py`.
  - Completion semantics are shared in `backend/domain/candidates/test1_shared.py`.
  - Shared next-action outputs include `select_interview_slot`, `recruiter_review`, `ask_candidate`, `hold`, and `human_decline_review`.
- Interview slot booking is `Live / Full`.
  - Telegram candidate booking runs through bot slot flow and shared slot/domain services.
  - Booking still depends on Telegram-linked candidate resolution in several downstream paths.
- No-slot fallback is `Live / Full`.
  - `backend/apps/bot/services/slot_flow.py` sends a manual scheduling prompt with `ForceReply`.
  - Candidate free-text availability is parsed, persisted, acknowledged, and recruiters are notified.
  - Candidate status is moved toward `waiting_slot` through status services when needed.
- Incoming/operator handoff is `Live / Full`.
  - Admin incoming and candidate workspace payloads include `state_contract_version`, `lifecycle_summary`, `scheduling_summary`, `candidate_next_action`, `operational_summary`, and `state_reconciliation`.
  - Waiting-slot and manual-availability data are surfaced in admin/operator flows.
- Recruiter chat is `Live / Full`.
  - Admin chat delivery resolves channel through recent inbound activity and candidate-linked identities.
  - Telegram delivery is still the normal live path when MAX is absent.
- Reminders and trigger notifications are `Live / Full`.
  - `backend/apps/bot/reminders.py` restores and schedules persisted reminder jobs.
  - Reminder/outbox execution remains heavily Telegram-coupled through `candidate_tg_id` and slot-linked Telegram identifiers.
- Test 2 is `Live / Full`.
  - `backend/apps/bot/services/test2_flow.py` starts, advances, and finalizes Test 2 in Telegram.
- Orientation-day and meeting-details delivery are `Partial`.
  - Shared lifecycle/status semantics and reminder types exist.
  - Telegram notification flow contains intro-day invitation/reminder handling.
  - A single end-to-end Telegram runtime truth document for every intro-day branch does not exist in code today.

## Boundaries / Not In Scope
- Telegram recruiter mini app at `/tg-app/*` is not candidate channel runtime.
- Legacy candidate portal is not part of current Telegram runtime truth.
- MAX bounded pilot must not be used to reinterpret Telegram behavior.

## Unknowns / Not Proven
- Resume / vacancy / HH link capture as a first-class required final Test 1 step is `Unknown / Not proven`.
- Complete end-to-end proof for all orientation-day branches and meeting-details branches inside Telegram candidate runtime is `Partial`, not fully proven from one canonical flow module.
- A single Telegram journey orchestrator module does not exist; the flow is spread across handlers/services/reminders.

## Evidence
- `backend/apps/bot/handlers/common.py`
- `backend/apps/bot/services/onboarding_flow.py`
- `backend/apps/bot/services/test1_flow.py`
- `backend/apps/bot/services/slot_flow.py`
- `backend/apps/bot/services/test2_flow.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services/notification_flow.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/candidates/helpers.py`
- `backend/domain/candidates/test1_shared.py`
- `backend/domain/candidates/state_contract.py`
- `docs/architecture/runtime-topology.md`
- `docs/architecture/supported_channels.md`
