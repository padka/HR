# TASK_GRAPH_FOR_CODEX

## Purpose
- This file decomposes epics into atomic implementation tasks.
- Every task references one epic from `EPIC_BREAKDOWN_FOR_CODEX.md`.
- Task IDs are stable and should be used in commit descriptions, PR notes and QA logs.

## Task Format
- Each task includes:
  - epic reference
  - description and why it matters
  - target files
  - change type: `ADD`, `MODIFY`, `EXTRACT`, `DELETE`
  - definition of done
  - regression risk
  - verification method
  - commit message template

## W1 Tasks
### T-W1.1-01
- Epic: `W1.1` | Type: `MODIFY` | Files: `frontend/app/src/theme/tokens.css`
- Do: inventory current token groups and add missing aliases such as `--z-fab`; Why: foundation work must reference canonical tokens instead of literal values.
- Done: token file exposes a complete ladder for spacing, surface and z-index needs used by shell and first-wave screens.
- Risk: token alias collisions or dead vars.
- Verify: `npm run lint && npm run test && npm run build:verify` | Commit: `refactor: normalize redesign foundation tokens`

### T-W1.1-02
- Epic: `W1.1` | Type: `MODIFY` | Files: `frontend/app/src/theme/tokens.css`
- Do: align motion, blur and contrast token naming with quiet-vs-ambient usage; Why: later waves need stable references for motion and surface tuning.
- Done: tokens expose explicit motion durations and surface-related values used by pages and shell.
- Risk: visual drift across existing liquid-glass styles.
- Verify: build plus visual spot-check on dashboard and incoming | Commit: `refactor: align motion and surface token naming`

### T-W1.1-03
- Epic: `W1.1` | Type: `MODIFY` | Files: `frontend/app/src/theme/tokens.css`, `frontend/app/src/theme/pages.css`
- Do: document or encode quiet/ambient hooks in token usage; Why: route atmosphere must stop being implicit.
- Done: quiet and ambient modes can be implemented without route-local magic numbers.
- Risk: ambient screens lose intended depth.
- Verify: quiet/ambient route smoke after implementation | Commit: `refactor: add quiet ambient token hooks`

### T-W1.2-01
- Epic: `W1.2` | Type: `MODIFY` | Files: `frontend/app/src/theme/material.css`
- Do: map `ui-surface--base`, `--raised`, `--floating`, `--overlay` to canonical visual rules; Why: surface ladder needs to be explicit before screen migration.
- Done: material layer expresses one reusable hierarchy.
- Risk: route screens relying on legacy `.glass` overrides change unexpectedly.
- Verify: build plus spot-check sections on dashboard and messenger | Commit: `refactor: formalize surface ladder classes`

### T-W1.2-02
- Epic: `W1.2` | Type: `MODIFY` | Files: `frontend/app/src/theme/pages.css`, `frontend/app/src/theme/material.css`
- Do: align quiet-shell surface treatment with the material ladder; Why: operational screens need calmer surfaces than ambient routes.
- Done: quiet shell surfaces render consistently across hero, section and utility surfaces.
- Risk: low contrast on dark theme.
- Verify: visual spot-check on incoming, slots and system | Commit: `refactor: align quiet shell surface treatment`

### T-W1.2-03
- Epic: `W1.2` | Type: `DELETE` | Files: route-local surface overrides as encountered in Wave 4/6 routes
- Do: remove redundant local surface styling only after shared ladder is ready; Why: prevent duplicate hierarchy logic.
- Done: shared ladder replaces redundant local border/shadow/background rules.
- Risk: missing fallback styles on legacy routes.
- Verify: route-specific smoke during migrations | Commit: `refactor: remove redundant local surface overrides`

### T-W1.3-01
- Epic: `W1.3` | Type: `MODIFY` | Files: `frontend/app/src/theme/pages.css`
- Do: formalize `.app-page`, `.app-page__hero`, `.app-page__section`, `.app-page__section-head`; Why: shared page shell must precede route migrations.
- Done: page shell contract is documented by CSS and supports overview/ops/admin variants.
- Risk: regressions on routes already using `app-page`.
- Verify: build plus smoke on dashboard/incoming | Commit: `refactor: formalize page shell primitives`

### T-W1.3-02
- Epic: `W1.3` | Type: `MODIFY` | Files: `frontend/app/src/theme/pages.css`, `frontend/app/src/theme/components.css`
- Do: define shared toolbar spacing and section-body rhythm under page shell; Why: prevent every route from inventing its own gap system.
- Done: hero, section and toolbar spacing rely on shared tokens.
- Risk: overly generic spacing compresses admin forms too much.
- Verify: visual pass on dashboard, profile and city-new | Commit: `refactor: unify page and toolbar rhythm`

### T-W1.3-03
- Epic: `W1.3` | Type: `DELETE` | Files: targeted duplicates in `frontend/app/src/theme/global.css`
- Do: remove or neutralize duplicate page-header/page-section definitions that conflict with the new page shell; Why: legacy duplicates cause drift.
- Done: new page shell rules are not being overridden by older repeated blocks.
- Risk: hidden dependencies in low-traffic pages.
- Verify: build plus smoke on dashboard, candidates, city-edit | Commit: `refactor: trim conflicting page shell legacy rules`

### T-W1.4-01
- Epic: `W1.4` | Type: `MODIFY` | Files: `frontend/app/src/theme/components.css`
- Do: stabilize `.ui-form-shell`, `.ui-form-grid`, `.ui-field` and related labels/errors/hints; Why: admin form grammar must become concrete.
- Done: shared form grammar supports simple, dense and long forms.
- Risk: field spacing regressions on existing forms.
- Verify: build plus manual pass on recruiter-new and template-edit | Commit: `refactor: formalize admin form grammar`

### T-W1.4-02
- Epic: `W1.4` | Type: `ADD` | Files: `frontend/app/src/theme/components.css`, `frontend/app/src/theme/mobile.css`
- Do: add shared save/cancel footer grammar with optional sticky mobile behavior; Why: long forms need predictable action placement.
- Done: footer pattern exists and can be reused without inline positioning.
- Risk: sticky footer overlaps page content or keyboard.
- Verify: mobile pass on city-edit and recruiter-edit later | Commit: `feat: add shared form action footer grammar`

