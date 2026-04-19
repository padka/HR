# RS-ADR-002: Target Data Model For Candidate, Application, Requisition, Lifecycle, And Event Log

## Status
Proposed

## Date
2026-04-16

## Context

Current candidate storage is centered on `users`, but that row currently mixes multiple business concepts:

- candidate as a person;
- application / response;
- lifecycle state;
- source attribution;
- HH linkage context;
- communication channel linkage;
- final outcome;
- archive state;
- part of recruiter workflow state.

The live code confirms deep coupling around that mixed model:

- `backend/domain/candidates/models.py` stores person data, Telegram/MAX linkage, status, archive, outcome, manual scheduling fields, source, and HH sync fields on `users`.
- `backend/apps/admin_api/webapp/routers.py` still resolves candidate identity by `users.telegram_id`.
- `backend/domain/slot_assignment_service.py` and `backend/domain/candidates/scheduling_integrity.py` still bridge candidate scheduling through `users`, `slots`, and `slot_assignments`.
- `backend/domain/candidates/status_service.py`, `backend/domain/candidates/journey.py`, and `backend/domain/analytics.py` still treat legacy candidate-level status as the operational write path.

This creates structural problems:

- one person cannot be modeled cleanly against multiple vacancies or requisitions;
- funnel reporting is candidate-centric instead of application-centric;
- source conversion is lossy because `users.source` is a single field, not per application;
- dedup and merge are unsafe because channel identity, HH linkage, and lifecycle are collapsed into one row;
- n8n does not have a stable event contract and currently interacts with narrow callback surfaces;
- SLA and next action are derived indirectly instead of from first-class application tasks and events.

## Decision

### 1. Keep `users` as the legacy candidate table in phases A-D

We will not rename `users` to `candidates` in this ADR.

Reason:

- renaming now would create high-risk churn across scheduling, recruiter UI, Telegram webapp, bot flows, HH callbacks, analytics, and tests;
- the current runtime still has broad direct dependencies on `users`, `users.telegram_id`, `users.candidate_status`, and `users.hh_*`;
- the business value comes from separating person/application/lifecycle, not from a table rename.

Decision:

- `users` remains the physical table name for the person record during migration;
- new target tables will reference `users.id` as `candidate_id`;
- after Phase E, we may introduce a logical alias or repository-level rename to `candidates`, but that is explicitly out of scope for this ADR.

### 2. Introduce application-centric operational modeling

The target model separates:

- candidate/person: `users` during migration;
- channel identity: `candidate_channel_identities`;
- demand: `requisitions`;
- candidate participation in demand: `applications`;
- auditable lifecycle changes and side effects: `application_events`;
- interview execution: `interviews`;
- recruiter next action and SLA: `recruiter_tasks`;
- dedup workflow: `dedup_candidate_pairs`;
- AI recommendation audit: `ai_decision_records`.

### 3. Keep existing runtime write owners during early phases

Until Phases B-C:

- `slot_assignments` and `slots` remain the source of truth for scheduling writes;
- `users.candidate_status` remains the compatibility write surface for existing flows;
- `analytics_events` remains raw telemetry;
- `candidate_journey_events`, `message_logs`, `notification_logs`, `hh_sync_log`, and HH integration tables remain valid audit sidecars.

The new model is additive first, then becomes the primary read model, then the primary write model.

### 4. Standardize on an append-only event contract

All future lifecycle, messaging, HH, AI, and n8n orchestration should publish canonical events into `application_events`.

Rules:

- `application_events` is append-only;
- every status transition emits `application.status_changed`;
- terminal domain events such as `application.hired` and `application.rejected` are emitted in addition to, not instead of, the status change;
- external systems use API/webhook contracts with `idempotency_key` and `correlation_id`;
- n8n never writes directly to PostgreSQL.

## Non-Goals

- no production migration is authored in this task;
- no runtime write path is changed in this task;
- no live API contract is broken in this task;
- no table rename from `users` to `candidates` is attempted now;
- no direct dedup merge executor is designed beyond the workflow and data contract.

## Target Domain Model

### Conceptual Boundaries

| Concept | Target owner | Notes |
| --- | --- | --- |
| Person / human identity | `users` during migration | physical table stays `users`; semantic role becomes candidate/person |
| Channel linkage | `candidate_channel_identities` | supports Telegram, HH, MAX, WhatsApp, email, phone, manual |
| Hiring demand | `requisitions` | operational requisition may outlive or reuse a vacancy |
| Reference vacancy | `vacancies` | existing catalog/reference entity remains |
| Candidate participation in a specific demand | `applications` | canonical funnel grain |
| Lifecycle history / side effects | `application_events` | append-only event ledger |
| Interview execution | `interviews` | normalized interview/intro-day record |
| Recruiter next action / SLA | `recruiter_tasks` | explicit work queue instead of implicit status heuristics |
| Dedup workflow | `dedup_candidate_pairs` | review queue, not immediate destructive merge |
| AI decision audit | `ai_decision_records` | ties AI output to human action and resulting event |

