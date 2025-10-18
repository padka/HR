# Аудит Smart Service HR Admin (экспресс)

## Архитектура сейчас
- **Фронтенд:** Jinja-шаблоны в `backend/apps/admin_ui/templates/`, базовый layout `base.html` подключает статические файлы напрямую (`<link rel="stylesheet" href="{{ url_for('static', path='css/tokens.css') }}">`, стр. 32) и содержит inline JS (стр. 9–35 и 244–330).
- **Сборка:** Tailwind CLI собирает `backend/apps/admin_ui/static/css/main.css` → `static/build/main.css` (`package.json` → `npm run build`). Дополнительно загружаются `css/tokens.css` и `css/ui.css`, что дублирует стили.
- **JS:** Модули в `backend/apps/admin_ui/static/js/modules/*.js` импортируются из шаблонов через абсолютные пути `/static/js/modules/...` (например, `candidates_list.html`, стр. 187). Inline скрипты управляют topbar и sheets.
- **Бэкенд:** FastAPI приложение `backend/apps/admin_ui/app.py` монтирует статику `/static` и подключает роуты `/slots`, `/candidates`, `/templates`, `/questions` и т.д. Регистрация Jinja-глобалов происходит в `register_template_globals()`.
- **Демо-приложение:** `app_demo.py` строит альтернативный FastAPI сервер и копирует шаблоны вручную, что приводит к расхождениям при сборке контейнера.

## Проблемы и риски
1. **Дублирование CSS** — `base.html` подключает `css/tokens.css`, `build/main.css`, `css/ui.css`; переменные и компоненты объявлены дважды. См. `docs/issues/001-css-duplication.md`.
2. **Inline-скрипты** — крупные блоки JS прямо в `base.html` и `slots_list.html`. См. `docs/issues/003-inline-scripts.md`.
3. **TemplateNotFound на `/questions/{id}/edit`** — в docker-стенде `app_demo` не копирует все шаблоны, Jinja поднимает `TemplateNotFound: questions_edit.html`. См. `docs/issues/002-template-not-found.md`.
4. **Жёсткие пути `/static/...`** — шаблоны подключают модули без `url_for`, ломается при `root_path`. См. `docs/issues/004-static-paths.md`.
5. **A11y долги** — focus trap реализован вручную, нет поддержки `prefers-reduced-motion` (анимации `glass-in` в `tailwind.config.js`).
6. **Нет manifest-helper** — бандлы не версионируются, при CDN возможны устаревшие ассеты.
7. **Тесты** — отсутствует Playwright, нет автоматических smoke/a11y проверок.
8. **Планировщик** — `dashboard_calendar.py` и `timezones.py` не учитывают `candidate_tz`, возможны неверные напоминания.

## Точки входа
- **Страницы:** `/` (`templates/index.html`), `/slots` (`templates/slots_list.html`), `/candidates` (`templates/candidates_list.html`), `/recruiters` (`templates/recruiters_list.html`), `/templates` (`templates/templates_list.html`), `/questions` (`templates/questions_list.html`).
- **API:** `/api/slots` и связанные ручки (`routers/api.py`), `/regions/{id}/timezone` (`routers/regions.py`).
- **JS-модули:** `static/js/modules/dashboard-calendar.js` (календарь), `candidates-list.js` (фильтры и токены поиска), `answers-modal.js` (sheet/модалка), `template-editor.js`.
- **Бот-интеграция:** `services/bot_service.py`, `services/dashboard.py`, `services/dashboard_calendar.py`.

## Маппинг статических путей
- `base.html` — `<link>` и `<script>` через `url_for('static', ...)`, но без manifest-helper.
- `candidates_list.html` — `<script type="module" src="/static/js/modules/candidates-list.js">` (стр. 187).
- `recruiters_list.html` — `<script type="module" src="/static/js/modules/recruiter-grid.js">` (стр. 170).
- `templates_edit.html` — inline `import { initTemplateEditor } from "/static/js/modules/template-editor.js";` (стр. 124).
- `slots_list.html` — встроенный `<script>` с `fetch('/api/slots')` без хост-префикса.

## Quick Wins
| Шаг | Описание | Эффект |
| --- | --- | --- |
| QW1 | Перенести topbar/тему в модуль `frontend/entries/app.ts` и подключить через Vite dev server | A11y (focus trap), поддерживаемость |
| QW2 | Заменить `/static/...` на `url_for('static', path=...)` до миграции на Vite | Надёжность деплоя |
| QW3 | Добавить smoke тест `pytest` для `/questions/{id}/edit` | Гарантия против TemplateNotFound |
| QW4 | Включить `prefers-reduced-motion` токен в CSS (обновить `tailwind.config.js`) | A11y |

## План на 3 спринта
1. **Спринт 1 — Vite и UI-core** (см. `codex/tasks/sprint1_refactor.yaml`)
   - Эффект: UI (-дубли), Перф (меньше CSS), A11y (focus-trap), Поддерживаемость (структура).
2. **Спринт 2 — Планировщик и TZ**
   - Обновить `dashboard_calendar.py`, `timezones.py`, добавить квоты и нормализацию recruiter/candidate TZ, покрыть тестами.
   - Эффект: UI (точные статусы), Перф (предкэш квот), A11y (доступные уведомления), Поддерживаемость (формализация расписания).
3. **Спринт 3 — QA/CI**
   - Настроить Playwright (`codex/tasks/e2e_basics.yaml`), GitHub Actions, Dockerfile/compose (агент DevOps).
   - Эффект: UI (регрессии ловим), Перф (авто smoke), A11y (axe в CI), Поддерживаемость (артефакты).

## Чеклист DoD по эпику
- **Frontend Refactorer**: Vite manifest, нет inline-скриптов, UI-core подключён, smoke `/slots` пройден, axe ок.
- **Scheduler Architect**: схемы квот согласованы, переходы статусов задокументированы, tz-конверсия покрыта тестами.
- **QA Playwright**: тесты E1–E7 реализованы, отчёты и trace в CI, `npm run test:e2e` в DoD.
- **DevOps CI**: workflow lint→test→build, Docker образ собирается, артефакты загружаются, `.env.example` обновлён.

## Список issue
- `docs/issues/001-css-duplication.md` — убрать дубли CSS.
- `docs/issues/002-template-not-found.md` — починить TemplateNotFound на `/questions/{id}/edit`.
- `docs/issues/003-inline-scripts.md` — вынести inline-скрипты.
- `docs/issues/004-static-paths.md` — заменить жёсткие пути `/static`.
