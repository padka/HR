# RESPONSIVE_AND_MOBILE_AUDIT

## Verdict
- Mobile readiness: `partially usable`.
- Responsive readiness: `acceptable but fragmented`.
- Main blockers to production-grade redesign sign-off:
  - shell-level hidden dialog semantics
  - page-specific responsive logic instead of shared contracts
  - weak mobile autonomy on admin-heavy screens

## Existing Breakpoint Inventory
- Tokens:
  - `--bp-desktop-lg` in `frontend/app/src/theme/tokens.css:273`
  - `--bp-desktop` in `frontend/app/src/theme/tokens.css:274`
  - `--bp-tablet` in `frontend/app/src/theme/tokens.css:275`
  - `--bp-mobile-lg` in `frontend/app/src/theme/tokens.css:276`
  - `--bp-mobile` in `frontend/app/src/theme/tokens.css:277`
- Store-driven mobile detection:
  - `frontend/app/src/app/hooks/useIsMobile.ts` uses 768px match and resize logic.
- Mobile CSS breakpoint:
  - `@media (max-width: 768px)` in `frontend/app/src/theme/mobile.css:3`

## Current Responsive Architecture
- Shell responsiveness is concentrated in:
  - `frontend/app/src/app/routes/__root.tsx`
  - `frontend/app/src/theme/mobile.css`
- Shared page responsiveness is partially expressed in:
  - `frontend/app/src/theme/pages.css:79-111`
  - `frontend/app/src/theme/global.css:6832-6938`
- Screen-level responsive behavior is often duplicated in route files, especially when mobile cards coexist with desktop tables.

## Key Findings
### 1. Mobile Shell Is Functionally Present But Semantically Fragile
- The mobile tab bar and safe-area padding are correctly established:
  - `frontend/app/src/theme/mobile.css:165-170`
  - `frontend/app/src/theme/mobile.css:841-850`
- The mobile "More" sheet is still rendered with active dialog structure in root markup:
  - `frontend/app/src/app/routes/__root.tsx:1250-1258`
- Root code compensates by toggling `inert` on sibling UI:
  - `frontend/app/src/app/routes/__root.tsx:672-702`
- Assessment: the contract is too manual and should be reworked in implementation.

### 2. Z-Index Ladder Exists But Is Too Tight
- FAB: `frontend/app/src/theme/mobile.css:64`
- tab bar: `frontend/app/src/theme/mobile.css:170`
- mobile header: `frontend/app/src/theme/mobile.css:114`
- mobile sheet: `frontend/app/src/theme/mobile.css:257`
- Risk: additional sticky filters, toasts and page overlays can collide or require ad hoc escalation.

### 3. Table-To-Card Conversion Exists, But State Parity Is Manual
- Slots:
  - cards `frontend/app/src/app/routes/app/slots.tsx:904-1018`
  - table `frontend/app/src/app/routes/app/slots.tsx:1019-1157`
- Candidates:
  - cards `frontend/app/src/app/routes/app/candidates.tsx:714-763`
  - table `frontend/app/src/app/routes/app/candidates.tsx:764-823`
- Questions:
  - mobile cards `frontend/app/src/app/routes/app/questions.tsx:43-66`
  - desktop table below in same file
- Templates:
  - matrix mobile list `frontend/app/src/app/routes/app/template-list.tsx:79-133`
  - desktop matrix table `frontend/app/src/app/routes/app/template-list.tsx:133-227`
- Assessment: responsive adaptation is useful but expensive to maintain.

### 4. Mobile Kanban Is Serviceable But Not Comfortable
- Mobile kanban scroll container uses horizontal overflow and 82vw columns:
  - `frontend/app/src/theme/mobile.css:743-746`
- Candidate kanban columns live in `frontend/app/src/app/routes/app/candidates.tsx:640-696`.
- Assessment: usable for inspection, weak for frequent drag and comparison on narrow devices.

### 5. Admin And Long-Form Screens Are Not Fully Mobile-First
- `city-edit` contains many locally styled sections and stats blocks:
  - `frontend/app/src/app/routes/app/city-edit.tsx:520-905`
