# SCREEN_IMPLEMENTATION_SPECS

## Purpose
- This file maps all 31 mounted routes to concrete implementation expectations.
- Fields per screen:
  - file path
  - line count
  - inline-style count
  - wave assignment
  - shell mode
  - priority
  - current problems
  - target structure
  - component families used
  - desktop/tablet/mobile behavior
  - navigation behavior
  - edge states
  - motion rules
  - acceptance criteria
  - implementation notes
  - regression watchpoints

## Shell Mode Rules
- Ambient:
  - `/app`
  - `/app/login`
  - `/app/dashboard`
- Quiet:
  - all other mounted routes

## Utility And Access Routes
### /app
- File: `frontend/app/src/app/routes/app/index.tsx` | Lines: 11 | Inline styles: 2 | Wave: W6 | Shell: ambient | Priority: P3
- Problems: placeholder copy only, inline layout wrappers, no real page contract.
- Target structure: minimal route shell or redirect-like utility state.
- Components: App Shell, Page Container, Hero/Header, Empty State.
- Desktop/tablet/mobile: same low-density utility block.
- Navigation: entry point only, no local nav.
- States: static informational state.
- Motion: ambient route, no extra interaction motion.
- Acceptance: no extra layout debt, no misleading navigation, optional redirect-safe behavior.
- Notes: do not over-design; keep as low-scope utility.
- Watchpoints: avoid adding new bespoke placeholder styling.

### /app/login
- File: `frontend/app/src/app/routes/app/login.tsx` | Lines: 79 | Inline styles: 1 | Wave: W6 | Shell: ambient | Priority: P2
- Problems: standalone auth card, one inline centered-link style, limited shared auth grammar.
- Target structure: ambient auth page -> auth card -> form section -> action footer.
- Components: App Shell, Page Container, Hero/Header, Form Sections, Buttons, Inputs, Empty/Message block.
- Desktop: centered premium auth card.
- Tablet/mobile: same card with reduced chrome and strong field spacing.
- Navigation: no app nav inside auth card, clear escape to legacy login.
- States: validation error, auth error, loading.
- Motion: minimal, ambient shell only.
- Acceptance: clear authentication flow, readable errors, no operational shell leakage.
- Notes: keep auth isolated from ops shells.
- Watchpoints: login redirect and legacy link behavior.

## Wave 4 Recruiter-First Screens
### /app/dashboard
- File: `frontend/app/src/app/routes/app/dashboard.tsx` | Lines: 1044 | Inline styles: 0 | Wave: W4 | Shell: ambient | Priority: P1
- Problems: overview and work-queue hierarchy compete; current hero/summary blocks need stronger ordering.
- Target structure:
  1. hero with title, summary context and top actions
  2. KPI/summary strip
  3. leaderboard or team performance section
  4. incoming queue section
  5. weekly KPI or supporting analytics
- Components: Page Container, Hero/Header, Section Container, Status Blocks, Cards, Toolbar, Empty States, Skeletons.
- Desktop: clear priority for work queue and operational summaries.
- Tablet: compress to two-column layout with queue dominance preserved.
- Mobile: compact overview with queue first, secondary stats collapsed.
- Navigation: direct drill-down into incoming, slots, candidates.
- States: loading cards, empty metrics, API error, filtered states.
- Motion: ambient only at shell level, section reveal minimal.
- Acceptance:
  - queue is easier to scan than decorative metrics
  - no overlap or overflow at 390/375/320
  - summary cards and KPI sections share common rhythm
- Notes: dashboard should demonstrate ambient mode, not excuse noisy UI.
- Watchpoints: metric cards becoming too decorative, queue losing prominence.

### /app/incoming
- File: `frontend/app/src/app/routes/app/incoming.tsx` | Lines: 836 | Inline styles: 0 | Wave: W4 | Shell: quiet | Priority: P0
- Problems: advanced filter reveal is page-local, queue cards need canonical parity and scheduling modal must align with overlay contract.
- Target structure:
  1. ops hero
  2. toolbar with search and primary filters
  3. advanced filter area or mobile filter sheet
  4. queue card list
  5. pagination/footer
  6. schedule modal
