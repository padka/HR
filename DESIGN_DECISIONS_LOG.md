# DESIGN_DECISIONS_LOG

## Purpose
- This file resolves terminology, scope and implementation ambiguities across the 11 planning artifacts.
- Codex App should read this file first before opening any execution spec.
- Status: canonical implementation decision log for redesign wave planning.

## Global Constraints
- Scope: 31 mounted SPA routes from `frontend/app/src/app/main.tsx:97-316`.
- Excluded from first implementation pass:
  - `frontend/app/src/app/routes/app/vacancies.tsx`
  - `frontend/app/src/app/routes/app/reminder-ops.tsx`
- No backend API changes.
- No route path changes.
- No new framework, no Tailwind, no Framer Motion.
- Implementation remains inside React 18 + TanStack Router/Query + custom CSS tokens.

## Resolved Terminology
| # | Inconsistency | Canonical Resolution |
|---|---|---|
| 1 | "Mobile sheet" vs "More sheet" | "More sheet" is the navigation product concept; `mobile-sheet` is the existing CSS class and DOM surface. |
| 2 | "Page container" vs "page shell" | "Page shell" means the outermost per-route wrapper. Existing CSS class remains `.app-page`. |
| 3 | Admin form grammar undefined | Canonical grammar: `.ui-form-shell` as root form grid, titled `.app-page__section` groups, `.ui-field` blocks, consistent save/cancel footer, sticky save footer on mobile where forms exceed one viewport. |
| 4 | Inline-style debt unquantified | Verified count: 356 `style={{...}}` across 21 route files in `frontend/app/src/app/routes/app`; 320 across 19 mounted route files. |
| 5 | Z-index mismatch | Canonical ladder comes from `tokens.css`, plus explicit `--z-fab: 980` and no route-local escalation outside the ladder. |
| 6 | Candidate detail restructure vague | Canonical target: hero -> pipeline strip -> collapsible section stack. Mobile uses accordion/tabs only for dense secondary sections, not as the primary shell. |
| 7 | No wireframes | Text-based structural specs are the canonical source. No Figma or pixel mock is required for execution. |
| 8 | No WCAG target | WCAG 2.1 Level AA is the accessibility target for focus, contrast, semantics and motion behavior. |
| 9 | CSS naming convention unclear | BEM-lite. Shared primitives use `ui-` prefix. Page-specific styles use page-scoped prefixes like `dashboard-`, `incoming-`, `cd-`, `messenger-`. |
| 10 | Inline-style migration strategy unclear | Extract-and-replace screen by screen, highest-debt first, categorized into spacing, layout, color, sizing and one-off semantic styling. |

## Verified Inline-Style Inventory
### Full Route Inventory
- Verified from `frontend/app/src/app/routes/app/*.tsx`.
- Total: 356 inline-style occurrences across 21 route files.
- Mounted-route total: 320 inline-style occurrences across 19 mounted route files.

### Highest-Debt Files
| File | Route Status | Lines | Inline styles | Notes |
|---|---|---:|---:|---|
| `frontend/app/src/app/routes/app/city-edit.tsx` | mounted | 1108 | 97 | primary Wave 6 extraction target |
| `frontend/app/src/app/routes/app/system.tsx` | mounted | 797 | 42 | primary Wave 6 extraction target |
| `frontend/app/src/app/routes/app/test-builder-graph.tsx` | mounted | 1147 | 29 | desktop-heavy graph/editor |
| `frontend/app/src/app/routes/app/detailization.tsx` | mounted | 529 | 27 | analytics/reporting debt |
| `frontend/app/src/app/routes/app/reminder-ops.tsx` | dormant | n/a | 26 | excluded from first pass |
| `frontend/app/src/app/routes/app/message-templates.tsx` | mounted | 322 | 25 | compact admin editor debt |
| `frontend/app/src/app/routes/app/template-list.tsx` | mounted | 530 | 24 | matrix/list duality |
| `frontend/app/src/app/routes/app/test-builder.tsx` | mounted | 446 | 23 | list/editor workspace |
| `frontend/app/src/app/routes/app/template-edit.tsx` | mounted | 326 | 16 | form/editor cleanup |

### Migration Categories
- Spacing:
  - margin, padding, gap, row/column gap
- Layout:
  - display, flex/grid, widths, min/max sizing, alignments
