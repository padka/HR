# MAX Execution Master Plan

## 1. Executive Summary

Current MAX program state is `CONDITIONAL GO`, but the pilot is still blocked operationally.

Code-closed today:
- B1. MAX `WebAppData` auth facade
- B2. Production-safe dedupe at code level

Still operationally open:
- B2. live pilot-env proof
- B3. real cohort proof
- B4. real-client smoke
- B5. moderation / business / owner bundle

What can be executed now:
- readiness and rollout guardrails
- operator-visible MAX health consolidation
- structured regression proof for rollout defaults
- candidate continuity and recovery hardening on shared contracts only
- scheduling regression hardening on the canonical path only

## 2. Current State Consolidation

Architecture decisions already fixed in live code and current docs:
- MAX mini app uses the shared `/api/candidate/*` path.
- MAX auth/session bootstrap stays on the shared candidate portal/session exchange contract.
- Candidate journey state is DB-backed and transport-neutral.
- Scheduling remains canonical and shared; no MAX-only write path is allowed.
- Browser portal fallback is allowed.
- Telegram business fallback is forbidden.
- Public entry stays off by default.

Backlog and rollout implications:
- B1/B2 are code-closed inputs for this phase, not redesign targets.
- B3/B4/B5 remain hard pilot blockers and must not be masked by code changes.
- Batch work must improve control, continuity, or proof quality without widening launch surface.

## 3. Workstream Map

- Shared backend hardening
  - production config fail-fast
  - runtime readiness payloads
  - machine-readable rollout guardrails
- Bot flow completion
  - reminder continuity
  - exact-state re-entry
- Mini app / candidate UX completion
  - deterministic recovery states
  - explicit browser fallback path
  - authoritative dashboard signaling
- Scheduling continuity
  - restore / replace / ownership regressions only
- Observability / guardrails
  - unified MAX readiness view
  - structured failure taxonomy
- Proof / testing / regression
  - config validation
  - readiness payload coverage
  - continuity / restart regressions
- Pilot evidence preparation
  - tooling and payloads that support B2/B3/B4/B5 evidence collection
- Operational handoff items
  - live pilot-env proof
  - real cohort proof
  - real-client smoke
  - moderation/business/owner bundle

## 4. Priority Plan

### Execute Now

- `MP-01` write this master plan from live code and current docs
- `NOW-01` tighten MAX production config validation
- `NOW-02` expose a unified MAX readiness view
- `NOW-03` instrument machine-readable guardrails and fallback markers
- `NOW-04` add regression tests for config fail-fast, readiness payloads, and rollout defaults

### Execute Next

- `NEXT-01` normalize reminder payloads and exact-state re-entry on shared journey/session state
- `NEXT-02` harden candidate start/journey recovery UX and browser fallback UX
- `NEXT-03` expand interrupted-flow, restart, stale-cookie, and reminder re-entry coverage

### Execute Only After Current Batch

- `LATER-01` expand scheduling restore / ownership / idempotency regression suite on the canonical path only

### Operational / External / Not Code-Closable

- `EXT-01` live pilot-env proof for MAX health, Redis dedupe, and webhook subscription
- `EXT-02` real cohort audit export, exclusion log, and signed allowlist
- `EXT-03` real-client smoke matrix with archived transcripts and fallback decisions
- `EXT-04` moderation, business, and named-owner approval bundle

## 5. Task Execution Table