- Components: Hero/Header, Toolbar, Search Field, Filter Bar, Cards, Pagination, Modals, Status Blocks.
- Desktop: full-width triage queue with clear counters and actions.
- Tablet: wrapped controls above queue, preserve scan rhythm.
- Mobile: card-first queue with bottom-safe actions and sheet-backed filters.
- Navigation: open candidate-related drill-downs without losing queue context where possible.
- States: loading, empty queue, filtered empty, scheduling pending/error/success.
- Motion: quick filter reveal, restrained modal motion.
- Acceptance:
  - scheduling remains one of the fastest flows in product
  - filter interactions are understandable on mobile
  - no blocked action at 320px+
- Notes: recommended first route after W1-W3.
- Watchpoints: modal focus return, filter discoverability, long-note expansion.

### /app/slots
- File: `frontend/app/src/app/routes/app/slots.tsx` | Lines: 1239 | Inline styles: 0 | Wave: W4 | Shell: quiet | Priority: P0
- Problems: dense filter area, bulk state complexity, duplicated table/card modes.
- Target structure:
  1. ops hero
  2. summary/status strip
  3. toolbar and filter area
  4. bulk action bar
  5. desktop table / mobile card list
  6. detail or secondary action surfaces
- Components: Hero/Header, Toolbar, Filter Bar, Tables, Mobile Card Lists, Buttons, Badges, Pagination, Empty States.
- Desktop: dense but readable table-first management surface.
- Tablet: summary retained, controls wrap, table stays usable.
- Mobile: cards with explicit status, owner/time meta and action row parity.
- Navigation: detail and create flows remain easy to reach.
- States: loading, empty, filtered empty, selected rows, pending bulk action.
- Motion: no flourish on rows; only button/card feedback.
- Acceptance:
  - mobile cards expose the same critical actions as rows
  - bulk actions remain safe and obvious
  - no horizontal overflow in critical states
- Notes: parity matrix is mandatory.
- Watchpoints: selected state visibility, bulk bar overlap, detail access on mobile.

### /app/candidates
- File: `frontend/app/src/app/routes/app/candidates.tsx` | Lines: 831 | Inline styles: 0 | Wave: W4 | Shell: quiet | Priority: P0
- Problems: list/kanban/calendar hierarchy is uneven; mobile must prioritize list view more clearly.
- Target structure:
  1. ops hero
  2. search/filter/view toolbar
  3. optional AI recommendation block
  4. active content area for current view
  5. pagination/state footer
- Components: Hero/Header, Toolbar, Search Field, Filter Bar, Tabs or Segmented Controls, Tables, Mobile Card Lists, Kanban Columns, Empty States.
- Desktop: list and alternate views clearly separated by hierarchy.
- Tablet: wrapped controls, alternate views still usable.
- Mobile: list-first; alternate views available but visually secondary.
- Navigation: strong list-detail relationship with candidate detail route.
- States: loading, empty, filtered empty, move error, delete pending/error.
- Motion: restrained view switching, drag-over only for kanban.
- Acceptance:
  - list mode is the primary mobile and desktop scanning mode
  - view switching remains predictable
  - no action loss between row and card variants
- Notes: do not polish mobile kanban before list parity is stable.
- Watchpoints: URL query sync, kanban drag behavior, calendar complexity.

### /app/candidates/$candidateId
- File: `frontend/app/src/app/routes/app/candidate-detail.tsx` | Lines: 2937 | Inline styles: 1 | Wave: W4 | Shell: quiet | Priority: P0
- Problems: highest density screen, heavy cognitive load, mobile section access and scroll behavior need hardening.
- Target structure:
  1. hero with identity and critical CTA cluster
  2. pipeline strip and next-step actions
  3. summary chips/meta
  4. collapsible section stack:
     - profile/source
     - slots/interviews
     - tests/reports
     - AI insights
     - messaging/history
