# DESIGN_REDESIGN_PRD

## Document Status
- Статус: canonical redesign brief for Codex App.
- Дата: 2026-03-07.
- Фаза: audit and planning only. В этом пакете не предполагаются крупные кодовые изменения.
- Scope: только 31 смонтированный SPA route из `frontend/app/src/app/main.tsx:97-316`.
- Backlog outside first pass: `frontend/app/src/app/routes/app/vacancies.tsx`, `frontend/app/src/app/routes/app/reminder-ops.tsx`.

## Product Goal
- Усилить RecruitSmart Admin как daily-use CRM/ATS interface: быстрее читать, быстрее принимать решения, легче поддерживать, стабильнее работать на desktop, tablet и mobile.
- Сохранить текущую бизнес-логику, маршруты и API-контракты.
- Перевести текущую glassmorphism-эстетику в зрелую product-system language: premium depth without noise.

## Product Context
- Продукт: production CRM/ATS для рекрутмента, scheduling, candidate pipeline и командной координации.
- Пользователи:
  - Администратор: управляет городами, рекрутёрами, шаблонами, системными политиками, ботом, отчётами и quality controls.
  - Рекрутёр: работает со входящими, слотами, кандидатами, календарём, сообщениями, personal KPI.
- Core stack:
  - React 18, TanStack Router, React Query, Zustand, Vite 7, TypeScript.
  - Pure CSS with custom properties in `frontend/app/src/theme/tokens.css:1-299`.
  - Shell and pages are heavily controlled by `frontend/app/src/app/routes/__root.tsx:1-1286` and `frontend/app/src/theme/global.css:1-8717`.

## Scope
### In Scope
- Полный аудит дизайна, UX, responsive behavior, mobile usability, motion, accessibility.
- Screen inventory и redesign contract для всех mounted SPA routes.
- Новый planning package для Codex App:
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
- Foundation contract для будущей реализации: tokens, surfaces, shell, responsive rules, motion rules, QA criteria.

### Out Of Scope
- Полная визуальная перепись приложения в этой фазе.
- Изменение backend business APIs.
- Перемещение mounted routes или пересборка router architecture.
- Внедрение нового UI framework, CSS framework или animation library.

## Current System Assessment
- Overall verdict: `visually promising but operationally flawed`.
- Mobile verdict: `partially usable`.
- Verified strengths:
  - strong token base in `frontend/app/src/theme/tokens.css:5-299`
  - reduced-motion support in `frontend/app/src/theme/motion.css:1-165`
  - safe-area aware mobile shell in `frontend/app/src/theme/mobile.css:109-170`, `frontend/app/src/theme/mobile.css:841-850`
  - route-level code splitting in `frontend/app/src/app/main.tsx:4-95`
- Verified structural problems:
  - shell monolith in `frontend/app/src/app/routes/__root.tsx:1-1286`
  - CSS monolith in `frontend/app/src/theme/global.css:1-8717`
  - repeated page-level layout logic across route files
  - high inline-style debt in admin-heavy screens such as `city-edit`, `system`, `test-builder-graph`

## Current Problems
### UI Problems
- Visual language is attractive but not sufficiently governed by a strict page contract.
- `global.css` contains duplicated and overlapping page/table/empty-state definitions at `frontend/app/src/theme/global.css:3401-3697`, `frontend/app/src/theme/global.css:4310-4327`, `frontend/app/src/theme/global.css:6832-6920`.
- Liquid glass effects compete with dense CRM content on operational screens.
- Shared `ui-surface` layer exists in `frontend/app/src/theme/material.css:1-76`, but route files still re-implement local surface rhythm.

### UX Problems
- High-traffic recruiter pages solve filters, toolbars and hierarchy locally instead of through reusable patterns:
  - `frontend/app/src/app/routes/app/dashboard.tsx:427-509`
  - `frontend/app/src/app/routes/app/incoming.tsx:409-466`
  - `frontend/app/src/app/routes/app/messenger.tsx:392-423`
- Candidate detail is functionally strong but too dense for fast scanning in one session:
  - `frontend/app/src/app/routes/app/candidate-detail.tsx:1855-2665`
- System admin pages prioritize completeness over operational readability:
  - `frontend/app/src/app/routes/app/system.tsx:393-783`
  - `frontend/app/src/app/routes/app/city-edit.tsx:520-905`

### Responsive And Mobile Problems
- `mobile-sheet` remains mounted and dialog-semantic when open state is represented in root render path:
  - `frontend/app/src/app/routes/__root.tsx:1250-1258`
- Current z-index ladder is fragile:
  - FAB `frontend/app/src/theme/mobile.css:64`
  - tab bar `frontend/app/src/theme/mobile.css:170`
  - header `frontend/app/src/theme/mobile.css:114`
  - sheet `frontend/app/src/theme/mobile.css:257`
