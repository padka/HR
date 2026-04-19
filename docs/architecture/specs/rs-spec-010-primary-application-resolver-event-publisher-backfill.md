# RS-SPEC-010: Primary Application Resolver, Transactional Event Publisher, And Backfill Readiness

## Status
Proposed

## Date
2026-04-16

## Companion Docs
- [RS-ADR-002: Target Data Model For Candidate, Application, Requisition, Lifecycle, And Event Log](../adr/rs-adr-002-application-requisition-lifecycle-event-log.md)
- [RS-ADR-004: Candidate Access And Journey Surfaces For Browser / Telegram / MAX / SMS](../adr/rs-adr-004-candidate-access-and-journey-surfaces.md)
- [RS-ADR-005: Messaging Delivery Model And Channel Routing For Telegram / MAX / SMS](../adr/rs-adr-005-messaging-delivery-model-and-channel-routing.md)
- [RS-PLAN-006: Unified Migration Blueprint](../implementation/rs-plan-006-unified-migration-blueprint.md)
- [RS-RFC-007: Phase A Schema And API Contract Pack](../rfc/rs-rfc-007-phase-a-schema-and-api-contract-pack.md)
- [docs/architecture/supported_channels.md](../supported_channels.md)
- [docs/security/trust-boundaries.md](../../security/trust-boundaries.md)

## Scope
Этот spec фиксирует implementation-ready design для следующего blocker-пакета перед dual-write:

- deterministic primary application resolver;
- transactional `application_events` publisher;
- safe read-only profiling/backfill readiness plan.

Документ не меняет runtime behavior. Он задаёт contracts, sequencing и validation rules для будущего `Phase B`.

## Non-Goals
- no runtime cutover;
- no migration code;
- no changes to existing APIs;
- no changes to scheduling truth in `slots` / `slot_assignments`;
- no Telegram webapp changes;
- no HH callback contract changes;
- no feature flags in этом spec;
- no destructive merge/backfill;
- no direct DB writes from `n8n`;
- no restoration of legacy candidate portal or historical MAX runtime.

## Current Runtime Anchors
Current write paths, которые нужно покрыть в будущем implementation:

- candidate create/update/manual lifecycle:
  - [backend/apps/admin_ui/routers/api_misc.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py:2602)
  - [backend/apps/admin_ui/services/candidates/helpers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/helpers.py:3658)
  - [backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py:252)
  - [backend/domain/candidate_status_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidate_status_service.py:1)
- slot / interview lifecycle:
  - [backend/domain/slot_assignment_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py:1)
  - [backend/domain/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py:1180)
- HH import / sync / webhook processing:
  - [backend/domain/hh_integration/importer.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/hh_integration/importer.py:1)
  - [backend/domain/hh_integration/outbound.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/hh_integration/outbound.py:1)
  - [backend/domain/hh_sync/worker.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/hh_sync/worker.py:1)
  - [backend/apps/admin_api/hh_sync.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/hh_sync.py:1)
- candidate chat / notification / outbox:
  - [backend/apps/admin_ui/services/chat.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/chat.py:1)
  - [backend/domain/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py:645)
  - [backend/domain/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py:846)
- AI audit and feedback:
  - [backend/core/ai/service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/ai/service.py:1)
  - [backend/domain/ai/models.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/ai/models.py:1)

## Normative Decisions
1. Resolver never guesses requisition aggressively. Ambiguous demand must resolve to `applications.requisition_id = null`, not to a guessed requisition.
2. Strong signals outrank weak signals. Resolver precedence is deterministic and stable across write paths.
3. Resolver may create a null-requisition application when a write path needs an application anchor for lifecycle/event consistency.
4. Business mutation and `application_events` insert must be in one database transaction for every new dual-write path.
5. `application_events` is append-only. Corrections are follow-up events, not updates of prior rows.
6. `idempotency_key` is producer-scoped. Same key plus same normalized payload returns existing event; same key plus different payload is a hard conflict.
7. `correlation_id` must flow through resolver, mutation, outbox, delivery, AI and HH side effects.
8. `n8n` remains API-driven only and never writes event tables directly.

