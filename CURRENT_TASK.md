# Current Task

## Task Goal

Continue the first implementation wave in a disciplined way by reusing the live wave artifacts, confirming the current W1/W2 state, and completing the next narrow route-light adoption batch without expanding into shell work or broader route migrations.

## Active Scope

- W1 foundation layer
- W2 shell semantics only where already relevant to shared theme contracts
- Current session target: Batch I single-route explicit form grammar adoption for:
  - `frontend/app/src/app/routes/app/recruiter-new.tsx`

## Out Of Scope

- W3 shared primitive rollout beyond what is strictly required for the first batch
- W4 recruiter screen migrations except for passive regression checks
- W6 admin cleanup
- dormant routes `vacancies.tsx` and `reminder-ops.tsx`
- backend/API/business logic changes

## Canonical Docs Used

- `README.md`
- `AGENTS.md`
- `PROJECT_CONTEXT_INDEX.md`
- `CURRENT_PROGRAM_STATE.md`
- `REPOSITORY_WORKFLOW_GUIDE.md`
- `VERIFICATION_COMMANDS.md`
- `CODEX_FIRST_WAVE_RECOMMENDATION.md`
- `CODEX_EXECUTION_PLAN.md`
- `WAVE_START_GUARDRAILS.md`
- `PRE_IMPLEMENTATION_CHECKLIST.md`
- `COMPONENT_IMPLEMENTATION_SPECS.md`
- `SCREEN_IMPLEMENTATION_SPECS.md`

## Files To Inspect First

- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/material.css`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/components.css`
- `frontend/app/src/theme/mobile.css`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/__root.ui-mode.test.tsx`
- `frontend/app/tests/e2e/mobile-smoke.spec.ts`
- `frontend/app/tests/e2e/smoke.spec.ts`
- `frontend/app/src/app/routes/app/candidate-new.tsx`
- `frontend/app/src/app/routes/app/city-new.tsx`
- `frontend/app/src/app/routes/app/template-new.tsx`
- `frontend/app/src/app/routes/app/template-edit.tsx`
- `frontend/app/src/app/routes/app/question-new.tsx`
- `frontend/app/src/app/routes/app/question-edit.tsx`
- `frontend/app/src/app/routes/app/recruiter-new.tsx`

## Implementation Approach

- Confirm what W1/W2 behavior is already present in live code
- Avoid redoing already-landed shell/foundation work
- Make one narrow batch that improves the shared foundation or shell contract with minimal blast radius
- Verify immediately after the batch
- Record status for the next agent before considering a second batch

## Live Inspection Findings

- `__root.tsx` already keeps the More sheet out of the DOM until open and restores focus on close.
- Quiet vs ambient route mapping already exists and is wired through `showAmbientBackground`.
- Shared first-wave primitives already exist in partial form:
  - `.app-page`
  - `.app-page__hero`
  - `.app-page__section`
  - `.app-page__toolbar`
  - `.ui-form-shell`
  - `.ui-toolbar`
- The clearest remaining W1/W2 shared gap is incomplete z-index normalization:
  - `tokens.css` still lacks explicit `--z-fab`
  - `mobile.css` still uses hardcoded values for FAB, mobile header, tab bar, sheet, and candidate-detail mobile sticky layers
  - `pages.css` still carries a hardcoded app-header layer
- Current session will target the safest subset of that gap first: shared z-index tokenization and mobile layer normalization.
- Follow-up inspection for this session confirms the next safe shared gap is form/footer grammar, not shell logic:
  - `components.css` has `ui-form-shell`, `ui-form-header`, `ui-form-grid`, `ui-field`, and `ui-toolbar`, but no shared form section or footer grammar.
  - `pages.css` has generic section/header primitives, but no form-specific footer contract.
  - `candidate-new.tsx`, `city-new.tsx`, and `template-new.tsx` all end with direct-child `.action-row` blocks inside `.ui-form-shell`.
  - Nested token/tool rows in `template-new.tsx` stay inside `.ui-field`, so contextual selectors on `.ui-form-shell > .action-row` are safe and avoid route migrations.
  - Dirty worktree still affects the same shared theme files, so the batch must stay additive and avoid `global.css`, route TSX rewrites, or shell logic edits.
- Current follow-up inspection confirms the next safe shared-only gap is helper/status grammar around `.ui-field`:
  - `components.css` currently defines only `ui-field`, `ui-field__label`, `ui-field__hint`, and `ui-field__error`.
  - Existing form screens still mix several support-message patterns:
    - `template-new.tsx` uses `.subtitle` inside `.ui-field` and a nested `.action-row.ui-toolbar--between` for char-count/error status.
    - `city-new.tsx` uses `.ui-field__error` plus route-local status rows like `city-form__tz-status`.
    - `candidate-new.tsx` mostly relies on field groups and inline controls, with no explicit helper grammar yet.
  - The safest improvement is a scoped `components.css` batch that:
    - normalizes helper/support/error typography inside `.ui-field`
    - formalizes field status/meta rows for future adoption
    - improves mobile wrapping for field-level status rows
  - This is safer than shell follow-up or route migration because it stays in one shared CSS file and does not depend on markup rewrites.
- Current follow-up inspection confirms the next safe step after Batch E is a route-light form-only adoption batch:
  - `template-new.tsx` still relies on compatibility selectors for:
    - selected template description via `.subtitle`
    - char-count row via `.action-row.ui-toolbar--between`
    - footer actions via direct-child `.action-row`
  - `city-new.tsx` still relies on compatibility selectors for:
    - timezone status row via `.city-form__tz-status`
    - plan field errors rendered outside explicit support containers
    - footer actions via direct-child `.action-row`
  - `candidate-new.tsx` already has mostly stable form structure and only needs explicit footer/action adoption in this batch.
  - This batch is safe now because shared `.ui-form-actions`, `.ui-field__support`, and `.ui-field__status-row` contracts already exist in `components.css`, so route changes can stay markup-only and logic-free.
- Current follow-up inspection confirms `recruiter-new.tsx` is the next safest single-route batch after Batch H:
  - the route already has a stable recruiter-specific page grammar that should remain intact:
    - credentials banner
    - recruiter hero and aside summary
    - city selection grid
  - the safest explicit shared adoption points are limited and readable:
    - outer panel can adopt `.ui-form-shell`
    - bottom action row can adopt `.ui-form-actions.ui-form-actions--end`
    - route-level `formError` can adopt `ui-message ui-message--error`
    - field-level helper and validation text can adopt `.ui-field__support` + `.ui-field__note` without touching mutation/query logic
  - what must remain untouched in this batch:
    - `createdCredentials` banner behavior
    - city toggle and filtering logic
    - header save CTA behavior
    - any recruiter-edit companion route assumptions
  - this is safer than shell Batch C because it stays in one route file and uses already-proven explicit grammar from prior batches.

## Implementation Batches

### Batch A. Session Setup And Live State Confirmation

- Purpose: instantiate current run artifacts and verify live W1/W2 state
- Likely files: current task/session/verification docs, `WAVE_START_GUARDRAILS.md`, `PRE_IMPLEMENTATION_CHECKLIST.md`
- Risks: documentation drifts from live code
- Done means: current run docs exist and target files/regression zones are listed

### Batch B. Foundation Alignment

- Purpose: normalize the shared z-index contract for mobile shell and fixed action layers
- Likely files: `tokens.css`, `mobile.css`, optional small `pages.css` touch
- Risks: overlay stacking regressions on mobile
- Expected verification: lint, test, build:verify, `test:e2e:smoke`
- Done means: shared layer values stop depending on ad hoc literals where a canonical token already exists

### Batch C. Shell Semantics Follow-Up

- Purpose: only if still needed after live inspection, address a remaining W2 shell gap
- Likely files: `__root.tsx`, `mobile.css`, tests
- Risks: all-route regression
- Expected verification: lint, test, build:verify, `test:e2e:smoke`
- Done means: one shell issue is resolved and documented

### Batch D. Shared Form/Footer Grammar

- Purpose: normalize shared form sections and form footer/action grammar in the shared theme layer without touching route markup
- Likely files: `components.css`, optional very small `pages.css` touch only if required
- Risks: shared form spacing regressions across existing create/edit flows
- Expected verification: lint, typecheck, test, build:verify, `test:e2e:smoke`
- Done means: `.ui-form-shell` gets an explicit section/action contract, direct-child form action rows become consistent, and future shared classes exist for later migrations

### Batch E. Shared Form Helper/Status Grammar

- Purpose: normalize field-level helper text, inline support notes, validation/error messaging, and status rows in the shared theme layer without touching route markup
- Likely files: `components.css` only unless inspection proves a tiny adjacent shared touch is required
- Risks: field-level subtitle/message selectors could accidentally overreach if not scoped to `.ui-field`
- Expected verification: lint, typecheck, test, build:verify, `test:e2e:smoke`
- Done means: `.ui-field` gets explicit helper/status primitives, existing helper/message consumers inside fields become more consistent, and mobile wrapping remains stable

### Batch F. First Route-Light Form Adoption

- Purpose: replace compatibility-only form grammar usage with explicit shared classes in three in-scope form routes
- Likely files:
  - `frontend/app/src/app/routes/app/template-new.tsx`
  - `frontend/app/src/app/routes/app/city-new.tsx`
  - `frontend/app/src/app/routes/app/candidate-new.tsx`
- Risks: JSX cleanup could accidentally alter form layout or footer alignment if the batch grows beyond explicit class adoption
- Expected verification: lint, typecheck, test, build:verify, `test:e2e:smoke`, manual desktop/mobile review on all three routes
- Done means: the three routes explicitly use shared form classes where appropriate, no shell/business logic changes occur, and existing shared grammar behavior stays stable

### Batch I. Single-Route Recruiter Create Adoption

- Purpose: adopt proven shared create-form grammar in `recruiter-new.tsx` only
- Likely files:
  - `frontend/app/src/app/routes/app/recruiter-new.tsx`
- Risks:
  - recruiter-specific summary/banner layout could shift if the batch expands beyond wrapper/footer/support messaging
  - route-local credential banner action row must not be unintentionally restyled
- Expected verification:
  - lint, typecheck, test, build:verify, `test:e2e:smoke`
  - manual desktop/mobile review on `/app/recruiters/new`
- Done means:
  - the route explicitly adopts shared wrapper/footer/support/error grammar where appropriate
  - recruiter-specific logic and banner behavior remain intact
  - no shell/CSS redesign work is mixed in

## Success Criteria

### Full Success For This Session

- current run artifacts exist and are populated
- missing wave-start operational docs are created
- exact W1/W2 implementation area is inspected and documented
- at least one safe shared first-wave batch is implemented
- verification commands are run and recorded
- remaining work is explicit and resumable

### Partial Success

- current run artifacts exist and live inspection is complete
- batch plan and verification plan are recorded
- code changes are deferred because live inspection shows a larger conflict or risk

### Must Not Regress

- More sheet behavior on mobile
- quiet vs ambient shell behavior
- existing mounted route scope
- backend/API contracts
- dormant route exclusion

## Verification Plan

### Post-Batch Verification

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Manual Review Points

- quiet vs ambient route atmosphere
- mobile closed More sheet state
- mobile safe-area and tab-bar overlap
- shared surface contrast on changed primitives
- form create flows with `.ui-form-shell`:
  - `candidate-new`
  - `city-new`
  - `template-new`
- direct-child footer action alignment vs nested inline tool rows
- mobile stacked action row behavior for affected forms
- field-level helper/status alignment inside the same screens:
  - `.ui-field__error`
  - `.ui-field > .subtitle`
  - nested `.action-row.ui-toolbar--between` inside `.ui-field`
- no regression to Batch D footer behavior
- recruiter create flow:
  - `/app/recruiters/new`
  - recruiter-specific summary/banner behavior remains intact
  - footer/actions stay readable on mobile `375x812`
  - support/error rows do not collide with section copy or footer

## Risks

- dirty worktree across the same frontend files
- shared theme files affect many routes
- shell changes can cause silent overlay/focus regressions
- prior partial W1/W2 implementation may already exist and must not be overwritten blindly

## Rollback / Regression Watchpoints

- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/mobile.css`
- `frontend/app/src/theme/components.css`
- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/material.css`

## Iteration Plan

1. Finish Batch A and record findings
2. Inspect live W1/W2 code for unresolved gaps
3. Execute Batch B as z-index ladder normalization
4. Verify and log outcomes
5. Execute Batch D as shared form/footer grammar normalization
6. Verify and log outcomes
7. Execute Batch E as shared form helper/status grammar normalization
8. Verify and log outcomes
9. Execute Batch F as the first route-light adoption batch
10. Verify and log outcomes
11. Re-evaluate whether Batch C should stay deferred
12. Execute Batch G as a single-route follow-up on `template-edit.tsx`
13. Verify and log outcomes
14. Execute Batch H as a paired question-form follow-up
15. Verify and log outcomes

## Current Batch Status

- Batch A: completed
- Batch B: completed
- Batch D: completed
- Batch E: completed
- Batch F: completed
- Batch G: completed
- Batch H: completed
- Batch I: completed
- Batch C: deferred for a follow-up session

## Current Handoff Note

- Batch I is now complete in:
  - `frontend/app/src/app/routes/app/recruiter-new.tsx`
- explicit shared grammar adopted in the route:
  - `.ui-form-shell`
  - `.ui-field`
  - `.ui-field__support`
  - `.ui-field__note`
  - `.ui-form-actions`
  - `.ui-form-actions--end`
  - `ui-message ui-message--error`
- intentionally left untouched:
  - `createdCredentials` banner logic and CTA flow
  - city filtering/toggle logic
  - recruiter hero / summary layout logic
  - recruiter edit route
- next safest batch:
  - inspect `frontend/app/src/app/routes/app/recruiter-edit.tsx` as a single-route follow-up
  - keep shell Batch C deferred unless a smaller safer delta appears

## Revalidation Note

- A follow-up user request asked to execute the `recruiter-new.tsx` batch again.
- Fresh inspection confirmed the route already contains the intended Batch I adoption:
  - `.ui-form-shell`
  - `.ui-field`
  - `.ui-field__support`
  - `.ui-field__note`
  - `.ui-form-actions.ui-form-actions--end`
  - `ui-message ui-message--error`
- This run therefore stays verification-only:
  - no new app-code edits
  - no shell work
  - no business-logic changes
  - fresh lint/type/test/build/e2e/manual review evidence recorded in the live run artifacts

## Current Outcome

- First-wave execution has started in code, not just in docs
- Shared z-index normalization is now partially aligned to the canonical ladder:
  - `tokens.css` now defines `--z-fab`
  - `pages.css` uses `--z-app-header`
  - `mobile.css` uses canonical tokens for FAB, mobile header, mobile nav, and sheet layers
  - candidate-detail mobile sticky layers now derive from shared z tokens instead of isolated literals
- Current session target is narrowed to the next safe shared batch:
  - add explicit `.ui-form-section` and `.ui-form-actions` grammar in `components.css`
  - normalize direct-child `.action-row` inside `.ui-form-shell`
  - leave route markup and shell logic untouched
- Batch D is now complete:
  - `.ui-form-shell` now defines shared section/action spacing variables
  - direct-child `.action-row` inside `.ui-form-shell` now gets a consistent footer divider and alignment contract
  - new future-safe shared primitives now exist:
    - `.ui-form-section`
    - `.ui-form-section--compact`
    - `.ui-form-section__head`
    - `.ui-form-actions`
    - `.ui-form-actions--start`
    - `.ui-form-actions--end`
    - `.ui-form-actions--between`
    - `.ui-form-actions--sticky-mobile`
  - nested tool/action rows inside `.ui-field` remain untouched
- Full verification passed after Batch D:
  - lint: pass with 2 existing warnings
  - typecheck: pass
  - test: pass
  - build:verify: pass
  - test:e2e:smoke: pass
- Targeted manual review passed on:
  - `/app/candidates/new`
  - `/app/cities/new`
  - `/app/templates/new`
  - desktop and mobile `375x812`
- Current session is now narrowed to another shared-only batch:
  - helper/status grammar around `.ui-field` has now been added in `components.css`
  - existing field-level `.subtitle`, `.text-muted`, `.ui-message`, and `.ui-field__error` consumers now share scoped support/error typography
  - field status rows now have explicit shared primitives and mobile wrapping rules
- Batch E is now complete:
  - `.ui-field` now exposes shared support/error variables and future-safe primitives:
    - `.ui-field__support`
    - `.ui-field__note`
    - `.ui-field__status-row`
    - `.ui-field__status`
    - `.ui-field__status-item`
    - success / warning / error modifiers
  - existing field consumers were normalized without route TSX edits:
    - `.ui-field > .subtitle`
    - `.ui-field > .text-muted`
    - `.ui-field > .ui-message`
    - `.ui-field > .text-danger`
    - `.ui-field > .ui-message--error`
    - `.ui-field > .action-row.ui-toolbar--between`
  - mobile behavior now keeps status/meta rows stable:
    - `align-items: stretch` at `768px`
    - stacked `.ui-field__status-row` items at `480px`
- Full verification passed after Batch E:
  - lint: pass with 2 existing warnings
  - typecheck: pass
  - test: pass
  - build:verify: pass
  - test:e2e:smoke: pass
- Targeted manual review re-confirmed `/app/candidates/new`, `/app/cities/new`, and `/app/templates/new` on desktop and mobile `375x812`:
  - helper/support text now resolves to shared `12px` support typography inside `.ui-field`
  - `template-new` nested status row now keeps muted helper text and stacks cleanly on mobile
  - `city-new` validation error remains red, compact, and footer-safe on mobile
  - Batch D footer grammar remains intact across all three forms
- Next safe shared-only gap is smaller than shell follow-up:
  - first route-light adoption batch is now complete in exactly three forms:
    - `template-new.tsx`
    - `city-new.tsx`
    - `candidate-new.tsx`
  - explicit shared grammar now exists directly in route markup:
    - `.ui-form-actions`
    - `.ui-field__support`
    - `.ui-field__status-row`
  - Batch F kept scope discipline:
    - no shell work
    - no backlog routes
    - no business logic changes
- Batch F is now complete:
  - `template-new.tsx`
    - selected template description now uses `.ui-field__support` + `.ui-field__note`
    - char-count row now uses `.ui-field__status-row` + `.ui-field__status-item`
    - footer now uses `.ui-form-actions.ui-form-actions--between`
  - `city-new.tsx`
    - timezone status row now uses `.ui-field__status-row`
    - plan validation messages now use `.ui-field__support` wrappers
    - footer now uses `.ui-form-actions.ui-form-actions--end`
  - `candidate-new.tsx`
    - deferred interview note now uses `.ui-field__support` + `.ui-field__note`
    - footer now uses `.ui-form-actions.ui-form-actions--end`
- Full verification passed after Batch F:
  - lint: pass with 2 existing warnings
  - typecheck: pass
  - test: pass
  - build:verify: pass
  - test:e2e:smoke: pass
- Targeted manual review passed on desktop and mobile `375x812` for:
  - `/app/templates/new`
  - `/app/cities/new`
  - `/app/candidates/new`
  - support/helper rows render through explicit shared classes
  - status/error rows render through explicit shared classes
  - footers/actions still align and wrap correctly
- Remaining compatibility-based pieces are now narrower:
  - `template-new` token button row still uses route-local `action-row ui-toolbar ui-toolbar--compact`
  - `city-new` recruiter/help copy outside field containers remains route-local
  - `candidate-new` city timezone section note remains a route-local subtitle
- Playwright execution caveat remains active for this session:
  - if `test:e2e:smoke` fails inside the sandbox because the Playwright web server cannot bind to `127.0.0.1:18000`, rerun the same command outside the sandbox and record it explicitly
- Batch H is now complete in the question create/edit pair:
  - both routes now mount `.ui-form-shell`
  - stacked labels now use `.ui-field`
  - payload editor blocks now sit inside explicit field containers
  - footer rows now use `.ui-form-actions.ui-form-actions--between`
  - active toggles now use `.ui-inline-checkbox`
  - route-level form and detail errors now use shared `ui-message--error`
- Full verification passed after Batch H:
  - lint: pass with 2 existing warnings
  - typecheck: pass
  - test: pass
  - build:verify: pass
  - test:e2e:smoke: pass inside the sandbox, so no rerun workaround was needed for this batch
- Targeted manual review passed on desktop and mobile `375x812` for:
  - `/app/questions/new`
  - `/app/questions/1/edit`
  - payload hierarchy remains readable
  - `QuestionPayloadEditor` status stays stable at `12px`
  - footer wraps safely with shared divider spacing
- Next safest route-light batch should stay form-only and avoid shell work:
  - Batch I is now complete in `frontend/app/src/app/routes/app/recruiter-new.tsx`
  - explicit shared create-form grammar now covers:
    - wrapper via `.ui-form-shell`
    - active form labels via `.ui-field`
    - helper/validation copy via `.ui-field__support` and `.ui-field__note`
    - footer via `.ui-form-actions.ui-form-actions--end`
    - route-level errors via `ui-message--error`
  - recruiter-specific banner, hero, summary, and city-selection logic were intentionally left intact
- next exact follow-up should inspect `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- keep shell Batch C deferred unless a smaller safer delta appears

