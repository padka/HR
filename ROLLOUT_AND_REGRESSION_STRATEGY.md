# ROLLOUT_AND_REGRESSION_STRATEGY

## Purpose
- Define how implementation should be validated and rolled out wave by wave.
- Prevent W(N+1) from compounding unresolved W(N) defects.

## Rollout Model
- One wave at a time.
- Each wave lands on its own `codex/` branch or branch segment.
- No merge of W(N+1) until W(N) has no unresolved P0 issues.
- Prefer small logical commits inside each wave.

## Validation Tiers
### Tier 1. Automated
- Run on every meaningful commit:
  - `cd frontend/app && npm run lint`
  - `cd frontend/app && npm run test`
  - `cd frontend/app && npm run build:verify`
- Goal:
  - catch syntax, unit and bundle regressions immediately

### Tier 2. Smoke
- Run after W2, W4 and W5.
- Target:
  - shell
  - incoming
  - slots
  - candidates
  - candidate detail
  - messenger
  - calendar
  - selected admin hotspots
- Goal:
  - catch flow regressions in high-risk routes

### Tier 3. Full QA
- Run after W4, W5 and W7.
- Source checklist:
  - `DESIGN_QA_CHECKLIST.md`
- Goal:
  - close responsive, accessibility and visual regressions before next major wave

## Regression Risk Register
### W1 Risks
- Token changes can alter contrast or spacing globally.
- Surface ladder changes can affect all glass panels.
- Mitigation:
  - small commits
  - visual spot-check on dashboard, incoming, profile

### W2 Risks
- Shell changes can break every route.
- More sheet changes can break focus or mobile navigation.
- Quiet/ambient mapping can visually regress overview routes.
- Mitigation:
  - shell-first smoke
  - keyboard-only pass
  - screenshot comparison on login/dashboard/incoming

### W3 Risks
- Shared primitives can overfit or underfit real routes.
- Filter and overlay primitives can introduce unintended behavior changes.
- Mitigation:
  - migrate one route exemplar first
  - avoid mass route edits in the same commit

### W4 Risks
- First-wave screens can regress live workflows.
- Candidate detail changes can break complex actions.
- Table/card parity gaps can hide actions on mobile.
- Mitigation:
  - route-by-route smoke
  - parity checklist
  - candidate detail only after slots/candidates settle

### W5 Risks
- Mobile-specific fixes can fork logic from desktop behavior.
- Sticky and keyboard-safe changes can create overlap bugs.
- Mitigation:
  - mobile smoke at 390/375/320
  - manual short-height checks
  - explicit parity review

### W6 Risks
- High inline-style extraction creates large visual diffs.
- Admin screens may regress lower-frequency workflows that lack broad coverage.
- Mitigation:
  - file-by-file extraction
  - category-based inline migration
  - admin manual QA subset each time

### W7 Risks
- Polish work can reopen solved defects.
- New smoke tests can be brittle if hooks are unstable.
- Mitigation:
  - only polish against already stable primitives
  - stabilize selectors before heavy smoke expansion

## High-Risk Zones
- Z-index and overlay collisions:
  - More sheet
  - mobile header
  - tab bar
  - FAB
  - toasts
  - route modals
- Mobile breakage:
  - safe-area padding
  - keyboard overlap
  - sticky action bars
  - table/card parity loss
- Filter and list flows:
  - advanced filters
  - multi-view candidates
  - slots bulk actions
- Motion and performance:
  - ambient background
  - blur-heavy surfaces
  - overlay motion on dense screens
- Inline-style extraction:
  - city-edit
  - system
  - test-builder-graph
  - detailization

## Rollback Protocol
- Branching:
  - `codex/w1-foundation`
  - `codex/w2-shell`
  - `codex/w3-primitives`
  - `codex/w4-recruiter`
  - `codex/w5-mobile`
  - `codex/w6-admin`
  - `codex/w7-polish`
- Rule:
  - never merge W(N+1) if W(N) still contains unresolved P0 issues
- Rollback:
  - revert the last logical commit set for the active wave
  - do not mix rollback with forward fixes in the same commit

## Mobile Regression Checklist
- More sheet:
  - closed state not interactive
  - open state focus and backdrop correct
- Tab bar:
  - does not cover critical actions
- Mobile header:
  - correct back behavior and title truncation
- FAB:
  - no collision with tab bar, sheet or keyboard
- Keyboard:
  - composer and form submit actions stay reachable
- Safe-area:
  - bottom padding correct with inset
- Card parity:
  - slots and candidates keep critical actions in mobile mode

## Performance Regression Checklist
- No new ambient animation on quiet operational routes.
- Backdrop-filter use stays bounded to shell and intended surfaces.
- Route-level code splitting remains intact.
- Candidate detail and calendar do not gain new heavy always-on effects.
- Overlay motion remains short and GPU-friendly.

## Accessibility Regression Checklist
- Focus rings visible on buttons, links, tabs, inputs and icon-only controls.
- Shell landmarks remain explicit after every shell change.
- More sheet and modals leave the tree when closed.
- Status is still understandable without color only.
- Touch targets remain at or above 44px for mobile controls.
- Reduced-motion still disables decorative motion.

## Manual QA Subset By Wave
### W1
- dashboard visual pass
- incoming visual pass
- profile form pass

### W2
- mobile shell open/close pass
- login/dashboard/incoming quiet-vs-ambient comparison
- keyboard-only shell pass

### W3
- hero/section/toolbar examples on first-wave screens
- overlay open/close behavior
- filter reveal behavior

### W4
- incoming full flow
- slots list and bulk actions
- candidates view switching
- candidate detail top-level flow
- messenger thread/send/task flow
- calendar create/edit flow

### W5
- 390/375/320 passes for first-wave screens
- keyboard and safe-area checks
- card/table parity review

### W6
- city-edit save flow
- system tabs/logs/policies
- template/question create/edit
- test-builder list and graph modes

### W7
- full subset from `DESIGN_QA_CHECKLIST.md`
- responsive matrix
- reduced-motion
- a11y sanity

## Minimum Wave Exit Criteria
- W1:
  - shared tokens and page/surface contracts stable
- W2:
  - shell P0 issue closed
- W3:
  - shared primitives ready for route adoption
- W4:
  - first-wave recruiter screens stable on desktop/mobile
- W5:
  - mobile-first regressions burned down
- W6:
  - admin debt materially reduced on top hotspots
- W7:
  - no unresolved P0/P1 issues in first-wave screens and shell