### Requisition vs Vacancy

`vacancies` remains the existing reference/job catalog table.

`requisitions` becomes the operational hiring demand entity:

- multiple requisitions may point to one vacancy;
- one requisition carries headcount, owner, SLA, status, and source plan;
- funnel analytics should aggregate by `requisition_id`, not only by `vacancy_id`;
- `applications` point to `requisition_id` first and keep `vacancy_id` only as a transition bridge.

## Target Tables

### `candidate_channel_identities`

Purpose:

- detach channel/external identity from the person row;
- allow one candidate to own multiple linked channels;
- create a stable identity layer for dedup and messaging.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | surrogate key |
| `candidate_id` | FK -> `users.id` | no | person row |
| `channel` | varchar(32) | no | `telegram`, `hh`, `max`, `whatsapp`, `email`, `phone`, `manual` |
| `external_user_id` | varchar(128) | yes | normalized external identifier for the channel |
| `username_or_handle` | varchar(255) | yes | display handle |
| `is_primary` | boolean | no | preferred identity within channel |
| `linked_at` | timestamptz | no | first successful link time |
| `last_seen_at` | timestamptz | yes | last observed activity on that channel |
| `metadata_json` | jsonb | yes | provider-specific payload |

Recommended constraints and indexes:

- index on `(candidate_id, channel)`;
- index on `(channel, external_user_id)`;
- partial unique on `(candidate_id, channel)` where `is_primary = true`;
- do not enforce global unique `(channel, external_user_id)` in Phase A if dirty data exists; validate first, then tighten later.

Notes:

- `users.telegram_id`, `users.telegram_user_id`, `users.telegram_username`, `users.telegram_linked_at`, `users.max_user_id`, and `users.messenger_platform` remain legacy mirrors during Phases A-B;
- for `channel = 'hh'`, `external_user_id` should store only the stable person/resume identity when available; negotiation- and vacancy-specific HH state remains on HH integration tables and/or application metadata.

### `requisitions`

Purpose:

- represent an operational hiring demand that owns applications and SLA.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | surrogate key |
| `vacancy_id` | FK -> `vacancies.id` | yes in migration | target becomes not null once vacancy coverage is complete |
| `city_id` | FK -> `cities.id` | yes in migration | keep nullable until legacy city strings are normalized |
| `title` | varchar(255) | no | requisition title shown to recruiters |
| `headcount` | integer | no | default `1` |
| `priority` | varchar(16) | no | `low`, `normal`, `high`, `urgent` |
| `owner_type` | varchar(32) | no | `recruiter`, `city`, `team`, `system` |
| `owner_id` | integer | yes | polymorphic owner id |
| `status` | varchar(24) | no | `draft`, `open`, `paused`, `closed`, `cancelled` |
| `opened_at` | timestamptz | yes | open timestamp |
| `closed_at` | timestamptz | yes | close timestamp |
| `sla_config_json` | jsonb | yes | due rules, escalation rules |
| `source_plan_json` | jsonb | yes | planned source mix for analytics/ops |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |

Recommended indexes:

- `(status, owner_type, owner_id)`;
- `(vacancy_id, status)`;
- `(city_id, status)`;
- `(opened_at desc)`.

### `applications`

Purpose:

- canonical per-candidate-per-demand funnel record;
- supports one person across multiple requisitions.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | surrogate key |
| `candidate_id` | FK -> `users.id` | no | person row |
| `requisition_id` | FK -> `requisitions.id` | yes in Phases A-B | nullable while legacy candidates are backfilled |
| `vacancy_id` | FK -> `vacancies.id` | yes in Phases A-B | bridge for legacy desired position / HH vacancy linkage |
| `source` | varchar(32) | no | canonical application source |
| `source_detail` | varchar(255) | yes | source subtype, campaign, referral label, import key |
| `recruiter_id` | FK -> `recruiters.id` | yes in migration | current owner |
| `lifecycle_status` | varchar(32) | no | canonical application state machine |
| `lifecycle_reason` | text | yes | reason for current lifecycle state |
| `final_outcome` | varchar(32) | yes | terminal business outcome |
| `final_outcome_reason` | text | yes | free text / controlled code |
| `created_at` | timestamptz | no | creation time |
| `updated_at` | timestamptz | no | update time |
| `archived_at` | timestamptz | yes | soft-close timestamp |

Recommended indexes and constraints:

- `(candidate_id, created_at desc)`;
- `(requisition_id, lifecycle_status)`;
- `(recruiter_id, lifecycle_status)`;
- `(vacancy_id, lifecycle_status)`;
- target partial unique after backfill: one active application per `(candidate_id, requisition_id)`.

Migration note:

- while `requisition_id` is nullable, do not enforce strict uniqueness in the database;
- service logic should maintain at most one open legacy-migrating application per candidate without `requisition_id`.

### `application_events`

Purpose:

- canonical append-only operational ledger for lifecycle, messaging, HH, AI, and integration events.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | internal surrogate key |
| `event_id` | uuid | no | immutable business event id |
| `occurred_at` | timestamptz | no | event time |
| `actor_type` | varchar(16) | no | `system`, `recruiter`, `admin`, `candidate`, `ai`, `n8n`, `hh` |
| `actor_id` | varchar(64) | yes | string to support recruiter/admin/system/external ids without lossy coercion |
| `candidate_id` | FK -> `users.id` | no | candidate anchor |
| `application_id` | FK -> `applications.id` | yes | nullable for candidate-level events during migration |
| `requisition_id` | FK -> `requisitions.id` | yes | nullable for migration |
| `event_type` | varchar(64) | no | canonical noun.verb name |
| `status_from` | varchar(32) | yes | previous status |
| `status_to` | varchar(32) | yes | new status |
| `source` | varchar(32) | yes | source channel / producer |
| `channel` | varchar(32) | yes | messenger or external system channel |
| `idempotency_key` | varchar(128) | yes | external retry guard |
| `correlation_id` | uuid | yes | cross-event workflow trace |
| `metadata_json` | jsonb | yes | event payload |

Recommended indexes and constraints:

- unique on `event_id`;
- unique on `idempotency_key` where not null once producers are namespaced;
- `(application_id, occurred_at desc)`;
- `(candidate_id, occurred_at desc)`;
- `(requisition_id, occurred_at desc)`;
- `(event_type, occurred_at desc)`;
- `(correlation_id)`.

Notes:

- `candidate_journey_events` remains as a legacy portal/journey log until migrated;
- `message_logs`, `notification_logs`, and `hh_sync_log` remain specialized audit tables during migration, but should also emit matching `application_events`.

### `interviews`

Purpose:

- normalized execution record for phone screens, interviews, intro days, and related outcomes.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | surrogate key |
| `application_id` | FK -> `applications.id` | no | owner application |
| `slot_assignment_id` | FK -> `slot_assignments.id` | yes | bridge to current scheduling model |
| `kind` | varchar(24) | no | `phone_screen`, `interview`, `intro_day`, `other` |
| `status` | varchar(24) | no | `scheduled`, `confirmed`, `completed`, `cancelled`, `no_show` |
| `scheduled_at` | timestamptz | yes | planned time |
| `started_at` | timestamptz | yes | actual start |
| `completed_at` | timestamptz | yes | actual completion |
| `no_show_at` | timestamptz | yes | no-show time |
| `result` | varchar(32) | yes | pass/fail/hold/etc |
| `result_reason` | text | yes | controlled reason or free text |
| `interviewer_id` | FK -> `recruiters.id` | yes | owner |
| `feedback_json` | jsonb | yes | structured evaluation |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |

Recommended indexes:

- `(application_id, status)`;
- `(slot_assignment_id)`;
- `(scheduled_at)`.

### `recruiter_tasks`

Purpose:

- first-class next action and SLA tracking for recruiters and automation.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | surrogate key |
| `application_id` | FK -> `applications.id` | yes | nullable for candidate-level tasks |
| `candidate_id` | FK -> `users.id` | no | candidate anchor |
| `owner_recruiter_id` | FK -> `recruiters.id` | no | assignee |
| `task_type` | varchar(64) | no | contact, qualify, schedule, confirm, follow_up, merge_review, etc |
| `status` | varchar(24) | no | `open`, `in_progress`, `resolved`, `cancelled` |
| `due_at` | timestamptz | yes | task SLA due time |
| `sla_breached_at` | timestamptz | yes | breach marker |
| `origin_event_id` | uuid | yes | references `application_events.event_id` |
| `payload_json` | jsonb | yes | structured task context |
| `created_at` | timestamptz | no | created timestamp |
| `resolved_at` | timestamptz | yes | resolution timestamp |

Recommended indexes and constraints:

- `(owner_recruiter_id, status, due_at)`;
- `(application_id, status)`;
- `(candidate_id, status)`;
- target partial unique on `(application_id, task_type)` for open tasks once behavior is stable.

### `dedup_candidate_pairs`

Purpose:

- queue suspected duplicates for review before merge.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | surrogate key |
| `candidate_a_id` | FK -> `users.id` | no | lower id in normalized pair |
| `candidate_b_id` | FK -> `users.id` | no | higher id in normalized pair |
| `match_score` | numeric(5,4) | no | confidence score |
| `match_reasons_json` | jsonb | yes | reasons and evidence |
| `status` | varchar(16) | no | `pending`, `merged`, `dismissed` |
| `decided_by` | varchar(64) | yes | principal descriptor such as `admin:7` or `recruiter:42` |
| `decided_at` | timestamptz | yes | decision time |
| `created_at` | timestamptz | no | created timestamp |

Recommended constraints:

- check `candidate_a_id < candidate_b_id`;
- unique on `(candidate_a_id, candidate_b_id)`;
- `(status, created_at desc)`.

### `ai_decision_records`

Purpose:

- keep AI recommendation output separate from the resulting human decision and emitted event.

Columns:

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | surrogate key |
| `ai_request_log_id` | FK -> `ai_request_logs.id` | yes | existing AI request audit |
| `ai_output_id` | FK -> `ai_outputs.id` | yes | cached model output |
| `candidate_id` | FK -> `users.id` | no | candidate anchor |
| `application_id` | FK -> `applications.id` | yes | application scope |
| `kind` | varchar(64) | no | summary, recommendation, next_action, risk_flag, etc |
| `recommendation_json` | jsonb | no | model output snapshot |
| `human_action` | varchar(16) | no | `accepted`, `edited`, `rejected`, `ignored` |
| `final_action_event_id` | uuid | yes | references `application_events.event_id` |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |

Recommended indexes:

- `(candidate_id, created_at desc)`;
- `(application_id, kind, created_at desc)`;
- `(human_action, created_at desc)`.

## Field Ownership: What Stays In `users` vs What Moves

### Fields that stay in `users` long-term

These remain person-centric:

- `id`
- `candidate_id`
- `fio`
- `phone`
- `phone_normalized`
- `city` until a separate normalized candidate-location model exists
- `conversation_mode`
- `conversation_mode_expires_at`
- `last_activity`
- `is_active`

### Fields that stay in `users` temporarily as legacy compatibility

These remain during Phases A-D but should stop being canonical:

- `candidate_status`
- `workflow_status`
- `rejection_stage`
- `rejection_reason`
- `rejected_at`
- `rejected_by`
- `lifecycle_state`
- `archive_stage`
- `archive_reason`
- `archived_at`
- `final_outcome`
- `final_outcome_reason`
- `manual_slot_from`
- `manual_slot_to`
- `manual_slot_comment`
- `manual_slot_timezone`
- `manual_slot_requested_at`
- `manual_slot_response_at`
- `intro_decline_reason`
- `source`
- `desired_position`
- `responsible_recruiter_id`
- `telegram_id`
- `telegram_user_id`
- `telegram_username`
- `telegram_linked_at`
- `messenger_platform`
- `max_user_id`
- `hh_resume_id`
- `hh_negotiation_id`
- `hh_vacancy_id`
- `hh_synced_at`
- `hh_sync_status`
- `hh_sync_error`

### Fields that become canonical in `applications`

The new canonical owners are:

| Legacy field / concept | New canonical owner |
| --- | --- |
| `users.source` | `applications.source`, `applications.source_detail` |
| `users.desired_position` | `requisitions.title` and `applications.vacancy_id` bridge |
| `users.responsible_recruiter_id` | `applications.recruiter_id` and `requisitions.owner_*` |
| `users.candidate_status` | `applications.lifecycle_status` |
| `users.rejection_reason` | `applications.lifecycle_reason` or `applications.final_outcome_reason` |
| `users.final_outcome` | `applications.final_outcome` |
| `users.final_outcome_reason` | `applications.final_outcome_reason` |
| archive semantics | `applications.archived_at` plus archive events |

### Fields that move to `candidate_channel_identities`

The canonical identity layer becomes:

- Telegram linkage from `users.telegram_*`;
- MAX linkage from `users.max_user_id` and `users.messenger_platform`;
- future email/phone/WhatsApp identities;
- optional coarse HH person identity.

### Fields that become events instead of mutable columns

The canonical audit history becomes `application_events` for:

- lifecycle transitions;
- assignment / owner changes;
- source attribution updates;
- message sent / delivered / failed / received;
- HH sync request / completion;
- AI recommendation generation and acceptance;
- task creation / resolution;
- dedup suspicion and merge actions.

## Backward Compatibility Strategy

### Database compatibility

- `users` remains untouched as the physical table name.
- `slots`, `slot_assignments`, `outbox_notifications`, `message_logs`, `candidate_journey_events`, HH tables, and `analytics_events` remain valid until later phases.
- New tables are additive only in Phase A.

### Runtime compatibility