## Continuation — Light Theme Redesign

### Task Goal

Completely redesign and harden the light theme as a product-grade CRM interface layer: stronger contrast, clearer hierarchy, readable surfaces, visible actions, and calm premium depth without reopening shell architecture or business logic.

### Active Scope

- shared light-theme token layer
- shared light-theme surface and border system
- shared text hierarchy under light theme
- shared controls, inputs, badges, alerts, and table readability under light theme
- shared overlays/drawers/mobile nav surfaces under light theme
- representative validation on:
  - create form: `frontend/app/src/app/routes/app/recruiter-new.tsx`
  - edit form: `frontend/app/src/app/routes/app/template-edit.tsx`
  - list/table screen: `frontend/app/src/app/routes/app/candidates.tsx`
  - admin-like screen: `frontend/app/src/app/routes/app/system.tsx`
  - modal flow: `frontend/app/src/app/routes/app/slots.tsx`

### Out Of Scope

- business logic changes
- route map or shell architecture rewrites
- backlog-only routes
- dark-theme redesign
- broad route-level rewrites unrelated to light-theme readability
- component API rewrites

### Files To Inspect First

- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/material.css`
- `frontend/app/src/theme/components.css`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/mobile.css`
- `frontend/app/src/theme/global.css`
- `frontend/app/src/app/routes/app/recruiter-new.tsx`
- `frontend/app/src/app/routes/app/template-edit.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/system.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`