## 1. Primary Application Resolver

### 1.1 Resolver Invariants
- `applications` is the recruiting lifecycle grain. `users` remains the legacy person record.
- Phase B must allow candidate-scoped applications with `requisition_id = null` for ambiguous or weak-demand writes.
- One active application per candidate per requisition is the target invariant, but repair of dirty legacy data happens before hardening.
- Resolver is deterministic by signal strength, not by last-updated randomness.
- A slot-driven or HH-driven strong signal can bind to a requisition later; weak signals cannot.

### 1.2 Signal Hierarchy

**Strong signals**
- explicit `application_id` supplied by trusted caller;
- active `slot_assignment_id` or slot chain that already anchors candidate scheduling;
- exact HH linkage: `hh_negotiation_id`, `hh_vacancy_id`, `candidate_external_identities.external_negotiation_id`, `candidate_external_identities.external_vacancy_id`;
- explicit manual requisition or vacancy chosen by recruiter in the same transaction.

**Weak signals**
- `users.desired_position`;
- `users.source`;
- `users.city`;
- `users.telegram_id`, `users.telegram_user_id`, `users.max_user_id`, `users.messenger_platform`;
- message-only context without application correlation.

**Rule**
- weak signals may justify creating or reusing a null-requisition application;
- weak signals must not choose a requisition when several live demands are plausible.

### 1.3 Deterministic Resolution Order
1. Reuse explicit `application_id` if it belongs to the candidate and is not duplicated by another active exact match.
2. Reuse the unique active application already bound to the exact requisition when the caller supplies trusted requisition or vacancy context.
3. Resolve via active `slot_assignment` or slot-derived demand binding.
4. Resolve via HH negotiation or HH vacancy binding.
5. Resolve via explicit manual requisition/vacancy provided by trusted admin flow.
6. Reuse one active null-requisition application if and only if it is the only candidate-scoped active unresolved application.
7. If no safe anchor exists and the write path requires an application anchor, create a null-requisition application.
8. If the write path does not require an application anchor, return unresolved without creation.

### 1.4 Resolver Rule Matrix

#### Candidate created manually
- Inputs:
  - `candidate_id`
  - optional recruiter-selected requisition or vacancy
  - optional `desired_position`, `city`, `source`
- Decision:
  - use explicit requisition/vacancy if trusted and unique
  - otherwise create candidate-scoped application with `requisition_id = null` only when the create flow needs lifecycle anchoring
- Fallback:
  - unresolved candidate plus later manual binding
- Creates application:
  - `yes` if the create path needs lifecycle/event anchoring
- Leaves `requisition_id = null`:
  - `yes` when only weak signals exist
- Emitted events:
  - `candidate.created`
  - `application.created` when application row created
- Idempotency key:
  - `candidate-create:{candidate_id}:{source_ref}`

#### Candidate imported from HH
- Inputs:
  - `candidate_id`
  - `hh_resume_id`
  - optional `hh_negotiation_id`
  - optional `hh_vacancy_id`
  - optional linked `candidate_external_identities`
- Decision:
  - exact HH negotiation or vacancy binding is strong and may create or reuse requisition-bound application
  - if HH data exists but vacancy binding is missing or maps to several requisitions, create/reuse null-requisition application
- Fallback:
  - keep application candidate-scoped and push to HH/manual review queue
- Creates application:
  - `yes`
- Leaves `requisition_id = null`:
  - `yes` when no unique requisition binding exists
- Emitted events:
  - `candidate.created`
  - `candidate.updated`
  - `application.created`
  - `hh.negotiation.imported`
- Idempotency key:
  - `hh-import:{source}:{external_resume_or_negotiation_id}`

#### Candidate from Telegram flow
- Inputs:
  - `candidate_id`
  - `telegram_id` and/or `telegram_user_id`
  - optional invite token, start param, message correlation, slot offer context
