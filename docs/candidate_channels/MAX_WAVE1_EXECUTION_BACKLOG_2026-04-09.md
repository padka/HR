# MAX Wave 1 Execution Backlog

Дата: `2026-04-09`

Source of truth:
- [MAX_BOT_READINESS_AUDIT_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md)
- [MAX_IMPLEMENTATION_SPEC_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_IMPLEMENTATION_SPEC_2026-04-09.md)
- [MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md)
- [MAX_RECRUITSMART_ARCHITECTURE_AND_ROADMAP_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_RECRUITSMART_ARCHITECTURE_AND_ROADMAP_2026-04-09.md)

Backlog assembly mode:
- multi-agent synthesis
- specialized inputs used: backend/domain, bot/integration, mini app/frontend, security/identity, QA/validation, infra/rollout
- Lead Architect resolved overlaps, conflicts, and phase boundaries into one Wave 1 execution plan

## 1. Executive Summary

Wave 1 for MAX in RecruitSmart should ship the minimum launchable `bot + mini app` candidate path on top of the existing shared backend core.

The minimum safe production scope is:
- MAX bot entry with stable webhook ingress
- canonical candidate binding and session bootstrap
- MAX mini app entry through the shared candidate portal/session model
- shared journey/profile/screening progression
- scheduling through one canonical write path
- bot-to-mini-app handoff and reminder-driven re-entry
- pilot-grade security, observability, test coverage, and rollback controls

The main architectural rule for all tasks in this backlog:
- do not create a MAX-only backend path
- do not let MAX mini app drift into legacy Telegram webapp contracts
- do not allow MAX to open a second scheduling write path
- do not duplicate Telegram business logic in MAX handlers

Wave 1 is complete only when:
- a pilot candidate can start in MAX, complete profile/screening, book or resume scheduling, and recover after interruption
- shared journey/session and scheduling state remain authoritative
- duplicate/replay/idempotency safeguards are proven
- rollout gates, smoke validations, and rollback path are ready

## 2. Wave 1 Scope

### In scope

- MAX webhook ingress and readiness
- MAX candidate entry and attribution
- MAX identity binding with deterministic conflict handling
- MAX mini app auth/bootstrap onto shared candidate portal session
- shared journey/profile/screening flow
- scheduling, reschedule, cancel through canonical backend path
- bot reminders, confirmations, and exact-state re-entry
- pilot feature flags and cohort gating
- critical validation suite and manual client smoke

### Explicitly out of scope for Wave 1 minimum launch

- channels as a required funnel surface
- QR, document capture, biometry, or other advanced client capabilities
- full messenger identity normalization across the whole schema
- Telegram rewrite
- MAX-only recruiter operator tooling
- large-scale dashboard or analytics redesign beyond pilot readiness

### Minimum launchable Wave 1 scope

The minimum pilot-safe scope is:
1. invite or controlled cohort entry in MAX
2. contact capture and basic qualification in bot
3. exact-state handoff to mini app
4. shared profile/screening flow in mini app
5. scheduling through shared candidate portal/scheduling services
6. reminders and re-entry from bot
7. blocking tests, smoke validations, and rollout gates green

## 3. Epic Breakdown

### Table 1. Epic Overview

| Epic | Goal | Business Value | Complexity | Dependencies | Done Criteria | Owner Type |
| --- | --- | --- | --- | --- | --- | --- |
| E1. Security and Ingress Foundation | Make MAX ingress and mini app auth safe for pilot | High | High | secrets, webhook infra, bot token | webhook/auth fail closed, replay-safe, observable | Backend Platform + Security |
| E2. Identity and Session Contract | Establish one canonical MAX candidate binding and resume model | High | High | E1 | one binding path, deterministic conflicts, shared session bootstrap | Backend Domain |
| E3. Shared Journey and Resume Core | Keep MAX mini app on shared candidate portal/journey path | High | Medium-High | E2 | one journey/session contract, interruption recovery works | Backend Domain |
| E4. Scheduling Path Consolidation | Force candidate scheduling onto one canonical write path | High | High | E3 | no direct divergent slot writes for MAX, repair gates enforced | Backend Domain |
| E5. Bot Entry, Handoff, and Reminder Continuity | Make bot the reliable entry and re-entry shell | High | Medium | E1, E2, E3 | exact-state handoff and reminder continuity proven | Bot/Integration |
| E6. Mini App Wave 1 UX Surface | Deliver entry, dashboard, screening, scheduling, and recovery UX | High | Medium-High | E3, E4, E5 | candidate can complete and resume the flow inside MAX | Frontend/Mini App |
| E7. Observability, Rollout Controls, and Pilot Ops | Make rollout controllable, visible, and reversible | High | Medium | E1-E6 core signals | readiness dashboard, feature flags, runbook, fallback ready | Infra/SRE + Product Ops |
| E8. Validation and Pilot Certification | Prove parity, continuity, idempotency, and rollback safety | High | Medium | E1-E7 | blocker suite green, smoke evidence captured, pilot sign-off possible | QA/Validation |