### T-W1.4-03
- Epic: `W1.4` | Type: `DELETE` | Files: route-local form layout helpers during Wave 6
- Do: remove duplicated local form wrappers as routes migrate; Why: avoid dual grammar.
- Done: migrated screens rely on shared grammar, not local grid wrappers.
- Risk: form sections lose intended emphasis.
- Verify: per-route regression during Wave 6 | Commit: `refactor: remove route local form wrappers`

### T-W1.5-01
- Epic: `W1.5` | Type: `MODIFY` | Files: `frontend/app/src/theme/components.css`
- Do: extend `ui-state` patterns for loading, empty, error and success; Why: first-wave screens need predictable state blocks.
- Done: shared state blocks are reusable for list, form and detail screens.
- Risk: state visuals become too generic.
- Verify: error/loading states on dashboard and messenger | Commit: `refactor: expand shared state block variants`

### T-W1.5-02
- Epic: `W1.5` | Type: `ADD` | Files: `frontend/app/src/theme/components.css`
- Do: add skeleton conventions for hero, card, table and form loading; Why: many screens load via React Query and need consistent placeholders.
- Done: skeleton utilities exist for first-wave screens.
- Risk: skeleton styles become visually noisy.
- Verify: build and spot-check skeleton classes in Story-like route contexts | Commit: `feat: add shared skeleton primitives`

### T-W1.5-03
- Epic: `W1.5` | Type: `DELETE` | Files: `frontend/app/src/theme/global.css`, route files during migration
- Do: phase out duplicated empty-state and ad hoc loading treatments; Why: duplicated states increase inconsistency.
- Done: migrated screens stop depending on bespoke empty-state blocks where shared patterns fit.
- Risk: some state-specific copy/layout still needs local handling.
- Verify: screen state regression during W4/W6 | Commit: `refactor: retire duplicated state treatments`

## W2 Tasks
### T-W2.1-01
- Epic: `W2.1` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/__root.tsx`
- Do: render More sheet only when open and remove closed-state dialog semantics; Why: current mobile sheet is a P0 semantic issue.
- Done: closed More sheet leaves no active dialog node or interactive backdrop in DOM flow.
- Risk: open/close animation or focus return breaks.
- Verify: mobile shell smoke, keyboard open/close pass | Commit: `fix: remove closed more sheet from active dom`

### T-W2.1-02
- Epic: `W2.1` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/__root.tsx`, `frontend/app/src/theme/mobile.css`
- Do: normalize More sheet backdrop, body, close button and focus return behavior; Why: navigation overlay needs predictable semantics and motion.
- Done: open More sheet traps attention correctly and returns focus to trigger on close.
- Risk: body scroll lock or inert handling regressions.
- Verify: mobile smoke with keyboard and touch | Commit: `fix: normalize more sheet focus and backdrop behavior`

### T-W2.1-03
- Epic: `W2.1` | Type: `MODIFY` | Files: tests touching shell behavior
- Do: extend shell tests to assert closed/open More sheet behavior; Why: the shell bug must be protected from regressions.
- Done: automated checks fail if closed More sheet becomes interactive again.
- Risk: brittle selectors or timing-sensitive tests.
- Verify: `npm run test` and smoke suite | Commit: `test: cover mobile more sheet semantics`

### T-W2.2-01
- Epic: `W2.2` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/__root.tsx`
- Do: encode quiet-vs-ambient route mapping exactly as defined in `DESIGN_DECISIONS_LOG.md`; Why: atmosphere must be deterministic.
- Done: only `/app`, `/app/login`, `/app/dashboard` receive ambient mode by default.
- Risk: future routes forget to declare mode.
- Verify: route smoke on login, dashboard, incoming | Commit: `refactor: apply quiet ambient route mapping`

### T-W2.2-02
- Epic: `W2.2` | Type: `MODIFY` | Files: `frontend/app/src/theme/pages.css`
- Do: tune quiet-shell surfaces and ambient-shell surfaces to differ clearly but remain related; Why: shell mode should be visible without separate component systems.
- Done: quiet routes are calmer and more legible than ambient routes.
- Risk: ambient mode becomes too subtle or too strong.
- Verify: screenshot comparison across mapped routes | Commit: `refactor: tune quiet and ambient shell surfaces`

### T-W2.2-03
- Epic: `W2.2` | Type: `DELETE` | Files: `frontend/app/src/app/routes/__root.tsx`, `frontend/app/src/theme/global.css`
- Do: remove assumptions that ambient background is default for all app routes; Why: data-heavy screens must not inherit decorative motion/noise automatically.
- Done: ambient behavior is opt-in only.
- Risk: hidden route-specific dependencies on background scene.
- Verify: dashboard retains ambience, incoming does not | Commit: `refactor: remove ambient background default behavior`

### T-W2.3-01
- Epic: `W2.3` | Type: `MODIFY` | Files: `frontend/app/src/theme/tokens.css`, `frontend/app/src/theme/mobile.css`
- Do: codify `--z-fab` and align tab/header/sheet/FAB/toast usage to tokens; Why: z-index drift must be stopped early.
- Done: shell layering values reference tokens instead of literals wherever feasible.
- Risk: existing literal values remain and cause mixed ladders.
- Verify: build and shell overlap pass | Commit: `refactor: normalize shell z index ladder`

### T-W2.3-02
- Epic: `W2.3` | Type: `MODIFY` | Files: `frontend/app/src/theme/mobile.css`
- Do: align safe-area padding, main bottom padding and floating controls with the canonical shell ladder; Why: later waves depend on stable mobile spacing.
- Done: shell spacing for tab bar, header and overlays is centralized.
- Risk: page content gains extra dead space or clips under shell.
- Verify: 390/375/320 viewport pass | Commit: `refactor: normalize mobile shell spacing and safe areas`

### T-W2.3-03
- Epic: `W2.3` | Type: `DELETE` | Files: route-local z-index fixes encountered later
- Do: remove route-local shell z-index overrides when discovered; Why: page-local escalation must not survive once shell ladder is stable.
- Done: migrated routes do not invent new shell-layer values.
- Risk: hidden overlay collisions reappear in admin routes.
- Verify: regression checks during W4-W6 | Commit: `refactor: remove route local shell z index overrides`

### T-W2.4-01
- Epic: `W2.4` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/__root.tsx`
- Do: improve landmarks, main/nav/header semantics and auth fallback structure; Why: shell landmarks are the foundation for route a11y.
- Done: shell has clear landmark hierarchy for authenticated and unauthenticated states.
- Risk: nav or header semantics conflict with existing tests.
- Verify: keyboard-only pass and a11y checks | Commit: `fix: improve shell landmark semantics`

