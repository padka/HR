# SCREEN_ARCHITECTURE_MAP

## Scope
- Mounted SPA routes: 31.
- Source of truth: `frontend/app/src/app/main.tsx:97-316`.
- Dormant backlog, not part of first redesign pass:
  - `frontend/app/src/app/routes/app/vacancies.tsx`
  - `frontend/app/src/app/routes/app/reminder-ops.tsx`

## Global Navigation Model
### Desktop
- Primary navigation lives in the root shell and top navigation layer.
- Content model is mostly single-column page flow with optional internal grids.
- Context recovery depends on page title, local actions and direct links rather than breadcrumbs.

### Tablet
- Tablet should preserve the desktop information model, but compress action rails, metrics and side utilities.
- Avoid partial desktop split panes when both columns become weak.

### Mobile
- Primary pattern:
  - fixed header with title/back/profile
  - bottom tab bar for top destinations
  - "More" sheet for secondary routes
  - drill-down routes for dense detail screens
- Target improvement: mobile navigation should feel like a coherent app shell, not a desktop adaptation.

## Shared State Taxonomy
- Loading:
  - local skeleton or screen-level loading state
- Empty:
  - useful next-step message
- Error:
  - preserve context and retry
- Success:
  - lightweight feedback, often toast or inline confirmation
- Disabled/pending:
  - clear reason and visible affordance

## Workflow Groups
### Recruiter Daily Ops
- `/app/incoming`
- `/app/slots`
- `/app/slots/create`
- `/app/candidates`
- `/app/candidates/new`
- `/app/candidates/$candidateId`
- `/app/messenger`
- `/app/calendar`

### Admin Ops
- `/app/dashboard`
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
- `/app/detailization`
- `/app/copilot`
- `/app/simulator`
- `/app/test-builder`
- `/app/test-builder/graph`

### Access And Utility
- `/app`
- `/app/login`

## Screen Inventory
### /app
- Source: `frontend/app/src/app/routes/app/index.tsx`
- Purpose: placeholder SPA landing inside authenticated shell.
- User: admin or recruiter after login/redirect.
- Primary action: jump into real working sections from navigation.
- Secondary actions: none.
- Data density: very low.
- Desktop/tablet/mobile recommendation: keep as redirect-like lightweight shell state; do not treat as meaningful product screen.
- States: static.
- Risks: currently acts as a weak placeholder, not a useful overview.

### /app/login
- Source: `frontend/app/src/app/routes/app/login.tsx`
- Purpose: direct SPA login alternative to legacy auth page.
- User: unauthenticated admin or recruiter.
- Primary action: authenticate.
- Secondary actions: open legacy login page.
- Data density: low.
- Desktop: premium but restrained auth card.
- Tablet/mobile: centered card with minimal decorative chrome.
- States: idle, validation error, auth error, loading.
- Risks: should stay separate from operational shell ambience.

### /app/dashboard
- Source: `frontend/app/src/app/routes/app/dashboard.tsx`
- Purpose: department KPI overview and operational summary.
- User: mostly admin.
- Primary action: scan metrics and drill into active problems.
- Secondary actions: filter KPIs, refresh data, inspect incoming queue from dashboard.
- Data density: medium-high.
- Desktop: hero, summary cards, leaderboard, KPI block, incoming queue.
- Tablet: two-column compression with clear dominance of active queue.
- Mobile: compact executive snapshot, not a full analyst board.
- States: loading, empty metrics, API error, filtered states.
- Risks: work queue and decorative metrics currently compete for attention.

### /app/profile
- Source: `frontend/app/src/app/routes/app/profile.tsx`
- Purpose: user settings, KPI, planner, health and personal controls.
- User: admin and recruiter.
- Primary action: update settings and inspect personal operating context.
- Secondary actions: avatar upload/delete, KPI review.
- Data density: medium.
- Desktop: hero plus modular personal panels.
- Tablet: stacked panels with retained KPI visibility.
- Mobile: profile-first layout, fewer simultaneous cards, clear save area.
- States: loading, save success, save error, KPI loading/error.
- Risks: cabinet-style visual language differs from newer app-page patterns.