- existing admin UI, admin API, bot, and Telegram webapp keep reading and writing legacy fields at first;
- new tables are initially populated only by migration/backfill and then by write-through dual write;
- no existing endpoint is removed before Phase D.

### Compatibility projection

During Phases B-C, recruiter UI should read a compatibility projection:

- primary candidate/person from `users`;
- primary active application from `applications`;
- canonical lifecycle and next action derived from `applications` and `application_events`;
- scheduling summary still bridged from `slot_assignments` until `interviews` becomes authoritative.

That aligns with the current additive direction already visible in `docs/architecture/candidate-state-contract.md`.

## Canonical Lifecycle State Machine

Status semantics:

- the lifecycle belongs to `applications`, not to `users`;
- every transition emits `application.status_changed`;
- specialized domain events may be emitted in addition to the generic transition event;
- side effects are executed by application services and recorded as events/tasks, not inferred only from mutable columns.

| Status | Allowed previous statuses | Allowed next statuses | Typical actor | Required fields | Event emitted | Side effects |
| --- | --- | --- | --- | --- | --- | --- |
| `new` | none | `contact_pending`, `archived` | `system`, `recruiter`, `hh`, `n8n` | `candidate_id`, `source`, `created_at` | `application.created` | create default open follow-up task if human contact is required |
| `contact_pending` | `new`, `archived` via explicit reopen | `contacted`, `qualification_pending`, `rejected`, `archived` | `recruiter`, `system` | `recruiter_id` or owner resolution | `application.status_changed` | create/update contact SLA task |
| `contacted` | `contact_pending`, `new` | `qualification_pending`, `rejected`, `archived` | `recruiter`, `system`, `candidate` | at least one contact attempt in event metadata | `application.status_changed` | close initial contact task, open qualification task |
| `qualification_pending` | `contact_pending`, `contacted` | `qualified`, `not_qualified`, `rejected`, `archived` | `recruiter`, `candidate` | screening context or note in metadata | `application.status_changed` | due task for qualification decision |
| `qualified` | `qualification_pending` | `interview_scheduling`, `archived` | `recruiter`, `admin` | qualification reason or scorecard | `application.status_changed` | create scheduling task |
| `not_qualified` | `qualification_pending` | `archived`, `qualification_pending` via explicit reopen | `recruiter`, `admin` | `lifecycle_reason` | `application.status_changed` | close active work tasks, keep candidate merge-safe for future reopen |
| `interview_scheduling` | `qualified`, `no_show` | `interview_scheduled`, `rejected`, `archived` | `recruiter`, `system` | owner and scheduling intent | `application.status_changed` | open scheduling task, maybe create interview draft |
| `interview_scheduled` | `interview_scheduling` | `interview_confirmed`, `interview_completed`, `no_show`, `rejected`, `archived` | `recruiter`, `system`, `hh` | linked `interviews` row with `scheduled_at` or bridge to `slot_assignment_id` | `interview.scheduled` and `application.status_changed` | enqueue invite/reminder messages |
| `interview_confirmed` | `interview_scheduled` | `interview_completed`, `no_show`, `rejected`, `archived` | `candidate`, `recruiter`, `system` | scheduled interview exists and confirmation timestamp in metadata | `interview.confirmed` and `application.status_changed` | close confirmation task, update reminder plan |
| `interview_completed` | `interview_scheduled`, `interview_confirmed` | `intro_day_scheduled`, `offer_pending`, `rejected`, `archived` | `recruiter`, `system` | completed interview result and `completed_at` | `interview.completed` and `application.status_changed` | create next-step task, optionally trigger AI summary |
| `no_show` | `interview_scheduled`, `interview_confirmed`, `intro_day_scheduled` | `interview_scheduling`, `rejected`, `archived` | `system`, `recruiter` | linked interview and `no_show_at` | `interview.no_show` and `application.status_changed` | create recovery or rejection task, mark SLA breach if needed |
| `intro_day_scheduled` | `interview_completed` | `intro_day_completed`, `no_show`, `rejected`, `archived` | `recruiter`, `system` | `interviews.kind = intro_day`, `scheduled_at` | `interview.scheduled` and `application.status_changed` | enqueue intro-day communication |
| `intro_day_completed` | `intro_day_scheduled` | `offer_pending`, `hired`, `rejected`, `archived` | `recruiter`, `system` | completed intro-day result | `interview.completed` and `application.status_changed` | create final-decision task |
| `offer_pending` | `interview_completed`, `intro_day_completed` | `hired`, `rejected`, `archived` | `recruiter`, `admin` | owner, pending decision context | `application.status_changed` | SLA timer for final decision |
| `hired` | `offer_pending`, `intro_day_completed` | `archived` | `recruiter`, `admin`, `hh` | `final_outcome = hired`, decision timestamp | `application.hired` and `application.status_changed` | close tasks, emit analytics conversion, trigger HH sync if linked |
| `rejected` | `contact_pending`, `contacted`, `qualification_pending`, `qualified`, `interview_scheduling`, `interview_scheduled`, `interview_confirmed`, `interview_completed`, `no_show`, `intro_day_scheduled`, `intro_day_completed`, `offer_pending` | `archived` | `recruiter`, `admin`, `system`, `hh` | rejection reason code/text | `application.rejected` and `application.status_changed` | close active tasks, optionally send rejection notification |
| `archived` | `new`, `contact_pending`, `contacted`, `qualification_pending`, `not_qualified`, `no_show`, `rejected`, `hired`, `offer_pending`, `intro_day_completed` | none in v1; reopen becomes explicit future flow | `recruiter`, `admin`, `system` | `archived_at`, archive reason | `application.status_changed` | remove from active queues, keep full audit history |

