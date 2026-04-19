# RS-RFC-007: Phase A Schema And API Contract Pack

## Status
Proposed

## Date
2026-04-16

## Companion Docs
- [RS-ADR-002: Target Data Model For Candidate, Application, Requisition, Lifecycle, And Event Log](../adr/rs-adr-002-application-requisition-lifecycle-event-log.md)
- [RS-ADR-004: Candidate Access And Journey Surfaces For Browser / Telegram / MAX / SMS](../adr/rs-adr-004-candidate-access-and-journey-surfaces.md)
- [RS-ADR-005: Messaging Delivery Model And Channel Routing For Telegram / MAX / SMS](../adr/rs-adr-005-messaging-delivery-model-and-channel-routing.md)
- [docs/data/data-dictionary.md](../../data/data-dictionary.md)
- [docs/data/erd.md](../../data/erd.md)
- [docs/security/trust-boundaries.md](../../security/trust-boundaries.md)
- [docs/security/auth-and-token-model.md](../../security/auth-and-token-model.md)
- [docs/architecture/supported_channels.md](../supported_channels.md)

## Scope Note
Этот документ фиксирует implementable schema proposal и additive API contract pack для будущего `Phase A` implementation.

Document intent:

- задать decision-complete schema RFC для additive foundation tables;
- задать additive API contract pack без изменения существующих API;
- зафиксировать phased constraint hardening и backfill boundaries;
- не писать migration code;
- не менять runtime;
- не обещать production rollout браузерного candidate surface, MAX или SMS в рамках этого документа.

## Current Runtime And Boundary Baseline

Current live runtime, который нельзя противоречить:

- Telegram bot runtime остаётся единственным supported live messaging runtime;
- Telegram Mini App / recruiter webapp уже существует на `admin_api`;
- MAX bot runtime сейчас unsupported / disabled by default;
- browser candidate portal сейчас deliberately disabled;
- SMS/OTP transport не реализован как live runtime surface;
- `admin_ui` остаётся authenticated admin/recruiter boundary с session/CSRF;
- `admin_api` уже обслуживает external-ish surfaces и callbacks, но candidate boundary не должен быть впаян в текущий `/api/webapp/*`.

This RFC therefore defines:

- target Phase A schema;
- additive APIs and contracts;
- no-cutover compatibility strategy;
- explicit non-goals for runtime.

## Normative Decisions

1. `users` остаётся legacy person table и не переименовывается в рамках Phase A.
2. `applications`, `requisitions`, `application_events`, `interviews`, `recruiter_tasks`, `dedup_candidate_pairs`, `ai_decision_records` вводятся как additive target tables, а не как retrofit существующего runtime ownership.
3. `candidate_journey_sessions` остаётся progress-only table и не становится access/session store.
4. `candidate_access_tokens` и `candidate_access_sessions` вводятся как отдельный access/auth layer поверх journey progress.
5. Messaging truth режется как `message_threads -> messages -> message_deliveries -> provider_receipts`.
6. `candidate_contact_policies` и `channel_health_registry` не смешиваются с identity layer и не дублируют history tables.
7. Candidate launch/journey API не переиспользует `/api/webapp/*` и не возрождает `/candidate*` namespace.
8. `n8n` идёт только через backend APIs и не пишет напрямую в PostgreSQL.

## Design Principles

- additive-first, no runtime cutover in Phase A;
- stable grain separation: person, application, access session, thread, delivery attempt, receipt;
- no hidden ownership transfer from legacy `users`, `slots`, `slot_assignments`, `chat_messages`, `outbox_notifications`;
- candidate journey is shared across browser, Telegram, MAX and future SMS/browser-link launch surfaces;
- browser fallback is a required target state, but not a current runtime promise;
- MAX and SMS are target integration surfaces, not present-tense supported runtime promises;
- JSON fields are used only for variable-shaped payloads, snapshots, and provider/shell-specific context;
- scalar business identity, status, timestamps, and foreign keys stay typed.

## Section 1. Table-By-Table Schema Proposal

### 1. `candidate_channel_identities`

**Purpose**

- отделить candidate identity от legacy `users.telegram_*`, `users.max_user_id`, `users.hh_*`;
- дать единый identity layer для Telegram / MAX / HH / phone / email / manual;
- использовать этот слой как canonical bridge для messaging routing, reachability и dedup review.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `candidate_id` | int FK -> `users.id` | no | person anchor |
| `channel` | varchar(32) | no | `telegram`, `max`, `phone`, `email`, `hh`, `manual` |
| `external_user_id` | varchar(128) | yes | stable provider/user identifier |
| `username_or_handle` | varchar(255) | yes | display handle |
| `is_primary` | boolean | no | preferred identity within channel |
| `linked_at` | timestamptz | no | first known successful link time |
| `last_seen_at` | timestamptz | yes | last observed activity |
| `verification_status` | varchar(24) | yes | `verified`, `unverified`, `assumed`, `revoked` |
| `reachability_status` | varchar(24) | yes | `reachable`, `unreachable`, `degraded`, `unknown` |
| `delivery_health` | varchar(24) | yes | `healthy`, `watch`, `poor`, `blocked` |
| `last_successful_delivery_at` | timestamptz | yes | latest confirmed success |
| `last_failed_delivery_at` | timestamptz | yes | latest fail |
| `last_hard_fail_code` | varchar(64) | yes | normalized failure code |
| `consent_status` | varchar(24) | yes | channel-specific override if needed |
| `serviceability_status` | varchar(24) | yes | region/provider/channel usability |
| `cooldown_until` | timestamptz | yes | anti-spam or recovery cooldown |
| `metadata_json` | jsonb | yes | provider-specific identity snapshot |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |

**PK**

- `id`

**FK**

- `candidate_id -> users.id`

**Indexes**

- `(candidate_id, channel)`
- `(channel, external_user_id)`
- `(candidate_id, delivery_health, updated_at desc)`
- `(candidate_id, reachability_status, updated_at desc)`

**Uniqueness**

- partial unique `(candidate_id, channel)` where `is_primary = true`
- do not enforce global unique `(channel, external_user_id)` in Phase A

**Retention Notes**

- long-lived identity/audit table
- rows should survive channel unlink, revocation, or degraded periods
- prefer state transitions over deletes

**PII Notes**

- high PII / identity sensitivity
- contains provider identifiers, handles, possible phone/email IDs
- logs and exports must redact `external_user_id` and provider payload fragments where not strictly necessary

**Recommended JSON Fields And Why**

- `metadata_json` because provider identity payload shape varies across Telegram, MAX, HH, phone enrichment, and future providers
- do not move typed lifecycle or consent status into JSON

**Phase A No-Hard-Constraints**

- no global unique on `(channel, external_user_id)`
- no mandatory `verification_status` or `reachability_status`
- no assumption that each candidate already has a canonical primary row for every linked channel

### 2. `requisitions`

**Purpose**

- represent operational hiring demand as a first-class object;
- break the implicit coupling between candidate row and demand ownership;
- support headcount, SLA and owner semantics separate from `vacancies`.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `vacancy_id` | int FK -> `vacancies.id` | yes | nullable in Phase A |
| `city_id` | int FK -> `cities.id` | yes | nullable in Phase A |
| `title` | varchar(255) | no | recruiter-visible title |
| `headcount` | integer | no | default `1` |
| `priority` | varchar(16) | no | `low`, `normal`, `high`, `urgent` |
| `owner_type` | varchar(32) | no | `recruiter`, `city`, `team`, `system` |
| `owner_id` | integer | yes | polymorphic owner id |
| `status` | varchar(24) | no | `draft`, `open`, `paused`, `closed`, `cancelled` |
| `opened_at` | timestamptz | yes | open time |
| `closed_at` | timestamptz | yes | close time |
| `sla_config_json` | jsonb | yes | SLA and escalation rules |
| `source_plan_json` | jsonb | yes | source mix planning |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |

**PK**

- `id`

**FK**

- `vacancy_id -> vacancies.id`
- `city_id -> cities.id`

**Indexes**

- `(status, owner_type, owner_id)`
- `(vacancy_id, status)`
- `(city_id, status)`
- `(opened_at desc)`

**Uniqueness**

- no business unique beyond PK in Phase A

**Retention Notes**

- keep closed and cancelled requisitions for reporting and audit
- do not soft-delete in Phase A

**PII Notes**

- low direct PII
- can still reveal organizational staffing and sourcing plans

**Recommended JSON Fields And Why**

- `sla_config_json` because escalation rules and timers vary by requisition/team/city
- `source_plan_json` because source mix planning is sparse and likely to evolve

**Phase A No-Hard-Constraints**

- do not require `vacancy_id`
- do not require `city_id`
- do not require `owner_id`
- do not assume 1:1 mapping between legacy vacancy and requisition

### 3. `applications`

**Purpose**

- move funnel grain from candidate-level row to per-candidate-per-demand record;
- support one person across multiple requisitions;
- become canonical home for application lifecycle and ownership.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `candidate_id` | int FK -> `users.id` | no | person anchor |
| `requisition_id` | bigint FK -> `requisitions.id` | yes | nullable in Phase A |
| `vacancy_id` | int FK -> `vacancies.id` | yes | bridge to legacy vacancy references |
| `source` | varchar(32) | no | canonical application source |
| `source_detail` | varchar(255) | yes | campaign/import/referral detail |
| `recruiter_id` | int FK -> `recruiters.id` | yes | current owner |
| `lifecycle_status` | varchar(32) | no | canonical state machine |
| `lifecycle_reason` | text | yes | explanatory reason |
| `final_outcome` | varchar(32) | yes | terminal business outcome |
| `final_outcome_reason` | text | yes | explanatory reason |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |
| `archived_at` | timestamptz | yes | closed/archive timestamp |