### Localized Audit Findings

- Current light theme is materially weaker than dark theme because the shared liquid-glass formulas remain dark-biased:
  - `:root[data-theme='light']` only overrides a subset of glass variables
  - `--glass-subtle`, `--glass-glow-subtle`, and related depth variables remain effectively dark-theme tuned
- `html[data-ui='liquid-glass-v2'][data-theme='light']` uses nearly white surfaces (`--ui-surface-0..4`) with weak borders and shallow shadows, so layered cards/panels/toolbars collapse into each other.
- Shared controls and data primitives still assume dark backdrops:
  - `.ui-btn--ghost`, `.chip`, `.status-badge`, `.data-card`, `.data-table`, `.form-group__input`, and `.modal-overlay` rely on white-alpha fills and faint borders
  - in light theme this produces low-action visibility and weak row/card separation
- Light mobile surfaces are especially soft:
  - `.mobile-header`, `.mobile-tab-bar`, and `.mobile-sheet` use translucent elevated backgrounds that do not separate strongly enough from page content
  - active nav affordance depends too much on color instead of structure/contrast
- What should be preserved:
  - dark theme direction
  - existing route structure
  - shared form grammar from previous batches
  - liquid-glass v2 motion and shell behavior unless light-theme contrast demands small shared style adjustments only

