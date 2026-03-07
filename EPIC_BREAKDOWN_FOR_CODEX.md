# EPIC_BREAKDOWN_FOR_CODEX

## Purpose
- This file breaks the redesign into epics that Codex App can execute and parallelize safely.
- Every epic maps to a wave from `CODEX_EXECUTION_PLAN.md`.
- Task IDs in `TASK_GRAPH_FOR_CODEX.md` must reference these epic IDs exactly.

## Dependency Graph
- `W1.*` depends on `W0`.
- `W2.*` depends on `W1.*`.
- `W3.*` depends on `W1.*` and the relevant `W2.*` shell contracts.
- `W4.*` depends on `W1.*`, `W2.*`, `W3.*`.
- `W5.*` depends on `W2.*`, `W3.*`, `W4.*`.
- `W6.*` depends on `W1.*`, `W2.*`, `W3.*`; some admin cleanup can run in parallel after `W3.*`, but high-risk routes should wait until `W5.*` mobile patterns settle.
- `W7.*` depends on all previous waves.

## Parallelization Opportunities
| Phase | Can Run In Parallel | Notes |
|---|---|---|
| after W1 | `W2.2`, `W2.3`, `W3.1`, `W3.2` | if `W1.1` and `W1.2` are stable |
| after W2 | `W3.3`, `W3.4`, `W3.5`, `W3.6` | shared primitives can progress independently |
| after W3 | `W4.1`, `W4.2`, `W4.6` | lower coupling than slots/candidates/detail |
| after W4 | `W5.1`, `W5.2`, `W5.3`, `W6.4` | mobile hardening and lower-risk admin work |
| after W5 | `W6.1`, `W6.2`, `W6.3`, `W6.5` | big admin cleanup |
| final | `W7.1`, `W7.2` | `W7.3` waits on both |

## W1 Foundation Epics
### W1.1 Token Audit And Canonical Mapping
- Goal:
  - align existing tokens with the redesign contract
- Value:
  - prevents route-local design drift
- Included:
  - colors, spacing, radii, blur, motion, z-index
- Target files:
  - `frontend/app/src/theme/tokens.css`
- Dependencies:
  - W0
- Notes:
  - add `--z-fab`, document quiet/ambient usage hooks
- Risks:
  - token churn can create noisy diffs
- Acceptance:
  - tokens cover all required surface, motion and layering needs
- QA:
  - verify no existing theme vars break

### W1.2 Surface Ladder Alignment
- Goal:
  - formalize `base / raised / floating / overlay`
- Value:
  - gives shared visual hierarchy before page migrations
- Included:
  - `ui-surface` and glass layer rules
- Target files:
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/pages.css`
- Dependencies:
  - W1.1
- Notes:
  - avoid route-local shadow and border overrides
- Risks:
  - too much contrast loss or too much opacity
- Acceptance:
  - surface ladder is explicit and reusable
- QA:
  - spot-check quiet and ambient routes

### W1.3 Page Shell Primitive Extraction
- Goal:
  - stabilize `.app-page`, hero, section and toolbar wrappers
- Value:
  - lets multiple screens migrate with low rediscovery
- Included:
  - page shell, hero, section, section head, toolbar spacing
- Target files:
  - `frontend/app/src/theme/pages.css`
- Dependencies:
  - W1.1, W1.2
- Notes:
  - keep existing class names where feasible
- Risks:
  - accidental breakage of route-specific layouts
- Acceptance:
  - page shell primitives exist and are documented
- QA:
  - verify dashboard, incoming, messenger still render acceptably

### W1.4 Admin Form Grammar Extraction
- Goal:
  - formalize long-form admin layout and save/footer behavior
- Value:
  - unlocks safe cleanup of `city-edit`, `recruiter-edit`, `template-edit`
- Included:
  - `.ui-form-shell`, `.ui-form-grid`, `.ui-field`, footer pattern
- Target files:
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
- Dependencies:
  - W1.3
- Notes:
  - grammar must support sticky mobile save
- Risks:
  - overfitting to one form screen
- Acceptance:
  - canonical admin form grammar is implementable
- QA:
  - spot-check city/recruiter/template form fit

### W1.5 State Blocks And Skeleton Pattern
- Goal:
  - standardize loading, empty, error and success blocks
- Value:
  - removes page-by-page improvisation
- Included:
  - `ui-state`, skeleton placeholders, empty-state contract
- Target files:
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/global.css`
- Dependencies:
  - W1.3
- Notes:
  - prioritize compatibility with ApiErrorBanner and route-level queries
- Risks:
  - duplicated legacy empty-state classes remain alive