- Decision:
  - if invite token or slot assignment resolves to one application, reuse it
  - if the flow only proves identity/channel ownership, do not guess requisition from Telegram presence alone
- Fallback:
  - reuse one active null-requisition application or create one if lifecycle anchoring is required
- Creates application:
  - `yes` only for lifecycle write paths, not for passive identity-link flows
- Leaves `requisition_id = null`:
  - `yes` when demand is not explicit
- Emitted events:
  - `candidate.channel_identity.linked`
  - `application.created` if application created
- Idempotency key:
  - `telegram-flow:{candidate_id}:{transport_ref}`

#### Candidate has `desired_position` only
- Inputs:
  - `candidate_id`
  - `desired_position`
- Decision:
  - treat as weak demand hint only
- Fallback:
  - null-requisition application if caller requires an application anchor
- Creates application:
  - `optional`, only if the write path needs it
- Leaves `requisition_id = null`:
  - `always`
- Emitted events:
  - `candidate.updated`
  - `application.created` if created
- Idempotency key:
  - `desired-position:{candidate_id}:{normalized_position_hash}`

#### Candidate has `hh_vacancy_id`
- Inputs:
  - `candidate_id`
  - `hh_vacancy_id`
  - optional negotiation id
- Decision:
  - map `hh_vacancy_id` to requisition only if there is one deterministic binding
  - multiple candidate requisitions sharing same vacancy stays ambiguous
- Fallback:
  - create/reuse null-requisition application
- Creates application:
  - `yes`
- Leaves `requisition_id = null`:
  - `yes` if vacancy-to-requisition binding is absent or ambiguous
- Emitted events:
  - `application.created`
  - `hh.negotiation.imported` or `hh.status_sync.completed` depending on path
- Idempotency key:
  - `hh-vacancy:{candidate_id}:{hh_vacancy_id}`

#### Candidate has `slot_assignment`
- Inputs:
  - `candidate_id`
  - `slot_assignment_id`
  - underlying `slot_id`, recruiter, city, purpose
- Decision:
  - slot assignment is strong
  - resolver should reuse slot-bound application if unique
  - if slot chain exists but requisition binding does not, create/reuse candidate-scoped application and attach interview linkage later
- Fallback:
  - null-requisition application plus manual scheduling review
- Creates application:
  - `yes`
- Leaves `requisition_id = null`:
  - `yes` if scheduling truth has no deterministic demand binding
- Emitted events:
  - `interview.scheduled`
  - `application.owner_assigned` when recruiter ownership becomes explicit
  - `application.created` if created
- Idempotency key:
  - `slot-assignment:{slot_assignment_id}:{status_or_transition}`

#### Candidate has city but no vacancy
- Inputs:
  - `candidate_id`
  - `city`
- Decision:
  - city alone is weak signal and never resolves requisition
- Fallback:
  - null-requisition application or unresolved candidate
- Creates application:
  - `optional`
- Leaves `requisition_id = null`:
  - `always`
- Emitted events:
  - `candidate.updated`
  - `application.created` if created
- Idempotency key:
  - `city-only:{candidate_id}:{normalized_city}`

#### Candidate has multiple possible vacancies or requisitions
- Inputs:
  - several live requisition candidates from HH, manual ownership, scheduling or analytics sidecars
- Decision:
  - do not auto-pick one
  - if there is already one active exact match and the other candidates are historical or terminal, reuse exact match
  - otherwise treat as ambiguous
- Fallback:
  - null-requisition application and manual review queue
- Creates application:
  - `yes` if no safe existing anchor exists and write path needs one
- Leaves `requisition_id = null`:
  - `always`
- Emitted events:
  - `application.created`
  - optional `candidate.updated` or domain event from caller
- Idempotency key:
  - `resolver-ambiguous:{candidate_id}:{context_hash}`

#### Candidate has no demand context
- Inputs:
  - candidate identity only
- Decision:
  - `resolve_primary_application` returns unresolved
  - `ensure_application_for_candidate` may create a candidate-scoped application for lifecycle/event continuity
