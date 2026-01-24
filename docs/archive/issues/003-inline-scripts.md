# Issue 003 — Inline-скрипты в шаблонах

## Симптомы
- `backend/apps/admin_ui/templates/base.html` содержит два крупных блока `<script>` (стр. 9–35 — тема, 244–330 — topbar/focus trap).
- `backend/apps/admin_ui/templates/slots_list.html` — inline `<script>` ~200 строк с логикой sheet, фильтров и hotkeys.

Это нарушает CSP (невозможно включить `script-src 'self'`), усложняет тестирование и не позволяет повторно использовать код.

## Как воспроизвести
1. Открыть `/slots` в DevTools → Elements — видно inline-скрипты.
2. Включить строгий CSP в ответе — страница ломается из-за `Refused to execute inline script`.

## Предлагаемое решение
- Перенести логику в Vite entrypoints (`frontend/entries/app.ts`, `frontend/entries/slots.ts`).
- Подключить через manifest-helper.
- Покрыть функциональность Playwright-тестами (см. `codex/tasks/e2e_basics.yaml`).

## Ссылки
- `codex/tasks/sprint1_refactor.yaml` (шаги по выносу скриптов).