- Components: Hero/Header, Section Container, Tabs, Form Sections, Cards, Preview Panels, AI Panels, Status Blocks, Modals.
- Desktop: one clear narrative flow from action to detail.
- Tablet: stack side information below critical actions.
- Mobile: keep as full route, use accordion/tabs only for dense secondary sections.
- Navigation: back to list keeps context; internal section navigation should not mimic global nav.
- States: loading, partial AI loading/error, preview overlays, empty tests/slots/history.
- Motion: minimal; dense content should not animate heavily.
- Acceptance:
  - hero and pipeline are readable without scrolling deep
  - mobile sections remain accessible and keyboard-safe
  - AI, test and report blocks feel secondary to primary hiring actions
- Notes: migrate only after shared primitives settle.
- Watchpoints: action displacement, report/preview dialogs, scrollable-region focus.

### /app/messenger
- File: `frontend/app/src/app/routes/app/messenger.tsx` | Lines: 858 | Inline styles: 0 | Wave: W4 | Shell: quiet | Priority: P1
- Problems: split pane and route shell are functionally solid but visually fragmented; multiple modal flows must align with shared overlay contract.
- Target structure:
  1. messenger hero/header
  2. thread list section
  3. active chat section
  4. composer
  5. task/action overlays
- Components: Hero/Header, Section Container, Chat Components, Toolbar, Search Field, Modals, Toasts, Empty States.
- Desktop: split pane remains, but hierarchy must be calmer and more deliberate.
- Tablet: compress panes or stack if width is insufficient.
- Mobile: sequential thread list -> conversation flow.
- Navigation: thread selection and back behavior must remain obvious on mobile.
- States: loading threads/messages, empty thread list, send error, task accept/decline flows.
- Motion: subtle message and modal feedback only.
- Acceptance:
  - thread and conversation hierarchy is clear
  - mobile thread/chat flow remains fast
  - send and task flows preserve context
- Notes: route depends on shell toast behavior; coordinate with W2/W7.
- Watchpoints: composer height, modal stacking, unread state visibility.

### /app/calendar
- File: `frontend/app/src/app/routes/app/calendar.tsx` | Lines: 962 | Inline styles: 1 | Wave: W4 | Shell: quiet | Priority: P1
- Problems: current mobile behavior is incremental rather than redesigned; filters and overlays are isolated from shared grammar.
- Target structure:
  1. ops hero
  2. calendar toolbar/filters
  3. mobile view switch if needed
  4. calendar surface
  5. task modal/sheet flows
- Components: Hero/Header, Toolbar, Filter Bar, Calendar Surfaces, Modals/Sheets, Buttons, Status Blocks.
- Desktop: preserve calendar density with cleaner controls.
- Tablet: simplify top controls and modal sizing.
- Mobile: default to readable day or short-range mode, strong task drill-down.
- Navigation: task create/edit overlays should not feel detached from calendar context.
- States: loading, create/edit/delete task error, busy modal state.
- Motion: overlay-only, no large calendar flourish.
- Acceptance:
  - mobile calendar is usable without precision scrolling
  - task flows are consistent with shared overlays
  - filters fit in available width or move into sheet
- Notes: separate wrapper polish from FullCalendar internals.
- Watchpoints: calendar CSS bleed, modal sizing, event density on narrow screens.

## Wave 6 Admin And Utility Screens
### /app/profile
- File: `frontend/app/src/app/routes/app/profile.tsx` | Lines: 676 | Inline styles: 1 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: cabinet-style layout diverges from `app-page` grammar.
- Target structure: hero, settings sections, KPI section, planner section.
- Components: Hero/Header, Section Container, Form Sections, Status Blocks, Cards.
- Desktop/tablet/mobile: modular personal dashboard with quieter chrome and clear save pattern.
- Navigation: profile remains terminal route, no deep subnav.
- States: load/save/KPI states.
- Motion: minimal.
- Acceptance: personal settings and KPI blocks align with shared system; Watchpoints: avatar actions, planner density.

