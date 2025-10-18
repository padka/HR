# Bootstrap Codex

## Быстрый обзор репозитория
- `backend/apps/admin_ui/app.py` — точка входа FastAPI, подключение роутов и статики.
- `backend/apps/admin_ui/templates/` — шаблоны Jinja2 для всех страниц админки.
- `backend/apps/admin_ui/static/` — исходные CSS/JS и сборочный артефакт Tailwind (`build/main.css`).
- `backend/apps/admin_ui/routers/` — обработчики страниц и API, сгруппированные по доменам.
- `backend/apps/admin_ui/services/` — бизнес-логика (слоты, кандидаты, шаблоны, дашборд).
- `backend/apps/admin_ui/timezones.py` — справочник часовых поясов и утилиты нормализации.
- `backend/core/` — настройки, bootstrap БД и общие утилиты.
- `backend/domain/models.py` — ORM-модели для рекрутёров, кандидатов, городов и слотов.
- `docs/` — пользовательская и разработческая документация.
- `scripts/` и `tools/` — вспомогательные CLI/скрипты.

## Где искать шаблоны и статику
- Главный layout — `backend/apps/admin_ui/templates/base.html`.
- Компоненты и макросы — `backend/apps/admin_ui/templates/page_primitives.html` и папка `partials/`.
- CSS токены и утилиты — `backend/apps/admin_ui/static/css/tokens.css`, `ui.css`.
- Tailwind-источник — `backend/apps/admin_ui/static/css/main.css` (используется CLI, будет заменён Vite).
- JS-модули страниц — `backend/apps/admin_ui/static/js/modules/*.js`.

## Навигация по роутам
- `/` — дашборд (`backend/apps/admin_ui/routers/dashboard.py`).
- `/slots` — список слотов с фильтрами и экспортом (`routers/slots.py`).
- `/candidates` — фильтрованный список кандидатов, деталка `/candidates/{id}` (`routers/candidates.py`).
- `/recruiters` — CRUD рекрутёров и привязка городов (`routers/recruiters.py`).
- `/cities` — управление городами и часовыми поясами (`routers/cities.py`).
- `/templates` — управление шаблонами сообщений и тестов (`routers/templates.py`).
- `/questions` — редактирование вопросов тестов (`routers/questions.py`).
- Системные и health-эндпоинты — `routers/system.py`, `routers/api.py`.

## Админка и страницы
UI построен на Jinja-макросах (`page_primitives.html`) и Tailwind-классах. Таблицы и панели собираются через макросы `table_shell`, `filter_bar`, формы — через `partials/form_shell.html`. JS-модули добавляют динамику: фильтры (`candidates-list.js`), календари (`dashboard-calendar.js`), модалки (`answers-modal.js`).

## Следующие шаги
1. Прочитайте `codex/guidelines.md` для процессов и требований DoD.
2. Ознакомьтесь с `codex/context/project_map.md` и `codex/context/guide_full.md` для полной картины.
3. Запустите аудит (`codex/context/audit.md`) и задачи из `codex/tasks/*.yaml` для миграции на Vite.