## 4. Task Backlog by Epic

### Table 2. Task Backlog

| Task ID | Epic | Title | Priority | Owner | Parallelizable | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WF1-SEC-01 | E1 | Fail closed on missing/invalid MAX prod config | P0 | Backend Platform + Security | Yes | none | Production startup blocks when `MAX_WEBHOOK_SECRET`, `MAX_WEBHOOK_URL`, `MAX_BOT_TOKEN`, `MAX_BOT_LINK_BASE`, or `CANDIDATE_PORTAL_PUBLIC_URL` are missing/invalid; health explains exact block reason |
| WF1-SEC-02 | E1 | Require Redis-backed dedupe and safe webhook ingress policy in prod | P0 | Backend Platform | No | WF1-SEC-01 | Duplicate callback/message/body deliveries do not cause duplicate side effects; prod does not rely on in-memory dedupe; handled internal failures follow explicit retry-safe policy |
| WF1-SEC-03 | E1 | Implement MAX-specific `WebAppData` auth facade | P0 | Backend Platform + Security | Yes | WF1-SEC-01 | Server validates `WebAppData`, checks freshness, rejects tampered/stale payloads, and exposes normalized MAX context without trusting client state |
| WF1-ID-01 | E2 | Normalize MAX owner keys and channel inputs | P0 | Backend Domain | Yes | none | `max_user_id` normalization is shared everywhere; channel aliases normalize deterministically; whitespace-only or ambiguous values never auto-merge |
| WF1-ID-02 | E2 | Produce pilot owner preflight report | P0 | Backend Domain + DB | Yes | WF1-ID-01 | Report lists duplicate owners, whitespace anomalies, invite conflicts, and journey collisions; `ready_for_pilot=false` when blockers exist |
| WF1-ID-03 | E2 | Collapse MAX binding onto one canonical resolver | P0 | Backend Domain | No | WF1-ID-01, WF1-SEC-03 | `bot_started`, `message_created`, `message_callback`, invites, and signed launches resolve through one path; duplicate owner, reused invite, and stale session reject deterministically and are audited |
| WF1-SES-01 | E2 | Freeze MAX launch/session version contract | P0 | Backend Domain | No | WF1-ID-03 | MAX launch tokens require matching `journey_session_id` and `session_version`; stale or foreign version is rejected before any mutation |
| WF1-SES-02 | E3 | Make candidate portal session payload the single resume contract | P0 | Backend Domain | No | WF1-SES-01 | MAX, web portal, and Telegram-compatible flows resume from the same session payload and `CandidateJourneySession`; no transport-local progress state is required |
| WF1-SES-03 | E3 | Isolate MAX launch token helpers behind shared entry contract | P1 | Backend Domain | Yes | WF1-SES-01 | MAX launch URL generation remains available, but journey/session logic sees one channel-neutral entry contract |
| WF1-SES-04 | E3 | Make interruption recovery journey-state only | P0 | Backend Domain | Yes | WF1-SES-02 | Profile and screening resume after restart using DB-backed journey/step state only; no Telegram state store dependency remains on MAX path |
| WF1-SCH-01 | E4 | Introduce candidate scheduling facade | P0 | Backend Domain | No | WF1-SES-02 | All candidate-facing scheduling writes go through one shared entrypoint that selects canonical behavior |
| WF1-SCH-02 | E4 | Route `/api/candidate/slots/*` writes through facade and block divergent slot-only writes | P0 | Backend Domain | No | WF1-SCH-01 | Reserve, confirm, cancel, and reschedule for MAX use the facade; `SlotAssignment` is authoritative whenever assignment-owned scheduling exists |
| WF1-SCH-03 | E4 | Enforce repair gate and no silent fallback on split-brain scheduling states | P0 | Backend Domain | Yes | WF1-SCH-01 | Manual-repair or ownership-conflict states fail deterministically; no fallback to legacy slot-only mutation occurs |
| WF1-SCH-04 | E4 | Add regression fixtures for assignment conflicts and restore | P1 | Backend Domain + QA | Yes | WF1-SCH-02, WF1-SCH-03 | Tests cover duplicate active assignments, old-slot release, cross-owner claims, and retry idempotency |
| WF1-BOT-01 | E5 | Finalize webhook subscription lifecycle and callback/message ack policy | P0 | Bot/Integration + Backend Platform | Yes | WF1-SEC-01, WF1-SEC-02 | One active subscription is reconciled; stale subscriptions are pruned; callback acks happen only after durable processing; retry storms are avoided |
| WF1-BOT-02 | E5 | Use one server-side continuation path for all MAX bot events | P0 | Bot/Integration | Yes | WF1-ID-03, WF1-SES-01 | `process_bot_started`, `process_text_message`, and `process_callback` share one continuation contract and never route through Telegram handlers or state storage |
| WF1-BOT-03 | E5 | Build exact-state bot -> mini app handoff envelope | P0 | Bot/Integration + Backend Domain | No | WF1-BOT-02, WF1-SES-03 | Handoff includes `candidate_uuid`, `journey_session_id`, `session_version`, `source_channel`, signed `startapp` URL, and browser fallback generated from the same state |
| WF1-BOT-04 | E5 | Normalize reminder and re-entry continuity | P1 | Bot/Integration + Backend Messaging | Yes | WF1-BOT-03, WF1-SES-02 | Reminder payloads reopen the exact journey state; stale links are rejected or refreshed; no Telegram callback assumptions leak into MAX reminders |
| WF1-UI-01 | E6 | Harden mini app entry and recovery state machine | P0 | Frontend/Mini App + Backend Contract | No | WF1-SES-02, WF1-BOT-03, WF1-SEC-03 | Route token, `startapp` param, and stored resume token resolve to the same deterministic entry state; blocked/stale cases show recovery CTA |
| WF1-UI-02 | E6 | Make journey dashboard the single authenticated home surface | P0 | Frontend/Mini App | Yes | WF1-UI-01 | Current step, next action, alerts, and active slot are visible above the fold; the candidate lands on one authoritative home screen |
| WF1-UI-03 | E6 | Deliver scheduling action surface on shared `/api/candidate/slots/*` contracts | P0 | Frontend/Mini App + Backend Contract | No | WF1-SCH-02, WF1-UI-01 | Candidate can reserve, confirm, cancel, and reschedule in mini app; invalid transitions are hidden or disabled; state returns to dashboard correctly |
| WF1-UI-04 | E6 | Implement interrupted-flow recovery UX and fallback states | P0 | Frontend/Mini App | Yes | WF1-UI-01, WF1-BOT-04 | Expired link, session mismatch, reload interruption, and missing bridge all lead to explicit recovery states with safe next actions |
| WF1-UI-05 | E6 | Polish profile/screening draft flow and return-to-chat CTA | P1 | Frontend/Mini App | Yes | WF1-UI-02 | Draft save is visible, progress survives reload, and each eligible state offers one clear return-to-chat action |
| WF1-OPS-01 | E7 | Expose unified MAX readiness and blocker view | P1 | Infra/SRE + Backend Platform | Yes | WF1-SEC-01, WF1-BOT-01 | Operators can see webhook readiness, subscription status, portal readiness, token validity, and delivery blockers in one place |
| WF1-OPS-02 | E7 | Instrument MAX failure taxonomy and delivery health | P1 | Infra/SRE + Backend Platform | Yes | WF1-BOT-01, WF1-BOT-02, WF1-SCH-03 | Logs/metrics separate auth reject, secret missing, subscription drift, dedupe hit, stale token, binding conflict, queue stall, and delivery failure |
| WF1-OPS-03 | E7 | Add feature flags and pilot cohort gating policy | P0 | Infra/SRE + Product Ops + Backend Platform | Yes | WF1-SEC-01, WF1-ID-02 | `MAX_BOT_ENABLED` and `MAX_BOT_ALLOW_PUBLIC_ENTRY` are controllable; pilot-only routing is possible; non-pilot users fall back without side effects |
| WF1-OPS-04 | E7 | Produce pilot runbook, moderation checklist, and rollback rehearsal | P1 | Infra/SRE + Product Ops | No | WF1-OPS-01, WF1-OPS-03 | Named owners, escalation path, moderation readiness, smoke evidence checklist, and config-based rollback are documented and rehearsed |
| WF1-QA-01 | E8 | Add stale `mx1` launch-token and session-mismatch regression coverage | P0 | QA + Backend | Yes | WF1-SEC-03, WF1-SES-01 | Stale launch token returns `401`, clears resume/session state, logs mismatch, and mutates nothing |
| WF1-QA-02 | E8 | Add interrupted bot -> mini app exact-state resume coverage | P0 | QA + Full-stack | No | WF1-BOT-03, WF1-UI-01, WF1-UI-04 | Mid-profile or mid-screening interruption resumes on the exact step without duplicate `screening_started` or state reset |
| WF1-QA-03 | E8 | Extend duplicate/replay webhook and duplicate-press coverage | P0 | QA + Backend | Yes | WF1-BOT-01, WF1-BOT-02 | Duplicate `message_created`, `message_callback`, and repeated button presses never duplicate writes or notifications |
| WF1-QA-04 | E8 | Add scheduling restore/replace/ownership regression suite | P0 | QA + Backend Domain | Yes | WF1-SCH-02, WF1-SCH-03, WF1-UI-03 | Slot and assignment remain synchronized; old slot is released; candidate-side scheduling stays on assignment-owned path |
| WF1-QA-05 | E8 | Add portal restart, stale-cookie, and resume coverage | P0 | QA + Backend | Yes | WF1-SES-02, WF1-UI-04 | Valid resume cookie restores journey, version bump forces fresh link, and stale cookie is cleared safely |
| WF1-QA-06 | E8 | Execute real-client MAX smoke matrix | P1 | QA + Product Ops | No | WF1-UI-01, WF1-BOT-03, WF1-OPS-03 | Supported pilot clients pass smoke for deep links, callbacks, `open_app`, `requestContact`, re-entry, and close/back behavior |
| WF1-QA-07 | E8 | Run end-to-end PostgreSQL-backed pilot path | P1 | QA + Backend + Frontend | No | all Wave 1 P0 flow tasks | A candidate can go from MAX entry to booked interview through shared backend contracts without duplicate side effects |