Notes:

- `rejected` is a final business decision; `not_qualified` is an earlier screening result and may still be reopened intentionally.
- `archived` is a record-state, not a business success/failure outcome.
- `no_show` is intentionally non-terminal to allow controlled recovery or rescheduling.

## Canonical Event Taxonomy

### Naming rules

- use `noun.verb` format;
- use singular entity names;
- keep event names stable even if producer implementation changes;
- every event is stored in `application_events` even when a specialized table also exists.

### Canonical names

| Domain | Event names |
| --- | --- |
| Candidate | `candidate.created`, `candidate.updated`, `candidate.channel_identity.linked`, `candidate.duplicate_suspected`, `candidate.merged` |
| Application | `application.created`, `application.owner_assigned`, `application.status_changed`, `application.rejected`, `application.hired` |
| Messaging | `message.sent`, `message.delivered`, `message.failed`, `message.received` |
| Interview | `interview.scheduled`, `interview.confirmed`, `interview.rescheduled`, `interview.completed`, `interview.no_show` |
| Recruiter task | `recruiter_task.created`, `recruiter_task.resolved`, `recruiter_task.sla_breached` |
| AI | `ai.summary.generated`, `ai.recommendation.generated`, `ai.recommendation.accepted`, `ai.recommendation.edited`, `ai.recommendation.rejected` |
| HH | `hh.negotiation.imported`, `hh.status_sync.requested`, `hh.status_sync.completed` |
| n8n | `n8n.workflow.triggered`, `n8n.workflow.completed`, `n8n.workflow.failed` |

### Event emission rules

- `application.status_changed` is always emitted for lifecycle transitions;
- `application.rejected` and `application.hired` are emitted together with the terminal status change;
- `message.*` does not require a lifecycle transition;
- `recruiter_task.sla_breached` must not mutate lifecycle by itself; it only records the breach and may create a follow-up task/event;
- `n8n.workflow.*` tracks orchestration only and must not replace the underlying business event.

## n8n Contract

### Envelope

The canonical envelope is:

```json
{
  "schema_version": "2026-04-16.v1",
  "event_id": "uuid",
  "correlation_id": "uuid",
  "idempotency_key": "string",
  "event_type": "application.status_changed",
  "occurred_at": "datetime",
  "actor": {
    "type": "system|recruiter|admin|candidate|ai|hh|n8n",
    "id": "string|null"
  },
  "candidate_id": 123,
  "application_id": 456,
  "requisition_id": 789,
  "payload": {}
}
```

Decision:

- this extends the draft actor enum with `admin` because current runtime already distinguishes admin actions and dropping that actor would make audit lossy;
- `application_id` and `requisition_id` may be null during early migration phases, but `candidate_id`, `event_id`, `event_type`, `occurred_at`, `correlation_id`, and `idempotency_key` remain required.

### Contract rules

- n8n must never connect directly to PostgreSQL;
- n8n must only receive events through signed webhooks or poll API endpoints;
- n8n callbacks must call API/webhook endpoints with `idempotency_key` and `correlation_id`;
- application code owns validation, authorization, deduplication, persistence, retries, and business side effects;
- every accepted n8n callback writes an `application_events` row.

### Suggested API shape for future orchestration

- outbound from app to n8n: signed webhook with the canonical envelope;
- inbound from n8n to app: `POST /api/integrations/events` or domain-specific action endpoints that require the same envelope headers/fields;
- callbacks should return the persisted `event_id`, acceptance status, and duplicate marker when idempotency hits an existing event.

## Migration Strategy

### Phase A: Additive tables only

Scope:

- create `candidate_channel_identities`, `requisitions`, `applications`, `application_events`, `interviews`, `recruiter_tasks`, `dedup_candidate_pairs`, `ai_decision_records`;
- keep `users`, scheduling tables, HH tables, analytics tables, and all legacy APIs unchanged;
- backfill is optional and offline-safe, but no runtime flow depends on new tables yet.