**PK**

- `id`

**FK**

- `candidate_id -> users.id`
- `requisition_id -> requisitions.id`
- `vacancy_id -> vacancies.id`
- `recruiter_id -> recruiters.id`

**Indexes**

- `(candidate_id, created_at desc)`
- `(requisition_id, lifecycle_status)`
- `(recruiter_id, lifecycle_status)`
- `(vacancy_id, lifecycle_status)`

**Uniqueness**

- no hard active unique in Phase A
- target later: partial unique active `(candidate_id, requisition_id)`

**Retention Notes**

- canonical business history row
- keep archived and terminal outcomes
- no destructive merge behavior in Phase A

**PII Notes**

- very high business sensitivity because it ties person, source, recruiter and outcome

**Recommended JSON Fields And Why**

- none in Phase A
- keep lifecycle and ownership typed
- do not introduce speculative JSON until a stable variable payload is proven necessary

**Phase A No-Hard-Constraints**

- `requisition_id` stays nullable
- `vacancy_id` stays nullable
- do not enforce one-active-application constraint yet

### 4. `application_events`

**Purpose**

- canonical append-only audit/event ledger for lifecycle, access, messaging, HH, AI and operational side effects;
- provide one correlation surface for backend, workers and integrations.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `event_id` | uuid | no | immutable business event id |
| `occurred_at` | timestamptz | no | event time |
| `actor_type` | varchar(16) | no | `system`, `recruiter`, `admin`, `candidate`, `ai`, `n8n`, `hh` |
| `actor_id` | varchar(64) | yes | string id for mixed actor space |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | nullable in Phase A |
| `requisition_id` | bigint FK -> `requisitions.id` | yes | nullable in Phase A |
| `event_type` | varchar(64) | no | canonical event name |
| `status_from` | varchar(32) | yes | previous state |
| `status_to` | varchar(32) | yes | new state |
| `source` | varchar(32) | yes | source producer |
| `channel` | varchar(32) | yes | relevant channel |
| `idempotency_key` | varchar(128) | yes | retry guard |
| `correlation_id` | uuid | yes | end-to-end trace |
| `metadata_json` | jsonb | yes | event payload snapshot |
| `created_at` | timestamptz | no | row creation time |

**PK**

- `id`

**FK**

- `candidate_id -> users.id`
- `application_id -> applications.id`
- `requisition_id -> requisitions.id`

**Indexes**

- unique `(event_id)`
- `(candidate_id, occurred_at desc)`
- `(application_id, occurred_at desc)`
- `(requisition_id, occurred_at desc)`
- `(event_type, occurred_at desc)`
- `(correlation_id)`

**Uniqueness**

- `event_id` unique immediately
- `idempotency_key` not hard-unique in Phase A until producer namespaces are locked

**Retention Notes**

- append-only long-lived audit ledger
- should outlive legacy sidecar logs

**PII Notes**

- very high sensitivity
- `metadata_json` must avoid raw secrets and minimize PII duplication

**Recommended JSON Fields And Why**

- `metadata_json` because event payload shape varies across lifecycle, access, messaging, AI, and external integrations

**Phase A No-Hard-Constraints**

- keep `application_id` nullable
- keep `requisition_id` nullable
- do not hard-unique `idempotency_key` across all producers yet

### 5. `interviews`

**Purpose**

- normalized execution record for phone screen / interview / intro day / no-show outcomes;
- bridge from current slot-centric scheduling model to application-centric operational model.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `application_id` | bigint FK -> `applications.id` | no | owner application |
| `slot_assignment_id` | int FK -> `slot_assignments.id` | yes | legacy scheduling bridge |
| `kind` | varchar(24) | no | `phone_screen`, `interview`, `intro_day`, `other` |
| `status` | varchar(24) | no | `scheduled`, `confirmed`, `completed`, `cancelled`, `no_show` |
| `scheduled_at` | timestamptz | yes | planned time |
| `started_at` | timestamptz | yes | actual start |
| `completed_at` | timestamptz | yes | actual completion |
| `no_show_at` | timestamptz | yes | no-show marker |
| `result` | varchar(32) | yes | pass/fail/hold/etc |
| `result_reason` | text | yes | explanatory reason |
| `interviewer_id` | int FK -> `recruiters.id` | yes | interviewer or owner |
| `feedback_json` | jsonb | yes | structured evaluation |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |

**PK**

- `id`

**FK**

- `application_id -> applications.id`
- `slot_assignment_id -> slot_assignments.id`
- `interviewer_id -> recruiters.id`

**Indexes**

- `(application_id, status)`
- `(slot_assignment_id)`
- `(scheduled_at)`

**Uniqueness**

- no additional unique constraint in Phase A

**Retention Notes**

- retain as part of candidate/application execution history
- do not delete old records after reschedule/no-show

**PII Notes**

- high sensitivity because of interviewer feedback and attendance outcome

**Recommended JSON Fields And Why**

- `feedback_json` because structured scorecards and interview notes can vary by stage, vacancy and future rubric evolution

**Phase A No-Hard-Constraints**

- keep `slot_assignment_id` nullable
- keep `interviewer_id` nullable
- keep `result` and `result_reason` nullable
- do not attempt to replace `slot_assignments` as scheduling truth

### 6. `recruiter_tasks`

**Purpose**

- first-class next action and SLA queue;
- make implicit work visible without relying only on status heuristics.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `application_id` | bigint FK -> `applications.id` | yes | candidate-level tasks remain possible |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `owner_recruiter_id` | int FK -> `recruiters.id` | no | assignee |
| `task_type` | varchar(64) | no | `contact`, `qualify`, `schedule`, `follow_up`, `merge_review`, etc. |
| `status` | varchar(24) | no | `open`, `in_progress`, `resolved`, `cancelled` |
| `due_at` | timestamptz | yes | SLA due time |
| `sla_breached_at` | timestamptz | yes | breach marker |
| `origin_event_id` | uuid | yes | related `application_events.event_id` |
| `payload_json` | jsonb | yes | task context |
| `created_at` | timestamptz | no | created timestamp |
| `resolved_at` | timestamptz | yes | resolution time |

**PK**

- `id`

**FK**

- `application_id -> applications.id`
- `candidate_id -> users.id`
- `owner_recruiter_id -> recruiters.id`

**Indexes**

- `(owner_recruiter_id, status, due_at)`
- `(application_id, status)`
- `(candidate_id, status)`

**Uniqueness**

- no hard open-task uniqueness in Phase A
- target later: partial unique on active `(application_id, task_type)`

**Retention Notes**

- retain resolved tasks for SLA and operational audit

**PII Notes**

- medium-high sensitivity due to candidate context inside payload

**Recommended JSON Fields And Why**

- `payload_json` because task creation context, SLA hints, and merge-review evidence vary by task type

**Phase A No-Hard-Constraints**

- `application_id` stays nullable
- no hard uniqueness on active task types
- no assumption that every legacy implicit task can be backfilled

### 7. `dedup_candidate_pairs`

**Purpose**

- represent suspected duplicates as review queue items;
- enable phased constraint hardening before any destructive merge behavior exists.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `candidate_a_id` | int FK -> `users.id` | no | lower id in normalized pair |
| `candidate_b_id` | int FK -> `users.id` | no | higher id in normalized pair |
| `match_score` | numeric(5,4) | no | confidence score |
| `match_reasons_json` | jsonb | yes | evidence bundle |
| `status` | varchar(16) | no | `pending`, `merged`, `dismissed` |
| `decided_by` | varchar(64) | yes | actor string |
| `decided_at` | timestamptz | yes | decision time |
| `created_at` | timestamptz | no | created timestamp |

**PK**

- `id`

**FK**

- `candidate_a_id -> users.id`
- `candidate_b_id -> users.id`

**Indexes**

- `(status, created_at desc)`

**Uniqueness**

- unique normalised pair `(candidate_a_id, candidate_b_id)`
- check `candidate_a_id < candidate_b_id`

**Retention Notes**

- keep dismissed and merged review history
- no destructive cleanup in Phase A

**PII Notes**

- very high sensitivity because duplicate suspicion is itself sensitive operational data

**Recommended JSON Fields And Why**

- `match_reasons_json` because evidence bundle can contain heterogeneous match signals: phone, Telegram, MAX, HH, content hash, manual notes

**Phase A No-Hard-Constraints**

- no auto-merge behavior
- no hard cascading cleanup of related identities, messages or sessions

### 8. `ai_decision_records`

**Purpose**

- separate AI recommendation snapshot from human decision and resulting domain event;
- make later AI governance/reporting possible without treating AI cache/logs as workflow truth.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `ai_request_log_id` | int FK -> `ai_request_logs.id` | yes | request audit link |
| `ai_output_id` | int FK -> `ai_outputs.id` | yes | cached output link |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | nullable in Phase A |
| `kind` | varchar(64) | no | recommendation category |
| `recommendation_json` | jsonb | no | model output snapshot |
| `human_action` | varchar(16) | no | `accepted`, `edited`, `rejected`, `ignored` |
| `final_action_event_id` | uuid | yes | resulting `application_events.event_id` |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |

**PK**

- `id`

**FK**

- `ai_request_log_id -> ai_request_logs.id`
- `ai_output_id -> ai_outputs.id`
- `candidate_id -> users.id`
- `application_id -> applications.id`

**Indexes**

- `(candidate_id, created_at desc)`
- `(application_id, kind, created_at desc)`
- `(human_action, created_at desc)`

**Uniqueness**

- no extra unique constraint in Phase A