### Localized Light-Theme Batch Plan

#### Batch LT-A. Audit And Design Hypothesis

- confirm light-theme token failures and preserve-worthy strengths
- define the smallest shared-only implementation batch

#### Batch LT-B. Core Light Tokens

- redesign `:root[data-theme='light']` and `html[data-ui='liquid-glass-v2'][data-theme='light']`
- strengthen background ladder, border contrast, surface opacity, shadows, and glass depth tokens

#### Batch LT-C. Shared Surfaces And Hierarchy

- update shared material and page-shell surfaces for light theme
- improve page hero/section, nav pill, card, panel, and toolbar separation

#### Batch LT-D. Shared Controls And States

- harden buttons, inputs, labels, helper text, badges, alerts, and action visibility in light theme

#### Batch LT-E. Tables, Cards, And Overlays

- improve row delineation, card readability, overlay dimming, and modal/sheet separation in light theme

#### Batch LT-F. Mobile Light Normalization

- strengthen light mobile header/tab bar/sheet/FAB surfaces and active states

#### Batch LT-G. Hardening

- recheck affected screens, note remaining weak zones, and leave next exact shared batch

### Success Criteria

- light theme is materially redesigned, not cosmetically recolored
- interactive controls are immediately visible in light theme
- cards, tables, inputs, and overlays have clear separation in light theme
- mobile light theme remains readable and structurally clear
- no business logic, shell architecture, or backlog routes are touched
- verification stays green
- manual desktop and mobile review is recorded on representative screens

### Verification Plan

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Manual Review Points

- force light theme via `localStorage.setItem('theme', 'light')`
- desktop and mobile `375x812`
- review:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/system`
  - one modal/drawer interaction on `/app/slots` if data is available
- confirm:
  - layer separation is readable
  - actions are visible at first scan
  - table/list hierarchy is clearer
  - helper/error/status copy remains readable on pale surfaces
  - mobile header/tab bar/sheet do not wash out

### Risks

- shared theme blast radius is high because light-theme fixes affect many routes at once
- `global.css` still contains dark-biased generic component formulas; shared light overrides must be more specific and stay scoped
- mobile light theme can regress if header/tab bar contrast is strengthened without checking safe-area and overlay stacking

### Light-Theme Implementation Result

- One shared-only light-theme batch is complete:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/mobile.css`
- Implemented redesign areas:
  - rebuilt light token ladder for bg/surface/border/shadow/glass depth
  - hardened light liquid-glass surface hierarchy for `base / raised / floating / overlay`
  - strengthened page shell, nav pill, hero/section, and card separation in light theme
  - increased control visibility for inputs, ghost buttons, primary buttons, badges, alerts, tables, and overlays
  - strengthened mobile light header/tab-bar/sheet/card surfaces
- Scope discipline held:
  - no route TSX changes
  - no shell logic changes
  - no business logic changes
  - no backlog routes touched

### Light-Theme Manual Review Result

- Desktop reviewed:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
- Mobile `375x812` reviewed:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
  - mobile More sheet on `/app/candidates`
- Review findings:
  - create and edit forms now read as layered white-on-cool surfaces instead of washed-out translucent panels
  - primary actions are easier to spot against the new light surface ladder
  - table/list scanability improved through stronger header/background/border contrast
  - profile/settings-like cards and quick links remain readable in light mode
  - mobile header, tab bar, and More sheet now separate clearly from page content
- Manual-review caveat:
  - the isolated review harness returned backend-side `503` on a `system/detailization` path because of a pre-existing sqlite schema gap (`detailization_entries` missing), so `/app/profile` was used as the admin-like review screen for this run
  - `/app/slots` had no modal-capable slot rows in the seeded review DB, so the mobile More sheet served as the required drawer/sheet interaction check

## Current Light-Theme Follow-Up Batch

### Task Goal

Continue the active light-theme implementation with one shared-only hardening pass in `frontend/app/src/theme/global.css` to normalize legacy light-theme pockets that still conflict with the redesigned token and surface system.

### Active Scope

- `frontend/app/src/theme/global.css` only
- legacy light-theme hardening for:
  - dashboard hero surfaces
  - stat-card surfaces
  - slot-create tabs
  - toast / lightweight notification surfaces
  - old profile and recruiter-cabinet light blocks

### Out Of Scope

- route TSX edits
- shell or `__root.tsx` work
- business logic changes
- dark-theme redesign
- backlog-only routes
- broad cleanup outside the identified legacy light pockets

### Files To Inspect First

- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/material.css`
- `frontend/app/src/theme/components.css`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/mobile.css`
- `frontend/app/src/theme/global.css`
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/profile.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`
- `frontend/app/src/app/routes/app/slots-create.tsx`

### Localized Audit Findings

- `global.css` still contains legacy blocks that override or weaken the improved light-theme system shipped in the previous tranche.
- Clearly broken or conflicting in light theme:
  - `.toast` stays on a dark, nearly black base in all themes, so it looks detached from the new premium light overlay language.
  - `.stat-card` has a second legacy definition using `rgba(255, 255, 255, 0.02)`, which flattens KPI cards in light mode.
  - `.dashboard-hero--incoming` still leans on dark-oriented `var(--glass-gradient-strong)` and soft blue haze, making the hero weaker than nearby page sections in light mode.
  - `.slot-create-tabs` / `.slot-create-tab.is-active` still use white-alpha pills tuned for dark surfaces, so active state separation is weak in light mode.
- Visually weak but safe to normalize now:
  - `.profile-dropdown-menu` and related dropdown rows remain dark/charcoal even in light theme.
  - recruiter-cabinet light overrides (`.profile-cabinet .cabinet-glass`, `.cabinet-kpi-card`, `.cabinet-table`, avatar upload/delete chips) are still too pale and weakly bounded compared to the new light surface ladder.
- Preserve:
  - new light tokens in `tokens.css`
  - page-shell hierarchy in `pages.css`
  - control grammar from `components.css`
  - route structure and business logic

### Batch Goal

- harden only the remaining legacy light-theme pockets in `global.css`
- align them with the new token ladder, border logic, and surface hierarchy
- keep the batch shared-only and additive

### Success Criteria

- only `frontend/app/src/theme/global.css` is touched in app code
- no route TSX changes occur
- no shell work is mixed in
- dashboard/stat/profile/toast/slot-tab light surfaces become clearer and more readable
- legacy light-theme blocks stop visually undercutting the new light token/surface system
- lint, typecheck, test, build:verify, and e2e smoke remain green
- desktop/mobile light-theme manual review is completed and documented

### Verification Plan

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Manual Review Points

- force light theme with:
  - `localStorage.setItem('theme', 'light')`
  - `localStorage.setItem('ui:liquidGlassV2', '1')`
- desktop and mobile `375x812`
- review:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
  - More sheet interaction on `/app/candidates`
  - dashboard/stat surfaces if present
  - slot-create tabs if reachable
  - toast readability if easy to trigger

### Risks

- `global.css` is the largest blast-radius file in the frontend
- legacy selectors here often override newer shared styles because `global.css` comes after imported theme layers
- profile-specific light blocks are mixed between old and new grammar; this batch must harden them without reopening route-level cleanup

### Global.css Hardening Result

- One shared-only light-theme hardening batch is complete in:
  - `frontend/app/src/theme/global.css`
- Normalized legacy light-theme pockets:
  - `dashboard-hero` and `dashboard-hero--incoming`
  - `stat-card`
  - `slot-create-tabs` and `slot-create-tab`
  - `toast`
  - `profile-dropdown-menu` and dropdown rows
  - `profile-hero`, `profile-page .action-link`, and recruiter-cabinet legacy light blocks
  - `profile-avatar__upload` and `profile-avatar__delete`
- Implementation stayed within scope:
  - no route TSX changes
  - no shell/root changes
  - no business logic changes

### Global.css Manual Review Result

- Desktop reviewed in light theme:
  - `/app/dashboard`
  - `/app/slots/create`
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
- Mobile `375x812` reviewed in light theme:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
  - `/app/slots/create`
  - More sheet interaction on `/app/candidates`
- Review findings:
  - dashboard hero and KPI cards now read as distinct light surfaces instead of pale translucent blocks
  - slot-create tabs now have a clearly visible active state in light theme
  - recruiter create and template edit forms remained readable and stable after the shared hardening
  - candidates list/card hierarchy remained clear on desktop and mobile
  - profile/recruiter-cabinet blocks now have stronger borders, surface separation, and card depth in light theme
  - More sheet on mobile remained readable and separated from content after the global hardening pass
- Review caveats:
  - toast states were hardened in CSS, but a safe real-user trigger was not forced during this manual pass
  - isolated review harness login accepted `admin/admin`; the expected `playwright_admin` pair was not valid for that harness, so this is recorded as an environment caveat rather than a regression from the CSS batch

## Continuation — Light Theme Nav/Profile Legacy Hardening

### Task Goal

Finish the remaining legacy light-theme pockets near the top of `frontend/app/src/theme/global.css` that still conflict with the redesigned shared light-theme system.

### Active Scope

- `frontend/app/src/theme/global.css` only
- legacy light selectors for:
  - `.app-nav`
  - `.app-nav__item`
  - `.app-profile`
  - `.app-profile-pill`
  - `.profile-dropdown-menu` and related dropdown rows
- explicit validation targets for this run:
  - opened profile dropdown state in light theme if a live dropdown is discoverable
  - one real toast state in light theme

### Out Of Scope

- route TSX changes
- shell/root architecture changes
- business logic changes
- backlog-only routes
- dark-theme redesign
- broad CSS cleanup beyond the targeted nav/profile legacy selectors

### Audit Findings

- `global.css` still starts with pre-redesign light overrides that are weaker than the new token/surface system:
  - `.app-nav` still uses a pale `rgba(255,255,255,0.5)` glass fill with weak boundary contrast
  - `.app-nav__item:not(.is-active)` still drops to `opacity: 0.5`
  - `.app-nav__item.is-active` still relies on `color: #fff` without an explicit light-surface active treatment
  - `.app-profile` still uses a dark-biased gradient and shadow recipe
  - `.app-profile-pill` still keeps low-opacity pale styling that undercuts the stronger light shell
  - `.profile-dropdown-menu` base block is still dark/charcoal by default; only a later light override partly hardens it
- mounted SPA reality checked in `__root.tsx`:
  - the current shell uses `vision-nav-pill` and `vision-nav__item` for desktop nav
  - the current shell uses `app-profile-pill` as a link to `/app/profile`
  - no live React-rendered profile dropdown component is mounted right now, so runtime opened-dropdown validation may be blocked without going out of scope
- safe batch boundary:
  - harden the remaining legacy nav/profile light selectors in `global.css`
  - keep route files and shell logic untouched

### Localized Success Criteria