### Epic notes

Critical architecture-stability tasks:
- `WF1-SEC-03`
- `WF1-ID-03`
- `WF1-SES-02`
- `WF1-SCH-02`
- `WF1-BOT-03`

Critical UX-continuity tasks:
- `WF1-BOT-04`
- `WF1-UI-01`
- `WF1-UI-02`
- `WF1-UI-04`
- `WF1-QA-02`

Critical pilot-rollout tasks:
- `WF1-OPS-03`
- `WF1-OPS-04`
- `WF1-QA-06`
- `WF1-QA-07`

## 5. Dependency Graph

### High-level dependency graph

```text
E1 Security and Ingress Foundation
  -> E2 Identity and Session Contract
    -> E3 Shared Journey and Resume Core
      -> E4 Scheduling Path Consolidation
      -> E5 Bot Entry, Handoff, and Reminder Continuity
        -> E6 Mini App Wave 1 UX Surface
          -> E8 Validation and Pilot Certification

E1 + E5 + E6
  -> E7 Observability, Rollout Controls, and Pilot Ops
  -> E8 Validation and Pilot Certification
```

### Task-level dependency spine

```text
WF1-SEC-01 -> WF1-SEC-02
WF1-SEC-01 -> WF1-SEC-03
WF1-ID-01 -> WF1-ID-02 -> WF1-OPS-03
WF1-ID-01 + WF1-SEC-03 -> WF1-ID-03 -> WF1-SES-01 -> WF1-SES-02
WF1-SES-02 -> WF1-SCH-01 -> WF1-SCH-02 -> WF1-UI-03 -> WF1-QA-04
WF1-SES-02 -> WF1-BOT-02 -> WF1-BOT-03 -> WF1-UI-01 -> WF1-UI-02
WF1-BOT-03 -> WF1-BOT-04 -> WF1-UI-04 -> WF1-QA-02
WF1-BOT-01 + WF1-SEC-02 -> WF1-QA-03
WF1-SEC-03 + WF1-SES-01 -> WF1-QA-01
WF1-OPS-01 + WF1-OPS-02 + WF1-OPS-04 + WF1-QA-06 + WF1-QA-07 -> Pilot Go/No-Go
```