- `system` renders multiple wide tables and custom flex rows:
  - `frontend/app/src/app/routes/app/system.tsx:560-783`
- `test-builder-graph` is desktop-heavy by default:
  - `frontend/app/src/app/routes/app/test-builder-graph.tsx:785-1099`
- Assessment: these screens are conditionally usable on mobile/tablet but not yet redesigned as mobile products.

## Overflow And Collision Catalog
- Potential shell collision:
  - mobile header + tab bar + sheet + page sticky elements
- Potential table overflow:
  - system tables in `frontend/app/src/app/routes/app/system.tsx:560-783`
  - template matrix in `frontend/app/src/app/routes/app/template-list.tsx:133-227`
- Potential layout overflow:
  - kanban horizontal scroll in `frontend/app/src/theme/mobile.css:743-746`
  - desktop-wide preview/editor pages like `test-builder-graph`
- Potential overlay collision:
  - root chat toast plus mobile sheet plus page modal

## Mobile Workflow Completeness Matrix
### Strongest Current Mobile Flows
- `/app/incoming`
- `/app/slots`
- `/app/candidates`
- `/app/candidates/$candidateId`
- `/app/messenger`

### Conditional Mobile Flows
- `/app/calendar`
- `/app/profile`
- `/app/cities`
- `/app/recruiters`
- `/app/templates`
- `/app/questions`

### Weakest Mobile Flows
- `/app/system`
- `/app/cities/$cityId/edit`
- `/app/test-builder`
- `/app/test-builder/graph`
- `/app/detailization`

## Per-Screen Responsive Assessment
### Recruiter-First
- Dashboard:
  - desktop works as summary board
  - tablet needs clearer compression
  - mobile should reduce visual load and prioritize active queue
- Incoming:
  - mobile card-first queue works
  - advanced filters need cleaner sheet/accordion model
- Slots:
  - mobile cards cover core actions
  - bulk actions and sticky context need stricter contract
- Candidates:
  - list mode adapts well
  - kanban and calendar are weaker on narrow screens
- Candidate detail:
  - correct full-route drill-down model
  - density and scroll-region handling still need improvement
- Messenger:
  - sequential mobile thread/chat behavior is sound
  - shell semantics still contaminate quality perception
- Calendar:
  - mobile mode switch exists, but interaction model is still desktop-derived

### Admin And Configuration
- Cities and recruiters lists are mostly safe, but action density could be calmer.
- City and recruiter forms need more section-driven mobile flow.
- Template and question screens are manageable, but matrices and JSON-heavy forms require stronger small-screen rules.
- System, detailization and test-builder pages need separate mobile simplification strategies.

## Viewport Height And Keyboard Risks
- Safe-area variables exist:
  - `frontend/app/src/theme/tokens.css:281-283`
  - `frontend/app/src/theme/mobile.css:388-388`
- Risks remain for:
  - modal-heavy pages on mobile browsers
  - bottom tab bar plus keyboard plus sticky CTA
  - long textareas in copilot and messaging

## Recommended Mobile Layout Strategy
- Shell:
  - closed `mobile-sheet` removed from accessibility tree and hit testing
  - unify scroll lock, focus return, backdrop behavior
- Lists:
  - cards remain default mobile transformation for slots, candidates, templates where needed
  - filters move into sheets or accordions when there are more than 3 controls
- Detail:
  - keep candidate detail and similar entities as full routes
  - use segmented/tabs only for very dense secondary sections
- Forms:
  - stack inputs, simplify helper text, keep save action reachable
- Calendar:
  - mobile mode defaults to fewer simultaneous time columns and stronger task drill-down

## Mobile Acceptance Criteria
- No blocked key action at 320px+.
- No horizontal overflow on core recruiter flows.
- Closed overlays are not focusable or screen-reader visible.
- Header, tab bar, sheet and toast never overlap critical content or each other.
- Forms remain usable with virtual keyboard and short viewport heights.
- Candidate detail, messenger and scheduling remain usable one-handed in primary actions.