- only `frontend/app/src/theme/global.css` changes in app code unless a tiny shared exception is strictly required and documented
- remaining nav/profile legacy light selectors align visually with the new light token and surface hierarchy
- profile pill readability and hover affordance improve in light theme
- legacy nav/profile selectors stop using obviously washed-out or dark-biased formulas
- no route TSX changes occur
- no shell work or business logic changes occur
- lint, typecheck, test, build:verify, and `test:e2e:smoke` remain green
- desktop/mobile light-theme manual review is recorded again
- one real toast is validated in context
- opened profile dropdown validation is either completed with evidence or explicitly documented as blocked by absent runtime component

### Verification Plan

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Manual Review Points

- force light theme with:
  - `localStorage.setItem('theme', 'light')`
  - `localStorage.setItem('ui:liquidGlassV2', '1')`
- desktop and mobile `375x812`
- review:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - More sheet interaction on `/app/candidates` for chrome comparison
- explicit validation:
  - open the visible profile surface and confirm current `app-profile-pill` readability
  - try to validate an opened profile dropdown state; if none exists in the mounted shell, record that limitation instead of pretending
  - trigger one real toast in context, preferably on `/app/slots/create`

### Risks

- `global.css` remains the highest blast-radius frontend stylesheet
- the target selectors are partly legacy and partly dormant, so changes must not destabilize the current `vision-nav` shell
- the current shell does not appear to render a live dropdown, which may block full runtime validation of opened dropdown state in this batch

### Implementation Result

- Shared-only `global.css` hardening batch completed for the remaining nav/profile legacy light selectors.
- Normalized in this batch:
  - `.app-nav`
  - `.app-nav__item`
  - `.app-nav__icon`
  - `.app-profile`
  - `.app-profile-pill`
  - `.app-profile__icon`
  - `.profile-dropdown-menu`
  - `.profile-dropdown-header`
  - `.profile-dropdown-item`
- Scope discipline held:
  - no route TSX edits
  - no shell/root changes
  - no business logic changes
  - no dark-theme changes

### Manual Review Result

- Review harness:
  - isolated local server on `127.0.0.1:18005`
  - light theme forced with:
    - `localStorage.setItem('theme', 'light')`
    - `localStorage.setItem('ui:liquidGlassV2', '1')`
- Login caveat for this harness:
  - `playwright_admin` / `playwright_admin_password` worked
  - `admin` / `admin` failed on the SPA login form
- Desktop reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - `/app/copilot` for a real toast state
- Mobile `375x812` reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - More sheet interaction on `/app/candidates`
- Findings:
  - dashboard and KPI surfaces now read as clearer light layers against the header chrome
  - the visible desktop profile pill now has stronger boundary contrast and no washed-out opacity
  - profile/settings surfaces remain readable after the nav/profile hardening pass
  - recruiter create and slots create kept clear field boundaries in light mode on desktop and mobile
  - More sheet remains readable and properly separated from background content on mobile
  - real toast validated in context on `/app/copilot` via document enable flow (`Документ включён`)
  - mounted SPA shell still does not render a live `profile-dropdown-menu`; only the profile pill link is live today
  - opened dropdown styling was therefore validated through an in-context DOM harness attached under the live profile pill, not through a shipped runtime dropdown component

## Final Light-Theme Global.css Cleanup Batch

### Task Goal

Finish the last safe shared-only cleanup pass in `frontend/app/src/theme/global.css` by removing or merging residual legacy light-theme selectors that are now duplicated, effectively dead, or slightly misaligned with the redesigned light-theme system.

### Active Scope

- `frontend/app/src/theme/global.css` only
- residual light-theme cleanup for:
  - top-of-file legacy `.app-nav` / `.app-nav__item` / `.app-profile` light overrides
  - duplicated `profile-dropdown-menu` light overrides inside later hardening blocks
  - any adjacent nav/profile legacy light formulas that can be safely removed or merged without changing runtime shell behavior

### Out Of Scope

- route TSX changes
- shell/root architecture work
- business logic changes
- dark-theme redesign
- new shared theme redesign
- product changes to expose a real runtime profile dropdown

### Audit Findings

- `global.css` still carries two kinds of residual nav/profile light debt:
  - early top-of-file light overrides for `.app-nav`, `.app-nav__item`, and `.app-profile` that predate the hardened system
  - duplicated later light overrides for `.profile-dropdown-menu` and related rows
- runtime reality checked again:
  - mounted SPA desktop nav uses `vision-nav-pill` / `vision-nav__item`
  - mounted SPA live profile surface is `.app-profile-pill`
  - `.app-nav`, `.app-profile`, and `.profile-dropdown-menu` are currently legacy/fallback selectors, not active shell UI
- safest cleanup boundary:
  - remove top duplicated light overrides that no longer meaningfully govern active UI
  - keep a single hardened legacy fallback block near the end of `global.css` for dormant compatibility
  - do not touch route markup, shell code, or token/component/page files

### Localized Success Criteria