### /app/recruiters
- File: `frontend/app/src/app/routes/app/recruiters.tsx` | Lines: 210 | Inline styles: 3 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: local card grid and inline progress styling.
- Target structure: hero + roster list/grid.
- Components: Hero/Header, Cards, Badges, Toolbar, Empty States.
- Desktop/tablet/mobile: responsive card roster with edit CTA.
- Navigation: create/edit routes easy to reach.
- States: loading, empty, row-level error.
- Motion: subtle card hover only.
- Acceptance: recruiter list fits shared entity-list pattern; Watchpoints: load bar styling.

### /app/recruiters/new
- File: `frontend/app/src/app/routes/app/recruiter-new.tsx` | Lines: 440 | Inline styles: 4 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: partly aligned with edit flow but still local in layout.
- Target structure: hero -> grouped form sections -> summary footer.
- Components: Form Sections, Buttons, Inputs, Selects, Cards.
- Desktop/tablet/mobile: same grammar as recruiter-edit with simplified create emphasis.
- Navigation: back to list safe, unsaved changes awareness if later added.
- States: validation, save error, success/redirect.
- Motion: local submit feedback only.
- Acceptance: create and edit recruiter flows feel like one family; Watchpoints: city selection cards.

### /app/recruiters/$recruiterId/edit
- File: `frontend/app/src/app/routes/app/recruiter-edit.tsx` | Lines: 559 | Inline styles: 6 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: grouped well already, but still local layout and action semantics.
- Target structure: hero -> primary form sections -> aside diagnostics -> action footer.
- Components: Form Sections, Toolbar, Buttons, Inputs, Selects, Status Blocks.
- Desktop/tablet/mobile: shared admin form grammar with optional sticky mobile footer.
- Navigation: destructive and reset actions remain visible but secondary.
- States: loading, save error, delete error, validation error.
- Motion: none beyond action feedback.
- Acceptance: edit flow adopts canonical admin form grammar; Watchpoints: delete/reset and city search behavior.

### /app/cities
- File: `frontend/app/src/app/routes/app/cities.tsx` | Lines: 210 | Inline styles: 0 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: entity list is functional but not yet normalized.
- Target structure: hero + city list/grid.
- Components: Hero/Header, Cards, Badges, Toolbar, Empty States.
- Desktop/tablet/mobile: same entity-list grammar as recruiters.
- Navigation: edit/create clear and fast.
- States: loading, empty, action errors.
- Motion: card hover/tap only.
- Acceptance: city list aligns with entity management pattern; Watchpoints: toggle/delete affordances.

### /app/cities/new
- File: `frontend/app/src/app/routes/app/city-new.tsx` | Lines: 440 | Inline styles: 0 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: good grouping but still page-local form identity.
- Target structure: hero -> parameters -> plan -> additional -> recruiter selection -> footer.
- Components: Form Sections, Inputs, Selects, Chips, Cards, Buttons.
- Desktop/tablet/mobile: canonical admin form grammar with stacked mobile recruiter selection.
- Navigation: back to city list, clear save path.
- States: validation, save error, empty recruiter search.
- Motion: no extra motion.
- Acceptance: city-new shares exact grammar with city-edit where relevant; Watchpoints: recruiter card density.

### /app/cities/$cityId/edit
- File: `frontend/app/src/app/routes/app/city-edit.tsx` | Lines: 1108 | Inline styles: 97 | Wave: W6 | Shell: quiet | Priority: P0
- Problems: highest mounted inline-style debt, long-form density, mixed summary and field grammar.
- Target structure:
  1. hero summary
  2. core config section
  3. recruiting ownership section
  4. automation/reminder section
  5. HH/templates/linked entities section
  6. save footer
