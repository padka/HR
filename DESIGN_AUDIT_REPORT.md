# DESIGN_AUDIT_REPORT

## Executive Verdict
- Overall interface quality: `visually promising but operationally flawed`.
- Mobile readiness: `partially usable`.
- Product maturity signal: strong foundation, weak systemic execution.
- Audit scope: 31 mounted SPA routes plus theme and shell layers. Dormant routes are documented as backlog only.

## Audit Method
- Read router map in `frontend/app/src/app/main.tsx:97-316`.
- Read app shell and mobile navigation in `frontend/app/src/app/routes/__root.tsx:542-702`, `frontend/app/src/app/routes/__root.tsx:763-858`, `frontend/app/src/app/routes/__root.tsx:1144-1279`.
- Read tokens and theme layers:
  - `frontend/app/src/theme/tokens.css:5-299`
  - `frontend/app/src/theme/components.css:51-173`
  - `frontend/app/src/theme/pages.css:56-226`
  - `frontend/app/src/theme/mobile.css:3-863`
  - `frontend/app/src/theme/motion.css:1-165`
  - `frontend/app/src/theme/global.css:1-8717`
- Read core workflow screens and representative admin screens.

## Baseline Snapshot
- Frontend stack: React 18, TanStack Router, React Query, Zustand, Vite 7, TypeScript.
- Styling model: pure CSS with tokens, page CSS, mobile CSS, motion CSS, no component library package.
- Known code-shape signals:
  - `frontend/app/src/theme/global.css` is 8717 lines.
  - `frontend/app/src/app/routes/__root.tsx` is 1286 lines.
  - Inline-style debt is concentrated in `city-edit`, `system`, `test-builder-graph`, `detailization`, `message-templates`, `template-list`, `recruiters`.

## Strengths
- Design tokens are already richer than average CRM projects:
  - spacing, radii, blur, motion, z-index, surfaces in `frontend/app/src/theme/tokens.css:10-299`
- Existing shared style primitives already hint at the right direction:
  - `ui-form-shell`, `ui-toolbar`, `ui-state` in `frontend/app/src/theme/components.css:51-173`
  - quiet/ambient shell split in `frontend/app/src/theme/pages.css:56-226`
  - surface layers in `frontend/app/src/theme/material.css:1-76`
- Mobile shell already considers safe area and bottom navigation:
  - `frontend/app/src/theme/mobile.css:109-170`
  - `frontend/app/src/theme/mobile.css:841-850`
- Motion already has reduced-motion guardrails:
  - `frontend/app/src/theme/motion.css:1-165`
- Key recruiter screens already have mobile card fallbacks:
  - `frontend/app/src/app/routes/app/slots.tsx:904-1020`
  - `frontend/app/src/app/routes/app/candidates.tsx:714-764`
- Candidate detail and messenger already contain the right business depth; redesign is a structuring task, not a functional invention.

## A. Visual Design Audit
### What Works
- Liquid glass variant gives the product a distinct aesthetic instead of generic admin styling.
- Typography and spacing tokens are available and reusable.
- Hero/section split is already emerging in redesigned screens:
  - `frontend/app/src/app/routes/app/dashboard.tsx:427-509`
  - `frontend/app/src/app/routes/app/incoming.tsx:409-466`
  - `frontend/app/src/app/routes/app/messenger.tsx:392-406`

### Problems
- Visual language is inconsistent because page-level implementations outrun shared contracts.
- `global.css` defines repeated page headers, page sections, tables and empty states in multiple places:
  - `frontend/app/src/theme/global.css:3401-3697`
  - `frontend/app/src/theme/global.css:4310-4327`
  - `frontend/app/src/theme/global.css:6832-6920`
- Background ambience is too global for data-heavy screens:
  - `frontend/app/src/app/routes/__root.tsx:763-858`
  - `frontend/app/src/app/routes/__root.tsx:1144-1160`
- Dense admin screens still use local hardcoded values and local inline type/spacing rules:
  - `frontend/app/src/app/routes/app/city-edit.tsx:520-905`
  - `frontend/app/src/app/routes/app/system.tsx:393-783`
  - `frontend/app/src/app/routes/app/test-builder-graph.tsx:734-1099`

