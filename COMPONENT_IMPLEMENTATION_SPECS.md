# COMPONENT_IMPLEMENTATION_SPECS

## Purpose
- This file turns the 32 component families from `DESIGN_SYSTEM_PLAN.md` into implementation-ready specs.
- Status legend:
  - `EXISTING` = already present in code and should be stabilized
  - `EXTRACT` = exists in fragmented form and should be pulled into shared primitives
  - `NEW` = not meaningfully present as a reusable primitive yet

## Shared Rules
- Naming:
  - shared primitives use `ui-`
  - page shell uses `app-`
  - page-local classes keep page prefix
- Token dependencies come from `frontend/app/src/theme/tokens.css`.
- Surface ladder comes from `frontend/app/src/theme/material.css`.
- Motion contract comes from `frontend/app/src/theme/motion.css`.
- Accessibility target: WCAG 2.1 AA.

## Canonical Admin Form Grammar
- Root: `.ui-form-shell`
- Section: `.app-page__section`
- Section head: `.app-page__section-head`
- Grid: `.ui-form-grid`, `.ui-form-grid--md`, `.ui-form-grid--lg`
- Field: `.ui-field`, `.ui-field__label`, `.ui-field__hint`, `.ui-field__error`
- Footer: shared action footer, sticky on mobile only when needed
- Migration targets:
  - `city-edit.tsx`
  - `recruiter-edit.tsx`
  - `recruiter-new.tsx`
  - `template-edit.tsx`
  - `message-templates.tsx`

## Priority Order
- First wave components:
  - App Shell
  - Page Container
  - Hero/Header
  - Section Container
  - Toolbar
  - Buttons
  - Inputs
  - Selects
  - Cards
  - Tables
  - Filter Bar
  - Filter Sheet/Drawer
  - Modals/Sheets/Drawers
  - Badges
  - Tabs
  - Empty States
  - Skeletons

## 1. App Shell
- Status: `EXISTING`
- Code refs: `frontend/app/src/app/routes/__root.tsx`, `frontend/app/src/theme/pages.css:56-226`, `frontend/app/src/theme/mobile.css:109-291`
- Target CSS: `pages.css`, `mobile.css`
- Class hierarchy: `.app-shell`, `.app-shell--quiet`, `.app-shell--ambient`, `.app-main`, `.app-header`, `.mobile-header`, `.mobile-tab-bar`, `.mobile-sheet`
- HTML:
  ```html
  <div class="app-shell app-shell--quiet"><header class="app-header"></header><main class="app-main"></main></div>
  ```
- Variants/states: quiet, ambient, overlay-open, unauthenticated fallback
- Responsive: desktop nav shell, mobile header/tab shell, More sheet only when open
- Tokens: spacing, `--header-height`, safe-area, z-index ladder
- Motion: route transition only, no ambient motion on quiet routes
- A11y: landmarks, focus return, closed overlays absent from tree
- Wave: W1-W2
- Migration notes: stabilize shell before any recruiter screen work

## 2. Page Container
- Status: `EXISTING`
- Code refs: `frontend/app/src/theme/pages.css:79-111`
- Target CSS: `pages.css`
- Class hierarchy: `.app-page`, `.app-page--ops`
- HTML:
  ```html
  <div class="page app-page app-page--ops">...</div>
  ```
- Variants/states: ops, admin, overview, utility
- Responsive: width clamps per breakpoint, consistent vertical rhythm
- Tokens: page width, section gap, spacing scale
- Motion: route-entry only, subtle
- A11y: one `h1` per page, clear main content region
- Wave: W1, consumed in W4/W6
- Migration notes: do not invent new outer wrappers

## 3. Hero/Header
- Status: `EXTRACT`
- Existing refs: `dashboard.tsx:427-434`, `incoming.tsx:409-420`, `messenger.tsx:392-406`, `candidate-detail.tsx:1855-1883`
- Target CSS: `pages.css`
- Class hierarchy: `.app-page__hero`, `.ui-section-header`, `.ui-section-header__actions`
- HTML:
  ```html
  <header class="glass panel app-page__hero"><div class="ui-section-header">...</div></header>
  ```
