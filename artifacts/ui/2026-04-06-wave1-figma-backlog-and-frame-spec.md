# Wave 1 Figma-Ready Backlog And Frame Spec

## Executive Summary

This document is the Wave 1 extraction from the canonical screen audit in [2026-04-06-page-design-audit-and-figma-handoff.md](/Users/mikhail/Projects/recruitsmart_admin/artifacts/ui/2026-04-06-page-design-audit-and-figma-handoff.md). It does not replace that document and does not re-audit route inventory. It turns the already approved screen scope into a Figma-ready backlog and frame specification.

Wave 1 is the minimum Figma package that improves recruiter speed and clarity. It covers recruiter triage, queue processing, candidate movement, and candidate decisioning across the shared recruiter-web shell, dashboard, incoming queue, candidate worklist, candidate detail, and the shared blocked/warning/repair states attached to those surfaces.

Wave 1 intentionally excludes candidate portal, admin CRUD, system-heavy surfaces, and all dormant pages. The goal is to avoid diluting the first wave with secondary setup or cross-channel work and to deliver one cohesive recruiter-operating package that a designer or Figma-capable agent can assemble without re-analyzing the repo.

## Wave 1 Scope

Scope source map:

- canonical audit: [2026-04-06-page-design-audit-and-figma-handoff.md](/Users/mikhail/Projects/recruitsmart_admin/artifacts/ui/2026-04-06-page-design-audit-and-figma-handoff.md)
- route tree: [route-map.md](/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/route-map.md)
- recruiter grammar anchors: [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md), [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
- backend design boundary: [candidate-state-contract.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/candidate-state-contract.md)

| Family | Included routes | Why now | Primary user | Primary job to be done | Desktop | Mobile | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Shell foundation | `/app/*` chrome around `/app/dashboard`, `/app/incoming`, `/app/candidates`, `/app/candidates/$candidateId` | Wave 1 screens need one consistent navigation, page framing, title/action behavior, and mobile shell state | recruiter, admin acting in recruiter workflow | Orient quickly, switch between triage/worklist/detail without losing context | Required | Required | P1 |
| Dashboard | `/app/dashboard` | This is the control tower and first attention surface for recruiter/admin triage | recruiter, admin | Scan KPIs and route urgent candidates into action | Required | Required | P0 |
| Incoming queue | `/app/incoming` | This is the main processing queue for new candidates and scheduling handoff | recruiter, admin | Triage incoming candidates and send them to the next safe step | Required | Required | P0 |
| Candidate worklist | `/app/candidates` | This is the main grouping and movement surface for recruiter execution | recruiter, admin | Search, segment, inspect, and move candidates through the funnel | Required | Required | P0 |
| Candidate detail | `/app/candidates/$candidateId` | This is the main decision and action surface with the richest recruiter contract | recruiter, admin | Understand candidate state, act, recover from blockers, and resolve next step | Required | Required | P0 |
| Shared blocked/warning/repair states | cross-surface states attached to dashboard, incoming, worklist, and candidate detail | Backend already exposes blockers, conflicts, reconciliation, and repair visibility; they cannot be deferred to a later Figma pass | recruiter, admin | Understand why an action is blocked and what the recovery path is | Required | Required where the host screen is mobile | P0 |

## Frame Specification

Frame naming rule:

- `W1 / {Family} / {Surface} / {Viewport} / {State}`

Locked viewport strategy:

- Desktop primary frame: `1440`
- Desktop dense-check frame: `1280`
- Desktop minimum-supported check: `1024`
- Mobile primary frame: `390`
- Mobile check frame: `430`

### Wave 1 Frame Inventory

| Frame name | Route mapping | Viewport | Required states | Empty/loading/error | Overlays | Reusable layout zones |
| --- | --- | --- | --- | --- | --- | --- |
| `W1 / Shell / Desktop / Base / Default` | `/app/dashboard`, `/app/incoming`, `/app/candidates`, `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: no. Primary: `1440`. Check: `1280`, `1024` | default shell, active nav item, unread chat badge, detail-route back behavior | loading shell placeholder only if profile/nav data is unresolved; permission redirect not designed here | none in base frame | desktop app header, page title row, page canvas, content width rule, ambient background |
| `W1 / Shell / Mobile / Base / Default` | same routes as desktop shell | Desktop required: no. Mobile required: yes. Primary: `390`. Check: `430` | default shell, active tab, back state, profile affordance | mobile loading shell only if route depends on shell data; no separate empty state | More sheet closed and open states must be linked from this frame | mobile header, mobile tab bar, More sheet, content safe-area spacing |
| `W1 / Dashboard / Overview / Desktop / Default` | `/app/dashboard` | Desktop required: yes. Mobile required: no. Primary: `1440`. Check: `1280`, `1024` | KPI overview, triage lanes, top filters, leaderboard, reusable triage card | include loading, empty triage lane, API error banner | schedule action handoff into candidate detail or scheduling modal | page header, metric strip, lane header, lane list, right-side secondary analytics zone |
| `W1 / Dashboard / Overview / Mobile / Default` | `/app/dashboard` | Desktop required: no. Mobile required: yes. Primary: `390`. Check: `430` | condensed KPI stack, triage card stack, compact page controls | include loading, no work, API error | none on base mobile frame | mobile page header, KPI stack, lane stack, compact candidate card list |
| `W1 / Dashboard / TriageCard / Desktop / Expanded` | `/app/dashboard` | Desktop required: yes. Mobile required: optional as card specimen. Primary: `1440` | expanded candidate card with next action, state context, scheduling context, risk banner | include card-level no-risk variant and risk-present variant in annotations | no modal; this is a state specimen | candidate identity, primary action block, one-line context, risk banner, actions row |
| `W1 / Incoming / Queue / Desktop / Default` | `/app/incoming` | Desktop required: yes. Mobile required: no. Primary: `1440`. Check: `1280`, `1024` | queue list, basic filters, advanced filters collapsed, schedule CTA, assign CTA, preview CTA | include loading, empty queue, no results, API error | schedule modal entry, test preview modal entry | page header, filter bar, queue list, card actions, inline helper/status rows |
| `W1 / Incoming / Queue / Desktop / AdvancedFilters` | `/app/incoming` | Desktop required: yes. Mobile required: no. Primary: `1440` | same as default plus advanced filters expanded | include no-results-after-filtering treatment | no extra modal in base state | header, basic filter row, advanced filter panel, queue list |
| `W1 / Incoming / Queue / Mobile / Default` | `/app/incoming` | Desktop required: no. Mobile required: yes. Primary: `390`. Check: `430` | stacked queue cards, compact actions, filters compressed for mobile | include loading, empty queue, no results, API error | schedule modal and test preview modal must be available as mobile sheets/modals | mobile page header, compact filter trigger, candidate cards, sticky bottom action safety spacing |
| `W1 / Incoming / Modal / Schedule / Default` | `/app/incoming` | Desktop required: yes. Mobile required: yes. Desktop modal on `1440`; mobile sheet on `390` | manual scheduling path, existing slot path, date/time inputs, slot selection, confirm state | include validation error, no slots available, scheduling conflict response, success feedback | desktop modal and mobile sheet variants | modal header, body form area, supporting context, destructive/confirm footer |
| `W1 / Incoming / Modal / TestPreview / Default` | `/app/incoming` | Desktop required: yes. Mobile required: yes. Desktop modal on `1440`; mobile sheet on `390` | candidate preview summary, test summary, next-action CTA from preview | include loading and API error inside modal context | desktop modal and mobile sheet variants | modal header, summary stack, preview body, footer CTA row |
| `W1 / Worklist / List / Desktop / Default` | `/app/candidates` | Desktop required: yes. Mobile required: no. Primary: `1440`. Check: `1280`, `1024` | filter bar, candidate rows/cards, selection-only helpers, route into detail | include loading, empty list, no results, API error | none in base frame | page header, filter bar, results header, list body, bulk-selection helper rail |
| `W1 / Worklist / Kanban / Desktop / Default` | `/app/candidates` | Desktop required: yes. Mobile required: no. Primary: `1440`. Check: `1280`, `1024` | canonical kanban with column headers, guided vs locked columns, candidate cards, safe interactive columns | include loading, empty column, no results, API error | no modal in base frame; blocked explanation links to dedicated state frame | page header, filter bar, kanban strip, column header grammar, card stacks |
| `W1 / Worklist / Kanban / Desktop / BlockedMove` | `/app/candidates` | Desktop required: yes. Mobile required: no. Primary: `1440` | blocked move explanation tied to backend contract and `target_column` boundary | include blocked response, issue-code note, recoverable/manual-resolution-required note | inline explanation surface only; no new modal required unless product adds one later | same kanban zones plus blocked explanation callout area |
| `W1 / Worklist / Mobile / Default` | `/app/candidates` | Desktop required: no. Mobile required: yes. Primary: `390`. Check: `430` | mobile list/card mode, no desktop kanban, compact filters, quick route to detail | include loading, empty list, no results, API error | none in base frame | mobile page header, compact filter zone, candidate card list, safe touch targets |
| `W1 / Candidate Detail / Desktop / Overview` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: no. Primary: `1440`. Check: `1280`, `1024` | header, pipeline, action center, lifecycle, scheduling, risks, context/history, tests entry points | include loading, full-page API error, no critical blocker variant | drawer and modal entry points only | page header, candidate hero, pipeline strip, action center, section stack, secondary side surfaces |
| `W1 / Candidate Detail / Mobile / Profile` | `/app/candidates/$candidateId` | Desktop required: no. Mobile required: yes. Primary: `390`. Check: `430` | mobile profile tab, action center, lifecycle/scheduling/risk summary | include loading and API error | chat drawer/sheet and modal entry points | mobile header, mobile tab set, hero, action center, section stack |
| `W1 / Candidate Detail / Mobile / Tests` | `/app/candidates/$candidateId` | Desktop required: no. Mobile required: yes. Primary: `390`. Check: `430` | mobile tests tab with transition from profile tab | include loading and API error | test preview/report preview hooks if visible in current UI | mobile header, mobile tab set, tests content area |
| `W1 / Candidate Detail / Drawer / Chat` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: yes. Desktop drawer on `1440`; mobile sheet on `390` | chat open, draft seeded, channel context visible | include loading, empty conversation, delivery error, send error | drawer/sheet itself is the overlay | drawer header, message list, composer, helper/status strip |
| `W1 / Candidate Detail / Drawer / Insights` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: yes. Desktop drawer on `1440`; mobile sheet on `390` | insights open, AI/context details visible | include loading, empty insight, API error | drawer/sheet overlay | drawer header, insight body, supporting note zone |
| `W1 / Candidate Detail / Modal / Schedule Interview` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: yes. Desktop modal on `1440`; mobile sheet on `390` | interview scheduling path, time selection, confirmation | include validation, scheduling conflict, success feedback | modal/sheet overlay | modal header, body form, supporting context, footer CTA |
| `W1 / Candidate Detail / Modal / Schedule Intro Day` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: yes. Desktop modal on `1440`; mobile sheet on `390` | intro day scheduling path, confirmation | include validation, blocked scheduling, success feedback | modal/sheet overlay | modal header, form/context body, footer CTA |
| `W1 / Candidate Detail / Modal / Reject Confirm` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: yes. Desktop modal on `1440`; mobile sheet on `390` | destructive confirmation, reason capture if relevant, safe cancel | include validation and success feedback | modal/sheet overlay | destructive modal header, reason block, confirm/cancel footer |
| `W1 / Candidate Detail / State / Scheduling Conflict` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: optional adaptation note. Primary: `1440` | surfaced conflict, blocked action, resolution guidance, write-owner visibility | include warning vs blocked severity, API follow-up failure note | may link to repair entry; no separate modal required | action center, scheduling context block, risk/blocker banner, recovery hint zone |
| `W1 / Candidate Detail / State / Reconciliation Warning` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: optional adaptation note. Primary: `1440` | warning banner driven by `state_reconciliation`, issue summary, non-blocking caution | include warning-only and escalated caution variants | none | action center top, banner zone, supporting detail note, section continuation |
| `W1 / Candidate Detail / State / Repair Entry` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: optional adaptation note. Primary: `1440` | visible `repair_workflow`, allowed action selection, required confirmations, audit note | include `allow_with_warning` and `needs_manual_repair` framing | confirmation modal may be linked if repair requires it | scheduling block, repair action panel, confirmation requirements zone |
| `W1 / Candidate Detail / State / Repair Denied` | `/app/candidates/$candidateId` | Desktop required: yes. Mobile required: optional adaptation note. Primary: `1440` | deny path, failure reason, safe next step copy | include retryable false/true note if surfaced | confirm/result modal optional if product already separates it | banner/result zone, denied explanation block, next-step guidance |

## Shared Grammar

Wave 1 recruiter surfaces must use one shared UI grammar. Designers should not invent route-local hierarchies for dashboard, incoming, worklist, and candidate detail.

Locked top-of-surface order:

1. page header
2. primary action area
3. one-line state context
4. risk/blocker banner
5. lifecycle strip
6. scheduling context block
7. queue/worklist or detail body

### Normative Grammar Rules

| Grammar item | Rule |
| --- | --- |
| Header pattern | Title first, compact subtitle second, role-aware utility actions on the right. No decorative hero panel, no marketing copy, no oversized summary card above work content. |
| Primary action area | The backend-owned next action is always the strongest CTA. It must appear before filters, tables, or secondary analytics on recruiter decision surfaces. |
| One-line state context | Operational context stays compressed to one readable line and should answer what is happening now, not repeat raw status labels. |
| Risk/blocker banner | Driven by `blocking_state` and `state_reconciliation`, never by route-local heuristics. If the backend surfaces a blocker or warning, the banner appears in the shared position. |
| Lifecycle strip | Always visible near the top on candidate-facing recruiter surfaces. It must not be buried below tests, AI, or history. |
| Scheduling context block | Separate from lifecycle. It must explain slot state, ownership, assignment-vs-slot tension, or surfaced scheduling conflict. |
| Queue/worklist context | Worklist bucket, urgency, and triage meaning must be visible on cards and list/kanban headers. |
| Card grammar | Candidate identity -> next action -> one-line context -> risk/banner -> lifecycle/scheduling snippets -> secondary actions. |
| Detail section hierarchy | `Action center` first, then `Lifecycle`, `Scheduling`, `Risks & blockers`, `Context & history`. Tests and AI remain secondary and cannot displace the top decision stack. |

### Mini Component Catalog

| Component | Purpose | Must appear in Wave 1 |
| --- | --- | --- |
| Page header | Shared route title, subtitle, and utility actions | yes |
| Recruiter action block | Backend-owned next action container with explanation and CTA | yes |
| Recruiter risk banner | Shared warning/blocker surface | yes |
| Lifecycle strip | Compact lifecycle status visualization | yes |
| Scheduling context block | Scheduling ownership and next-step context | yes |
| Candidate identity block | Name, city, owner, and compact metadata | yes |
| Queue/worklist card | Shared card grammar for dashboard/incoming/worklist | yes |
| Kanban column header | Header with `interactive`, `guided`, `system` treatment and `droppable` meaning | yes |

## Mandatory States & Overlays

| State / overlay | Applies to | Trigger contract | Must exist in Wave 1 Figma |
| --- | --- | --- | --- |
| blocked action state | incoming, worklist, candidate detail | `blocking_state` on recruiter write error | yes |
| scheduling conflict state | candidate detail, incoming, worklist | `blocking_state.code = scheduling_conflict`, `scheduling_summary`, conflict outcomes `block` or `needs_manual_repair` | yes |
| reconciliation warning state | dashboard cards, incoming cards, worklist cards, candidate detail | `state_reconciliation` issues | yes |
| repair workflow entry | candidate detail state surface | `repair_workflow` present with allowed actions or confirmations | yes |
| repair denied state | candidate detail state surface | repair endpoint deny path with `failure_reason` or denied result state | yes |
| guided vs locked kanban explanation | worklist kanban | `droppable`, `interactive/guided/system`, canonical `target_column` boundary | yes |
| confirm / destructive confirmation modal | candidate detail, incoming where destructive action exists | recruiter action requires confirm or destructive decision | yes |
| success feedback state | incoming, worklist, candidate detail | successful write or scheduled action | yes |
| empty list | dashboard lanes, incoming, worklist | valid empty payload | yes |
| no results after filtering | incoming, worklist | filter combination returns zero items | yes |
| no candidates / no work | dashboard, incoming, worklist | queue/worklist is valid but has nothing actionable | yes |
| loading skeleton / spinner state | all Wave 1 surfaces | async query unresolved | yes |
| API error state | all Wave 1 surfaces | failed query or failed overlay fetch | yes |
| permission denied | shell-linked recruiter surfaces only where host screen is role-restricted | route or action unavailable by role | yes, but only if already relevant to the host surface |
| stale session / stale link | portal only | stale token/session flow | no, deferred with portal |

Contract language to preserve in annotations:

- `blocking_state`
- `state_reconciliation`
- `repair_workflow`
- `droppable`
- canonical `target_column`
- conflict outcomes: `block`, `allow_with_warning`, `needs_manual_repair`

## Prototype Flow Map

| Flow | Start frame | Intermediate states | End frame | Critical decision points |
| --- | --- | --- | --- | --- |
| List -> Detail | `W1 / Worklist / List / Desktop / Default` | candidate selected from list/card | `W1 / Candidate Detail / Desktop / Overview` | row/card click, preserve filter context, mobile back behavior |
| Dashboard/Incoming -> Detail | `W1 / Dashboard / Overview / Desktop / Default` and `W1 / Incoming / Queue / Desktop / Default` | triage card expanded or queue card opened | `W1 / Candidate Detail / Desktop / Overview` | open profile vs open scheduling path |
| Kanban -> Detail / Blocked move | `W1 / Worklist / Kanban / Desktop / Default` | drag allowed, drag blocked, guided/system explanation surfaced | `W1 / Candidate Detail / Desktop / Overview` or `W1 / Worklist / Kanban / Desktop / BlockedMove` | `droppable` decision, guided vs locked handling, blocked message visibility |
| Detail -> Action / Blocked / Repair | `W1 / Candidate Detail / Desktop / Overview` | destructive confirm, scheduling conflict, reconciliation warning, repair entry | success feedback state or `W1 / Candidate Detail / State / Repair Denied` | primary CTA execution, blocked response, repair allowed vs denied |
| Incoming -> Schedule modal | `W1 / Incoming / Queue / Desktop / Default` | schedule modal open, manual path vs existing slot path | queue success feedback state | manual vs existing slot path, validation and conflict handling |

Portal flow is explicitly deferred from Wave 1.

## Figma File Structure

Wave 1 file layout:

1. `00 Readme`
2. `01 Foundations`
3. `02 Shell`
4. `03 Dashboard`
5. `04 Incoming`
6. `05 Worklist`
7. `06 Candidate Detail`
8. `07 States & Overlays`
9. `08 Components`
10. `09 Prototype Flows`
11. `10 Handoff Notes`

### Page Rules

| Area | Rule |
| --- | --- |
| Pages | Use the page list above exactly for Wave 1. |
| Sections | Inside each page, separate `Desktop`, `Mobile`, `State Specimens`, and `Overlays` as distinct sections. |
| Frame naming | Always use `W1 / {Family} / {Surface} / {Viewport} / {State}`. |
| Component groups | `Shell`, `Headers`, `Cards`, `Banners`, `Lifecycle`, `Scheduling`, `Kanban`, `Drawers`, `Modals`. |
| Tokens/styles expectations | Reuse existing Liquid Glass v2 semantics, dark/light parity, `Manrope` and `Space Grotesk`. No new color system and no visual reset. |
| Prototype zones | Keep clickable flow frames only in `09 Prototype Flows`. |
| Annotation zones | Reserve a fixed right-side annotation rail in each major frame for design-dev notes, contract mapping, and open questions. |

### Handoff Convention

| Zone | Meaning |
| --- | --- |
| Left / main canvas | Final UI frame |
| Right annotation rail | Behavior notes, contract fields, edge-case notes, open questions |
| Bottom strip | Linked overlays/states for the same frame family |
| `08 Components` only | Component specimen frames and shared grammar parts |

## What Is Deferred

Deferred to Wave 2+:

- candidate portal entry and journey
- Telegram Mini App
- admin recruiter CRUD
- slots
- calendar
- messenger
- copilot
- profile
- system
- all dormant pages

These are intentionally out of Wave 1 so the first design package stays recruiter-speed focused and can be assembled without mixing triage surfaces with admin setup or cross-channel experiences.

## Assumptions

- The current audit file remains the source map. This document is a Wave 1 extraction and specification, not a replacement.
- `Recruiter list` in this context means the candidate worklist at `/app/candidates`, not admin recruiter CRUD at `/app/recruiters`.
- Candidate portal is out of Wave 1 unless product direction changes later.
- Admin recruiter CRUD is out of Wave 1 even though the route exists in the mounted tree.
- Frame specs are written for direct Figma assembly by a human designer or a later Figma-capable agent.
- Runtime shell switches to mobile behavior at `<= 480px` and desktop starts at `>= 1024px`, based on current frontend tokens.
- No runtime or public API changes are required. The only new interfaces introduced here are internal design-ops conventions: frame naming, file structure, and recruiter-surface grammar.
- Figma file creation itself still depends on later manual assembly or a runtime with working Figma access.
