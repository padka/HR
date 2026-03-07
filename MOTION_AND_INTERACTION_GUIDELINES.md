# MOTION_AND_INTERACTION_GUIDELINES

## Purpose
- Define a motion language that supports premium feel without slowing down operator workflows.
- Keep implementation CSS-first and consistent with existing motion tokens and reduced-motion support.

## Motion Principles
1. Motion must explain state or spatial change.
2. Motion must never compete with data reading.
3. The more operational the screen, the quieter the motion.
4. Decorative motion is opt-in and route-specific.
5. Reduced-motion users get clarity, not abrupt UI.

## Motion Hierarchy
### Essential Motion
- Overlay enter/exit.
- Route transition on mobile.
- Expand/collapse for filters or disclosures.
- Press, hover and focus feedback on controls.

### Supportive Motion
- Card or section reveal on first load.
- Toast appearance/disappearance.
- Sort or selection emphasis in lists.

### Decorative Motion
- Background ambience, floating bubbles, sheen or subtle parallax.
- Only allowed on overview, login, empty/demo contexts.
- Not allowed as a default on data-heavy routes.

## Required Timings
- 120ms:
  - active press feedback
  - small hover transitions
  - icon state changes
- 180ms:
  - menus
  - filter chips
  - inline state reveals
- 280ms:
  - sheets
  - dialogs
  - route transitions
  - larger section reveals

## Easing Rules
- Standard easing for everyday state changes.
- Emphasized easing for overlays and route transitions only.
- No bouncy easing in CRM-operational flows.

## Motion By Surface Type
### Shell
- Mobile route transitions can use slide/fade but remain short and predictable.
- Header and tab bar should not animate continuously.

### Overlays
- Backdrop fades.
- Surface slides or lifts a short distance.
- Closed state is fully removed from interaction tree after exit.

### Glass Surfaces
- Animate opacity, transform and shadow subtly.
- Avoid animating blur radius aggressively.
- Glass layers should move less than their content.

### Lists And Tables
- No row-by-row flourish on every update.
- Use simple emphasis for selection, filter application and bulk state.

### Cards
- Hover: subtle raise or border contrast.
- Active: quick press-in.
- Loading: skeleton or local shimmer, never whole-page pulsing noise.

### Filters
- Replace `max-height` feel with more deliberate opacity/transform/clip strategy in implementation.
- Advanced filters should open with clear directional logic and close fast.

## Interaction Feedback
### Hover
- Slight contrast or elevation increase.
- No bright glow on dense operational screens.

### Active
- 120ms press feedback.
- Buttons and icon buttons should feel firm, not rubbery.

### Focus
- Focus ring must be more explicit than hover.
- Focus should survive glass backgrounds and mixed themes.

### Disabled
- Clear visual reduction, but readable labels.
- Avoid disabled states that look like missing controls.

### Pending
- Local spinners or text substitutions near action origin.
- Do not freeze large panels unless necessary.

### Success
- Short toast or inline confirmation.
- Avoid modal success interruptions.

### Error
- Inline error near source plus optional global banner or toast.
- Preserve entered data and current context.

## Screen-Specific Motion Guidance
### Dashboard
- Small reveal on summary cards and leaderboard blocks.
- No constant ambient motion on metric surfaces.

### Incoming
- Filter reveals should be quick.
- Queue item expansion should feel immediate and stable.

### Slots And Candidates
- View switching can use gentle fade/translate between list and alternate views.
- Drag states in kanban need clear drop affordance, not flourish.

### Candidate Detail
- Section transitions must be minimal; content is already dense.
- AI panels may use subtle progressive disclosure.

### Messenger
- Thread change should preserve continuity without flashy animation.
- New messages may animate in lightly once, not pulse.

### Calendar
- Event and task overlays should feel crisp.
- Large calendar view transitions should remain restrained.

## Reduced Motion Contract
- Existing reduced-motion support in `frontend/app/src/theme/motion.css:1-165` remains mandatory.
- Decorative background motion is disabled.
- Large transforms become opacity-only or instant.
- Route transitions shorten significantly.
- Sheet and dialog transitions remain understandable but simplified.

## Anti-Patterns To Avoid
- Continuous ambient motion on every route.
- Long easing on repeated operational interactions.
- Simultaneous motion of header, content and background.
- Large blur animation during open/close.
- Layout-jank animation based on `height: auto` or unstable `max-height`.

## Implementation Notes For Codex App
- Keep motion tokens in `tokens.css`.
- Keep shared transition classes in `motion.css`.
- Bind motion behavior to component primitives, not per-screen patches.
- Validate all overlay motions with keyboard and reduced-motion flows.