- Variants/states: overview, ops, detail, form
- Responsive: actions wrap under title on tablet/mobile
- Tokens: title scale, section padding, surface ladder
- Motion: none beyond subtle route-entry
- A11y: title hierarchy, descriptive subtitle, action group labels where needed
- Wave: W3 then W4/W6
- Migration notes: replace bespoke page headers, not domain-specific inner content

## 4. Section Container
- Status: `EXTRACT`
- Existing refs: `pages.css:79-111`, `dashboard.tsx:480-509`
- Target CSS: `pages.css`, `material.css`
- Class hierarchy: `.app-page__section`, `.app-page__section-head`
- HTML:
  ```html
  <section class="glass panel app-page__section"><div class="app-page__section-head">...</div></section>
  ```
- Variants/states: default, dense, side, warning, interactive
- Responsive: single-column first, split only on desktop where meaningful
- Tokens: section padding, gap, border, surface variant
- Motion: hover lift only on interactive sections
- A11y: section heading required for major content blocks
- Wave: W3
- Migration notes: page-level padding should move here

## 5. Toolbar
- Status: `EXTRACT`
- Existing refs: `components.css:120-131`, route-specific toolbars in incoming/slots/candidates/system
- Target CSS: `components.css`
- Class hierarchy: `.ui-toolbar`, `.ui-toolbar--compact`, `.ui-toolbar--between`
- HTML:
  ```html
  <div class="ui-toolbar ui-toolbar--between">...</div>
  ```
- Variants/states: compact, between, wrap, filter-heavy
- Responsive: wraps on tablet, stacks or sheet-trigger support on mobile
- Tokens: gap scale, control heights
- Motion: control-only
- A11y: logical tab order, group labels when mixed controls
- Wave: W3
- Migration notes: preserve route-specific filter logic, change layout only

## 6. Buttons
- Status: `EXISTING`
- Existing refs: `components.css`, `global.css` button rules, `mobile.css` FAB rules
- Target CSS: `components.css`, `mobile.css`
- Class hierarchy: `.ui-btn`, modifiers `--primary`, `--ghost`, `--danger`, `--sm`, `--lg`, `--fab`
- HTML:
  ```html
  <button class="ui-btn ui-btn--primary">Save</button>
  ```
- Variants/states: primary, secondary, ghost, danger, loading, disabled
- Responsive: `44px+` touch target on mobile
- Tokens: motion, focus ring, accent/status colors
- Motion: 120ms active press, subtle hover
- A11y: focus-visible, disabled semantics, icon-only label when needed
- Wave: W3
- Migration notes: no new page-local button sizes

## 7. Icon Buttons
- Status: `EXISTING`
- Existing refs: shell nav and local route icon actions
- Target CSS: `components.css`
- Class hierarchy: `.ui-btn`, `.ui-btn--icon`, route-specific action wrappers
- HTML:
  ```html
  <button class="ui-btn ui-btn--ghost ui-btn--icon" aria-label="Close"></button>
  ```
- Variants/states: neutral, ghost, danger
- Responsive: enlarged hit area on mobile
- Tokens: radius, focus ring, min-height
- Motion: active press only
- A11y: `aria-label` mandatory for icon-only actions
- Wave: W3
- Migration notes: remove per-route icon button sizing

## 8. Inputs
- Status: `EXISTING`
- Existing refs: `components.css:85-118`
- Target CSS: `components.css`
- Class hierarchy: `.ui-field`, native input/textarea
- HTML:
  ```html
  <label class="ui-field"><span class="ui-field__label">Name</span><input /></label>
  ```
- Variants/states: text, number, date, time, textarea; default/focus/error/disabled
- Responsive: full-width on mobile
- Tokens: min-height, focus ring, text sizes
- Motion: none beyond focus/press
- A11y: label association, error/hint text
- Wave: W3
- Migration notes: use native controls, no custom replacement

## 9. Selects
- Status: `EXISTING`
- Target CSS: `components.css`
- Class hierarchy: native `select` in `.ui-field`
- HTML:
  ```html
  <label class="ui-field"><span class="ui-field__label">Status</span><select></select></label>
  ```
