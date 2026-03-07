# CODEX_EXECUTION_PLAN

## Purpose
- This is the master execution reference for Codex App.
- Read this after `DESIGN_DECISIONS_LOG.md`.
- It converts the planning package into an ordered implementation program grounded in real files, line counts and debt hotspots.

## Required Reading Order
1. `DESIGN_DECISIONS_LOG.md`
2. `CODEX_EXECUTION_PLAN.md`
3. Planning artifacts:
   - `DESIGN_REDESIGN_PRD.md`
   - `DESIGN_AUDIT_REPORT.md`
   - `UI_PRINCIPLES_AND_LAYOUT_PATTERNS.md`
   - `RESPONSIVE_AND_MOBILE_AUDIT.md`
   - `SCREEN_ARCHITECTURE_MAP.md`
   - `DESIGN_SYSTEM_PLAN.md`
   - `MOTION_AND_INTERACTION_GUIDELINES.md`
   - `IMPLEMENTATION_ROADMAP_FOR_CODEX.md`
   - `ACCEPTANCE_CRITERIA.md`
   - `DESIGN_QA_CHECKLIST.md`
   - `EXECUTIVE_SUMMARY.md`
4. Parallel execution specs:
   - `EPIC_BREAKDOWN_FOR_CODEX.md`
   - `COMPONENT_IMPLEMENTATION_SPECS.md`
   - `SCREEN_IMPLEMENTATION_SPECS.md`
5. `TASK_GRAPH_FOR_CODEX.md`
6. `CODEX_FIRST_WAVE_RECOMMENDATION.md`
7. `ROLLOUT_AND_REGRESSION_STRATEGY.md`

## Scope And Constraints
- Scope: 31 mounted SPA routes.
- No backend or API changes.
- No route path changes.
- No new CSS/JS framework.
- No rewrite of TanStack Router or Query setup.
- No first-wave redesign of dormant routes:
  - `frontend/app/src/app/routes/app/vacancies.tsx`
  - `frontend/app/src/app/routes/app/reminder-ops.tsx`

## System Snapshot
### Theme File Inventory
| File | Path | Lines | Role |
|---|---|---:|---|
| tokens | `frontend/app/src/theme/tokens.css` | 299 | token source of truth, breakpoints, z-index, motion |
| global | `frontend/app/src/theme/global.css` | 8717 | monolith, base styles, legacy and page rules |
| components | `frontend/app/src/theme/components.css` | 423 | shared `ui-*` primitives |
| pages | `frontend/app/src/theme/pages.css` | 640 | page shell, hero, section, quiet/ambient |
| mobile | `frontend/app/src/theme/mobile.css` | 863 | mobile header, tab bar, more sheet, cards |
| motion | `frontend/app/src/theme/motion.css` | 165 | transition primitives, reduced-motion |
| material | `frontend/app/src/theme/material.css` | 76 | surface ladder |

### Shell Snapshot
| File | Lines | Notes |
|---|---:|---|
| `frontend/app/src/app/routes/__root.tsx` | 1286 | nav, mobile sheet, ambient background, chat polling, shell state |

### High-Risk Route Files
| File | Lines | Inline styles | Reason |
|---|---:|---:|---|
| `frontend/app/src/app/routes/app/candidate-detail.tsx` | 2937 | 1 | densest workflow screen |
| `frontend/app/src/app/routes/app/slots.tsx` | 1239 | 0 | filtering, bulk actions, card/table parity |
| `frontend/app/src/app/routes/app/city-edit.tsx` | 1108 | 97 | highest mounted debt |
| `frontend/app/src/app/routes/app/test-builder-graph.tsx` | 1147 | 29 | desktop-heavy editor |
| `frontend/app/src/app/routes/app/dashboard.tsx` | 1044 | 0 | recruiter/admin overview hybrid |
| `frontend/app/src/app/routes/app/calendar.tsx` | 962 | 1 | FullCalendar and modal-heavy |
| `frontend/app/src/app/routes/app/messenger.tsx` | 858 | 0 | split-pane plus shell dependency |
| `frontend/app/src/app/routes/app/incoming.tsx` | 836 | 0 | work queue and modal scheduling |
| `frontend/app/src/app/routes/app/candidates.tsx` | 831 | 0 | multi-view list/kanban/calendar |
| `frontend/app/src/app/routes/app/system.tsx` | 797 | 42 | admin ops tables and policies |

### Shared Component Inventory
| File | Lines | Notes |
|---|---:|---|
| `frontend/app/src/app/components/ApiErrorBanner.tsx` | 51 | existing error surface |
| `frontend/app/src/app/components/ErrorBoundary.tsx` | 70 | shell-level fallback pattern |
| `frontend/app/src/app/components/RoleGuard.tsx` | 68 | auth/role boundary |
| `frontend/app/src/app/components/QuestionPayloadEditor.tsx` | 534 | admin JSON/payload editor |
| `frontend/app/src/app/components/Calendar/ScheduleCalendar.tsx` | 433 | shared scheduling component |
| `frontend/app/src/app/components/Calendar/calendar.css` | 356 | FullCalendar-specific styling |