- Color:
  - hardcoded text or status colors
- Sizing:
  - font-size, border-radius, min-width, height
- One-off semantics:
  - progress widths, per-row computed visuals, dynamic width fills

## Canonical Severity Levels
- `P0`
  - breaks navigation, blocked primary action, major a11y defect, data-hidden-by-layout, broken overlay semantics
- `P1`
  - major workflow slowdown, strong visual inconsistency on core screen, mobile action friction, high regression risk
- `P2`
  - meaningful but non-blocking usability inconsistency, maintainability hotspot, secondary responsive issue
- `P3`
  - polish, cleanup, low-risk visual refinement, copy or spacing micro-fixes

## Quiet vs Ambient Route Mapping
### Ambient Routes
- `/app`
- `/app/login`
- `/app/dashboard`

### Quiet Routes
- `/app/profile`
- `/app/incoming`
- `/app/slots`
- `/app/slots/create`
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
- `/app/test-builder`
- `/app/test-builder/graph`
- `/app/message-templates`
- `/app/messenger`
- `/app/calendar`
- `/app/system`
- `/app/copilot`
- `/app/simulator`
- `/app/detailization`
- `/app/candidates`
- `/app/candidates/new`
- `/app/candidates/$candidateId`

## Canonical Z-Index Ladder
| Layer | Value | Source / Decision |
|---|---:|---|
| base content | `--z-base = 1` | `frontend/app/src/theme/tokens.css` |
| sticky page utility | `--z-sticky = 20` | `frontend/app/src/theme/tokens.css` |
| overlay baseline | `--z-overlay = 60` | `frontend/app/src/theme/tokens.css` |
| toast | `--z-toast = 80` | `frontend/app/src/theme/tokens.css` |
| FAB | `--z-fab = 980` | new canonical alias for existing `.ui-btn--fab` value in `mobile.css` |
| mobile nav | `--z-mobile-nav = 1000` | `frontend/app/src/theme/tokens.css` |
| mobile header | `--z-mobile-header = 1001` | `frontend/app/src/theme/tokens.css` |
| sheet | `--z-sheet = 1010` | `frontend/app/src/theme/tokens.css` |

## Admin Form Grammar
- Root:
  - `.ui-form-shell`
- Section:
  - `.app-page__section`
  - `.app-page__section-head`
- Fields:
  - `.ui-field`
  - `.ui-field__label`
  - `.ui-field__hint`
  - `.ui-field__error`
- Layout:
  - `.ui-form-grid`
  - `.ui-form-grid--md`
  - `.ui-form-grid--lg`
- Footer:
  - save/cancel block inside last `.app-page__section`
  - mobile variant may become sticky only when form length exceeds one viewport and save action is primary
- Rule:
  - summary cards and side diagnostics are secondary; field groups dominate.

## Candidate Detail Canonical Structure
1. Hero with identity, primary CTA cluster and top-level status chips.
2. Pipeline strip with next-step actions.
3. Collapsible section stack:
   - profile and source context
   - slots/interviews
   - tests/reports
   - AI insights
   - messaging/history
4. Mobile:
   - one route
   - top summary stays visible
   - section stack uses accordion or segmented controls only for dense secondary navigation

## CSS Naming Convention
- Shared primitive:
  - `ui-*`
- Page shell:
  - `app-*`
- Page-local:
  - `dashboard-*`
  - `incoming-*`
  - `slots-*`
  - `cd-*`
  - `messenger-*`
- Rule:
  - no generic new class names inside route files when a shared `ui-` primitive can express the same concern.

## Commit Conventions
- Branch prefix: `codex/`.
- Commit types:
  - `docs:`
  - `fix:`
  - `refactor:`
  - `feat:`
  - `test:`
- Commit rule:
  - one logical unit per commit
  - no mixed unrelated screens in one commit
  - shell/foundation and page work stay separate

## Validation Conventions
- After each implementation wave:
  - `npm run lint`
  - `npm run test`
  - `npm run build:verify`
- Additional mandatory checkpoints:
  - mobile smoke after W2, W4, W5
  - full QA after W7

## Non-Decisions
- No pixel-perfect wireframes are required.
- No mandate to split `global.css` in the first wave; it is a debt hotspot, not the first deliverable.
- No requirement to redesign dormant routes in the first pass.