### Safe parallel workstreams

After `WF1-SEC-01`, `WF1-ID-01`, and `WF1-SEC-03` are in progress, these tracks can run largely in parallel:
- Track A: identity/session core
  - `WF1-ID-02`, `WF1-ID-03`, `WF1-SES-01`, `WF1-SES-02`
- Track B: ingress and bot shell
  - `WF1-SEC-02`, `WF1-BOT-01`, `WF1-BOT-02`
- Track C: rollout controls
  - `WF1-OPS-03`
- Track D: observability
  - `WF1-OPS-01`, `WF1-OPS-02`

After `WF1-SES-02`, `WF1-BOT-03`, and `WF1-SCH-02` are stable:
- Track E: mini app UX
  - `WF1-UI-01`, `WF1-UI-02`, `WF1-UI-04`, `WF1-UI-05`
- Track F: validation hardening
  - `WF1-QA-01`, `WF1-QA-03`, `WF1-QA-05`

Late-stage parallel tracks:
- `WF1-QA-06`, `WF1-QA-07`
- `WF1-OPS-04`

## 6. Test and Validation Backlog

### Table 5. Validation Matrix

| Validation Item | Type | Owner | Blocking? | Related Scope | Expected Result |
| --- | --- | --- | --- | --- | --- |
| Webhook secret reject and blocked-prod health | automated | QA + Backend | Yes | E1 | invalid or missing secret returns hard reject; health shows blocked state |
| Duplicate webhook dedupe | automated | QA + Backend | Yes | E1, E5 | duplicate callback/message/body creates one side effect only |
| MAX `WebAppData` auth validation | automated | QA + Security | Yes | E1 | valid data accepted; tampered or stale data rejected |
| Stale `mx1` launch token rejection | automated | QA + Backend | Yes | E2, E3 | stale token fails closed, clears resume state, no mutation |
| Session version mismatch rejection | automated | QA + Backend | Yes | E2, E3 | stale journey session link is rejected before mutation |
| Invite conflict / duplicate owner binding | automated | QA + Backend Domain | Yes | E2 | conflicting owner or reused invite does not rebind candidate |
| Interrupted bot -> mini app resume | automated | QA + Full-stack | Yes | E5, E6 | candidate resumes exact step after interruption |
| Scheduling ownership and restore | automated | QA + Backend Domain | Yes | E4 | assignment-owned path stays authoritative; old slot released; no split-brain |
| Portal restart / stale cookie / resume | automated | QA + Backend | Yes | E3, E6 | browser/device restart restores valid session and rejects stale one safely |
| Feature-flag matrix (`MAX_BOT_ENABLED`, `MAX_BOT_ALLOW_PUBLIC_ENTRY`) | automated | QA + Backend | Yes | E7 | flags gate exposure cleanly without side effects |
| MAX callback/button continuity | automated | QA + Frontend | No | E5, E6 | duplicate press does not double-fire; callback ack shown once |
| End-to-end Postgres-backed pilot path | automated integration | QA + Backend + Frontend | Yes | E1-E8 | candidate reaches booked interview through shared path |
| Real MAX deep-link entry and resume | manual smoke | QA + Product Ops | Yes | E5, E6, E7 | deep link opens correct state and re-entry works |
| Real `open_app` / bot-to-mini-app handoff | manual smoke | QA + Product Ops | Yes | E5, E6 | bot CTA opens mini app with correct next step |
| Real `requestContact` behavior on pilot clients | manual smoke | QA + Product Ops | Yes | E5, E6 | contact share works or manual fallback is clear |
| Back/close behavior in MAX client | manual smoke | QA + Product Ops | No | E6 | accidental close or back preserves recoverable state |
| Rollback rehearsal | manual operational validation | Infra/SRE + QA | Yes | E7 | disabling MAX flags leaves Telegram/browser fallback usable |