- only `frontend/app/src/theme/global.css` is touched in app code
- residual legacy light-theme debt is measurably reduced through removal/merge of duplicated or dead selectors
- no regressions are introduced to the already-hardened light theme
- no route TSX changes, shell work, or business logic changes occur
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` remain green
- desktop/mobile light-theme manual review is recorded again
- final handoff explicitly states whether theme-only cleanup is effectively complete

### Verification Plan

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Manual Review Points

- force light theme with:
  - `localStorage.setItem('theme', 'light')`
  - `localStorage.setItem('ui:liquidGlassV2', '1')`
- desktop and mobile `375x812`
- review:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - More sheet on `/app/candidates`
- compare:
  - nav/profile readability
  - active/current state clarity
  - profile pill boundary and hover state
  - card/list clarity and mobile chrome stability after selector cleanup

### Risks

- `global.css` remains the highest blast-radius stylesheet in the frontend
- some legacy selectors are dormant rather than fully deleted from history, so cleanup must be based on live-code evidence, not guesswork
- runtime opened profile dropdown is still absent from the mounted shell; this pass must not claim to solve that product/runtime limitation

### Implementation Result

- Final narrow `global.css` cleanup batch completed.
- Reduced residual light-theme debt by:
  - removing the duplicated top-of-file light overrides for:
    - `.app-nav`
    - `.app-nav__item`
    - `.app-profile`
  - removing the duplicated mid-file light override block for:
    - `.profile-dropdown-menu`
    - `.profile-dropdown-header`
    - `.profile-dropdown-item`
  - keeping one explicit hardened legacy fallback block near the end of `global.css`
  - simplifying redundant declarations inside the surviving legacy fallback block
- Scope discipline held:
  - no route TSX edits
  - no shell/root changes
  - no business logic changes
  - no other theme files touched

### Manual Review Result

- Review harness:
  - isolated local server on `127.0.0.1:18006`
  - effective login on this harness: `playwright_admin` / `playwright_admin_password`
  - light theme forced with:
    - `localStorage.setItem('theme', 'light')`
    - `localStorage.setItem('ui:liquidGlassV2', '1')`
- Desktop reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
- Mobile `375x812` reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - More sheet on `/app/candidates`
- Findings:
  - dashboard active nav and profile pill stayed clearly bounded after selector cleanup
  - candidates list/table header remained readable and stable
  - profile/settings action cards remained well-separated in light mode
  - recruiter create and slots create surfaces kept strong form/tab hierarchy
  - mobile header, tab bar, active tab, and More sheet remained readable and visually stable
  - no visual regression appeared from removing the duplicated legacy selectors

## Recruiter Edit Route-Light Batch

### Task Goal

Adopt the existing shared form grammar in `frontend/app/src/app/routes/app/recruiter-edit.tsx` with minimal markup changes and without touching edit-specific business behavior.

### Active Scope

- `frontend/app/src/app/routes/app/recruiter-edit.tsx` only
- form-only adoption of:
  - `.ui-form-shell`
  - `.ui-field`
  - `.ui-field__support`
  - `.ui-field__note`
  - `.ui-form-actions`
  - `.ui-form-actions--between`
  - `ui-message ui-message--error`

### Out Of Scope

- summary/load cards redesign
- reset-password banner logic changes
- delete flow changes
- shell/root work
- backlog-only routes
- CSS redesign
- business logic changes

### Audit Findings

- `recruiter-edit.tsx` is the next safest single-route batch because it already mirrors the create-flow structure and can reuse the same shared grammar patterns.
- Current mixed-grammar points:
  - outer edit panel still lacks `.ui-form-shell`
  - field wrappers in “Основные данные” and “Контакты” use route-local `.recruiter-edit__field` only
  - helper/error copy still uses `.subtitle`, `.field-error`, and route-local spacing
  - reset-password controls and bottom footer still use plain `.action-row`
  - `formError` currently renders through `ApiErrorBanner`, which is fine functionally but not aligned with the explicit shared form grammar
- Must remain untouched in this batch:
  - aside summary/load cards
  - reset-password mutation logic and credentials banner behavior
  - delete mutation flow
  - detail loading and `ApiErrorBanner` for load/delete states

### Localized Success Criteria

- only `frontend/app/src/app/routes/app/recruiter-edit.tsx` changes in app code
- batch remains form-only
- explicit shared grammar is adopted where appropriate
- no shell work
- no business logic changes
- no summary/load card redesign
- no reset-password banner logic changes
- no delete flow changes
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` remain green
- desktop/mobile manual review is recorded for the recruiter edit route

### Verification Plan

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Manual Review Points

- desktop and mobile `375x812`
- review the mounted recruiter edit route
- confirm:
  - form wrapper and sections read clearly
  - helper/support/error rows render through shared grammar
  - reset-password block remains intact
  - delete flow remains intact
  - footer/actions align correctly
  - mobile stacking remains stable

### Risks

- `recruiter-edit.tsx` combines form content with summary/load, reset-password, and delete zones, so the batch must stay tightly limited to wrapper/field/footer/message grammar
- dirty worktree remains large
- route currently mixes inline styles inside service/support areas; only the subset required for explicit grammar adoption should be touched

### Implementation Result

- Completed a single-route, form-only adoption batch in `frontend/app/src/app/routes/app/recruiter-edit.tsx`.
- Explicit shared grammar now mounts in the edit route for:
  - outer panel via `.ui-form-shell`
  - field wrappers via `.ui-field`
  - helper/support copy via `.ui-field__support` / `.ui-field__note`
  - inline validation via `ui-message ui-message--error`
  - reset-password controls via `.ui-form-actions`
  - bottom footer via `.ui-form-actions.ui-form-actions--between`
- Intentionally left untouched:
  - summary/load cards
  - reset-password mutation logic and credentials behavior
  - delete mutation logic
  - load/delete `ApiErrorBanner` handling

### Verification Result

- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` all passed after the route patch.
- Desktop and mobile `375x812` manual review completed on `/app/recruiters/2/edit` using an isolated sqlite review harness on `127.0.0.1:18007`.

### Manual Review Notes

- Desktop confirmed:
  - inline validation renders `Укажите имя` through the shared error grammar
  - reset-password flow still works and repopulates the password field while enabling the copy CTA
  - delete CTA still opens the destructive confirmation prompt and the recruiter remains present after dismiss
  - summary/load cards remained visually and functionally unchanged
- Mobile `375x812` confirmed:
  - wrapper, fields, and aside sections stack cleanly
  - footer actions stay visible above mobile navigation
  - helper/error copy does not collide with actions or cards

### Exact Next Step

- Next safest batch should stay route-light and form-only:
  - `frontend/app/src/app/routes/app/city-edit.tsx`
- Scope:
  - adopt the same shared wrapper/support/footer grammar
  - leave city-specific summary and any destructive/edit-only flows untouched