### /app/slots
- Source: `frontend/app/src/app/routes/app/slots.tsx`
- Purpose: manage slot inventory, statuses and assignments.
- User: recruiter and admin.
- Primary action: filter, inspect and act on slots.
- Secondary actions: bulk remind, bulk delete, view details.
- Data density: high.
- Desktop: summary strip, advanced filters, table view.
- Tablet: summary retained, filters wrap, table stays readable.
- Mobile: card list with primary actions and status.
- States: loading, empty, filtered empty, bulk selection, pending actions.
- Risks: dual rendering for card/table and bulk-toolbar complexity need shared contract.

### /app/slots/create
- Source: `frontend/app/src/app/routes/app/slots-create.tsx`
- Purpose: create one slot or a batch of slots with timezone preview.
- User: recruiter and admin.
- Primary action: create slot inventory.
- Secondary actions: compare single-slot vs series behavior.
- Data density: medium.
- Desktop: two clear creation modes with preview.
- Tablet: stacked creation blocks.
- Mobile: form-first with bottom-safe CTA.
- States: validation, preview, create success/error.
- Risks: complex date/time inputs and long-form layout on mobile.

### /app/recruiters
- Source: `frontend/app/src/app/routes/app/recruiters.tsx`
- Purpose: browse recruiter roster and quick stats.
- User: admin.
- Primary action: inspect recruiter health and open edit/new flows.
- Secondary actions: view load, active status and city coverage.
- Data density: medium.
- Desktop: responsive card grid.
- Tablet: two-column card layout.
- Mobile: single-column cards with clear edit CTA.
- States: loading, empty, row-level errors.
- Risks: inline styles and locally defined progress bar treatment.

### /app/recruiters/new
- Source: `frontend/app/src/app/routes/app/recruiter-new.tsx`
- Purpose: create recruiter profile and assign city access.
- User: admin.
- Primary action: complete recruiter setup.
- Secondary actions: review communication readiness and permissions summary.
- Data density: medium-high.
- Desktop: hero plus form sections and aside checks.
- Tablet: stacked form groups with summary blocks below.
- Mobile: simplified section sequence, large targets for city selection.
- States: validation, unsaved changes, save error, save success/redirect.
- Risks: partially shares patterns with recruiter-edit, but still includes local layout styling.