### Blocker test list

The following are blocker tests or blocker smoke validations for pilot:
- webhook secret reject path
- duplicate/replay dedupe
- stale `WebAppData` reject path
- stale `mx1` token reject path
- session version mismatch reject path
- duplicate-owner / invite-conflict path
- interrupted exact-state resume
- assignment-owned scheduling restore path
- feature-flag gating
- real-client `open_app` + `requestContact` smoke

## 7. Rollout Gates

### Table 3. Rollout Gates

| Gate | Required Work | Required Tests | Blockers | Exit Criteria |
| --- | --- | --- | --- | --- |
| G1. Environment Ready | `WF1-SEC-01`, `WF1-OPS-03` | config sanity, health checks | missing/invalid secrets, non-HTTPS URLs, unresolved link base | prod-like env is fail-closed and health explains status |
| G2. Ingress and Auth Ready | `WF1-SEC-02`, `WF1-SEC-03`, `WF1-BOT-01` | webhook secret/dedupe tests, MAX auth tests | duplicate side effects, stale auth acceptance, unstable subscription | MAX ingress is secret-protected, deduped, and subscription-ready |
| G3. Shared Contract Ready | `WF1-ID-03`, `WF1-SES-01`, `WF1-SES-02`, `WF1-SCH-02`, `WF1-SCH-03` | identity/session/scheduling regressions | duplicate owners, split-brain scheduling, transport leakage | one canonical identity/session/scheduling path is enforced |
| G4. Candidate UX Continuity Ready | `WF1-BOT-03`, `WF1-BOT-04`, `WF1-UI-01`, `WF1-UI-02`, `WF1-UI-03`, `WF1-UI-04` | interrupted-flow resume, real `open_app` smoke | dead-end handoff, broken recovery, non-authoritative dashboard | candidate can enter, continue, recover, and return cleanly |
| G5. Observability and Ops Ready | `WF1-OPS-01`, `WF1-OPS-02`, `WF1-OPS-04` | health, log, alert, rollback checks | no operator view, no failure taxonomy, no rollback playbook | operators can see readiness, failures, and execute rollback |
| G6. Pilot Certification | `WF1-QA-01`..`WF1-QA-07` | full blocker suite + real-client smoke | any P0 defect, missing smoke evidence, moderation/account not ready | CI/integration/manual evidence complete and pilot sign-off possible |