### Assessment
- Visual quality is above average for internal tooling, but premium styling is not yet backed by premium control.
- Glass layers need stricter contrast and calmer deployment on operational routes.

## B. UX Audit
### Navigation And Wayfinding
- Navigation model is shallow and mostly understandable.
- Mobile shell offers back/title/profile and tab bar, which is good.
- Secondary destinations are hidden behind "More", but the sheet contract is not robust enough yet.

### Workflow Clarity
- `/app/incoming` is close to a strong work queue, but filter density and modal scheduling still feel local to the page:
  - `frontend/app/src/app/routes/app/incoming.tsx:420-466`
  - `frontend/app/src/app/routes/app/incoming.tsx:673-820`
- `/app/candidates` has useful list, kanban and calendar modes, but the screen must explain hierarchy better:
  - `frontend/app/src/app/routes/app/candidates.tsx:461-603`
  - `frontend/app/src/app/routes/app/candidates.tsx:635-823`
- `/app/candidates/$candidateId` is feature-rich but cognitively heavy:
  - `frontend/app/src/app/routes/app/candidate-detail.tsx:1855-2665`
- `/app/messenger` has strong functional flow, but desktop split layout and mobile transition should feel more deliberate:
  - `frontend/app/src/app/routes/app/messenger.tsx:392-502`

### Forms And Admin Operations
- City and recruiter forms expose a lot of business logic, but section grouping and scan rhythm vary by page:
  - `frontend/app/src/app/routes/app/city-new.tsx:211-425`
  - `frontend/app/src/app/routes/app/city-edit.tsx:520-905`
  - `frontend/app/src/app/routes/app/recruiter-new.tsx:221-435`
  - `frontend/app/src/app/routes/app/recruiter-edit.tsx:247-552`
- `system`, `message-templates`, `template-list`, `test-builder*` all solve dense admin UX in different local ways.

### Assessment
- The product supports real daily work, but hierarchy is fragmented.
- Major gain will come from standardizing patterns, not inventing more UI.

## C. Responsive / Adaptive Audit
### What Works
- Breakpoint model exists and is tokenized:
  - `frontend/app/src/theme/tokens.css:273-299`
- Mobile shell and page padding already use safe-area values:
  - `frontend/app/src/theme/tokens.css:281-283`
  - `frontend/app/src/theme/mobile.css:25-25`
  - `frontend/app/src/theme/mobile.css:843-850`
- Mobile card patterns exist for multiple list screens:
  - `frontend/app/src/app/routes/app/slots.tsx:904-1020`
  - `frontend/app/src/app/routes/app/candidates.tsx:714-764`
  - `frontend/app/src/app/routes/app/questions.tsx:43-66`

### Problems
- Responsive behavior is duplicated per route instead of normalized.
- Table/card dual rendering increases maintenance surface and state parity risk:
  - `frontend/app/src/app/routes/app/slots.tsx:904-1157`
  - `frontend/app/src/app/routes/app/candidates.tsx:711-823`
  - `frontend/app/src/app/routes/app/template-list.tsx:79-227`, `frontend/app/src/app/routes/app/template-list.tsx:420-463`
- Kanban on mobile uses horizontally scrolling columns with `grid-auto-columns: minmax(82vw, 82vw)`:
  - `frontend/app/src/theme/mobile.css:743-746`
- Data tables rely on horizontal wrappers, but admin screens still embed tables inside locally styled panels:
  - `frontend/app/src/theme/global.css:6895-6938`
  - `frontend/app/src/app/routes/app/system.tsx:560-783`

### Assessment
- Responsive adaptation exists, but it is partial and page-specific rather than systematic.

## D. Mobile UX Audit
### What Works
- Bottom tab bar is reachable and safe-area aware.
- Mobile candidate detail is already a separate route, not a panel squeezed into a desktop shell.
- Touch targets in shell are generally adequate.

### Problems
- `mobile-sheet` is rendered as an open-class dialog block in root markup:
  - `frontend/app/src/app/routes/__root.tsx:1250-1258`
- Root code manually toggles `inert` on header and tab bar nodes:
  - `frontend/app/src/app/routes/__root.tsx:672-702`
  - This shows the right intent, but the rendered contract is still too brittle.
