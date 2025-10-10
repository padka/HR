# Liquid Glass v2 — Design System Strategy

## Token governance
- Source of truth lives in `backend/apps/admin_ui/static/css/tokens.css`.
- Additions must express values as CSS custom properties with semantic names (roles, surfaces, typography, motion).
- Always expose RGB triplets for colors so Tailwind theme extensions (`tailwind.config.js`) can read them via `rgb(var(--token) / <alpha>)`.
- When introducing new roles, document their intent and dual light/dark values; avoid ad-hoc hex literals in templates.
- Preserve backwards-compatible aliases only when migrating existing views—remove once consumers adopt the new tokens.

## Utility layer
- Shared utilities belong in `backend/apps/admin_ui/static/css/main.css` inside the `@layer components` block.
- Prefer composable primitives (`.glass`, `.panel`, `.card`, `.pill`, `.btn`, `.badge-*`) over page-specific selectors.
- Keep motion subtle (`var(--transition-snap)`) and honor `prefers-reduced-motion`—wire all interactive transitions through the helper.
- Use CSS variables for focus colors and glows so variants inherit the same Liquid Glass “physics”.

## Layout & responsiveness
- `app-shell` drives responsive behavior: top header on ≥1024 px, icon rail between 768–1023 px, burger overlay below 768 px.
- Content containers should align to the grid (`.container > * { grid-column: 1 / -1; }`) and rely on utility classes instead of hard-coded widths.
- When adding new regions, scope them under the existing breakpoints to keep the notebook/tablet/phone model consistent.

## Accessibility & contrast
- Apply visible focus via the shared `.focus-ring` contract (`outline` with accent color). Extend via `--focus-ring-color` for variant states.
- Badge and pill backgrounds must meet WCAG AA against both light and glassy surfaces; increase alpha or switch to darker text when in doubt.
- Inputs and buttons should remain keyboard-accessible; test flows with Tab/Shift+Tab after each UI change.

## Performance budget
- CSS bundle budget: ≤ 90 KB raw / ≤ 70 KB gzip.
- Rebuild with `npm run build:css` and record output sizes in `audit/CSS_SIZE.md` on each structural change.
- If the bundle grows, dedupe utilities before adding new selectors; prefer extending existing tokens to introducing bespoke rules.
