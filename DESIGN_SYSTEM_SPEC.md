# DESIGN_SYSTEM_SPEC

## Token Source of Truth
- Единственный источник: `frontend/app/src/theme/tokens.css`.
- Layers: `tokens -> material -> motion -> components -> pages -> mobile`.

## Core Token Groups
- Breakpoints: `1280 / 1024 / 768 / 640 / 480`.
- Spacing: `--space-xs .. --space-3xl`.
- Radius: `--radius-xs .. --radius-2xl`.
- Motion: `--motion-fast/base/slow`, `--ease-standard/emphasized`.
- Focus/interaction: `--focus-ring`, `--touch-target-min`.
- Surfaces/borders/text/status: semantic tokens (`--text-*`, `--surface-*`, `--border-*`, `--status-*`).
- Elevation/z-index: `--elevation-*`, `--z-*`.

## Component Contract
- Forms: `ui-form-shell`, `ui-form-header`, `ui-form-grid`, `ui-field`.
- States: `ui-state`, `ui-state--loading|empty|error|success`.
- Toolbars: `ui-toolbar`, `ui-toolbar--compact`, `ui-toolbar--between`.
- Messaging: `ui-message`, `ui-message--error|muted`.

## Theming
- Base dark/light tokens in `:root` + `:root[data-theme='light']`.
- `html[data-ui='liquid-glass-v2']` overlays tokens for glass-v2 visual mode.

## Rule of Use
- Не объявлять root tokens в других CSS слоях.
- Не использовать inline-style для статичных layout/spacing/typography решений.