- Acceptance:
  - shared state blocks are available for Wave 4 screens
- QA:
  - validate loading/error states on dashboard and messenger

## W2 Shell Epics
### W2.1 More Sheet Semantics Fix
- Goal:
  - fix mobile More sheet closed-state semantics and rendering behavior
- Value:
  - removes a P0 blocker for mobile quality
- Included:
  - mobile More sheet, backdrop, focus return
- Target files:
  - `frontend/app/src/app/routes/__root.tsx`
  - `frontend/app/src/theme/mobile.css`
- Dependencies:
  - W1.1, W1.2
- Notes:
  - keep product term "More sheet", CSS class may remain `.mobile-sheet`
- Risks:
  - focus or overlay regressions across mobile shell
- Acceptance:
  - closed sheet is not dialog-active or interactive
- QA:
  - mobile smoke on 390/375/320

### W2.2 Quiet vs Ambient Route Mapping
- Goal:
  - apply route-specific atmosphere rules
- Value:
  - removes visual noise from operational screens
- Included:
  - ambient only on `/app`, `/app/login`, `/app/dashboard`
- Target files:
  - `frontend/app/src/app/routes/__root.tsx`
  - `frontend/app/src/theme/pages.css`
- Dependencies:
  - W1.2
- Notes:
  - quiet mode should become the default
- Risks:
  - overview screens feel too plain if mapping is wrong
- Acceptance:
  - route mapping matches `DESIGN_DECISIONS_LOG.md`
- QA:
  - screenshot smoke for ambient and quiet routes

### W2.3 Shell Layering And Safe-Area Cleanup
- Goal:
  - normalize shell z-index and spacing contracts
- Value:
  - prevents sheet/header/tab collisions before screen redesign
- Included:
  - tab bar, header, FAB, toast, sheet, main padding
- Target files:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/mobile.css`
- Dependencies:
  - W1.1, W2.1
- Notes:
  - add `--z-fab`
- Risks:
  - page-local sticky bars may still collide later
- Acceptance:
  - canonical shell ladder is implemented
- QA:
  - test overlay, tab and FAB interactions

### W2.4 Shell Landmarks And Focus Management
- Goal:
  - improve shell-level accessibility structure
- Value:
  - reduces repeated a11y bugs on every route
- Included:
  - landmarks, focus return, inert usage
- Target files:
  - `frontend/app/src/app/routes/__root.tsx`
- Dependencies:
  - W2.1
- Notes:
  - keep login/auth fallback behavior intact
- Risks:
  - regressions in unauthenticated or mobile-only flows
- Acceptance:
  - shell passes landmark and focus sanity checks
- QA:
  - keyboard-only pass through nav and overlays

## W3 Shared Component Epics
### W3.1 Hero/Header Primitive
- Goal:
  - define one shared hero/header pattern
- Value:
  - reduces 6+ existing header variants
- Included:
  - app-page hero, title/subtitle, action cluster
- Target files:
  - `frontend/app/src/theme/pages.css`
  - selected route files during migration
- Dependencies:
  - W1.3, W2.2
- Notes:
  - should absorb dashboard, incoming, messenger header needs
- Risks:
  - forcing identical layouts where domain needs differ
- Acceptance:
  - hero primitive supports overview, ops and detail modes
- QA:
  - compare dashboard vs incoming vs candidate detail headers

### W3.2 Section Container Primitive
- Goal:
  - standardize section container and section-head behavior
- Value:
  - creates predictable rhythm across screens
- Included:
  - section padding, head, body spacing, interactive modifiers
- Target files:
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/material.css`
- Dependencies:
  - W1.2, W1.3
- Notes:
  - support dense and long-form modes
- Risks:
  - overly generic sections can hide hierarchy
- Acceptance:
  - section contract works for ops and admin screens
- QA:
  - spot-check sections on dashboard, system, city-edit

### W3.3 Toolbar And Filter Bar System
- Goal:
  - unify toolbar, search and filter behavior
- Value:
  - removes route-specific filter rhythm
- Included:
  - toolbar, search field, filter bar, advanced filters
- Target files:
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/global.css`
  - `frontend/app/src/theme/mobile.css`
- Dependencies:
  - W1.3, W1.5, W2.3
- Notes:
  - must support inline and sheet-backed modes
- Risks:
  - filter logic is route-specific; only layout and semantics should be unified
- Acceptance:
  - shared toolbar and filter patterns exist
- QA:
  - verify incoming, slots, candidates filter interaction

### W3.4 Button And Field Alignment
- Goal:
  - align buttons, inputs and selects under one shared treatment
- Value:
  - reduces ad hoc control styling and tap-target drift
- Included:
  - button variants, inputs, selects, focus states
- Target files:
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/tokens.css`
- Dependencies:
  - W1.1, W1.4