### T-W2.4-02
- Epic: `W2.4` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/__root.tsx`
- Do: centralize focus return and inert logic for shell overlays; Why: overlay behavior should not depend on ad hoc DOM queries more than necessary.
- Done: More sheet and future shell overlays share one focus management contract.
- Risk: focus gets lost on close or route change.
- Verify: keyboard open/close and back-navigation pass | Commit: `fix: centralize shell focus return logic`

### T-W2.4-03
- Epic: `W2.4` | Type: `MODIFY` | Files: shell tests
- Do: add assertions for focus return and landmark stability; Why: shell fixes should stay protected.
- Done: tests fail on lost focus-return or landmark regressions.
- Risk: flaky focus assertions.
- Verify: `npm run test` | Commit: `test: cover shell focus and landmark behavior`

## W3 Tasks
### T-W3.1-01
- Epic: `W3.1` | Type: `EXTRACT` | Files: `frontend/app/src/theme/pages.css`
- Do: extract one hero/header pattern from the route variants already present; Why: 6+ different header patterns create duplication.
- Done: shared hero can express overview, ops and detail variants.
- Risk: shared hero becomes too rigid.
- Verify: visual pass on dashboard, incoming, candidate detail | Commit: `refactor: extract shared hero primitive`

### T-W3.1-02
- Epic: `W3.1` | Type: `MODIFY` | Files: `frontend/app/src/theme/components.css`, `frontend/app/src/theme/pages.css`
- Do: add shared hero action cluster and subtitle rules; Why: action hierarchy must be consistent at the top of each screen.
- Done: hero supports left content and right action grouping without route-local flex hacks.
- Risk: long titles and action clusters wrap poorly on tablet.
- Verify: tablet width pass on dashboard and profile | Commit: `refactor: add hero action cluster rules`

### T-W3.1-03
- Epic: `W3.1` | Type: `DELETE` | Files: route-local header styles during migrations
- Do: replace custom header containers with the shared hero where fit; Why: prevent drift from reappearing.
- Done: migrated screens no longer depend on bespoke hero wrappers.
- Risk: page-specific utility header behavior is lost.
- Verify: route-level regression during W4/W6 | Commit: `refactor: replace bespoke page headers with shared hero`

### T-W3.2-01
- Epic: `W3.2` | Type: `EXTRACT` | Files: `frontend/app/src/theme/pages.css`, `frontend/app/src/theme/material.css`
- Do: extract shared section container and head/body structure; Why: sections are the product’s main layout unit.
- Done: one section contract supports ops and admin density modes.
- Risk: subtle hierarchy differences disappear.
- Verify: section pass on system, dashboard, city-edit | Commit: `refactor: extract shared section container`

### T-W3.2-02
- Epic: `W3.2` | Type: `MODIFY` | Files: `frontend/app/src/theme/pages.css`
- Do: add modifiers for dense sections, side sections and interactive sections; Why: not every section has equal density or intent.
- Done: section variants exist without new page-local wrappers.
- Risk: too many modifiers reduce clarity.
- Verify: use on candidate detail and system previews | Commit: `feat: add section density and intent modifiers`

### T-W3.2-03
- Epic: `W3.2` | Type: `DELETE` | Files: targeted route-level section padding rules
- Do: remove local section padding/margin hacks where shared section contract is adopted; Why: keep spacing centralized.
- Done: migrated routes stop setting major section spacing inline or locally.
- Risk: hidden nesting cases may need exceptions.
- Verify: per-route screenshots in W4/W6 | Commit: `refactor: remove route local section spacing hacks`

### T-W3.3-01
- Epic: `W3.3` | Type: `EXTRACT` | Files: `frontend/app/src/theme/components.css`
- Do: define a shared toolbar structure with search/filter/action order; Why: core screens currently solve this separately.
- Done: toolbar primitive supports compact and wrap modes.
- Risk: some screens have too many controls for a single pattern.
- Verify: incoming, candidates and system toolbar pass | Commit: `refactor: extract shared toolbar structure`

### T-W3.3-02
- Epic: `W3.3` | Type: `MODIFY` | Files: `frontend/app/src/theme/global.css`, `frontend/app/src/theme/mobile.css`
- Do: replace `max-height`-driven advanced filter feel with a cleaner reveal strategy; Why: filter motion is currently janky.
- Done: advanced filters open and close crisply with predictable spacing.
- Risk: filter reveal accessibility or focus order breaks.
- Verify: filter interaction pass on incoming and slots | Commit: `refactor: improve advanced filter reveal behavior`

### T-W3.3-03
- Epic: `W3.3` | Type: `ADD` | Files: `frontend/app/src/theme/mobile.css`
- Do: add mobile sheet-backed filter helper classes and triggers; Why: W5 mobile filter work should not start from scratch.
- Done: filter-sheet primitives exist for later route adoption.
- Risk: duplicated overlay grammar with modal/sheet primitives.
- Verify: build plus shell overlay regression pass | Commit: `feat: add mobile filter sheet primitives`

### T-W3.4-01
- Epic: `W3.4` | Type: `MODIFY` | Files: `frontend/app/src/theme/components.css`
- Do: align button variants, sizes and states to shared tokens and motion; Why: controls need consistent hierarchy and touch targets.
- Done: buttons and icon buttons share variant/state contract.
- Risk: button density changes on desktop.
- Verify: manual pass on forms and toolbars | Commit: `refactor: align shared button variants`

### T-W3.4-02
- Epic: `W3.4` | Type: `MODIFY` | Files: `frontend/app/src/theme/components.css`
- Do: align inputs, selects and search field behavior including focus and error states; Why: forms must feel coherent across pages.
- Done: text/date/time/textarea/select/search all sit on one shared visual contract.
- Risk: form field height or font size regressions on mobile.
- Verify: recruiter-new, template-edit and candidate-new spot checks | Commit: `refactor: align shared field controls`

### T-W3.4-03
- Epic: `W3.4` | Type: `DELETE` | Files: route-local control styling during migrations
- Do: remove local control overrides where shared controls suffice; Why: avoid two control systems.
- Done: migrated screens rely on shared control states.
- Risk: specialty controls may still need local wrappers.
- Verify: per-screen visual diff during W4/W6 | Commit: `refactor: remove route local control styling`

### T-W3.5-01
- Epic: `W3.5` | Type: `EXTRACT` | Files: `frontend/app/src/theme/material.css`, `frontend/app/src/theme/mobile.css`, `frontend/app/src/theme/motion.css`
- Do: formalize modal, sheet and drawer surface/motion behavior; Why: overlays currently vary too much by route.
- Done: shared overlay contract exists for dialog, sheet and drawer variants.
- Risk: route-specific overlay content still requires local fixes.
- Verify: open/close pass on incoming and calendar modals | Commit: `refactor: extract shared overlay primitives`

### T-W3.5-02
- Epic: `W3.5` | Type: `MODIFY` | Files: `frontend/app/src/theme/motion.css`
- Do: align overlay timings to 280ms/180ms contract and reduced-motion behavior; Why: modal/sheet motion should be predictable.
- Done: overlays share timing and reduced-motion rules.
- Risk: visual jank if old keyframes still override.
- Verify: reduced-motion and mobile overlay smoke | Commit: `refactor: align overlay motion timings`

### T-W3.5-03
- Epic: `W3.5` | Type: `DELETE` | Files: route-local overlay styles during migration
- Do: remove route-local modal/sheet visual hacks once shared overlay exists; Why: eliminate duplicate overlay systems.
- Done: first-wave routes use shared overlay surfaces and motion.
- Risk: some highly custom preview overlays may need exceptions.
- Verify: route smoke on candidate detail, messenger, calendar | Commit: `refactor: remove route local overlay hacks`

### T-W3.6-01
- Epic: `W3.6` | Type: `EXTRACT` | Files: `frontend/app/src/theme/mobile.css`, `frontend/app/src/theme/global.css`
- Do: define shared mobile-card-list and table-wrapper parity rules; Why: multiple screens currently duplicate this logic.
- Done: card/table parity contract exists in shared CSS.
- Risk: parity rules too generic for matrix-like templates list.
- Verify: visual pass on slots, candidates and questions | Commit: `refactor: extract card table parity primitives`

### T-W3.6-02
- Epic: `W3.6` | Type: `ADD` | Files: `frontend/app/src/theme/components.css`
- Do: define metadata order and action row conventions for mobile entity cards; Why: cards need a consistent content hierarchy.
- Done: mobile cards share title, status, meta and action order.
- Risk: some domain-specific cards need exceptions.
- Verify: mobile card pass on slots and candidates | Commit: `feat: add shared mobile entity card conventions`

### T-W3.6-03
- Epic: `W3.6` | Type: `DELETE` | Files: route-local duplicated card wrappers during migration
- Do: remove card/table duplication patterns that no longer need bespoke wrappers; Why: reduce route-level responsive debt.
- Done: migrated routes use shared card/table conventions.
- Risk: hidden per-screen states get dropped.
- Verify: regression on list empty/loading/action states | Commit: `refactor: reduce duplicated route card wrappers`

## W4 Tasks
### T-W4.1-01
- Epic: `W4.1` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/dashboard.tsx`
- Do: migrate dashboard header and summary blocks to shared hero/section primitives; Why: dashboard should prove the foundation is usable.
- Done: dashboard uses shared page shell and surface hierarchy.
- Risk: overview becomes too rigid or loses personality.
- Verify: dashboard smoke at desktop/tablet/mobile | Commit: `feat: migrate dashboard to shared page shell`