- Components: Form Sections, Status Blocks, Cards, Buttons, Inputs, Selects, Preview Panels.
- Desktop: grouped long-form with strong section rhythm.
- Tablet: stacked sections with reduced multi-column density.
- Mobile: section-first flow with sticky save only if validated safe.
- Navigation: secondary actions remain visible but cannot bury primary save.
- States: loading, linked-entity empty, validation, save success/error.
- Motion: minimal.
- Acceptance:
  - inline-style debt materially reduced
  - long-form is scannable and keyboard-safe
  - mobile save remains reachable
- Notes: split extraction by spacing/layout/color/sizing.
- Watchpoints: hidden layout dependencies, linked section collapses, save footer overlap.

### /app/templates
- File: `frontend/app/src/app/routes/app/template-list.tsx` | Lines: 530 | Inline styles: 24 | Wave: W6 | Shell: quiet | Priority: P1
- Problems: matrix/list duality and inline debt.
- Target structure: hero -> toolbar -> optional matrix summary -> list/card content.
- Components: Hero/Header, Toolbar, Tables, Mobile Card Lists, Status Blocks, Buttons.
- Desktop/tablet/mobile: list-first with matrix as secondary analytical surface.
- Navigation: create/edit available from same shell.
- States: loading, filtered empty, action feedback.
- Motion: none beyond controls.
- Acceptance: list and matrix do not fight for primary attention; Watchpoints: card/table parity and matrix overflow.

### /app/templates/new
- File: `frontend/app/src/app/routes/app/template-new.tsx` | Lines: 262 | Inline styles: 0 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: mostly clean but should inherit form grammar explicitly.
- Target structure: hero -> metadata section -> message body -> footer.
- Components: Form Sections, Inputs, Selects, Preview Panels, Buttons.
- Desktop/tablet/mobile: focused edit form with stacked mobile body.
- Navigation: safe back to library.
- States: validation, preview error, save error.
- Motion: none.
- Acceptance: shares same grammar as template-edit; Watchpoints: long text body readability.

### /app/templates/$templateId/edit
- File: `frontend/app/src/app/routes/app/template-edit.tsx` | Lines: 326 | Inline styles: 16 | Wave: W6 | Shell: quiet | Priority: P1
- Problems: moderate inline debt, preview/editor hierarchy could be clearer.
- Target structure: hero -> metadata and key selection -> body editor -> preview/history area -> footer.
- Components: Form Sections, Inputs, Selects, Preview Panels, Status Blocks, Buttons.
- Desktop/tablet/mobile: stack preview below editor on smaller widths.
- Navigation: preserve template context and safe return to list.
- States: loading, preview loading/error, save error.
- Motion: no flourish.
- Acceptance: editor and preview fit shared library-edit grammar; Watchpoints: character count and context-key help.

### /app/questions
- File: `frontend/app/src/app/routes/app/questions.tsx` | Lines: 126 | Inline styles: 0 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: small list screen but needs consistency with templates and other admin libraries.
- Target structure: hero -> toolbar -> table/card list.
- Components: Hero/Header, Toolbar, Tables, Mobile Card Lists, Buttons.
- Desktop/tablet/mobile: simple library list with mobile cards.
- Navigation: clear create/edit.
- States: loading, empty.
- Motion: minimal.
- Acceptance: aligns with library pattern; Watchpoints: mobile card parity.

### /app/questions/new
- File: `frontend/app/src/app/routes/app/question-new.tsx` | Lines: 121 | Inline styles: 7 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: compact form with local inline layout.
- Target structure: hero -> metadata fields -> JSON payload editor -> footer.
- Components: Form Sections, Inputs, Selects, Buttons, Status Blocks.
- Desktop/tablet/mobile: identical focused edit flow, stacked on mobile.
- Navigation: back to list.
- States: validation, JSON parse error, save error.
- Motion: none.
- Acceptance: create flow uses shared form grammar; Watchpoints: payload editor height and error tone.

