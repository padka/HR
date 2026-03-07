# UI_PRINCIPLES_AND_LAYOUT_PATTERNS

## Purpose
- This document translates audit findings into practical UI principles and layout patterns for Codex App.
- It is intentionally opinionated: RecruitSmart Admin should feel like a premium operating system for recruiting, not a gallery of glass cards.

## What Good Looks Like For This CRM
- The interface communicates urgency, status and next actions in under three seconds.
- The UI feels calm under high data density.
- Filters and actions are predictable across screens.
- Mobile flows preserve critical actions instead of exposing compressed desktop leftovers.
- Visual depth helps navigation, not decoration.

## Core Design Principles
1. Clarity over decoration.
2. Premium depth without noise.
3. Data density with breathing space.
4. Primary action first, analytics second.
5. Reuse before local invention.
6. Mobile is a separate workflow layer.
7. Motion must explain, not entertain.
8. System status is always visible.
9. Accessibility is a visible part of the design.
10. CRM speed wins over visual novelty.

## Premium SaaS Visual System Rules
- Use glass selectively. Dense work surfaces prefer quieter glass or raised opaque surfaces.
- Use one clear elevation ladder:
  - base surface for page backgrounds
  - raised for cards and sections
  - floating for sticky utility or transient controls
  - overlay for sheets, modals, toasts
- Avoid multi-layer glow on tables, long forms and chat areas.
- Typography should increase hierarchy before color does.
- Borders should do more work than shadows on operational screens.

## Layout Patterns
### Page Shell
- Every page starts with one hero/header zone.
- The hero handles page title, subtitle, top-level KPIs or actions.
- Everything below uses sections with repeated internal rhythm.

### Section Pattern
- Section head: title, helper line, section-level actions.
- Section body: one primary content type only.
- Avoid mixing summary metrics, filters, data table and side panel in the same visual container unless the layout is explicitly split.

### Toolbar Pattern
- Search, filters, view toggles and bulk actions follow a stable order.
- Toolbar wraps predictably on tablet.
- On mobile, filters and secondary actions move to sheet/accordion when necessary.

### Data-Heavy List Pattern
- Desktop:
  - filters above the table
  - state counters and bulk actions stay close to the list
  - row actions are stable in position
- Tablet:
  - reduce column count first
  - keep primary metadata visible
- Mobile:
  - transform rows into cards or stacked list items
  - keep title, status, primary meta and primary action above the fold

### Detail Route Pattern
- Candidate detail and similar screens should use:
  - hero with identity and primary actions
  - compact summary strip
  - section stack for secondary domains
  - mobile tab or segmented access only when it reduces scanning cost

### Split Pane Pattern
- Messenger and similar views use split panes only when both panes are useful at once.
- On mobile, thread list and conversation become sequential steps, not a compressed split pane.

### Long Form Pattern
- Use titled sections with short helper copy.
- Group fields by decision domain, not by backend model shape.
- Keep save action predictable and visible.
- Summaries or sidecards are secondary, not equal in prominence to form fields.

## Layout Patterns By Product Domain
### Dashboard And KPI Pages
- One summary hero.
- A small number of high-signal metric cards.
- One operational panel per section.
- Avoid equal-weight blocks everywhere; the work queue must dominate decorative stats.

### Queue And Pipeline Pages
- Filters and counters should feel like control rails, not decorative chips.
- Cards or rows must reveal next-step actions immediately.
- Status colors should be supplemented by text and icon cues.

### Calendar And Scheduling
- Desktop can remain grid-heavy.
- Mobile needs mode reduction, fewer simultaneous controls and stronger task drill-down.
- Scheduling overlays should be sheet-first on mobile.

### Configuration And Admin
- Favor quiet panels, strong labels, tighter spacing and explicit save lifecycle.
- Long-form pages should not inherit dashboard-level ambience.

## Mobile-First Principles
- Reachability beats symmetry.
- Sticky elements must earn their place.
- One primary action per viewport.
- Back navigation, close actions and route titles stay in fixed predictable locations.
- Any table that requires horizontal scroll on mobile must justify itself. Default answer: convert it.

## Motion Principles For Productivity Tools
- Motion should only do four jobs:
  - show spatial transition
  - confirm interaction
  - reveal additional controls
  - explain state change
- Motion must not do these jobs:
  - constantly animate background on data-heavy pages
  - add flourish to repeated list/table actions
  - hide poor hierarchy

## Interaction Principles
- Hover is subtle and faster than focus.
- Focus is explicit and higher contrast than hover.
- Disabled looks inert but readable.
- Pending states are local and contextual.
- Success feedback is brief and non-blocking.
- Error feedback preserves context and next step.

## Accessibility Principles
- Contrast is non-negotiable even on glass surfaces.
- Focus indicators should not rely on low-opacity rings.
- Semantic state must not depend on color only.
- Scrollable interactive regions need keyboard logic.
- Reduced motion should preserve meaning, not remove clarity.

## Patterns To Avoid
- Global ambient motion on every route.
- Multiple competing cards with equal visual weight.
- Wide decorative hero blocks on operational pages with no action value.
- Shrinking desktop tables into unusable mobile tables.
- Mixed filter and content containers with no stable hierarchy.
- Inline style decisions for layout, spacing, type scale or state tone.
- Sticky elements that overlap content without visual separation.
- Modal-over-modal and sheet-over-sheet nesting.

## Codex App Implementation Notes
- Prefer evolving existing contracts in:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/mobile.css`
  - `frontend/app/src/theme/material.css`
- Treat `frontend/app/src/theme/global.css` as a debt hotspot to split, not as the place for new one-off rules.
- Start with shell and page primitives before editing individual screens.