### T-W4.1-02
- Epic: `W4.1` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/dashboard.tsx`
- Do: rebalance metric, leaderboard and incoming queue visual priority; Why: active work must outrank decorative stats.
- Done: queue and KPI hierarchy is clearly ordered.
- Risk: admin overview loses useful secondary analytics visibility.
- Verify: manual scan-speed review and screenshot check | Commit: `refactor: rebalance dashboard content hierarchy`

### T-W4.1-03
- Epic: `W4.1` | Type: `DELETE` | Files: local dashboard visual wrappers if replaced
- Do: remove dashboard-specific spacing or surface wrappers made obsolete by shared primitives; Why: avoid partial migration.
- Done: dashboard relies on shared hero/section rhythm wherever possible.
- Risk: some leaderboard-specific layout helpers still needed.
- Verify: build and visual regression pass | Commit: `refactor: remove redundant dashboard wrappers`

### T-W4.2-01
- Epic: `W4.2` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/incoming.tsx`
- Do: migrate incoming to shared hero, section, toolbar and filter primitives; Why: incoming is the recommended first ops screen.
- Done: incoming top-level structure uses shared layout.
- Risk: filter logic or modal wiring breaks.
- Verify: incoming smoke desktop/mobile | Commit: `feat: migrate incoming to shared ops primitives`

### T-W4.2-02
- Epic: `W4.2` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/incoming.tsx`
- Do: align advanced filters and queue cards with the new toolbar/card parity grammar; Why: the screen should become the ops reference implementation.
- Done: queue card order and filter interaction follow shared contracts.
- Risk: card density becomes too low or too high.
- Verify: 390/375/320 queue pass | Commit: `refactor: align incoming filters and queue cards`

### T-W4.2-03
- Epic: `W4.2` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/incoming.tsx`
- Do: migrate scheduling modal to overlay primitive; Why: incoming relies on modal flow for a core action.
- Done: schedule flow preserves context, motion and focus behavior.
- Risk: timezone preview or submit flow regresses.
- Verify: open/close/submit modal smoke | Commit: `refactor: migrate incoming schedule modal to shared overlay`