**Retention Notes**

- retain enough history for AI audit and operational investigation
- do not prune ahead of governance policy

**PII Notes**

- very high sensitivity because recommendation payload may embed candidate information and inferred risk signals

**Recommended JSON Fields And Why**

- `recommendation_json` because output schema may vary by AI use case, prompt version and model

**Phase A No-Hard-Constraints**

- keep `application_id` nullable
- keep `final_action_event_id` nullable
- do not assume all existing AI logs map cleanly to application grain

### 9. `candidate_access_tokens`

**Purpose**

- bootstrap artifact table for invite / launch / resume / OTP challenge material;
- separate token lifecycle from authenticated sessions and from journey progress;
- enable browser / Telegram / MAX / SMS launch symmetry.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `token_id` | uuid | no | public token reference |
| `token_hash` | varchar(128) | no | stored hash only |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | nullable in Phase A |
| `journey_session_id` | int FK -> `candidate_journey_sessions.id` | yes | launch target |
| `token_kind` | varchar(24) | no | `invite`, `launch`, `resume`, `otp_challenge` |
| `journey_surface` | varchar(24) | no | `standalone_web`, `telegram_webapp`, `max_miniapp` |
| `auth_method` | varchar(24) | no | `telegram_init_data`, `max_init_data`, `signed_link`, `otp`, `admin_invite` |
| `launch_channel` | varchar(16) | no | `telegram`, `max`, `sms`, `email`, `manual`, `hh` |
| `launch_payload_json` | jsonb | yes | launcher/provider context |
| `start_param` | varchar(512) | yes | opaque short ref for MAX/Telegram launcher |
| `provider_user_id` | varchar(64) | yes | provider identity snapshot |
| `provider_chat_id` | varchar(64) | yes | provider chat/shell context |
| `session_version_snapshot` | integer | yes | security snapshot |
| `phone_verification_state` | varchar(24) | yes | `not_required`, `pending`, `verified`, `failed`, `expired` |
| `phone_delivery_channel` | varchar(16) | yes | OTP transport |
| `secret_hash` | varchar(128) | yes | used for OTP challenge |
| `attempt_count` | integer | no | current attempts |
| `max_attempts` | integer | no | attempt cap |
| `correlation_id` | uuid | yes | end-to-end trace |
| `idempotency_key` | varchar(128) | yes | token issuance retry guard |
| `issued_by_type` | varchar(32) | yes | actor type |
| `issued_by_id` | varchar(64) | yes | actor id |
| `expires_at` | timestamptz | no | TTL |
| `consumed_at` | timestamptz | yes | first successful consumption |
| `revoked_at` | timestamptz | yes | explicit revocation |
| `last_seen_at` | timestamptz | yes | last validation attempt |
| `created_at` | timestamptz | no | created timestamp |
| `metadata_json` | jsonb | yes | campaign/surface/debug snapshot |

**PK**

- `id`

**FK**

- `candidate_id -> users.id`
- `application_id -> applications.id`
- `journey_session_id -> candidate_journey_sessions.id`

**Indexes**

- unique `(token_id)`
- unique `(token_hash)`
- `(candidate_id, token_kind, expires_at)`
- `(application_id, token_kind, expires_at)`
- `(journey_session_id, token_kind)`
- `(launch_channel, auth_method, created_at desc)`
- unique `(start_param)` where used

**Uniqueness**

- `token_id` unique immediately
- `token_hash` unique immediately
- `start_param` unique if emitted
- do not hard-enforce “one active invite per candidate/channel” across all token kinds in Phase A

**Retention Notes**

- keep revoked and consumed tokens for audit
- token rows should not be deleted just because a session was opened

**PII Notes**

- high sensitivity because of launch mapping, provider identity snapshot and OTP challenge linkage
- raw token secret must never be persisted or logged

**Recommended JSON Fields And Why**

- `launch_payload_json` because launcher metadata differs between browser links, Telegram launch, MAX launch and campaign delivery
- `metadata_json` because support/audit context is sparse and evolving

**Phase A No-Hard-Constraints**

- `application_id` stays nullable
- `journey_session_id` stays nullable
- `session_version_snapshot` may be null for imported legacy invite rows
- no hard active-invite uniqueness beyond what current legacy data safely supports

### 10. `candidate_access_sessions`

**Purpose**

- server-side authenticated candidate session after launch validation;
- separate session lifecycle from bootstrap token lifecycle and from journey progress state.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `session_id` | uuid | no | public session reference |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | nullable in Phase A |
| `journey_session_id` | int FK -> `candidate_journey_sessions.id` | no | progress target |
| `origin_token_id` | bigint FK -> `candidate_access_tokens.id` | yes | bootstrap token link |
| `journey_surface` | varchar(24) | no | `standalone_web`, `telegram_webapp`, `max_miniapp` |
| `auth_method` | varchar(24) | no | same taxonomy as token table |
| `launch_channel` | varchar(16) | no | original transport |
| `provider_session_id` | varchar(128) | yes | provider query id or shell session id |
| `provider_user_id` | varchar(64) | yes | validated provider identity snapshot |
| `session_version_snapshot` | integer | no | revocation/recovery guard |
| `phone_verification_state` | varchar(24) | yes | `required`, `pending`, `verified`, `bypassed`, `expired` |
| `phone_verified_at` | timestamptz | yes | OTP success time |
| `phone_delivery_channel` | varchar(16) | yes | OTP transport |
| `csrf_nonce` | varchar(128) | yes | cookie-bound mutation guard |
| `status` | varchar(16) | no | `active`, `expired`, `revoked`, `blocked` |
| `issued_at` | timestamptz | no | session start |
| `last_seen_at` | timestamptz | yes | activity marker |
| `refreshed_at` | timestamptz | yes | last refresh |
| `expires_at` | timestamptz | no | session expiry |
| `revoked_at` | timestamptz | yes | explicit revocation |
| `correlation_id` | uuid | yes | end-to-end trace |
| `metadata_json` | jsonb | yes | device/UA/capabilities snapshot |

**PK**

- `id`

**FK**

- `candidate_id -> users.id`
- `application_id -> applications.id`
- `journey_session_id -> candidate_journey_sessions.id`
- `origin_token_id -> candidate_access_tokens.id`

**Indexes**

- unique `(session_id)`
- `(candidate_id, status, expires_at)`
- `(application_id, status, expires_at)`
- `(journey_session_id, status)`
- `(provider_user_id, journey_surface, issued_at desc)`

**Uniqueness**

- `session_id` unique immediately
- no active-session-per-candidate hard unique in Phase A

**Retention Notes**

- keep revoked and expired sessions for security audit
- do not delete on refresh

**PII Notes**

- high sensitivity because of session, provider identity, device and verification traces

**Recommended JSON Fields And Why**

- `metadata_json` because device/user-agent/capability snapshot shape varies by browser, Telegram and MAX surfaces

**Phase A No-Hard-Constraints**

- `application_id` stays nullable
- `provider_session_id` stays nullable
- no strict one-active-session partial unique in Phase A
- no historical backfill promise

### 11. `candidate_journey_sessions` additive fields

**Purpose**

- keep existing table as journey progress state only;
- add only enough fields to bridge progress to access and application grain.

**Additive Fields**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `application_id` | bigint FK -> `applications.id` | yes | target application |
| `last_access_session_id` | bigint FK -> `candidate_access_sessions.id` | yes | latest auth session |
| `last_surface` | varchar(32) | yes | last active surface |
| `last_auth_method` | varchar(32) | yes | last bootstrap method |

**PK**

- existing `id`

**FK**

- `application_id -> applications.id`
- `last_access_session_id -> candidate_access_sessions.id`

**Indexes**

- existing `(candidate_id, status)` remains
- add `(application_id, status)`
- add `(last_access_session_id)`

**Uniqueness**

- keep existing semantics
- do not add new hard unique constraints in Phase A

**Retention Notes**

- journey progress should remain resumable and auditable

**PII Notes**

- medium-high sensitivity because payload stores candidate progress

**Recommended JSON Fields And Why**

- keep existing `payload_json` progress-only
- do not store auth state in `payload_json`

**Phase A No-Hard-Constraints**

- `application_id` remains nullable
- `last_access_session_id` remains nullable
- do not repurpose existing portal-oriented rows

### 12. `message_threads`

**Purpose**

- canonical business-thread across candidate/application/channel fallback;
- unify what is currently spread across `chat_messages`, outbox and logs.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `thread_uuid` | uuid | no | public thread id |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | nullable in Phase A |
| `requisition_id` | bigint FK -> `requisitions.id` | yes | nullable in Phase A |
| `thread_kind` | varchar(32) | no | `recruiting`, `scheduling`, `campaign`, `support`, `reactivation` |
| `purpose_scope` | varchar(32) | no | `transactional`, `operational`, `campaign` |
| `source_entity_type` | varchar(32) | yes | `slot`, `slot_assignment`, `campaign_run`, `test_result` |
| `source_entity_id` | varchar(64) | yes | source identifier |
| `status` | varchar(24) | no | `open`, `snoozed`, `closed`, `archived` |
| `current_primary_channel` | varchar(32) | yes | cached routing hint |
| `last_inbound_at` | timestamptz | yes | latest inbound activity |
| `last_outbound_at` | timestamptz | yes | latest outbound activity |
| `last_message_id` | bigint FK -> `messages.id` | yes | latest message |
| `thread_context_json` | jsonb | yes | creation and surface snapshot |
| `created_at` | timestamptz | no | created timestamp |
| `updated_at` | timestamptz | no | updated timestamp |
| `closed_at` | timestamptz | yes | closed timestamp |

**PK**

