# Frontend Migration Log (React + TS, Vite)

## 2026-01-23
- Инициирована новая SPA `frontend/app` на Vite+React+TS. Добавлены токены/глобальные стили, базовый layout, заглушка слотов.
- Проблема: `@tanstack/react-router` — отсутствует `createRouteTree` в версии 1.74. Решение: отказаться от авто‑генерации, использовать `createRootRoute/createRoute/createRouter`, удалить `routeTree.gen.ts`.
- Проблема: `npm install` — конфликт peer deps (`eslint` 9 vs `@typescript-eslint` 6) из-за `eslint-config-standard-with-typescript`. Решение: `npm install --legacy-peer-deps`.
- Проблема: PostCSS искал tailwind из корневого `postcss.config.cjs`. Решение: отдельный `postcss.config.cjs` в `frontend/app` c только `autoprefixer`; установить `autoprefixer`.
- Добавлен dev proxy Vite к FastAPI (`/api`, `/slots`, `/auth`).
- Добавлен базовый API клиент (`apiFetch`, `queryClient`) и первичное подключение страницы слотов к реальному API `/api/slots`.

## 2026-01-24
- Сгенерирован `openapi.json` из FastAPI (через `create_app().openapi()`) и типы `src/api/schema.ts` (openapi-typescript). Удалён временный `types.ts`.
- Страница слотов на React подключена к типам OpenAPI; добавлены фильтры по статусу, рекрутёру и лимиту, выводятся статусные счётчики из payload.

### Priority 1: Candidate Flows (DONE)
- **Candidate create** (`/app/candidates/new`): форма с выбором города, рекрутёра, даты/времени собеседования. Превью, быстрые кнопки дат, отображение таймзоны.
- **API endpoint**: `POST /api/candidates` для JSON-создания кандидатов.
- **Candidates list**: добавлены status filters (hired/not_hired и др.), status badges с цветами, ссылка на создание.
- **Candidate detail**: улучшено отображение статуса (badge с цветом), добавлены кнопки scheduling.
- **Schedule slot modal**: модальное окно назначения собеседования прямо из карточки кандидата. Выбор рекрутёра, города, даты/времени, опционально кастомное сообщение.
- **Schedule intro day modal**: модальное окно назначения ознакомительного дня из карточки.
- **API endpoints**: `POST /api/candidates/{id}/schedule-slot`, `POST /api/candidates/{id}/schedule-intro-day`.
- Detailization page (`candidates_detailization.html`) теперь покрывается status filters в основном списке кандидатов — можно удалить после проверки.

### Priority 2: Slots Flows (DONE)
- **Approve/Reject**: кнопки для PENDING слотов в таблице и sheet. API: `POST /slots/{id}/approve_booking`.
- **Reschedule**: кнопка для BOOKED слотов. API: `POST /slots/{id}/reschedule`.
- **Booking modal**: модал поиска кандидата и бронирования на FREE слот. API: `POST /slots/{id}/book`.
- **Bulk actions**: мультивыбор чекбоксами, тулбар с bulk delete/remind. API: `POST /slots/bulk`.
- **Status badges**: цветовая индикация статусов в таблице.
- **Link to create**: кнопка "Создать слоты" в заголовке.

### Priority 3: Dashboard (DONE)
- Добавлен Funnel chart в SPA с конверсиями и переходом на candidates по сегменту.
- Добавлен календарь слотов (14 дней) с выбором даты и списком событий.
- Добавлены Weekly KPI карточки из `/api/kpis/current`.
- Добавлены фильтры по датам и рекрутёру (admin-only).
- Добавлены API: `/api/dashboard/funnel`, фильтрация `/api/dashboard/calendar` и `/api/kpis/current` по recruiter.

