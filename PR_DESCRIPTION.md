# Liquid Glass UI Migration

## Summary
- Introduced design tokens (`tokens.css`) with light/dark palettes, blur and noise presets.
- Added Tailwind toolchain with custom config, generated `globals.css` to restyle navigation, tables, forms and feedback surfaces.
- Documented design principles (`DesignSystem.md`) and audit findings (`Audit.md`).

## Rollout
1. Install Node dev deps: `npm install`.
2. Build CSS bundle: `npm run build:css` (generates `backend/apps/admin_ui/static/css/globals.css`).
3. Restart FastAPI app to load new assets.

## Regression checklist
- [ ] Dashboard metrics and tables render with glass layering.
- [ ] Recruiter/cards, list toolbars and filters keep spacing in both themes.
- [ ] Forms support keyboard navigation and visible focus states.
- [ ] Toasts/modals inherit glass styling.
- [ ] Theme toggle persists preference across reloads.
