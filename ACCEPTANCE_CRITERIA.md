# ACCEPTANCE_CRITERIA

## Global Acceptance Criteria
- Route map and path structure remain unchanged.
- Core recruiter and admin business logic remains intact.
- All redesign work maps to mounted SPA scope only unless backlog is explicitly activated.
- Lint, tests and build remain green after implementation phases.

## Phase 1. Audit Package
- All required root artifacts exist.
- Screen map covers all 31 mounted routes.
- Audit cites real code locations.
- Roadmap is file-aware and implementation-oriented.
- Executive summary contains required verdicts and ranked issue/improvement lists.

## Phase 2. Foundation Layer
- Shared page and surface contracts are present in theme files.
- Decorative ambience is opt-in for overview/login/demo contexts only.
- Tokens remain the single source of truth for spacing, radii, color, blur, motion and z-index.
- New redesign work does not introduce new inline spacing/layout/type values in route files.

## Phase 3. Shell And Navigation
- Closed mobile "More" sheet is not an active dialog, not focusable and not visible in viewport.
- Opening a sheet or modal applies scroll lock and focus management consistently.
- Header, tab bar, sheet and toast do not collide across target mobile viewports.
- Desktop, tablet and mobile all preserve clear page titles and contextual navigation.

## Phase 4. Recruiter-First Screens
### Dashboard
- KPI, leaderboard and queue blocks have clear visual priority.
- Dashboard remains readable without decorative overload.

### Incoming
- Queue actions are reachable on desktop and mobile.
- Filter controls remain understandable when wrapped or collapsed.
- Scheduling flow preserves context and feedback.

### Slots
- Mobile card view covers all critical actions represented in table view.
- Bulk action state is clear and non-destructive by accident.
- No horizontal overflow in critical slot states.

### Candidates
- Search, filter and view switch hierarchy is obvious.
- List, kanban and calendar have consistent status language.
- Mobile list is usable without relying on desktop table.

### Candidate Detail
- Hero, pipeline actions and major sections have a readable order.
- Mobile remains a full-route drill-down experience.
- Interactive scroll regions are keyboard accessible.

### Messenger
- Thread list and conversation hierarchy are clear.
- Mobile thread-to-chat flow is understandable and recoverable.
- Send errors and task flows preserve context.

### Calendar
- Task creation and editing remain usable on tablet and mobile.
- Mobile view modes are limited to readable, useful options.

## Phase 5. Mobile-First Pass
- No critical action is blocked at widths 320px and above.
- No horizontal overflow in critical recruiter flows.
- Sticky elements do not cover actionable content.
- Filters, drawers, sheets and modals remain reachable and dismissible.
- Safe-area padding works on devices with bottom inset.
- Virtual keyboard does not permanently hide primary submit actions.

## Phase 6. Admin And Long-Form Screens
- Forms are grouped into clear sections with readable labels and helper text.
- Save, validation and error feedback are consistent across admin screens.
- Wide tables are either transformed or intentionally wrapped with preserved usability.
- Mobile versions are readable and navigable, not just compressed.

## Accessibility Acceptance Criteria
- Focus-visible states are visible on all interactive elements.
- Landmark structure is explicit on shell and major screens.
- Status is not communicated by color alone.
- Closed overlays are not present in the accessibility tree.
- Reduced-motion mode preserves usability and context.
- Touch targets remain at or above 44px where applicable.

## Motion Acceptance Criteria
- Motion uses the approved duration ladder: 120ms, 180ms, 280ms.
- No decorative motion is applied on dense operational routes by default.
- Overlay and route transitions are consistent and predictable.
- No janky height-based reveals remain in critical controls after redesign.

## Responsive Acceptance Criteria
- Verified widths:
  - 1440
  - 1280
  - 1024
  - 768
  - 390
  - 375
  - 320
- Verified short-height and browser zoom scenarios on critical screens.
- No header, tab bar, sheet or floating action collisions on verified viewports.

## Performance Acceptance Criteria
- No redesign block introduces perceptible lag in common tasks.
- Background or decorative effects do not dominate paint cost on operational routes.
- Route-level code splitting remains intact.

## Visual QA Acceptance Criteria
- Shared page primitives are used consistently.
- Surface elevation and border language is coherent.
- Typography hierarchy is consistent.
- Decorative chrome never outranks primary actions or important statuses.

## Testing Acceptance Criteria
- Required implementation validation:
  - `npm run lint`
  - `npm run test`
  - `npm run build:verify`
- Recommended additional validation in implementation phases:
  - route smoke tests
  - a11y checks
  - mobile shell checks
