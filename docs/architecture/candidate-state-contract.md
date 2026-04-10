# Candidate State Contract

## Status

Additive compatibility layer landed on `2026-04-03`.

This is not the final write-path migration. It is the phase A/B to B+ read-contract foundation that:

- introduces one backend-owned compatibility contract for recruiter surfaces
- projects lifecycle and scheduling summaries from current legacy fields
- exposes backend-owned `candidate_next_action`
- exposes backend-owned `operational_summary` for recruiter buckets / kanban / queue semantics
- reports reconciliation issues instead of mutating state on read

Safe write consolidation for recruiter surfaces also landed on `2026-04-03` as an additive phase:

- kanban drag/drop now uses canonical `target_column` intent as the primary wire contract
- recruiter action endpoints now resolve domain intent server-side before bridging into any remaining legacy status helper
- write responses now return refreshed canonical recruiter-facing state instead of only a raw stored status

Dedicated lifecycle execution for four high-value recruiter actions also landed on `2026-04-03`:

- `send_to_test2`
- `mark_test2_completed`
- `finalize_hired`
- `finalize_not_hired`

These actions no longer use `backend/apps/admin_ui/services/candidates/helpers.py::update_candidate_status` as their primary execution core.

## Code anchors

- projector: [backend/domain/candidates/state_contract.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/state_contract.py)
- recruiter candidate detail/list read-model: [backend/apps/admin_ui/services/candidates/helpers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/helpers.py)
- dedicated recruiter lifecycle use-cases: [backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py)
- reusable domain status applier for loaded candidates: [backend/domain/candidates/status_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status_service.py)
- dashboard waiting queue payload enrichment: [backend/apps/admin_ui/services/dashboard.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/dashboard.py)
- recruiter detail UI consumer: [frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx)
- frontend contract types: [frontend/app/src/api/services/candidates.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/api/services/candidates.ts)

## Contract shape

Backend recruiter payloads now expose:

- `state_contract_version`
- `lifecycle_summary`
- `scheduling_summary`
- `candidate_next_action`
- `operational_summary`
- `state_reconciliation`

Recruiter write responses now also expose an additive blocked-state contract when an action or kanban move is rejected:

- `blocking_state`

These fields are additive. Legacy fields remain in place for compatibility:

- `candidate_status_slug`
- `workflow_status`
- `journey`
- `archive`
- `final_outcome`
- `candidate_actions`

## Authoritative intent

Current implementation encodes the target architecture without forcing a big-bang rewrite:

- lifecycle business stage is read from `lifecycle_summary`
- scheduling state is read from `scheduling_summary`
- recruiter CTA is read from `candidate_next_action`
- recruiter-facing bucket / kanban / queue semantics are read from `operational_summary`
- drift is surfaced via `state_reconciliation`

The old fields are still stored and still used by some write paths, but they should no longer be treated as the only decision-making surface for recruiter UI.

## Current migration boundary

Already done:

- backend compatibility projector over current `candidate_status`, `workflow_status`, journey/archive data, `Slot`, and `SlotAssignment`
- recruiter detail/list/dashboard payload enrichment
- recruiter detail action rail can use backend `candidate_next_action`
- recruiter incoming queue, dashboard incoming widgets, candidates list, and kanban now read a shared frontend adapter that treats `lifecycle_summary`, `scheduling_summary`, `candidate_next_action`, and `state_reconciliation` as the primary read contract
- dashboard waiting queue now batch-loads `Slot` and `SlotAssignment` state before projecting the compatibility contract, so recruiter incoming surfaces can render scheduling cues from backend-owned summaries instead of legacy-only status slugs
- dangerous write-on-read autofix after passed Test2 removed from candidate detail read-model
- `/api/candidates` now accepts canonical `state=` filters with backend-side compatibility for legacy values
- recruiter candidate list filter options are now server-owned and pipeline-aware
- kanban columns / target statuses / totals are now emitted by backend payloads and grouped by backend `operational_summary.kanban_column`
- incoming/dashboard queue semantics now prefer backend `operational_summary.queue_state` and backend signals over frontend-local derivation

Not done yet:

- broad write consolidation around dedicated lifecycle/scheduling use-cases beyond the four recruiter lifecycle actions listed above
- admin/API/bot/portal write-path retirement from raw legacy status helpers
- analytics event ledger migration
- legacy field retirement
- full retirement of `status=` query compatibility and other legacy list params
- full backend-owned action execution contract for all recruiter, admin, bot, and portal write flows