- Fallback:
  - unresolved candidate until an explicit demand appears
- Creates application:
  - `only` via `ensure_*` methods
- Leaves `requisition_id = null`:
  - `always`
- Emitted events:
  - `application.created` if created
- Idempotency key:
  - `candidate-anchor:{candidate_id}:{producer_family}`

#### Candidate is archived or reopened
- Inputs:
  - candidate lifecycle change
  - optional prior terminal or archived application
- Decision:
  - if the same requisition is reactivated and no active twin exists, reopen/reuse the archived application
  - if reopened reason does not map deterministically to prior demand, create/reuse null-requisition application
- Fallback:
  - unresolved reopen review
- Creates application:
  - `yes` if no safe archived anchor exists
- Leaves `requisition_id = null`:
  - `yes` when reopen context is weak or ambiguous
- Emitted events:
  - `application.status_changed`
  - `candidate.updated`
- Idempotency key:
  - `candidate-reopen:{candidate_id}:{reopen_source_ref}`

#### Candidate has duplicate applications risk
- Inputs:
  - multiple active exact or null-requisition applications
- Decision:
  - if one active exact candidate+requisition match exists, reuse it
  - if more than one active exact match exists, fail with duplicate error
  - if more than one active null-requisition application exists, fail ambiguous and route to manual repair
- Fallback:
  - no new application creation until duplicate risk is resolved
- Creates application:
  - `no`
- Leaves `requisition_id = null`:
  - not applicable; resolver stops
- Emitted events:
  - none from resolver itself; caller should surface repair task
- Idempotency key:
  - `duplicate-guard:{candidate_id}:{context_hash}`

### 1.5 Resolver Algorithm Sketch

```text
collect signals
normalize source context
load candidate applications + active slot chains + HH identities in one transaction
if explicit application_id is valid -> return it
if trusted requisition/vacancy maps to one active application -> return it
if active slot assignment maps to one application -> return it
if exact HH signal maps to one requisition/application -> return it
if one active null-requisition application exists -> return it
if caller allows create -> create null-requisition application
else -> unresolved
```

### 1.6 Resolver Safety Rules
- Resolver must be pure with respect to ambiguous demand: `ambiguous` is a valid outcome.
- Resolver must not infer requisition from `desired_position`, `source`, `city`, Telegram/MAX identity or message history alone.
- Resolver must not mutate scheduling truth.
- Resolver must not auto-merge duplicate applications.

## 2. Resolver Service Interfaces

### 2.1 Shared DTOs

```python
class ResolverContextDTO(TypedDict, total=False):
    producer_family: str
    source_system: str
    source_ref: str
    actor_type: str
    actor_id: str | int | None
    correlation_id: str | None
    explicit_application_id: int | None
    explicit_requisition_id: int | None
    explicit_vacancy_id: int | None
    slot_assignment_id: int | None
    slot_id: int | None
    hh_resume_id: str | None
    hh_negotiation_id: str | None
    hh_vacancy_id: str | None
    message_thread_id: int | None
    message_correlation_id: str | None
    ai_scope_type: str | None
    ai_scope_id: int | None
    allow_create: bool
```

```python
class ResolverResultDTO(TypedDict):
    status: Literal["resolved", "created", "unresolved", "ambiguous", "duplicate_conflict"]
    candidate_id: int
    application_id: int | None
    requisition_id: int | None
    created_application: bool
    used_signal: str | None
    resolution_notes: list[str]
    emitted_event_types: list[str]
```

### 2.2 `resolve_primary_application(candidate_id, context)`
- Input DTO:
  - `candidate_id`
  - `ResolverContextDTO`
- Output DTO:
  - `ResolverResultDTO`
- Error classes:
  - `CandidateNotFoundError`
  - `DuplicateActiveApplicationError`
  - `ResolverContextConflictError`
- Idempotency behavior:
  - read-only resolution; deterministic for same candidate snapshot and normalized context