- Variants/states: full, dense, inline
- Responsive: avoid tiny inline selects on mobile
- Tokens: min-height, font size, border, radius
- Motion: focus only
- A11y: label plus error text when invalid
- Wave: W3
- Migration notes: local min-width hacks should be replaced with field/grid rules

## 10. Search Field
- Status: `EXTRACT`
- Existing refs: `incoming-toolbar__search`, `messenger` search, candidates search
- Target CSS: `components.css`
- Class hierarchy: `.ui-search`, `.ui-search__input`, `.ui-search__icon`, optional clear button
- HTML:
  ```html
  <label class="ui-search"><span class="sr-only">Search</span><input /></label>
  ```
- Variants/states: page search, list search, chat search
- Responsive: full-width or first-row control on mobile
- Tokens: control height, icon spacing
- Motion: caret and focus only
- A11y: accessible label and clear control
- Wave: W3
- Migration notes: stop inventing route-local search wrappers

## 11. Filter Bar
- Status: `EXTRACT`
- Existing refs: `global.css:8605-8616`, incoming/slots/candidates route filters
- Target CSS: `components.css`, `mobile.css`, selected cleanup in `global.css`
- Class hierarchy: `.ui-filter`, `.ui-filter__row`, `.ui-filter__advanced`, `.ui-filter__summary`
- HTML:
  ```html
  <div class="ui-filter"><div class="ui-filter__row">...</div></div>
  ```
- Variants/states: inline, advanced, dirty, collapsed, sheet-backed
- Responsive: advanced filters collapse or move to sheet on mobile
- Tokens: gap, spacing, motion duration
- Motion: clean reveal, not `max-height` jank
- A11y: expanded state, logical tab order
- Wave: W3 then W5
- Migration notes: keep logic local, unify structure and motion

## 12. Chips
- Status: `EXISTING`
- Target CSS: `global.css`, `components.css`
- Class hierarchy: `.chip`, `.status-pill`, `.cd-chip`
- HTML:
  ```html
  <span class="chip">Active</span>
  ```
- Variants/states: status, filter, info, removable
- Responsive: avoid multi-row chip walls on mobile
- Tokens: tone colors, radius, text size
- Motion: optional press only when interactive
- A11y: text, not color only
- Wave: W3/W4
- Migration notes: rationalize chip semantics by tone

## 13. Badges
- Status: `EXISTING`
- Target CSS: `components.css` or `global.css`
- Class hierarchy: `.ui-badge` or existing `status-pill` family if retained
- HTML:
  ```html
  <span class="ui-badge ui-badge--warning">Pending</span>
  ```
- Variants/states: neutral, success, warning, error, info
- Responsive: compact but readable
- Tokens: status color tokens
- Motion: none
- A11y: textual status required
- Wave: W3
- Migration notes: merge route-specific badge variants where possible

## 14. Tabs
- Status: `EXISTING`
- Existing refs: shell tabs, system tabs, candidate mobile tabs
- Target CSS: `components.css`, `mobile.css`
- Class hierarchy: `.ui-tabs`, `.ui-tabs__item`
- HTML:
  ```html
  <div class="ui-tabs" role="tablist">...</div>
  ```
- Variants/states: top tabs, inline tabs, mobile tabs
- Responsive: segmented control when small set; horizontal scroll if justified
- Tokens: spacing, radius, focus
- Motion: active indicator only
- A11y: proper tab roles when semantic tabs, otherwise buttons
- Wave: W3 then W6
- Migration notes: do not confuse product nav with content tabs

## 15. Segmented Controls
- Status: `EXTRACT`
- Existing refs: view switches in candidates and calendar
- Target CSS: `components.css`
- Class hierarchy: `.ui-segmented`, `.ui-segmented__item`
- HTML:
  ```html
  <div class="ui-segmented" role="group">...</div>
  ```
- Variants/states: view switch, mode switch
- Responsive: compact on mobile with max 2-3 options visible
- Tokens: control sizing, border, active background
- Motion: 120-180ms active shift
- A11y: group label, selected state
- Wave: W3/W4
- Migration notes: prefer segmented control over ad hoc button clusters for small mode sets

