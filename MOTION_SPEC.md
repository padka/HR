# MOTION_SPEC

## Motion Principles
- Анимация для понимания перехода состояния, не для декора.
- Короткие duration и предсказуемые easings.
- Reduced-motion обязателен.

## Transition Language
- Page enter: `ui-page-enter`.
- Mobile route transitions: `slideInRight`, `slideInLeft`, `fadeIn`.
- Overlay/sheet: `sheetSlideUp`, `sheetSlideDown`.
- Feedback: button press scale, pull-to-refresh spin.

## Centralization
- `frontend/app/src/theme/motion.css` содержит keyframes и orchestration rules.
- Дубли mobile animation assignments удаляются из `mobile.css`.

## Reduced Motion
- Поддержка через `data-motion='reduced'` и `prefers-reduced-motion: reduce`.
- Animation/transition duration минимизируются до near-zero.