| Task ID | Workstream | Description | Owner Type | Priority | Dependency | Can start now? | Done Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MP-01 | Program | Write `MAX_EXECUTION_MASTER_PLAN_2026-04-09.md` from live code and current docs | Program Orchestrator | P0 | none | Yes | Document exists and separates code-closed from operationally-open items |
| NOW-01 | Readiness | Tighten MAX production config validation for webhook URL, portal public URL, link base shape, and Redis-backed ingress posture | Backend Platform + Infra | P0 | none | Yes | Prod-like misconfig fails closed with explicit reason; dev/test semantics unchanged |
| NOW-02 | Readiness | Expose one unified MAX readiness view for webhook, subscription, dedupe, portal readiness, auth posture, and public-entry state | Backend Platform + Frontend/Admin | P1 | NOW-01 | Yes | Operators can read one coherent MAX readiness surface without cross-checking separate payloads |
| NOW-03 | Guardrails | Instrument structured MAX failure taxonomy and fallback markers | Backend Platform + Infra | P1 | NOW-02 | Yes | Dedupe, webhook, subscription, and fallback states are machine-readable and test-covered |
| NOW-04 | QA | Add regression tests for config fail-fast, readiness payloads, and rollout defaults | QA + Backend + Frontend | P0 | NOW-01, NOW-02, NOW-03 | Yes | Targeted tests pass and prove public entry remains off by default |
| NEXT-01 | Bot/Domain | Normalize reminder payloads and exact-state re-entry on shared journey/session state | Bot/Integration + Backend Messaging | P1 | NOW-04 | No | Reminder entry reopens the exact current step or safe recovery state |
| NEXT-02 | Frontend | Harden candidate start/journey recovery UX and browser fallback UX on existing shared contracts | Frontend/Mini App | P1 | NOW-04 | No | Stale link, missing bridge, reload, and resume states are deterministic and explicit |
| NEXT-03 | QA | Expand interrupted-flow, restart, stale-cookie, and reminder re-entry regression coverage | QA + Full-stack | P0 | NEXT-01, NEXT-02 | No | Tests prove exact-state continuity without duplicate writes or state reset |
| LATER-01 | Scheduling | Expand scheduling restore / ownership / idempotency regression suite only on the canonical path | Backend Domain + QA | P1 | NEXT-03 | No | Assignment-owned scheduling stays authoritative across replace / cancel / retry / conflict |
| EXT-01 | Operational | Run live pilot-env proof for health, Redis dedupe, and webhook subscription | Infra/SRE + Security | P0 | code batches complete | No | Archived pilot-env readiness bundle exists |
| EXT-02 | Operational | Run real cohort audit and freeze signed allowlist | Backend Domain + Product Ops | P0 | existing tooling | No | Actual cohort audit export, exclusion log, and signed allowlist exist |
| EXT-03 | Operational | Run real-client smoke matrix for `deep-link`, `open_app`, `requestContact`, resume/back-close, and reminder re-entry | QA + Product Ops + Frontend/Bot | P0 | NEXT-03 | No | Archived pass/fail matrix with fallback decisions exists |
| EXT-04 | Operational | Collect moderation, business, and named-owner approval bundle | Product Ops + Launch Lead | P0 | EXT-01, EXT-02, EXT-03 | No | Approval artifacts are archived and match pilot restrictions |

## 6. Restrictions and Non-Negotiables

- Public entry stays off by default.
- Telegram business fallback is forbidden.
- Browser portal fallback is allowed.
- No MAX-only backend path.
- No second scheduling write path.
- No weakening of auth, dedupe, or shared session integrity.
- No code change may be used to declare B3/B4/B5 closed.
- No batch may widen cohort, enable public entry, or treat pilot start as code-complete.

## 7. Implementation Sequence

### Batch 1

Scope:
- `MP-01`
- `NOW-01`
- `NOW-02`
- `NOW-03`
- `NOW-04`

Rationale:
- improves rollout control immediately
- makes restrictions operator-visible
- does not widen the launch surface

Risks:
- touching MAX runtime health and settings validation is high risk; changes must stay additive and fail-closed only in prod-like mode

Proof expectations:
- targeted readiness/config tests pass
- admin delivery-health tests pass
- no change to shared candidate/session/scheduling contracts
- explicit proof that public entry remains off by default

### Batch 2

Scope:
- `NEXT-01`
- `NEXT-02`
- `NEXT-03`

Rationale:
- strengthens exact-state continuity after Batch 1 guardrails are stable
- keeps browser fallback explicit and safe

Risks:
- continuity work must not drift into MAX-only state handling or Telegram logic reuse

Proof expectations:
- interrupted-flow and recovery tests pass
- reminder re-entry tests pass
- stale-cookie/version mismatch still fail closed

### Batch 3

Scope:
- `LATER-01`

Rationale:
- hardens scheduling only after continuity paths are stable

Risks:
- scheduling regression work must stay on the canonical assignment-owned path

Proof expectations:
- restore / replace / ownership / retry regressions pass
- no slot-only fallback path is introduced

## 8. Deferred / External Items

- B2 live pilot-env proof
- B3 real cohort proof
- B4 real-client smoke
- B5 moderation / business / owner bundle
- actual pilot start
- public-entry enablement
- cohort expansion

These items remain outside code closure for this execution phase.

## 9. Definition of Done for Current Execution Phase

This execution phase is done when:
- the master plan exists and reflects live code truth
- Batch 1 is implemented and accepted
- Batch 2 is implemented and accepted
- Batch 3 is implemented if scheduling coverage still has a meaningful gap
- conditional-go restrictions remain explicit in code and operator surfaces
- code-closed items are backed by tests
- operational blockers are still called out as open where applicable