### T-W4.3-01
- Epic: `W4.3` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/slots.tsx`
- Do: migrate slots screen structure to shared hero/section/toolbar grammar; Why: slots is a dense ops screen with repeated patterns.
- Done: shared structure replaces bespoke header and filter rhythm.
- Risk: summary chips and bulk toolbar spacing regress.
- Verify: slots smoke desktop/mobile | Commit: `feat: migrate slots screen structure`

### T-W4.3-02
- Epic: `W4.3` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/slots.tsx`, shared mobile/table styles
- Do: align slots table and mobile cards with parity contract; Why: no action can be lost between modes.
- Done: slots cards expose same critical status and actions as table rows.
- Risk: bulk-select or detail behavior diverges.
- Verify: compare table/card action matrix | Commit: `refactor: align slots table and card parity`

### T-W4.3-03
- Epic: `W4.3` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/slots.tsx`
- Do: normalize bulk action bar and selection state styling; Why: bulk actions are high risk for regressions.
- Done: selection and bulk state are visually clear on desktop and mobile.
- Risk: selection state disappears in dense filters.
- Verify: bulk remind/delete smoke | Commit: `refactor: normalize slots bulk action states`

### T-W4.4-01
- Epic: `W4.4` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/candidates.tsx`
- Do: migrate candidates hero and filter/view toolbar to shared patterns; Why: view switching needs stronger hierarchy.
- Done: candidates top-level controls use shared grammar.
- Risk: query parameter/view logic regresses.
- Verify: switch list/kanban/calendar smoke | Commit: `feat: migrate candidates view shell`

### T-W4.4-02
- Epic: `W4.4` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/candidates.tsx`, shared styles
- Do: align list view and mobile cards with table/card parity contract; Why: list mode is the most-used candidate view.
- Done: candidate list is robust on mobile and desktop.
- Risk: status or action parity gaps.
- Verify: desktop vs mobile candidate list comparison | Commit: `refactor: align candidates list parity`

### T-W4.4-03
- Epic: `W4.4` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/candidates.tsx`, `frontend/app/src/theme/mobile.css`
- Do: reduce mobile burden of kanban/calendar and clarify alternate view semantics; Why: multi-view screens need a mobile-first priority order.
- Done: mobile emphasizes list first and constrains alternate views appropriately.
- Risk: users lose access to needed alternate views.
- Verify: mobile view-switch smoke | Commit: `refactor: prioritize mobile candidates views`

### T-W4.5-01
- Epic: `W4.5` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/candidate-detail.tsx`
- Do: restructure candidate detail top of page into hero plus pipeline strip; Why: the first screenful currently carries too much unstructured density.
- Done: hero and pipeline actions are visually separated and easy to scan.
- Risk: top-level actions get moved away from existing user memory.
- Verify: candidate detail screenshot and keyboard pass | Commit: `feat: restructure candidate detail hero and pipeline`

### T-W4.5-02
- Epic: `W4.5` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/candidate-detail.tsx`
- Do: reorganize secondary content into a deliberate section stack; Why: tests, slots, AI and reports need clearer boundaries.
- Done: section order follows the canonical structure from `DESIGN_DECISIONS_LOG.md`.
- Risk: internal anchors or contextual actions become harder to find.
- Verify: manual flow through slots/tests/AI/history | Commit: `refactor: reorganize candidate detail section stack`

### T-W4.5-03
- Epic: `W4.5` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/candidate-detail.tsx`, shared styles
- Do: apply mobile accordion/tab rules only to dense secondary sections and improve interactive scroll behavior; Why: mobile detail must stay full-route and accessible.
- Done: mobile detail remains drill-down first with accessible section access.
- Risk: `scrollable-region-focusable` issue persists.
- Verify: mobile a11y and candidate detail smoke | Commit: `fix: harden mobile candidate detail section access`

### T-W4.6-01
- Epic: `W4.6` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/messenger.tsx`
- Do: migrate messenger header and shell to shared page primitives; Why: split-pane still needs consistent app grammar.
- Done: messenger uses shared hero/section structure while retaining split-pane logic.
- Risk: active thread layout or search placement regresses.
- Verify: messenger smoke on desktop/mobile | Commit: `feat: migrate messenger shell to shared primitives`

### T-W4.6-02
- Epic: `W4.6` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/messenger.tsx`
- Do: align thread list, conversation and composer spacing with shared patterns; Why: chat should feel operationally crisp rather than ad hoc.
- Done: thread list and active chat hierarchy are clearer.
- Risk: composer density becomes too tall on mobile.
- Verify: send/read/task flow smoke | Commit: `refactor: align messenger thread and composer layout`

### T-W4.6-03
- Epic: `W4.6` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/messenger.tsx`, overlay primitives
- Do: migrate messenger task and action modals to the shared overlay contract; Why: messenger includes multiple modal-heavy flows.
- Done: message/task modals use common semantics and motion.
- Risk: task approval/decline flows regress.
- Verify: approve/decline modal smoke | Commit: `refactor: migrate messenger overlays to shared contract`

### T-W4.7-01
- Epic: `W4.7` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/calendar.tsx`
- Do: migrate calendar header and filters to shared hero/toolbar/filter patterns; Why: current calendar controls are isolated from the rest of the system.
- Done: calendar top controls look and behave like other ops screens.
- Risk: FullCalendar width/layout shifts.
- Verify: calendar route smoke desktop/tablet | Commit: `feat: migrate calendar controls to shared patterns`

### T-W4.7-02
- Epic: `W4.7` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/calendar.tsx`, `frontend/app/src/app/components/Calendar/ScheduleCalendar.tsx`
- Do: reduce mobile calendar mode burden and improve task drill-down; Why: current mobile switch is minimal, not strategic.
- Done: mobile calendar emphasizes readable views and clear task access.
- Risk: admin filters or event density become hidden.
- Verify: mobile calendar create/edit flow | Commit: `refactor: simplify mobile calendar modes`

