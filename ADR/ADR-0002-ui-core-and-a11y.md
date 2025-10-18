# ADR-0002 — UI-core и доступность

- **Дата:** 2024-11-XX
- **Статус:** Принято

## Контекст
Админка использует макросы `page_primitives.html`, но взаимодействие (модалки, sheet, toast) реализовано разрозненно: inline JS в шаблонах, нет focus-trap, отсутствует единый toast, анимации не учитывают `prefers-reduced-motion`.

## Решение
- Создать UI-core слой в `frontend/ui/core/`:
  - `modal.ts` — контроллер модалки с ARIA (`role="dialog"`, `aria-modal="true"`, возврат фокуса).
  - `sheet.ts` — боковая панель фильтров с trap и lock body scroll.
  - `toast.ts` — уведомления с `aria-live` и очередью.
  - `focus-trap.ts` — общий util (поддержка `prefers-reduced-motion`).
- Обновить макросы `page_primitives.html`, чтобы они создавали разметку с `data-ui-*` и не содержали бизнес-логики.
- Перенести inline-скрипты `base.html`/`slots_list.html` в Vite entrypoints (`entries/app.ts`, `entries/slots.ts`).
- Добавить CSS-токены для состояния фокуса, темной темы и `prefers-reduced-motion`.

## Последствия
- Единая точка для UI поведения, проще писать E2E и unit тесты.
- Повышенная доступность: клавиатурная навигация, trap, aria.
- Потребуется обновить документацию (`codex/context/guide_full.md`, `codex/context/risks.md`).

## Альтернативы
- Оставить inline JS — не проходит DoD (CSP, тестирование).
- Использовать сторонний UI kit — увеличивает вес, не покрывает кастомный дизайн.

## Follow-up
- Создать smoke Playwright сценарии (см. `codex/tasks/e2e_basics.yaml`).
- Обновить ревью-чеклист в `codex/guidelines.md` (выполнено).