## 16. Cards
- Status: `EXTRACT`
- Existing refs: stat cards, incoming cards, recruiter cards, mobile cards
- Target CSS: `components.css`, `pages.css`, `mobile.css`
- Class hierarchy: `.ui-card`, page-specific card modifiers when needed
- HTML:
  ```html
  <article class="glass ui-card ui-surface--raised">...</article>
  ```
- Variants/states: stat, entity, action, summary, selected
- Responsive: cards replace tables selectively on mobile
- Tokens: section/card padding, radius, surface ladder
- Motion: subtle hover only when interactive
- A11y: use headings or strong title hierarchy
- Wave: W3/W4/W6
- Migration notes: card metadata order should follow parity rules

## 17. Tables
- Status: `EXISTING`
- Existing refs: `global.css:3634-3697`, `global.css:6895-6938`
- Target CSS: `global.css` initially, later shared extraction as feasible
- Class hierarchy: `.data-table-wrapper`, `.data-table`, modifiers like `__row--selected`
- HTML:
  ```html
  <div class="data-table-wrapper"><table class="data-table">...</table></div>
  ```
- Variants/states: entity table, dense admin table, selected row, sortable
- Responsive: wrapper on desktop/tablet, transform to cards when appropriate on mobile
- Tokens: border, background, row spacing
- Motion: none beyond selection highlight
- A11y: proper table semantics, row header when needed
- Wave: W3/W4/W6
- Migration notes: do not force every table into cards; use parity rules

## 18. Mobile Card Lists
- Status: `EXTRACT`
- Existing refs: `slots.tsx:904-1018`, `candidates.tsx:714-763`, `questions.tsx`
- Target CSS: `mobile.css`
- Class hierarchy: `.mobile-card-list`, plus domain card classes
- HTML:
  ```html
  <div class="mobile-card-list"><article class="entity-mobile-card">...</article></div>
  ```
- Variants/states: slot, candidate, template, question, admin summary
- Responsive: mobile-only or narrow-tablet optional
- Tokens: gap, card padding, action spacing
- Motion: none beyond tap feedback
- A11y: cards must expose the same critical actions as tables
- Wave: W3/W5
- Migration notes: parity matrix required before migration

## 19. Kanban Columns
- Status: `EXISTING`
- Existing refs: `candidates.tsx:640-696`, `mobile.css:743-746`
- Target CSS: `global.css`, `mobile.css`
- Class hierarchy: `.kanban`, `.kanban__column`, `.kanban__cards`, `.kanban__card`
- HTML:
  ```html
  <div class="kanban"><article class="kanban__column">...</article></div>
  ```
- Variants/states: drag-over, empty, mobile horizontal
- Responsive: mobile should deprioritize kanban relative to list
- Tokens: card gap, column width, surface
- Motion: drag-over emphasis only
- A11y: draggable state must still preserve clear actions
- Wave: W4/W5
- Migration notes: do not over-invest in mobile kanban drag polish before list parity is stable

## 20. Calendar Surfaces
- Status: `EXISTING`
- Existing refs: `calendar.tsx`, `ScheduleCalendar.tsx`, `calendar.css`
- Target CSS: `calendar.css`, `components.css`, `mobile.css`
- Class hierarchy: page-level calendar wrappers plus FullCalendar overrides
- HTML:
  ```html
  <section class="calendar-surface"><ScheduleCalendar /></section>
  ```
- Variants/states: day, range, task modal, selected slot
- Responsive: reduced complexity on mobile
- Tokens: section spacing, overlay surface
- Motion: overlays only
- A11y: visible labels and modal focus management
- Wave: W4/W5
- Migration notes: isolate wrapper chrome from FullCalendar internals

## 21. Form Sections
- Status: `EXTRACT`
- Target CSS: `components.css`, `pages.css`
- Class hierarchy: `.ui-form-shell`, `.app-page__section`, `.ui-form-grid`
- HTML:
  ```html
  <form class="ui-form-shell"><section class="app-page__section">...</section></form>
  ```