- Transaction boundary:
  - same transaction as caller when used for business mutation; standalone read transaction allowed for dry-run/debug use

### 2.3 `ensure_application_for_candidate(candidate_id, context)`
- Input DTO:
  - `candidate_id`
  - `ResolverContextDTO` with `allow_create=True`
- Output DTO:
  - `ResolverResultDTO`
- Error classes:
  - `CandidateNotFoundError`
  - `DuplicateActiveApplicationError`
  - `ApplicationCreateConflictError`
- Idempotency behavior:
  - same `producer_family + source_ref + candidate_id` must not create more than one application
- Transaction boundary:
  - creates application in caller transaction only

### 2.4 `resolve_application_for_slot_assignment(slot_assignment_id)`
- Input DTO:
  - `slot_assignment_id`
  - optional `candidate_id`
  - optional `correlation_id`
- Output DTO:
  - `ResolverResultDTO`
- Error classes:
  - `SlotAssignmentNotFoundError`
  - `SchedulingLinkIntegrityError`
  - `DuplicateActiveApplicationError`
- Idempotency behavior:
  - deterministic per slot assignment state
- Transaction boundary:
  - must share caller transaction for any write path that also updates scheduling rows

### 2.5 `resolve_application_for_hh_event(...)`
- Input DTO:
  - `candidate_id`
  - `hh_resume_id`
  - optional `hh_negotiation_id`
  - optional `hh_vacancy_id`
  - `producer_family`
  - `source_ref`
- Output DTO:
  - `ResolverResultDTO`
- Error classes:
  - `HHIdentityConflictError`
  - `DuplicateActiveApplicationError`
- Idempotency behavior:
  - deterministic by external HH identity and source event id
- Transaction boundary:
  - same transaction as HH job mutation or callback persistence

### 2.6 `resolve_application_for_message(...)`
- Input DTO:
  - `candidate_id`
  - message correlation, thread id, template purpose, optional slot assignment id
- Output DTO:
  - `ResolverResultDTO`
- Error classes:
  - `ThreadCandidateMismatchError`
  - `DuplicateActiveApplicationError`
- Idempotency behavior:
  - deterministic by message intent correlation
- Transaction boundary:
  - same transaction as message intent creation for new dual-write paths

### 2.7 `resolve_application_for_ai_output(...)`
- Input DTO:
  - `candidate_id`
  - `ai_scope_type`
  - `ai_scope_id`
  - optional related HH or scheduling refs
- Output DTO:
  - `ResolverResultDTO`
- Error classes:
  - `AIScopeConflictError`
  - `DuplicateActiveApplicationError`
- Idempotency behavior:
  - deterministic by AI request/output anchor
- Transaction boundary:
  - same transaction as AI audit row write when AI output becomes business-relevant

## 3. Transactional Event Publisher

### 3.1 Base Event Contract

```python
class ApplicationEventCommand(TypedDict, total=False):
    event_id: str
    correlation_id: str
    idempotency_key: str
    event_type: str
    occurred_at: datetime
    actor_type: str | None
    actor_id: str | int | None
    candidate_id: int
    application_id: int | None
    requisition_id: int | None
    source_system: str
    source_ref: str
    channel: str | None
    metadata_json: dict
```

Required fields for every published event:
- `event_id` UUID
- `correlation_id` UUID
- `idempotency_key`
- `event_type`
- `occurred_at`
- `candidate_id`
- `source_system`
- `source_ref`
- `metadata_json`

Nullable in early phases:
- `application_id`
- `requisition_id`
- `actor_type`
- `actor_id`
- `channel`

### 3.2 Publisher Interface
- `publish_application_event(command)`
- `publish_status_transition(command, status_from, status_to)`
- `publish_message_event(command)`
- `publish_interview_event(command)`
- `publish_ai_event(command)`
- `publish_hh_event(command)`
- `publish_n8n_event(command)`

### 3.3 Transaction Boundary
- New dual-write path rule:
  - business mutation and event insert are in one transaction
  - if event insert fails, business mutation must roll back