### Pilot blockers

Pilot is blocked if any of these remain unresolved:
- no dedicated MAX `WebAppData` validation path
- prod dedupe still relies on in-memory fallback
- duplicate or ambiguous `max_user_id` in pilot cohort
- scheduling integrity report indicates manual repair for pilot candidates
- unresolved `MAX_BOT_LINK_BASE` or `CANDIDATE_PORTAL_PUBLIC_URL`
- unstable webhook subscription or missing public HTTPS ingress
- real-client `open_app` / deep-link / `requestContact` smoke failing
- moderation/business approval incomplete

## 8. Ownership Map

### Table 4. Ownership Map

| Area | Responsible Owner Type | Supporting Owner Types | Notes |
| --- | --- | --- | --- |
| MAX webhook ingress and adapter lifecycle | Backend Platform | Security, SRE | owns webhook secret policy, subscription lifecycle, dedupe |
| Candidate identity and session contract | Backend Domain | Security, DB | owns `max_user_id`, launch token contract, session/version rules |
| Shared journey/profile/screening core | Backend Domain | Frontend/Mini App | MAX mini app must sit on this path |
| Scheduling write path and repair gates | Backend Domain | QA, DB | no second write path allowed |
| Bot entry, handoff, reminders | Bot/Integration | Backend Platform, Backend Messaging | owns transport shell and exact-state handoff copy/structure |
| MAX mini app UX | Frontend/Mini App | Backend Domain, QA | owns entry, dashboard, scheduling, recovery UX |
| Delivery/outbox observability | Backend Messaging | SRE, Backend Platform | owns queue health and degraded-channel signals |
| Health/readiness dashboard | Infra/SRE | Backend Platform | operator view and alerts |
| Pilot cohort gating and moderation | Product Ops | Recruiter Ops, Infra/SRE | non-engineering blockers are owned here |
| Automated validation and manual smoke | QA/Validation | Backend, Frontend, Product Ops | owns blocker suite, evidence, and go/no-go testing |

## 9. Risks and Prioritization

### High priority architectural risks

