# UI Smoke Checklist (Light/Dark)

- **Dashboard**: header/nav/cards readable; glass not obstructing; no dark artifacts in light theme.
- **Table/List**: sticky header visible; zebra + hover via tokens; scrolling inside wrapper; loading/empty states readable.
- **Form**: inputs/selects/buttons same height; focus ring visible; disabled/readonly legible.
- **Modal/Dropdown/Popover**: surface uses token background/border; backdrop not muddy; z-index above nav; animations only opacity/transform.
- **Dropdown/Toast/Tooltip**: text readable; no black backgrounds; shadows token-based.
- **Theme switch**: no flicker (localStorage > prefers-color-scheme > default).
- **Viewport**: 375px and 1024px — header/nav/tables intact, table scrolls horizontally without breaking layout.
- **Reduced motion**: transitions/animations disabled where expected.
- **Keyboard**: focus-visible on links/buttons/inputs/popovers.
