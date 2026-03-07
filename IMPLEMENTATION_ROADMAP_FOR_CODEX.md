# IMPLEMENTATION_ROADMAP_FOR_CODEX

## Purpose
- Convert the audit package into an implementation sequence that Codex App can execute without rewriting the product.
- Keep the roadmap grounded in current files, current routes and current frontend architecture.

## Delivery Model
- Implementation remains progressive.
- Each phase must preserve business logic and route map.
- Each phase ends with validation and QA against acceptance criteria.

## Phase 1. Audit And Foundation Alignment
### Goal
- Freeze redesign intent, scope and acceptance rules before code changes.

### Deliverables
- Root planning package:
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

### Scope
- Audit current shell, theme and routes.
- Confirm mounted route inventory.
- Confirm dormant backlog routes are out of first implementation pass.

### Key Evidence Files
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/global.css`
- `frontend/app/src/theme/mobile.css`

### Risks
- Starting code changes before the system contract is explicit.

### Acceptance Criteria
- Planning package is complete and self-contained.
- All 31 mounted routes are documented.
- Responsive/mobile/motion/a11y requirements are explicit.

## Phase 2. Foundation Layer
### Goal
- Fix shell defects and introduce shared visual and layout contracts.

### Scope
- Shell semantics and layering in `frontend/app/src/app/routes/__root.tsx`
- Tokens and surface tuning in:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/pages.css`
- Shared state, toolbar and form primitives in `frontend/app/src/theme/components.css`
- Quiet vs ambient route behavior in `frontend/app/src/theme/pages.css`
- Minimal cleanup in `frontend/app/src/theme/global.css` only where unavoidable

### Core Tasks
- Remove hidden `mobile-sheet` from closed interaction tree.
- Normalize scroll-lock, focus return, backdrop and safe-area behavior.
- Make ambient background opt-in instead of shell default.
- Adopt one surface ladder: base, raised, floating, overlay.
- Adopt one page contract: hero, section, toolbar, state container.
- Standardize z-index rules for header, tab bar, floating action, sheets, toasts.

### Risks
- Shell changes can easily cause regressions across all routes.

### Dependencies
- Phase 1 artifacts approved.

### Acceptance Criteria
- Closed mobile sheet is not present as active dialog.
- Quiet operational routes no longer use distracting ambient background by default.
- Shared page/surface contract exists in theme files.

## Phase 3. App Shell And Navigation Redesign
### Goal
- Make navigation and shell behavior coherent across desktop, tablet and mobile.

### Scope
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/theme/mobile.css`
- `frontend/app/src/theme/pages.css`
- any shell-specific tests

### Core Tasks
- Tighten desktop navigation hierarchy and page container width rules.
- Refine mobile header title/back/profile behavior.
- Refine mobile tab bar and "More" sheet semantics.
- Ensure shell-level toasts and overlays do not collide.

### Risks
- Global shell refactors can break route context or focus logic.

### Acceptance Criteria
- Mobile header, tab bar and overlays do not overlap critical content.
- Shell works cleanly across 1440, 1280, 1024, 768, 390, 375 and 320.
- Landmark structure is improved at shell level.

## Phase 4. Core Workflow Screens
### Goal
- Redesign the highest-value recruiter workflows first.

### Scope
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/app/routes/app/messenger.tsx`
- `frontend/app/src/app/routes/app/calendar.tsx`

### Core Tasks
- Apply shared hero/section/toolbar contract.
- Reduce glow and decorative noise on operational screens.
- Standardize filter bars, state blocks and list containers.
- Clarify candidate detail hierarchy.
- Improve messenger split-pane to sequential mobile flow continuity.
- Improve calendar controls and overlay behavior.

### Risks
- Candidate detail and slots are dense enough to tempt local fixes instead of systemic reuse.

### Dependencies
- Phase 2 page/surface primitives.
- Phase 3 shell behavior stabilized.

### Acceptance Criteria
- Recruiter-first screens feel visually related and operationally faster.
- Key actions remain available on 320px+.
- No new horizontal overflow or overlay collisions.

## Phase 5. Mobile-First Pass
### Goal
- Turn mobile adaptation into a real product layer.

