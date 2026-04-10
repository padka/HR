# MAX Conditional GO Review

Дата: `2026-04-09`

Source of truth:
- [MAX_BOT_READINESS_AUDIT_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md)
- [MAX_IMPLEMENTATION_SPEC_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_IMPLEMENTATION_SPEC_2026-04-09.md)
- [MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md)
- [MAX_RECRUITSMART_ARCHITECTURE_AND_ROADMAP_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_RECRUITSMART_ARCHITECTURE_AND_ROADMAP_2026-04-09.md)
- [MAX_WAVE1_EXECUTION_BACKLOG_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_WAVE1_EXECUTION_BACKLOG_2026-04-09.md)
- [MAX_PILOT_LAUNCH_PLAYBOOK_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_PILOT_LAUNCH_PLAYBOOK_2026-04-09.md)
- `MAX_PILOT_BLOCKERS_CLOSURE_PLAN_2026-04-09.md`

Review caveat:
- `MAX_PILOT_BLOCKERS_CLOSURE_PLAN_2026-04-09.md` was referenced in the brief but is not present in the local repo.
- This review therefore uses the last agreed blocker model from the program context plus live implementation evidence, validation results, backlog, and launch playbook.

Assembly mode:
- multi-agent review synthesis
- independent review inputs were collected from:
  - Review Orchestrator / Decision Lead
  - Backend / Architecture Review
  - Reliability / Dedupe Review
  - Cohort / Product Ops Review
  - Mini App / Client Validation Review
  - Security / Risk Review
  - QA / Evidence Review
  - Infra / External Dependencies Review

