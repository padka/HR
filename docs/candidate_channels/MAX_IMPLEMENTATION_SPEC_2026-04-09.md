# MAX Implementation Spec

Дата: `2026-04-09`

Source of truth for this spec:
- [`docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md`](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md)

Implementation goal:
- довести MAX candidate channel до production-ready состояния
- не наращивать Telegram-bound legacy
- не создавать второй параллельный бизнес-поток кандидата
- использовать уже существующий candidate portal / journey / slot-assignment core как primary business layer

Non-goals:
- не переписывать Telegram bot целиком
- не делать большой platform rewrite ради идеальной multi-channel purity
- не удалять весь legacy в первой волне

## 1. Executive Summary

Рекомендуемая стратегия: `частичный рефакторинг + завершение MAX поверх существующего channel-agnostic core`.

Причина:
- быстрый copy-paste adapter от Telegram создаст ещё один legacy branch
- полный предварительный core-extraction замедлит поставку без критической необходимости
- audit уже подтвердил, что значимая часть ядра существует:
  - candidate journey / portal core: [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
  - status/workflow contracts: [`backend/domain/candidates/status.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status.py)
  - scheduling core: [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)
  - messenger abstraction: [`backend/core/messenger/*`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger)
  - MAX runtime already exists: [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py), [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)

Delivery principle:
- использовать existing MAX runtime as delivery shell
- запрещать новые Telegram-bound контракты
- дорабатывать MAX только через domain-owned path:
  - identity linkage
  - journey/profile/screening
  - assignment-owned scheduling
  - outbox/retry/audit

## 2. Current State Summary from Audit

Краткое резюме того, что подтверждено аудитом и влияет на implementation plan:

- MAX уже частично реализован и не должен проектироваться "с нуля".
- Telegram bot остаётся историческим source of behavior, но не должен быть source of architecture.
- Candidate journey уже частично channel-agnostic:
  - steps: `profile`, `screening`, `slot_selection`, `status`
  - sessions/step states/events already persisted in DB
- Scheduling находится в переходном состоянии:
  - legacy `Slot` path still exists
  - target path is `SlotAssignment`-owned flow
- Главные архитектурные долги:
  - Telegram-first identity model
  - Telegram-bound ephemeral bot state
  - mixed transport/business logic in parts of Telegram onboarding and slot flows
  - incomplete parity of dedupe/replay protection between channels

Implication for execution:
- MAX first release must ride on existing domain core
- any remaining Telegram-only contracts must be isolated or wrapped, not spread

## 3. Recommended Delivery Strategy

### Chosen strategy

`Частичный рефакторинг + реализация MAX`

### Why this strategy

Why not `быстрый адаптер`:
- audit showed that Telegram orchestration still mixes transport and business logic in [`backend/apps/bot/services/test1_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/test1_flow.py) and [`backend/apps/bot/services/slot_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/slot_flow.py)
- reusing these directly for MAX would duplicate Telegram callback assumptions and chat-id state semantics

Why not `сначала полный channel-agnostic core`:
- candidate portal / journey / slot assignment core already exists
- MAX runtime and many tests already exist
- full extraction before delivery would spend time on platform cleanup that is not required for first safe launch

### Delivery compromise

What we optimize for:
- safest path to production
- smallest amount of new legacy
- maximal reuse of audited core

What we accept:
- some Telegram legacy will remain after MAX v1
- full schema cleanup and final multi-channel normalization are deferred

### Success condition for strategy

Strategy is considered correct only if MAX v1:
- uses one canonical identity linkage path
- uses one canonical scheduling write path
- uses journey/session as source of candidate progress
- passes parity tests against Telegram/portal critical flows

## 4. Scope: In / Out / Deferred

### In Scope

Первая production-версия MAX must support:

1. MAX candidate entry
- `bot_started`
- `message_created`
- `message_callback`
- signed deep-link / invite-based start
- signed mini-app / browser launch continuation where applicable

2. Candidate identification and binding
- bind MAX user to existing candidate via invite/signed access
- support public entry only when explicitly allowed by config
- reject duplicate owner / stale session / conflicting link deterministically

3. Candidate questionnaire flow
- profile collection in MAX
- screening/questionnaire completion in MAX
- draft save
- validation of required inputs
- deterministic continuation after interruption

4. State transitions
- lead -> screening-related progression
- screening completion -> scheduling stage
- scheduling-related status transitions through canonical backend contracts

5. Scheduling
- candidate can receive or resume current scheduling state
- candidate can confirm interview
- candidate can request reschedule
- candidate can cancel/decline where existing business logic allows it
- all writes must go through assignment-owned path where available

6. Notifications and service messages
- delivery of candidate-facing confirmations
- service replies for invalid input / stale token / blocked state
- outbox-aware routing where current domain path expects it

7. Reliability
- webhook secret verification
- inbound dedupe
- idempotent action handling
- replay-safe token handling

8. Observability and audit
- audit log for link/reject/conflict/recovery actions
- notification logs / outbox metadata
- health endpoint and operator-visible readiness

9. Functional parity for critical business flow
- same outcome as Telegram/portal for core candidate path

### Out of Scope

Не входит в first MAX wave:

- полный rewrite Telegram bot
- новый universal FSM engine для всех каналов
- full schema migration to generic messenger identities
- removal of all Telegram fields from DB
- large recruiter UX redesign for MAX operations
- advanced MAX-only rich UI beyond what is needed for parity
- non-critical reminder experiments
- bulk operational tooling unrelated to candidate core flow

### Deferred

Во вторую волну:

- full messenger identity normalization
- full retirement of legacy slot-only scheduling writes
- full unification of recruiter messaging operations across channels
- expanded MAX-native UX customizations
- deep cleanup of Telegram-bound payload names in old APIs
- richer delivery metrics and operator dashboards

## 5. Workstreams and Execution Plan

### Workstream 1. Channel Identity & Auth

Goal:
- сделать один canonical MAX candidate binding path без параллельных identity flows

Modules:
- [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- [`backend/domain/candidates/services.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/services.py)
- [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py)

Create:
- explicit internal contract docstrings/helpers for MAX binding outcomes

Change:
- standardize MAX linkage on one flow:
  - signed access token or invite token
  - session version check
  - owner ambiguity detection

Must not break:
- existing Telegram invite binding
- portal token exchange
- current MAX tests for duplicate-owner and stale-session paths

Done criteria:
- no new MAX binding path outside current audited candidate_flow/service contours
- duplicate-owner, stale-session, reused invite behavior fully covered by tests

### Workstream 2. Candidate Transport Adapter

Goal:
- harden MAX webhook runtime as transport shell only

Modules:
- [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- [`backend/core/messenger/max_adapter.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/max_adapter.py)
- [`backend/core/messenger/bootstrap.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/bootstrap.py)

Create:
- no new business layer here; only transport glue and readiness checks

Change:
- keep parsing and event routing thin
- enforce dedupe and secret verification consistently

Must not break:
- Telegram adapter bootstrap
- existing messenger registry contract

Done criteria:
- transport layer contains no new candidate business logic beyond routing, auth, dedupe and callback acknowledgement

### Workstream 3. Conversation / Questionnaire Orchestration

Goal:
- finish MAX conversational flow on top of profile/screening domain core

Modules:
- [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- optionally small shared helpers from [`backend/apps/bot/test1_validation.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/test1_validation.py)

Create:
- if needed, shared helper layer for screening validation reused by MAX and portal

Change:
- route all MAX profile/screening writes through journey step state and portal service

Must not break:
- current portal screening behavior
- candidate journey session model

Done criteria:
- MAX questionnaire no longer depends on Telegram ephemeral `StateStore`
- interruption recovery always resumes from journey state

### Workstream 4. Scheduling Integration

Goal:
- enforce one safe scheduling owner for MAX candidate writes

Modules:
- [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)
- [`backend/apps/admin_api/slot_assignments.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/slot_assignments.py)
- [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- [`backend/domain/candidates/scheduling_integrity.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/scheduling_integrity.py)

Create:
- if needed, MAX-facing wrapper around public assignment actions

Change:
- MAX must not call legacy slot-only mutations for candidate scheduling writes where assignment-owned path exists

Must not break:
- existing admin/recruiter assignment actions
- portal scheduling guards

Done criteria:
- confirm/reschedule from MAX use assignment-owned contract
- conflict states return deterministic candidate-safe messages

### Workstream 5. Reschedule / Cancellation Flows

Goal:
- align MAX reschedule and decline behavior with existing business rules

Modules:
- [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)
- [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py)

Create:
- none unless a small MAX-safe prompt helper is required

Change:
- support reschedule request, stale token handling, unavailable slot responses, recovery after interrupted request

Must not break:
- existing recruiter-side resolution flow

Done criteria:
- MAX reschedule lifecycle produces same state changes and side effects as Telegram/portal critical path

### Workstream 6. Message Formatting / UX Adaptation for MAX

Goal:
- adapt candidate-facing conversation UX to MAX without changing business semantics

Modules:
- [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- [`backend/core/messenger/protocol.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/protocol.py)
- candidate portal-related URLs in [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)

Create:
- MAX-safe button/layout helpers if needed

Change:
- tune prompts, buttons, fallback browser/mini-app entry text

Must not break:
- current signed URL/token semantics

Done criteria:
- all MAX-required prompts are understandable, deterministic and do not depend on Telegram callback semantics

### Workstream 7. Reliability / Retry / Dedupe / Replay Protection

Goal:
- unify the minimum required safeguards for MAX launch

Modules:
- [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- [`backend/core/messenger/reliability.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/reliability.py)
- [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py)
- [`backend/domain/candidates/services.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/services.py)

Create:
- none unless small shared helper is needed

Change:
- make duplicate event behavior explicit and testable
- ensure stale/replayed tokens fail closed

Must not break:
- Telegram callback token behavior
- outbox retry policy

Done criteria:
- duplicate webhook delivery, replayed callback, stale portal token and conflicting invite all behave deterministically and are audited

### Workstream 8. Logging / Metrics / Observability

Goal:
- ensure MAX launch is operable

Modules:
- [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- [`backend/apps/admin_ui/services/messenger_health.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/messenger_health.py)
- [`backend/domain/repositories.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py)

Create:
- missing operator-facing MAX readiness signals if absent

Change:
- make sure logs and health distinguish:
  - auth/secret problems
  - subscription problems
  - dedupe hits
  - candidate binding conflicts
  - delivery failures

Must not break:
- existing `/health` and system delivery-health UI assumptions

Done criteria:
- operator can answer: is MAX ready, are messages being sent, why candidate delivery is blocked

### Workstream 9. Config / Deployment / Secrets

Goal:
- make runtime configuration explicitly production-safe

Modules:
- [`backend/core/settings.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py)
- env templates
- MAX health/readiness surfaces

Create:
- no large infra rewrite

Change:
- ensure required envs are validated and surfaced

Must not break:
- local dev bootstrap (`make dev-max-bot`, `make dev-max-live`)

Done criteria:
- staging/prod fail closed on missing MAX secrets and invalid webhook readiness

### Workstream 10. Testing / Parity / Rollout Safety

Goal:
- prove MAX is not merely "working", but behaviorally aligned with core workflow

Modules:
- `tests/test_max_*`
- `tests/test_candidate_portal_api.py`
- scheduling and notification suites

Create:
- parity tests listed in section 14

Change:
- expand existing MAX/portal/scheduling suites instead of introducing test-only fake flows

Must not break:
- current passing audited MAX/portal/scheduling tranche

Done criteria:
- parity suite passes and is required before feature flag rollout

## 6. Mandatory Pre-Refactors

### Mandatory before MAX

1. Canonicalize MAX candidate write path onto journey/session state
- MAX must not depend on Telegram `StateStore`
- blocker reason: otherwise recovery semantics diverge immediately

2. Lock MAX scheduling writes to assignment-owned APIs where available
- blocker reason: dual scheduling model is the highest-risk domain area

3. Make MAX identity linkage single-path
- no second parallel "quick bind" flow
- blocker reason: duplicate-owner and stale-session risks are security-critical

4. Formalize forbidden Telegram-bound inputs in new MAX code
- no new domain/service signature may require Telegram callback semantics or Telegram chat id if generic candidate identity exists

### Can be done during MAX implementation

1. Extract minimal shared screening validation helpers
2. Reduce MAX candidate_flow business branching where thin wrappers can move into domain helper
3. Improve channel health/readiness reporting
4. Normalize selected API payload names internally where compatibility permits

### Post-launch cleanup

1. Full messenger identity normalization
2. Full removal of legacy slot-only candidate write paths
3. Cleanup of Telegram-specific columns in reusable message/scheduling entities
4. Full shared orchestration layer across Telegram/MAX/portal

## 7. Reuse / Refactor / Rewrite Matrix

| Component | Where | Reuse as-is | Reuse with adaptation | Refactor first | Rewrite | Why | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MAX webhook runtime | [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) | Yes | No | Small hardening only | No | already exists and is transport-shaped | Low |
| MAX candidate flow shell | [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py) | No | Yes | Yes | No | substantial implementation exists, but some logic should be thinned around domain boundaries | Medium |
| Messenger protocol/registry | [`backend/core/messenger/*`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger) | Yes | No | No | No | already clean abstraction | Low |
| Candidate journey core | [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py) | Yes | Yes | Small additions only | No | strongest reusable business layer | Low |
| Identity binding | [`backend/domain/candidates/services.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/services.py) | No | Yes | Yes | No | supports invite/token logic but still Telegram-first in model and API shape | High |
| Questionnaire logic | [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py), [`backend/apps/bot/test1_validation.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/test1_validation.py) | No | Yes | Yes | No | validation and question bank exist, but Telegram Test1 orchestration is mixed | Medium |
| Telegram StateStore FSM | [`backend/apps/bot/state_store.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/state_store.py) | No | No | No | No | must not be reused for MAX business flow | High |
| Scheduling access | [`backend/apps/admin_api/slot_assignments.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/slot_assignments.py) | Yes | Yes | Small cleanup | No | public candidate-facing assignment endpoints already exist | Medium |
| Slot assignment core | [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py) | Yes | No | No | No | authoritative target path | Low |
| Legacy slot-only flow | [`backend/domain/slot_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_service.py), [`backend/apps/bot/services/slot_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/slot_flow.py) | No | Partial | Yes | No | useful only where no assignment-owned equivalent exists | High |
| Audit/outbox/retry | [`backend/apps/bot/services/notification_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/notification_flow.py) | No | Yes | Yes | No | shared runtime is usable, but package ownership is Telegram-biased | Medium |
| Portal interoperability | [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py) | Yes | No | No | No | already central to resume/recovery | Low |
| Admin-triggered channel flows | [`backend/apps/admin_ui/*`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui) | No | Yes | Yes | No | admin surfaces must issue/rotate MAX access via current security model | Medium |

## 8. Detailed Functional Requirements for MAX

### 8.1 Supported MAX events

MAX v1 must support:
- `bot_started`
- `message_created`
- `message_callback`

Source:
- [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)

No other event types are required for v1 unless already needed by provider API for delivery/health.

### 8.2 Supported candidate entry states

MAX must accept these entry states:

1. Existing CRM candidate with valid signed portal access token
- expected result: candidate is resolved, active journey checked, session version validated, MAX linked if allowed

2. Existing CRM candidate with valid MAX invite token
- expected result: candidate is linked to MAX owner and resumed into current step

3. Existing already-linked MAX candidate
- expected result: bot resumes current journey/status without relinking side effects

4. Public candidate entry when `MAX_BOT_ALLOW_PUBLIC_ENTRY` is enabled
- expected result: create public placeholder candidate only if existing ownership rules allow it

MAX must reject:
- invalid invite token
- superseded/conflicting invite reuse
- session version mismatch
- ambiguous MAX owner

### 8.3 Required flow progression

Mandatory v1 journey:

```text
MAX entry
  -> candidate resolve/link
  -> ensure active journey session
  -> profile step if incomplete
  -> screening step if incomplete
  -> status / cabinet / scheduling stage if screening completed
  -> assignment-related candidate actions when pending/active meeting exists
```

### 8.4 Supported user responses

MAX must support:
- free-text answers for profile fields
- free-text answers for open screening questions
- option selection through MAX callbacks/buttons for questions with canonical options
- explicit callback actions for scheduling controls when provided

MAX must not require:
- Telegram-specific callback prefixes in shared domain logic
- Telegram-only keyboard semantics outside MAX transport adapter/payload layer

### 8.5 Required transition behavior

Mandatory transitions:
- incomplete `profile` -> `profile` remains `in_progress`
- completed `profile` -> `screening`
- incomplete `screening` -> `screening` remains `in_progress`
- completed `screening` -> `slot_selection` or `status`, depending on current candidate state
- active scheduling state -> candidate can confirm/reschedule/decline using canonical assignment actions

MAX must preserve shared candidate workflow semantics from:
- [`backend/domain/candidates/status.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status.py)
- [`backend/domain/candidates/state_contract.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/state_contract.py)

### 8.6 Continuation after interruption

MAX must resume from journey/session state, not from ephemeral transport state.

Required behavior:
- repeated `bot_started` by already linked candidate returns current step/status
- repeated text while profile incomplete continues profile
- repeated text while screening incomplete continues current unanswered question
- if screening already completed, MAX responds with current status/cabinet entry instead of restarting screening
- if active schedule exists, MAX shows current schedule-aware status instead of re-running questionnaire

### 8.7 Duplicate / replay / repeated input handling

MAX must support:
- webhook duplicate delivery dedupe
- repeated callback delivery with same semantic action producing no duplicate business side effects
- replayed stale token failing closed
- repeated invite use by same owner being idempotent where current policy allows

Expected system behavior:
- duplicate webhook event: `200 ok`, no second side effect
- replayed already-consumed or conflicting invite: deterministic rejection message, audit event
- repeated candidate confirm on already confirmed assignment: no duplicate slot mutation or duplicate delivery side effect

### 8.8 Scheduling integration errors

If scheduling integration cannot proceed, MAX must:
- never silently fall back to another write path
- surface candidate-safe explanation
- keep canonical DB state unchanged
- write audit/log entries where current infrastructure already supports it

Examples:
- no available slot -> candidate gets waiting/manual follow-up message consistent with business rule
- scheduling conflict requires repair -> candidate receives generic blocked message; no legacy slot-only fallback
- invalid or stale assignment token -> candidate receives “action unavailable / reopen current step” type response

### 8.9 Behavior when interview cannot be assigned

If no interview can be assigned:
- system must keep candidate in valid waiting state
- if business rule already supports manual availability, MAX may collect/store manual window only through canonical save path
- no ad-hoc MAX-only waiting status may be introduced

### 8.10 Compatibility with existing candidate workflow

MAX v1 must be workflow-compatible with current core:
- no separate MAX-only candidate statuses
- no separate MAX-only scheduling record type
- no separate MAX-only questionnaire persistence model
- no separate MAX-only recovery/session model

## 9. Detailed Non-Functional Requirements

### Reliability

- MAX webhook processing must be secret-protected and deduplicated.
- Business writes must be safe under repeated provider delivery.
- Delivery failures must remain observable through existing outbox/logging surfaces.

### Idempotency

- repeated webhook events must not duplicate candidate binding
- repeated scheduling actions must not duplicate slot mutations
- repeated invite/token use must follow explicit policy: idempotent for same owner where allowed, conflict for different owner

### Observability

- every critical MAX failure mode must be visible via logs and health surfaces:
  - missing/invalid webhook secret
  - subscription not ready
  - adapter missing
  - duplicate event deduped
  - candidate binding conflict
  - stale session version
  - delivery failure classification

### Testability

- new behavior must be covered by deterministic automated tests
- parity tests must use real domain services and current public contracts, not isolated speculative mocks

### Maintainability

- shared business logic belongs in domain/core modules, not in transport shell
- MAX-specific code must stay bounded to event parsing, messaging adaptation and thin orchestration

### Channel isolation

- MAX transport failures must not corrupt Telegram state
- Telegram-specific chat state must not become a dependency for MAX candidate progress

### Backward compatibility

- Telegram flow must keep working
- portal flow must keep working
- existing signed token contracts and tested candidate portal resume model must not regress

## 10. Scheduling and Interview Assignment Requirements

1. MAX candidate-side scheduling writes must prefer `SlotAssignment` services:
- `confirm_slot_assignment`
- `request_reschedule`
- `begin_reschedule_request`
- other assignment-owned actions as required

2. MAX must not introduce new direct `Slot` mutation path for candidate actions.

3. If scheduling integrity reports `needs_manual_repair`, MAX must not attempt recovery via legacy fallback.

4. Candidate-visible meeting/reschedule details in MAX must be rendered from canonical assignment/slot state, not from local transport cache.

5. Reschedule approval/replacement remains recruiter/admin responsibility through existing surfaces unless an audited candidate-side contract already exists.

6. If candidate already has active assignment-owned schedule, MAX must show current state instead of offering a fresh slot selection branch.

## 11. Identity / Security / Idempotency Requirements

1. One canonical MAX linking path.
- No new secondary “fast bind” flow.

2. Identity source hierarchy:
- signed candidate portal access token
- invite token
- existing `max_user_id` link
- public entry only when explicitly enabled

3. Security checks required before candidate linkage:
- owner ambiguity detection
- session version validation
- invite conflict validation
- stale token rejection

4. No new shared domain entity may add Telegram-bound linkage fields for MAX delivery.

5. Any new reusable service interface must prefer channel-neutral identifiers:
- `candidate_id`
- `candidate_uuid`
- `messenger_platform`
- provider-specific user id only at transport boundary

6. Replay and duplicate handling:
- webhook dedupe required
- action token single-use semantics preserved
- no duplicate outbox side effects on repeated callback handling

## 12. UX / Conversation Adaptation Requirements for MAX

1. Preserve business semantics, adapt transport presentation.

2. MAX prompts must support:
- profile entry
- questionnaire answers
- recovery after interruption
- active-candidate redirect to current step/status
- scheduling confirmations and errors

3. MAX UX must not depend on Telegram-only affordances:
- no assumption of Telegram inline keyboard wording/layout
- no Telegram-specific deep-link copy in MAX candidate text
- no `tg://` links in MAX candidate responses

4. Candidate should always receive an actionable next step:
- answer profile field
- answer current question
- open cabinet
- confirm/reschedule current meeting
- contact recruiter only when canonical flow says no automatic scheduling path exists

5. Error messaging must distinguish:
- invalid input
- stale or invalid link
- already active existing progress
- scheduling temporarily unavailable

## 13. Forbidden Contracts and Anti-Patterns

## Forbidden in new MAX scope

1. Не добавлять новые Telegram-bound поля в shared domain entities.

2. Не делать MAX business logic как copy-paste ветку из Telegram handlers/services.

3. Не использовать [`backend/apps/bot/state_store.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/state_store.py) как source of truth для MAX candidate progress.

4. Не добавлять новый parallel scheduling write path мимо `SlotAssignment` там, где assignment-owned contract уже существует.

5. Не добавлять новый способ candidate identity linkage помимо audited token/invite/owner flow.

6. Не вводить MAX-only shared workflow statuses без отдельной domain abstraction.

7. Не тянуть Telegram callback payload semantics в shared orchestration layer.

8. Не полагаться на `candidate_tg_id` как единственный identity input в новых reusable service contracts.

9. Не обходить existing idempotency and dedupe safeguards ради “удобного” happy path.

10. Не делать silent fallback из MAX в legacy slot-only mutation при scheduling conflict.

11. Не хранить MAX-specific candidate progress в transport-local памяти без DB-backed journey/session sync.

## 14. Parity Test Plan

### 14.1 Contract parity tests

#### Status transition parity
Check:
- same candidate scenario in Telegram/portal/MAX reaches same `candidate_status`

Why critical:
- status drift breaks recruiter UI and downstream actions

Expected result:
- identical final status and compatible journey state

#### Screening persistence parity
Check:
- same answers persist to same journey/screening structures and, where applicable, same downstream result records

Why critical:
- avoids parallel questionnaire implementations

Expected result:
- identical saved answers and same completion side effects

#### Scheduling side effect parity
Check:
- confirm/reschedule/decline produce same assignment/slot mutations and outbox behavior

Why critical:
- scheduling is highest-risk domain

Expected result:
- same `SlotAssignment` and `Slot` final state, same notification/audit expectations

### 14.2 Flow parity tests

#### Happy path candidate flow
Check:
- start -> profile -> screening -> status/scheduling

Expected:
- journey progresses without channel-specific divergence

#### Invalid answer handling
Check:
- invalid FIO/phone/city/option

Expected:
- same validation rule, no partial invalid state commit

#### Interrupted conversation recovery
Check:
- candidate leaves after profile or mid-screening and returns

Expected:
- resume from current journey state, no restart

#### Reschedule path
Check:
- candidate with active assignment requests new time

Expected:
- `RescheduleRequest` created or updated through canonical service path

#### Cancellation / decline path
Check:
- decline current assignment from MAX

Expected:
- same status and slot release semantics as current core rules

#### Duplicate event path
Check:
- same webhook delivered twice

Expected:
- no duplicate side effects

#### Replayed update path
Check:
- same callback/token reused after consumption

Expected:
- rejected or idempotent according to contract, but never duplicated side effects

#### Already-bound candidate path
Check:
- candidate already linked to MAX re-enters

Expected:
- current step/status rendered, no rebind conflict

### 14.3 Integration tests

#### Scheduling sync
Check:
- assignment confirm keeps `Slot` and `SlotAssignment` in sync

Expected:
- no split-brain after candidate action

#### Slot reservation consistency
Check:
- reschedule replacement frees old slot and binds new slot

Expected:
- one active owner only

#### Portal / MAX interoperability
Check:
- signed browser/mini-app/MAX entry all resolve same candidate journey

Expected:
- same candidate, same session-version guarantees, same current step

#### Audit / outbox behavior
Check:
- binding conflict, stale token, successful confirm/reschedule all emit expected logs

Expected:
- operator can reconstruct incident path

#### Retry semantics
Check:
- delivery failures classify consistently for MAX

Expected:
- transient retry, permanent/misconfiguration dead-letter semantics preserved

### 14.4 Negative / edge tests

#### Duplicate update
- expected: deduped, no duplicate writes

#### Stale token
- expected: fail closed, no relink, no progress mutation

#### Double booking attempt
- expected: rejected through canonical scheduling conflict path

#### Candidate re-entry after partial completion
- expected: resume current step, no duplicate screening completion

#### Channel mismatch
- expected: candidate linked to one owner/channel cannot hijack another candidate path

#### Concurrent schedule write
- expected: one winner, no inconsistent active slot/assignment pair

#### Invalid candidate state restore
- expected: candidate gets safe blocked/recovery message, not silent corruption

## 15. Rollout Plan

### 15.1 Feature flag strategy

Use staged enablement:
- `MAX_BOT_ENABLED`
- `MAX_BOT_ALLOW_PUBLIC_ENTRY`
- optional internal rollout flag for recruiter-visible issuing of MAX links if needed

Policy:
- public entry stays off until parity suite and pilot are complete
- invite-based/internal candidate rollout can start earlier

### 15.2 Hidden/internal testing phase

Before pilot:
- enable MAX only for internal QA candidates or operator-driven test cohort
- verify:
  - entry/link
  - profile/screening
  - scheduling action roundtrip
  - logs/health/readiness

### 15.3 Pilot cohort

Pilot should be small and explicit:
- limited recruiters
- limited cities
- limited candidate segment

Why:
- scheduling integrity and identity conflicts are easier to observe/rollback

### 15.4 Observability checklist before launch

Required:
- MAX `/health` reports ready state
- messenger health surface shows MAX readiness and failure reason
- audit log captures link conflict and stale-session rejection
- notification logs/outbox show channel-specific delivery outcome
- duplicate webhook hits are observable

### 15.5 Fallback / rollback

Fallback rule:
- if MAX candidate flow hits blocker-level production issues, recruiter/admin continues using portal or Telegram entry without changing shared candidate workflow model

Rollback approach:
- disable MAX via feature flag
- keep shared journey/scheduling data intact
- do not run destructive schema rollback as part of first operational response

### 15.6 Post-launch verification

After enablement verify:
- successful link rate
- screening completion rate
- scheduling action success rate
- duplicate/replay rejection counts
- dead-letter / misconfiguration spikes
- no increase in scheduling conflicts caused by MAX path

### 15.7 Success metrics

Track:
- MAX start -> linked candidate conversion
- linked candidate -> screening completed conversion
- screening completed -> scheduling action success
- assignment confirm/reschedule success
- outbox send success for MAX
- number of stale-token / conflict / duplicate-owner incidents

### 15.8 Blockers for rollout

Block rollout if any of these occur:
- repeated duplicate-owner ambiguities without safe operator handling
- scheduling split-brain caused by MAX path
- webhook secret/subscription readiness unstable
- high rate of stale-session or invalid-link false positives
- MAX outbox channel enters persistent degraded state

## 16. Deliverables Checklist

| Deliverable | Priority | Owner | Done criteria |
| --- | --- | --- | --- |
| MAX candidate flow spec-compliant routing | Mandatory | backend/bot | MAX events map to canonical journey/scheduling behavior |
| Canonical MAX identity linkage path | Mandatory | backend | no parallel bind path, tested stale/conflict handling |
| MAX screening/profile resume behavior | Mandatory | backend | journey-backed resume works after interruption |
| Assignment-owned MAX scheduling actions | Mandatory | backend | confirm/reschedule use canonical services |
| MAX reliability guards | Mandatory | backend/infra | secret verification, dedupe, replay-safe actions pass tests |
| MAX observability/readiness surface | Mandatory | backend/infra | health and logs explain blocked states |
| Parity contract suite | Mandatory | QA/backend | parity tests pass in CI/local gate |
| Pilot rollout flagging | Mandatory | backend/infra | internal-only rollout possible without code changes |
| UX text/button adaptation for MAX | Desirable | bot/product/backend | candidate messages are channel-appropriate |
| Post-launch cleanup backlog | Desirable | backend | explicit deferred list recorded and prioritized |

## 17. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| MAX implementation reuses Telegram local state | progress divergence and broken resume | forbid `StateStore` as source of truth for MAX |
| MAX path writes through legacy slot-only flow | scheduling inconsistency | force assignment-owned writes and parity tests |
| New MAX bind path bypasses audited token/session rules | identity takeover/conflicts | single canonical binding path only |
| Transport-specific copy-paste grows | long-term maintenance debt | keep business logic in portal/domain core |
| Weak observability hides rollout failures | slow incident response | mandatory health/log/readiness checklist before pilot |

## 18. Final Recommendation

Start MAX delivery now, but only with a bounded implementation plan:
- do the mandatory pre-refactors first or in the opening tranche
- keep MAX on top of journey/session and assignment-owned scheduling
- reject any shortcut that copies Telegram business flow into a separate MAX branch

Recommended implementation order:
1. lock identity + security + dedupe contract
2. lock scheduling write-owner contract
3. finish MAX questionnaire/resume behavior
4. finish candidate scheduling actions
5. complete parity suite
6. ship behind feature flag to pilot

## GO / NO-GO RECOMMENDATION FOR MAX DELIVERY

1. Можно ли начинать реализацию сразу?
   Да, но не с прямой feature-build поверх текущего MAX flow. Начинать нужно с bounded pre-refactor tranche по identity, scheduling write-owner и forbidden contract enforcement.

2. Какие pre-refactors являются обязательными blocker’ами?
   - MAX progress must be journey-backed, not Telegram-state-backed
   - MAX scheduling writes must use assignment-owned path where available
   - MAX identity linkage must remain single-path with stale/conflict checks

3. Какой минимальный безопасный scope для первого запуска?
   - invite/signed-token based MAX entry
   - profile + screening
   - current-status/cabinet resume
   - confirm/reschedule current interview through canonical assignment API
   - health/audit/dedupe/feature flag rollout

4. Какая стратегия даст наилучший баланс скорости и качества?
   `частичный рефакторинг + реализация MAX`

5. Какие 5 ошибок наиболее вероятны при неправильной реализации?
   - reuse Telegram `StateStore` as MAX business state
   - add a second MAX binding path outside audited token/session model
   - call legacy slot-only writes from MAX candidate actions
   - copy-paste Telegram handler logic into MAX flow
   - ship without parity tests for duplicate/replay/scheduling consistency