### Priority 4: Admin CRUD parity (IN PROGRESS)
- Recruiters list: inline toggle активности, улучшены формы с базовой валидацией.
- Cities list: inline обновление plan_week/plan_month + активность, формы с базовой валидацией.
- Questions: добавлены create + clone (новая страница `/app/questions/new` и кнопка clone из списка).
- Message templates: добавлен history UI в SPA.
- Templates: добавлен stage templates editor (SPA), новый API `/api/templates/save`.
- Templates list: фильтры по городу/ключу/поиску + summary по custom templates.
- Templates list: добавлен notification summary (missing_required/coverage) со ссылкой на уведомления.
- Усилены базовые валидации в формах Recruiter/City/Template, добавлена проверка JSON для вопросов.

## TODO next
- Priority 6: Cleanup — удалить legacy/preview файлы после подтверждения и проверки SPA.

## 2026-01-24 (Later)
- Priority 4 помечен завершённым (валидации + inline actions + templates editor).
- Добавлен System page (`/app/system`) с `/api/health` + `/api/bot/integration` и RoleGuard admin-only.
- SPA login форма переведена на `/auth/login` (native form POST) с fallback на legacy страницу.
- Candidates SPA: добавлены Kanban + Calendar view и pipeline switch (`/api/candidates` расширен параметрами `pipeline`, `calendar_mode`, `date_from/date_to`).
- Slots SPA: bulk create усилен валидацией дат/окон/перерыва и UX ошибок.
- Candidate detail: добавлен status center (pipeline stages + быстрые переходы + ручная коррекция при legacy).
- Templates: create/edit получили полноценный editor (presets, placeholders, preview, char count, city search).
- Profile SPA: добавлены метрики администратора/рекрутёра, встречи, кандидаты, планировщик, напоминания.
- Добавлен `/api/timezones` и подключены таймзоны в формах городов/рекрутёров.

## 2026-01-24 (Questions edit parity)
- Questions edit: добавлен JSON-конструктор (choice/text), шаблоны, предпросмотр и валидация в SPA (`/app/questions/:id/edit`).
- Questions new: подключён тот же конструктор/preview для создания.

## 2026-01-24 (Templates list parity)
- `/app/templates`: добавлен блок уведомлений с группировкой по этапам, поиском, toggle активного статуса и удалением.
- Добавлены стили карточек/панелей для уведомлений и stage legend.

## 2026-01-24 (Recruiters/Cities parity)
- `/app/recruiters`: добавлены удаление рекрутёра и empty state.
- `/app/cities`: добавлены удаление города и empty state.

## 2026-01-24 (Full Parity Completion)
- **Recruiters create/edit**: Полная переработка форм - добавлены секции, поиск городов с тайлами, счётчик выбора, summary hero card для edit, пилюли выбранных городов, hint для TZ.
- **Cities create/edit**: Полная переработка форм - авто-подстановка TZ по названию города, валидация TZ с показом текущего времени, quick presets для планов (5/10/20 для недели, 30/60/100 для месяца), поиск рекрутёров с тайлами, summary hero card.
- **Slots create UX**: Добавлены success messages после создания, улучшенный preview для bulk create с визуальными счётчиками и предупреждением при большом количестве.
- **Migration map**: Статусы Recruiters и Cities обновлены с PARTIAL на DONE (~98% coverage).
- **Cleanup status**: Backup/preview файлы в основном удалены, остаётся .env.backup и legacy JS modules.

## 2026-01-24 (Cleanup + API Align)
- Удалены legacy Jinja шаблоны в `backend/apps/admin_ui/templates/*` (оставлены public test pages).
- Полностью удалён `backend/apps/admin_ui/static/js/` (legacy JS modules и утилиты).
- Удалён legacy CSS build `backend/apps/admin_ui/static/build/main.css`.
- Legacy `/profile` переведён на redirect → `/app/profile`.
- Candidate scheduling endpoints (`/candidates/{id}/schedule-slot`, `/schedule-intro-day`) переведены на JSON вход/выход (убраны TemplateResponse).
- Исправлены артефакты после ранней замены (лишние строки в candidates router), очищены неиспользуемые импорты.