Primary live-code anchors used during review:
- [backend/apps/admin_api/webapp/auth.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py)
- [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)
- [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- [backend/apps/admin_ui/services/messenger_health.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/messenger_health.py)
- [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- [backend/domain/candidates/max_owner_preflight.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/max_owner_preflight.py)
- [backend/domain/candidates/scheduling_integrity.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/scheduling_integrity.py)
- [scripts/max_pilot_cohort_audit.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/max_pilot_cohort_audit.py)
- [frontend/app/src/app/routes/candidate/start.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/start.tsx)
- [frontend/app/src/app/routes/candidate/webapp.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/webapp.ts)
- [frontend/app/src/api/candidate.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/api/candidate.ts)

## 1. Executive Summary

Current review outcome:
- overall program-state can now be moved from `NO-GO` to `CONDITIONAL GO`
- actual pilot start is still blocked
- `GO` is not justified yet

Why `CONDITIONAL GO` is now defensible:
- B1 is closed at code and architecture level:
  - MAX-specific `WebAppData` validation exists in [backend/apps/admin_api/webapp/auth.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py)
  - MAX-origin exchange is enforced on the shared candidate portal path in [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)
- B2 is closed at code and policy level:
  - prod-like ingress now fails closed without Redis-backed dedupe in [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
  - duplicate/replay handling and false-duplicate regressions are covered by tests
- there is no visible MAX-only backend drift:
  - shared `/api/candidate/*` contracts remain canonical
  - no second identity/session linkage path is evident

Why actual pilot start is still blocked:
- B3 is only tooling-ready, not evidence-closed
- B4 still lacks real-client smoke artifacts
- B5 still lacks moderation/business approvals and live operational evidence
- B2 still needs live pilot-environment proof, even though code-level closure is strong

Decision rule used in this review:
- `code-level closure` proves the implementation is directionally safe
- `pilot-level closure` requires operational proof in the target environment
- `rollout-level closure` requires approvals, named ownership, and launch controls

## 2. Current Readiness State

Current readiness split:
- B1:
  - code-level: closed
  - pilot-level: conditionally accepted
  - rollout-level: still requires live end-to-end proof in actual MAX clients
- B2:
  - code-level: closed
  - pilot-level: not yet fully accepted
  - rollout-level: blocked pending live Redis/health/drill evidence
- B3:
  - code-level/tooling-level: ready
  - pilot-level: open
  - rollout-level: open
- B4:
  - code-level: partially ready
  - pilot-level: open
  - rollout-level: open
- B5:
  - code-level: not applicable
  - pilot-level: open
  - rollout-level: open

Current state statement:
- `CONDITIONAL GO` is appropriate only as a controlled pre-launch status.
- This means the program may enter final preflight and decision-gate execution.
- This does not authorize live pilot traffic yet.

### NO-GO -> CONDITIONAL GO decision flow

```text
Previous state: NO-GO
  -> verify B1 code/architecture closure
  -> verify B2 code/policy closure
  -> confirm no MAX-only backend drift
  -> identify whether remaining blockers are operational proof / approvals
  -> if yes, move to CONDITIONAL GO
  -> keep actual pilot-start gate blocked until B3/B4/B5 and live env proof are green
```

## 3. Blocker Status Review

### Table 1. Blocker Status Table

| Blocker | Previous Status | Current Status | Evidence Present | Evidence Missing | Owner | Pilot Impact |
| --- | --- | --- | --- | --- | --- | --- |
| B1. MAX `WebAppData` auth facade | Open / `NO-GO` | Code-level closed; pilot-level conditionally accepted | MAX validator in [auth.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py), exchange enforcement in [candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py), negative-path tests in [tests/test_webapp_auth.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_webapp_auth.py) and [tests/test_candidate_portal_api.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_candidate_portal_api.py) | real MAX-client end-to-end smoke through the actual bridge/client matrix | Backend Platform + Security + Backend Identity | No longer blocks conditional-go; still requires live proof before actual pilot traffic |
| B2. Production-safe dedupe | Open / `NO-GO` | Code-level closed; pilot-level partially open | fail-closed ingress, Redis-required prod behavior, `/health` exposure in [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py), duplicate/replay tests in [tests/test_max_bot.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_max_bot.py), end-to-end MAX flow regression coverage in [tests/test_max_candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_max_candidate_flow.py) | live Redis-backed health snapshot, live failure drill, pilot-env duplicate/replay smoke | Backend Platform + Security + Infra/SRE | Blocks actual pilot start until live env proof is archived |
| B3. Clean pilot cohort | Open / `NO-GO` | Tooling-ready; operationally open | owner preflight logic in [max_owner_preflight.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/max_owner_preflight.py), scheduling integrity logic in [scheduling_integrity.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/scheduling_integrity.py), audit runner in [scripts/max_pilot_cohort_audit.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/max_pilot_cohort_audit.py) | real audit export, signed allowlist, owner acknowledgement, exclusion log | Product Ops + Backend Domain + Recruiter Ops | Launch blocker |
| B4. Real-client smoke validation | Open / `NO-GO` | Open | bridge-aware start/resume logic in [start.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/start.tsx), MAX bridge helpers in [webapp.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/webapp.ts), exchange of `max_webapp_data` in [candidate.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/api/candidate.ts), route tests in [start.test.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/candidate/start.test.tsx) | manual smoke matrix, transcripts or recordings, pass/fail interpretation, explicit supported client list, fallback decisions | QA + Frontend + Bot/Integration + Product Ops | Launch blocker |
| B5. Moderation / business sign-off | Open / `NO-GO` | Open | rollout ownership and restriction model in [MAX_PILOT_LAUNCH_PLAYBOOK_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_PILOT_LAUNCH_PLAYBOOK_2026-04-09.md), readiness/health surfaces in [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) and [backend/apps/admin_ui/services/messenger_health.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/messenger_health.py) | moderation approval, business sign-off, named owner acknowledgement, live env readiness bundle | Product Ops + Launch Lead + Infra/SRE | Launch blocker |

### B1/B2 proof acceptance flow

```text
B1/B2 implementation changes
  -> targeted automated tests pass
  -> full backend suite passes
  -> live code review confirms shared-path integrity
  -> classify as code-level closed
  -> require pilot-env proof before promoting to pilot-level closed
```

## 4. Evidence Inventory

### Table 2. Evidence Inventory

| Evidence Item | Related Blocker | Type | Owner | Verified? | Notes |
| --- | --- | --- | --- | --- | --- |
| MAX-specific `WebAppData` validator in [auth.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py) | B1 | code | Backend Platform | Yes | Includes freshness, signature, and normalized MAX user extraction |
| MAX exchange auth enforcement in [candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py) | B1 | code | Backend Platform + Backend Identity | Yes | Rejects missing, stale, unbound, and mismatched MAX context before session bootstrap |
| `MAX_WEBAPP_AUTH_MAX_AGE_SECONDS` in [backend/core/settings.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py) and env examples | B1 | config contract | Backend Platform | Yes | Makes freshness policy explicit and configurable |
| Automated MAX auth tests in [tests/test_webapp_auth.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_webapp_auth.py) | B1 | automated test | QA + Security | Yes | Covers valid, tampered, stale, and invalid user-id cases |
| Automated shared exchange tests in [tests/test_candidate_portal_api.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_candidate_portal_api.py) | B1 | automated test | QA + Backend | Yes | Covers MAX accept/reject paths and stale/mismatch behavior |
| Fail-closed dedupe logic and health exposure in [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) | B2 | code | Backend Platform + Security | Yes | Redis required in prod-like mode; webhook rejects when unavailable |
| Automated duplicate/replay tests in [tests/test_max_bot.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_max_bot.py) | B2 | automated test | QA + Backend | Yes | Covers duplicate message/callback, blocked health, dedupe unavailable reject |
| End-to-end MAX regression proof in [tests/test_max_candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_max_candidate_flow.py) | B1, B2 | automated test | QA + Full-stack | Yes | Confirms valid progression after dedupe hardening |
| Full backend validation run: `make test` -> `1036 passed, 18 skipped` | B1, B2 | automated suite | QA + Engineering | Yes | Strong code-level confidence, not live pilot proof |
| Frontend route/test/build gates for MAX start path | B1, B4 | frontend validation | Frontend + QA | Yes | `start.test.tsx`, `lint`, `typecheck`, `build:verify` passed |
| Cohort audit runner in [scripts/max_pilot_cohort_audit.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/max_pilot_cohort_audit.py) | B3 | tooling | Backend Domain + Product Ops | Yes | Tool exists and can fail closed |
| Live cohort audit export on actual pilot data | B3 | operational proof | Product Ops + Backend Domain | No | Still missing |
| Real-client smoke matrix and transcripts | B4 | manual proof | QA + Product Ops | No | Still missing |
| Live pilot-env health/subscription/Redis snapshot | B2, B5 | operational proof | Infra/SRE + Backend Platform | No | Still missing |
| Moderation/business sign-off bundle | B5 | approval artifact | Product Ops + Launch Lead | No | Still missing |
| Named owner acknowledgement sheet | B3, B5 | operational approval | Launch Lead | No | Still missing |

## 5. Remaining Proof Gaps

### Table 3. Proof Gap Matrix

| Gap | Related Blocker | Why It Matters | Required Action | Blocking? | Closure Artifact |
| --- | --- | --- | --- | --- | --- |
| Live Redis-backed dedupe proof | B2 | code-level policy is not enough for pilot | capture pilot-env `/health`, `dedupe_ready=true`, `dedupe_mode=redis`, and subscription-ready state | Yes | archived health snapshot |
| Redis failure drill in prod-like env | B2 | fail-closed behavior must be proven operationally | simulate Redis unavailability and confirm webhook rejection plus blocked health | Yes | drill record + logs |
| Real duplicate/replay smoke in pilot env | B2 | provider retry semantics can differ from local tests | replay duplicate `message_created` and `message_callback` deliveries in target env | Yes | smoke transcript + logs |
| Real cohort audit execution | B3 | tooling existence is not cohort proof | run `scripts/max_pilot_cohort_audit.py --fail-on-blockers` on intended cohort | Yes | text/json audit export |
| Signed allowlist and cohort freeze | B3 | pilot must be narrow and interpretable | freeze candidate IDs, recruiter owners, city/source slice, and supported client set | Yes | signed allowlist artifact |
| Exclusion log for dirty candidates | B3 | prevents contamination drift | archive rejected candidates and reasons | Yes | cohort exclusion log |
| Real-client smoke matrix | B4 | official capability support is not real behavior proof | run manual smoke for iOS, Android, Desktop, and Web MAX clients as applicable | Yes | smoke matrix |
| `requestContact` fallback decision | B4 | launch cannot rely on ambiguous UX | either prove native behavior or formally accept manual-entry fallback per client | Yes | signed fallback note + smoke result |
| Browser portal fallback proof in actual client mix | B4 | fallback must be reachable and safe | verify bot-to-browser and app-to-browser recovery path on unsupported clients | Yes | smoke transcript |
| Moderation/business approval | B5 | external blockers remain real blockers | obtain explicit approval and archive it | Yes | sign-off record |
| Named owner acknowledgement | B5 | conditional launch needs accountable owners | collect owner acknowledgement for launch, monitoring, incidents, and stop decisions | Yes | ownership sheet |
| Monitoring/alerting readiness proof | B5 | hidden failures invalidate pilot control | prove dashboards, alert routes, and on-call ownership are active | Yes | monitoring readiness bundle |

### B3 cohort evidence review flow

```text
Select intended pilot cohort
  -> run owner preflight
  -> run scheduling integrity audit
  -> inspect blocking candidates
  -> exclude or repair dirty records
  -> freeze allowlist
  -> obtain owner acknowledgement
  -> accept or reject B3 for pilot start
```

### B4 client smoke evidence flow

```text
Define supported client/version matrix
  -> run deep-link smoke
  -> run open_app/startapp smoke
  -> run requestContact or manual-fallback smoke
  -> run resume/back-close/reminder smoke
  -> classify pass / fallback / exclude
  -> archive transcripts
  -> accept or reject B4 for pilot start
```

### B5 external sign-off flow

```text
Prepare launch evidence bundle
  -> collect moderation approval
  -> collect business sign-off
  -> confirm named owners
  -> confirm pilot-env readiness bundle
  -> archive approvals
  -> accept or reject B5 for pilot start
```

## 6. Residual Risks

### Table 6. Residual Risk Matrix

| Risk | Severity | Likelihood | Area | Mitigation | Accepted / Not Accepted |
| --- | --- | --- | --- | --- | --- |
| Live provider retries behave differently from local duplicate tests | High | Medium | Reliability | live duplicate/replay drill before pilot start; narrow cohort on day 1 | Accepted only for conditional-go |
| False-positive dedupe collapse under reused transport markers | High | Low-Medium | Reliability | pilot-env smoke plus day-1 monitoring for unexpected funnel stalls | Accepted only for conditional-go |
| Dirty cohort includes duplicate owner or `needs_manual_repair` candidate | High | Medium | Product Ops / Domain | mandatory audit + allowlist freeze | Not accepted |
| Real MAX clients diverge from official capability docs | High | Medium | Frontend / Product | manual smoke matrix; supported-client restriction | Not accepted until smoke passes |
| Public entry accidentally enabled | High | Low-Medium | Security / Ops | keep `MAX_BOT_ALLOW_PUBLIC_ENTRY=false`, config freeze, gate in review checklist | Not accepted |
| Browser fallback reduces conversion relative to native MAX path | Medium | Medium | UX / Conversion | use only on unsupported clients; monitor funnel drop; keep cohort narrow | Accepted |
| Missing moderation/business approval delays or invalidates launch | High | Medium | External / Ops | explicit sign-off gate | Not accepted |
| Missing live monitoring or owner acknowledgement causes slow incident response | High | Medium | Ops / Governance | launch evidence bundle must include monitoring and owner sheet | Not accepted |

## 7. Conditional Launch Restrictions

### Table 4. Conditional Launch Restrictions

| Restriction | Why Required | Owner | Can Be Lifted When | Explicitly Enforced How |
| --- | --- | --- | --- | --- |
| No live pilot traffic yet | `CONDITIONAL GO` does not equal pilot activation | Launch Lead | after all recheck gates pass | launch checklist + no invite send |
| Invite-only allowlist cohort only | keeps pilot interpretable and safe | Product Ops + Recruiter Ops | after successful pilot phase and fresh approval | allowlist / invite gating |
| Public entry disabled by default | avoids privacy and abuse expansion | Infra/SRE + Product Ops | only after separate approval and fresh smoke | `MAX_BOT_ALLOW_PUBLIC_ENTRY=false` |
| Supported-client matrix limited to manually proven clients | official docs are insufficient proof | QA + Frontend + Product Ops | after new client smoke bundle is archived | client list in pilot brief and operator instructions |
| Browser portal fallback allowed; Telegram business fallback forbidden | preserves shared backend path without transport drift | Frontend + Bot/Integration + Security | browser fallback may remain; Telegram fallback never | runbook and incident rules |
| MAX scheduling exposure only for clean cohort and proven clients | prevents dirty scheduling states from entering pilot | Backend Domain + Product Ops | after fresh integrity proof and client smoke | allowlist + UI/ops gating |
| Monitoring and stop conditions are mandatory from first invite | conditional launch must stay controlled | Launch Lead + Infra/SRE | never during pilot | dashboards, alert routes, daily review |
| No cohort expansion and no public-entry change on the same day | reduces attribution and ops ambiguity | Launch Lead + Product Ops | after pilot stabilizes and new approval | rollout control policy |

### Conditional launch restriction enforcement flow

```text
Conditional-go granted
  -> keep public entry off
  -> keep pilot invites paused until recheck gates green
  -> narrow supported-client list
  -> freeze cohort allowlist
  -> enable only approved surfaces
  -> monitor health/dedupe/session signals
  -> stop or constrain immediately on breach
```

## 8. Recheck Requirements Before Pilot Start

### Table 5. Recheck Gate Matrix

| Gate | Required Inputs | Decision Owner | Blocking? | Exit Criteria |
| --- | --- | --- | --- | --- |
| G1. B1/B2 Code Acceptance | targeted tests, full suite, live code review | Review Lead + Backend Platform | No, already passed | B1/B2 accepted as code-level closed |
| G2. Pilot-Env Ingress Acceptance | live `/health`, messenger health, Redis proof, subscription ready, failure drill | Infra/SRE + Security + Backend Platform | Yes | ingress healthy, Redis-backed dedupe proven, fail-closed behavior confirmed |
| G3. Cohort Acceptance | cohort audit export, allowlist freeze, exclusion log, owner acknowledgement | Product Ops + Backend Domain | Yes | clean cohort, no dirty records admitted |
| G4. Client Acceptance | smoke matrix, transcripts, fallback decisions, supported client list | QA + Frontend + Product Ops | Yes | required scenarios pass on supported clients; unsupported clients are excluded or routed to browser fallback |
| G5. External Approval Acceptance | moderation approval, business sign-off, named owner sheet, monitoring readiness bundle | Launch Lead + Product Ops + Infra/SRE | Yes | all external and governance artifacts archived |
| G6. Pilot Start Decision | G2-G5 complete, launch restrictions acknowledged, rollback ready | Launch Lead | Yes | pilot invite send may start |

## 9. Ownership and Decision Map

### Table 7. Ownership / Decision Matrix

| Area | Primary Owner | Secondary Owner | Decision Scope | Escalation Rule |
| --- | --- | --- | --- | --- |
| MAX auth trust boundary | Backend Platform + Security | Backend Identity | accept B1 closure, reject any second linkage path | escalate immediately on stale/tampered accept or auth bypass |
| Shared candidate/session contract | Backend Identity + Backend Domain | Bot/Integration | approve shared-path integrity and session bootstrap model | escalate on any MAX-only session path |
| Dedupe / replay safety | Backend Platform | Security + Infra/SRE | accept B2 env proof and failure drill | escalate on any `dedupe_ready=false`, duplicate side effect, or missing Redis |
| Cohort integrity | Product Ops | Backend Domain + Recruiter Ops | approve allowlist and exclusions | escalate on any ambiguity or `needs_manual_repair` candidate |
| Client capability matrix | QA | Frontend + Product Ops | approve supported client list and fallback policy | escalate on any unsupported client entering cohort |
| Monitoring / on-call readiness | Infra/SRE | Launch Lead | approve dashboards, alerts, response ownership | escalate on any missing alert path or unnamed owner |
| Moderation / business approval | Product Ops | Launch Lead | approve external readiness | escalate if any approval is missing or scope changes |
| Final pilot start | Launch Lead | All functional leads | decide whether to move from conditional-go to live pilot start | stop if any blocking gate is unresolved |

## 10. Multi-Agent Reconciliation Notes

### Conflict 1: Is B1 still open or already closed?

Initial conflict:
- one backend agent produced a stale read and claimed B1 remained open
- security review and live code inspection showed explicit MAX auth implementation in current code

Resolution:
- the stale backend input was re-run against current files
- final decision is based on current live code and tests

Accepted position:
- B1 is closed at code and architecture level
- B1 is not by itself a reason to keep current status at `NO-GO`

Residual risk:
- future feature work must keep all MAX entry points converged on shared `/api/candidate/session/exchange`

### Conflict 2: Does B2 count as fully closed after automated tests?

Conflicting positions:
- code review and tests show strong closure
- reliability and infra reviews insist that pilot readiness still needs live Redis and failure-drill evidence

Resolution:
- B2 is treated as `code-level closed`, but not `pilot-level fully closed`

Accepted position:
- B2 no longer blocks `CONDITIONAL GO`
- B2 still blocks actual pilot start until G2 passes

Residual risk:
- provider retry semantics and env drift can still invalidate local confidence

### Conflict 3: Is current overall status still `NO-GO` because B3/B4/B5 are open?

Conflicting positions:
- cohort, QA, and infra reviews each recommended `NO-GO` for actual pilot launch
- backend, security, and reliability reviews judged that architecture-critical blockers are retired

Resolution:
- the review separates `program-state` from `pilot-start authorization`

Accepted position:
- overall status can move to `CONDITIONAL GO`
- actual pilot start remains blocked

Residual risk:
- if teams interpret `CONDITIONAL GO` as permission to send invites, governance will fail

### Conflict 4: Is `requestContact` always a hard blocker?

Conflicting positions:
- architecture docs allow manual fallback
- playbook and client-validation review keep it as a blocking smoke item unless fallback is explicitly proven

Resolution:
- `requestContact` is not a standalone architecture blocker
- it remains a pilot blocking item until either:
  - native behavior is proven, or
  - manual fallback is explicitly accepted and verified per supported client

Residual risk:
- fallback may protect launch safety while still reducing conversion

### Conflict 5: Is browser portal fallback an acceptable substitute for native MAX continuity?

Conflicting positions:
- product-side concern: fallback can hide client gaps
- security and architecture reviews: browser fallback is acceptable only on the same shared backend path

Resolution:
- browser portal fallback remains allowed
- it cannot be used to bypass auth failures, identity mismatches, or unsupported governance

Residual risk:
- heavy reliance on browser fallback may indicate that the supported MAX matrix is too narrow for broader rollout

### Conflict 6: Missing source artifact

Issue:
- `MAX_PILOT_BLOCKERS_CLOSURE_PLAN_2026-04-09.md` is missing locally

Resolution:
- this review uses the already agreed blocker model plus live code, tests, backlog, and pilot playbook

Residual risk:
- there is one missing documentation artifact in the evidence chain
- this does not block the review itself, but it should be restored for auditability

## 11. Conditional GO Criteria

`CONDITIONAL GO` is justified only if all of the following are true:
- B1 is accepted as code-level closed
- B2 is accepted as code-level closed
- shared backend architecture remains canonical:
  - no MAX-only backend path
  - no second identity/session linkage path
  - no new scheduling write-path drift
- remaining blockers are explicitly classified as operational proof / governance blockers, not hidden architecture debt
- launch restrictions are acknowledged and enforceable:
  - invite-only cohort
  - public entry disabled
  - supported clients only
  - browser fallback allowed
  - Telegram business fallback forbidden

`CONDITIONAL GO` does not authorize:
- broad rollout
- public entry
- unsupported clients
- skipping cohort audit
- skipping real-client smoke
- skipping moderation/business sign-off

To convert conditional-go into actual pilot-start authorization, the minimum remaining proof set is:
- G2 live ingress/Redis/subscription proof
- G3 clean cohort evidence
- G4 real-client smoke evidence
- G5 external approval and owner bundle

## 12. Final Review Verdict

Current recommended status:
- `CONDITIONAL GO`

Interpretation:
- the program is no longer blocked by core architecture or code-level trust-boundary gaps
- the program is still blocked from actual pilot start by missing operational proof and approvals

## CONDITIONAL GO REVIEW VERDICT

1. Можно ли сейчас перевести статус из `NO-GO` в `CONDITIONAL GO`?

Да, можно.

Но только как статус финального preflight и decision-gate phase.
Это не `GO` на запуск pilot traffic.

2. Если да, то при каких жёстких ограничениях?

- без live pilot traffic до прохождения G2-G5
- только invite-only / allowlist cohort
- `MAX_BOT_ALLOW_PUBLIC_ENTRY=false`
- только smoke-proven client matrix
- browser portal fallback допустим
- Telegram business fallback запрещён
- без cohort expansion и без public-entry changes в один день
- с обязательным monitoring + stop-condition ownership с первого дня

3. Какие blocker-ы считаются полностью закрытыми?

- B1:
  - полностью закрыт на code-level и architecture-level
- B2:
  - полностью закрыт на code-level и policy-level
  - не считается полностью закрытым на pilot-level, пока нет live env proof

4. Какие blocker-ы остаются частично или полностью открытыми?

- B2:
  - частично открыт на pilot-level
- B3:
  - частично открыт, потому что есть tooling, но нет real cohort proof
- B4:
  - полностью открыт как manual/client validation blocker
- B5:
  - полностью открыт как external operational blocker

5. Какой минимальный набор доказательств ещё нужен до фактического pilot start?

- live `/health` + messenger health snapshot with Redis-backed dedupe and ready subscription
- Redis failure drill with blocked-ingress proof
- `scripts/max_pilot_cohort_audit.py --fail-on-blockers` export on actual cohort
- signed allowlist / cohort freeze / exclusion log
- manual smoke matrix with transcripts for `deep-link`, `open_app`, `requestContact` or approved fallback, resume/back-close, reminder re-entry
- explicit supported-client list
- moderation/business sign-off
- named owner acknowledgement sheet
- monitoring/alerting readiness bundle

6. При каких условиях статус должен оставаться `NO-GO`?

- если кто-то трактует `CONDITIONAL GO` как разрешение сразу открыть pilot traffic
- если G2-G5 не закрыты
- если public entry планируется включить до отдельного approval
- если supported client matrix не подтверждён руками
- если cohort audit на реальных данных не выполнен
- если moderation/business sign-off отсутствует
- если Redis-backed dedupe не доказан в live env

7. Что должно произойти, чтобы статус стал полноценным `GO`?

- B2 должен получить live pilot-env proof
- B3 должен получить clean cohort evidence и signed allowlist
- B4 должен получить archived real-client smoke evidence и fallback decisions
- B5 должен получить все approvals, owner acknowledgement, monitoring/alerting proof
- G2-G5 должны быть formally accepted
- Launch Lead должен провести финальный pilot-start decision review без unresolved blocking dependency