- `id`

**FK**

- `candidate_id -> users.id`
- `application_id -> applications.id`
- `requisition_id -> requisitions.id`
- `last_message_id -> messages.id`

**Indexes**

- `(candidate_id, updated_at desc)`
- `(application_id, updated_at desc)`
- `(status, updated_at desc)`

**Uniqueness**

- target partial unique active `(candidate_id, application_id, thread_kind)` after cleanup
- do not hard-enforce for imported legacy rows in Phase A

**Retention Notes**

- retain even when routing channel changes
- thread should survive fallback and reopening

**PII Notes**

- high sensitivity because thread anchors conversation scope and candidate journey context

**Recommended JSON Fields And Why**

- `thread_context_json` because first-seen surface, campaign, and source snapshot can vary by use case

**Phase A No-Hard-Constraints**

- no hard active-thread unique for rows without `application_id`
- `requisition_id` stays nullable
- `last_message_id` stays nullable

### 13. `messages`

**Purpose**

- canonical message intent table;
- separate business intent from transport attempts;
- preserve template lineage and dedupe state.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `message_uuid` | uuid | no | public message id |
| `thread_id` | bigint FK -> `message_threads.id` | no | parent thread |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | nullable in Phase A |
| `requisition_id` | bigint FK -> `requisitions.id` | yes | nullable in Phase A |
| `direction` | varchar(16) | no | `outbound`, `inbound`, `system` |
| `intent_key` | varchar(64) | no | canonical intent name |
| `purpose_scope` | varchar(32) | no | routing/policy scope |
| `sender_type` | varchar(16) | no | `system`, `recruiter`, `candidate`, `n8n`, `provider_webhook` |
| `sender_id` | varchar(64) | yes | actor id |
| `template_family_key` | varchar(100) | yes | renderer family |
| `template_version` | integer | yes | resolved template version |
| `template_context_json` | jsonb | yes | logical render context |
| `canonical_payload_json` | jsonb | yes | normalized message intent payload |
| `render_context_json` | jsonb | yes | render-specific context snapshot |
| `idempotency_key` | varchar(128) | no | create-intent retry guard |
| `correlation_id` | uuid | yes | workflow trace |
| `dedupe_scope_key` | varchar(160) | yes | anti-spam grouping |
| `reply_to_message_id` | bigint FK -> `messages.id` | yes | reply threading |
| `intent_status` | varchar(24) | no | `created`, `routing`, `in_flight`, `completed`, `failed`, `cancelled` |
| `created_at` | timestamptz | no | created timestamp |
| `completed_at` | timestamptz | yes | terminal timestamp |

**PK**

- `id`

**FK**

- `thread_id -> message_threads.id`
- `candidate_id -> users.id`
- `application_id -> applications.id`
- `requisition_id -> requisitions.id`
- `reply_to_message_id -> messages.id`

**Indexes**

- unique `(idempotency_key)`
- `(thread_id, created_at asc)`
- `(candidate_id, created_at desc)`
- `(application_id, intent_key, created_at desc)`
- `(dedupe_scope_key, created_at desc)`

**Uniqueness**

- `idempotency_key` unique immediately
- no hard unique on `dedupe_scope_key`

**Retention Notes**

- retain as canonical message intent history
- do not collapse multiple fallback attempts into one row

**PII Notes**

- very high sensitivity because message content and render context may embed candidate data

**Recommended JSON Fields And Why**

- `template_context_json` because template variables vary by intent
- `canonical_payload_json` because intent payload shape is sparse and evolvable
- `render_context_json` because renderer-specific context differs by Telegram / MAX / SMS / browser_link

**Phase A No-Hard-Constraints**

- `application_id` stays nullable
- `requisition_id` stays nullable
- no hard unique dedupe key beyond create-intent idempotency

### 14. `message_deliveries`

**Purpose**

- one routed attempt in one channel/provider;
- represent retry and fallback history explicitly;
- become operational source of truth for transport execution.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `delivery_uuid` | uuid | no | public delivery id |
| `message_id` | bigint FK -> `messages.id` | no | parent message |
| `thread_id` | bigint FK -> `message_threads.id` | no | denormalized join |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | nullable in Phase A |
| `channel` | varchar(32) | no | `telegram`, `max`, `sms`, `browser_link` |
| `provider` | varchar(32) | no | `telegram_bot_api`, `max_api`, `sms_provider`, `link_service` |
| `identity_id` | bigint FK -> `candidate_channel_identities.id` | yes | routed identity |
| `destination_fingerprint` | varchar(160) | yes | masked endpoint fingerprint |
| `route_order` | integer | no | primary/fallback order |
| `channel_attempt_no` | integer | no | retry count within channel |
| `overall_attempt_no` | integer | no | monotonic within message |
| `delivery_status` | varchar(24) | no | `planned`, `sending`, `provider_accepted`, `delivered`, `read`, `failed`, `skipped`, `cancelled` |
| `failure_class` | varchar(16) | yes | `hard`, `soft`, `temporary` |
| `failure_code` | varchar(64) | yes | normalized code |
| `provider_message_id` | varchar(128) | yes | provider id |
| `provider_correlation_id` | varchar(128) | yes | provider trace id |
| `rendered_payload_json` | jsonb | yes | final rendered payload |
| `request_payload_json` | jsonb | yes | redacted request snapshot |
| `idempotency_key` | varchar(160) | no | delivery retry guard |
| `next_retry_at` | timestamptz | yes | retry schedule |
| `sent_at` | timestamptz | yes | send acceptance time |
| `terminal_at` | timestamptz | yes | terminal time |
| `created_at` | timestamptz | no | created timestamp |

**PK**

- `id`

**FK**

- `message_id -> messages.id`
- `thread_id -> message_threads.id`
- `candidate_id -> users.id`
- `application_id -> applications.id`
- `identity_id -> candidate_channel_identities.id`

**Indexes**

- unique `(idempotency_key)`
- `(message_id, overall_attempt_no)`
- `(candidate_id, channel, created_at desc)`
- `(delivery_status, next_retry_at)`
- `(provider, provider_message_id)`

**Uniqueness**

- `idempotency_key` unique immediately
- provider message uniqueness only where provider id exists

**Retention Notes**

- retain attempt history even when retries/fallback succeed later
- do not collapse retry chain

**PII Notes**

- high sensitivity because it references endpoint fingerprints and transport payloads

**Recommended JSON Fields And Why**

- `rendered_payload_json` because final payload differs across channels/renderers
- `request_payload_json` because provider request shape differs by adapter

**Phase A No-Hard-Constraints**

- `identity_id` stays nullable for browser links and unresolved imports
- `application_id` stays nullable
- no hard provider id requirement for imported legacy rows

### 15. `provider_receipts`

**Purpose**

- append-only provider ingest truth;
- decouple external receipt events from delivery row mutation;
- support reconciliation and analytics.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `receipt_uuid` | uuid | no | public receipt id |
| `delivery_id` | bigint FK -> `message_deliveries.id` | no | delivery anchor |
| `message_id` | bigint FK -> `messages.id` | no | message join |
| `channel` | varchar(32) | no | channel |
| `provider` | varchar(32) | no | provider |
| `provider_message_id` | varchar(128) | yes | provider delivery id |
| `provider_event_id` | varchar(160) | yes | provider event id |
| `receipt_type` | varchar(24) | no | `accepted`, `delivered`, `read`, `failed`, `bounced`, `blocked`, `session_opened` |
| `provider_status_code` | varchar(64) | yes | provider code |
| `provider_status_text` | text | yes | provider text |
| `normalized_failure_class` | varchar(16) | yes | normalized class |
| `normalized_failure_code` | varchar(64) | yes | normalized code |
| `raw_payload_json` | jsonb | yes | raw provider payload |
| `occurred_at` | timestamptz | no | provider event time |
| `received_at` | timestamptz | no | ingestion time |

**PK**

- `id`

**FK**

- `delivery_id -> message_deliveries.id`
- `message_id -> messages.id`

**Indexes**

- `(delivery_id, occurred_at asc)`
- `(provider, provider_message_id)`
- `(provider, provider_event_id)`

**Uniqueness**

- unique `(provider, provider_event_id)` where available

**Retention Notes**

- retain longer than transport row state changes
- do not mutate raw receipt history

**PII Notes**

- high sensitivity because raw payloads may contain identifiers and provider metadata

**Recommended JSON Fields And Why**

- `raw_payload_json` only, because provider receipt body is inherently provider-shaped and append-only

**Phase A No-Hard-Constraints**

- allow null `provider_message_id`
- allow null `provider_event_id`
- do not reject imported historical rows missing provider identifiers

### 16. `candidate_contact_policies`

**Purpose**

- purpose-aware routing truth: preferred channel, fallback order, consent, quiet windows, anti-spam;
- keep policy separate from identity and delivery history.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `candidate_id` | int FK -> `users.id` | no | candidate anchor |
| `application_id` | bigint FK -> `applications.id` | yes | optional application override |
| `purpose_scope` | varchar(32) | no | `transactional`, `operational`, `campaign` |
| `preferred_channel` | varchar(32) | yes | routing preference |
| `fallback_order_json` | jsonb | no | ordered channel list |
| `fallback_enabled` | boolean | no | fallback switch |
| `consent_status` | varchar(24) | no | `granted`, `implicit_transactional`, `revoked`, `unknown` |
| `serviceability_status` | varchar(24) | no | `serviceable`, `limited`, `unsupported`, `manual_only` |
| `do_not_contact` | boolean | no | hard stop |
| `quiet_windows_json` | jsonb | yes | timezone-aware quiet window config |
| `max_messages_per_day` | integer | yes | cadence budget |
| `min_spacing_minutes` | integer | yes | spacing budget |
| `last_contacted_at` | timestamptz | yes | cadence state |
| `policy_version` | integer | no | optimistic version |
| `updated_by` | varchar(64) | yes | actor id |
| `updated_at` | timestamptz | no | update timestamp |