- MAX mini app auth facade is not yet confirmed as a dedicated live-code boundary
- direct slot mutation paths can still create scheduling divergence if not routed through a facade
- duplicate or ambiguous `max_user_id` can break deterministic candidate binding
- webhook 500/retry behavior can create replay storms if ack policy is wrong
- public bot discoverability increases privacy risk if candidate-specific content leaks before auth

### High priority UX risks

- broken bot-to-mini-app handoff causes abandonment
- mini app without a single dashboard home creates disorientation
- interrupted-flow recovery that restarts instead of resumes will hurt completion
- missing browser fallback makes client-capability issues fatal

### High priority rollout risks

- partner verification and moderation not complete
- missing public HTTPS ingress or unstable subscription
- no operator-ready health/alerting dashboard
- no real-client smoke evidence for the supported pilot matrix

### Prioritization rules

`P0`:
- blocks pilot or risks data corruption / security failure / divergent workflow

`P1`:
- materially improves continuity, observability, or rollout safety; can finish after the core path is stable but before broader rollout

`P2`:
- useful hardening that is not required for the first constrained pilot

## 10. Definition of Done for Wave 1

Wave 1 is done only when all of the following are true:
- all `P0` tasks are completed
- rollout gates `G1` through `G6` are passed
- MAX bot ingress is stable, deduped, and observable
- MAX mini app enters through validated auth and shared candidate portal session
- candidate can resume the exact current step after interruption
- scheduling is proven on the shared canonical path without split-brain
- feature flags and fallback paths are tested and rollback-safe
- blocker automated tests are green
- real-client smoke evidence exists for the supported pilot clients
- pilot cohort, moderation readiness, and operational ownership are explicitly signed off

## 11. Multi-Agent Reconciliation Notes

### Reconciliation input summary

Independent specialized inputs were gathered for:
- backend/domain
- bot/integration
- mini app/frontend
- security/identity
- QA/validation
- infra/rollout

Lead Architect then normalized:
- epic boundaries
- duplicated tasks
- dependency order
- rollout gates
- owner types

### Conflict 1: Which backend API should MAX mini app use?

Conflict:
- mini app/frontend analysis referenced both shared candidate portal APIs and the legacy Telegram webapp router for contrast
- architecture and backend/domain analyses required MAX to stay on shared `candidate portal / journey` contracts

Decision:
- MAX Wave 1 target path is `/api/candidate/*` via [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)
- `/api/webapp/*` remains legacy Telegram compatibility only

Why:
- prevents MAX-only backend drift
- keeps one journey/session contract
- avoids duplicating Telegram webapp semantics in MAX

Residual risk:
- some live code and tests still reference legacy Telegram webapp routes, so regression boundaries must stay explicit

### Conflict 2: Webhook failure behavior

Conflict:
- bot/integration analysis flagged current `500` handler failure risk
- security/infra analysis demanded fail-closed ingress with replay safety

Decision:
- auth/config failures remain hard reject
- post-auth internal processing must use an explicit retry-safe policy with audit visibility and no retry storm behavior

Why:
- matches official MAX guidance reviewed earlier
- preserves security at the trust boundary while reducing duplicate-side-effect risk

Residual risk:
- exact provider retry semantics still require staging validation with real subscription behavior

### Conflict 3: Public entry in Wave 1

Conflict:
- bot/domain paths support public entry behind `MAX_BOT_ALLOW_PUBLIC_ENTRY`
- security and infra treat public entry as a privacy and rollout risk

Decision:
- minimum Wave 1 pilot assumes invite/cohort-driven entry
- public entry remains disabled by default and is not a launch requirement

Why:
- reduces privacy and identity-binding risk
- keeps pilot cohort controllable

Residual risk:
- if product later wants public acquisition in MAX, it must pass a separate gate with real smoke evidence

### Conflict 4: Telegram fallback reuse

Conflict:
- mini app analysis allowed Telegram legacy surfaces as fallback/contrast
- backend/bot analyses rejected Telegram-shaped business flow reuse in MAX

Decision:
- browser portal fallback is allowed
- Telegram runtime/business handler reuse is not part of MAX Wave 1 target path

Why:
- browser fallback preserves shared backend contracts
- Telegram fallback would reintroduce transport-specific drift

Residual risk:
- operator expectations may still assume Telegram as default channel, so rollout comms must be explicit

## 12. Final Recommendation

The best Wave 1 execution strategy is:
- finish the security and session foundation first
- freeze one shared identity/session/scheduling contract
- then build the bot handoff and mini app UX on top of that contract
- gate everything behind rollout controls and a hard validation suite