### /app/recruiters/$recruiterId/edit
- Source: `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- Purpose: edit recruiter profile, connectivity and coverage.
- User: admin.
- Primary action: update recruiter settings safely.
- Secondary actions: password reset, delete, review access coverage.
- Data density: high.
- Desktop: hero, grouped form sections, sidecards.
- Tablet: stacked groups with narrower aside.
- Mobile: section-first edit flow with clear save and destructive actions.
- States: loading, save error, delete error, validation error.
- Risks: large form, local component grammar and mixed inline styles.

### /app/cities
- Source: `frontend/app/src/app/routes/app/cities.tsx`
- Purpose: browse configured cities and access edit/create actions.
- User: admin.
- Primary action: inspect city setup and open edit.
- Secondary actions: toggle state, delete.
- Data density: medium.
- Desktop: card list or grid.
- Tablet/mobile: stacked cards with visible ownership and status.
- States: loading, empty, delete/toggle error.
- Risks: needs stronger shared admin-list pattern.

### /app/cities/new
- Source: `frontend/app/src/app/routes/app/city-new.tsx`
- Purpose: create city configuration, hiring plan, recruiter assignment and metadata.
- User: admin.
- Primary action: create new city.
- Secondary actions: preview timezone and select recruiters.
- Data density: high.
- Desktop: hero plus grouped city form.
- Tablet: stacked sections with compact chips and recruiter cards.
- Mobile: long-form flow with reduced simultaneous controls.
- States: validation, save error, empty recruiter search.
- Risks: recruiter selection can become visually noisy on small screens.

### /app/cities/$cityId/edit
- Source: `frontend/app/src/app/routes/app/city-edit.tsx`
- Purpose: edit the most complex city-specific hiring and automation settings.
- User: admin.
- Primary action: maintain city configuration without breaking operations.
- Secondary actions: manage responsible recruiters, reminders, HH vacancy links, templates, quotas.
- Data density: very high.
- Desktop: grouped long-form sections with summary hero.
- Tablet: stacked sections, reduced side-by-side density.
- Mobile: needs full redesign into digestible sections and sticky save model.
- States: loading, validation error, save success/error, empty linked entities.
- Risks: highest inline-style debt and one of the biggest long-form UX risks.

### /app/templates
- Source: `frontend/app/src/app/routes/app/template-list.tsx`
- Purpose: browse template coverage by stage and city.
- User: admin.
- Primary action: inspect template availability and open edit/create.
- Secondary actions: search, filter by stage and city, compare overrides.
- Data density: high.
- Desktop: coverage matrix plus list table.
- Tablet: reduce matrix complexity and preserve list usability.
- Mobile: cards/list, matrix summary only when helpful.
- States: loading, filtered empty, save/delete feedback.
- Risks: desktop matrix and mobile card logic diverge heavily.

### /app/templates/new
- Source: `frontend/app/src/app/routes/app/template-new.tsx`
- Purpose: create message template.
- User: admin.
- Primary action: choose template key/stage and author message.
- Secondary actions: preview variables, watch character count.
- Data density: medium.
- Desktop: focused edit form.
- Tablet/mobile: stacked composer form with strong helper text.
- States: validation, preview error, save error.
- Risks: textarea-heavy editing on small screens.

### /app/templates/$templateId/edit
- Source: `frontend/app/src/app/routes/app/template-edit.tsx`
- Purpose: edit template content and preview context substitution.
- User: admin.
- Primary action: safely update a live template.
- Secondary actions: preview, inspect key metadata, char count.
- Data density: medium.
- Desktop: split knowledge and editing rhythm.
- Tablet/mobile: stacked editing with preview below.
- States: loading, preview loading/error, save error.
- Risks: context-heavy template editing needs clearer preview hierarchy.

### /app/questions
- Source: `frontend/app/src/app/routes/app/questions.tsx`
- Purpose: question library list for tests.
- User: admin.
- Primary action: browse and edit questions.
- Secondary actions: create new question.
- Data density: medium.
- Desktop: compact table.
- Tablet/mobile: card list with essential metadata.
- States: loading, empty, list errors.
- Risks: simple today, but lacks shared library-list pattern.

### /app/questions/new
- Source: `frontend/app/src/app/routes/app/question-new.tsx`
- Purpose: create test question with JSON payload.
- User: admin.
- Primary action: compose question metadata and payload.
- Secondary actions: toggle active state.
- Data density: medium.
- Desktop/tablet/mobile: focused form with JSON editor.
- States: validation, JSON parse error, save error.
- Risks: payload editing needs stronger error affordance and responsive editor sizing.

### /app/questions/$questionId/edit
- Source: `frontend/app/src/app/routes/app/question-edit.tsx`
- Purpose: edit existing question payload.
- User: admin.
- Primary action: update question content safely.
- Secondary actions: inspect question ID and activation.
- Data density: medium.
- Desktop/tablet/mobile: same focused edit form model as create.
- States: loading, save error, validation error.
- Risks: consistency with new-question flow should be exact.

### /app/test-builder
- Source: `frontend/app/src/app/routes/app/test-builder.tsx`
- Purpose: build and order tests/questions in list-oriented interface.
- User: admin.
- Primary action: edit test blocks and question order.
- Secondary actions: switch to graph view, preview dirty state.
- Data density: high.
- Desktop: multi-column builder/editor workspace.
- Tablet: simplified stacked builder and detail editor.
- Mobile: read-only or heavily simplified management view is preferable.
- States: loading, dirty state, save message, question detail loading.
- Risks: complex editor workspace is desktop-native and currently uses many local patterns.

### /app/test-builder/graph
- Source: `frontend/app/src/app/routes/app/test-builder-graph.tsx`
- Purpose: graph-based test flow editor and bot preview.
- User: admin.
- Primary action: inspect and edit branching graph.
- Secondary actions: run preview, edit nodes and conditions.
- Data density: very high.
- Desktop: canvas plus preview plus editor.
- Tablet: reduced multi-panel mode, likely drawer-based editing.
- Mobile: not suited for full graph editing; needs simplified review mode or restricted capability.
- States: loading, preview loading/error, save/apply state, node detail loading.
- Risks: extremely desktop-heavy layout and high inline-style debt.

### /app/message-templates
- Source: `frontend/app/src/app/routes/app/message-templates.tsx`
- Purpose: simplified message template management with list left and editor right.
- User: admin.
- Primary action: choose template and edit it.
- Secondary actions: inspect history, create new template, delete.
- Data density: medium-high.
- Desktop: two-panel editor flow.
- Tablet: stack list and editor with persistent context.
- Mobile: route or accordion-based edit sequence, not equal-width panels.
- States: loading, history empty, save/delete errors.
- Risks: many inline layout rules and weak responsive abstraction.

### /app/messenger
- Source: `frontend/app/src/app/routes/app/messenger.tsx`
- Purpose: internal coordination and candidate task handoff.
- User: admin and recruiter.
- Primary action: read and send messages.
- Secondary actions: send files, approve/decline tasks, open candidate context.
- Data density: high.
- Desktop: split pane with thread list and active chat.
- Tablet: adaptive split or stacked progression.
- Mobile: thread list, then active chat route state.
- States: thread loading, message loading, send pending/error, task modal states.
- Risks: chat polling and toast logic partly coupled to root shell, not only messenger page.

### /app/calendar
- Source: `frontend/app/src/app/routes/app/calendar.tsx`
- Purpose: schedule and manage calendar tasks.
- User: recruiter and admin.
- Primary action: inspect events, create or edit tasks.
- Secondary actions: switch mobile calendar view, filter by city/recruiter/status.
- Data density: high.
- Desktop: grid calendar with filters and task modals.
- Tablet: fewer controls per row, modal sizes adapted.
- Mobile: stronger drill-down, smaller default views, sheet-first task editing.
- States: loading, create/edit/delete error, task modal busy state.
- Risks: current mobile strategy is incremental, not redesigned.

### /app/incoming
- Source: `frontend/app/src/app/routes/app/incoming.tsx`
- Purpose: work queue for incoming candidates waiting on recruiter action.
- User: recruiter primarily.
- Primary action: filter and offer interview time or next step.
- Secondary actions: expand notes, inspect wait time, toggle advanced filters.
- Data density: high.
- Desktop: queue with toolbar and advanced filter band.
- Tablet: stacked controls above list.
- Mobile: card-first queue with immediate actions.
- States: loading, empty queue, filtered empty, scheduling modal, send pending.
- Risks: filter reveal and modal behavior need shared mobile and motion rules.

### /app/system
- Source: `frontend/app/src/app/routes/app/system.tsx`
- Purpose: system health, jobs, reminders, delivery and template operations.
- User: admin.
- Primary action: inspect and manage system operational status.
- Secondary actions: edit policies, search jobs, review logs.
- Data density: very high.
- Desktop: observability and configuration workspace.
- Tablet: stacked panels with simplified toolbars.
- Mobile: should become audit-style sections and simplified tables/cards.
- States: loading, degraded state, empty logs, API error.
- Risks: wide tables, local styling, high cognitive load.

### /app/copilot
- Source: `frontend/app/src/app/routes/app/copilot.tsx`
- Purpose: AI copilot chat and knowledge base operations.
- User: admin and recruiter; admin has more controls.
- Primary action: ask questions and inspect AI output.
- Secondary actions: upload knowledge assets, preview KB items, reindex.
- Data density: medium-high.
- Desktop: split task-oriented AI workspace.
- Tablet: stacked knowledge controls and chat.
- Mobile: chat-first, KB admin actions moved to lower-priority sections or separate route later.
- States: loading, send pending/error, KB preview, reindex status.
- Risks: role-based density and textarea-heavy interactions.

### /app/simulator
- Source: `frontend/app/src/app/routes/app/simulator.tsx`
- Purpose: local scenario simulator and run report.
- User: admin or QA.
- Primary action: run scenario and inspect bottlenecks.
- Secondary actions: switch scenario parameters.
- Data density: medium.
- Desktop/tablet/mobile: compact report page; low redesign priority.
- States: run pending, report loading/error, disabled in prod by flag.
- Risks: feature is utility-like and should not drive system-level patterns.

### /app/detailization
- Source: `frontend/app/src/app/routes/app/detailization.tsx`
- Purpose: detailed analytics/reporting.
- User: admin.
- Primary action: inspect granular breakdowns and filters.
- Secondary actions: compare segments and totals.
- Data density: high.
- Desktop: report page with filter bar and comparison blocks.
- Tablet: stacked grids and fewer columns.
- Mobile: card summaries first, detailed tables behind progressive disclosure.
- States: loading, API error, empty filter result.
- Risks: many inline layout rules and analytics density.

### /app/candidates
- Source: `frontend/app/src/app/routes/app/candidates.tsx`
- Purpose: manage candidate inventory across list, kanban and calendar views.
- User: recruiter and admin.
- Primary action: find candidate and move to next workflow state.
- Secondary actions: AI recommendations, delete, move between kanban stages.
- Data density: high.
- Desktop: filter rail plus view switch plus list/kanban/calendar content.
- Tablet: same hierarchy with tighter wraps and fewer simultaneous controls.
- Mobile: list-first, simplified view switching, careful use of kanban/calendar.
- States: loading, empty, filtered empty, move error, delete pending/error.
- Risks: different view modes have unequal mobile quality.

### /app/candidates/new
- Source: `frontend/app/src/app/routes/app/candidate-new.tsx`
- Purpose: create candidate record and optionally schedule next step.
- User: recruiter and admin.
- Primary action: submit candidate profile.
- Secondary actions: preview timing and scheduling.
- Data density: medium-high.
- Desktop: grouped onboarding form.
- Tablet: stacked form sections with preserved schedule preview.
- Mobile: shorter sections, keyboard-safe fields, clear bottom CTA.
- States: validation, save error, schedule preview.
- Risks: mixed data-entry and scheduling responsibilities increase form length.

### /app/candidates/$candidateId
- Source: `frontend/app/src/app/routes/app/candidate-detail.tsx`
- Purpose: candidate single source of truth.
- User: recruiter and admin.
- Primary action: decide and execute next step for candidate.
- Secondary actions: review AI, HH, pipeline, tests, slots, messaging, notes.
- Data density: very high.
- Desktop: hero, summary, action rail, multi-section detail page.
- Tablet: stacked secondary sections and preserved top actions.
- Mobile: full-route drill-down with compact section access.
- States: loading, partial AI loading/error, slot modals, test/report previews, empty data states.
- Risks: highest functional density in product, major hierarchy challenge.

## Screen Relationship Notes
- `/app/dashboard` should hand off to `/app/incoming`, `/app/slots`, `/app/candidates`.
- `/app/candidates` and `/app/candidates/$candidateId` form a primary list-detail pair.
- `/app/slots` and `/app/slots/create` form an inventory plus creation pair.
- `/app/templates`, `/app/templates/new`, `/app/templates/$templateId/edit` form a canonical admin library flow.
- `/app/questions`, `/app/questions/new`, `/app/questions/$questionId/edit` should share exactly one form grammar.
- `/app/test-builder` and `/app/test-builder/graph` should be one product area with two modes, not two separate visual systems.

## Redesign Priorities By Screen
### Wave 1
- `/app/incoming`
- `/app/slots`
- `/app/candidates`
- `/app/candidates/$candidateId`
- `/app/messenger`
- `/app/dashboard`

### Wave 2
- `/app/calendar`
- `/app/profile`
- `/app/cities/$cityId/edit`
- `/app/recruiters/$recruiterId/edit`
- `/app/templates*`
- `/app/questions*`
- `/app/message-templates`
- `/app/system`
- `/app/test-builder*`
- `/app/detailization`
- `/app/copilot`

## Backlog Screens
- `frontend/app/src/app/routes/app/vacancies.tsx`
- `frontend/app/src/app/routes/app/reminder-ops.tsx`
- Recommendation: keep them in documentation only until they are mounted or confirmed as active roadmap items.