**PK**

- `id`

**FK**

- `candidate_id -> users.id`
- `application_id -> applications.id`

**Indexes**

- `(preferred_channel)`
- `(do_not_contact, updated_at desc)`

**Uniqueness**

- partial unique `(candidate_id, purpose_scope)` where `application_id is null`
- partial unique `(candidate_id, application_id, purpose_scope)` where `application_id is not null`

**Retention Notes**

- Phase A can keep current-state row only
- history should be preserved via events/audit, not by uncontrolled overwrites

**PII Notes**

- medium-high sensitivity because policy reveals consent and communication constraints

**Recommended JSON Fields And Why**

- `fallback_order_json` because channel order is dynamic and purpose-aware
- `quiet_windows_json` because quiet windows are timezone/surface-specific and likely to evolve

**Phase A No-Hard-Constraints**

- do not require a row for every candidate
- do not require `preferred_channel`
- synthesize defaults for legacy candidates

### 17. `channel_health_registry`

**Purpose**

- persisted operational registry for channel/provider/runtime current state;
- bridge current bot health/degraded state to future multi-channel routing and operator APIs.

**Columns**

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigint PK | no | surrogate key |
| `channel` | varchar(32) | no | `telegram`, `max`, `sms`, `browser_link` |
| `provider` | varchar(32) | no | provider identifier |
| `runtime_surface` | varchar(32) | no | `bot_worker`, `webhook_ingest`, `link_service` |
| `health_status` | varchar(24) | no | `healthy`, `degraded`, `down`, `disabled` |
| `failure_domain` | varchar(64) | yes | normalized incident bucket |
| `reason_code` | varchar(64) | yes | machine-readable reason |
| `reason_text` | text | yes | human explanation |
| `circuit_state` | varchar(24) | no | `closed`, `open`, `half_open` |
| `last_probe_at` | timestamptz | yes | latest probe |
| `last_failure_at` | timestamptz | yes | latest fail |
| `last_recovered_at` | timestamptz | yes | latest recovery |
| `probe_payload_json` | jsonb | yes | probe-specific data |
| `updated_at` | timestamptz | no | update timestamp |

**PK**

- `id`

**FK**

- none required in Phase A

**Indexes**

- unique `(channel, provider, runtime_surface)`
- `(health_status, updated_at desc)`

**Uniqueness**

- one current row per `(channel, provider, runtime_surface)`

**Retention Notes**

- current-state table only
- history belongs in events, not unbounded row churn

**PII Notes**

- low direct PII
- still operationally sensitive

**Recommended JSON Fields And Why**

- `probe_payload_json` because probe data varies by provider/runtime

**Phase A No-Hard-Constraints**

- do not require rows for dormant or not-yet-live surfaces
- do not claim MAX/SMS/browser are live runtime surfaces merely because rows exist

## Section 2. Relation Summary / ERD-Level Explanation

### `users -> applications`

`users` remains the person row. `applications` becomes the funnel grain. One person may have multiple applications over time, across requisitions, sources, and recruiters.

### `applications -> requisitions`

`requisitions` owns operational demand, headcount, SLA and owner semantics. `applications` references `requisition_id` when known. During Phase A some applications may still exist without resolved requisition linkage.

### `applications -> application_events`

`application_events` is append-only canonical history. Every lifecycle transition, messaging side effect, access event, AI decision handoff or integration callback should eventually map to an event row. `application_id` may stay null for candidate-level historical imports in Phase A.

### `applications -> interviews`

`interviews` is a child execution record of `applications`. `slot_assignments` and `slots` remain current scheduling truth in Phase A. `interviews` therefore acts as bridge/read model, not scheduling replacement.

### `users -> candidate_channel_identities`

`candidate_channel_identities` is canonical identity truth. It absorbs what is currently mirrored on `users.telegram_*`, `users.max_user_id`, and parts of HH identity linkage. Messaging and dedup should join through this table rather than through legacy mirrors.

### `users/applications -> candidate_access_tokens/sessions`

Access is candidate- and optionally application-scoped. `candidate_access_tokens` is launch/bootstrap material. `candidate_access_sessions` is authenticated session state. `candidate_journey_sessions` remains progress-only and links to application/session via additive fields.

### `users/applications -> message_threads/messages/message_deliveries`

`message_threads` groups the conversation by candidate and optional application. `messages` is one business intent in that thread. `message_deliveries` is one routed attempt in one channel/provider. `provider_receipts` is append-only external truth for that attempt.

### AI linkage

`ai_decision_records` links candidate/application scope to `ai_request_logs`, `ai_outputs`, and resulting `application_events`. If AI assists routing or content later, those decisions still resolve to application/message/event lineage rather than living only in AI cache tables.

### Dedup linkage

`dedup_candidate_pairs` tracks suspected duplicate people before any destructive merge is allowed. Identity conflicts found in Telegram/MAX/phone/HH or messaging history should result in review rows and corresponding events, not implicit rewrite of business truth.

### Scheduling truth note

In Phase A:

- `slots` and `slot_assignments` remain scheduling write truth;
- `interviews` is additive bridge/read model;
- no runtime ownership changes are implied.

### Identity / routing / transport truth note

- `candidate_channel_identities` = identity truth
- `candidate_contact_policies` = routing truth
- `message_deliveries` and `provider_receipts` = transport truth

## Section 3. Constraint Hardening Plan

### Constraints Introduced Immediately In Phase A

- PKs on all new tables
- typed mandatory anchor FKs where grain is clear
- required typed status fields:
  - `applications.lifecycle_status`
  - `requisitions.status`
  - `application_events.event_type`
  - `interviews.status`
  - `recruiter_tasks.status`
  - `messages.intent_status`
  - `message_deliveries.delivery_status`
  - `provider_receipts.receipt_type`
  - `channel_health_registry.health_status`
- unique `application_events.event_id`
- unique `candidate_access_tokens.token_id`
- unique `candidate_access_tokens.token_hash`
- unique `candidate_access_sessions.session_id`
- unique `messages.idempotency_key`
- unique `message_deliveries.idempotency_key`
- unique normalised dedup pair
- partial unique policy rows
- unique `provider_receipts(provider, provider_event_id)` only where event id is present

### Constraints Explicitly Deferred In Phase A

- `NOT NULL` on:
  - `applications.requisition_id`
  - `messages.application_id`
  - `message_threads.application_id`
  - `candidate_journey_sessions.application_id`
- global unique `(channel, external_user_id)` on `candidate_channel_identities`
- active unique on `(candidate_id, requisition_id)` for `applications`
- active unique on threads
- active unique on invite/session/task rows
- mandatory policy row for every candidate
- hard uniqueness on `application_events.idempotency_key`

### Phase B/C Constraint Hardening Targets

- tighten `candidate_channel_identities(channel, external_user_id)` after dedupe and identity validation
- tighten active `applications(candidate_id, requisition_id)` after requisition backfill
- require application-bound messaging where `intent_key` is application-scoped
- require policy row presence for actively routed candidates
- harden open-task uniqueness only after task creation is centralized

### Partial Uniques That Should Remain Partial

- active thread uniqueness by `(candidate_id, application_id, thread_kind)` only for non-archived rows
- candidate contact policy uniqueness by candidate/purpose and candidate/application/purpose
- provider receipt uniqueness by provider event id only when provider actually emits one
- channel primary identity uniqueness only where `is_primary = true`

## Section 4. Backfill Sources

### Backfill Matrix

| Entity | Primary source | Reliability | Notes |
| --- | --- | --- | --- |
| `candidate_channel_identities` | `users.telegram_*`, `users.max_user_id`, `users.messenger_platform`, `candidate_external_identities`, `chat_messages.telegram_user_id`, `slot_assignments.candidate_tg_id`, `outbox_notifications.candidate_tg_id`, `notification_logs.candidate_tg_id`, `manual_slot_audit_logs.candidate_tg_id`, `bot_message_logs.candidate_tg_id` | partial | duplicate and stale ids expected |
| `requisitions` | `vacancies`, `users.desired_position`, `users.responsible_recruiter_id`, `users.hh_vacancy_id`, `slot_assignments`, `detailization_entries` | partial | avoid 1:1 assumptions; seed coarse requisitions first |
| `applications` | `users.source`, `users.desired_position`, `users.responsible_recruiter_id`, `users.candidate_status`, `users.workflow_status`, `users.rejection_reason`, `users.archive_*`, `users.final_outcome*`, `users.status_changed_at`, `users.hh_*`, `slot_assignments`, `detailization_entries` | partial | candidate-level state needs deterministic projection |
| `application_events` | `candidate_journey_events`, `chat_messages`, `notification_logs`, `outbox_notifications`, `hh_sync_log`, `ai_request_logs`, `ai_outputs`, `ai_interview_script_feedback` | partial | many legacy logs are not 1:1 business events |
| `interviews` | `slot_assignments`, `slots`, `manual_slot_audit_logs`, `detailization_entries` | partial | scheduling/outcome semantics mixed |
| `recruiter_tasks` | `candidate_journey_events`, `slot_reminder_jobs`, `users.candidate_status/status_changed_at`, `slot_assignments`, outbox | partial | many tasks are implicit today |
| `dedup_candidate_pairs` | exact collisions in Telegram/MAX/phone/HH/history | partial | prefer fill-forward after initial exact collisions |
| `ai_decision_records` | `ai_request_logs`, `ai_outputs`, `ai_interview_script_feedback` | partial | many existing AI rows lack `application_id` |
| `candidate_access_tokens` | `candidate_invite_tokens` | reliable for invite rows | other token kinds fill forward |
| `candidate_access_sessions` | none reliable | fill forward only | do not fabricate history |
| additive `candidate_journey_sessions.*` | existing `candidate_journey_sessions`, `users.messenger_platform`, invite/history hints | partial | `application_id` only where unambiguous |
| `message_threads` | `chat_messages`, `outbox_notifications`, `notification_logs`, `candidate_journey_sessions` | partial | cluster legacy rows conservatively with deterministic key; split on ambiguity |
| `messages` | `chat_messages`, `outbox_notifications`, `notification_logs` | reliable/partial mix | imported rows may remain candidate-only |
| `message_deliveries` | `outbox_notifications`, `notification_logs` | reliable | strongest source for attempt history |
| `provider_receipts` | `notification_logs`, `chat_messages.telegram_message_id`, `outbox_notifications.provider_message_id` | partial | provider event ids often missing |
| `candidate_contact_policies` | `users.telegram_*`, `users.max_user_id`, `users.messenger_platform`, `users.phone`, `notification_logs`, `chat_messages` | partial | synthesize defaults for gaps |
| `channel_health_registry` | `bot_runtime_configs.messenger_channel_health` | reliable snapshot only | no historical backfill needed |