Recommended delivery sequence:
1. `WF1-SEC-01` to `WF1-SEC-03`
2. `WF1-ID-01` to `WF1-SES-02`
3. `WF1-SCH-01` to `WF1-SCH-03`
4. `WF1-BOT-01` to `WF1-BOT-03`
5. `WF1-UI-01` to `WF1-UI-04`
6. `WF1-OPS-01` to `WF1-OPS-04`
7. `WF1-QA-01` to `WF1-QA-07`

If constrained by time, do not cut:
- shared session/bootstrap correctness
- scheduling write-path unification
- duplicate/replay safety
- interrupted-flow recovery
- rollout gates and real-client smoke

What can slip after the first pilot if needed:
- `WF1-SES-03`
- `WF1-UI-05`
- `WF1-OPS-02`
- `WF1-SCH-04`
- `WF1-QA-07` can remain a broadened pre-scale gate if all other blocker evidence is strong, but not if scheduling risk remains

## 13. WAVE 1 EXECUTION VERDICT

1. What is the minimum set of tasks required for pilot launch?

- `WF1-SEC-01`
- `WF1-SEC-02`
- `WF1-SEC-03`
- `WF1-ID-01`
- `WF1-ID-02`
- `WF1-ID-03`
- `WF1-SES-01`
- `WF1-SES-02`
- `WF1-SCH-01`
- `WF1-SCH-02`
- `WF1-SCH-03`
- `WF1-BOT-01`
- `WF1-BOT-02`
- `WF1-BOT-03`
- `WF1-UI-01`
- `WF1-UI-02`
- `WF1-UI-03`
- `WF1-UI-04`
- `WF1-OPS-03`
- `WF1-OPS-04`
- `WF1-QA-01`
- `WF1-QA-02`
- `WF1-QA-03`
- `WF1-QA-04`
- `WF1-QA-05`
- `WF1-QA-06`

2. Which 5 tasks are most critical for architectural stability?

- `WF1-SEC-03` MAX-specific `WebAppData` auth facade
- `WF1-ID-03` canonical MAX binding resolver
- `WF1-SES-02` single candidate portal resume contract
- `WF1-SCH-02` shared scheduling facade routing for candidate writes
- `WF1-BOT-03` exact-state bot -> mini app handoff envelope

3. Which tasks can be done safely in parallel?

Parallel early:
- `WF1-SEC-02`, `WF1-SEC-03`, `WF1-ID-01`, `WF1-OPS-03`

Parallel after session contract freeze:
- `WF1-SCH-01`
- `WF1-BOT-01`
- `WF1-BOT-02`
- `WF1-OPS-01`
- `WF1-OPS-02`

Parallel after handoff and scheduling contracts stabilize:
- `WF1-UI-02`
- `WF1-UI-04`
- `WF1-UI-05`
- `WF1-QA-01`
- `WF1-QA-03`
- `WF1-QA-05`

Late parallel:
- `WF1-QA-06`
- `WF1-OPS-04`

4. Which open points must be closed manually before rollout?

- real MAX client support matrix for deep links, `open_app`, `requestContact`, back/close behavior
- staging verification of MAX retry/ack behavior under handler failures
- moderation and business/account readiness
- pilot cohort cleanliness for duplicate owner and scheduling integrity conflicts
- rollback rehearsal with feature flags in a production-like environment

5. What counts as real completion of Wave 1?

Wave 1 is really complete when a pilot candidate can:
- start from MAX
- bind safely
- enter the mini app through validated shared session bootstrap
- complete profile/screening
- book or resume scheduling through the shared path
- leave and return without losing state
- receive reminders and confirmations
- do all of the above with blocker tests and rollout gates green

6. Which agent findings influenced the final backlog the most?

Most influential findings:
- backend/domain: shared session contract and one scheduling path are the architectural center of gravity
- security/identity: MAX needs a dedicated server auth facade and prod dedupe cannot rely on in-memory fallback
- bot/integration: exact-state handoff and retry-safe webhook policy are pilot-critical
- mini app/frontend: dashboard and recovery UX must be first-class, not polish
- QA/validation: interrupted-flow and stale-token tests are missing blocker coverage
- infra/rollout: moderation, ingress, readiness, and client smoke are true launch dependencies, not postscript tasks