### T-W4.7-03
- Epic: `W4.7` | Type: `MODIFY` | Files: calendar route and overlay styles
- Do: move task and slot overlays onto shared modal/sheet behavior; Why: calendar interactions are modal-heavy and must match the global contract.
- Done: task overlays use shared semantics and motion.
- Risk: overlay nesting or focus issues.
- Verify: create/edit/delete task smoke | Commit: `refactor: migrate calendar overlays to shared primitives`

## W5 Tasks
### T-W5.1-01
- Epic: `W5.1` | Type: `ADD` | Files: shared mobile filter primitives, affected route files
- Do: add trigger, body, apply/reset and summary patterns for filter sheets; Why: mobile filters need a repeatable structure.
- Done: core screens can open filters in a consistent sheet pattern.
- Risk: discoverability of advanced filters drops.
- Verify: mobile filter smoke on incoming and candidates | Commit: `feat: add reusable mobile filter sheet flow`

### T-W5.1-02
- Epic: `W5.1` | Type: `MODIFY` | Files: `incoming.tsx`, `slots.tsx`, `candidates.tsx`, optionally `system.tsx`
- Do: migrate highest-density filters to the sheet-backed pattern where needed; Why: reduce toolbar overload on narrow widths.
- Done: mobile filter flows preserve current filter power with simpler layout.
- Risk: mismatch between inline desktop filters and mobile sheet filters.
- Verify: filter apply/reset parity check | Commit: `refactor: migrate core mobile filters to sheet pattern`

### T-W5.1-03
- Epic: `W5.1` | Type: `DELETE` | Files: route-local mobile filter hacks
- Do: remove temporary or duplicated mobile filter wrappers once sheet pattern is adopted; Why: keep filter logic centralized.
- Done: routes stop carrying bespoke mobile filter containers.
- Risk: some screens still need special-case subfilters.
- Verify: mobile regression on filter flows | Commit: `refactor: remove bespoke mobile filter wrappers`

### T-W5.2-01
- Epic: `W5.2` | Type: `MODIFY` | Files: `slots.tsx`, `candidates.tsx`, shared mobile styles
- Do: build explicit parity matrix for slots and candidates cards vs tables and implement missing pieces; Why: first-wave parity must be guaranteed.
- Done: mobile cards expose the same critical actions and statuses as desktop rows.
- Risk: parity changes bloat card density.
- Verify: row-to-card parity checklist | Commit: `refactor: complete first wave card parity matrix`

### T-W5.2-02
- Epic: `W5.2` | Type: `MODIFY` | Files: `template-list.tsx`, `questions.tsx`, admin list styles
- Do: apply the parity rules to smaller library/admin list screens; Why: reuse should extend beyond recruiter screens.
- Done: lower-risk list screens share card/table parity grammar.
- Risk: template matrix remains special-case heavy.
- Verify: mobile list pass on templates and questions | Commit: `refactor: apply card parity to admin lists`

### T-W5.2-03
- Epic: `W5.2` | Type: `DELETE` | Files: duplicated card metadata blocks where parity primitives replace them
- Do: delete ad hoc mobile-card metadata layouts replaced by shared conventions; Why: avoid future parity divergence.
- Done: migrated card layouts use shared structure.
- Risk: some screens lose domain-specific metadata ordering.
- Verify: per-screen regression screenshots | Commit: `refactor: delete duplicated mobile card metadata layouts`

### T-W5.3-01
- Epic: `W5.3` | Type: `MODIFY` | Files: `frontend/app/src/theme/mobile.css`
- Do: tune safe-area padding and sticky positioning for shell, filters and action areas; Why: keyboard and browser UI must not hide controls.
- Done: safe-area and sticky rules are explicit and reused.
- Risk: excess bottom padding on simple screens.
- Verify: short-height manual pass | Commit: `refactor: tune mobile safe area and sticky rules`

### T-W5.3-02
- Epic: `W5.3` | Type: `MODIFY` | Files: long-form and chat route files as needed
- Do: make key forms and composer areas keyboard-safe on mobile; Why: data entry flows must stay usable when browser chrome shifts.
- Done: no primary submit or composer actions are hidden by the virtual keyboard in target screens.
- Risk: route-local workaround creep.
- Verify: mobile keyboard pass on city-edit, candidate-new, messenger | Commit: `fix: harden mobile keyboard safe interactions`

### T-W5.3-03
- Epic: `W5.3` | Type: `DELETE` | Files: route-local sticky offset hacks
- Do: remove per-route sticky offset fixes after safe-area and sticky rules are centralized; Why: they will otherwise rot.
- Done: migrated routes rely on shared shell/mobile spacing.
- Risk: leftover admin pages still need local offsets.
- Verify: 390/375/320 overlap pass | Commit: `refactor: remove route local sticky offset hacks`

### T-W5.4-01
- Epic: `W5.4` | Type: `MODIFY` | Files: candidate detail, shell and overlay code
- Do: fix interactive scroll region focus and focus-visible issues on mobile-first flows; Why: a11y defects are concentrated in dense mobile interactions.
- Done: candidate detail and overlays meet keyboard/focus requirements.
- Risk: scroll behavior changes unexpectedly.
- Verify: keyboard-only mobile spot pass | Commit: `fix: improve mobile focus and scroll accessibility`

### T-W5.4-02
- Epic: `W5.4` | Type: `MODIFY` | Files: shared styles and route files as needed
- Do: validate and tighten touch targets, landmark semantics and status independence from color; Why: WCAG target is AA.
- Done: core mobile controls respect hit target and semantic rules.
- Risk: increased touch area impacts dense layouts.
- Verify: mobile a11y checklist subset | Commit: `fix: harden mobile touch and semantic accessibility`

### T-W5.4-03
- Epic: `W5.4` | Type: `MODIFY` | Files: shell and route tests
- Do: add targeted coverage for mobile a11y watchpoints; Why: later waves should not reintroduce solved issues.
- Done: tests or assertions catch regressions in focus and hidden-overlay behavior.
- Risk: test fragility.
- Verify: `npm run test` | Commit: `test: cover mobile accessibility watchpoints`