### Scope
- Review all mounted routes with mobile behavior, prioritizing:
  - `incoming`
  - `slots`
  - `candidates`
  - `candidate detail`
  - `messenger`
  - `calendar`
  - `city-edit`
  - `system`

### Core Tasks
- Convert problematic tables into cards or stacked rows where needed.
- Move dense filters into sheets or accordions.
- Improve bottom-reachable primary actions.
- Validate safe-area and keyboard behavior on long forms.
- Simplify kanban and calendar behavior on narrow screens.

### Risks
- Mobile fixes can fork logic if card/table parity is not designed carefully.

### Acceptance Criteria
- No blocked core flow at 320px+.
- No horizontal overflow in critical scenarios.
- Keyboard, safe-area and sticky-element behavior remain stable.

## Phase 6. Admin Screens And Long-Form Cleanup
### Goal
- Bring configuration and admin screens under the same design contract.

### Scope
- `frontend/app/src/app/routes/app/cities.tsx`
- `frontend/app/src/app/routes/app/city-new.tsx`
- `frontend/app/src/app/routes/app/city-edit.tsx`
- `frontend/app/src/app/routes/app/recruiters.tsx`
- `frontend/app/src/app/routes/app/recruiter-new.tsx`
- `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- `frontend/app/src/app/routes/app/template-list.tsx`
- `frontend/app/src/app/routes/app/template-new.tsx`
- `frontend/app/src/app/routes/app/template-edit.tsx`
- `frontend/app/src/app/routes/app/questions.tsx`
- `frontend/app/src/app/routes/app/question-new.tsx`
- `frontend/app/src/app/routes/app/question-edit.tsx`
- `frontend/app/src/app/routes/app/message-templates.tsx`
- `frontend/app/src/app/routes/app/system.tsx`
- `frontend/app/src/app/routes/app/test-builder.tsx`
- `frontend/app/src/app/routes/app/test-builder-graph.tsx`
- `frontend/app/src/app/routes/app/detailization.tsx`
- `frontend/app/src/app/routes/app/copilot.tsx`
- `frontend/app/src/app/routes/app/profile.tsx`
- `frontend/app/src/app/routes/app/simulator.tsx`

### Core Tasks
- Reduce inline-style debt.
- Standardize long-form layout and field grouping.
- Standardize table wrappers and mobile fallbacks.
- Standardize edit-library-create flows for templates and questions.
- Quiet the visual system for configuration-heavy pages.

### Risks
- High local styling debt can hide regressions unless QA is strict.

### Acceptance Criteria
- Admin forms and libraries share one coherent grammar.
- Long-form screens are readable on tablet and conditionally usable on mobile.
- Inline-style debt is materially reduced on highest-risk screens.

## Phase 7. Hardening And QA
### Goal
- Lock in responsive, accessibility, motion and regression quality.

### Scope
- Theme files, shell, shared primitives and test suites.

### Core Tasks
- Add shell and route visual smoke coverage.
- Add axe checks on major screens.
- Validate reduced-motion behavior.
- Validate viewport matrix and zoom behavior.
- Tune motion and contrast based on QA findings.

### Suggested Test Targets
- `dashboard`
- `incoming`
- `slots`
- `candidates`
- `candidate detail`
- `messenger`
- `city-edit`
- `system`

### Acceptance Criteria
- Lint, test and build remain green.
- Smoke and QA matrix pass for target screens.
- No P0/P1 responsive or overlay bugs remain open for first-wave screens.

## Sequence Recommendation
### First Week
- Complete Phase 1.
- Start Phase 2 shell and token work.

### First Two Weeks
- Finish Phase 2 and Phase 3.
- Deliver first wave of Phase 4 on recruiter-first screens.

### First Month
- Finish recruiter-first screens.
- Run Phase 5 mobile-first pass.
- Start Phase 6 on highest-risk admin screens.

## Implementation Notes For Codex App
- Prefer foundation changes in theme and shell before screen-by-screen styling.
- Use small logical commits:
  - `docs: redesign audit package`
  - `fix: mobile shell dialog semantics`
  - `refactor: shared page surfaces`
  - `feat: recruiter screen redesign foundation`
- Keep unrelated dirty changes untouched.
