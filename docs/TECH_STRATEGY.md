# Liquid Glass v2 Frontend Strategy

## Token governance
- All design tokens live in [`backend/apps/admin_ui/static/css/tokens.css`](../backend/apps/admin_ui/static/css/tokens.css).
- Keep the neutral and role palettes in sync with Liquid v2 (`--bg`, `--surface-*`, `--text`, `--muted-text`, `--success`/`--info`/`--warn`/`--danger`).
- Add new tokens as CSS custom properties; avoid redefining primitives inside page CSS.
- When changing token names or semantics, update Tailwind config (`tailwind.config.js`) and documentation in the same commit.

## Utility surface
- Core utilities live in [`main.css`](../backend/apps/admin_ui/static/css/main.css) under `@layer components`.
- Reuse `.glass`, `.panel`, `.card`, `.pill`, `.badge-*`, `.btn` variants, and shared grid helpers before inventing new bespoke selectors.
- If a new pattern repeats 3+ times, promote it into a utility class instead of copy/pasting declarations.
- Keep motion subtle: respect `prefers-reduced-motion` and wire new transitions into the existing variables (`--transition-fast`, `--transition-base`).

## Contrast & focus
- Every interactive element must surface `:focus-visible` using the shared ring (utility `.focus-ring` or dedicated selectors).
- Check contrast for pills, badges, and chips against AA (>4.5:1). If contrast is low, increase opacity or mix toward darker tones rather than darkening text arbitrarily.
- Prefer semantic colors (`--success-rgb`, `--info-rgb`, etc.) with alpha adjustments over hard-coded hex values in component CSS.

## Build discipline & budgets
- `make ui` rebuilds CSS; run it when token or utility changes land.
- Bundle budget: **≤ 90 KB raw** and **≤ 70 KB gzip** per shipped CSS artifact. Track compliance in [`audit/CSS_SIZE.md`](../audit/CSS_SIZE.md).
- Remove unused selectors when refactoring; rely on the shared utilities instead of adding page-specific overrides.