- Notes:
  - maintain 44px mobile hit targets
- Risks:
  - subtle regressions in form density
- Acceptance:
  - controls share a consistent appearance and focus contract
- QA:
  - sample forms across recruiter and admin routes

### W3.5 Overlay Primitive Alignment
- Goal:
  - standardize modal, drawer and sheet behavior
- Value:
  - consistent close, backdrop and mobile behavior
- Included:
  - modals, sheets, drawers, destructive confirm flows
- Target files:
  - `frontend/app/src/theme/mobile.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/motion.css`
- Dependencies:
  - W2.1, W2.4
- Notes:
  - mobile-first preference for sheets in filter flows
- Risks:
  - overlay behavior differs between route implementations today
- Acceptance:
  - primitives support modal/sheet variants consistently
- QA:
  - open/close and keyboard tests

### W3.6 Table And Card Parity Primitive
- Goal:
  - define how desktop tables map to mobile cards
- Value:
  - prevents divergent list logic across screens
- Included:
  - table wrapper, mobile card list, shared row metadata order
- Target files:
  - `frontend/app/src/theme/global.css`
  - `frontend/app/src/theme/mobile.css`
  - route migrations
- Dependencies:
  - W1.5, W3.2, W3.3
- Notes:
  - parity definition is crucial before W4/W5
- Risks:
  - action mismatch between cards and tables
- Acceptance:
  - card parity rules are explicit and reusable
- QA:
  - compare slots, candidates and templates list behavior

## W4 Recruiter Screen Epics
### W4.1 Dashboard Screen Migration
- Goal:
  - move dashboard to shared hero/section grammar
- Value:
  - aligns overview surface with new foundation
- Included:
  - dashboard summary, leaderboard, KPI and queue blocks
- Target files:
  - `frontend/app/src/app/routes/app/dashboard.tsx`
- Dependencies:
  - W3.1, W3.2, W3.3
- Notes:
  - queue should visually outrank decorative metrics
- Risks:
  - over-designing overview area
- Acceptance:
  - clear metric and queue hierarchy
- QA:
  - desktop/tablet/mobile screenshot pass

### W4.2 Incoming Screen Migration
- Goal:
  - make incoming the first exemplar ops screen
- Value:
  - high traffic, moderate complexity, strong ROI
- Included:
  - queue cards, advanced filters, schedule modal
- Target files:
  - `frontend/app/src/app/routes/app/incoming.tsx`
- Dependencies:
  - W3.1, W3.3, W3.5, W3.6
- Notes:
  - preferred first route after shell/foundation
- Risks:
  - modal and filter interactions regress on mobile
- Acceptance:
  - queue and scheduling remain fast and clear
- QA:
  - mobile and desktop smoke

### W4.3 Slots Screen Migration
- Goal:
  - unify dense filters, bulk actions and card/table parity
- Value:
  - high-value scheduling surface
- Included:
  - summary chips, filters, table, mobile cards, bulk bar
- Target files:
  - `frontend/app/src/app/routes/app/slots.tsx`
- Dependencies:
  - W3.3, W3.5, W3.6
- Notes:
  - preserve all bulk action affordances
- Risks:
  - selection and bulk state can drift between modes
- Acceptance:
  - no action loss between desktop and mobile
- QA:
  - bulk action smoke and overflow checks

### W4.4 Candidates Screen Migration
- Goal:
  - stabilize list/kanban/calendar hierarchy and list/mobile behavior
- Value:
  - central pipeline work surface
- Included:
  - view switch, list view, kanban, calendar, AI recommendations
- Target files:
  - `frontend/app/src/app/routes/app/candidates.tsx`
- Dependencies:
  - W3.3, W3.6
- Notes:
  - calendar and kanban should not dominate mobile
- Risks:
  - multi-view state regressions
- Acceptance:
  - view hierarchy is explicit and mobile list is robust
- QA:
  - switch-view smoke and mobile pass

### W4.5 Candidate Detail Restructure
- Goal:
  - reorganize the densest screen around the canonical structure
- Value:
  - biggest UX payoff if done after primitives stabilize
- Included:
  - hero, pipeline strip, slots, tests, AI, messaging blocks
- Target files:
  - `frontend/app/src/app/routes/app/candidate-detail.tsx`
- Dependencies:
  - W3.1, W3.2, W3.5, W4.4
- Notes:
  - do not start this epic before shared primitives and candidates list settle
