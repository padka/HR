# Risk Register: Candidate Channels

## Risk Scale

- Likelihood: `Low / Medium / High`
- Impact: `Low / Medium / High / Critical`

## Risk Register

| ID | Category | Risk | Likelihood | Impact | Mitigation | Suggested owner |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | Technical | Telegram remains hidden source of truth even after portal launch | Medium | Critical | Explicitly move journey state, reminders and status transitions to candidate-centric services before broad rollout | Backend lead |
| R2 | Technical | Candidate duplicates across phone/email/messenger channels | High | High | Introduce channel accounts + phone/email dedup + admin merge tooling | Backend lead |
| R3 | Technical | Bot flow regresses during decoupling | Medium | High | Keep bot as adapter over shared services gradually; run dual-path regression tests | Backend + QA |
| R4 | Technical | Reminder jobs stay bound to `candidate_tg_id` and break fallback strategy | High | High | Refactor reminder scheduling to resolve delivery channel at send time, not schedule time | Backend lead |
| R5 | Technical | CRM outbound chat remains Telegram-only | High | High | Route outbound through notification/communication abstraction and preferred channel logic | Backend lead |
| R6 | Technical | Max integration is assumed ready but is not production-grade | Medium | Medium | Treat Max as phase-after-core adapter; harden identity binding and end-to-end tests before rollout | Integrations engineer |
| R7 | Product | OTP / auth friction reduces completion rate | Medium | High | Minimize steps, prefill from invite token, test OTP vs hybrid auth | Product + frontend |
| R8 | Product | Portal becomes too heavy for mobile mass-hiring users | Medium | High | Mobile-first design, short steps, autosave, fast load budget | Frontend lead |
| R9 | Product | Candidate does not understand current status or next action | Medium | High | Use simplified external status taxonomy and one primary CTA per screen | Product + design |
| R10 | Product | Too many fallback messages create notification fatigue | Medium | Medium | Per-message fallback rules, quiet hours, rate limiting, dedupe sends | Product ops |
| R11 | Operational | Recruiters keep working from Telegram habits and ignore portal states | Medium | High | Surface delivery history and next action directly in CRM; update playbooks | Ops lead |
| R12 | Operational | Second channel launched before portal is stable, splitting focus | High | High | Gate second adapter behind portal MVP success criteria | Program lead |
| R13 | Operational | Manual scheduling remains out-of-band and candidates still get stuck without slots | Medium | High | Add portal “request another time” path and recruiter queue visibility | Product + backend |
| R14 | Analytics | Old bot-centric events and new portal events produce fragmented reporting | High | Medium | Introduce unified event taxonomy and mapping table early | Data/analytics |
| R15 | Analytics | Channel attribution is incomplete for campaign-level decisions | Medium | Medium | Persist entry channel, current channel, source and fallback metadata in all critical events | Data/analytics |
| R16 | Security | One-time links can be replayed or leaked | Medium | High | Short TTL, single-use tokens, device binding when practical, audit token usage | Security/backend |
| R17 | Security | OTP abuse / SMS flooding | Medium | High | Rate limit requests, captcha/risk checks, provider anti-abuse tooling | Security/backend |
| R18 | Security | Candidate documents and PII expand data exposure surface | Medium | High | Minimize fields in MVP, encrypt storage, scoped access, retention policy | Security/backend |
| R19 | Legal | SMS/email outreach without proper consent/compliance creates legal exposure | Medium | High | Confirm lawful basis and consent wording; log consent/source | Legal + ops |
| R20 | Legal | Personal data crosses new vendors/channels without contract review | Medium | High | Vendor due diligence, DPAs, region/storage review | Legal + procurement |
| R21 | Vendor | SMS provider instability or pricing spikes hurt fallback economics | Medium | Medium | Multi-provider strategy or fast-switch abstraction; message prioritization | Platform/ops |
| R22 | Vendor | WhatsApp / messenger policies constrain message types or onboarding | Medium | Medium | Use WhatsApp only as optional notification channel, not core journey runtime | Integrations |
| R23 | Delivery | Portal release ships without clear deep-link strategy, so re-entry remains weak | Medium | Critical | Every reminder and outreach must carry exact-step deep link | Product + frontend |
| R24 | Delivery | Feature rollout across all cities at once hides operational problems | Medium | High | Feature flags by city/source/recruiter group | Program lead |
| R25 | UX | Candidate loses progress due to session expiration or validation errors | Medium | High | Autosave server-side per answer and resume on re-auth | Frontend + backend |
| R26 | UX | Status center exposes internal recruiter jargon that confuses candidates | Medium | Medium | Separate external status vocabulary from internal CRM statuses | Product |
| R27 | Data quality | Phone/email normalization inconsistent, causing false dedup or missed merges | Medium | High | Standardize normalization library and test dataset | Backend |
| R28 | Scheduling | Concurrent booking/reschedule flows create race conditions in new portal APIs | Medium | High | Reuse existing reservation locking/idempotency; add portal-specific concurrency tests | Backend |
| R29 | Change management | Teams expect “second bot” and underinvest in shared core | High | High | Make roadmap dependency explicit and tie funding to web-first milestones | Engineering leadership |
| R30 | Business | Candidate audience for MAX/VK is overestimated | Medium | Medium | Launch as limited pilot with source-specific cohorts and clear success thresholds | Product/marketing |

## Top Risks To Tackle First

### Critical first-wave risks

1. `R1` Telegram remains hidden source of truth.
2. `R2` Duplicate candidates across channels.
3. `R4` Reminders remain Telegram-bound.
4. `R7` Auth friction in portal.
5. `R23` No exact-step deep-link strategy.

These five risks determine whether the multi-channel initiative genuinely reduces loss or just adds another surface over the same bottleneck.

## Stage-Based Risk View

### Before Stage 1

Highest risks:

- `R1`, `R2`, `R29`

### Before Stage 2

Highest risks:

- `R7`, `R8`, `R25`

### Before Stage 3

Highest risks:

- `R4`, `R10`, `R21`

### Before Stage 4

Highest risks:

- `R6`, `R12`, `R30`

## Monitoring Signals

### Product signals

- start-to-complete conversion in portal
- share of interrupted sessions later resumed
- slot booking rate after switching from messenger to web
- candidate complaints about auth or status clarity

### Delivery signals

- fallback-trigger rate by message type
- successful resume after fallback
- unreachable-candidate rate by channel
- reminder conversion by channel

### Operational signals

- recruiter manual interventions per candidate
- candidates stuck in waiting-slot without follow-up
- median time from Test1 completion to booking

## Acceptance Gates For Rollout

### Gate A. Portal beta

- journey progress survives interruption
- candidate can complete screening and booking without Telegram
- no material duplicate spike

### Gate B. Fallback activation

- SMS/email links work end to end
- recruiters see fallback history
- delivery metrics are queryable

### Gate C. Second adapter rollout

- portal completion rate stable
- journey/session core has replaced Telegram-only state for key flows
- operations team trained on new channel history semantics

## Final Risk Recommendation

Самый опасный сценарий для команды:

**запустить второй мессенджер раньше, чем будут решены `candidate_id`-first identity, portal resume state и fallback orchestration.**

В этом случае система станет не отказоустойчивой, а просто multi-fragile.