### Legacy Field Notes

#### `users.telegram_*`

- source for Telegram identity bootstrap into `candidate_channel_identities`
- partial because duplicate `telegram_id` / `telegram_user_id` conflicts may exist
- `telegram_linked_at` is useful as `linked_at` seed where present

#### `users.max_user_id`

- source for MAX identity bootstrap into `candidate_channel_identities`
- partial because MAX runtime is not current supported live surface
- should not be treated as fully verified identity without later validation

#### `users.messenger_platform`

- legacy routing hint only
- useful for initial `preferred_channel` and `last_surface` inference
- not canonical routing truth in Phase A

#### `users.source`

- source for `applications.source`
- reliable enough for initial projection, but lossy because one person row can only hold one source
- combine with `users.candidate_status`, `workflow_status`, `status_changed_at`, `rejection_reason`, `archive_*`, and `final_outcome*` when projecting first application row

#### `users.desired_position`

- hint for `requisitions.title` and `applications.vacancy_id` bridge
- partial only
- do not use as strict requisition key
- when demand mapping is ambiguous, create candidate-scoped `applications` row with nullable `requisition_id` instead of guessing

#### `users.responsible_recruiter_id`

- seed for `applications.recruiter_id`
- also informs `requisitions.owner_*`
- can be null or stale for historical rows

#### `users.hh_*`

- seed for HH-linked application/source/integration context
- partial bridge into `applications`, `candidate_channel_identities(channel='hh')`, and event payloads
- do not assume clean one-to-one application mapping

#### `slots / slot_assignments`

- remain scheduling truth
- source for `interviews`
- source for `applications` inference and `message_threads/messages` source entity linkage
- keep bridge semantics only in Phase A
- `slot_assignments.candidate_tg_id` is also a strong Telegram identity recovery source when `users.telegram_*` is empty or stale

#### `chat_messages / outbox_notifications / notification_logs`

- strongest source for initial messaging history
- `chat_messages` is best for chat timeline and inbound/outbound chronology
- `outbox_notifications` + `notification_logs` is strongest source for deliveries/receipts, retry and correlation lineage
- `outbox_notifications.candidate_tg_id` and `notification_logs.candidate_tg_id` should outrank weak handle-based inference when rebuilding Telegram identity rows

#### `ai_outputs / ai_request_logs`

- source for `ai_decision_records`
- not all rows are application-scoped
- many links should remain null rather than guessed

#### `candidate_journey_sessions / events`

- `candidate_journey_sessions` is reliable for journey progress seed
- `candidate_journey_events` is partial source for `application_events` and task inference
- keep progress and auth separated during backfill

### Deterministic Backfill Rules

- `applications`: seed one primary application row per candidate from legacy candidate-level lifecycle fields. Populate `lifecycle_status` from `users.candidate_status`, keep `workflow_status`, rejection/archive/final outcome overlays in `metadata_json`, and leave `requisition_id` null when demand mapping is not unambiguous.
- `requisitions`: seed one coarse requisition per explicit demand signal first. Use `(vacancy_id, responsible_recruiter_id, city_id, opened window)` as an initial split heuristic only when supported by `slot_assignments`, `detailization_entries`, or HH evidence; otherwise keep one vacancy-backed requisition and defer finer splitting to Phase B validation.
- `candidate_channel_identities`: Telegram precedence for backfill is `users.telegram_*` when verified and recent, then `slot_assignments.candidate_tg_id`, `outbox_notifications.candidate_tg_id`, `notification_logs.candidate_tg_id`, `manual_slot_audit_logs.candidate_tg_id`, `bot_message_logs.candidate_tg_id`, and finally handle-based hints from chat history. Conflicts stay unresolved in Phase A and must not trigger hard uniqueness.
- `message_threads`: cluster legacy rows only when `(candidate_id, application_id if known, purpose_scope, source_entity_type/id, correlation_id or booking/slot anchor)` matches and timestamps do not overlap conflicting conversations. If those anchors disagree, create separate candidate-only threads and preserve provenance in `thread_context_json`.

### Fill-Forward Only Fields

- `candidate_access_sessions`
- OTP verification state
- `provider_session_id`
- `csrf_nonce`
- many `ai_decision_records.application_id` links
- legacy receipt `provider_event_id`

## Section 5. Idempotency And Event Strategy

### Canonical Identifiers

- `event_id` = immutable business/ingest event id
- `correlation_id` = cross-flow trace through invite, access, messaging, delivery, lifecycle
- `idempotency_key` = caller retry guard within endpoint/table scope

### Where Uniqueness Lives

- `candidate_access_tokens.token_id`
- `candidate_access_tokens.token_hash`
- `candidate_access_sessions.session_id`
- `messages.idempotency_key`
- `message_deliveries.idempotency_key`
- `provider_receipts(provider, provider_event_id)` where event id exists
- `application_events.event_id`

### Callback / Webhook Mapping

1. provider callback/webhook hits backend API
2. backend validates auth and replay scope
3. backend writes `provider_receipts`
4. backend updates derived delivery state
5. backend emits matching `application_events`

### Messaging Canonical Events

- `message.intent_created`
- `message.sent`
- `message.delivered`
- `message.failed`
- `message.read`
- `channel.health_changed`

### Routing Failure Classes And Fallback Decision Table

Default outbound routing order for operational intents is:

- `telegram -> max -> sms -> browser_link`

The routing layer must skip channels that are unsupported in the current environment, blocked by consent/serviceability, or temporarily disabled in `channel_health_registry`.

| Failure class | Meaning | Same-channel retry | Fallback action | Candidate/channel state update |
| --- | --- | --- | --- | --- |
| `temporary_fail` | provider timeout, 5xx, rate limit, transient network | yes, bounded by per-channel attempt budget | fallback only after budget exhaustion or channel degradation | keep identity reachable, mark channel health/watch |
| `soft_fail` | content rejected, unsupported format, missing optional capability, recoverable routing mismatch | no blind repeat with same payload | immediately compute next allowed channel | keep identity state, record channel-specific failure code |
| `hard_fail` | blocked user, invalid chat id, revoked identity, permanent serviceability failure | no | mark current identity/channel unusable and move to next allowed channel, otherwise terminal fail | downgrade reachability/serviceability and persist `last_hard_fail_code` |
| `success` / `read` | provider accepted / delivered / read | stop | no fallback | update last success and thread state |

Stop conditions:

- `do_not_contact = true` or active quiet window defers the whole intent and creates no new delivery attempt.
- duplicate `dedupe_scope_key` returns the existing non-terminal or recent terminal message instead of creating a second candidate contact.
- browser fallback is represented by a `message_deliveries` row with `channel = 'browser_link'` and backend-owned provider. Link issuance is delivery truth; later link-open/auth success is tracked via `candidate_access_*` and `application_events` using the same `correlation_id`, not via `provider_receipts`.

### Why `n8n` Must Not Write Directly To DB

- it cannot guarantee transactional dedupe with business mutation
- it cannot safely own fallback ordering
- it cannot safely own receipt reconciliation
- it would split operator audit between low-code flow state and PostgreSQL truth
- it would bypass canonical `application_events` and messaging ledgers

## Section 6. Additive API Contract Pack

## Common Contract Rules

- `X-Request-ID` on all calls
- `X-Idempotency-Key` on all mutating calls
- `X-CSRF-Token` for cookie-backed post-auth candidate and admin mutations
- `X-Telegram-Init-Data` for Telegram bootstrap
- `X-Max-Init-Data` for MAX bootstrap
- `Authorization: Bearer <service-token>` for worker / n8n / service-principal calls
- `correlation_id` is a domain field in payload/response, not just transport header
- namespaces stay under `/api/v1/...`
- do not reuse `/api/webapp/*`
- do not resurrect `/candidate*`
- `/api/v1/candidate-access/*` and `/api/v1/candidate-journey/*` belong to an external/API runtime boundary equivalent to `admin_api`, not to `admin_ui`
- provider callbacks/webhooks must authenticate by provider signature or dedicated ingest secret and must terminate in backend API handlers, never in direct DB writes

### 6.1 Applications / Requisitions

#### `GET /api/v1/candidates/{candidate_id}/applications`