- Risks:
  - very high regression and diff size
- Acceptance:
  - section order and action visibility are materially improved
- QA:
  - route smoke plus mobile a11y spot check

### W4.6 Messenger Screen Migration
- Goal:
  - align split-pane and mobile conversation flow to shared grammar
- Value:
  - critical cross-team coordination surface
- Included:
  - thread list, active chat, composer, task modals
- Target files:
  - `frontend/app/src/app/routes/app/messenger.tsx`
- Dependencies:
  - W3.1, W3.2, W3.5
- Notes:
  - maintain continuity with root chat toast behavior
- Risks:
  - shell and messenger interactions overlap
- Acceptance:
  - desktop and mobile chat hierarchy is clearer
- QA:
  - send flow, modal flow, mobile thread/chat pass

### W4.7 Calendar Screen Migration
- Goal:
  - improve calendar controls and mobile readability
- Value:
  - scheduling quality affects recruiter trust
- Included:
  - filters, FullCalendar wrapper, task modal behavior
- Target files:
  - `frontend/app/src/app/routes/app/calendar.tsx`
  - `frontend/app/src/app/components/Calendar/ScheduleCalendar.tsx`
  - `frontend/app/src/app/components/Calendar/calendar.css`
- Dependencies:
  - W3.3, W3.5, W3.6
- Notes:
  - mobile mode reduction is required, not optional
- Risks:
  - FullCalendar customization can be brittle
- Acceptance:
  - mobile and tablet task flow is cleaner
- QA:
  - create/edit/delete task smoke

## W5 Mobile Hardening Epics
### W5.1 Mobile Filter Sheet Pattern
- Goal:
  - convert dense filter experiences into sheet-backed patterns where needed
- Value:
  - reduces toolbar overload on narrow devices
- Included:
  - incoming, slots, candidates, system top filters if needed
- Target files:
  - `frontend/app/src/theme/mobile.css`
  - affected route files
- Dependencies:
  - W3.3, W3.5, W4.2-W4.4
- Notes:
  - preserve clear reset/apply feedback
- Risks:
  - filter discoverability drops
- Acceptance:
  - mobile filter interaction is simpler with no blocked actions
- QA:
  - mobile filter smoke on core screens

### W5.2 Card Parity Hardening
- Goal:
  - ensure mobile cards expose same critical data and actions as desktop tables
- Value:
  - avoids mobile feature loss
- Included:
  - slots, candidates, template list, question list, admin lists as needed
- Target files:
  - affected route files and `mobile.css`
- Dependencies:
  - W3.6, W4.3, W4.4
- Notes:
  - parity matrix should be explicit per screen
- Risks:
  - silent omissions in mobile card variants
- Acceptance:
  - parity checklist passes on first-wave screens
- QA:
  - compare desktop and mobile action availability

### W5.3 Safe-Area, Keyboard And Sticky Pass
- Goal:
  - normalize sticky bars, keyboard safety and safe-area padding
- Value:
  - removes common mobile friction points
- Included:
  - tab bar, sticky save, filter sheets, bottom actions
- Target files:
  - `frontend/app/src/theme/mobile.css`
  - affected route files
- Dependencies:
  - W2.3, W3.5, W4.*
- Notes:
  - long forms and chat composer are priority checks
- Risks:
  - browser UI height changes can expose hidden controls
- Acceptance:
  - no persistent overlap or unreachable CTA
- QA:
  - mobile keyboard and short-height manual pass

### W5.4 Mobile Accessibility Hardening
- Goal:
  - close the remaining mobile a11y gaps
- Value:
  - aligns mobile layer with WCAG 2.1 AA target
- Included:
  - focus, landmarks, scrollable interactive regions, hit targets
- Target files:
  - shell and affected route files
- Dependencies:
  - W2.4, W4.5, W5.3
- Notes:
  - candidate detail and overlays are key targets
- Risks:
  - regressions hidden in dynamic or modal content
- Acceptance:
  - mobile a11y spot checks pass on core routes
- QA:
  - keyboard, SR sanity and focus-visible checks

## W6 Admin Cleanup Epics
### W6.1 City-Edit Inline Extraction
- Goal:
  - remove the biggest inline-style hotspot first
- Value:
  - highest debt reduction per file
- Included:
  - city hero, summary stats, grouped sections, helper blocks
- Target files:
  - `frontend/app/src/app/routes/app/city-edit.tsx`
  - theme files as needed
- Dependencies:
  - W1.4, W3.2, W5.3
- Notes:
  - split extraction by spacing/layout/color/sizing
- Risks:
  - very large visual diff
