# RESPONSIVE_STRATEGY

## Breakpoint Policy
- `1280`: large desktop compression.
- `1024`: laptop/tablet landscape adjustments.
- `768`: primary mobile switch.
- `640/480`: compact mobile refinements.

## Ownership Rule
- Mobile overrides размещаются в `frontend/app/src/theme/mobile.css`.
- Page-level responsive compositions определяются через shared/mobile classes, а не inline-style.

## Mobile UX Standards
- Bottom tab bar + safe-area.
- Sticky mobile header.
- Table -> card fallback on constrained width.
- Touch targets >= 44px на mobile controls.
- No horizontal overflow for `390`/`375`/`768` layouts.

## Verification Matrix
- Desktop: `1440`, `1280`.
- Tablet: `1024`, `768`.
- Mobile: `390`, `375`.