- Closed-state overlay semantics are the main blocker for mobile quality sign-off.
- Long admin forms are usable only conditionally; they behave like stacked desktop pages, not mobile-first workflows.
- FullCalendar page has only a minimal mobile view switch, not a rethought mobile scheduling model:
  - `frontend/app/src/app/routes/app/calendar.tsx:362-393`
  - `frontend/app/src/app/routes/app/calendar.tsx:397-549`

### Assessment
- Mobile is functionally present, but not yet product-complete.

## E. Motion Audit
### What Works
- Motion tokens and reduced-motion coverage already exist.
- Shell/page transitions can stay CSS-first.

### Problems
- Decorative background motion is expensive in attention, even if not necessarily expensive in FPS.
- Filter reveal uses `max-height`, which tends to feel soft and janky:
  - `frontend/app/src/theme/global.css:8605-8616`
- Motion hierarchy is not explicitly tied to screen importance, so decorative and operational movement are too close in visual priority.

### Assessment
- Motion quality is promising, but needs stronger governance and less ambient animation on work screens.

## F. Accessibility Audit
### What Works
- App already uses ARIA labels and modal semantics in several places.
- Reduced motion and touch size concerns are not ignored.

### Problems
- Landmark structure is inconsistent at shell and page levels.
- Scrollable regions are not always keyboard-reachable when they become interactive containers.
- Closed overlays must leave interaction tree entirely.
- Color and glass layering should be validated against contrast especially on quiet operational shells.

### Assessment
- Accessibility is above "unstyled internal tool" level, but below production-grade consistency.

## Cross-Screen Consistency Findings
- Headers vary between `page-header`, `dashboard-header`, `messenger-header`, `cabinet-hero`, `recruiter-edit__hero`, `city-form__header`.
- Toolbar/filter zones vary between `toolbar`, `filter-bar`, `ui-filter`, `incoming-toolbar`, `messenger-header__actions`, custom inline flex rows.
- Empty/loading/error states are not standardized enough, despite `ui-state` existing in shared styles.
- Admin pages often ship their own visual grammar instead of extending a common system.

## Critical Issue Register
### P0
1. Mobile sheet is not fully absent from interaction tree when not intended. Ref: `frontend/app/src/app/routes/__root.tsx:1250-1258`.
2. Decorative ambience is still shell-level and distracts from operational screens. Ref: `frontend/app/src/app/routes/__root.tsx:763-858`.
3. No enforced page contract across routes. Evidence: competing page implementations in `dashboard.tsx:427-509`, `incoming.tsx:409-466`, `profile.tsx:236-641`, `system.tsx:216-783`.

### P1
4. Candidate detail density reduces scan speed. Ref: `frontend/app/src/app/routes/app/candidate-detail.tsx:1855-2665`.
5. Mobile/admin responsive patterns are incomplete. Ref: `frontend/app/src/app/routes/app/city-edit.tsx:520-905`, `frontend/app/src/app/routes/app/system.tsx:606-783`.
6. Table/card duplication increases maintenance and consistency risk. Ref: `slots.tsx:904-1157`, `candidates.tsx:711-823`.
7. Calendar mobile model is not fully optimized. Ref: `frontend/app/src/app/routes/app/calendar.tsx:362-549`.

### P2
8. `global.css` monolith slows systemic improvement. Ref: `frontend/app/src/theme/global.css:1-8717`.
9. Filter advanced reveal uses layout-janky animation. Ref: `frontend/app/src/theme/global.css:8605-8616`.
10. Z-index hierarchy is fragile and manually curated. Ref: `frontend/app/src/theme/mobile.css:64`, `frontend/app/src/theme/mobile.css:114`, `frontend/app/src/theme/mobile.css:170`, `frontend/app/src/theme/mobile.css:257`.

## High-Value Opportunities
- Make ambient background opt-in only for dashboard/login/empty/demo routes.
- Standardize page hero, section head, toolbar, state block and content container.
- Replace page-local form rhythm with shared admin-form contract.
- Introduce table/card parity rules so mobile variants remain equivalent.
- Convert candidate detail into clearer hero plus section stack plus action rail hierarchy.
- Normalize empty/loading/error/success treatment across routes.

## Audit Conclusion
- RecruitSmart Admin has a strong visual and technical base.
- The main redesign task is systemic consolidation, not visual reinvention.
- The first implementation wave must start with shell, surfaces, page contract and recruiter-first workflows.