## W6 Tasks
### T-W6.1-01
- Epic: `W6.1` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/city-edit.tsx`, theme files
- Do: extract spacing-related inline styles from city-edit into shared or page-scoped classes; Why: spacing is the largest portion of the file’s debt.
- Done: margin/padding/gap inline styles are materially reduced and replaced by classes.
- Risk: form section rhythm changes subtly across the page.
- Verify: city-edit screenshot diff desktop/mobile | Commit: `refactor: extract city edit spacing inline styles`

### T-W6.1-02
- Epic: `W6.1` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/city-edit.tsx`, theme files
- Do: extract layout-related inline styles from city-edit into form and section grammar; Why: layout debt drives most visual inconsistency.
- Done: flex/grid/min-width/layout wrappers move to classes.
- Risk: breakpoints or wrap behavior regress.
- Verify: 1440/1024/390 city-edit layout pass | Commit: `refactor: extract city edit layout inline styles`

### T-W6.1-03
- Epic: `W6.1` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/city-edit.tsx`, theme files
- Do: extract color, sizing and typography inline styles into tokens and named classes; Why: hardcoded status and font tweaks block maintainability.
- Done: local color/font/min-width values are class- or token-driven.
- Risk: semantic emphasis is lost if tokens are too generic.
- Verify: city-edit visual regression plus token audit | Commit: `refactor: extract city edit color and sizing inline styles`

### T-W6.1-04
- Epic: `W6.1` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/city-edit.tsx`
- Do: rebuild city-edit structure around admin form grammar and section containers; Why: extraction only matters if the page adopts the shared system.
- Done: city-edit uses `.ui-form-shell`, `.ui-field`, `.app-page__section` and shared footer behavior.
- Risk: deeply nested logic becomes harder to trace during migration.
- Verify: save flow and linked-entity manual pass | Commit: `feat: migrate city edit to admin form grammar`

### T-W6.2-01
- Epic: `W6.2` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/system.tsx`, theme files
- Do: extract spacing and layout inline styles from system screen; Why: system is the second-largest mounted debt hotspot.
- Done: toolbars, panels and table wrappers use classes instead of inline layout rules.
- Risk: wide-table behavior changes unexpectedly.
- Verify: system screenshot diff and table overflow pass | Commit: `refactor: extract system layout inline styles`

### T-W6.2-02
- Epic: `W6.2` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/system.tsx`, theme files
- Do: extract color, sizing and one-off table styling into reusable admin classes; Why: operational tables need shared semantics.
- Done: status colors, white-space rules and sizing move out of JSX where possible.
- Risk: log and job tables lose important dense readability.
- Verify: system logs/jobs visual pass | Commit: `refactor: extract system table and color inline styles`

### T-W6.2-03
- Epic: `W6.2` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/system.tsx`
- Do: migrate system tabs, policies and logs into admin section grammar; Why: the page should stop being a patchwork of special cases.
- Done: system uses shared section, toolbar and state patterns.
- Risk: tabbed structure or policy controls regress.
- Verify: tab switching and filter/manual pass | Commit: `feat: migrate system page to admin grammar`

### T-W6.2-04
- Epic: `W6.2` | Type: `MODIFY` | Files: system tests or smoke coverage
- Do: add smoke coverage for system high-risk tables and tabs; Why: this page has high regression surface.
- Done: system-specific smoke asserts presence and basic usability of major regions.
- Risk: selectors become brittle.
- Verify: smoke run | Commit: `test: add system smoke assertions`

### T-W6.3-01
- Epic: `W6.3` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/test-builder.tsx`, theme files
- Do: extract inline layout and spacing styles from list-based test builder; Why: workspace cleanup should start with the simpler builder view.
- Done: builder/editor layout uses shared workspace classes.
- Risk: drag or selection affordances shift.
- Verify: builder layout pass | Commit: `refactor: extract test builder workspace inline styles`

