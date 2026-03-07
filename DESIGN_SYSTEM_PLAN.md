# DESIGN_SYSTEM_PLAN

## Goal
- Build a design system that can be implemented inside the current CSS and React architecture.
- The system must support premium glass depth, dense operational workflows and real mobile behavior without a rewrite.

## Source Of Truth
- Tokens: `frontend/app/src/theme/tokens.css`
- Shared components/styles: `frontend/app/src/theme/components.css`
- Page-level contracts: `frontend/app/src/theme/pages.css`
- Surface primitives: `frontend/app/src/theme/material.css`
- Mobile behavior: `frontend/app/src/theme/mobile.css`

## Design Principles
1. Clarity over decoration.
2. Premium depth without noise.
3. Data density with breathing space.
4. Mobile-first operability.
5. Predictable action hierarchy.
6. Reusable primitives before route-local styling.
7. Motion with purpose.
8. Quiet operational screens, expressive overview screens.
9. Accessible by default.
10. Progressive hardening over one-shot rewrite.

## Surface Model
- `base`
  - page background and low-emphasis content foundation
- `raised`
  - primary cards, section containers, structured panels
- `floating`
  - sticky bars, temporary utilities, hover-elevated controls
- `overlay`
  - sheets, dialogs, toasts, modal surfaces

## Token Recommendations
### Colors
- Preserve current semantic token approach.
- Split surfaces into:
  - shell background
  - content background
  - quiet operational glass
  - ambient overview glass
  - overlay glass
- Tighten text contrast on dense screens.

### Existing Token Groups To Keep
- Spacing: `--space-xs` to `--space-3xl`
- Radius: `--radius-xs` to `--radius-full`
- Blur: `--blur-sm`, `--blur`, `--blur-lg`, `--blur-xl`
- Motion: `--motion-fast`, `--motion-base`, `--motion-slow`
- Easing: `--ease-standard`, `--ease-emphasized`
- Z-index: `--z-base`, `--z-sticky`, `--z-overlay`, `--z-toast`, `--z-mobile-nav`, `--z-mobile-header`, `--z-sheet`
- Liquid Glass v2 aliases: `--ui-space-*`, `--ui-radius-*`, `--ui-blur-*`, `--ui-surface-*`, `--ui-shadow-*`, `--ui-border-*`

### New Token Direction
- Surface opacity by use case, not only by theme.
- Quiet-shell and ambient-shell modifiers on top of existing tokens.
- Explicit content-width and section-gap tokens for page rhythm.
- Stronger state tokens for success, warning, error and neutral emphasis on glass backgrounds.

## Typography Scale
- Hero title
- Page title
- Section title
- Card title
- Label
- Body
- Dense body
- Micro/meta
- Rule: hierarchy must be readable even with muted color palette.

## Spacing Rules
- Page vertical rhythm should use one scale, not page-local numbers.
- Section padding is narrower on dense operational screens than on overview/landing screens.
- Mobile spacing uses fewer simultaneous layers and more obvious grouping.

## Border And Shadow Rules
- Borders carry most of the grouping load on operational pages.
- Shadows are soft and shallow on data-heavy screens.
- Strongest shadow reserved for overlays and floating utilities.

## Z-Index Rules
- One standardized ladder:
  - base content
  - sticky page utility
  - shell navigation
  - floating action
  - overlay backdrop
  - dialog or sheet
  - toast
- Avoid route-local escalation outside this ladder.

## Motion Tokens
- Required durations:
  - 120ms
  - 180ms
  - 280ms
- Required easings:
  - standard
  - emphasized
- Reduced motion must map to shorter opacity changes and no decorative transforms.

## Component Families
### 1. App Shell
- Variants: quiet, ambient.
- States: normal, loading route, overlay-open.
- Responsive: desktop top nav, mobile header/tab shell.
- Accessibility: landmarks, skip target, overlay isolation.
- Motion: route transition, nav state.

### 2. Page Container
- Variants: ops, admin, overview, utility.
- States: normal, loading, empty, error.
- Responsive: width and gap adapt by breakpoint.
- Motion: subtle reveal only on route load.

### 3. Hero/Header
- Variants: overview, ops, detail, form.
- States: with KPIs, with actions, with filters.
- Responsive: stack actions under title on tablet/mobile.
- Accessibility: heading hierarchy, action grouping.

### 4. Section Container
- Variants: neutral, interactive, data, form, side panel.
- States: default, selected, warning, error.
- Responsive: single-column by default; optional split on desktop.
- Motion: low-key elevation on interaction.

### 5. Toolbar
- Variants: compact, between, sticky, filter-heavy.
- States: default, wrap, collapsed.
- Responsive: wraps on tablet, stacks or sheet-trigger on mobile.

### 6. Buttons
- Variants: primary, secondary, ghost, danger, success, FAB.
- States: hover, active, focus, disabled, loading.
- Responsive: minimum 44px hit target on mobile.

### 7. Icon Buttons
- Variants: neutral, subtle, danger, disclosure.
- States: hover, active, focus, disabled.
- Responsive: circle or rounded-square with hit-area padding.

