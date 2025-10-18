# Журнал решений

- 2024-11-XX — Стратегия миграции фронтенда на Vite зафиксирована в ADR-0001. Tailwind CLI остаётся как fallback до завершения внедрения manifest-helper.
- 2024-11-XX — UI-core (modal, sheet, toast, focus-trap) стандартизирован, детали в ADR-0002. Все макросы используют новые компоненты, inline-скрипты запрещены.
- 2024-11-XX — Playwright выбран основным инструментом E2E/axe-проверок. Smoke-сценарии описаны в `codex/tasks/e2e_basics.yaml`.
- 2024-11-XX — Планировщик слотов синхронизируется с ботом через `bot_service`; reminder queue обязателен для production (см. `codex/context/dev_department.md`).
