# 1. Executive summary

RecruitSmart уже выглядит как production-like recruiting CRM с заметной попыткой построить собственный визуальный язык для операторского SPA, но система не воспринимается как единый продукт на всех candidate-facing и recruiter-facing поверхностях. Внутри `/app/*` есть достаточно зрелая dark-first token-based тема, mobile shell, route-level UI grammar и отдельный `liquid-glass-v2` mode. При этом Telegram mini app, bounded MAX mini app и основной SPA используют разные UI-парадигмы, разные уровни зрелости и разные паттерны состояния.

Сильная сторона продукта: основной SPA уже имеет собственную theme layer, понятный стек, покрытие тестами, реальный responsive shell и достаточно широкую surface area для recruiter operations. Главная проблема: дизайн-система централизована только внутри admin SPA. Между `/app/*`, `/tg-app/*` и `/miniapp` нет общего продуктового языка по typography, state semantics, feedback patterns, empty/loading/error states и визуальной иерархии. Из-за этого candidate journey и operator tooling выглядят как несколько соседних продуктов, а не как одна система.

Ближайшие 24 часа стоит тратить не на переписывание архитектуры, а на выравнивание иерархии, контрастов, форм, пустых состояний, auth behavior и mobile readability. Это даст быстрый визуальный и UX-эффект без риска залезть в backend contracts.

# 2. Tech/design inventory

## Frontend stack

- `React 18.3.1`
- `TypeScript 5.6.3`
- `Vite 7.3.1`
- `Vitest 4.0.18`
- `Playwright 1.48.2`
- `ESLint 9`

Source:
- [frontend/app/package.json](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/package.json)
- [frontend/app/vite.config.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/vite.config.ts)

## Routing