### /app/questions/$questionId/edit
- File: `frontend/app/src/app/routes/app/question-edit.tsx` | Lines: 141 | Inline styles: 8 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: same as create flow plus loading state.
- Target structure: hero -> metadata section -> JSON payload editor -> footer.
- Components: Form Sections, Inputs, Selects, Buttons, Status Blocks.
- Desktop/tablet/mobile: same as create.
- Navigation: clear back path and identity of edited item.
- States: loading, validation, save error.
- Motion: none.
- Acceptance: edit flow matches new-question pattern exactly; Watchpoints: consistency with create screen.

### /app/test-builder
- File: `frontend/app/src/app/routes/app/test-builder.tsx` | Lines: 446 | Inline styles: 23 | Wave: W6 | Shell: quiet | Priority: P1
- Problems: workspace-specific layout and editor styles.
- Target structure: hero -> mode switch -> builder list -> editor side section.
- Components: Hero/Header, Section Container, Toolbar, Form Sections, Preview Panels, Buttons.
- Desktop: two-panel workspace.
- Tablet: stacked or drawer-assisted editing.
- Mobile: simplified or constrained utility mode.
- Navigation: easy switch to graph mode.
- States: loading, dirty state, save message.
- Motion: minimal.
- Acceptance: builder feels like admin workspace, not isolated tool; Watchpoints: drag/sort handles and question detail editor.

### /app/test-builder/graph
- File: `frontend/app/src/app/routes/app/test-builder-graph.tsx` | Lines: 1147 | Inline styles: 29 | Wave: W6 | Shell: quiet | Priority: P1
- Problems: graph canvas and side panels are desktop-heavy, high inline debt.
- Target structure: hero -> mode switch -> toolbar -> canvas -> preview -> side editor.
- Components: Hero/Header, Section Container, Preview Panels, Form Sections, Buttons, Status Blocks.
- Desktop: desktop-first workspace preserved.
- Tablet: side editor becomes lower section or drawer.
- Mobile: constrained view or read-mostly fallback, not full graph editing.
- Navigation: keep clear path back to list mode.
- States: graph loading, preview loading/error, apply/sync state.
- Motion: minimal, no canvas flourish.
- Acceptance: graph mode shares workspace grammar and clearer panel hierarchy; Watchpoints: canvas sizing, preview/editor persistence.

### /app/message-templates
- File: `frontend/app/src/app/routes/app/message-templates.tsx` | Lines: 322 | Inline styles: 25 | Wave: W6 | Shell: quiet | Priority: P1
- Problems: list/editor split with many inline layout choices.
- Target structure: hero -> library list section -> editor section -> history section.
- Components: Hero/Header, Section Container, Form Sections, Buttons, Tables or Cards, Status Blocks.
- Desktop/tablet/mobile: list and editor stack gracefully on smaller widths.
- Navigation: clear active template context.
- States: loading, history empty, save/delete error.
- Motion: none beyond overlay if used.
- Acceptance: message-template workflow fits admin library grammar; Watchpoints: editor/history balance and mobile stacking.

### /app/system
- File: `frontend/app/src/app/routes/app/system.tsx` | Lines: 797 | Inline styles: 42 | Wave: W6 | Shell: quiet | Priority: P0
- Problems: dense ops/config workspace, wide tables, mixed local grammar.
- Target structure:
  1. hero
  2. tab or mode control
  3. policy/config sections
  4. jobs/logs sections
  5. table/card responsive wrappers
- Components: Hero/Header, Tabs, Toolbar, Tables, Status Blocks, Form Sections, Buttons, Empty States.
- Desktop: dense observability page.
- Tablet: stack toolbars and reduce table complexity.
- Mobile: card or stacked summaries, no broken wide tables.
- Navigation: tabs remain obvious and stable.
- States: loading, degraded, empty logs/jobs, errors.
- Motion: none beyond tabs/overlay.
- Acceptance:
  - inline-style debt materially reduced
  - tabs and tables remain operationally clear
  - mobile/tablet no longer feel like compressed desktop