### Mounted Route Debt Snapshot
- Mounted route inline-style total: 320 across 19 files.
- Highest-debt mounted routes:
  - `city-edit.tsx`: 97
  - `system.tsx`: 42
  - `test-builder-graph.tsx`: 29
  - `detailization.tsx`: 27
  - `message-templates.tsx`: 25
  - `template-list.tsx`: 24
  - `test-builder.tsx`: 23
  - `template-edit.tsx`: 16

## Route Inventory By Implementation Wave
### Wave 2-3 Shell / Shared Pattern Consumers
- all mounted routes indirectly, because shell and primitives are global

### Wave 4 Recruiter-First
- `/app/dashboard`
- `/app/incoming`
- `/app/slots`
- `/app/candidates`
- `/app/candidates/$candidateId`
- `/app/messenger`
- `/app/calendar`

### Wave 6 Admin / Long-Form
- `/app/profile`
- `/app/recruiters`
- `/app/recruiters/new`
- `/app/recruiters/$recruiterId/edit`
- `/app/cities`
- `/app/cities/new`
- `/app/cities/$cityId/edit`
- `/app/templates`
- `/app/templates/new`
- `/app/templates/$templateId/edit`
- `/app/questions`
- `/app/questions/new`
- `/app/questions/$questionId/edit`
- `/app/message-templates`
- `/app/system`
- `/app/copilot`
- `/app/simulator`
- `/app/detailization`
- `/app/test-builder`
- `/app/test-builder/graph`
- `/app/slots/create`
- `/app/candidates/new`

## Wave Program
### W0. Package Approval
- Purpose:
  - freeze terminology, scope, priorities and handoff docs
- Target files:
  - all planning and execution docs
- Tasks:
  - confirm route inventory, component inventory, inline-debt counts
  - resolve terminology via `DESIGN_DECISIONS_LOG.md`
- Dependencies:
  - none
- Risks:
  - implementation starts from ambiguous terms
- Acceptance criteria:
  - decisions log and execution plan are approved
  - epics/tasks/specs can be generated with no unresolved terms
- Validation:
  - document cross-reference checks only

### W1. Foundation
- Purpose:
  - stabilize tokens, surface ladder and page contract before screen work
- Target files:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/components.css`
- Tasks:
  - add or normalize surface tokens and `--z-fab`
  - formalize quiet vs ambient shell usage
  - formalize page shell, hero, section, toolbar and form grammar
  - formalize state blocks, buttons, inputs and selects contracts
- Dependencies:
  - W0
- Risks:
  - foundation drifts from existing route usage
- Acceptance criteria:
  - shared primitives exist for hero, section, toolbar, form, state
  - token ladder covers real z-index and surface use cases
- Validation:
  - `npm run lint`
  - `npm run test`
  - `npm run build:verify`

### W2. Shell
- Purpose:
  - fix shell semantics and global route atmosphere
- Target files:
  - `frontend/app/src/app/routes/__root.tsx`
  - `frontend/app/src/theme/mobile.css`
  - `frontend/app/src/theme/pages.css`
- Tasks:
  - More sheet semantics and closed-state behavior
  - ambient opt-in route mapping
  - shell z-index and safe-area normalization
  - focus return, inert, landmarks
- Dependencies:
  - W1
- Risks:
  - global regressions across all routes
- Acceptance criteria:
  - closed More sheet is absent from active accessibility tree
  - ambient background only shows on mapped routes
  - shell remains stable on 1440/1280/1024/768/390/375/320
- Validation:
  - lint/test/build
  - mobile smoke after W2

### W3. Shared Components
- Purpose:
  - create reusable primitives before page rewrites
- Target files:
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/mobile.css`
  - selected shared component files if extraction is needed
- Tasks:
  - hero/header primitive
  - section container primitive
  - toolbar and filter bar unification
  - state blocks, skeletons, empty states
  - buttons, inputs, selects, badges, tabs
  - sheet/modal/drawer contracts
- Dependencies:
  - W1, W2
- Risks:
  - premature extraction that does not match route diversity
- Acceptance criteria:
  - first-wave screens can be migrated without new inline layout styling
  - primitives have mobile and a11y contracts
- Validation:
  - lint/test/build
  - component- or page-level spot tests if added

### W4. Recruiter Screens
- Purpose:
  - redesign highest-traffic workflow screens first