- Mobile kanban uses horizontal pseudo-carousel columns:
  - `frontend/app/src/theme/mobile.css:743-746`
- Table/card dual rendering is repeated route-by-route:
  - `frontend/app/src/app/routes/app/slots.tsx:904-1020`
  - `frontend/app/src/app/routes/app/candidates.tsx:714-764`
  - `frontend/app/src/app/routes/app/template-list.tsx:79-133`, `frontend/app/src/app/routes/app/template-list.tsx:420-463`

### Motion Problems
- Motion primitives exist, but filter reveal still uses `max-height` transition:
  - `frontend/app/src/theme/global.css:8605-8616`
- Background ambience is still shell-level by default, driven from root:
  - `frontend/app/src/app/routes/__root.tsx:763-858`
  - `frontend/app/src/app/routes/__root.tsx:1144-1160`
- Motion hierarchy is not clearly divided into essential, supportive and decorative layers.

### Accessibility Problems
- Desktop landmark structure is not consistently explicit across all major screens.
- Candidate detail has a known `scrollable-region-focusable` problem in mobile audit.
- Hidden overlays and sheet semantics degrade SR and keyboard experience when closed state is not removed from interaction tree.

## Target Experience
- Interface feels like a premium operational system, not a concept showcase.
- Glass surfaces communicate elevation and grouping, not decoration.
- Primary actions are always easier to spot than secondary analytics or metadata.
- Data-heavy screens are calmer, denser and more legible.
- Desktop, tablet and mobile each have an intentional behavior model.
- Mobile is a first-class product layer: key flows are reachable on 320px width with one-hand operation where possible.
- Motion feels premium but never delays action.

## Design Principles
- Clarity over decoration.
- Premium depth without noise.
- Data density with breathing space.
- Mobile-first operability.
- Motion with purpose.
- Predictable action hierarchy.
- Reusable page primitives before local fixes.
- Visible system status.
- Accessible by default.
- Responsive behavior is part of the design system, not a patch layer.

## Users And Jobs To Be Done
### Admin
- Monitor recruiting performance.
- Configure cities, recruiters, templates, question banks and system policies.
- Investigate delivery jobs, reminders, system templates and logs.
- Maintain trust in automation and scheduling workflows.

### Recruiter
- Triage incoming candidates quickly.
- Create, filter and assign slots.
- Operate candidate list across list, kanban and calendar views.
- Work from candidate detail as the main source of truth.
- Coordinate with team in messenger.
- Work from mobile when desk access is limited.

## Primary User Scenarios
1. Recruiter opens `/app/incoming`, filters queue, proposes a slot, leaves context with no ambiguity.
2. Recruiter uses `/app/slots` to inspect availability, bulk-manage states and confirm details on mobile cards if needed.
3. Recruiter switches `/app/candidates` between list and kanban, then drills down into `/app/candidates/$candidateId`.
4. Recruiter uses `/app/candidates/$candidateId` to review HH info, pipeline, AI recommendations, tests, slots and messaging in one coherent hierarchy.
5. Team member uses `/app/messenger` to pick a thread, reply, forward candidate task and recover from send errors fast.
6. Admin uses `/app/dashboard`, `/app/system`, `/app/cities/$cityId/edit`, `/app/recruiters/$recruiterId/edit`, `/app/templates/$templateId/edit`, `/app/questions/$questionId/edit` to maintain operating model without layout fatigue.
7. Admin or recruiter uses `/app/calendar` on tablet/mobile without critical overflow, blocked controls or viewport traps.

## Functional Design Requirements
### Shell And Navigation
- Keep current route map and path structure.
- Introduce one canonical shell contract:
  - desktop top navigation and profile entry
  - mobile header with contextual back/title/profile
  - mobile tab bar for primary destinations
  - sheet or drawer for secondary routes only when open
- Decorative background becomes opt-in by route type: dashboard, login, empty/demo contexts. Not default for dense data screens.

### Page Contract
- Every screen must map to shared primitives:
  - page shell
  - hero/header
  - section container
  - toolbar/filter area
  - list/table/card container
  - loading/empty/error/success block
- Page-local inline spacing and ad hoc layout values are not allowed in new redesign work.

### Lists And Tables
- Desktop lists may remain tabular when they support rapid scanning.
- Mobile replacements must be intentional, not hidden copies of desktop rows.
- Filters should collapse into sheet/accordion patterns when density requires it.
- Bulk actions must remain visible and non-blocking.

### Forms
- Long forms are sectioned, with clear field grouping, helper text, save feedback and validation rhythm.
- Mobile forms use stacked sections, safe keyboard behavior and bottom-reachable primary actions.

### Overlays
- Closed overlays are fully removed from interaction tree.
- Modals are reserved for high-commit actions.
- Sheets are preferred for mobile filters and secondary options.