Expected outputs:

- schema exists;
- read-only exploration queries and admin/debug tooling can inspect the new model;
- no production behavior change.

### Phase B: Write-through dual write

Scope:

- every legacy status mutation also resolves or creates the current primary `application`;
- lifecycle transitions dual-write to `applications` and `application_events`;
- channel link updates dual-write to `candidate_channel_identities`;
- HH callbacks, AI recommendation acceptance, and message outcomes emit canonical application events;
- scheduling remains authoritative in `slot_assignments`, but interview scheduling/completion also creates or updates `interviews`.

Rules:

- legacy writes still happen;
- new writes must be idempotent;
- no status change is considered complete unless the event write succeeds or the transaction rolls back.

### Phase C: Read migration

Scope:

- dashboards, candidate lists, kanban, candidate detail, and analytics read from `applications` plus `application_events`;
- compatibility payloads still include legacy fields, but new application-centric payloads become primary;
- derived SLA and next action move to `recruiter_tasks`.

Cutover target:

- recruiter surfaces read lifecycle from `applications.lifecycle_status`;
- event timeline reads from `application_events`;
- scheduling summary still bridges from `slot_assignments` until `interviews` is fully authoritative.

### Phase D: Deprecate legacy status fields

Scope:

- stop writing `users.candidate_status`, `users.workflow_status`, `users.lifecycle_state`, `users.archive_*`, and `users.final_outcome*` as canonical sources;
- mark legacy DTO fields as deprecated;
- keep read-only compatibility projection for a defined sunset period.

### Phase E: Cleanup

Scope:

- delete or freeze legacy write paths;
- remove compatibility-only status columns from active runtime decisions;
- tighten constraints on requisitions/applications/channel identities;
- optionally introduce a logical `candidates` alias or repository rename after all dependencies are retired.

## API Migration Plan

### Existing APIs that continue to work

These remain supported through Phases A-C:

- `GET /api/candidates`
- `GET /api/candidates/{id}`
- existing recruiter action endpoints and kanban move endpoints
- `admin_api` Telegram webapp endpoints under `/api/webapp/*`
- existing HH callback endpoints under `/api/hh-sync/*`

### New APIs to add

Suggested additive resources:

- `GET /api/candidates/{candidate_id}/applications`
- `GET /api/applications/{application_id}`
- `POST /api/applications`
- `POST /api/applications/{application_id}/status-transitions`
- `GET /api/applications/{application_id}/events`
- `GET /api/requisitions`
- `POST /api/requisitions`
- `GET /api/candidates/{candidate_id}/channel-identities`
- `POST /api/candidates/{candidate_id}/channel-identities`
- `GET /api/recruiter-tasks`
- `POST /api/candidates/merge`

### DTOs to mark deprecated

Once application-centric endpoints exist, mark these as deprecated compatibility fields:

- `candidate_status_slug`
- `workflow_status`
- `journey`
- `archive`
- `final_outcome`
- `final_outcome_reason`
- `source` on candidate detail/list payloads as the primary funnel source
- `hh_resume_id`, `hh_negotiation_id`, `hh_vacancy_id` on generic candidate payloads

Fields that remain temporarily but should move later:

- `telegram_id`
- `telegram_username`
- `messenger_platform`
- `responsible_recruiter_id`
- `desired_position`

### Compatibility payload shape

During Phases B-C, candidate detail/list responses should add:

- `applications` or `primary_application`;
- `channel_identities`;
- `requisition_summary`;
- `legacy_status` or `legacy_candidate_state` block for consumers that still need old fields.

## UI Migration Plan

### First screens to migrate

1. Dashboard / incoming / kanban
2. Candidate detail page
3. Scheduling and slot-related recruiter screens
4. Detailization and analytics screens
5. HH system/admin surfaces
6. Telegram webapp and bot-facing candidate journey screens

Rationale:

- dashboard/incoming/kanban and candidate detail already consume additive backend state contracts;
- these screens benefit immediately from `primary_application`, requisition context, and event timeline;
- Telegram webapp and slot scheduling are higher-risk and should move after the application layer is stable.

### UI behavior target

- recruiter list cards become candidate-person cards with one or more application badges;
- candidate detail becomes split-pane:
  - person profile;
  - active/past applications;
  - event timeline;
  - tasks / SLA;
  - channel identities;
- scheduling widgets bind to `interviews` plus `slot_assignment` bridge;
- merge review becomes an explicit dedup workflow, not an ad-hoc overwrite.

## Analytics Migration Plan

### Current state