- Variants/states: standard, dense, aside-summary, destructive
- Responsive: stacked groups, sticky save optional on mobile
- Tokens: section gap, label sizes, footer spacing
- Motion: none except local submit feedback
- A11y: label/error association, heading hierarchy
- Wave: W1/W6
- Migration notes: primary admin grammar primitive

## 22. Drawers And Sheets
- Status: `EXTRACT`
- Existing refs: `.mobile-sheet`, modal-sheet patterns
- Target CSS: `mobile.css`, `material.css`, `motion.css`
- Class hierarchy: `.sheet`, `.sheet__backdrop`, `.sheet__body`, `.sheet__header`
- HTML:
  ```html
  <div class="sheet is-open"><button class="sheet__backdrop"></button><div class="sheet__body">...</div></div>
  ```
- Variants/states: mobile More sheet, filter sheet, contextual drawer
- Responsive: preferred mobile secondary pattern
- Tokens: overlay surface, z-index, motion
- Motion: 280ms open/close, simplified in reduced motion
- A11y: dialog semantics only when open, focus return
- Wave: W2/W3/W5
- Migration notes: More sheet is nav concept; generic sheet should absorb that behavior

## 23. Modals
- Status: `EXTRACT`
- Existing refs: incoming modal, calendar modals, messenger modals
- Target CSS: `material.css`, `motion.css`, selected route files
- Class hierarchy: `.modal`, `.modal__header`, `.modal__body`, `.modal__footer`
- HTML:
  ```html
  <div class="modal"><div class="modal__header"></div><div class="modal__body"></div></div>
  ```
- Variants/states: confirm, form, preview, destructive
- Responsive: sheet substitute on mobile where appropriate
- Tokens: overlay surface, radius, motion
- Motion: fade plus slide-up
- A11y: `role="dialog"`, `aria-modal`, focus trap/return
- Wave: W3/W4/W6
- Migration notes: move route-specific overlay chrome here, not business content

## 24. Dropdowns And Menus
- Status: `EXTRACT`
- Target CSS: `components.css`
- Class hierarchy: `.ui-menu`, `.ui-menu__item`, `.ui-dropdown`
- HTML:
  ```html
  <div class="ui-dropdown"><button></button><div class="ui-menu">...</div></div>
  ```
- Variants/states: action menu, context menu, compact select menu
- Responsive: convert to sheet when menu is dense on mobile
- Tokens: surface ladder, radius, spacing
- Motion: short fade/lift
- A11y: keyboard open/close, focus order
- Wave: W3/W6
- Migration notes: use only where simple button rows fail

## 25. Toasts
- Status: `EXISTING`
- Existing refs: `global.css:1207-1267`, shell chat toast
- Target CSS: `global.css`, `mobile.css`
- Class hierarchy: `.toast`, `.chat-toast`
- HTML:
  ```html
  <div class="toast" role="status">Saved</div>
  ```
- Variants/states: success, warning, error, info
- Responsive: must not collide with tab bar or sheet
- Tokens: z-index, tone colors, motion
- Motion: brief fade/lift
- A11y: polite live region where appropriate
- Wave: W2/W7
- Migration notes: unify placement logic before adding new toasts

## 26. Empty States
- Status: `EXTRACT`
- Existing refs: `components.css:135-173`, legacy empty-state blocks in `global.css`
- Target CSS: `components.css`
- Class hierarchy: `.ui-state`, `.ui-state--empty`
- HTML:
  ```html
  <div class="ui-state ui-state--empty"><h3 class="ui-state__title"></h3></div>
  ```
- Variants/states: first-use, filtered empty, no data
- Responsive: stack actions below text on mobile
- Tokens: muted text, section padding
- Motion: none
- A11y: helpful text, clear next step
- Wave: W1/W3/W4/W6
- Migration notes: replace duplicated empty-state variants gradually

## 27. Skeletons
- Status: `NEW`
- Target CSS: `components.css`
- Class hierarchy: `.ui-skeleton`, variant modifiers
- HTML:
  ```html
  <div class="ui-skeleton ui-skeleton--card"></div>
  ```
