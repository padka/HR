# Полный гайд по Smart Service HR Admin

## Назначение продукта
Smart Service HR автоматизирует массовый рекрутинг. Кандидат проходит путь:
1. Отклик на вакансию и регистрация в боте.
2. Тестирование (Test 1/Test 2) и анкетирование.
3. Выбор доступного слота интервью (бот или оператор).
4. Интервью и решение рекрутёра (операционное действие, ОД).
5. Нотификация кандидата и обновление статусов.

KPI: конверсия отклик → слот, скорость закрытия слота, доля подтверждённых кандидатов, время реакции рекрутёра, выполнение квот по городам.

## Архитектура
- **FastAPI** (`backend/apps/admin_ui/app.py`): монтирует `/static`, подключает роуты (`routers/*.py`), настраивает middleware (TrustedHost, HTTPS, Session). Жизненный цикл (`lifespan`) валидирует настройки и инициализирует интеграцию с ботом.
- **Jinja шаблоны** (`backend/apps/admin_ui/templates/`): layout `base.html`, макросы `page_primitives.html`, partials.
- **Статика** (`backend/apps/admin_ui/static/`): CSS (`css/`, `build/main.css`), JS (`js/`, `js/modules/`).
- **Сервисы** (`backend/apps/admin_ui/services/`): бизнес-логика слотов, кандидатов, дашборда, шаблонов.
- **Домен** (`backend/domain/models.py`): ORM-модели `City`, `Recruiter`, `Candidate`, `Slot`, `NotificationLog` и др.
- **Bot integration** (`services/bot_service.py`): управление очередями напоминаний, синхронизация статусов.

### Статика и Vite
Плановая миграция: Vite генерирует `backend/apps/admin_ui/static/build/manifest.json`. Точки входа `frontend/entries/app.ts`, `slots.ts`, `candidates.ts`. Слои стилей:
- `frontend/styles/tokens.css` — дизайн-токены (цвета, типографика, радиусы).
- `frontend/styles/components.css` — UI-core (модалки, sheet, toast, таблицы).
- `frontend/styles/pages/*.css` — специфические правила страниц.

Manifest-helper `vite_asset()` читает `manifest.json`, кэширует, предоставляет `{% vite_asset 'entries/app.ts' %}`. В dev режим (`npm run dev`) подключается `@vite/client`.

### UI-core
- **Modal** — focus trap, aria атрибуты, поддержка `prefers-reduced-motion`.
- **Sheet** — используется для фильтров (`/slots`), поддержка клавиатуры.
- **Toast** — единый компонент с `aria-live="polite"`, закрытие по таймеру.
- **Focus-trap** — общий util, отключает trap при `prefers-reduced-motion` и возвращает фокус.
Макросы `page_primitives.html` должны вызывать UI-core вместо inline HTML.

## Часовые пояса и напоминания
- **Хранение TZ**: `City.tz`, `Recruiter.timezone`, `Candidate.timezone` (если есть). `backend/apps/admin_ui/timezones.py` содержит список допустимых зон.
- **Конверсия**: при отображении слотов всё приводим к `settings.timezone` (recruiter_tz). При отправке напоминаний учитываем `candidate_tz` и локальное время.
- **Напоминания**: `bot_service` управляет очередью. SLA: T-24, T-1, T-0.5 до слота, учитывая локальное время города. Переход статусов должен логироваться (`NotificationLog`).

## Команды разработки
```bash
# Backend
uvicorn backend.apps.admin_ui.app:app --reload --port 8000

# Node
npm install
npm run dev        # Vite dev server
npm run build      # Production build (manifest)
npm run lint       # ESLint/Stylelint (добавить)
npm run test       # Unit тесты фронтенда (добавить)
npm run test:e2e   # Playwright smoke

# Python tests
pytest
```
Для bootstrap используйте `make bootstrap`, `make dev-db`, `make test`.

## CI/CD
Плановый workflow (`.github/workflows/ci.yml`):
1. **lint** — ruff, black, mypy, eslint, stylelint.
2. **test** — pytest, Playwright (chromium, firefox).
3. **build** — `npm run build`, `python -m compileall`, smoke `uvicorn` (`pytest -k smoke`).
4. **artefacts** — загружать `frontend-dist`, `playwright-report`, coverage, axe.
Deploy: Docker image (`python:3.11-slim` + Node stage) → registry → staging/prod. Compose: сервисы `admin`, `db`, `redis` (для напоминаний).

## Безопасность и роли
- **Рекрутёр**: CRUD слотов, кандидатов, подтверждение статусов.
- **Супервайзер**: настройка квот, шаблоны сообщений, KPI доступ.
- **Админ**: доступ к `/system` эндпоинтам, переключение бот-интеграции.
Логирование отправок (Telegram) через `bot_service`, храним в `NotificationLog` + `app.state.reminder_service` метрики. Включить audit trail в UI.

## Стандарты PR
- Ветка `feature/...` от `develop`.
- Описание: проблема, решение, скриншоты, результаты тестов.
- Чеклист DoD (см. `codex/guidelines.md`): зелёные линтеры, Vite ассеты, UI-core, axe, обновлённые ADR/решения.
- Для визуальных изменений — скриншоты/видео + ссылка на Playwright trace.
