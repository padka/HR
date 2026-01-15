# QA Visual Smoke

## A11y smoke

- Criteria: 0 critical/serious accessibility violations detected by axe-core.

## Keyboard A11y (focus trap, ESC)

- Sheets and modals move focus inside when opened and keep focus cycling with Tab/Shift+Tab.
- Pressing Escape closes the sheet/modal and restores focus to the trigger element.
- Covered by Playwright specs in `tests/e2e/focus.slots.spec.ts` and `tests/e2e/focus.cities.spec.ts`.
