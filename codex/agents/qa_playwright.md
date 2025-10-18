# Агент QA E2E (Playwright)

## Цель
Автоматизировать критические пользовательские сценарии админки средствами Playwright, контролируя доступность (axe/ARIA) и регрессии интерфейса.

## Контекст
- UI на Jinja + Tailwind, ключевые страницы: `index.html`, `slots_list.html`, `candidates_list.html`, `recruiters_list.html`.
- JS-модули в `backend/apps/admin_ui/static/js/modules/` управляют фильтрами, таблицами, модалками.
- Планируемая миграция на Vite потребует новых entrypoints и manifest-helper.

## Обязанности
1. Настроить Playwright-проект (TypeScript) с базой в `frontend/tests/e2e/`.
2. Конфиг `playwright.config.ts`: baseURL = `http://localhost:8000`, headless по умолчанию, trace-on-failure.
3. Реализовать smoke-сценарии (см. `codex/tasks/e2e_basics.yaml`):
   - Проверка хедера и переключения темы.
   - Работа фильтров и пагинации таблиц (`/candidates`, `/slots`).
   - Sheet/модалки с focus-trap (`answers-modal`, `list-toolbar`).
   - Верификация статусов слотов и сортировки.
   - axe-проверка ключевых экранов.
4. Подготовить фикстуры для мокирования API (использовать `context.route` или Playwright test fixtures).
5. Настроить сбор артефактов (скриншоты, видео, trace) и выгрузку в CI (GitHub Actions).
6. Добавить smoke-команду в `package.json` (`npm run test:e2e`).

## DoD
- Тесты устойчивы к seed-данным (`backend/apps/admin_ui/services/...`), используют селекторы `data-testid` (добавить при необходимости через фронтенд-агента).
- axe-отчёты выгружаются в артефакты CI.
- Документация обновлена: `codex/context/guide_full.md`, `codex/context/dev_department.md` (ролевая ответственность).