### 8. Inputs
- Variants: text, number, date, time, textarea.
- States: default, filled, focus, invalid, disabled.
- Responsive: full-width on mobile forms.

### 9. Selects
- Variants: inline, full, dense.
- States: default, focus, invalid, disabled.
- Responsive: avoid tiny inline selects on mobile.

### 10. Search Field
- Variants: page search, list search, chat search.
- States: default, typing, loading, clearable.
- Responsive: full-width on mobile toolbars.

### 11. Filter Bar
- Variants: inline, advanced, sheet-backed.
- States: collapsed, expanded, dirty, resettable.
- Responsive: advanced filters move to accordion or sheet.

### 12. Chips
- Variants: status, filter, suggestion, removable.
- States: active, inactive, disabled.
- Responsive: avoid chip walls on narrow viewports.

### 13. Badges
- Variants: neutral, success, warning, error, info.
- States: static, pulsing-notification only when justified.

### 14. Tabs
- Variants: top tabs, mobile tabs, inline section tabs.
- States: active, inactive, disabled.
- Responsive: segmented controls on mobile when count is small.

### 15. Segmented Controls
- Variants: view switch, density switch, mode switch.
- States: selected, hover, disabled.

### 16. Cards
- Variants: stat, entity, action, summary, mobile row card.
- States: default, hover, selected, pending.
- Responsive: mobile cards replace tables selectively.

### 17. Tables
- Variants: entity table, audit table, dense admin table.
- States: loading, empty, selected row, sortable, bulk-select.
- Responsive: convert to cards or stacked list when scanning is primary need.

### 18. Mobile Card Lists
- Variants: slot card, candidate card, template card, question card.
- States: default, selected, expanded, loading.
- Responsive: source of truth for mobile list behavior.

### 19. Kanban Columns
- Variants: board column, mobile horizontal column.
- States: drag-over, empty, loading.
- Responsive: mobile should reduce drag friction and cognitive load.

### 20. Calendar Surfaces
- Variants: day, range, task modal.
- States: selected slot, busy, disabled range.
- Responsive: reduced mode complexity on mobile.

### 21. Form Sections
- Variants: standard, dense, with side summary, destructive.
- States: dirty, valid, invalid, saving.
- Responsive: stacked sections with sticky save on mobile where needed.

### 22. Drawers And Sheets
- Variants: filter sheet, mobile more sheet, contextual drawer.
- States: closed, opening, open, closing.
- Accessibility: dialog semantics only when open, focus trap, return focus.

### 23. Modals
- Variants: confirm, form, preview, destructive, picker.
- States: idle, busy, success, error.
- Responsive: sheet substitute on mobile for many cases.

### 24. Dropdowns And Menus
- Variants: action menu, select menu, context menu.
- States: closed, open, keyboard focus.

### 25. Toasts
- Variants: success, warning, error, info.
- States: visible, dismissing.
- Responsive: avoid collision with mobile tab bar and sheet.

### 26. Empty States
- Variants: first-use, filtered-empty, no-results, no-data.
- States: passive, action-oriented.

### 27. Skeletons
- Variants: hero, list, table, card, form.
- States: initial loading, refresh loading.

### 28. Status Blocks
- Variants: health, KPI, incident, warning, success summary.
- States: neutral, warning, error, success.

### 29. Pagination
- Variants: compact, full, mobile stepper.
- States: disabled, active page, loading.

### 30. Chat Components
- Variants: thread row, message bubble, composer, task card.
- States: unread, own, failed, pending, action-required.

### 31. AI Panels
- Variants: summary, recommendation, draft, coach card.
- States: loading, empty, stale, refreshed.

### 32. Preview Panels
- Variants: slot preview, template preview, report preview, graph preview.
- States: loading, empty, invalid input.

## Shared Rules For All Components
- Spacing rules come from tokens only.
- Interactive states include hover, active, focus-visible, disabled and pending.
- Desktop/tablet/mobile behavior must be specified before implementation.
- Motion is optional unless it explains transition or feedback.
- Accessibility contract includes semantic roles, readable contrast and keyboard operation where interactive.

## Responsive Rules
- Desktop:
  - higher data density
  - split layouts allowed when both columns are useful
- Tablet:
  - compress first, do not miniaturize
  - side utilities often become lower sections or drawers
- Mobile:
  - prefer stacked sections
  - one primary action zone per viewport
  - tables transform when scanning and action are more important than raw column density

## Implementation Guidance For Codex App
- Introduce or extend primitives in theme files before editing route files.
- Use `pages.css` and `components.css` as the destination for shared contracts.
- Use `material.css` and tokens for surface/elevation rules.
- Minimize new rules in `global.css`; prefer moving or splitting old ones over adding more monolith.
- Remove inline style usage in highest-debt routes first:
  - `frontend/app/src/app/routes/app/city-edit.tsx`
  - `frontend/app/src/app/routes/app/system.tsx`
  - `frontend/app/src/app/routes/app/test-builder-graph.tsx`