- Acceptance:
  - inline-style count is materially reduced and form grammar is applied
- QA:
  - admin form manual pass on desktop/mobile

### W6.2 System Inline Extraction
- Goal:
  - standardize the densest admin ops page
- Value:
  - improves health/logs/template policy readability
- Included:
  - tabs, toolbars, wide tables, reminder policy panels
- Target files:
  - `frontend/app/src/app/routes/app/system.tsx`
  - theme files as needed
- Dependencies:
  - W3.3, W3.6, W5.1
- Notes:
  - system tables may need responsive wrappers or card fallbacks
- Risks:
  - accidental loss of admin controls
- Acceptance:
  - visual grammar matches admin contract and mobile/tablet usability improves
- QA:
  - logs/jobs/policy manual pass

### W6.3 Test Builder Workspace Cleanup
- Goal:
  - align `test-builder` and `test-builder-graph` with admin workspace rules
- Value:
  - removes desktop-only drift in internal tools
- Included:
  - list builder, graph builder, preview/editor panels
- Target files:
  - `frontend/app/src/app/routes/app/test-builder.tsx`
  - `frontend/app/src/app/routes/app/test-builder-graph.tsx`
- Dependencies:
  - W1.4, W3.2, W3.5
- Notes:
  - graph remains desktop-first, but mobile fallback must be explicit
- Risks:
  - complex editor behavior can overshadow visual cleanup
- Acceptance:
  - workspace panels use shared section/form grammar where feasible
- QA:
  - desktop-first manual pass plus narrow-tablet spot check

### W6.4 Admin Libraries And Template Flows
- Goal:
  - standardize list/create/edit flows for templates, questions and message templates
- Value:
  - reusable library/edit patterns reduce future drift
- Included:
  - template list/new/edit, questions list/new/edit, message-templates
- Target files:
  - relevant route files in `frontend/app/src/app/routes/app/`
- Dependencies:
  - W1.4, W3.3, W3.6
- Notes:
  - list/table/card parity and editor rhythm are key
- Risks:
  - matrix/list complexity in templates
- Acceptance:
  - list/create/edit family feels coherent
- QA:
  - create/edit consistency checks

### W6.5 Remaining Admin Screen Cleanup
- Goal:
  - align profile, cities, recruiters, copilot, simulator and detailization with the same system
- Value:
  - closes the remaining fragmentation in the mounted route set
- Included:
  - remaining admin and utility screens
- Target files:
  - respective route files
- Dependencies:
  - W1-W5, partial W6.1-W6.4
- Notes:
  - lower-risk screens can be cleaned in smaller commits
- Risks:
  - temptation to skip because they are not the worst offenders
- Acceptance:
  - all mounted admin routes sit on the shared grammar
- QA:
  - quick regression sweep for each route family

## W7 Polish Epics
### W7.1 Motion Polish
- Goal:
  - apply motion rules after structural work stabilizes
- Value:
  - avoids polishing moving targets
- Included:
  - route transitions, overlays, microinteractions, reduced-motion review
- Target files:
  - `frontend/app/src/theme/motion.css`
  - supporting theme files
- Dependencies:
  - W1-W6
- Notes:
  - no new decorative motion on quiet routes
- Risks:
  - motion polish becomes performance regression
- Acceptance:
  - motion matches approved hierarchy and durations
- QA:
  - reduced-motion and interaction spot checks

### W7.2 Automated Smoke And A11y Coverage
- Goal:
  - expand safety net for shell and key routes
- Value:
  - lowers regression risk for ongoing redesign
- Included:
  - shell smoke, recruiter route smoke, a11y checks
- Target files:
  - existing test files and new smoke specs if needed
- Dependencies:
  - W2-W6
- Notes:
  - prioritize shell, incoming, slots, candidates, candidate detail, messenger, city-edit, system
- Risks:
  - brittle tests if selectors are not stabilized
- Acceptance:
  - smoke suite covers high-risk flows
- QA:
  - CI/local runs stable

### W7.3 Full Responsive QA And Burn-Down
- Goal:
  - close remaining P0/P1 responsive and interaction regressions
- Value:
  - final production hardening step
- Included:
  - viewport matrix, zoom, safe-area, keyboard, overlay, visual QA
- Target files:
  - no single file; driven by defects found in W1-W7
- Dependencies:
  - W7.1, W7.2
- Notes:
  - use `DESIGN_QA_CHECKLIST.md` as the manual checklist source
- Risks:
  - hidden regressions in low-traffic admin routes
- Acceptance:
  - first-wave screens have no unresolved P0/P1 issues
- QA:
  - full manual subset and smoke rerun