- **Purpose**: list applications for a candidate
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "items": [
    {
      "application_id": 123,
      "candidate_id": 45,
      "requisition_id": 67,
      "vacancy_id": 89,
      "source": "bot",
      "source_detail": null,
      "recruiter_id": 12,
      "lifecycle_status": "qualification_pending",
      "final_outcome": null,
      "created_at": "2026-04-16T12:00:00Z",
      "updated_at": "2026-04-16T12:00:00Z"
    }
  ],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: additive read API over current candidate detail/list surfaces

#### `GET /api/v1/applications/{application_id}`

- **Purpose**: get one application
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "application": {
    "application_id": 123,
    "candidate_id": 45,
    "requisition_id": 67,
    "vacancy_id": 89,
    "source": "bot",
    "source_detail": null,
    "recruiter_id": 12,
    "lifecycle_status": "qualification_pending",
    "lifecycle_reason": null,
    "final_outcome": null,
    "final_outcome_reason": null,
    "archived_at": null,
    "created_at": "2026-04-16T12:00:00Z",
    "updated_at": "2026-04-16T12:00:00Z"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: application becomes canonical read grain, but legacy candidate detail can remain unchanged

#### `POST /api/v1/applications`

- **Purpose**: create application
- **Auth model**: admin/recruiter or service principal
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `Authorization` for service principals, `X-CSRF-Token` if cookie-authenticated admin boundary
- **Request body skeleton**:

```json
{
  "candidate_id": 45,
  "requisition_id": 67,
  "vacancy_id": 89,
  "source": "bot",
  "source_detail": "telegram_campaign_spring",
  "recruiter_id": 12
}
```

- **Response skeleton**:

```json
{
  "application": {
    "application_id": 123
  },
  "correlation_id": "uuid",
  "event": {
    "event_id": "uuid",
    "event_type": "application.created",
    "correlation_id": "uuid"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required; repeated retries with same business intent must resolve to the same application/event pair where safe
- **Compatibility note**: no implied cutover from legacy candidate row ownership

#### `POST /api/v1/applications/{application_id}/status-transitions`

- **Purpose**: explicit lifecycle transition
- **Auth model**: admin/recruiter or service principal
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `X-CSRF-Token` where applicable
- `Authorization` is additionally required when the caller is a service principal
- **Request body skeleton**:

```json
{
  "to_status": "interview_scheduled",
  "reason": "slot_assigned",
  "expected_current_status": "waiting_slot",
  "actor_context": {
    "source": "admin_ui"
  }
}
```

- **Response skeleton**:

```json
{
  "application": {
    "application_id": 123,
    "lifecycle_status": "interview_scheduled"
  },
  "correlation_id": "uuid",
  "event": {
    "event_id": "uuid",
    "event_type": "application.status_changed",
    "correlation_id": "uuid"
  },
  "tasks": [],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required; replay returns same resulting event where transition already applied
- **Compatibility note**: legacy mirrors may continue to exist, but canonical transition writes to application/events first

#### `GET /api/v1/applications/{application_id}/events`

- **Purpose**: list application event timeline
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "items": [
    {
      "event_id": "uuid",
      "event_type": "application.status_changed",
      "occurred_at": "2026-04-16T12:00:00Z",
      "actor_type": "recruiter",
      "actor_id": "12",
      "status_from": "waiting_slot",
      "status_to": "interview_scheduled",
      "correlation_id": "uuid",
      "metadata_json": {}
    }
  ],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: additive read timeline over legacy sidecar logs

#### `GET /api/v1/requisitions`

- **Purpose**: list requisitions
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "items": [
    {
      "requisition_id": 67,
      "vacancy_id": 89,
      "city_id": 3,
      "title": "Recruiter",
      "headcount": 2,
      "priority": "high",
      "owner_type": "recruiter",
      "owner_id": 12,
      "status": "open"
    }
  ],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: `vacancies` remains reference catalog

#### `POST /api/v1/requisitions`

- **Purpose**: create requisition
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `X-CSRF-Token` where applicable
- **Request body skeleton**:

```json
{
  "title": "Recruiter",
  "vacancy_id": 89,
  "city_id": 3,
  "headcount": 2,
  "owner_type": "recruiter",
  "owner_id": 12,
  "priority": "high",
  "sla_config_json": {},
  "source_plan_json": {}
}
```

- **Response skeleton**:

```json
{
  "requisition": {
    "requisition_id": 67
  },
  "correlation_id": "uuid",
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required on create
- **Compatibility note**: additive operational demand layer

### 6.2 Access / Journey

#### `POST /api/v1/candidate-access/invites`

- **Purpose**: create invite package for browser / Telegram / MAX / SMS target surfaces
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `X-CSRF-Token` where applicable
- **Request body skeleton**:

```json
{
  "candidate_id": 45,
  "application_id": 123,
  "journey_surface_targets": [
    "standalone_web",
    "telegram_webapp",
    "max_miniapp",
    "sms"
  ],
  "purpose": "test1_invite",
  "source_entity_type": "application",
  "source_entity_id": "123"
}
```

- **Response skeleton**:

```json
{
  "invite": {
    "token_id": "uuid",
    "browser_url": "https://example/start?t=opaque",
    "telegram_launcher": "https://t.me/...",
    "max_launcher": "https://max.ru/...",
    "sms_hint": {
      "browser_url": "https://example/start?t=opaque"
    }
  },
  "correlation_id": "uuid",
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required per candidate/application/purpose issuance
- **Compatibility note**: browser fallback is target-state contract, not present-tense portal rollout promise

#### `POST /api/v1/candidate-access/launch/validate`

- **Purpose**: validate signed link / Telegram initData / MAX initData / resume context
- **Auth model**: public pre-auth endpoint
- **Required headers**:
  - always `X-Request-ID`
  - optionally `X-Telegram-Init-Data`
  - optionally `X-Max-Init-Data`
- **Request body skeleton**:

```json
{
  "launch_token": "opaque-or-null",
  "init_data": null,
  "start_param": null
}
```

- **Response skeleton**:

```json
{
  "result": "ok",
  "reason_code": null,
  "correlation_id": "uuid",
  "access_session": {
    "session_id": "uuid",
    "journey_surface": "standalone_web",
    "auth_method": "signed_link",
    "expires_at": "2026-04-16T20:00:00Z"
  },
  "journey_envelope": {
    "schema_version": "2026-04-16.v1"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: token/query-id/session-version driven; safe repeated launch reopens same valid session where allowed
- **Compatibility note**: must not use admin session or recruiter webapp auth
- **Security note**: resume flow must use existing server-issued session cookie or token proof; caller-provided arbitrary `session_id` must never be trusted

#### `POST /api/v1/candidate-journey/start`

- **Purpose**: bootstrap shared journey envelope after access validation
- **Auth model**: candidate access session
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "correlation_id": "uuid",
  "journey_envelope": {
    "schema_version": "2026-04-16.v1",
    "access": {},
    "candidate": {},
    "application": {},
    "journey": {},
    "surface_capabilities": {}
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: safe replay
- **Compatibility note**: one shared journey across browser, Telegram and MAX

#### `GET /api/v1/candidate-journey/current`

- **Purpose**: resume current journey
- **Auth model**: candidate access session
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "correlation_id": "uuid",
  "journey_envelope": {
    "schema_version": "2026-04-16.v1"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: additive resume API, not portal runtime restoration

#### `POST /api/v1/candidate-access/otp/send`

- **Purpose**: create OTP challenge
- **Auth model**: public pre-auth or pre-validated launch context
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`
- **Request body skeleton**:

```json
{
  "challenge_context_ref": "opaque-launch-or-session-bound-ref",
  "delivery_channel": "sms"
}
```

- **Response skeleton**:

```json
{
  "challenge_id": "uuid",
  "correlation_id": "uuid",
  "expires_at": "2026-04-16T12:10:00Z",
  "masked_destination": "+7***0000",
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required per challenge target / launch context
- **Compatibility note**: transport may initially be non-SMS while contract remains stable
- **Security note**: request must resolve the candidate/phone from opaque launch context or existing session state; the API must not reveal whether an arbitrary raw phone exists in the system

#### `POST /api/v1/candidate-access/otp/verify`

- **Purpose**: verify challenge and open session
- **Auth model**: public pre-auth with challenge/token context
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`
- **Request body skeleton**:

```json
{
  "challenge_id": "uuid",
  "code": "123456"
}
```

- **Response skeleton**:

```json
{
  "correlation_id": "uuid",
  "access_session": {
    "session_id": "uuid",
    "auth_method": "otp",
    "expires_at": "2026-04-16T20:00:00Z"
  },
  "journey_envelope": {
    "schema_version": "2026-04-16.v1"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: retry-safe until challenge consumed
- **Compatibility note**: anti-enumeration and rate limiting are mandatory

#### `POST /api/v1/candidate-access/session/refresh`

- **Purpose**: refresh active candidate session
- **Auth model**: candidate access session
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`
- **Request body skeleton**:

```json
{}
```

- **Response skeleton**:

```json
{
  "correlation_id": "uuid",
  "access_session": {
    "session_id": "uuid",
    "expires_at": "2026-04-16T21:00:00Z"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: refresh is idempotent while session remains active and version-valid
- **Compatibility note**: no bearer-by-default contract implied

#### `POST /api/v1/candidate-access/session/revoke`

- **Purpose**: revoke token/session
- **Auth model**: candidate access session or admin/recruiter principal
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `X-CSRF-Token` if cookie-backed
- **Request body skeleton**:

```json
{
  "session_id": null,
  "token_id": null,
  "reason": "operator_revoked",
  "cascade_mode": "revoke_current_session_version"
}
```

- **Response skeleton**:

```json
{
  "ok": true,
  "correlation_id": "uuid",
  "revoked": {
    "session_id": "uuid",
    "token_count": 2,
    "session_version_snapshot": 4
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: repeated revoke remains success
- **Compatibility note**: should not touch recruiter webapp sessions
- **Security note**: candidate-authenticated revoke targets only the current cookie-bound session; admin/service revoke may target an explicit `session_id` or `token_id`. Revocation must invalidate outstanding invite/launch/resume tokens for the same session version and bump the access-version snapshot used for reopen checks.

### 6.3 Messaging

#### `POST /api/v1/messaging/intents`

- **Purpose**: create message intent
- **Auth model**: admin/recruiter or service principal
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `Authorization` for service principals, `X-CSRF-Token` where applicable
- **Request body skeleton**:

```json
{
  "candidate_id": 45,
  "application_id": 123,
  "requisition_id": 67,
  "intent_key": "booking_invite",
  "purpose_scope": "operational",
  "template_family_key": "booking_invite",
  "template_context_json": {},
  "dedupe_scope_key": "candidate:45:booking_invite:application:123",
  "route_policy": {
    "preferred_channel": "telegram",
    "fallback_order": [
      "telegram",
      "max",
      "sms",
      "browser_link"
    ],
    "allow_fallback": true,
    "max_same_channel_attempts": 2
  },
  "source_entity_type": "application",
  "source_entity_id": "123"
}
```

- **Response skeleton**:

```json
{
  "message": {
    "message_uuid": "uuid",
    "intent_status": "created"
  },
  "thread": {
    "thread_uuid": "uuid"
  },
  "correlation_id": "uuid",
  "initial_route_plan": [],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required; same create-intent business request reuses same message
- **Compatibility note**: intent is separate from actual provider delivery

#### `POST /api/v1/messaging/messages/{message_uuid}/dispatch`

- **Purpose**: send through routing layer
- **Auth model**: service/worker or admin operator
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `Authorization` for service/worker calls
- **Request body skeleton**:

```json
{
  "force_recompute_route": false
}
```

- **Response skeleton**:

```json
{
  "message": {
    "message_uuid": "uuid",
    "intent_status": "in_flight"
  },
  "correlation_id": "uuid",
  "deliveries": [],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: message-scoped
- **Compatibility note**: worker should call backend routing layer, not provider directly as canonical write path

#### `GET /api/v1/messaging/threads/{thread_uuid}`

- **Purpose**: get thread detail
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "thread": {
    "thread_uuid": "uuid",
    "thread_kind": "recruiting",
    "status": "open"
  },
  "messages": [],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: thread is stable across channel fallback

#### `GET /api/v1/messaging/messages/{message_uuid}/deliveries`

- **Purpose**: list delivery attempts
- **Auth model**: admin/recruiter or service principal
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "items": [
    {
      "delivery_uuid": "uuid",
      "channel": "telegram",
      "provider": "telegram_bot_api",
      "delivery_status": "provider_accepted",
      "failure_class": null,
      "failure_code": null,
      "provider_message_id": "abc",
      "route_order": 1,
      "channel_attempt_no": 1,
      "overall_attempt_no": 1
    }
  ],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: source of truth is new delivery/receipt tables, not old logs

#### `POST /api/v1/messaging/deliveries/{delivery_uuid}/retry`

- **Purpose**: retry allowed delivery
- **Auth model**: admin/recruiter or service principal
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `Authorization` for service principals, `X-CSRF-Token` where applicable
- **Request body skeleton**:

```json
{
  "reason": "operator_retry",
  "allow_fallback": true
}
```

- **Response skeleton**:

```json
{
  "delivery_plan": {
    "delivery_uuid": "uuid"
  },
  "correlation_id": "uuid",
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required
- **Compatibility note**: retry allowed only for retryable states

#### `GET /api/v1/messaging/channel-health`

- **Purpose**: list channel/provider health snapshot
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`
- **Request body**: none
- **Response skeleton**:

```json
{
  "items": [
    {
      "channel": "telegram",
      "provider": "telegram_bot_api",
      "runtime_surface": "bot_worker",
      "health_status": "healthy",
      "last_probe_at": "2026-04-16T12:00:00Z",
      "last_failure_at": null,
      "last_recovered_at": null,
      "reasons": []
    }
  ],
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency**: n/a
- **Compatibility note**: initial implementation may project from current messenger-health service

#### `POST /api/v1/messaging/channel-health/{channel}/{provider}/actions`

- **Purpose**: operator override / pause / recover channel health
- **Auth model**: admin/recruiter authenticated boundary
- **Required headers**: `X-Request-ID`, `X-Idempotency-Key`, `X-CSRF-Token`
- **Request body skeleton**:

```json
{
  "action": "recover",
  "purpose": "operator_recovery",
  "reason": "token_rotated",
  "manual_override_until": null
}
```

- **Response skeleton**:

```json
{
  "channel_health": {
    "channel": "telegram",
    "provider": "telegram_bot_api",
    "health_status": "healthy"
  },
  "correlation_id": "uuid",
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: required
- **Compatibility note**: operator action must emit `channel.health_changed`

### 6.4 Provider Receipt Ingest

#### `POST /api/v1/messaging/providers/{provider}/receipts`

- **Purpose**: canonical ingest endpoint for provider callbacks/webhooks and internal delivery bridges
- **Auth model**: provider signature / webhook secret or service principal
- **Required headers**:
  - always `X-Request-ID`
  - provider-specific signature header or dedicated webhook secret
  - `Authorization` when called by internal bridge/service principal
- **Request body skeleton**:

```json
{
  "provider_event_id": "evt_123",
  "provider_message_id": "msg_456",
  "occurred_at": "2026-04-16T12:00:00Z",
  "receipt_type": "delivered",
  "payload": {}
}
```

- **Response skeleton**:

```json
{
  "receipt": {
    "receipt_uuid": "uuid",
    "delivery_uuid": "uuid",
    "message_uuid": "uuid"
  },
  "correlation_id": "uuid",
  "application_event": {
    "event_id": "uuid",
    "event_type": "message.delivered"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

- **Idempotency rule**: dedupe by `(provider, provider_event_id)` where present, otherwise by normalized receipt tuple plus payload hash
- **Compatibility note**: this is the only canonical write path for provider receipts; webhooks and low-code workers must not write `provider_receipts` or `application_events` directly

## Section 7. Auth Model Summary

### Telegram initData flow

- server-side validation only
- never trust `initDataUnsafe`
- `initData` is launch/auth proof only
- candidate/application resolution must come from token/session/identity binding logic, not raw init payload

### MAX initData flow

- same server-side validation model
- `start_param` must stay short opaque ref
- no dependency on `SecureStorage`
- MAX bridge capabilities influence shell UX, not business state ownership

### Signed link flow

- opaque token reference only
- `token_hash` stored at rest
- TTL, revocation and `session_version_snapshot` enforced server-side
- browser fallback is canonical target-state launch path

### OTP flow

- challenge and code stored hashed
- anti-enumeration and rate limiting required
- SMS is target transport contract
- temporary delivery via Telegram/MAX/email is allowed without changing auth API shape

### Admin / recruiter authenticated APIs

- unchanged current session/bearer/CSRF boundary
- these APIs create invites, manage health, inspect applications and manage messaging
- candidate-facing access/journey routes should live under API runtime ownership aligned with `admin_api`, not `admin_ui`

### CSRF applicability

- pre-auth bootstrap endpoints are CSRF-exempt
- post-auth candidate journey mutations are cookie + CSRF
- admin browser mutation rules remain unchanged

### Session vs bearer usage

- candidate browser/webview defaults to cookie + CSRF
- bearer remains appropriate for non-browser admin/recruiter and service/integration clients
- candidate access boundary must not inherit recruiter `/api/webapp/*` semantics

## Section 8. Phase A Implementation Boundary

### Safe In Phase A

- additive tables only
- repository/service interface stubs
- read-only projections from legacy tables
- admin/debug/read APIs
- no-op event publisher interfaces
- channel health projection bridge from current messenger health
- access token issuance stubs behind feature flags
- shared candidate journey envelope contract without runtime rollout

### Phase A Does Not Change

- scheduling write ownership
- current Telegram recruiter webapp runtime
- admin UI auth model
- supported channels runtime matrix
- current legacy APIs
- existing SQLAlchemy model ownership

## Section 9. Exclusions

The following are explicitly out of Phase A:

- full runtime cutover
- replacing scheduling truth
- replacing candidate detail UI completely
- browser rollout to production
- MAX rollout to production
- SMS rollout to production
- legacy cleanup
- destructive merges
- analytics cutover
- immediate replacement of `chat_messages`, `outbox_notifications`, `notification_logs`
- replacement of current recruiter Telegram webapp

## Validation Checklist For This RFC

- all required entities are present
- all required endpoint families are present
- all three companion ADR links resolve
- MAX / browser / SMS / Telegram context is reflected in schema, auth and APIs
- nothing contradicts [supported_channels.md](../supported_channels.md)
- no runtime or migration promises are introduced

## Assumptions

- `docs/architecture/rfc/` is valid new location for architecture RFCs
- `browser_link` is modeled as routing surface / analytics channel, not provider
- `candidate_channel_identities` remains canonical identity layer from `RS-ADR-002`
- `candidate_journey_sessions` remains progress-only from `RS-ADR-004`
- messaging canonical truth remains `thread -> message -> delivery -> receipt` from `RS-ADR-005`
- current environment supported only 4 parallel subagents, so data/migration-risk synthesis was completed by the main agent locally without changing the coverage target