### T-W6.3-02
- Epic: `W6.3` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/test-builder-graph.tsx`, theme files
- Do: extract spacing and layout inline styles from graph workspace; Why: graph view is a major desktop-specific debt hotspot.
- Done: graph header, toolbar, preview and editor wrappers rely on classes.
- Risk: graph canvas sizing regresses.
- Verify: graph layout pass on desktop/tablet | Commit: `refactor: extract graph workspace layout inline styles`

### T-W6.3-03
- Epic: `W6.3` | Type: `EXTRACT` | Files: `frontend/app/src/app/routes/app/test-builder-graph.tsx`, theme files
- Do: extract color, sizing and typography inline styles from graph preview/editor; Why: visual semantics should be shared, not embedded in JSX.
- Done: graph preview/editor typography and emphasis use tokens/classes.
- Risk: node/editor readability suffers.
- Verify: graph preview/editor screenshot diff | Commit: `refactor: extract graph preview styling inline styles`

### T-W6.3-04
- Epic: `W6.3` | Type: `MODIFY` | Files: `frontend/app/src/app/routes/app/test-builder.tsx`, `frontend/app/src/app/routes/app/test-builder-graph.tsx`
- Do: align both builder modes with shared admin workspace and section grammar; Why: they should feel like one product area with two modes.
- Done: list and graph modes share headers, sections and form/editor grammar where applicable.
- Risk: forcing parity where tool mode needs differ.
- Verify: mode-switch and save/manual pass | Commit: `feat: align test builder modes to shared workspace grammar`

### T-W6.4-01
- Epic: `W6.4` | Type: `MODIFY` | Files: `template-list.tsx`, `template-new.tsx`, `template-edit.tsx`
- Do: standardize template list/create/edit flow using shared library and form patterns; Why: template flows are a reusable admin family.
- Done: list/create/edit hierarchy feels coherent and uses shared toolbars and forms.
- Risk: template matrix still needs local exceptions.
- Verify: create/edit/list manual pass | Commit: `feat: unify template library flows`

### T-W6.4-02
- Epic: `W6.4` | Type: `MODIFY` | Files: `questions.tsx`, `question-new.tsx`, `question-edit.tsx`
- Do: standardize question list/create/edit flow using the same family pattern; Why: questions should mirror template family consistency.
- Done: list/create/edit question screens share header and form grammar.
- Risk: JSON payload editor density becomes awkward on mobile.
- Verify: question create/edit pass | Commit: `feat: unify question library flows`

### T-W6.4-03
- Epic: `W6.4` | Type: `MODIFY` | Files: `message-templates.tsx`
- Do: bring message-templates onto the same library/edit grammar and reduce inline-style debt; Why: it sits between library and two-panel editor behavior.
- Done: message-templates uses shared sections, form grammar and state blocks.
- Risk: editor/history split becomes less clear.
- Verify: select/edit/history pass | Commit: `refactor: align message templates with admin library grammar`

### T-W6.5-01
- Epic: `W6.5` | Type: `MODIFY` | Files: `profile.tsx`, `cities.tsx`, `city-new.tsx`, `recruiters.tsx`, `recruiter-new.tsx`, `recruiter-edit.tsx`
- Do: align remaining profile and entity-management screens with shared hero/section/form patterns; Why: these routes are lower risk but visible.
- Done: entity and profile routes match the system without route-local layout drift.
- Risk: recruiter/profile screens lose beneficial personality.
- Verify: entity management manual pass | Commit: `refactor: align profile cities and recruiters screens`

### T-W6.5-02
- Epic: `W6.5` | Type: `MODIFY` | Files: `copilot.tsx`, `simulator.tsx`, `detailization.tsx`
- Do: align utility/admin surfaces with shared section and state contracts; Why: utility pages should stop being isolated visual sub-products.
- Done: copilot, simulator and detailization use the same admin shell logic.
- Risk: analytical density suffers if too much simplification happens.
- Verify: utility route visual pass | Commit: `refactor: align utility admin screens to shared grammar`

### T-W6.5-03
- Epic: `W6.5` | Type: `MODIFY` | Files: `slots-create.tsx`, `candidate-new.tsx`
- Do: align creation forms for recruiter flows with the shared form grammar; Why: not all forms are admin-only.
- Done: create-slot and create-candidate forms fit the same system.
- Risk: data-entry speed regresses due to overly generic form layout.
- Verify: create-flow manual pass mobile/desktop | Commit: `refactor: align recruiter creation forms to shared grammar`

## W7 Tasks
### T-W7.1-01
- Epic: `W7.1` | Type: `MODIFY` | Files: `frontend/app/src/theme/motion.css`
- Do: align motion tokens and key interactions to the approved 120/180/280ms hierarchy; Why: motion polish must be systemic.
- Done: overlay, route and microinteraction timings match the motion guidelines.
- Risk: changing motion late can reveal hidden layout assumptions.
- Verify: reduced-motion and interaction spot pass | Commit: `refactor: align motion timing hierarchy`

### T-W7.1-02
- Epic: `W7.1` | Type: `DELETE` | Files: targeted decorative or conflicting motion rules
- Do: remove non-essential decorative motion on quiet operational routes; Why: calm operational UI is a redesign principle.
- Done: quiet routes no longer animate decorative background or flourish states.
- Risk: some users perceive the UI as flatter.
- Verify: dashboard vs incoming motion comparison | Commit: `refactor: remove nonessential quiet route motion`

### T-W7.1-03
- Epic: `W7.1` | Type: `MODIFY` | Files: shared styles and route-level hover/active states
- Do: tune hover, active and focus states to feel premium but restrained; Why: quality lives in consistent microinteraction rules.
- Done: buttons, cards and nav states feel consistent across surfaces.
- Risk: hover and focus become visually too similar.
- Verify: keyboard and mouse interaction pass | Commit: `refactor: tune microinteraction polish`

### T-W7.2-01
- Epic: `W7.2` | Type: `ADD` | Files: existing test suites and/or new smoke specs
- Do: add or extend smoke coverage for shell, incoming, slots, candidates, candidate detail, messenger, city-edit and system; Why: these are the highest-risk routes.
- Done: smoke suite covers route rendering and key interactions for first-wave screens.
- Risk: test runtime or brittleness grows.
- Verify: `npm run test` and smoke commands | Commit: `test: expand redesign smoke coverage`

### T-W7.2-02
- Epic: `W7.2` | Type: `ADD` | Files: test suites
- Do: add targeted accessibility assertions for shell and dense routes; Why: landmark and focus issues are known risk areas.
- Done: a11y assertions cover More sheet, candidate detail and key shell structures.
- Risk: a11y tests become flaky without stable hooks.
- Verify: test run plus manual a11y spot pass | Commit: `test: add shell and route accessibility assertions`

### T-W7.2-03
- Epic: `W7.2` | Type: `MODIFY` | Files: test selectors/hooks in route files if needed
- Do: stabilize selectors used by smoke and a11y tests; Why: reliable tests require durable test hooks.
- Done: stable data-testid or semantic hooks exist for high-risk flows.
- Risk: selector sprawl in route JSX.
- Verify: smoke rerun | Commit: `test: stabilize selectors for redesign smoke`

### T-W7.3-01
- Epic: `W7.3` | Type: `MODIFY` | Files: any files changed by found defects
- Do: run responsive QA across the full viewport matrix and fix found P0/P1 issues; Why: final burn-down must be explicit.
- Done: no unresolved P0/P1 responsive issues remain on first-wave screens.
- Risk: last-minute fixes spread across many files.
- Verify: viewport matrix pass and smoke rerun | Commit: `fix: resolve responsive qa findings`

### T-W7.3-02
- Epic: `W7.3` | Type: `MODIFY` | Files: any files changed by found defects
- Do: run manual QA subset from `DESIGN_QA_CHECKLIST.md` and close functional polish issues; Why: not all defects surface in automated checks.
- Done: manual QA subset is executed and logged wave-by-wave.
- Risk: polish work expands into new feature requests.
- Verify: QA checklist sign-off | Commit: `fix: resolve manual qa findings`

### T-W7.3-03
- Epic: `W7.3` | Type: `MODIFY` | Files: docs and tests if needed
- Do: refresh artifact references, screenshots and regression notes after implementation stabilizes; Why: handoff docs should match the implemented system.
- Done: docs and test references reflect final delivered state.
- Risk: documentation drifts behind code changes.
- Verify: final doc cross-check and validation rerun | Commit: `docs: refresh redesign handoff after hardening`
