# Project Context Index

Compact navigation for current Attila Recruiting work.

## Canonical docs

Read in this order:

1. [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
2. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
3. [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
4. [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
5. [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
6. [`.codex/config.toml`](/Users/mikhail/Projects/recruitsmart_admin/.codex/config.toml)
7. [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/)

## Current system map

- Backend admin app: `backend/apps/admin_ui/app.py`
- Admin API: `backend/apps/admin_api/main.py`
- Telegram bot: `backend/apps/bot/app.py`
- MAX bot: `backend/apps/max_bot/app.py`
- Candidate domain: `backend/domain/candidates/*`
- Candidate state contract: `backend/domain/candidates/state_contract.py`
- Scheduling integrity evaluator: `backend/domain/candidates/scheduling_integrity.py`
- Scheduling repair use-cases: `backend/domain/scheduling_repair_service.py`
- Delivery/MAX reliability map: [docs/architecture/delivery-max-reliability-map.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/delivery-max-reliability-map.md)
- Slot/schedule domain: `backend/domain/slot_service.py`, `backend/domain/slot_assignment_service.py`
- Frontend SPA: `frontend/app/src/app/main.tsx`
- Candidate portal: `frontend/app/src/app/routes/candidate/*`
- Recruiter dashboard/chat: `frontend/app/src/app/routes/app/*`
- MAX ownership guard and migration plan: `docs/architecture/max-ownership-guard-plan.md`

## Current migration anchors

- Lifecycle/scheduling compatibility ADR implementation: [docs/architecture/candidate-state-contract.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/candidate-state-contract.md)
- MAX owner cleanup readiness now has a canonical preflight path in [backend/domain/candidates/max_owner_preflight.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/max_owner_preflight.py), CLI wrapper [scripts/max_owner_preflight.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/max_owner_preflight.py), and runbook [docs/runbooks/max-ownership-guard-plan.md](/Users/mikhail/Projects/recruitsmart_admin/docs/runbooks/max-ownership-guard-plan.md)
- Recruiter read payloads now include `lifecycle_summary`, `scheduling_summary`, `candidate_next_action`, `operational_summary`, and `state_reconciliation`
- Recruiter write intents now live in [backend/domain/candidates/write_contract.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/write_contract.py) and [backend/apps/admin_ui/services/candidates/write_intents.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/write_intents.py)
- Dedicated recruiter lifecycle execution for `send_to_test2`, `mark_test2_completed`, `mark_hired`, and `mark_not_hired` now lives in [backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py) and uses [backend/domain/candidates/status_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status_service.py) as the domain status applier
- Candidate detail read-model no longer performs hidden Test2 status autofix on read
- Recruiter list/incoming/kanban/dashboard surfaces now consume a shared frontend contract adapter in [frontend/app/src/app/routes/app/candidate-state.adapter.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-state.adapter.ts)
- Shared recruiter-state UI primitives now live in [frontend/app/src/app/components/RecruiterState/index.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/components/RecruiterState/index.tsx) with route-agnostic styling in [frontend/app/src/app/components/RecruiterState/recruiter-state.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/components/RecruiterState/recruiter-state.css)
- Dashboard incoming queue now batch-loads `Slot` and `SlotAssignment` summaries before projecting recruiter cards in [backend/apps/admin_ui/services/dashboard.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/dashboard.py)
- `/api/candidates` canonical filter / bucket semantics now live in [backend/apps/admin_ui/services/candidates/helpers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/helpers.py) and [backend/apps/admin_ui/routers/api_misc.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py)
- Recruiter kanban write contract now prefers `target_column` and returns refreshed `candidate_state` from [backend/apps/admin_ui/routers/api_misc.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py)
- Recruiter blocked write responses now expose additive `blocking_state`, and the current recruiter design boundary is documented in [docs/architecture/candidate-state-contract.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/candidate-state-contract.md) with three buckets: canonical-use-case-owned, canonical-intent-owned-but-legacy-executed, and not-stable-for-new-design-flows
- Scheduling integrity tranche now documents the current write-owner split between `Slot` and `SlotAssignment`, the minimal invariant set, conflict outcomes (`block`, `allow_with_warning`, `needs_manual_repair`), the structured `repair_workflow` read contract, and the explicit repair taxonomy in [docs/architecture/candidate-state-contract.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/candidate-state-contract.md)
- Scheduling repair use-cases now cover both the safe automated subset and the bounded manual subset in [backend/domain/scheduling_repair_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/scheduling_repair_service.py), and the recruiter/admin control surface at [backend/apps/admin_ui/routers/slot_assignments.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/slot_assignments.py) returns structured confirmations, deny reasons, post-repair canonical scheduling state, and audit metadata for future UI work
- Candidate portal slot-only scheduling writes are now gated by backend ownership in [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py), webapp slot-only scheduling writes are now similarly guarded in [backend/apps/admin_api/webapp/routers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/routers.py), and legacy repository confirm in [backend/domain/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py) now syncs the matching active `SlotAssignment` instead of leaving it stale behind `Slot`
- Candidate portal activity-guard and candidate-facing timeline now live in [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py), [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py), [frontend/app/src/app/routes/candidate/start.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/start.tsx), and [frontend/app/src/app/routes/candidate/journey.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/journey.tsx): repeat `Test 1` is blocked after existing progress, `candidate_journey_events` + persisted state are projected into `history.items`, and candidate UX now resumes the active stage instead of implying a fresh onboarding start
- Candidate-facing Telegram scheduling controls now live across [backend/apps/bot/services/base.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/base.py), [backend/apps/bot/slot_assignment_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/slot_assignment_flow.py), [backend/apps/bot/keyboards.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/keyboards.py), and [backend/apps/bot/services/notification_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/notification_flow.py): this contour owns the assignment-backed active-meeting keyboard, legacy callback bridge, and post-decline recruiter feedback loop
- Current recruiter-web design grammar is decision-first: `candidate_next_action` is primary, `operational_summary` drives one-line context and triage lanes, `blocking_state` / `state_reconciliation` drive shared risk banners, kanban locked/system-driven treatment comes from backend `droppable`, and bulk triage in [frontend/app/src/app/routes/app/candidates.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidates.tsx) is selection-only by design
- Admin control-tower implementation now lives in [frontend/app/src/app/routes/app/dashboard.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/dashboard.tsx), where triage lanes reuse the same recruiter-state primitives as [frontend/app/src/app/routes/app/incoming.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/incoming.tsx)
- Candidate detail action-center sections now live in [frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx) and [frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx), with `Lifecycle / Scheduling / Risks / Context` hierarchy above tests and tools

## Current verification anchors

- Fast backend gate remains `make test` in [Makefile](/Users/mikhail/Projects/recruitsmart_admin/Makefile)
- PostgreSQL production-like tranche now lives behind `make test-postgres-proof` in [Makefile](/Users/mikhail/Projects/recruitsmart_admin/Makefile) with opt-in harness behavior in [tests/conftest.py](/Users/mikhail/Projects/recruitsmart_admin/tests/conftest.py)
- PostgreSQL proof suites are [tests/integration/test_migrations_postgres.py](/Users/mikhail/Projects/recruitsmart_admin/tests/integration/test_migrations_postgres.py) and [tests/integration/test_postgres_stateful_proof.py](/Users/mikhail/Projects/recruitsmart_admin/tests/integration/test_postgres_stateful_proof.py)
- Candidate-activity guard regression coverage now lives in [tests/test_candidate_portal_api.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_candidate_portal_api.py), [tests/test_bot_test1_validation.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_bot_test1_validation.py), [frontend/app/src/app/routes/candidate/start.test.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/start.test.tsx), and [frontend/app/src/app/routes/candidate/journey.test.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/journey.test.tsx)
- Current tranche reports live in [artifacts/verification/2026-04-06-postgres-proof-tranche/README.md](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-06-postgres-proof-tranche/README.md) and [artifacts/verification/2026-04-06-postgres-proof-expansion-tranche/README.md](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-06-postgres-proof-expansion-tranche/README.md)

## Business-critical flows

- candidate lifecycle and status transitions
- slot booking, reschedule, and confirmation
- recruiter chat and dashboard actions
- candidate portal and MAX mini app
- bot/webhook delivery and idempotency
- invite / deep-link / session recovery boundaries
- analytics and KPI reporting

## High-risk surfaces

- auth/session handling
- candidate portal token exchange
- webhooks and retries
- scheduling and slot assignment
- migrations
- analytics calculations
- PII in logs and traces

## Local Codex layer

- `.codex/config.toml` holds project defaults for safe agent operation.
- `.agents/skills/` holds reusable workflow gates for recurring tasks.
- `.codexrc` remains only as a compatibility shim until runtime precedence is confirmed.

## Current delivery/MAX hardening anchors

- MAX payload/session validation now rejects stale portal/MAX launch tokens using the same `journey_session_id` + `session_version` boundary as the web portal.
- Candidate portal session creation/restart now serializes on the candidate row to reduce duplicate-active-journey drift.
- `ensure_candidate_invite_token(...)` now locks/reuses active invite rows deterministically for the same candidate/channel.
- Admin MAX delivery outcome now records `invite_id`, `journey_id`, `session_version`, `restarted`, and `correlation_id` in message/audit metadata.