### States
- Loading states must be screen-appropriate and predictable.
- Empty states must be informative, not decorative.
- Error states must preserve user context and actions.
- Success states must be visible but lightweight.

## Screen-Level Requirements By Workflow
### Recruiter Daily Ops
- `/app/incoming`, `/app/slots`, `/app/candidates`, `/app/candidates/$candidateId`, `/app/messenger`, `/app/calendar` form the first redesign wave.
- These screens must share one toolbar rhythm, one card/list/table logic and one mobile drill-down logic.

### Admin Ops
- `/app/dashboard`, `/app/cities*`, `/app/recruiters*`, `/app/templates*`, `/app/questions*`, `/app/message-templates`, `/app/system`, `/app/detailization`, `/app/copilot`, `/app/simulator`, `/app/profile`, `/app/test-builder*` form the second redesign wave.
- These screens must transition from page-local styling to reusable long-form/admin patterns.

## Non-Functional Design Requirements
- Performance:
  - no animation that causes measurable interaction lag on operational screens
  - no route-level redesign that regresses code splitting from `frontend/app/src/app/main.tsx:4-95`
- Visual consistency:
  - all surfaces map to shared elevation and border rules
  - typography and spacing come from tokens
- Responsiveness:
  - desktop 1440/1280
  - tablet 1024/768
  - mobile 390/375/320
- Accessibility:
  - visible focus states
  - touch targets 44px+
  - reduced motion
  - no semantic hidden dialogs
  - keyboard reachable scroll regions where interactive
- Maintainability:
  - route files stop owning spacing/layout primitives directly
  - token names remain source of truth in `frontend/app/src/theme/tokens.css`

## Constraints
- No rewrite of React architecture.
- No new UI kit, Tailwind, Framer Motion or design-token runtime.
- No route path changes.
- No destructive changes to API payloads.
- Redesign must fit existing CSS architecture and can progressively split it later.

## Risks And Mitigations
- Risk: visual redesign becomes decorative and hurts productivity.
  - Mitigation: controlled contrast, quiet operational shells, acceptance criteria tied to workflows.
- Risk: mobile effort turns into desktop shrink.
  - Mitigation: separate mobile acceptance criteria and screen logic.
- Risk: giant admin screens remain unmaintainable.
  - Mitigation: second-wave long-form patterns and inline-style debt burn-down.
- Risk: shell changes break navigation.
  - Mitigation: shell-specific tests and smoke coverage.

## Success Metrics
- No hidden-dialog artifacts in mobile shell.
- No blocked core action on 320px+ for recruiter-first flows.
- Reduced layout breakage and z-index conflicts across target viewport matrix.
- Shared page and surface primitives adopted by first-wave routes.
- Reduced inline-style debt on highest-risk admin screens in implementation phase.
- Accessibility regressions decrease on shell, candidate detail and overlay interactions.

## Milestones
### Milestone 1
- Deliver complete audit/planning package in root.
- Approve screen inventory, design principles, responsive contract and QA criteria.

### Milestone 2
- Implement shell, tokens, surfaces and page primitives.
- Fix mobile sheet semantics, quiet shell mode and foundation layers.

### Milestone 3
- Redesign recruiter-first workflows.

### Milestone 4
- Redesign admin-heavy and long-form screens.

### Milestone 5
- Hardening: responsive QA, motion polish, accessibility, automation coverage.

## Acceptance Criteria Summary
- Docs package is self-contained and mapped to real code files.
- Mounted screen inventory covers all 31 SPA routes.
- Responsive and mobile requirements are explicit for every major workflow.
- Design system plan names tokens and component families that exist or can be added within current architecture.
- Implementation roadmap is phase-based, file-aware and non-generic.

## Source Evidence
- Router map: `frontend/app/src/app/main.tsx:97-316`
- Root shell: `frontend/app/src/app/routes/__root.tsx:542-702`, `frontend/app/src/app/routes/__root.tsx:763-858`, `frontend/app/src/app/routes/__root.tsx:1144-1279`
- Tokens: `frontend/app/src/theme/tokens.css:5-299`
- Shared components/styles: `frontend/app/src/theme/components.css:51-173`, `frontend/app/src/theme/pages.css:56-226`, `frontend/app/src/theme/material.css:1-76`
- Mobile shell/z-index: `frontend/app/src/theme/mobile.css:51-170`, `frontend/app/src/theme/mobile.css:253-291`, `frontend/app/src/theme/mobile.css:743-746`
- CSS monolith and filter reveal: `frontend/app/src/theme/global.css:3401-3697`, `frontend/app/src/theme/global.css:7047-7144`, `frontend/app/src/theme/global.css:8141-8174`, `frontend/app/src/theme/global.css:8605-8616`
