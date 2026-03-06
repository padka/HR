# DESIGN_REDESIGN_ROADMAP

## Wave 1. Foundation
- What: централизация токенов в `tokens.css`, удаление root-token дубликатов из `global.css`.
- Why: исключить drift и повысить управляемость темы.
- Impact: высокий (все экраны).
- Effort: средний.
- Dependencies: нет.

## Wave 2. Shared Components
- What: унификация `ui-field`, `ui-form-*`, `ui-state-*`, `ui-toolbar-*`, table responsive wrappers.
- Why: единый ритм и предсказуемые control states.
- Impact: высокий.
- Effort: средний.
- Dependencies: Wave 1.

## Wave 3. High-Value Screens
- What: перенос inline-style в классы на `candidate-new`, `template-new`, `copilot`, `city-new`, частично `city-edit`, `test-builder-graph`.
- Why: убрать fragile style hacks и ускорить дальнейшие доработки.
- Impact: высокий.
- Effort: средний/высокий.
- Dependencies: Wave 2.

## Wave 4. Motion + Responsive Polish
- What: перенос mobile transition orchestration в `motion.css`, чистка дублей в `mobile.css`/`pages.css`.
- Why: уменьшить visual noise и расхождения по анимациям.
- Impact: средний/высокий.
- Effort: средний.
- Dependencies: Wave 1-3.

## Wave 5. Final Consistency Pass
- What: дальнейшая зачистка inline-style на `city-edit` и `test-builder-graph`, cleanup legacy selectors.
- Why: завершение консистентности и снижение техдолга.
- Impact: средний.
- Effort: средний.
- Dependencies: Wave 3/4.

## Quick Wins
- Единые utilities для форм и статусов.
- Централизованные mobile/tablet overrides.
- De-dup motion правил.

## Deeper Redesign Items
- Полный перенос `city-edit` и `test-builder-graph` на reusable page layout primitives.
- Декомпозиция крупных страниц на presentation-only subcomponents.
