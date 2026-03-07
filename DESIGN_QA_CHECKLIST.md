# DESIGN_QA_CHECKLIST

## How To Use
- Run this checklist after each major implementation block.
- Validate on desktop, tablet and mobile.
- Use both admin and recruiter roles where access differs.

## Shell
- Verify desktop navigation is readable and stable.
- Verify mobile header shows correct title and back behavior.
- Verify mobile tab bar keeps primary destinations reachable.
- Verify "More" sheet opens, traps focus and fully disappears when closed.
- Verify toasts do not cover bottom navigation or primary CTA.

## Visual Consistency
- Verify page heroes share one visual grammar.
- Verify section containers share one elevation and border logic.
- Verify typography hierarchy is consistent between overview, list, detail and form screens.
- Verify glass treatment is quieter on dense operational pages than on overview pages.
- Verify states, badges and chips use consistent tone semantics.

## Responsive Behavior
- Check widths:
  - 1440
  - 1280
  - 1024
  - 768
  - 390
  - 375
  - 320
- Check short viewport heights.
- Check browser zoom at 90%, 110% and 125% on critical screens.
- Check there is no unintended horizontal scroll.
- Check sticky elements do not overlap actionable content.

## Recruiter Daily Ops
- `/app/incoming`: filter, expand notes, open scheduling flow, submit and cancel.
- `/app/slots`: filter, bulk-select, remind/delete, open detail, mobile card actions.
- `/app/slots/create`: create one slot and a series, verify timezone preview.
- `/app/candidates`: search, filter, switch views, open candidate detail, delete or move where allowed.
- `/app/candidates/$candidateId`: inspect hero, pipeline, AI, slots, tests, reports, messaging and overlays.
- `/app/messenger`: search thread, open thread, send message, file/task flow, recover from error.
- `/app/calendar`: switch views, filter, create and edit task, close overlays.

## Admin Screens
- `/app/dashboard`: verify metric hierarchy and readability.
- `/app/profile`: save settings, upload or delete avatar, review KPI panels.
- `/app/cities` and `/app/cities/new`: browse, search, create, recruiter selection.
- `/app/cities/$cityId/edit`: long-form section readability, sticky save, linked entities.
- `/app/recruiters`, `/app/recruiters/new`, `/app/recruiters/$recruiterId/edit`: roster, creation, editing, destructive actions.
- `/app/templates*`, `/app/questions*`, `/app/message-templates`: library flows, previews, edit/create consistency.
- `/app/system`: tabs, filters, logs, reminder policy, delivery tables.
- `/app/test-builder*`: list mode, graph mode, preview/editor states.
- `/app/detailization`, `/app/copilot`, `/app/simulator`: utility/admin readability and mobile safety.

## Mobile Usability
- Verify one-handed reachability for primary actions where practical.
- Verify bottom-safe action areas are not hidden behind browser UI.
- Verify sheets are preferred over deep modal stacks where implemented.
- Verify list cards expose title, status and main action without expansion.
- Verify long forms remain usable with virtual keyboard open.

## State Handling
- Loading state looks intentional and scoped to the right container.
- Empty state explains what to do next.
- Error state preserves context and retry path.
- Success feedback is visible but does not block workflow.
- Pending state is near the action origin.
- Disabled state is readable and understandable.

## Accessibility
- Complete keyboard-only pass on shell and critical flows.
- Verify focus-visible on links, buttons, form fields, tabs, cards and menus.
- Verify overlay open/close focus management.
- Verify headings and landmarks form a logical structure.
- Verify color is not the only status cue.
- Verify touch targets remain large enough on mobile.

## Motion
- Verify route transitions are quick and consistent.
- Verify overlays animate in and out cleanly.
- Verify filter expansion does not feel janky.
- Verify hover and active feedback are subtle, not flashy.
- Verify reduced-motion mode removes decorative motion while preserving clarity.

## Regression Notes
- Capture any page-local inline-style workaround that appears during implementation.
- Track any z-index escalation added outside token ladder.
- Track any mobile-only action that lacks desktop or tablet parity, or vice versa.