- Target files:
  - `frontend/app/src/app/routes/app/dashboard.tsx`
  - `frontend/app/src/app/routes/app/incoming.tsx`
  - `frontend/app/src/app/routes/app/slots.tsx`
  - `frontend/app/src/app/routes/app/candidates.tsx`
  - `frontend/app/src/app/routes/app/candidate-detail.tsx`
  - `frontend/app/src/app/routes/app/messenger.tsx`
  - `frontend/app/src/app/routes/app/calendar.tsx`
- Tasks:
  - migrate headers and sections to shared primitives
  - normalize toolbar/filter rhythm
  - clarify candidate detail hierarchy
  - reduce decorative noise on operational routes
  - preserve or improve mobile card/drill-down behavior
- Dependencies:
  - W1, W2, W3
- Risks:
  - screen-local solutions reappear under delivery pressure
- Acceptance criteria:
  - recruiter-first screens share one visual language
  - no blocked action at 320px+
  - no new overflow, overlay or shell collisions
- Validation:
  - lint/test/build
  - mobile smoke after W4

### W5. Mobile Hardening
- Purpose:
  - make mobile behavior a product layer, not a shrink layer
- Target files:
  - `frontend/app/src/theme/mobile.css`
  - affected route files from W4 and top admin offenders
- Tasks:
  - filter sheets
  - card parity
  - keyboard-safe forms
  - safe-area review
  - sticky/floating control review
  - mobile a11y pass
- Dependencies:
  - W2, W3, W4
- Risks:
  - parity gaps between table and card modes
- Acceptance criteria:
  - critical recruiter flows pass mobile smoke and manual checks
  - keyboard, safe-area and sticky elements behave correctly
- Validation:
  - lint/test/build
  - mobile smoke after W5

### W6. Admin Screens
- Purpose:
  - reduce inline-style debt and bring long-form/admin screens under one grammar
- Target files:
  - `frontend/app/src/app/routes/app/city-edit.tsx`
  - `frontend/app/src/app/routes/app/system.tsx`
  - `frontend/app/src/app/routes/app/test-builder.tsx`
  - `frontend/app/src/app/routes/app/test-builder-graph.tsx`
  - `frontend/app/src/app/routes/app/template-list.tsx`
  - `frontend/app/src/app/routes/app/template-edit.tsx`
  - `frontend/app/src/app/routes/app/message-templates.tsx`
  - `frontend/app/src/app/routes/app/detailization.tsx`
  - remaining admin route files
- Tasks:
  - extract inline layout and spacing
  - apply admin form grammar
  - unify table wrappers and state blocks
  - quiet visual treatment for configuration-heavy screens
- Dependencies:
  - W1-W5
- Risks:
  - large diff size and visual regressions
- Acceptance criteria:
  - highest-debt screens materially reduce inline styling
  - long-form pages share one section grammar
- Validation:
  - lint/test/build
  - route smoke where practical

### W7. Polish
- Purpose:
  - close motion, accessibility, responsive and regression gaps
- Target files:
  - theme files
  - shell tests
  - route smoke tests
- Tasks:
  - motion polish
  - reduced-motion review
  - landmark/focus review
  - responsive QA
  - smoke suite expansion
- Dependencies:
  - W1-W6
- Risks:
  - polish turns into new scope instead of hardening
- Acceptance criteria:
  - no open P0/P1 regressions for first-wave screens
  - validation and QA matrix pass
- Validation:
  - lint/test/build
  - full QA after W7

## Validation Protocol
### After Every Wave
- `cd frontend/app && npm run lint`
- `cd frontend/app && npm run test`
- `cd frontend/app && npm run build:verify`

### Additional Gate Checks
- After W2:
  - mobile shell smoke
  - More sheet semantics
  - quiet vs ambient route smoke
- After W4:
  - recruiter-first mobile smoke
  - candidate detail and messenger smoke
- After W5:
  - mobile-specific regression sweep
- After W7:
  - full manual QA subset from `DESIGN_QA_CHECKLIST.md`

## Known Risks To Respect
- Do not start by splitting `global.css`; extract targeted contracts first.
- Do not start with `candidate-detail.tsx`; it should consume stabilized primitives.
- Do not add new inline styles to move faster.
- Do not refactor shell and candidate detail in the same commit.
- Do not merge W(N+1) while W(N) still has open P0 issues.

## Suggested Commit Sequence
1. `docs: add codex execution handoff`
2. `refactor: add shared page and surface primitives`
3. `fix: mobile more sheet semantics and shell layering`
4. `refactor: unify toolbar and state primitives`
5. `feat: redesign incoming screen`
6. `feat: redesign slots and candidates screens`
7. `feat: restructure candidate detail and messenger`
8. `refactor: extract admin form grammar and inline debt`
9. `test: expand responsive and shell smoke coverage`