- Acceptable sequence:
  1. open DB transaction
  2. run resolver if needed
  3. persist business mutation
  4. insert `application_events` row
  5. commit

### 3.4 Duplicate Handling
- same `idempotency_key` plus same normalized payload:
  - return existing event
  - mark publisher result as duplicate/no-op
- same `idempotency_key` plus different normalized payload:
  - raise `IdempotencyConflictError`
  - caller transaction must roll back
- same event type and correlation but different idempotency keys:
  - allowed only when the business action is intentionally different

### 3.5 Append-Only Behavior
- `application_events` rows are immutable after insert
- replay or correction creates a new event:
  - example: bad `application.status_changed` is corrected by a second status event, not by update-in-place

### 3.6 Failure Behavior
- Resolver error:
  - fail caller transaction
- Publisher uniqueness conflict:
  - return existing event only if normalized payload matches
- Database insert error:
  - roll back business mutation
- Downstream sidecar failure after commit:
  - allowed only if sidecar is non-canonical
  - canonical event row must already exist

### 3.7 Producer-Scoped Idempotency
Recommended key prefixes:

- `candidate-create:*`
- `candidate-status:*`
- `slot-assignment:*`
- `hh-import:*`
- `hh-sync:*`
- `message-intent:*`
- `message-delivery:*`
- `ai-feedback:*`
- `n8n-workflow:*`

## 4. Event Taxonomy Mapping

| Current write path | Canonical event(s) | Notes |
| --- | --- | --- |
| candidate create in [api_misc.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py:2602) and [helpers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/helpers.py:3658) | `candidate.created`, `application.created` | application event only when resolver creates or finds anchor |
| candidate update / recruiter edits in [helpers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates/helpers.py:3658) | `candidate.updated`, `application.owner_assigned` when recruiter ownership becomes explicit | do not emit owner assignment on cosmetic edits |
| Telegram/MAX identity linking in [backend/domain/candidates/services.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/services.py:1) | `candidate.channel_identity.linked` | identity truth, not message truth |
| status transitions in [candidate_status_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidate_status_service.py:1) and lifecycle use cases | `application.status_changed` | include `status_from`, `status_to` in metadata |
| recruiter assignment or manual ownership changes | `application.owner_assigned` | separate from status change |
| message intent creation in chat/outbox services | `message.intent_created` | business intent before provider delivery |
| delivery attempt success path | `message.sent` | emitted after attempt row becomes sent |
| provider receipt delivered | `message.delivered` | emitted after receipt normalization |
| provider failure terminal path | `message.failed` | include `failure_class`, `failure_code` |
| scheduling create/confirm flow in [slot_assignment_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py:1) | `interview.scheduled`, `interview.confirmed` | scheduling truth remains legacy |
| intro/interview outcome updates in slots/detailization flows | `interview.completed`, `interview.no_show` | do not replace detailization source yet |
| AI generation in [backend/core/ai/service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/ai/service.py:1) | `ai.recommendation.generated` | only when output is persisted as auditable recommendation |
| recruiter feedback on AI result | `ai.recommendation.accepted`, `ai.recommendation.edited`, `ai.recommendation.rejected` | map from `AIInterviewScriptFeedback` outcome |
| HH import and HH webhook intake | `hh.negotiation.imported`, `hh.status_sync.requested`, `hh.status_sync.completed` | use HH external ids in metadata |
| n8n workflow callbacks through backend API | `n8n.workflow.triggered`, `n8n.workflow.completed`, `n8n.workflow.failed` | `n8n` does not write DB directly |

## 5. Backfill And Profiling Plan

### 5.1 Read-Only Profiling Objectives
- quantify data conflicts before constraints hardening;
- identify which legacy rows can backfill deterministically;
- separate blockers from acceptable null-forward-fill cases;
- avoid printing PII or secrets;
- produce manual review queues, not guessed repairs.

### 5.2 Profiling Coverage