- `@tanstack/react-router`
- route tree declared directly in [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- mounted route families:
  - `/app/*` admin SPA
  - `/tg-app/*` Telegram recruiter mini app
  - `/miniapp` bounded MAX candidate mini app

## State management

- server state: `@tanstack/react-query`
- route state: TanStack Router
- local UI state: React component state
- small global store: `zustand`
  - proven usage in [frontend/app/src/app/hooks/useIsMobile.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/hooks/useIsMobile.ts)

## UI library / component primitives

- No Radix, MUI, Chakra, Ant, Mantine, Headless UI or equivalent shared component library found.
- Primary UI primitives are repo-local CSS classes and custom React components.
- Common pattern families live in:
  - [frontend/app/src/theme/components.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/components.css)
  - [frontend/app/src/theme/components-core.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/components-core.css)
  - [frontend/app/src/theme/components-extended.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/components-extended.css)
  - [frontend/app/src/theme/components-system.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/components-system.css)
  - [frontend/app/src/theme/layout.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/layout.css)

## Styling approach

- Custom CSS modules by import layering through [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)
- CSS custom properties / design tokens in [frontend/app/src/theme/tokens.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/tokens.css)
- No Tailwind, no utility framework, no CSS-in-JS
- Page-level CSS for route-specific composition:
  - `pages/*.css`
  - `miniapp/miniapp.css`
- Telegram mini app screens use heavy inline styles instead of shared primitives:
  - [frontend/app/src/app/routes/tg-app/index.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/index.tsx)
  - [frontend/app/src/app/routes/tg-app/incoming.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/incoming.tsx)
  - [frontend/app/src/app/routes/tg-app/candidate.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/candidate.tsx)

## Fonts

Proven by code:

- default body stack:
  - `Manrope`
  - `Space Grotesk`
  - system fallbacks
- default display stack:
  - `Space Grotesk`
  - `Manrope`
  - system fallbacks

Source:
- [frontend/app/src/theme/variables.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/variables.css)
- [frontend/app/src/theme/tokens.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/tokens.css)

Additional proven fallback in `liquid-glass-v2` mode:

- `SF Pro Text`
- `SF Pro Display`
- Apple/system UI fallback stack

This is fallback styling, not proof that actual SF fonts are installed everywhere.

Telegram mini app font stack is separate and inline:

- `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `Roboto`, sans-serif

Source:
- [frontend/app/src/app/routes/tg-app/layout.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/layout.tsx)

## Theme variables / tokens

Proven token families in `tokens.css`:

- breakpoints
- font family / weights
- spacing scale
- text scale
- radii
- blur
- duration / easing / transitions
- z-index
- semantic surfaces
- semantic border colors
- semantic text colors
- semantic accent/success/warning/danger colors
- shadow / glow / focus ring
- glass surface tokens

There is also a parallel TS token export in [frontend/app/src/theme/tokens.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/tokens.ts), but CSS tokens are the actual rendering source of truth.

## Icons

- `lucide-react`
- significant additional usage of inline SVG icons in shell/navigation

Source:
- [frontend/app/package.json](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/package.json)
- [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)

## Animation libraries

- `framer-motion`
- custom motion token layer in:
  - [frontend/app/src/theme/motion.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/motion.css)
  - [frontend/app/src/theme/animations.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/animations.css)
  - [frontend/app/src/shared/motion.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/shared/motion.ts)

Observed usage:

- dashboard
- candidates
- candidate detail drawers
- recruitment script
- interview script
- candidate pipeline

## Form libraries

- `react-hook-form`

Proven usage:
- [frontend/app/src/app/routes/app/slots-create.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/slots-create.tsx)

## Validation libraries

- `zod`
- `@hookform/resolvers/zod`

## Table / data-grid libraries

- No table/data-grid package found.
- Tables are custom HTML/CSS, especially in candidates and slots surfaces.

## Other specialized UI dependencies

- `@fullcalendar/react` and related plugins for calendar views
- `@xyflow/react` for graph/test builder
- `clsx` for conditional classes

## Design-system dependencies

- No external design-system dependency found.
- Real design system is internal and partial:
  - token layer is centralized
  - component grammar is semi-centralized
  - cross-surface consistency is incomplete

# 3. Current design language

## General style

The main admin SPA uses a dark, glass-heavy, low-chroma CRM aesthetic:

- rounded panels
- blurred elevated surfaces
- soft borders
- subdued gradients
- compact nav pills
- heavy use of dark navy/graphite backgrounds
- accent-driven buttons in blue-violet range

This is closer to “premium ops dashboard” than to utilitarian enterprise software. The look is intentional, but contrast and information hierarchy are not always strong enough to support dense operational work.

## Density

- Desktop density is high.
- Information is often compressed into long horizontal cards, pills, chip rows and dense table rows.
- Mobile density is still high relative to screen width, especially on candidates surfaces.

This is acceptable for a CRM, but the current hierarchy does not always separate primary task data from decorative atmosphere.

## Visual noise

Main SPA:

- moderate visual noise
- driven by stacked glass panels, pill nav, subtle gradients, glows and multiple card borders

Telegram mini app:

- visually simple
- low polish
- low visual noise
- almost no system-level hierarchy

MAX mini app:

- visually coherent inside its own surface
- stronger candidate-first storytelling
- still heavy on dark cards and layered containers

## Composition

Admin SPA composition pattern:

- sticky shell header
- wide hero/panel header
- stacked sections
- dense control bars
- KPI and list/table zones

This generally works on desktop but causes a recurring problem: page headers, filters, tabs, chips, badges and action groups compete at the same visual weight.

## Card patterns

Observed card styles:

- glass panel hero cards
- neutral data cards
- KPI cards
- compact chips/pills inside cards
- mobile cards as stacked list replacements

Strength:
- card system is recognizable

Weakness:
- multiple card grammars coexist
- border intensity, elevation and internal spacing vary too much across routes

## Buttons

Main SPA:

- `ui-btn`
- `ui-btn--primary`
- `ui-btn--ghost`
- `ui-btn--secondary`
- `ui-btn--danger`

Strength:
- there is a shared button grammar

Weakness:
- primary and secondary emphasis is not always obvious enough in dark mode
- small buttons are sometimes too visually weak inside dense toolbars
- some route-level links still behave like pseudo-buttons without consistent semantics

Telegram mini app:

- raw inline buttons with Telegram theme colors

MAX mini app:

- separate `.max-btn` grammar with its own weight, radius and gradient logic

## Forms

Main SPA form grammar exists:

- `.form-group`
- `.form-layout`
- `.form-row`
- route-level shared inputs/selects

Strength:
- core form layer exists

Weakness:
- login labels are not properly associated with inputs for accessibility/automation lookup
- several route forms remain visually route-specific
- filters often look like form controls but behave as dense toolbars without clear grouping

## Tables

Main SPA tables are custom.

Strength:
- domain-specific flexibility

Weakness:
- no shared data-grid system
- table density and column hierarchy vary
- mobile collapse patterns are not standardized

Candidates table is readable but under-emphasizes primary action and candidate state.

## Modals and drawers

Main SPA has a reasonably mature overlay layer:

- modals
- sheets
- drawers
- candidate insights/chat overlays

Strength:
- there is a real overlay system

Weakness:
- some candidate detail interactions rely on side drawers whose information density is too high for the visual contrast used

## Badges and chips

Many badge systems exist:

- channel chips
- status pills
- MAX/TG tags
- state chips
- filter pills

Strength:
- badges are used consistently as a language

Weakness:
- too many similar but not identical badge styles
- contrast and emphasis vary
- small labels become hard to scan in dark mode

## Navigation

Main SPA:

- desktop pill navigation in top shell
- mobile tab bar + more sheet

Strength:
- shell/navigation is custom and productized

Weakness:
- desktop nav labels are visually tiny
- shell chrome sometimes feels more decorative than functional
- unauthenticated routes can show a loader state rather than a clear auth decision

Telegram mini app:

- no comparable shared shell

MAX mini app:

- candidate-first, single-column task flow
- no shared system shell with SPA

## Light / dark theme

Proven:

- dark theme is default baseline
- light theme exists via `data-theme='light'`
- `liquid-glass-v2` can override additional UI mode behavior

Observed:

- many archived `ui_screenshots` show light theme variants
- current live authenticated runtime captured in test mode rendered dark-first admin surfaces

Conclusion:

- dark theme is the primary lived design language
- light theme exists, but current product identity feels more defined in dark mode

# 4. UI audit by page

## `/app/login`

Evidence:

- live screenshot: [audit-login-mobile.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/audit-login-mobile.png)
- code: [frontend/app/src/app/routes/app/login.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/login.tsx)

Purpose:

- admin/recruiter auth entry

What works well:

- compact single-purpose layout
- clear primary CTA
- visually aligned with dark shell language

What is weak:

- labels are visually present but not semantically bound to inputs
- helper copy is generic
- no explicit trust/status message
- no visible loading/error/state sophistication beyond inline text

What is overloaded:

- not overloaded

What is non-obvious:

- “legacy login page” link is technically useful but visually low-context

What blocks should be redesigned:

- input labeling/accessibility semantics
- error state block
- auth confidence/trust message
- secondary action explanation

## `/app`

Evidence:

- code: [frontend/app/src/app/routes/app/index.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/index.tsx)
- fresh live screenshot after auth: [live-app-home.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-app-home.png)

Purpose:

- current SPA landing

What works well:

- intentionally minimal

What is weak:

- placeholder-like page
- does not act as a meaningful home or operational landing

What is overloaded:

- not overloaded; under-designed instead

What is non-obvious:

- unclear why this route exists when dashboard is the real operational entry

What should be simplified:

- likely redirect or role-aware handoff to dashboard/incoming/candidates

## `/app/dashboard`

Evidence:

- live screenshot: [live-dashboard-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-dashboard-auth.png)
- screenshot artifact: [dashboard_smoke.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/ui/dashboard_smoke.png)
- code: [frontend/app/src/app/routes/app/dashboard.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/dashboard.tsx)

Purpose:

- recruiter/admin KPI overview and intake summary

What works well:

- coherent shell integration
- clearly grouped KPI and summary zones
- dashboard feels like part of a real ops product

What is weak:

- low contrast between containers and background
- too much empty dark space below content fold
- KPI cards and control tower area have similar emphasis

What is overloaded:

- filter + summary + KPI + leaderboard blocks compete on the same horizontal rhythm

What is non-obvious:

- first-action hierarchy is soft; user sees many “cards” but not one obvious next action

What should be redesigned:

- stronger section hierarchy
- clearer prioritization of urgent queue work
- tighter vertical rhythm
- more obvious empty-state messaging when data is sparse

## `/app/candidates`

Evidence:

- live desktop: [live-candidates-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidates-auth.png)
- live mobile: [live-candidates-mobile-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidates-mobile-auth.png)
- artifact: [01-candidates-list.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/max-pilot-browser/01-candidates-list.png)
- archived UI shots: [ui_screenshots/candidates__desktop__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/candidates__desktop__light.png), [ui_screenshots/candidates__mobile__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/candidates__mobile__light.png)
- code:
  - [frontend/app/src/app/routes/app/candidates.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidates.tsx)
  - [frontend/app/src/theme/pages/candidates.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages/candidates.css)

Purpose:

- main operational candidate database with list/kanban/calendar views

What works well:

- supports multiple operational representations
- channel chips help surface Telegram/MAX linkage
- new candidate CTA is visible
- filter model is functionally rich

What is weak:

- page opens with too many controls before the list itself
- AI recommendation block visually interrupts primary browsing flow
- small chip labels and muted borders reduce scan speed
- row-level primary action is too weak visually

What is overloaded:

- search
- pipeline filters
- view tabs
- linked channel filters
- preferred channel filters
- AI recommendation
- pagination
- per-page
- queue tags

All of this appears before or around the first row.

What is non-obvious:

- distinction between linked channel and preferred channel is not obvious enough
- “AI recommendation” appears as peer to core filtering, though it is secondary

What should be redesigned:

- compress filter hierarchy into primary vs advanced
- reduce control duplication
- promote row action clarity
- reduce badge/chip variety
- simplify mobile stacking and increase content-to-chrome ratio

## `/app/candidates/$candidateId`

Evidence:

- live desktop: [live-candidate-detail-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidate-detail-auth.png)
- live mobile: [live-candidate-detail-mobile-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidate-detail-mobile-auth.png)
- artifact: [02-candidate-detail.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/max-pilot-browser/02-candidate-detail.png)
- MAX card artifacts:
  - [03-max-pilot-card.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/max-pilot-browser/03-max-pilot-card.png)
  - [operator-candidate-detail-max-card.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/operator-candidate-detail-max-card.png)
- code:
  - [frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx)
  - [frontend/app/src/app/routes/app/candidate-detail/CandidateMaxPilotCard.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateMaxPilotCard.tsx)
  - [frontend/app/src/theme/pages/candidate-detail.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages/candidate-detail.css)

Purpose:

- primary candidate workspace

What works well:

- candidate detail is structured around lifecycle, scheduling, risks and context
- operator-facing MAX pilot visibility is useful
- screen already behaves like a real workflow workspace

What is weak:

- overall contrast is too low for such a dense workspace
- lifecycle visualization is visually subtle relative to its importance
- action center and channel/status badges do not strongly separate current state from next action
- mobile screenshot shows severe information compression

What is overloaded:

- profile
- lifecycle
- scheduling
- risks
- context/history
- overlays
- AI
- MAX rollout

The screen is feature-rich, but hierarchy is flatter than it should be.

What is non-obvious:

- next recommended operator action is not always visually dominant
- channel state, lifecycle stage and scheduling state are adjacent but semantically different

What should be redesigned:

- stronger “current status / next step / actions” triad
- improved mobile segmentation
- more explicit decision cards
- higher-contrast lifecycle and scheduling blocks

## `/app/slots`

Evidence:

- archived screenshot: [ui_screenshots/slots__desktop__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/slots__desktop__light.png)
- code: [frontend/app/src/app/routes/app/slots.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/slots.tsx)

Purpose:

- slot management and booking operations

What works well:

- feature depth is strong
- filters reflect real scheduling workflow complexity
- mobile-aware behavior exists in code

What is weak:

- visual density is likely very high
- controls are numerous before content
- likely same control-hierarchy problem as candidates

What is overloaded:

- status
- purpose
- search
- city
- recruiter
- candidate presence
- timezone relation
- date range
- sort
- pagination

What is non-obvious:

- advanced vs essential controls are not clearly separated in the code model

What should be redesigned:

- progressive disclosure for filters
- stronger booking/reschedule action hierarchy
- clearer empty / no-result / no-capacity messaging

Note:

- live render was not independently captured in this audit; assessment is based on code and archived screenshot evidence.

## `/app/recruiters`

Evidence:

- archived screenshot: [ui_screenshots/recruiters__desktop__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/recruiters__desktop__light.png)
- code: [frontend/app/src/app/routes/app/recruiters.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/recruiters.tsx)

Purpose:

- recruiter roster / load management

What works well:

- card-based overview is appropriate for staff roster
- utilization and city assignment are meaningful operational summaries

What is weak:

- light-theme screenshot shows very soft contrast and washed hierarchy
- cards are large and decorative relative to information density
- controls at the bottom compete with stats instead of following a clear footer hierarchy

What is overloaded:

- less overloaded than candidates, but each card contains many visual tokens

What is non-obvious:

- relationship between availability, load and nearest slot is readable but not prioritized cleanly

What should be redesigned:

- cleaner stat grouping
- better CTA alignment
- stronger hierarchy inside each card

## `/tg-app`

Evidence:

- code: [frontend/app/src/app/routes/tg-app/index.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/index.tsx)
- no independent live screenshot captured during this audit

Purpose:

- recruiter dashboard inside Telegram

What works well:

- minimal
- direct
- good for narrow Telegram task context

What is weak:

- completely separate visual grammar from SPA
- relies on inline styles rather than shared theme
- layout is simplistic and functionally narrow

What is overloaded:

- not overloaded

What is non-obvious:

- because it is so lightweight, it under-expresses product maturity compared with the main SPA

What should be redesigned:

- shared semantic status components
- better candidate/recruiter action emphasis
- closer alignment with main product language without breaking Telegram-native constraints

## `/tg-app/incoming`

Evidence:

- code: [frontend/app/src/app/routes/tg-app/incoming.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/incoming.tsx)

Purpose:

- quick triage of waiting candidates inside Telegram

What works well:

- single-purpose list
- candidate card entry is straightforward

What is weak:

- card visual language is generic
- waiting time, status and city are compressed into one metadata line
- no richer triage affordances

What is overloaded:

- not overloaded

What is non-obvious:

- candidate urgency and next best action are not visible enough

What should be redesigned:

- card hierarchy
- status prominence
- better urgency labeling

## `/tg-app/candidates/$candidateId`

Evidence:

- code: [frontend/app/src/app/routes/tg-app/candidate.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/tg-app/candidate.tsx)

Purpose:

- lightweight recruiter candidate detail in Telegram

What works well:

- concise
- status transitions are directly actionable

What is weak:

- very limited information architecture
- little visual distinction between static info and mutation controls
- does not feel connected to richer admin candidate workspace

What is overloaded:

- not overloaded

What is non-obvious:

- status changes are available, but downstream consequences are not obvious

What should be redesigned:

- stronger summary block
- clearer action grouping
- more explicit context for status changes

## `/miniapp` bounded MAX states

Evidence:

- code:
  - [frontend/app/src/app/routes/miniapp/index.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/miniapp/index.tsx)
  - [frontend/app/src/app/routes/miniapp/miniapp.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/miniapp/miniapp.css)
- screenshots:
  - [miniapp-home-next-step.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-home-next-step.png)
  - [miniapp-test1-in-progress.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-test1-in-progress.png)
  - [miniapp-booking-success.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-success.png)
  - [miniapp-booking-empty-slots.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-slots.png)
  - [miniapp-booking-empty-cities.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-cities.png)
  - [miniapp-booking-empty-recruiters.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-recruiters.png)
  - [miniapp-contact-required.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-contact-required.png)
  - [miniapp-manual-review.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-manual-review.png)
  - [miniapp-chat-ready.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-chat-ready.png)
  - [miniapp-booked-return-home.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booked-return-home.png)

Purpose:

- candidate-facing bounded pilot flow for launch, Test1, booking and follow-up states

What works well:

- strongest candidate-facing visual coherence in the repo
- clear single-column mobile rhythm
- strong CTA hierarchy
- good explicit empty-state and next-step treatment
- booking and follow-up cards feel more productized than Telegram mini app

What is weak:

- visually detached from the rest of the system
- separate token universe `--max-*`
- still dark and layered enough to risk contrast issues in smaller labels

What is overloaded:

- less overloaded than SPA

What is non-obvious:

- bounded pilot status is product-level knowledge, not UI-visible knowledge
- cross-channel continuity is not visually obvious to user

What should be redesigned:

- align semantic states with rest of system
- keep candidate-first UX, but harmonize typography, status patterns and tone with wider product

Note:

- this audit treats `/miniapp` as a real bounded pilot surface only, not as a full production MAX runtime.

# 5. UX / candidate flow audit

## Flow overview

Current candidate-facing logic is not yet channel-consistent as an end-user experience.

- Telegram is still historically dominant in the system model
- MAX mini app is more coherent as a candidate-first UI
- future standalone browser candidate flow remains target-state, not live mounted UI

## 1. Entry

Telegram:

- entry is channel-native
- candidate/recruiter experience is constrained by Telegram initData and lightweight UI

MAX:

- entry is more explicitly shaped around a dedicated mini app shell
- better “cabinet / next step / action” framing

Risk:

- channel entry semantics differ too much
- product feels different depending on channel

## 2. Authorization / identification

Confirmed findings:

- scripted login into local SPA works
- unauthenticated `/app/dashboard` and `/app/candidates` showed loader state instead of a clear redirect or unauthenticated guard
- login fields are not properly associated for automation/a11y label lookup

Candidate impact:

- on admin side, auth state handling is not explicit enough
- on candidate side, identity bootstrap across channels is more architectural than experiential; the UI does not yet strongly communicate continuity across entry methods

## 3. Test / questionnaire

Telegram:

- lightweight and transport-constrained

MAX:

- better form UX
- better pacing and continuation framing
- more product-like questionnaire experience

Gap:

- Test1 experience quality varies significantly by channel
- user expectations are not normalized

## 4. Booking

MAX evidence is strong:

- success state exists
- no slots / no recruiters / no cities states exist
- alternative time and chat CTA patterns exist

Strength:

- booking on MAX already has explicit failure branches and next-step fallback

Weakness:

- candidate booking semantics are clearer in MAX than in Telegram
- admin-side slots/candidates screens are still visually crowded and not obviously aligned to the same candidate mental model

## 5. Status visibility

Admin SPA:

- candidate detail exposes status, lifecycle and scheduling

Telegram mini app:

- status is present but simplified

MAX mini app:

- next-step and state cards are stronger and more understandable

Gap:

- same candidate state is communicated with different levels of richness and clarity across channels

## 6. Repeat entry / resume

Documented system intent supports resumeable candidate state, but the UI does not yet present a clearly unified cross-channel “resume your progress” mental model.

Risk:

- users may perceive MAX and Telegram as separate experiences rather than alternate shells over one journey

## 7. Errors

Observed issues:

- unauthenticated admin shell can sit in loader state
- some archived UI screenshots show internal server errors on pages such as `slots` or `questions`
- Telegram mini app errors are plain text blocks

Gap:

- error UX is inconsistent by surface
- product-grade recovery guidance is not standardized

## 8. Empty states

Strength:

- MAX empty states are explicit and actionable
- recruiters screen has a proper empty state in code

Weakness:

- main SPA often defaults to sparse panels with low-emphasis placeholders
- Telegram mini app empty states are minimal text only

## 9. Edge cases

Explicitly represented in MAX:

- contact required
- manual review required
- no cities
- no recruiters
- no slots
- booked return home
- chat handoff

This is good product thinking.

Weakness:

- these edge-case semantics are not echoed with equal maturity in other surfaces

## Where users can get confused

- when channel behavior differs more than status semantics
- when candidate next step is visible in MAX but flattened in Telegram
- when admin SPA shows multiple filters and chips before core action
- when auth behavior presents loader instead of explicit state

## Where users can drop off

- during entry/bootstrap ambiguity
- on overloaded operator screens where next action is visually weak
- in Telegram mini app where summaries are too compressed
- in low-contrast dark UI where small labels and chips lose importance

## Where transparency is missing

- cross-channel continuity
- difference between linked channel and preferred channel
- consequences of status transitions in lightweight surfaces
- auth/loading state reasoning on admin shell

# 6. Functional inconsistencies

## Code vs actual interface

- Mounted runtime is code-driven, and this audit followed that rule.
- The biggest functional UI mismatch observed live was auth-state behavior:
  - unauthenticated `/app/dashboard` and `/app/candidates` rendered loader state
  - not an explicit redirect or visible unauthorized message
- Login visually renders labels, but inputs are not semantically associated well enough for label-based automation lookup.

## Telegram flow vs MAX flow

- Telegram mini app is much simpler, more utility-like, and less productized.
- MAX mini app has a stronger candidate-first narrative, clearer state cards and clearer failure branches.
- As a result, candidate quality of experience differs by channel even when backend intent is shared.

## Between different pages in SPA

- Dashboard, candidates and candidate detail all use the same shell, but page-level information hierarchy is inconsistent.
- Candidates page is control-heavy before content.
- Candidate detail is content-heavy with weak hierarchy between “current state” and “possible actions”.
- Recruiters page uses large cards with lighter, softer visual emphasis than current dark runtime.

## Similar components behaving differently

- badges/chips/pills: multiple variants with different contrast and semantics
- action links vs buttons: not always clearly separated
- empty states: rich in some routes, bare text in others
- status surfaces: some are cards, some are pills, some are inline metadata
- Telegram mini app screens rely on inline styles rather than shared primitives, so similar concepts do not inherit the same UI behavior

# 7. Design debt

## Critical

- Auth shell behavior on unauthenticated protected routes shows loader instead of an explicit state.
- Login form labels are not properly associated for accessibility and reliable automation lookup.
- Cross-channel design system is fragmented: `/app/*`, `/tg-app/*`, `/miniapp` are not one coherent product language.
- Candidate detail page hierarchy is too weak for such a high-density decision screen.
- Candidates page front-loads too many controls before core data.

## Medium

- Badge/chip system is overly fragmented.
- Low-contrast dark surfaces reduce scan speed on dense recruiter screens.
- Telegram mini app feels technologically and visually like a fallback surface, not part of the same product.
- Main SPA uses too much decorative shell weight relative to operational hierarchy.
- Mobile candidate detail compresses too much information into too little width.

## Low

- `/app` landing route feels placeholder-like.
- Some light-theme archived screens look washed out and less intentional than current dark runtime.
- Recruiter/stat cards can be visually simplified.
- AI recommendation block placement on candidates page can be more tactically integrated.

## Priority for 24 hours

1. auth and route-state clarity
2. candidates list hierarchy
3. candidate detail hierarchy
4. mobile readability
5. chip/badge rationalization
6. Telegram/MAX semantic alignment at the UI layer

# 8. Quick wins for 24 hours

- Replace loader-only unauth shell behavior with explicit redirect or visible auth-required state.
- Fix login input labeling and error feedback.
- Split candidates filters into primary and advanced sections.
- Reduce chip count and unify badge styles on candidates page.
- Increase contrast and spacing in candidate detail’s key state blocks.
- Make “next action” the dominant visual unit in candidate detail.
- Tighten dashboard vertical rhythm and make empty KPI states more explicit.
- Improve mobile candidates layout to reduce chrome and increase row/card readability.
- Standardize empty/loading/error blocks across SPA and mini apps.
- Introduce one shared semantic status/badge grammar usable across `/app/*`, `/tg-app/*` and future candidate surfaces.

# 9. Concrete redesign recommendations

## Layout

- Reduce decorative shell weight and increase task-area clarity.
- On dense routes, visually subordinate shell chrome and promote content headers and primary action zones.
- Collapse non-essential filters behind advanced controls.

## Typography

- Increase small-label readability in dark mode.
- Use display type more selectively; keep operational text utilitarian and sharper.
- Normalize section-title scale across routes.

## Spacing

- Increase spacing between control clusters and data surfaces.
- Reduce stacked micro-gaps between chips, pills and meta lines.
- Give candidate detail stronger section separation.

## Hierarchy

- On every operational page, make these three things immediately obvious:
  - where I am
  - what is urgent
  - what I should do next

## Navigation

- Keep current custom shell, but reduce decorative emphasis on desktop nav.
- Enlarge label readability or simplify nav item density.
- Ensure protected routes never look like “still loading forever”.

## Buttons

- Strengthen primary button contrast in dense dark toolbars.
- Reduce pseudo-button links where action semantics matter.
- Normalize destructive vs secondary button treatment.

## Form UX

- Fix label/input semantics across all critical forms.
- Standardize inline errors, hints and empty input states.
- Use clearer grouping in filter bars so controls do not feel like raw fields.

## Cards

- Reduce number of card grammars.
- Establish one standard for:
  - hero/info panel
  - KPI card
  - decision card
  - empty state card

## Tables

- Increase visual separation between table header, row identity and row action zones.
- Standardize row priority so candidate identity and next action dominate.

## Empty states

- Promote empty states from plain text to guided decision surfaces.
- Reuse MAX-style actionable empty-state clarity in SPA where appropriate.

## Loading states

- Replace ambiguous loader screens with more contextual loading/skeleton states.
- Distinguish:
  - initial auth check
  - page data loading
  - action in progress

## Error states

- Make errors more explicit and more actionable.
- Avoid raw or low-context server failure displays.
- Ensure channel-specific failures always have a next action.

## Mobile adaptation

- Reduce header/chrome overhead on mobile lists.
- Give cards more breathing room and fewer stacked secondary chips.
- Rebuild candidate detail mobile segmentation into clearer tabs or stronger section cards.

# 10. Screenshot map

## Fresh live captures created in this audit

- [audit-login-mobile.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/audit-login-mobile.png) — mobile login screen
  - proves live login layout and button hierarchy
- [live-dashboard-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-dashboard-auth.png) — authenticated dashboard
  - proves current dark shell, KPI spacing, empty dashboard state
- [live-candidates-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidates-auth.png) — authenticated candidates desktop
  - proves current filter overload and table/CTA hierarchy
- [live-candidate-detail-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidate-detail-auth.png) — authenticated candidate detail desktop
  - proves density and weak hierarchy in high-value workspace
- [live-candidates-mobile-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidates-mobile-auth.png) — authenticated candidates mobile
  - proves mobile stacking and chrome-to-content ratio
- [live-candidate-detail-mobile-auth.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/live-candidate-detail-mobile-auth.png) — authenticated candidate detail mobile
  - proves severe compression on small widths
- [audit-dashboard.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/audit-dashboard.png) — unauthenticated dashboard route state
  - proves loader-only protected-route behavior without session
- [audit-candidates.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/audit-candidates.png) — unauthenticated candidates route state
  - same issue for candidate list
- [audit-candidates-mobile.png](/Users/mikhail/Projects/recruitsmart_admin/output/playwright/audit-candidates-mobile.png) — unauthenticated candidates mobile
  - same issue on mobile shell

## Existing evidence used

- [ui_screenshots/candidates__desktop__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/candidates__desktop__light.png) — archived light-theme candidates screen
- [ui_screenshots/candidates__mobile__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/candidates__mobile__light.png) — archived mobile candidates
- [ui_screenshots/recruiters__desktop__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/recruiters__desktop__light.png) — archived recruiters screen
- [ui_screenshots/slots__desktop__light.png](/Users/mikhail/Projects/recruitsmart_admin/ui_screenshots/slots__desktop__light.png) — archived slots screen
- [artifacts/verification/max-pilot-browser/01-candidates-list.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/max-pilot-browser/01-candidates-list.png) — operator candidates with MAX context
- [artifacts/verification/max-pilot-browser/02-candidate-detail.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/max-pilot-browser/02-candidate-detail.png) — operator candidate detail
- [artifacts/verification/max-pilot-browser/03-max-pilot-card.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/max-pilot-browser/03-max-pilot-card.png) — operator MAX pilot card
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/operator-candidate-detail-max-card.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/operator-candidate-detail-max-card.png) — operator MAX card variant
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-home-next-step.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-home-next-step.png) — MAX home/next-step
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-test1-in-progress.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-test1-in-progress.png) — MAX questionnaire state
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-success.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-success.png) — MAX booking success
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-slots.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-slots.png) — MAX no slots state
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-cities.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-cities.png) — MAX no cities state
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-recruiters.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booking-empty-recruiters.png) — MAX no recruiters state
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-contact-required.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-contact-required.png) — MAX contact capture requirement
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-manual-review.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-manual-review.png) — MAX manual review state
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-chat-ready.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-chat-ready.png) — MAX chat handoff state
- [artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booked-return-home.png](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/screenshots/miniapp-booked-return-home.png) — MAX return-home/booked state

# 11. Next implementation plan

## Do first

- Fix auth-shell UX on protected routes.
- Fix login label semantics and error states.
- Rebuild candidates page control hierarchy.
- Promote candidate detail “current status / next step / actions” structure.
- Improve mobile candidates and candidate detail readability.

## Do next

- Rationalize chips/badges/status pills into one semantic set.
- Standardize empty/loading/error states across admin SPA.
- Harmonize Telegram mini app status/action grammar with main product semantics.
- Reuse MAX-quality empty-state clarity in operator-facing surfaces where appropriate.

## Safe changes

- typography scale tuning
- spacing/rhythm adjustments
- button hierarchy
- filter-bar restructuring
- empty/loading/error states
- form semantics
- badge/chip reduction
- mobile polish inside existing route structure

## Medium-risk changes

- shell simplification
- candidate detail information architecture refactor
- cross-channel token harmonization at presentation layer
- shared component primitive adoption for Telegram-like surfaces

## Risky changes

- auth-shell behavior changes that alter guard timing
- candidate journey contract changes
- Telegram/MAX semantic unification that leaks into backend/business logic
- any attempt to represent unsupported future browser candidate flow as live surface

## Validation outcomes captured in this audit

- `npm --prefix frontend/app run typecheck` passed
- `npm --prefix frontend/app run test` passed
- `npm --prefix frontend/app run build:verify` passed
- local `admin_ui` was started on test runtime with seeded data
- scripted login into local SPA worked
- unauthenticated `/app/dashboard` and `/app/candidates` showed loader state instead of explicit auth UX
- login form inputs do not expose correct label association for automation lookup

## Assumptions and defaults used

- This report does not propose backend contract rewrites.
- Mounted runtime truth came from code, not target-state docs.
- Future browser candidate portal was not treated as a live screen.
- Screens not proven via live render are explicitly marked as code/screenshot-based evidence.
- MAX mini app was treated as bounded pilot only, not as full production runtime.

---

## Top 10 changes I would implement in the next 24 hours

1. Replace protected-route loader-only behavior with explicit auth redirect or “login required” state.
2. Fix login input labeling and add clearer inline error/success/loading semantics.
3. Cut candidates page top-of-page controls by separating primary filters from advanced filters.
4. Make candidate row “next action” visually dominant over supporting metadata.
5. Rebuild candidate detail header into three fixed zones: status, next action, actions.
6. Increase contrast and text size for small chips, pills and secondary metadata in dark mode.
7. Reduce shell visual dominance so operational content beats decorative nav chrome.
8. Standardize empty/loading/error state components and apply them across dashboard, candidates and Telegram mini app.
9. Rework mobile candidate detail into clearer stacked sections or stronger tab segmentation.
10. Introduce one shared semantic badge/status language and use it consistently across admin SPA, Telegram mini app and MAX-adjacent operator surfaces.
