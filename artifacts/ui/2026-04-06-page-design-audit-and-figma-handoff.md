# Attila Recruiting Page Design Audit And Figma Handoff

## Status

- Date: `2026-04-06`
- Scope: mounted SPA routes from [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- Route count in scope: `37`
- Canonical references used:
  - [docs/frontend/route-map.md](/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/route-map.md)
  - [docs/frontend/screen-inventory.md](/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/screen-inventory.md)
  - [docs/frontend/design-system.md](/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/design-system.md)
  - [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)
- Figma status in this session: direct Figma MCP creation is currently unavailable, because no Figma MCP resources/templates are exposed in the runtime.

## What This Report Is For

This document is the designer handoff for the current product surface. It is meant to:

1. enumerate all real pages that exist in the system now
2. define what each page must contain in design
3. define which states must exist in Figma
4. define how to structure one shared Figma file for further editing

## Current Visual Baseline To Preserve

The current frontend already has a usable product grammar. The design work should systematize and improve it, not replace it with abstract concept art.

- Base visual direction: Liquid Glass v2 over dense CRM surfaces.
- Themes: dark is default, light exists and must remain supported.
- Typography: `Manrope` for body/UI, `Space Grotesk` for display/headings.
- Interaction model: decision-first, action-first CRM, especially on `incoming`, `dashboard`, `candidates`, and `candidate detail`.
- Shell rule: `/app/*` uses shared desktop/mobile shell; `/app/login`, `/candidate/*`, `/tg-app/*` live outside that shell.
- Mobile rule: pages may structurally differ from desktop, but actions and state semantics must match.

## Design Invariants

These rules should be reflected in Figma components and page layouts:

- Do not hide operational status behind decorative cards.
- Next action, blocker, scheduling state, and channel health must stay visible above secondary content.
- Filters, tables, kanban, drawers, and modals are first-class design surfaces, not implementation leftovers.
- Candidate-facing portal and Telegram mini app should feel intentionally related to the admin product, but not share the admin shell.
- Every major page needs desktop and mobile variants when the route is used by recruiters/admins on mobile.

## Product Families

The current system splits cleanly into these design families:

1. Shared app shell and authentication
2. Recruiter operational surfaces
3. Candidate workbench surfaces
4. Admin setup / CRUD surfaces
5. Candidate-facing portal
6. Telegram Mini App for recruiters

## Shared Surfaces

| Surface | Routes | Purpose | Must be designed in Figma | Priority |
| --- | --- | --- | --- | --- |
| App shell | all `/app/*` except `/app/login` | Main navigation, page framing, role-aware entry | Desktop shell, mobile header, mobile tab bar, More sheet, active/hover/pressed states, unread chat badge, ambient background variants | High |
| Login page | `/app/login` | Authentication entry | Login card, loading, validation error, legacy link, light/dark variants | High |
| SPA landing | `/app` | Simple entry/redirect surface | Minimal landing state; can stay compact and low-investment | Low |

## Recruiter Operational Surfaces

| Route | Audience | Main goal | Core blocks to design | Mandatory states / variants | Priority |
| --- | --- | --- | --- | --- | --- |
| `/app/dashboard` | admin, recruiter | Control tower for metrics and urgent queue | KPI summary, recruiter leaderboard, incoming triage cards, filters, schedule modal entry points | Desktop overview, mobile condensed overview, triage card expanded/collapsed, loading, empty, error | High |
| `/app/incoming` | admin, recruiter | Process new candidates and assign next step | Queue cards, persisted filters, advanced filters, recruiter assignment, schedule modal, test preview modal | Default queue, advanced filters open, schedule flow, test preview, empty, error, mobile stack | High |
| `/app/slots` | admin, recruiter | Manage slot inventory and booking states | Filters, table/card list, row sheet, booking modal, manual booking modal, reschedule modal, bulk actions | Desktop table, mobile cards, row sheet open, booking states, empty, no results | High |
| `/app/slots/create` | admin, recruiter | Create single slot or slot series | Mode switch, single form, bulk form, timezone preview, validation rows, success toast | Single mode, bulk mode, validation errors, success, recruiter/mobile-safe layout | Medium |
| `/app/calendar` | admin, recruiter | Calendar-first scheduling and task planning | Calendar surface, recruiter/city filters, slot details, create/edit task modal | Desktop calendar, mobile day view, task modal create/edit, loading, filter states | High |
| `/app/messenger` | admin, recruiter | Work with candidate communication in one workspace | Inbox rail, chat pane, template tray, composer, delivery health, archive action | Desktop 2-pane, empty thread, template tray, delivery error, mobile inbox, mobile chat | High |
| `/app/detailization` | admin, recruiter | Attribute intro day outcomes and maintain reporting data | Summary cards, date filters, create entry flow, search candidate, inline row editing, export action | Summary view, create form expanded, editable row, validation error, empty, mobile compact view | Medium |
| `/app/copilot` | admin, recruiter | AI help plus knowledge base operations | AI chat, knowledge base list, document detail, create/upload controls | Chat default, sending, empty KB, doc detail, upload/create states, admin vs recruiter permission differences | Medium |
| `/app/profile` | admin, recruiter | Personal cabinet and settings | Avatar area, theme toggle, recruiter settings, password form, KPI snippets, planner rows | Admin variant, recruiter variant, avatar upload/delete, theme switch, password validation, loading | Medium |

## Candidate Workbench Surfaces

| Route | Audience | Main goal | Core blocks to design | Mandatory states / variants | Priority |
| --- | --- | --- | --- | --- | --- |
| `/app/candidates` | admin, recruiter | Find, segment, and move candidates through the funnel | Filters, kanban columns, candidate cards, bulk selection helpers, drag/drop affordances, alternate list behaviors on mobile | Kanban default, drag blocked state, risk banner on card, empty column, no results, mobile list | High |
| `/app/candidates/new` | admin, recruiter | Create candidate and optionally schedule immediately | Candidate form, city/recruiter selection, immediate scheduling section, validation, success/warning notice | Default create, schedule-now enabled, warning after create, success redirect, mobile form | Medium |
| `/app/candidates/$candidateId` | admin, recruiter | Full candidate workspace and action center | Header hero, pipeline, action center, lifecycle/scheduling/risk/context sections, tests, AI sections, chat drawer, insights drawer, reject/schedule/report modals, scripts | Desktop full page, mobile tabs, chat open, insights open, interview script open, reject modal, schedule slot modal, intro day modal, loading/error | Highest |

### Candidate Detail Subsurface Checklist

These frames should be separate in Figma because the page is too dense for a single frame:

- Header + candidate identity
- Pipeline strip
- Action center
- Lifecycle section
- Scheduling section
- Risks & blockers section
- Context & history section
- Tests section
- AI insights drawer
- Chat drawer
- Schedule slot modal
- Schedule intro day modal
- Reject modal
- Report preview / test preview states

## Admin Setup / CRUD Surfaces

| Route | Audience | Main goal | Core blocks to design | Mandatory states / variants | Priority |
| --- | --- | --- | --- | --- | --- |
| `/app/recruiters` | admin | Manage recruiter roster | Recruiter cards, load stats, city chips, activation toggle, empty state | Default list, empty, toggle pending, delete confirm | Medium |
| `/app/recruiters/new` | admin | Create recruiter and bind cities | Hero summary, sections, city selector tiles, timezone helper, credentials success state | Blank create, partially filled draft, validation, credentials created state, mobile form | Medium |
| `/app/recruiters/$recruiterId/edit` | admin | Edit recruiter profile and access | Hero summary, load indicators, city assignment, password reset state, delete action | Loaded profile, dirty state, password reset sheet/state, delete confirm | Medium |
| `/app/cities` | admin | Manage cities and local configuration | City cards/list items, recruiter assignment chips, plan chips, templates stage coverage | Default list, empty, archive toggle, row error, mobile list | Medium |
| `/app/cities/new` | admin | Create city with TZ and hiring plan | Basic params, hiring plan, recruiters picker, experts, validation, TZ live preview | Blank create, TZ valid/invalid, recruiter selection, quick preset use, mobile form | Medium |
| `/app/cities/$cityId/edit` | admin | Full city setup incl. contacts, templates, HH, reminders | Multi-section settings page, reminders section, template coverage, HH vacancy link state, contact info | Default loaded page, reminders custom/global, collapsed sections, HH data present/absent | Medium |
| `/app/templates` | admin | Browse stage-based message templates | Catalog/list, coverage matrix, city filter, stage filter, search, matrix mode | Catalog mode, matrix mode, missing required coverage, mobile card mode | Medium |
| `/app/templates/new` | admin | Create a message template | Template type picker, city selector, token chips, live preview | Blank, preselected key/city, preview populated, validation errors | Medium |
| `/app/templates/$templateId/edit` | admin | Edit and preview a template | Editor, context variables, preview, delete action | Loaded, server preview, delete confirm, validation error | Medium |
| `/app/questions` | admin | Browse and clone test questions | Grouped list/table, status chips, clone action | Desktop table, mobile cards, empty, clone in progress | Medium |
| `/app/questions/new` | admin | Create test question | Basic form, test selector, payload JSON editor | Blank, invalid JSON, active/inactive, save pending | Medium |
| `/app/questions/$questionId/edit` | admin | Edit test question | Edit form, payload editor, active toggle | Loaded, invalid JSON, save pending | Medium |
| `/app/test-builder` | admin | Linear test sequencing workspace | Test tabs, reorder list, detail editor, save order action | No selection, question selected, drag/reorder dirty state, save success | Medium |
| `/app/test-builder/graph` | admin | Graph-based branching editor | Flow canvas, nodes, edges, detail inspector, graph preview | Empty graph, populated graph, node selected, edge selected, preview mode | Medium |
| `/app/message-templates` | admin, recruiter | Broader message template operations and history | Filter bar, template list, editor, history, preview, permissions-aware controls | Admin full access, recruiter restricted access, no selection, preview error | Medium |
| `/app/system` | admin | Platform operations center | Tabbed control center, health cards, tests content, reminders policy, delivery outbox, HH integration, logs | Each tab as separate frame set, polling/loading, delivery error, HH connected/disconnected | High |
| `/app/simulator` | feature-flag/dev | Dev and demo surface | Lightweight debug/demo controls | Keep minimal unless product scope expands | Low |

## Candidate Portal

| Route | Audience | Main goal | Core blocks to design | Mandatory states / variants | Priority |
| --- | --- | --- | --- | --- | --- |
| `/candidate/start` | candidate | Public landing / token recovery / channel chooser | Entry hero, candidate explainer, OTP or token bridge states, channel chooser, trust signals | Public no-token entry, token entry, chooser, loading, invalid token, session restore | High |
| `/candidate/start/$token` | candidate | Token-based personalized entry | Same surface family as start, but with personalized entry resolution | Personalized loading, entry success, blocked/expired token | High |
| `/candidate/journey` | candidate | Self-service cabinet for progress, screening, scheduling, inbox, company info | Current step hero, workflow/timeline, messenger/channel cards, schedule states, history, alerts | Waiting, action needed, scheduled, blocked repeat screening, channel switch, mobile webview-safe variant | Highest |

## Telegram Mini App

| Route | Audience | Main goal | Core blocks to design | Mandatory states / variants | Priority |
| --- | --- | --- | --- | --- | --- |
| `/tg-app` | recruiter in Telegram | Quick KPI view | 3 KPI cards, quick CTA to queue, Telegram-native shell | Loading, initData missing, normal dashboard | Medium |
| `/tg-app/incoming` | recruiter in Telegram | Quick triage list | Compact candidate cards, queue count, zero state | Loading, empty, error, compact list | Medium |
| `/tg-app/candidates/$candidateId` | recruiter in Telegram | Lightweight candidate detail and status transition | Summary card, status card, transition buttons, inline status message | Loading, error/not found, status update pending, success | Medium |

## Dormant / Not Mounted In Current Route Tree

These files exist in the repo but are not part of the mounted route tree and should not be treated as active first-wave Figma pages:

- [frontend/app/src/app/routes/app/vacancies.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/vacancies.tsx)
- [frontend/app/src/app/routes/app/reminder-ops.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/reminder-ops.tsx)

## Recommended Figma File Structure

Create one Figma file with these pages:

1. `00 Cover`
   - file intro
   - scope note
   - route family map

2. `01 Foundations`
   - colors and semantic tokens
   - typography
   - spacing
   - radius/elevation
   - motion notes
   - dark/light examples

3. `02 Shell`
   - desktop shell
   - mobile shell
   - login
   - shell empty/loading/error patterns

4. `03 Recruiter Ops`
   - dashboard
   - incoming
   - slots
   - calendar
   - messenger
   - detailization
   - copilot
   - profile

5. `04 Candidate Workspace`
   - candidates list/kanban
   - candidate create
   - candidate detail
   - candidate detail overlays

6. `05 Admin Setup`
   - recruiters
   - cities
   - templates
   - questions
   - test builder
   - message templates
   - system
   - simulator

7. `06 Candidate Portal`
   - start
   - start with token
   - journey
   - mobile webview variants

8. `07 Telegram Mini App`
   - dashboard
   - incoming
   - candidate detail

9. `08 Components`
   - reusable cards
   - filters
   - tables
   - chips/badges
   - action blocks
   - modals/drawers
   - mobile tab bar

10. `09 Prototype Flows`
   - recruiter triage flow
   - candidate scheduling flow
   - candidate portal entry flow
   - message sending flow
   - system delivery triage flow

## Components That Must Be Abstracted In Figma

These are worth turning into component sets before page drawing continues:

- App shell header
- Mobile header
- Mobile tab bar + More sheet
- Filter bar
- KPI metric card
- Recruiter action block
- Recruiter risk banner
- Candidate identity block
- Candidate state context block
- Kanban card
- Table row with inline actions
- CRUD form section shell
- Timezone helper / preview row
- Messenger thread item
- Messenger bubble set
- Drawer shell
- Modal shell
- Candidate portal hero card
- TG mini app KPI card

## Overlay And State Coverage Checklist

Every page family in Figma should include at least these states:

- loading
- empty
- API error
- success/confirmation
- validation error
- no-permission or unavailable, where applicable

High-risk operational pages should also include:

- bulk action state
- blocked action state
- stale/conflict/risk surfaced state
- mobile condensed state

This especially applies to:

- `/app/incoming`
- `/app/candidates`
- `/app/candidates/$candidateId`
- `/app/slots`
- `/app/messenger`
- `/app/system`
- `/candidate/journey`

## Recommended Design Priority Waves

### Wave 1

Build these first because they define the main user-facing product quality:

- app shell
- login
- dashboard
- incoming
- candidates
- candidate detail
- messenger
- slots
- candidate portal journey

### Wave 2

- calendar
- profile
- candidate new
- detailization
- system
- candidate portal start
- tg mini app

### Wave 3

- recruiters
- cities
- templates
- message templates
- questions
- test builder

### Wave 4

- simulator
- `/app`
- dormant pages if they return to scope

## Recommended Prototype Flows

Prototype these flows explicitly in Figma:

1. Login -> Dashboard -> Incoming -> Candidate Detail -> Schedule modal
2. Candidates Kanban -> Candidate Detail -> Chat drawer -> Messenger
3. Candidate portal start -> channel chooser -> journey -> schedule confirmation
4. System delivery tab -> log drill-down -> retry flow
5. Recruiters/Cities CRUD -> edit -> save success

## Practical Next Step For Figma

Because direct Figma creation is blocked in this runtime, the next clean step is:

1. create an empty Figma file named `Attila Recruiting - Product Design`
2. reproduce the page structure from `Recommended Figma File Structure`
3. start with Wave 1 frames only
4. move shared patterns into `08 Components` before drawing Wave 2+

Once Figma MCP is available, this report can be converted into:

- page scaffolding in Figma
- frame naming convention
- linked prototype flows
- component inventory for iterative design edits

## Assumptions

- Scope was limited to routes actually mounted in [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx).
- Dormant route files were intentionally excluded from first-wave design implementation.
- Existing Liquid Glass v2 and current CRM density are preserved as baseline rather than replaced.
- Figma creation was not executed because the current session has no working Figma MCP exposure.