#### Identity and candidate linkage
- `users.phone_normalized` duplicates
- `users.telegram_id` and `users.telegram_user_id` duplicate groups
- `chat_messages.telegram_user_id` mapped to multiple candidates
- `candidate_invite_tokens.used_by_telegram_id` mapped to multiple candidates
- `users.max_user_id` duplicate groups

#### HH and demand signals
- candidates with any `hh_*` fields
- duplicated `hh_resume_id` / `hh_negotiation_id`
- `candidate_external_identities` with overlapping external resume or vacancy bindings
- candidates with `source` / `desired_position` but no deterministic vacancy binding

#### Scheduling anchors
- `slot_assignments` with neither `candidate_id` nor `candidate_tg_id`
- `slot_assignments` that only have `candidate_tg_id` but no matching user
- active slot assignment conflicts by candidate identifier

#### Messaging and delivery anchors
- `chat_messages` whose `telegram_user_id` does not match the linked user
- `outbox_notifications` with no usable booking, candidate, correlation or provider anchor
- `notification_logs` that still cannot map cleanly to delivery attempts

#### Interview, AI and journey artifacts
- `detailization_entries` without slot or assignment anchor
- `interview_notes` totals as a legacy interview artifact coverage check
- `ai_outputs` / `ai_request_logs` whose scope cannot map cleanly to candidate/application audit
- `candidate_journey_sessions` with multiple active sessions per candidate
- `candidate_journey_sessions` with no access-session anchor
- `candidate_invite_tokens` active duplicates by candidate/channel

### 5.3 Script
Read-only profiling script is provided at [scripts/profile_phase_a_backfill_readiness.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/profile_phase_a_backfill_readiness.py).

Rules for the script:
- read-only session usage only;
- no writes, no migrations, no commits;
- safe for local/staging against existing project DB settings;
- aggregate counts only;
- exits non-zero only on execution or schema error.

### 5.4 Backfill Readiness Interpretation

**Blockers**
- identity collisions that make candidate/application ownership unsafe
- duplicate active scheduling anchors
- conflicting active invite or channel ownership data

**Warnings**
- legacy rows that are still backfillable with nulls or later reconciliation
- unmappable AI or message artifacts that do not block resolver rollout

**Ambiguous cases**
- demand hints with no deterministic requisition
- historical message rows without enough correlation to reconstruct deliveries
- journey sessions that cannot be safely tied to a future access session

## 6. Dry-Run Report Format

Expected text report shape:

```text
Phase A backfill readiness
Generated at: 2026-04-16T...

Counts
- users_total: ...
- users_with_hh_fields: ...
- slot_assignments_total: ...

Blockers
- phone_normalized_duplicates: 12 groups
- telegram_identity_conflicts: 3 groups

Warnings
- weak_demand_only_candidates: 184
- ai_outputs_unmappable: 27

Ambiguous cases
- outbox_mapping_gaps: 41
- journey_sessions_without_access_anchor: 96

Manual review queues
- identity_conflicts_review
- ambiguous_demand_review
- scheduling_link_review
```

Expected JSON report shape:
- `generated_at`
- `counts`
- `blockers`
- `warnings`
- `ambiguous_cases`
- `manual_review_queues`

The report must not print phones, Telegram IDs, MAX IDs, tokens, raw payloads, or message text.

## 7. Testing Strategy

### Resolver tests
- unit tests for strong-signal precedence
- unit tests for weak-signal null-requisition behavior
- duplicate active application error tests
- archived/reopened reuse tests
- ambiguous demand tests that prove no aggressive requisition guess

### Event publisher tests
- append-only insert success
- same idempotency key plus same payload returns existing event
- same idempotency key plus different payload raises conflict
- publisher accepts nullable `application_id` and `requisition_id` in early phases

### Transaction tests
- candidate status mutation rolls back when event insert fails
- slot/interview mutation rolls back when event insert fails
- HH sync job mutation rolls back when event insert fails
- message intent creation rolls back when event insert fails

