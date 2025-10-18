# ADR-0001 — Переход на Vite и manifest-helper

- **Дата:** 2024-11-XX
- **Статус:** Принято

## Контекст
Текущая сборка фронтенда использует Tailwind CLI для генерации одного CSS-файла (`backend/apps/admin_ui/static/build/main.css`). Ассеты подключаются напрямую через `<link>` и `/static/js/...`, присутствуют inline-скрипты. Нет версионирования и manifest-helper; невозможно настроить HMR и динамические entrypoints.

## Решение
- Использовать Vite (Node 20, TypeScript) как основной сборщик.
- Создать каталог `frontend/` с entrypoints (`entries/app.ts`, `entries/slots.ts`, `entries/candidates.ts`).
- Перенести стили в `frontend/styles/` (tokens/components/pages) и подключить PostCSS/Tailwind через Vite.
- Добавить manifest-helper `vite_asset()` в Python (кеш читает `static/build/manifest.json`).
- Подключать ассеты в шаблонах через `{% vite_asset %}`. Для dev режима — `@vite/client` + HMR.

## Последствия
- Меньше дублированных стилей, поддержка код-сплиттинга, контроль CSP.
- Необходимо обновить CI (npm run build, кэш node_modules) и Docker (Node stage).
- Tailwind CLI остаётся fallback до миграции (см. `codex/tasks/sprint1_refactor.yaml`).

## Альтернативы
- Продолжить использовать Tailwind CLI + ручной JS-бандл — не решает проблему версионирования и inline-скриптов.
- Webpack/Rollup — heavier setup, нет готового manifest helper. Vite проще для SSR + HMR.

## Follow-up
- Обновить `codex/context/decisions.log.md` (зафиксировано).
- Настроить Playwright smoke после миграции.
