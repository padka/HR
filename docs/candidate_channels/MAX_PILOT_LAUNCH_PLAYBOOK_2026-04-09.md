# MAX Pilot Launch Playbook

Дата: `2026-04-09`

Source of truth:
- [MAX_BOT_READINESS_AUDIT_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md)
- [MAX_IMPLEMENTATION_SPEC_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_IMPLEMENTATION_SPEC_2026-04-09.md)
- [MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md)
- [MAX_RECRUITSMART_ARCHITECTURE_AND_ROADMAP_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_RECRUITSMART_ARCHITECTURE_AND_ROADMAP_2026-04-09.md)
- [MAX_WAVE1_EXECUTION_BACKLOG_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_WAVE1_EXECUTION_BACKLOG_2026-04-09.md)

Assembly mode:
- multi-agent launch team synthesis
- independent structured inputs collected from:
  - Launch Orchestrator / Release Lead
  - Backend / Domain Readiness
  - Bot / Integration Launch
  - Mini App / Frontend Launch
  - Security / Identity Readiness
  - QA / Validation Launch
  - Infra / Observability / Rollout
  - Product Ops / Conversion

Primary live-code anchors used during synthesis:
- [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- [backend/apps/max_bot/candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- [backend/domain/slot_assignment_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)
- [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)
- [backend/apps/admin_ui/services/messenger_health.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/messenger_health.py)
- [backend/apps/admin_api/webapp/auth.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py)
- [backend/core/settings.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py)
- [frontend/app/src/app/routes/candidate/start.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/start.tsx)
- [frontend/app/src/app/routes/candidate/journey.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/journey.tsx)
- [frontend/app/src/app/routes/candidate/webapp.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/webapp.ts)

## 1. Executive Summary

Wave 1 pilot for MAX must be a controlled, invite-only launch on top of the existing shared RecruitSmart candidate journey and scheduling core.

The pilot-safe path is:
- MAX bot entry and attribution
- validated MAX mini app bootstrap onto the shared candidate portal/session contract
- shared profile and screening flow
- scheduling only through the canonical shared write path
- bot reminders and exact-state re-entry
- health, alerting, rollback, and daily pilot review

The pilot must not start if any of these remain unresolved:
- no dedicated MAX `WebAppData` validation path
- prod dedupe still effectively relies on in-memory fallback
- unresolved `MAX_WEBHOOK_URL`, `MAX_BOT_LINK_BASE`, or `CANDIDATE_PORTAL_PUBLIC_URL`
- ambiguous `max_user_id` or manual-repair scheduling states inside the pilot cohort
- failing real-client smoke for `deep-link`, `open_app`, `requestContact`, or resume
- moderation or business readiness incomplete

Operational principle:
- keep the pilot cohort small and explicit
- keep public entry disabled
- prefer browser portal fallback over any Telegram logic reuse
- stop the pilot immediately on security, duplicate-side-effect, or scheduling-integrity breaches

## 2. Pilot Scope and Objectives

Pilot objectives:
- prove that MAX can support a controlled candidate flow without creating a second business workflow
- prove bot -> mini app -> scheduling -> reminder re-entry continuity
- prove replay, duplicate, and identity safeguards under live traffic
- prove operational control: flags, health visibility, incident response, and rollback

### Table 1. Pilot Scope Matrix

| Area | In Pilot | Out of Pilot | Why | Notes |
| --- | --- | --- | --- | --- |
| MAX bot entry | Yes | No | Bot is the canonical entry and reminder shell | Invite/cohort-driven starts only |
| Deep-link attribution | Yes | No | Needed for source-aware pilot analytics and routing | Keep payload small and signed |
| Public entry | No by default | Yes | Privacy and abuse risk is too high for pilot | `MAX_BOT_ALLOW_PUBLIC_ENTRY=false` |
| MAX mini app bootstrap | Yes | No | Required for stateful Wave 1 flow | Blocked until MAX auth facade is explicit |
| Shared profile/screening | Yes | No | Core candidate value path | Must use shared candidate portal contracts |
| Scheduling through canonical backend path | Yes | No | Pilot must prove one write path only | No divergent slot-only writes |
| MAX-native scheduling UX | Conditional | No as a hard requirement | Use only if smoke-proven on target clients | Browser portal fallback is acceptable |
| Browser portal fallback | Yes | No | Required recovery path for unsupported clients | Same shared backend contract |
| Telegram runtime fallback | No | Yes | Would reintroduce transport drift | Explicitly forbidden |
| Channels | No | Yes | Supporting layer, not pilot-critical | Can be evaluated after pilot |
| Advanced bridge features beyond `open_app` and `requestContact` | No | Yes | Not needed for Wave 1 proof | Treat as later-wave scope |
| Reminder and re-entry | Yes | No | Critical for conversion and interruption recovery | Must point to exact next step |
| Recruiter/admin UX redesign | No | Yes | Not needed for pilot | Keep focus on candidate path |

## 3. Pilot Cohort Definition

Recommended cohort shape:
- invite-only or allowlist-only candidates
- one city or office cluster at a time
- one vacancy family or narrow source mix at a time
- one recruiter/coordinator group with same-day manual fallback capacity
- only client types that passed real MAX smoke

Exclude from pilot:
- candidates with duplicate or ambiguous `max_user_id`
- candidates already marked `needs_manual_repair` or other scheduling integrity blockers
- public acquisition traffic
- unsupported MAX clients or unverified client versions
- candidates requiring unsupported advanced bridge capabilities

Cohort expansion rule:
- expand only after 3 consecutive daily reviews without stop conditions
- expand one axis at a time:
  - more candidates in same city/source
  - new recruiter group
  - new city/office
  - public entry only after separate approval and smoke evidence

## 4. Launch Readiness Checklist

### Launch Orchestrator / Release Lead

- Pilot scope frozen to invite/cohort-only path.
- Named owners confirmed for backend, bot, mini app, security, QA, infra, and product ops.
- Go/no-go gates mapped to launch-day sequence and rollback sequence.
- Daily review cadence and sign-off ritual agreed before launch.

### Backend / Domain Readiness

- Shared candidate portal/session contract remains authoritative.
- Session version mismatch and stale token paths fail closed.
- Scheduling stays on one canonical write path with repair gates.
- Outbox/reminder health signals are visible before pilot.

### Bot / Integration Launch

- Webhook secret validation and subscription reconciliation are green.
- MAX event handling stays on MAX/server-side continuation path only.
- Bot -> mini app handoff carries exact session state.
- Reminder links reopen valid current state or safe recovery state.

### Mini App / Frontend Launch

- Candidate start and resume work from `startapp`, query token, and stored session.
- Interrupted flow shows explicit recovery UX instead of silent restart.
- Dashboard is the authoritative candidate home.
- Unsupported capability fallback is clear and safe.

### Security / Identity Readiness

- Dedicated MAX `WebAppData` validation path is confirmed.
- Replay, duplicate, and rebind safeguards are proven.
- Public entry is off by default.
- Sensitive inbound MAX payload handling is reviewed for PII minimization.

### QA / Validation Launch

- Blocker automation is green.
- Real-client smoke evidence exists for supported pilot clients.
- Pilot gates `G1` through `G6` are signed off.
- Rollback rehearsal passed.

### Infra / Observability / Rollout

- Prod-like config is frozen and explicit.
- `/health` and messenger health surfaces show operator-ready readiness state.
- Alerts and incident routing are configured.
- Rollback owners and fallback path are confirmed.

### Product Ops / Conversion

- Cohort definition and business readiness are signed off.
- Success, warning, and stop metrics are ready.
- Manual fallback play for candidates is prepared.
- Daily review template is assigned and scheduled.

## 5. Preflight Validation Checklist

### Table 2. Preflight Checklist

| Item | Owner | Blocking? | Validation Method | Pass Criteria |
| --- | --- | --- | --- | --- |
| MAX prod config frozen | Infra/SRE | Yes | env review + startup validation | `MAX_BOT_ENABLED`, `MAX_BOT_TOKEN`, `MAX_WEBHOOK_URL`, `MAX_WEBHOOK_SECRET`, `MAX_BOT_LINK_BASE`, `CANDIDATE_PORTAL_PUBLIC_URL`, `REDIS_URL` are explicit and consistent |
| Public HTTPS webhook ready | Backend Platform + Infra/SRE | Yes | live URL check + health | webhook URL is public HTTPS and reachable; provider subscription can target it |
| MAX webhook secret enforced | Security + Backend Platform | Yes | negative test | invalid or missing secret is hard-rejected outside dev/test |
| Production dedupe is Redis-backed | Security + Backend Platform | Yes | config + failure drill | no pilot dependence on in-memory dedupe fallback |
| Dedicated MAX `WebAppData` auth path confirmed | Security + Identity/Auth | Yes | code path review + automated test | MAX mini app auth does not rely on Telegram-only auth code |
| Cohort owner preflight clean | Backend Domain + Recruiter Ops | Yes | owner report | no duplicate/ambiguous `max_user_id`, invite conflicts, or unresolved journey collisions |
| Scheduling integrity clean for pilot cohort | Backend Domain | Yes | integrity report | no pilot candidate is in manual-repair or split-brain scheduling state |
| Bot -> mini app handoff smoke | QA + Bot/Frontend | Yes | real-client smoke | handoff opens the correct current step with exact-state continuity |
| Real `requestContact` fallback verified | QA + Product Ops | Yes | real-client smoke | contact share works on supported clients or manual fallback is clear |
| Real `open_app` and back/close behavior verified | QA + Frontend | Yes | real-client smoke | app opens and recovery survives back/close or unsupported bridge path |
| Reminder re-entry smoke | QA + Bot/Integration | Yes | live reminder smoke | reminder returns candidate to exact state or safe recovery screen |
| Rollback rehearsal completed | Infra/SRE + QA | Yes | live flag drill | disabling MAX surfaces preserves browser fallback and avoids shared-state corruption |
| Moderation/business approval complete | Product Ops | Yes | business sign-off | account, moderation, and non-engineering approvals are explicit |
| Daily review owners assigned | Launch Lead | Yes | launch checklist | named owners for metrics, incidents, and go/no-go are present |

## 6. Launch-Day Sequence

### Pilot launch sequence

```text
T-1 day
  -> freeze cohort
  -> freeze config and flags
  -> verify moderation/business sign-off
  -> run blocker automation
  -> run real-client smoke

T-2 hours
  -> confirm /health and messenger health
  -> confirm subscription_status=ready
  -> confirm owner/integrity reports clean
  -> confirm rollback owner and bridge fallback

T0
  -> enable pilot cohort access
  -> keep public entry disabled
  -> send invite/deep links
  -> watch first candidates through handoff

T+15m to T+2h
  -> live monitoring
  -> one supervised happy-path smoke
  -> incident triage if needed

T+24h and daily thereafter
  -> daily pilot review
  -> decide continue / constrain / stop
```

Launch-day sequence:
1. Freeze env and flag states.
2. Reconfirm webhook subscription and secret status.
3. Re-run critical automated tests if any deploy occurred after last QA sign-off.
4. Execute one live internal happy-path on an approved MAX client.
5. Open pilot cohort access.
6. Watch first real candidates through entry, handoff, scheduling start, and confirmation.
7. Hold a first operational review within the first 2 hours.

## 7. Feature Flags and Rollout Controls

### Table 6. Feature Flag Matrix

| Flag | Purpose | Default State | Owner | Rollback Role |
| --- | --- | --- | --- | --- |
| `MAX_BOT_ENABLED` | Master enable for MAX bot runtime | `false` until pilot start, then `true` only in pilot env | Backend Platform + Infra/SRE | Primary kill switch for MAX bot ingress |
| `MAX_BOT_ALLOW_PUBLIC_ENTRY` | Public onboarding through MAX bot | `false` | Product Ops + Backend Platform | First switch to keep off or turn off during incident |
| Pilot cohort allowlist / invite gating | Restrict which candidates may start the pilot | restricted | Product Ops + Recruiter Ops + Backend Domain | Remove or narrow cohort immediately without changing shared logic |
| MAX mini app entry exposure | Allow validated candidates to launch mini app from bot | restricted to pilot cohort | Bot/Integration + Frontend | Disable and fall back to browser portal if handoff is unstable |
| MAX scheduling exposure | Allow scheduling inside approved MAX pilot path | restricted to pilot cohort and smoke-proven clients | Product Ops + Backend Domain + Frontend | Disable and route candidates to browser portal fallback |
| MAX dashboard exposure | Candidate dashboard entry inside MAX | restricted to pilot cohort | Frontend/Mini App | Disable advanced surface while keeping bot alive |

Control rules:
- never enable public entry and a new cohort expansion on the same day
- do not widen supported client matrix without fresh smoke evidence
- if scheduling surface is unstable, keep bot entry alive and move candidates to browser portal fallback

## 8. Smoke Test Plan

### Table 3. Smoke Test Matrix

| Scenario | Surface | Owner | Manual / Automated | Blocking? | Expected Result |
| --- | --- | --- | --- | --- | --- |
| Invalid webhook secret reject | Bot runtime | QA + Security | Automated | Yes | request is rejected and no side effect is created |
| Duplicate `message_created` dedupe | Bot runtime | QA + Backend | Automated | Yes | one side effect only |
| Duplicate `message_callback` dedupe | Bot runtime | QA + Backend | Automated | Yes | one callback effect only |
| Stale `WebAppData` reject | Mini app auth | QA + Security | Automated | Yes | stale/tampered MAX context is rejected |
| Stale `mx1` launch token reject | Shared session | QA + Backend | Automated | Yes | candidate receives recovery path, no mutation |
| Session-version mismatch reject | Shared session | QA + Backend | Automated | Yes | stale session does not mutate journey state |
| Duplicate owner / invite conflict reject | Binding | QA + Backend Domain | Automated | Yes | candidate is not rebound incorrectly |
| Bot -> mini app exact-state resume | Bot + Mini App | QA + Full-stack | Automated + Manual | Yes | interrupted candidate resumes exact current step |
| Reserve -> confirm scheduling | Mini app / browser portal | QA + Backend Domain | Automated + Manual | Yes | booking succeeds on canonical assignment path |
| Cancel / reschedule | Mini app / browser portal | QA + Backend Domain | Automated + Manual | Yes | state stays synchronized and auditable |
| Real deep-link entry | MAX client | QA + Product Ops | Manual | Yes | candidate lands on correct personalized or cohort path |
| Real `open_app` handoff | MAX client | QA + Product Ops | Manual | Yes | bot CTA opens mini app with correct state |
| Real `requestContact` | MAX client | QA + Product Ops | Manual | Yes | contact is captured or manual fallback is clear |
| Back / close recovery | MAX client | QA + Frontend | Manual | Yes | candidate can recover without duplicate side effects |
| Reminder continuity | Bot + Mini App | QA + Bot/Frontend | Manual | Yes | reminder reopens current state or safe recovery screen |
| Browser fallback | Browser portal | QA + Frontend | Manual | Yes | candidate can continue on shared backend path |

### Candidate happy-path during pilot

```text
Invite link
  -> MAX bot welcome
  -> contact capture
  -> short qualification
  -> open mini app
  -> profile
  -> screening
  -> scheduling start
  -> reserve slot
  -> confirm slot
  -> bot confirmation
  -> reminder / re-entry if interrupted
```

### Bot -> mini app -> scheduling -> confirmation flow

```text
MAX webhook
  -> candidate_flow resolves candidate + session
  -> bot sends signed startapp URL
  -> candidate opens mini app
  -> MAX auth facade validates WebAppData
  -> /api/candidate/session/exchange establishes session
  -> candidate completes screening
  -> /api/candidate/slots/* uses canonical scheduling path
  -> booking confirmed
  -> bot sends confirmation and future reminder
```

## 9. Monitoring and Alerting Plan

### Table 4. Monitoring Matrix

| Signal / Metric | Source | Threshold | Severity | Response Owner | Action |
| --- | --- | --- | --- | --- | --- |
| MAX `/health` status not `ok` or `blocked` reason changes unexpectedly | [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) | any unexpected blocked/degraded state | P1 | Backend Platform | freeze cohort growth, inspect config/secret/subscription |
| `subscription_status != ready` | MAX health + messenger health | any non-ready during pilot | P1 | Backend Platform + Infra/SRE | pause new invites, reconcile subscription |
| `max_bot.webhook.secret_reject` spikes | runtime logs | >3 in 15 min | P2, P1 if sustained | Security | verify secret drift or probing; consider hard disable if malicious |
| `max_bot.webhook.dedupe.redis_unavailable` or `redis_fallback` | runtime logs | any in production | P1 | Security + Infra/SRE | stop cohort expansion; restore Redis or disable pilot |
| Duplicate/replay rejection counts | runtime logs + QA dashboard | rising trend above normal baseline | P2, P1 if side effects duplicate | Backend Platform | inspect dedupe and ack policy |
| Session exchange 401 / version mismatch rejects | candidate portal logs | warning if rising; stop if candidates are stranded | P2/P1 | Backend Domain | inspect session drift, refresh links, reduce cohort |
| `invite_conflict` / `max_link_rejected` / owner ambiguity | audit + logs | any repeated pattern in pilot cohort | P2 | Backend Domain + Recruiter Ops | clean cohort, halt affected candidates |
| Scheduling conflict / `needs_manual_repair` / 409 | scheduling integrity + portal logs | any pilot candidate enters repair state | P1 | Backend Domain | stop new scheduling, investigate split-brain |
| Outbox backlog / poll staleness / delivery failures | notification metrics | backlog growing for 15 min or send failures sustained | P2/P1 | Messaging + Infra/SRE | throttle pilot, inspect delivery runtime |
| Funnel conversion drop | product analytics | >10% below comparable baseline | P2, stop if >20% for 2 daily reviews | Product Ops | inspect friction point and narrow cohort |
| Browser fallback rate | mini app analytics | rising day-over-day or >20% of attempts | P2 | Frontend + Product Ops | investigate client capability gap |

Alerting requirements before launch:
- route P1 to Launch Lead, Backend Platform, Security, and Infra/SRE
- route P2 to owning team and include in daily review
- keep one operator-visible dashboard combining health, webhook, session, scheduling, outbox, and funnel signals

## 10. Incident Response Matrix

Severity model:
- `P0`: security or data-integrity breach, unauthorized access, duplicate mutation/booking, or uncontained replay
- `P1`: pilot-critical outage or corrupted candidate path with no safe fallback
- `P2`: degraded experience with safe fallback or limited cohort impact
- `P3`: minor issue, copy issue, or non-blocking analytics gap

### Table 5. Incident Matrix

| Incident Type | Severity | Detection Method | Immediate Action | Escalation Path | Rollback Needed? |
| --- | --- | --- | --- | --- | --- |
| Missing/invalid webhook secret or wrong webhook URL | P1 | health + secret reject logs | stop new cohort traffic, fix config | Backend Platform -> Launch Lead | Usually no if fixed fast; yes if unstable |
| Redis dedupe unavailable in prod | P1 | `redis_unavailable` / `redis_fallback` | stop new invites, restore Redis, evaluate disable | Infra/SRE + Security -> Launch Lead | Yes if not restored quickly |
| Duplicate booking or duplicate mutation | P0 | QA/live incident + audit mismatch | stop pilot immediately, disable MAX entry | Backend Domain + Security -> Exec/Launch Lead | Yes |
| Unauthorized or stale MAX auth accepted | P0 | security log/anomaly | stop pilot immediately, disable MAX surfaces | Security -> Launch Lead -> Product Ops | Yes |
| Session/version mismatch spike stranding users | P1 | portal rejects + support tickets | pause cohort growth, issue fresh links | Backend Domain + Product Ops | Maybe, if widespread |
| Scheduling split-brain / manual repair for pilot candidates | P1 | integrity report + 409s | stop scheduling entry, switch to manual handling | Backend Domain + Recruiter Ops | Yes for scheduling surface |
| Bot -> mini app handoff fails | P1 | smoke/live monitoring | switch affected cohort to browser fallback | Bot/Integration + Frontend | Usually partial rollback |
| `open_app` or `requestContact` broken on supported client | P2, P1 if no fallback | manual smoke + support reports | restrict client matrix, fallback to browser/manual entry | Frontend + Product Ops | Partial rollback by client/cohort |
| Reminder backlog or delivery failure | P2 | outbox metrics | pause reminder-heavy nudges, inspect worker | Messaging + Infra/SRE | No if core flow intact |
| Moderation/account readiness revoked or blocked | P1 | partner/business signal | stop pilot growth immediately | Product Ops -> Launch Lead | Yes |

### Incident escalation flow

```text
Detection
  -> classify P0/P1/P2/P3
  -> page primary owner
  -> notify Launch Lead
  -> decide: mitigate / constrain cohort / rollback
  -> communicate status to Product Ops + Recruiter Ops
  -> record incident and next review checkpoint
```

## 11. Rollback and Recovery Plan

Rollback priorities:
1. protect shared candidate and scheduling state
2. stop unsafe ingress or mini app auth
3. preserve fallback path for candidates already in progress
4. keep Telegram/web portal unaffected

Rollback procedure:
1. Set `MAX_BOT_ALLOW_PUBLIC_ENTRY=false`.
2. Stop new pilot invites and cohort access.
3. If ingress is unsafe, set `MAX_BOT_ENABLED=false`.
4. If mini app path is degraded but bot is safe, keep bot alive and route candidates to browser portal fallback.
5. If scheduling is degraded, disable MAX scheduling exposure and use manual or browser fallback on the same shared backend path.
6. Reissue fresh links for recoverable candidates only after root cause is understood.
7. Do not enable any alternate MAX-only or Telegram-based business flow as emergency workaround.

### Rollback flow

```text
P0/P1 trigger
  -> disable public entry
  -> stop new cohort access
  -> decide bot-only safe? yes/no
     -> yes: keep bot alive, send browser fallback
     -> no: disable MAX_BOT_ENABLED
  -> preserve shared backend state
  -> communicate to Ops
  -> investigate root cause
  -> re-open only after smoke + sign-off
```

## 12. Daily Pilot Review Routine

Daily review participants:
- Launch Lead
- Backend Platform
- Backend Domain
- Bot/Integration
- Frontend/Mini App
- Security
- QA
- Infra/SRE
- Product Ops
- Recruiter Ops

Daily review agenda:
1. Confirm no overnight stop condition was hit.
2. Review health, subscription, dedupe, session, scheduling, and outbox signals.
3. Review funnel metrics by step and by client type.
4. Review support/manual fallback cases.
5. Decide:
   - continue unchanged
   - continue with constrained cohort
   - pause one surface
   - stop pilot

Daily review template:
- cohort size and active candidate count
- started flow count
- mini app opens
- contact captures
- screening completions
- scheduling starts
- scheduling confirmations
- reminder sends and reminder-to-return rate
- session/version rejects
- dedupe fallback hits
- scheduling conflict/manual-repair cases
- product decisions for next 24h

### Daily pilot review loop

```text
Collect metrics and incidents
  -> review against targets/warnings/stops
  -> inspect top drop-off step
  -> inspect top technical incident
  -> decide continue / constrain / stop
  -> update cohort and flags
  -> publish next-day operating note
```

## 13. Success / Warning / Stop Metrics

Metric rule:
- where a comparable Telegram or portal baseline exists, compare against that baseline for the same vacancy/city/source cohort
- if no clean baseline exists, use the absolute fallback thresholds below

### Table 7. Pilot Metrics Matrix

| Metric | Why It Matters | Target | Warning Threshold | Stop Threshold |
| --- | --- | --- | --- | --- |
| Entry -> started flow conversion | proves deep-link + welcome path works | within 10% of comparable baseline | 10-20% below baseline for one daily review | >20% below baseline for 2 consecutive daily reviews |
| Started -> contact captured | measures early-friction and `requestContact` quality | within 10% of baseline or manual fallback success >=80% | 10-20% below baseline or manual fallback success <70% | >20% below baseline or manual fallback success <60% |
| Contact captured -> screening completed | proves form completion continuity | within 10% of baseline | 10-20% below baseline | >20% below baseline |
| Screening completed -> scheduling started | proves handoff into scheduling works | within 10% of baseline | 10-20% below baseline | >20% below baseline |
| Scheduling started -> scheduling confirmed | proves slot UX and canonical write path are working | within 10% of baseline and no duplicate bookings | 10-20% below baseline or rising conflict rate | any duplicate booking or >20% below baseline |
| Confirmed -> downstream handoff recorded | proves confirmed interviews reach downstream systems | 100% downstream handoff record presence | <98% | <95% |
| Reminder-to-return rate | proves chat reminders recover candidates | >= comparable baseline or >=35% of reminder recipients return | 20-35% return | <20% return for 2 daily reviews |
| Exact-state resume success rate | proves interruption recovery | >=80% of resume attempts succeed | 60-79% | <60% |
| Interrupted flow recovery rate | measures whether candidates recover after disruption | >=80% | 60-79% | <60% |
| Critical incident count | protects pilot safety | 0 P0, 0 unresolved P1 | 1 P1 or >3 P2/day | any P0 or >1 unresolved P1/day |
| Duplicate/replay anomaly count | protects idempotency and trust | 0 accepted duplicate side effects | dedupe degradation or >5 fallback hits/day | any duplicate mutation or booking |
| Browser fallback rate | tracks client-capability gaps | <=10% of pilot attempts | 10-20% | >20% or rising for 2 daily reviews |

## 14. Roles and Ownership

### Table 8. Ownership / On-Call Matrix

| Area | Primary Owner | Secondary Owner | Escalation Notes |
| --- | --- | --- | --- |
| Launch command and go/no-go | Launch Orchestrator / Release Lead | Product Ops | final gate owner for continue / constrain / stop |
| MAX webhook ingress and secrets | Backend Platform | Security | escalate immediately on secret or dedupe issues |
| MAX mini app auth and session exchange | Security / Identity | Backend Domain | any auth trust-boundary issue is P0/P1 |
| Candidate identity binding | Backend Domain | Recruiter Ops | owner ambiguity blocks cohort entry |
| Shared journey/session continuity | Backend Domain | Frontend/Mini App | stale-session spikes need same-day triage |
| Scheduling integrity | Backend Domain | Recruiter Ops + QA | any pilot manual-repair case is escalation-worthy |
| Bot entry, handoff, reminders | Bot/Integration | Backend Messaging | owns reminder continuity and exact-state CTA |
| MAX candidate UI and recovery UX | Frontend/Mini App | QA | owns client-specific fallback behavior |
| Outbox and delivery health | Backend Messaging | Infra/SRE | queue/dead-letter growth must page owner |
| Readiness dashboards and alerts | Infra/SRE | Backend Platform | owns operator view and alert routing |
| Pilot cohort and moderation | Product Ops | Recruiter Ops | owns business sign-off and cohort narrowing |
| Certification and smoke evidence | QA/Validation | All engineering leads | owns blocker suite and evidence archive |

## 15. Multi-Agent Reconciliation Notes

Independent structured inputs were collected before synthesis. Each input included:
- checklist
- blockers
- validations
- incident concerns
- ownership notes

### Launch Orchestrator local input

Checklist:
- pilot scope remains invite-only and controlled
- stop conditions are defined before any cohort enable
- every gate maps to an owner and validation method

Blockers:
- unresolved MAX auth facade
- unresolved dedupe posture
- missing business/moderation sign-off

Validations:
- source docs reconciled against live code anchors
- sub-agent outputs normalized into one launch sequence

Incident concerns:
- starting pilot with incomplete ownership
- over-trusting health as a substitute for real smoke

Ownership notes:
- Launch Lead owns gate progression and final go/no-go call

### Conflict 1: Is client capability smoke already “covered” or still a blocker?

Conflict:
- QA input described the client matrix as part of the readiness checklist and validated automated suites
- Mini app, bot, infra, and product ops inputs all treated real-client `open_app`, `requestContact`, back/close, and reminder continuity as unresolved pilot blockers

Decision:
- automated coverage is necessary but not sufficient
- real-client smoke on the supported pilot matrix remains a blocking launch gate

Why:
- live MAX client behavior is still an open point in the architecture and research docs
- browser fallback is allowed, but only after real unsupported-capability behavior is understood

Residual risk:
- smoke may pass on one client subset and fail on another; the pilot must explicitly restrict supported clients

### Conflict 2: Should MAX-native scheduling inside the mini app be mandatory on day 1?

Conflict:
- architecture and product docs treat scheduling as a central mini app surface
- mini app launch input found current reviewed UI more informational than fully transactional

Decision:
- the pilot objective is to prove canonical scheduling through the shared backend path
- MAX-native scheduling is allowed only if smoke-proven on the supported client matrix
- browser portal fallback remains acceptable during pilot if it uses the same shared scheduling contract

Why:
- operational safety matters more than forcing a specific UX surface
- this avoids inventing a second scheduling path or blocking pilot on front-end polish alone

Residual risk:
- fallback to browser may reduce conversion versus a stronger in-app scheduling UI

### Conflict 3: What is the correct policy for webhook failures after auth?

Conflict:
- bot/integration and infra inputs flagged that current `500` behavior can amplify retries
- security input demanded fail-closed trust-boundary behavior

Decision:
- keep hard reject at the trust boundary for missing/invalid secret and invalid auth
- after trust-boundary acceptance, treat retry storms as a launch blocker and stop or constrain the pilot if downstream processing becomes unstable

Why:
- this preserves security while acknowledging provider retry risk
- the playbook cannot assume provider semantics will save a half-broken internal pipeline

Residual risk:
- real provider retry timing still needs live observation during pilot

### Conflict 4: Can public entry be enabled for pilot acquisition learning?

Conflict:
- product research values public acquisition
- security, infra, and bot inputs treat public entry as a pilot risk

Decision:
- public entry remains off for Wave 1 pilot
- acquisition learning comes from invite/cohort links and attribution payloads only

Why:
- it keeps identity, privacy, and abuse exposure bounded
- it preserves a manageable rollout surface for the first pilot

Residual risk:
- public acquisition learnings are delayed until a later gated launch

### Conflict 5: Is existing Telegram-style auth a valid temporary MAX mini app path?

Conflict:
- frontend saw existing legacy webview patterns in the repo
- security and backend/domain inputs rejected Telegram-only auth as the MAX trust boundary

Decision:
- Telegram-only auth paths are not acceptable for MAX mini app pilot auth
- lack of a dedicated MAX `WebAppData` facade remains a blocker

Why:
- transport-specific auth leakage would undermine the shared identity/session model
- this was the clearest cross-agent blocker

Residual risk:
- until the dedicated MAX auth facade exists, mini app pilot launch is no-go

## 16. Pilot Go / No-Go Recommendation

Current recommendation:
- `NO-GO` until all blocking items in Sections 5 and 15 are green
- `GO` only for a controlled invite-only cohort after real-client smoke and rollback rehearsal pass

Pilot may start only when all of the following are true:
1. MAX-specific `WebAppData` validation is explicit and tested.
2. Redis-backed dedupe is mandatory in production and no in-memory fallback is relied on.
3. Webhook, link base, and portal public URL are explicit, public HTTPS where required, and health shows ready subscription state.
4. Pilot cohort is clean for identity ambiguity and scheduling integrity.
5. Real-client smoke passes on the supported MAX client matrix.
6. Moderation/business readiness and named operational owners are signed off.

## PILOT GO / NO-GO VERDICT

1. Minimal conditions required to start pilot:
   - dedicated MAX auth facade ready
   - production-safe dedupe ready
   - canonical identity/session/scheduling path clean
   - supported-client smoke green
   - moderation/business readiness signed off

2. Five checks that cannot be skipped:
   - invalid/stale MAX auth reject
   - duplicate webhook/callback dedupe
   - bot -> mini app exact-state handoff
   - scheduling integrity clean for pilot cohort
   - rollback rehearsal with fallback intact

3. Five signals to watch in the first 24 hours:
   - `/health` and `subscription_status`
   - dedupe degradation or replay anomalies
   - session/version reject spikes
   - scheduling conflicts/manual-repair cases
   - reminder-to-return and handoff conversion

4. Conditions that require immediate pilot stop:
   - any accepted stale MAX auth or unauthorized access
   - any duplicate booking or duplicate candidate mutation
   - any split-brain scheduling/manual-repair case inside pilot
   - webhook retry storm with unstable downstream processing
   - unsupported-client failures without safe fallback across the pilot cohort

5. What counts as a successful pilot:
   - no P0 incidents
   - no duplicate side effects
   - clean shared-state integrity
   - successful controlled cohort progression through entry, mini app, scheduling, and reminder re-entry
   - metrics stay within agreed warning thresholds and the team can expand cautiously

6. Agent findings that most influenced this playbook:
   - Security / Identity: MAX auth facade and Redis-backed dedupe are hard blockers
   - Backend / Domain: one shared session and scheduling contract must remain authoritative
   - QA / Validation: automated coverage is strong, but real-client smoke is still mandatory
   - Mini App / Frontend: scheduling UX and unsupported-capability recovery must be proven, not assumed
   - Infra / Rollout and Product Ops: moderation, cohort control, and rollback rehearsal are first-class launch gates, not post-launch work