### Profiling script tests
- aggregate bucket classification tests
- text and JSON rendering tests
- output redaction tests
- execution error path returns non-zero
- warnings and blockers still return exit code `0`

### Integration tests for future write paths
- candidate create/update path with resolver + publisher
- slot assignment confirmation path with resolver + interview event
- HH import path with resolver + HH event
- chat/outbox path with resolver + message intent event
- AI feedback path with resolver + AI recommendation event

## 8. Rollback Strategy

### 8.1 Disable dual-write
This spec does not introduce feature flags. Rollback for future Phase B implementation must therefore be operational:

1. deploy previous build that removes resolver/publisher wiring from write paths;
2. leave new tables in place but unread;
3. keep legacy writes as the only operational truth again.

### 8.2 Ignore new events in reads
- Phase B should keep reads on legacy truth until parity is validated
- analytics and dashboards must not switch to `application_events` during initial dual-write

### 8.3 Replay missed events
- replay only from canonical legacy audit sources:
  - `candidate_journey_events`
  - `hh_sync_log`
  - `chat_messages`
  - `notification_logs`
  - `outbox_notifications`
  - `ai_interview_script_feedback`
- replay uses new producer-scoped `idempotency_key` rules
- replay never mutates business rows, only fills event history gaps

### 8.4 Divergence detection
Required parity counters for future rollout:
- resolver ambiguity rate
- duplicate active application detection count
- event insert failure count
- mutation-without-event parity count
- delivery receipt completeness
- duplicate send rate
- scheduling anchor mismatch count

### 8.5 Avoid double analytics
- analytics continues to read legacy telemetry until formal cutover
- `application_events` is written but ignored by analytics reads during initial dual-write
- any shadow analytics run must write to separate debug tables or offline reports only

## 9. Phase B Backlog
1. Build write-path inventory doc with exact producer families and existing transaction scopes.
2. Implement repository-level application lookup primitives for exact requisition and null-requisition matches.
3. Implement `resolve_primary_application()` read-only path with strong/weak signal precedence.
4. Implement `ensure_application_for_candidate()` create path with producer-scoped idempotency.
5. Add `application_events` repository with append-only insert and idempotency conflict semantics.
6. Integrate publisher into candidate create/update flows without changing APIs.
7. Integrate publisher into status transition flows in `candidate_status_service`.
8. Integrate resolver and publisher into slot assignment confirmation/reschedule paths.
9. Integrate resolver and publisher into HH import and outbound sync worker paths.
10. Integrate resolver and publisher into message intent creation and delivery-attempt creation paths.
11. Integrate resolver and publisher into AI recommendation acceptance/edit/reject flows.
12. Add transactional tests for rollback on event insert failure.
13. Run profiling script on staging snapshot and publish aggregate readiness report.
14. Define manual review playbooks for identity conflicts, ambiguous demand and scheduling link gaps.
15. Repair the top blocker buckets in legacy data before constraint hardening.
16. Backfill candidate-scoped applications where future write paths require stable anchors.
17. Backfill `application_events` from deterministic legacy sidecars only.
18. Validate parity counters and shadow divergence reports before any read cutover.

## 10. Recommended Next Step Backlog

### Immediate
- run the read-only readiness script on local and staging copies;
- baseline blocker counts and manual review queue sizes;
- finalize producer-family idempotency namespaces for candidate, slot, HH, messaging, AI and `n8n`.

### Before dual-write implementation
- confirm exact places where business mutation and event insert can share one SQLAlchemy transaction;
- confirm replay sources and retention windows;
- confirm which write paths are allowed to create null-requisition applications automatically.

### Before constraint hardening
- clear identity conflicts first;
- clear duplicate active scheduling anchors;
- validate that candidate-scoped null-requisition applications do not explode due to noisy passive flows.

## Assumptions
- `applications` and `application_events` tables from `RS-RFC-007` are available before Phase B implementation work starts.
- Browser fallback, MAX and SMS remain target-state contexts, not current runtime promises.
- Existing legacy audit tables remain available during dual-write and replay.