- Variants/states: hero, card, list row, table row, form block
- Responsive: shapes follow container width
- Tokens: surface contrast, shimmer opacity, radius
- Motion: disabled or simplified in reduced motion
- A11y: decorative only, hidden from SR
- Wave: W1/W3
- Migration notes: preferred for first-wave async screens

## 28. Status Blocks
- Status: `EXTRACT`
- Existing refs: KPI/status/info blocks across dashboard/system/profile
- Target CSS: `components.css`, `pages.css`
- Class hierarchy: `.ui-status-block`, tone modifiers
- HTML:
  ```html
  <div class="ui-status-block ui-status-block--warning">...</div>
  ```
- Variants/states: neutral, warning, error, success, KPI
- Responsive: stack and simplify text on mobile
- Tokens: tone colors, border, section gap
- Motion: none
- A11y: icon/text plus color
- Wave: W3/W4/W6
- Migration notes: use for system health and KPI summaries

## 29. Pagination
- Status: `EXISTING`
- Existing refs: incoming and candidates pagination
- Target CSS: `components.css` or `pages.css`
- Class hierarchy: `.pagination`, `.pagination__info`
- HTML:
  ```html
  <div class="pagination"><button></button><span class="pagination__info"></span></div>
  ```
- Variants/states: full, compact, mobile stepper
- Responsive: stack info under controls on narrow widths
- Tokens: gap, button size
- Motion: none
- A11y: descriptive labels, disabled state
- Wave: W4/W6
- Migration notes: preserve existing query/page behavior

## 30. Chat Components
- Status: `EXTRACT`
- Existing refs: `messenger.tsx`, root chat toast
- Target CSS: route-level messenger styles plus shared helpers in `components.css`
- Class hierarchy: `messenger-thread*`, `messenger-message*`, `messenger-composer*`
- HTML:
  ```html
  <section class="messenger-chat"><div class="messenger-messages"></div><div class="messenger-composer"></div></section>
  ```
- Variants/states: unread, own, pending, task-required
- Responsive: sequential mobile flow
- Tokens: spacing, status tones, surface ladder
- Motion: minimal incoming message/reply feedback
- A11y: readable status, focus order in composer and task dialogs
- Wave: W4/W5
- Migration notes: keep route-specific classes, extract only what is reusable

## 31. AI Panels
- Status: `EXTRACT`
- Existing refs: candidate detail AI sections, copilot
- Target CSS: page-level shared AI helpers in `components.css` or page-scoped styles
- Class hierarchy: `.cd-ai*`, future shared `ui-ai-panel*` if reuse is real
- HTML:
  ```html
  <section class="ui-ai-panel"><header></header><div class="ui-ai-panel__body"></div></section>
  ```
- Variants/states: summary, recommendation, draft, coach
- Responsive: progressive disclosure on mobile
- Tokens: surface contrast, state colors
- Motion: disclosure only
- A11y: headings and readable score/status text
- Wave: W4 then W6 for copilot
- Migration notes: do not prematurely over-abstract candidate-detail AI blocks

## 32. Preview Panels
- Status: `EXTRACT`
- Existing refs: slot preview, template preview, graph preview, report preview
- Target CSS: `components.css` plus page-specific supporting styles
- Class hierarchy: `.ui-preview`, `.ui-preview__header`, `.ui-preview__body`
- HTML:
  ```html
  <aside class="ui-preview"><div class="ui-preview__header"></div><div class="ui-preview__body"></div></aside>
  ```
- Variants/states: slot preview, template preview, report preview, graph preview
- Responsive: stack below form/editor on tablet/mobile
- Tokens: surface ladder, section spacing
- Motion: none beyond reveal when opened
- A11y: title, close action, clear loading/error states
- Wave: W4/W6
- Migration notes: align preview blocks but keep domain content local

## Migration Rules
- Extract to shared primitives only when at least two screens benefit immediately.
- Keep business-content classes page-scoped.
- Do not introduce new inline styles while migrating components.
- Prefer route adoption in this order:
  - incoming
  - slots
  - candidates
  - dashboard
  - messenger
  - candidate detail
  - calendar
  - admin forms and libraries