- `analytics_events` is raw telemetry without full relational ownership;
- funnel events are still emitted from candidate-level status changes and webapp booking actions;
- some reporting still relies on `users.final_outcome` and related derived fields.

### Target state

- canonical funnel grain becomes `application_id`;
- requisition conversion uses `requisition_id`;
- source conversion uses `applications.source` and `applications.source_detail`;
- SLA metrics use `recruiter_tasks`;
- timeline and operational audit use `application_events`.

### Migration steps

1. Keep `analytics_events` as raw telemetry.
2. Dual-write business events into `application_events`.
3. Build analytics marts or SQL views from `applications` and `application_events`.
4. Migrate dashboards one metric family at a time:
   - active pipeline counts
   - source conversion
   - stage-to-stage conversion
   - recruiter SLA / next action
   - hire / reject / no-show outcomes
5. Retire candidate-level funnel derivation once parity is proven.

### Double-count prevention

- define one canonical metric source per dashboard tile before cutover;
- during transition, expose a source-of-truth flag in analytics queries;
- do not aggregate legacy candidate funnel counts and application-event counts in the same chart without an explicit compatibility view.

## Risk Register

| Risk | Why it matters | Mitigation | Rollback / containment |
| --- | --- | --- | --- |
| Break scheduling | current scheduling still spans `users`, `slots`, `slot_assignments`, and Telegram flows | keep scheduling write ownership unchanged until after application dual-write is proven; bridge `interviews.slot_assignment_id` first | disable new read model for scheduling and keep `slot_assignments` as sole source |
| Break Telegram webapp | webapp still resolves candidate by `users.telegram_id` and slot-only legacy flows | do not move Telegram webapp to application ownership before recruiter UI cutover; keep `users.telegram_*` mirrors until final phase | keep webapp on legacy candidate lookup and slot APIs |
| Wrong candidate merge | dedup/merge can corrupt multi-application history if executed too early | make dedup review explicit via `dedup_candidate_pairs`; do not auto-merge by background job in v1 | freeze merge action, keep only suspected pairs and manual review |
| Double analytics | legacy candidate funnel and new application funnel can both count the same business step | dual-write with explicit metric ownership and staged dashboard cutover | switch dashboards back to legacy queries while retaining application event ledger |
| Migration rollback complexity | dual write can leave partial data if not transactional | keep writes transactional; event insert failure rolls back the business mutation in new paths; Phase A is additive only | stop reading new tables and continue on legacy state until repaired |

## Why This Approach

This is the smallest safe path because it:

- solves the core modeling problem without renaming `users` up front;
- keeps current scheduling and Telegram flows stable while the new application layer is introduced;
- gives analytics and n8n a clean event contract before any destructive cleanup;
- supports one candidate across multiple requisitions without a big-bang rewrite.

## Consequences

### Positive

- person identity, application lifecycle, requisition demand, and event audit become separate concerns;
- per-requisition funnel analytics becomes possible;
- source attribution becomes application-specific;
- dedup and merge become reviewable and auditable;
- n8n gets a stable event envelope instead of narrow ad-hoc callbacks;
- SLA and next action become first-class data.

### Tradeoffs

- short-term dual-write complexity;
- temporary coexistence of legacy and target models;
- more tables and more explicit service orchestration;
- a later cleanup phase is mandatory to avoid permanent double truth.

## Proposed Implementation Backlog

1. Schema RFC review for the eight additive tables and target indexes.
2. Migration design doc for Phase A additive schema and non-destructive backfill plan.
3. Application resolution strategy for Phase B dual-write: how legacy candidate writes locate/create the primary application.
4. Event publisher abstraction that writes `application_events` transactionally with idempotency.
5. Channel identity mirror plan from `users.telegram_*` / `users.max_user_id` into `candidate_channel_identities`.
6. Requisition bootstrap plan from current `vacancies`, `desired_position`, `city`, and recruiter ownership.
7. Recruiter read-model projector for `primary_application`, event timeline, and task/SLA summary.
8. Scheduling bridge design from `slot_assignments` to `interviews`.
9. Analytics parity plan and dashboard-by-dashboard cutover map.
10. Dedup review workflow spec and merge safety guardrails.
11. n8n webhook/API contract spec with request signing, idempotency handling, and callback semantics.
12. Legacy field deprecation checklist and removal gates for Phases D-E.

## Assumptions

- `users` continues to be the physical candidate/person table through at least Phase D.
- `vacancies` remains a reference catalog, while `requisitions` becomes the operational demand entity.
- scheduling migration must stay behind the current `slot_assignments` boundary until application reads are stable.
- actor ids in `application_events` are stored as strings to avoid losing current mixed principal/external actor identity.
- `admin` is added to the n8n actor envelope even though the initial draft omitted it, because current runtime already uses admin-owned actions and audit needs that distinction.