- Notes: second-highest debt after city-edit.
- Watchpoints: table overflow, log readability, reminder policy grouping.

### /app/copilot
- File: `frontend/app/src/app/routes/app/copilot.tsx` | Lines: 432 | Inline styles: 0 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: role-based AI/chat and KB controls need shared section grammar.
- Target structure: hero -> chat area -> admin KB controls -> preview/asset sections.
- Components: Hero/Header, AI Panels, Form Sections, Toolbar, Buttons, Status Blocks.
- Desktop/tablet/mobile: chat-first on smaller widths, admin controls secondary.
- Navigation: preserve role-specific controls without clutter.
- States: loading, ask pending/error, KB action states.
- Motion: disclosure only.
- Acceptance: copilot fits shared admin/AI grammar; Watchpoints: long textareas and role gating.

### /app/simulator
- File: `frontend/app/src/app/routes/app/simulator.tsx` | Lines: 173 | Inline styles: 3 | Wave: W6 | Shell: quiet | Priority: P3
- Problems: utility page with minor inline debt and local summary styling.
- Target structure: hero -> run controls -> summary -> steps/report.
- Components: Hero/Header, Form Sections, Status Blocks, Cards, Buttons.
- Desktop/tablet/mobile: compact utility screen.
- Navigation: utility-only, no deep nav.
- States: run pending, report loading/error.
- Motion: none.
- Acceptance: simulator fits utility route grammar; Watchpoints: feature-flag state and summary blocks.

### /app/detailization
- File: `frontend/app/src/app/routes/app/detailization.tsx` | Lines: 529 | Inline styles: 27 | Wave: W6 | Shell: quiet | Priority: P1
- Problems: analytics density and high inline layout debt.
- Target structure: hero -> filter bar -> summary/comparison sections -> detail tables.
- Components: Hero/Header, Toolbar, Filter Bar, Tables, Status Blocks, Cards.
- Desktop: report page with quiet hierarchy.
- Tablet: stacked grids and narrowed summaries.
- Mobile: progressive disclosure before dense tables.
- Navigation: maintain filter context and export/drill actions if any.
- States: loading, error, empty filter result.
- Motion: none beyond filter controls.
- Acceptance: analytics page becomes readable and responsive; Watchpoints: table overflow and comparison-grid collapse.

### /app/slots/create
- File: `frontend/app/src/app/routes/app/slots-create.tsx` | Lines: 632 | Inline styles: 0 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: creation form should align with shared recruiter-form grammar.
- Target structure: hero -> single slot section -> series section -> preview/footer.
- Components: Form Sections, Inputs, Selects, Preview Panels, Buttons.
- Desktop/tablet/mobile: same flow with stacked mobile fields and safe action footer.
- Navigation: back to slots list.
- States: validation, preview, save error/success.
- Motion: none.
- Acceptance: slot-create uses shared form grammar; Watchpoints: date/time density and preview placement.

### /app/candidates/new
- File: `frontend/app/src/app/routes/app/candidate-new.tsx` | Lines: 519 | Inline styles: 0 | Wave: W6 | Shell: quiet | Priority: P2
- Problems: mixed data entry and optional scheduling need consistent long-form grammar.
- Target structure: hero -> candidate data section -> optional scheduling section -> preview/footer.
- Components: Form Sections, Inputs, Selects, Preview Panels, Buttons, Status Blocks.
- Desktop/tablet/mobile: recruiter form grammar with mobile-safe scheduling controls.
- Navigation: safe return to candidates list.
- States: validation, create error, schedule preview.
- Motion: minimal.
- Acceptance: candidate creation is faster to scan and safer on mobile; Watchpoints: optional scheduling path.

## Implementation Rules
- W4 screens must consume shared primitives first, not invent new ones.
- W6 screens should prioritize inline-style extraction in debt order.
- If a screen needs a truly unique pattern, define whether it belongs to Component Specs before coding it.