## Scheduling integrity tranche

Scheduling integrity stabilization and the follow-up repair/retirement tranche landed on `2026-04-05` as bounded migration-safe steps.

These tranches do not rewrite schema and do not introduce a competing scheduling model.

They do:

- make scheduling ownership explicit on the recruiter read contract
- block the most dangerous write-side conflict cases instead of silently proceeding
- add an explicit audited repair path for the safe persisted split-brain subset
- narrow several legacy slot-only contours instead of pretending they are already retired

### Scheduling integrity code anchors

- shared integrity evaluator: [backend/domain/candidates/scheduling_integrity.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/scheduling_integrity.py)
- recruiter read projection: [backend/domain/candidates/state_contract.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/state_contract.py)
- assignment-owned write execution: [backend/domain/slot_assignment_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)
- controlled repair use-case layer: [backend/domain/scheduling_repair_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/scheduling_repair_service.py)
- recruiter/admin repair endpoint: [backend/apps/admin_ui/routers/slot_assignments.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/slot_assignments.py)
- legacy compatibility confirm route: [backend/apps/admin_ui/routers/slot_assignments_api.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/slot_assignments_api.py)
- portal slot-only guard: [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- webapp slot-only guard: [backend/apps/admin_api/webapp/routers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/routers.py)
- legacy repository confirm bridge: [backend/domain/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py)
- recruiter write blockers: [backend/apps/admin_ui/services/candidates/write_intents.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/write_intents.py)

### Scheduling write-path map

Current mutation paths still span both `Slot` and `SlotAssignment`.

Primary `SlotAssignment`-owned paths:

- create / assign / offer: `create_slot_assignment(...)`
- candidate confirm: `confirm_slot_assignment(...)` and legacy compatibility `POST /api/slot-assignments/{id}/confirm`
- candidate reschedule request: `begin_reschedule_request(...)`, `request_reschedule(...)`
- recruiter exact reschedule approval: `approve_reschedule(...)`
- recruiter replace / alternative offer: `propose_alternative(...)`
- candidate decline / recruiter decline: assignment decline endpoints plus `decline_reschedule(...)`

Primary slot-only legacy paths still in circulation:

- `reserve_slot(...)`
- `approve_slot(...)`
- `reject_slot(...)`
- `confirm_slot_by_candidate(...)`
- portal slot-only endpoints in [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- older webapp/manual scheduling routes that still bind `Slot` directly before any full assignment-owned consolidation

Current narrowing already applied:

- portal slot-only reserve/confirm/cancel/reschedule now block when scheduling is assignment-owned or already requires manual repair
- webapp slot-only booking/reschedule/cancel now block when scheduling is assignment-owned or already requires manual repair
- legacy `confirm_slot_by_candidate(...)` now synchronizes a single matching active `SlotAssignment` on the same slot instead of leaving `SlotAssignment` stale behind a confirmed `Slot`

Read/write coupling surfaces:

- recruiter kanban / candidate actions now block on surfaced scheduling conflict
- dashboard / incoming / candidate detail now read `scheduling_summary` and `state_reconciliation` instead of normalizing conflict away

### Minimal invariant set

This tranche formalizes only the smallest migration-safe invariant set.

- Active `SlotAssignment` statuses are `offered`, `confirmed`, `reschedule_requested`, and `reschedule_confirmed`.
- An active `SlotAssignment` must point to an existing `Slot`.
- If an active `SlotAssignment` exists, write ownership is `slot_assignment`, not slot-only legacy helpers.
- Slot-only writes are allowed only when there is no active `SlotAssignment` and no manual-repair scheduling conflict.
- `offered -> pending slot` is valid.
- `confirmed -> booked/confirmed_by_candidate slot` is valid.
- `reschedule_requested -> pending/booked/confirmed_by_candidate slot` is valid while the previous candidate-held slot may still be visible as a surfaced transitional warning.
- `reschedule_confirmed -> booked/confirmed_by_candidate slot` is valid.

Conflict classes:

- `needs_manual_repair`
  - multiple active `SlotAssignment` rows for one candidate
  - active `SlotAssignment` without a real `Slot`
  - confirmed / reschedule-confirmed assignment that points to a different active slot than the candidate-held slot
  - assignment slot status that cannot explain the active assignment state
- `allow_with_warning`
  - recruiter alternative offer or candidate reschedule-request flow where `SlotAssignment` already points to a future slot while the old active slot is still retained as the currently held fact

### Repair taxonomy

Current persisted conflict taxonomy is intentionally narrow.

Repairable now:

- `scheduling_split_brain` where exactly one active `SlotAssignment` is the clear owner, the assignment status is `confirmed` or `reschedule_confirmed`, the assignment slot exists, and the stale active slot belongs to the same recruiter/purpose without another active assignment attached
- `scheduling_status_conflict` where exactly one active `SlotAssignment` exists, the assignment slot exists, and the canonical fix is to re-bind or re-status the assignment slot itself

Manual-only now:

- multiple active assignments
- missing assignment slot
- assignment slot claimed by another candidate
- cross-recruiter or cross-purpose stale active slot
- stale active slot that still has its own active assignment
- transitional split-brain around `offered` / `reschedule_requested`, where candidate confirmation or recruiter follow-up is still part of the unresolved business flow

Safe repair outcome for the supported subset:

- `assignment_authoritative`
  - use the single active `SlotAssignment` as the owner of fact
  - synchronize the assignment slot to the expected legacy `Slot` status
  - release superseded stale active slots for the same candidate when no other active assignment depends on them
  - write an explicit `AuditLog` record with before/after issue codes and released slot ids

Audit trail requirement:

- every controlled repair writes `scheduling_repair.assignment_authoritative` into `audit_log`
- repair is explicit and route-triggered; there is no write-on-read and no silent autofix

### Manual repair subset

Manual repair is now explicit and deny-by-default on the same `POST /api/slot-assignments/{id}/repair` control surface.

Supported manual actions now:

- `resolve_to_active_assignment`
  - conflict class: `multiple_active_assignments`
  - preconditions: all active assignments stay inside one recruiter owner and one purpose, operator explicitly chooses the canonical active assignment, and the chosen assignment slot is not claimed by another candidate
  - effect: cancel non-selected active assignments, release their stale candidate-held slots when no active assignment still depends on them, keep one active `SlotAssignment` owner
  - required confirmations: `selected_assignment_is_canonical`, `cancel_non_selected_active_assignments`
- `cancel_active_assignment`
  - conflict classes: `assignment_slot_missing`, `assignment_slot_claimed_by_other_candidate`
  - preconditions: operator accepts that the broken assignment owner should be removed instead of auto-rebound
  - effect: mark the active assignment inactive, optionally release its slot only when that slot is candidate-held by the same candidate and no active assignment still depends on it
  - required confirmations: `cancel_active_assignment`, `candidate_loses_assignment_owned_schedule`
- `rebind_assignment_slot`
  - conflict classes: `assignment_slot_missing`, `assignment_slot_claimed_by_other_candidate`
  - preconditions: operator explicitly chooses a candidate-held active slot under the same recruiter owner, and no competing active assignment already owns that slot
  - effect: rebind the active assignment to the selected slot and re-synchronize the canonical slot status from assignment state
  - required confirmations: `selected_slot_is_canonical`, `rebind_assignment_to_selected_slot`

Unsupported/manual-only classes remain deny-only:

- `cross_recruiter_active_slot`
- `cross_purpose_active_slot`
- `stale_slot_has_active_assignment`
- `assignment_status_not_repairable`
- `transitional_split_brain`
- `unsupported_conflict_class`
- `no_active_assignment_owner`

Current operator workflow boundary:

- backend only supports explicit single-record repair decisions; there is still no bulk repair or background normalization
- backend never auto-picks the winning owner for ambiguous/cross-owner conflicts
- backend requires explicit operator confirmations for manual actions and writes audit metadata for every successful repair decision
- repair request payload is bounded to `action`, optional `chosen_assignment_id`, optional `chosen_slot_id`, explicit `confirmations`, and optional `note`; there is no hidden mutation surface outside that contract

Required audit trail for manual subset:

- every successful manual action writes `scheduling_repair.manual_resolution` into `audit_log`
- audit payload records the chosen repair action, selected assignment/slot ids when relevant, cancelled assignment ids, released slot ids, before/after issue codes, operator confirmations, and optional note

### Conflict behavior policy

Current explicit write outcomes:

- `block`
  - recruiter action endpoints and kanban move endpoints when scheduling conflict is surfaced
  - portal slot-only mutations when an active `SlotAssignment` owns the fact
  - webapp slot-only mutations when an active `SlotAssignment` owns the fact
  - assignment-owned writes when persisted state already requires manual repair
  - exact reschedule approval / alternative proposal when the target slot is already occupied or effectively full
- `allow_with_warning`
  - recruiter alternative offer may still produce a surfaced transitional split-brain until the candidate confirms the new slot
- `needs_manual_repair`
  - surfaced on read contract, never hidden behind read normalization, and only repairable through the explicit subset below
- `controlled_repair`
  - `POST /api/slot-assignments/{id}/repair` now supports `assignment_authoritative`, `resolve_to_active_assignment`, `cancel_active_assignment`, and `rebind_assignment_slot`
  - caller must be admin or the owning recruiter
  - unsupported or cross-owner cases are still denied when taxonomy says `manual_only`

### Read contract additions

`scheduling_summary` now also exposes additive integrity ownership fields:

- `integrity_state`
- `write_behavior`
- `write_owner`
- `assignment_owned`
- `slot_only_writes_allowed`
- `repairability`
- `repair_options`
- `manual_repair_reasons`
- `repair_workflow`

`repair_workflow` is the future-UI bridge for operator tooling and includes:

- `policy`
- `conflict_class`
- `conflict_classes`
- `allowed_actions`
- `required_confirmations`
- `audit_metadata`

Action entries inside `repair_workflow.allowed_actions` may also include:

- `selection_requirements`
- `selection_options`
- `safe_outcome`
- `audit_action`

Repair endpoint success payloads now also return:

- `result_state.scheduling_summary`
- `audit_metadata`
- `failure_reason` on deny paths

These are for backend-owned recruiter/portal behavior and future repair tooling. They do not replace legacy fields yet.

### Persisted coverage added in this tranche

- recruiter action blocker on persisted split-brain state
- kanban blocker on persisted split-brain state
- exact reschedule approval sync between old/new `Slot`
- stale active slot vs confirmed assignment mismatch on recruiter detail/read contract
- portal slot-only reserve blocked when scheduling is assignment-owned
- controlled repair success for persisted confirmed split-brain state
- controlled repair deny for transitional split-brain state
- post-repair recruiter read contract returning to consistent scheduling state
- manual resolve success for duplicate active assignments
- manual cancel success for broken foreign-claimed assignment ownership
- manual rebind success for explicit single-owner slot pairing
- structured deny for cross-owner duplicate assignment repair attempt
- manual repair read contract exposing `repair_workflow` selection options and confirmations
- webapp slot-only booking blocked when scheduling is assignment-owned
- legacy candidate confirm syncing the matching active `SlotAssignment`

### Still transitional after this tranche

- `propose_alternative(...)` is still intentionally transitional and may surface `allow_with_warning` until candidate confirmation finalizes the new slot
- repair is now operable for the minimal safe subset, but cross-owner/cross-purpose conflicts and stale-slot-with-own-active-assignment cases remain surfaced-and-blocked rather than generally repairable
- legacy slot-only repository/webapp paths still exist and remain visible in the action map even though some of them are now guarded instead of fully bridged
- there is still no broad operator console or bulk repair workflow for persisted split-brain records

## Canonical filter contract

Primary recruiter list filter param:

- `state=<token>`

Current canonical token families:

- `kanban:<column>`
- `lifecycle:<stage>`
- `worklist:<bucket>`

Current recruiter UI uses backend-provided `filters.state_options` and primarily sends `kanban:<column>` values.

Backward compatibility:

- old `status=` query params are still accepted
- legacy raw status slugs sent through `state=` are also tolerated temporarily
- compatibility mapping now lives on the backend, not in recruiter UI

Current intentional limitation:

- write-paths still remain legacy-backed
- `worklist:` filter support is narrower than the long-term model; current recruiter UI does not depend on it yet

## Canonical recruiter write intents

Primary recruiter write contracts introduced in this phase:

- `POST /api/candidates/{id}/kanban-status` with `target_column`
- `POST /api/candidates/{id}/actions/{action_key}` where backend resolves `action_key` to domain intent and permitted transition

Current backend write-intent anchors:

- intent mapping: [backend/domain/candidates/write_contract.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/write_contract.py)
- recruiter write handlers: [backend/apps/admin_ui/services/candidates/write_intents.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/write_intents.py)
- API boundary: [backend/apps/admin_ui/routers/api_misc.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py)

Current domain intent examples:

- kanban move intents such as `send_to_test2` and `mark_test2_completed`
- recruiter action intents such as `approve_slot`, `reject_candidate`, `finalize_hired`, and `finalize_not_hired`

Current dedicated lifecycle use-cases:

- `send_to_test2` now resolves interview slot context, persists slot outcome, then applies `CandidateStatus.TEST2_SENT`
- `mark_test2_completed` is strict-pass and only applies `CandidateStatus.TEST2_COMPLETED` when the latest TEST2 result is passing
- `mark_hired` now applies `CandidateStatus.HIRED` through a dedicated lifecycle handler
- `mark_not_hired` now applies `CandidateStatus.NOT_HIRED` through a dedicated lifecycle handler and preserves the legacy negative follow-ups that still matter (`is_active=false`, intro-day slot release, HH sync, rejection dispatch planning)

The backend remains responsible for:

- validating whether the action is allowed in current candidate state
- rejecting scheduling-conflict cases instead of silently degrading
- resolving the final lifecycle transition
- returning refreshed canonical recruiter-facing state:
  - `lifecycle_summary`
  - `scheduling_summary`
  - `candidate_next_action`
  - `operational_summary`
  - `state_reconciliation`

## Blocked recruiter write contract

Recruiter write endpoints now standardize blocked responses for:

- `POST /api/candidates/{id}/actions/{action_key}`
- `POST /api/candidates/{id}/kanban-status`

Blocked responses keep the existing envelope and may include:

- top-level `error` as the primary machine-readable reason
- top-level `message` as the primary human-readable explanation
- `candidate_state` when current recruiter-facing state is available
- additive `blocking_state` with:
  - `code`
  - `category`
  - `severity`
  - `retryable`
  - `recoverable`
  - `manual_resolution_required`
  - `issue_codes`

Current stable blocked-state families:

- `scheduling_conflict`
- `unsupported_kanban_move`
- `missing_interview_scheduling`
- `missing_intro_day_scheduling`
- `invalid_kanban_transition`
- `action_not_allowed`
- `invalid_transition`
- `test2_not_passed`
- `partial_transition_requires_repair`

`blocking_state.issue_codes` is always derived from `candidate_state.state_reconciliation.issues` when `candidate_state` is present.

## Compatibility boundary

Backward compatibility remains server-owned:

- legacy kanban callers may still send `target_status`; the backend maps it to canonical `target_column`
- out-of-scope action endpoints still bridge to legacy `update_candidate_status` where dedicated lifecycle/scheduling write use-cases do not exist yet

This compatibility is transitional. Frontend recruiter surfaces should treat:

- `target_column` as the primary kanban move contract
- returned `candidate_state` as the primary post-write refresh payload

## What remains legacy-owned on write-side

Current recruiter write boundary is intentionally split into three buckets.

Canonical-use-case-owned:

- `send_to_test2`
- `mark_test2_completed`
- `finalize_hired`
- `finalize_not_hired`

Canonical-intent-owned but still legacy-executed:

- `approve_upcoming_slot`
- recruiter actions that still resolve through `write_intents.py` into `update_candidate_status(...)`
- safe kanban moves that use canonical `target_column` but still end in legacy storage transitions

Not stable for new design-driven interactive flows:

- scheduling creation / reservation / reschedule orchestration
- drag/drop models that assume direct movement into `slot_pending`, `interview_scheduled`, or `intro_day_scheduled`
- legacy `/candidates/{id}/status` form posts
- bot / portal / MAX write-paths

Still intentionally legacy-backed in this phase:

- storage writes in `candidate_status` / `workflow_status`
- most lifecycle mutation logic outside `send_to_test2`, `mark_test2_completed`, `mark_hired`, and `mark_not_hired`
- scheduling creation / reservation semantics for kanban columns such as `incoming`, `slot_pending`, `interview_scheduled`, and `intro_day_scheduled`
- bot / portal / MAX write-paths outside the recruiter web surfaces

Direct drag/drop is intentionally restricted to safe kanban columns that do not require the UI to invent scheduling side effects.

## Reconciliation semantics

`state_reconciliation.issues` is the explicit replacement for silent autofix on read.

Current issue families:

- `candidate_status_stale_after_test2_pass`
- `workflow_status_drift`
- `scheduling_split_brain`
- `scheduling_status_conflict`
- `closed_candidate_missing_archive_reason`
- `interview_stage_without_active_scheduling`

These issues are intended for UI/debug visibility and for later repair tooling. Read endpoints must not silently mutate candidate state anymore.

For the current design phase, recruiter surfaces can safely treat these fields as stable:

- `lifecycle_summary`
- `scheduling_summary`
- `candidate_next_action`
- `operational_summary`
- `state_reconciliation`
- `blocking_state` on recruiter write errors
