# Liquid Glass v2 Frontend Strategy

## Token governance
- Design tokens live in `frontend/app/src/theme/tokens.css`.
- `frontend/app/src/theme/global.css` is the import shell and compatibility layer; it should not become a second source of truth for tokens.
- Mobile-only token overrides live under `@media` blocks in `tokens.css`, while behavioral mobile overrides belong in `mobile.css`.
- Keep the neutral and role palettes in sync with Liquid v2 (`--bg`, `--surface-*`, `--text`, `--muted-text`, `--border`). Accent roles live under `--accent-{success,info,warn,danger}` with matching `*-rgb` triplets.
- Add new tokens as CSS custom properties; avoid redefining primitives inside page CSS.
- When changing token names or semantics, update the SPA theme layer and documentation in the same commit.

## Theme system
- Themes are expressed through CSS custom properties on `:root[data-theme="light|dark"]`; omitting the attribute enables auto mode that follows `prefers-color-scheme`.
- `window.TGTheme.apply('light'|'dark'|'auto')` is the single entry point for runtime changes. It updates the DOM attribute, syncs `localStorage['tg-admin-theme']`, and notifies listeners.
- Liquid glass relies on shared tokens: `--glass-alpha{,-strong,-soft}`, `--glass-blur-{xs,sm,lg}`, and `--glass-highlight`. Always derive new gradients from those primitives so both themes stay in sync.
- Borders and shadows must respect the role tokens. Use `color-mix` with `var(--border)`/`var(--surface-*)` instead of hard-coded RGBA values when tweaking utilities.

## Utility surface
- Shared utilities are split across `components.css`, `pages.css`, `motion.css`, and `mobile.css`, imported via `global.css`.
- Reuse `.glass`, `.panel`, `.card`, `.pill`, `.badge-*`, `.btn` variants, and shared grid helpers before inventing new bespoke selectors.
- If a new pattern repeats 3+ times, promote it into a utility class instead of copy/pasting declarations.
- Keep motion subtle: respect `prefers-reduced-motion` and wire new transitions into the shared motion tokens and keyframes in `motion.css`.

## Contrast & focus
- Every interactive element must surface `:focus-visible` using the shared ring (utility `.focus-ring` or dedicated selectors).
- Check contrast for pills, badges, and chips against AA (>4.5:1). If contrast is low, increase opacity or mix toward darker tones rather than darkening text arbitrarily.
- Prefer semantic colors (`--success-rgb`, `--info-rgb`, etc.) with alpha adjustments over hard-coded hex values in component CSS.

## Build discipline & budgets
- `npm --prefix frontend/app run build:verify` is the baseline frontend gate for bundling changes.
- Bundle budgets are checked by `frontend/app/scripts/check-bundle-budgets.mjs`; adjust budgets deliberately and in the same commit as the change that requires them.
- Keep CSS payloads lean; remove unused selectors when refactoring and reuse shared utilities.
