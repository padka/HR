# RecruitSmart: технический аудит для техлида

Дата: 2026-04-16  
Формат: read-only аудит текущего workspace  
Ветка: `codex/index`

## 0. Scope и метод

- Аудит выполнен по **текущему dirty workspace**, а не по чистому `HEAD`.
- Код не менялся; миграции, destructive-операции и любые data writes не выполнялись.
- Использован статический анализ + targeted checks: `git status --short`, чтение docs/code, live OpenAPI introspection в test-env, инвентаризация SQLAlchemy metadata.
- Секреты и значения `.env` не раскрывались. В отчёте указаны только имена переменных и места использования.
- Все выводы ниже нужно читать с оговоркой: часть рисков может измениться после стабилизации текущей ветки.

### Baseline

- Dirty worktree: `105` строк в `git status --short`.
- Наиболее существенные отличия текущего workspace: candidate portal удалён из runtime, `backend/apps/max_bot/app.py` отсутствует, но compose/docs/schema ещё сохраняют следы этих потоков.
- Tracked `frontend/app/openapi.json`: `228` paths.
- Live `admin_ui` OpenAPI: `221` paths.
- Live `admin_api` OpenAPI: `19` paths.
- Stale tracked-only paths: `11`. Из них candidate portal-related: `11`.
- Live-only paths, отсутствующие в tracked schema: `4`.

### Dirty-worktree note

Ключевые строки baseline:

- D backend/apps/admin_ui/routers/candidate_portal.py
- D backend/apps/max_bot/app.py
- D backend/apps/max_bot/candidate_flow.py
- D backend/domain/candidates/portal_service.py

## 1. Общая карта проекта

### Назначение системы

RecruitSmart в текущем виде — это CRM/ATS-монорепозиторий для операционного рекрутинга с сильной привязкой к Telegram-каналу. Система покрывает intake кандидатов, квалификацию, управление слотами/собеседованиями, коммуникации, напоминания, HH.ru интеграцию и AI-assist для рекрутеров.

### Основные бизнес-процессы

- intake кандидата: ручное создание, Telegram-first вход, импорт из HH;
- квалификация: тесты, статусы, recruiter review, AI summary/coach;
- scheduling: подбор и резервирование слота, подтверждение, перенос, reminder pipeline;
- коммуникации: recruiter chat, outbound notifications, message templates;
- recruiter operations: dashboard, pipeline, detailization, calendar/tasks;
- HH integration: connection, import, sync, webhook ingestion, callbacks через n8n compatibility layer;
- AI layer: candidate summary, message drafts, interview script, recommendations, dashboard insights.

### Роли пользователей

- `admin`: системные настройки, справочники, интеграции, рекрутеры, тесты, шаблоны.
- `recruiter`: работа с кандидатами, календарём, чатами, AI copilot, частью operational screens.
- `candidate`: фактически поддержан через Telegram bot / Telegram webapp surface; отдельный browser portal в текущем runtime отсутствует.
- `external systems`: OpenAI, Telegram, HH.ru, n8n, Redis/PostgreSQL.

### Основные сущности

- кандидат: `users` + связанный test/chat/interview/history слой;
- рекрутер: `recruiters`;
- город / офисный контекст: `cities`;
- вакансия: `vacancies` + `test_questions`;
- слот / назначение / перенос: `slots`, `slot_assignments`, `slot_reschedule_requests`;
- коммуникации: `chat_messages`, `message_templates`, `outbox_notifications`;
- авторизация: `auth_accounts`;
- аудит и аналитика: `audit_log`, `analytics_events`;
- HH integration: `hh_connections`, `candidate_external_identities`, `hh_negotiations`, `hh_sync_jobs`, `hh_webhook_deliveries`;
- AI: `ai_outputs`, `ai_request_logs`, `ai_agent_threads`, `candidate_hh_resumes`, `ai_interview_script_feedback`, `knowledge_base_documents`.

### Что важно как вывод

- Система уже не является multi-surface CRM в духе “portal + bot + Max”. По текущему runtime это **Telegram-first ATS with admin SPA**.
- Важная отсутствующая сущность: **нет explicit application/requisition layer**. Из-за этого кандидат и заявка/отклик частично смешаны.

### Внешние сервисы

- Telegram Bot API / Telegram WebApp auth.
- OpenAI API.
- HH.ru API + HH webhooks.
- n8n webhooks для compatibility sync/resolve flows.
- PostgreSQL.
- Redis (notifications/cache/rate limit depending on env).
- Docker / docker-compose deployment surface.

## 2. Технологический стек

### Backend

- Язык: Python 3.11+.
- Framework: FastAPI + Starlette.
- ORM: SQLAlchemy asyncio.
- Auth: session cookie + JWT bearer + CSRF для mutating admin routes.
- Queue/background: Redis-backed notifications, APScheduler, outbox flows.
- Bot/webapp: aiogram + Telegram WebApp auth.

### Frontend

- React 18 + TypeScript + Vite.
- Routing: TanStack Router.
- State/data: TanStack Query, React Hook Form, Zod.
- Calendar/UI: FullCalendar, Framer Motion, Zustand.

### Data / infra

- Primary DB target: PostgreSQL; dev/test compatibility path for SQLite exists.
- Cache/broker: Redis.
- Infra: Dockerfile + `docker-compose.yml` with `postgres`, `redis_notifications`, `redis_cache`, `admin_ui`, `admin_api`, `bot`, `max_bot`, `migrate`.
- Cloud/deploy scripts: direct cloud manifests не найдены; деплой ориентирован на container runtime / compose.

### AI / integrations

- AI provider: OpenAI or fake provider.
- Default model surface in compose: `OPENAI_MODEL` (defaulted for GPT-5 mini family).
- n8n: only webhook call sites/export compatibility found, workflow exports в репозитории не найдены.
- Messengers: Telegram implemented; historical MAX surface in repo/runtime drift; email/SMS/WhatsApp first-class flows не найдены.

### Tests / linters

- Backend: pytest, pytest-asyncio, mypy (dev dependency), Ruff, Black, isort.
- Frontend: ESLint, TypeScript typecheck, Vitest, Playwright.
- Counts in current workspace: backend tests files `371`, frontend test files `14`.

## 3. Структура кодовой базы

```text
/backend
  /apps/admin_ui        # основной admin backend и SPA-facing API
  /apps/admin_api       # Telegram mini app, recruiter webapp, HH callbacks
  /apps/bot             # Telegram bot runtime, delivery/reminders
  /apps/max_bot         # исторический Max surface, сейчас runtime-incomplete
  /core                 # settings/db/auth/audit/ai/shared infra
  /domain               # ORM + доменные сервисы
  /migrations           # история схемы и foundation-изменения
/frontend/app
  /src/app/routes       # route map recruiter/admin интерфейса
  /src/api/services     # client wrappers над /api
  /src/theme            # visual system
/docs
  /architecture         # общая архитектура и topology
  /data                 # ERD и словарь данных
  /security             # trust boundaries / auth model
  /hh                   # HH integration design materials
/tests                  # backend test suite
/scripts                # dev/ops/gate tooling
```

| Директория | Что внутри | Критичность | Изучить сначала |
| --- | --- | --- | --- |
| /backend/apps/admin_ui | Основной admin FastAPI surface: SPA shell, API routers, services. | Критично | app.py, routers/ai.py, routers/candidates.py, routers/api_misc.py |
| /backend/apps/admin_api | Telegram mini-app / recruiter webapp / HH sync callbacks. | Критично | main.py, webapp/auth.py, webapp/routers.py, hh_sync.py |
| /backend/apps/bot | Telegram bot runtime, reminder and notification flows. | Критично | app.py, services/notification_flow.py, handlers/attendance.py |
| /backend/apps/max_bot | Former Max bot surface; currently runtime-incomplete in workspace. | Критично | __init__.py, max_bot.py entrypoint at repo root |
| /backend/core | Shared infra: settings, db, auth, audit, AI provider facade. | Критично | settings.py, db.py, audit.py, ai/service.py, ai/providers/openai.py |
| /backend/domain | ORM models and domain services for candidates, HH, AI, scheduling. | Критично | candidates/models.py, models.py, ai/models.py, hh_integration/models.py |
| /backend/migrations | Alembic and custom migration history. | Критично | versions/0091_add_hh_integration_foundation.py, 0099_add_users_phone_normalized.py, 0057_auth_accounts.py |
| /frontend/app/src/app/routes | SPA route map and recruiter/admin UI. | Критично | main.tsx, routes/app/candidates.tsx, routes/app/calendar.tsx, routes/app/system.tsx |
| /frontend/app/src/api/services | Typed client-side wrappers over /api. | Высокая | candidates.ts, dashboard.ts, messenger.ts, system.ts, hh-integration.ts |
| /docs | Архитектура, data, security, HH research, QA catalogs. Частично stale. | Высокая | architecture/*.md, data/*.md, security/*.md, candidate_channels/CANDIDATE_CHANNELS_AUDIT.md |
| /scripts | Dev/ops and helper scripts, migrations, smoke/gate tooling. | Средняя | run_migrations.py, dev_bot.sh, formal_gate_sprint12.py |
| /tests | Backend regression and integration coverage. | Высокая | test_ai_copilot.py, test_webapp_booking_api.py, test_hh_integration_* |

## 4. Функциональная карта

| Модуль | Что делает | Где реализован | Статус | Комментарии |
| --- | --- | --- | --- | --- |
| Создание / импорт кандидатов | Ручное создание в админке, intake через Telegram, импорт из HH. | backend/apps/admin_ui/routers/candidates.py; backend/apps/admin_ui/routers/hh_integration.py; backend/apps/admin_api/webapp/routers.py | implemented | Есть несколько входов в систему, но единой intake-модели нет. |
| Карточка кандидата | Хранение профиля, тестов, чатов, интервью-заметок, operational summaries. | backend/domain/candidates/models.py; frontend/app/src/app/routes/app/candidates.tsx | implemented | Карточка перегружена данными и partly заменяет Application. |
| Статусы кандидатов | Lifecycle/status tracking для воронки. | backend/domain/candidates/models.py; backend/domain/candidates/status_service.py | partially implemented | Статусы фрагментированы между несколькими полями. |
| Дедупликация | Сопоставление по Telegram/HH/телефону и слотам. | backend/domain/hh_integration/importer.py; backend/domain/repositories.py | partially implemented | Phone normalized only indexed; merge-flow отсутствует. |
| Вакансии | CRUD вакансий и привязка вопросов Test1/Test2. | backend/apps/admin_ui/routers/api_misc.py; backend/apps/admin_ui/services/vacancies.py | implemented | Есть локальные вакансии и HH bindings. |
| Заявки на подбор | Отдельная hiring request / requisition сущность. | Не найдена как first-class model | planned only | В коде нет явной сущности заявки на подбор. |
| Назначение рекрутеров | Ответственный рекрутер у кандидата/города/слота. | backend/domain/models.py; backend/domain/candidates/models.py | implemented | Есть ручное назначение, без rich ownership policies. |
| Коммуникации с кандидатами | Чаты, quick actions, Telegram notifications, recruiter webapp send. | backend/apps/admin_ui/services/chat.py; backend/apps/bot/services/notification_flow.py | implemented | Практически всё завязано на Telegram. |
| Шаблоны сообщений | CRUD шаблонов уведомлений. | backend/domain/models.py; backend/apps/admin_ui/routers/message_templates.py | implemented | Поддержка шаблонов есть и активно используется. |
| AI-анализ кандидатов | Summary, coach, city recommendations, dashboard insights. | backend/core/ai/service.py; backend/apps/admin_ui/routers/ai.py | implemented | Есть cache/quota/logging. |
| AI-генерация сообщений | Chat drafts и coach drafts для рекрутера. | backend/apps/admin_ui/routers/ai.py; backend/core/ai/prompts.py | implemented | Нужна более строгая схема output. |
| Запись на собеседование | Slot booking/scheduling через admin и Telegram webapp. | backend/apps/admin_ui/services/slots.py; backend/apps/admin_api/webapp/routers.py | implemented | Один из самых зрелых модулей. |
| Календарь | Calendar view, tasks, dashboard calendar. | backend/domain/models.py; frontend/app/src/app/routes/app/calendar.tsx | implemented | Есть recruiter calendar и tasks. |
| Напоминания | Reminder policy, jobs, resync, candidate reminders. | backend/apps/bot/services/notification_flow.py; frontend/app/src/api/services/system.ts | implemented | Есть operational tooling. |
| Результат интервью | Interview notes и detailization outcomes. | backend/domain/candidates/models.py; backend/apps/admin_ui/services/detailization.py | partially implemented | Нет единой interview evaluation entity. |
| No-show | Статусы/фиксация неявки. | backend/domain/models.py; backend/apps/bot/handlers/attendance.py | partially implemented | Есть статус и часть обработчиков, но recovery flow слабый. |
| Реактивация базы | Возврат старых кандидатов в работу. | Явный модуль не найден | planned only | Есть только косвенные механики через статус/чат. |
| Аналитика и дашборды | Funnel, KPIs, leaderboard, analytics_events. | backend/apps/admin_ui/services/dashboard.py; backend/domain/analytics.py | partially implemented | Сильнее по recruiter ops, слабее по vacancy/source analytics. |
| Роли и права доступа | admin/recruiter auth + route guards. | backend/domain/auth_account.py; backend/apps/admin_ui/security.py; frontend/app/src/app/components/RoleGuard.tsx | partially implemented | RBAC coarse-grained. |
| Логирование действий | Audit log, AI request logs, analytics events. | backend/core/audit.py; backend/domain/ai/models.py; backend/domain/analytics_models.py | partially implemented | Есть несколько лог-слоёв, но нет unified event trail. |
| Интеграции с n8n | HH sync / resolve via webhooks. | backend/domain/hh_sync/worker.py; backend/apps/admin_api/hh_sync.py | partially implemented | Call sites есть, workflow exports нет. |
| API / webhooks | Admin UI API, Admin API webapp, HH webhooks. | backend/apps/admin_ui/app.py; backend/apps/admin_api/main.py; backend/apps/hh_integration_webhooks.py | implemented | Контракт широкий, но docs/schema drift значительный. |
| Обработка ошибок | HTTP exceptions, fallbacks, degraded responses. | backend/apps/admin_ui/routers/*; backend/apps/admin_api/main.py | partially implemented | Есть graceful fallbacks, но они иногда скрывают structural drift. |

## 5. API и интеграции

### Общий вывод

- Live current code exposes `221` paths in `admin_ui` and `19` paths in `admin_api`.
- `frontend/app/openapi.json` не является source of truth: в нём остаются удалённые candidate portal endpoints и отсутствуют новые live routes вроде `/api/candidates/{candidate_id}/channel-health` и `/api/system/messenger-health`.
- Полный inventory находится в `artifacts/audit/2026-04-16-api-inventory.csv`.

### Что особенно важно

- Входящие webhooks:
  - `POST /api/hh-integration/webhooks/{webhook_key}` — приём HH delivery, idempotency через `hh_webhook_deliveries`.
  - `POST /api/hh-sync/callback` — callback от n8n после HH status sync.
  - `POST /api/hh-sync/resolve-callback` — callback от n8n после resolve negotiation.
- Исходящие вызовы во внешний automation layer:
  - `N8N_HH_SYNC_WEBHOOK_URL`.
  - `N8N_HH_RESOLVE_WEBHOOK_URL`.
  - auth для callback layer: `HH_WEBHOOK_SECRET`.
- Candidate portal contract в tracked schema больше не соответствует live current runtime.

### Ключевые endpoints

| Method | Path | Назначение | Auth | Input | Output | Где используется |
| --- | --- | --- | --- | --- | --- | --- |
| POST | /api/hh-integration/webhooks/{webhook_key} | Receive Hh Webhook | webhook_key in path | params: webhook_key(path:string) | 200: application/json:none | backend:backend.apps.hh_integration_webhooks:receive_hh_webhook |
| POST | /api/hh-sync/callback | Hh Sync Callback | X-Webhook-Secret header | params: x-webhook-secret(header:schema); body: application/json:SyncCallbackRequest | 200: application/json:none | backend:backend.apps.admin_api.hh_sync:hh_sync_callback |
| POST | /api/hh-sync/resolve-callback | Hh Resolve Callback | X-Webhook-Secret header | params: x-webhook-secret(header:schema); body: application/json:ResolveCallbackRequest | 200: application/json:none | backend:backend.apps.admin_api.hh_sync:hh_resolve_callback |
| POST | /api/webapp/booking | Create Booking | Telegram initData header (X-Telegram-Init-Data) | params: X-Telegram-Init-Data(header:string); body: application/json:CreateBookingRequest | 201: application/json:BookingInfo | backend:backend.apps.admin_api.webapp.routers:create_booking |
| POST | /api/webapp/reschedule | Reschedule Booking | Telegram initData header (X-Telegram-Init-Data) | params: X-Telegram-Init-Data(header:string); body: application/json:RescheduleBookingRequest | 200: application/json:BookingInfo | backend:backend.apps.admin_api.webapp.routers:reschedule_booking |
| POST | /api/ai/candidates/{candidate_id}/chat/drafts | Api Ai Chat Drafts | session cookie or bearer token + CSRF | params: candidate_id(path:integer) | 200: application/json:none | backend:backend.apps.admin_ui.routers.ai:api_ai_chat_drafts; frontend:frontend/app/src/api/services/candidates.ts |
| GET | /api/ai/candidates/{candidate_id}/summary | Api Ai Candidate Summary | session cookie or bearer token | params: candidate_id(path:integer) | 200: application/json:none | backend:backend.apps.admin_ui.routers.ai:api_ai_candidate_summary; frontend:frontend/app/src/api/services/candidates.ts |
| GET | /api/candidates/{candidate_id}/channel-health | Api Candidate Channel Health | session cookie or bearer token | params: candidate_id(path:integer) | 200: application/json:none | backend:backend.apps.admin_ui.routers.api_misc:api_candidate_channel_health; frontend:frontend/app/src/api/services/candidates.ts |
| GET | /api/dashboard/funnel | Api Dashboard Funnel | session cookie or bearer token | params: from(query:schema), to(query:schema), city(query:schema), recruiter(query:schema), source(query:schema) | 200: application/json:none | backend:backend.apps.admin_ui.routers.api_misc:api_dashboard_funnel |
| POST | /api/hh-integration/webhooks/{webhook_key} | Receive Hh Webhook | webhook_key in path | params: webhook_key(path:string) | 200: application/json:none | backend:backend.apps.hh_integration_webhooks:receive_hh_webhook |
| GET | /api/system/messenger-health | Api System Messenger Health | session cookie or bearer token | none | 200: application/json:none | backend:backend.apps.admin_ui.routers.api_misc:api_system_messenger_health; frontend:frontend/app/src/api/services/system.ts |
| GET | /api/vacancies | Api List Vacancies | session cookie or bearer token | params: city_id(query:schema) | 200: application/json:none | backend:backend.apps.admin_ui.routers.api_misc:api_list_vacancies; frontend:frontend/app/src/app/routes/app/vacancies.tsx |
| POST | /api/vacancies | Api Create Vacancy | session cookie or bearer token + CSRF | none | 200: application/json:none | backend:backend.apps.admin_ui.routers.api_misc:api_create_vacancy; frontend:frontend/app/src/app/routes/app/vacancies.tsx |

### Drift между tracked OpenAPI и live app

- Tracked-only paths (первые 20):
- /api/candidate/journey
- /api/candidate/messages
- /api/candidate/profile
- /api/candidate/screening/complete
- /api/candidate/screening/save
- /api/candidate/session/exchange
- /api/candidate/session/logout
- /api/candidate/slots/cancel
- /api/candidate/slots/confirm
- /api/candidate/slots/reschedule
- /api/candidate/slots/reserve
- Live-only paths (первые 20):
- /api/candidates/{candidate_id}/channel-health
- /api/slot-assignments/{assignment_id}/repair
- /api/system/messenger-health
- /api/system/messenger-health/{channel}/recover

### Особое внимание по группам

- `candidates`: очень широкий surface, но часть DTO и historical contracts вокруг portal/MAX устарела.
- `vacancies`: CRUD присутствует, но vacancy ещё не является полной бизнес-сущностью уровня requisition/application.
- `ai`: реализован набор recruiter-assist flows, а не autonomous decision layer.
- `messages`: operationally strong, но storage/delivery model ещё не multi-channel-first.
- `analytics`: recruiter/dashboard coverage есть, но vacancy/source-level truth ограничен data model.

## 6. База данных

### Сводка по схеме

- Найдено `70` таблиц/metadata entries в current SQLAlchemy metadata.
- Полный inventory находится в `artifacts/audit/2026-04-16-db-model-inventory.csv`.
- Важный сигнал: в схеме одновременно присутствуют зрелые operational tables (`slots`, `slot_assignments`, `outbox_notifications`, `ai_*`, `hh_*`) и stale/historical области, связанные с удалённым candidate portal / channel experiments.

### Ключевые таблицы/модели

| Таблица/модель | Model | Домен | PK | Связи | Индексы | Unique |
| --- | --- | --- | --- | --- | --- | --- |
| ai_interview_script_feedback | AIInterviewScriptFeedback | ai | id | candidate_id->users.id | ix_ai_interview_script_feedback_candidate(candidate_id,created_at); ix_ai_interview_script_feedback_candidate_id(candidate_id); ix_ai_interview_script_feedback_outcome(outcome) | uq_ai_interview_script_feedback_idempotency(idempotency_key) |
| ai_outputs | AIOutput | ai | id | - | ix_ai_outputs_expires_at(expires_at); ix_ai_outputs_scope_kind(scope_type,scope_id,kind) | uq_ai_outputs_scope_kind_hash(scope_type,scope_id,kind,input_hash) |
| ai_request_logs | AIRequestLog | ai | id | - | ix_ai_request_logs_principal_day(principal_type,principal_id,created_at); ix_ai_request_logs_scope(scope_type,scope_id,kind) | - |
| analytics_events | (table only) | platform | id | - | idx_analytics_events_candidate_id(candidate_id); idx_analytics_events_created_at(created_at); idx_analytics_events_event_name(event_name); idx_analytics_events_user_id(user_id) | - |
| audit_log | AuditLog | platform | id | - | ix_audit_log_action(action); ix_audit_log_created_at(created_at); ix_audit_log_entity_id(entity_id); ix_audit_log_entity_type(entity_type); ix_audit_log_username(username) | - |
| auth_accounts | AuthAccount | platform | id | - | - | uq_auth_accounts_username(username) |
| candidate_external_identities | CandidateExternalIdentity | candidates | id | candidate_id->users.id | ix_candidate_external_identity_resume(source,external_resume_id); ix_candidate_external_identity_vacancy(source,external_vacancy_id) | uq_candidate_external_identity_candidate(candidate_id,source); uq_candidate_external_identity_negotiation(source,external_negotiation_id) |
| candidate_hh_resumes | CandidateHHResume | candidates | id | candidate_id->users.id | ix_candidate_hh_resumes_candidate(candidate_id); ix_candidate_hh_resumes_candidate_id(candidate_id); ix_candidate_hh_resumes_content_hash(content_hash) | uq_candidate_hh_resumes_candidate(candidate_id) |
| candidate_journey_events | CandidateJourneyEvent | candidates | id | candidate_id->users.id | ix_candidate_journey_events_candidate_created(candidate_id,created_at); ix_candidate_journey_events_candidate_id(candidate_id); ix_candidate_journey_events_event_key(event_key) | - |
| chat_messages | ChatMessage | candidates | id | candidate_id->users.id | ix_chat_messages_candidate_created_at(candidate_id,created_at) | col_unique(client_request_id); unnamed(client_request_id) |
| cities | City | operations | id | responsible_recruiter_id->recruiters.id | ix_cities_responsible_recruiter_id(responsible_recruiter_id) | uq_city_name(name) |
| hh_connections | HHConnection | hh_integration | id | - | ix_hh_connections_employer(employer_id,manager_account_id); ix_hh_connections_status(status) | uq_hh_connections_principal(principal_type,principal_id); uq_hh_connections_webhook_key(webhook_url_key) |
| hh_negotiations | HHNegotiation | hh_integration | id | candidate_identity_id->candidate_external_identities.id; connection_id->hh_connections.id | ix_hh_negotiations_resume_vacancy(external_resume_id,external_vacancy_id); ix_hh_negotiations_state(employer_state,collection_name) | uq_hh_negotiations_external(external_negotiation_id) |
| hh_sync_jobs | HHSyncJob | hh_integration | id | candidate_id->users.id; connection_id->hh_connections.id | ix_hh_sync_jobs_candidate(candidate_id,status); ix_hh_sync_jobs_entity(entity_type,entity_external_id); ix_hh_sync_jobs_status(status,next_retry_at) | uq_hh_sync_jobs_idempotency(idempotency_key) |
| hh_webhook_deliveries | HHWebhookDelivery | hh_integration | id | connection_id->hh_connections.id | ix_hh_webhook_deliveries_action(action_type,received_at); ix_hh_webhook_deliveries_status(status) | uq_hh_webhook_deliveries_connection_delivery(connection_id,delivery_id) |
| message_templates | MessageTemplate | other | id | city_id->cities.id | - | uq_template_key_locale_channel_version(key,locale,channel,city_id,version) |
| outbox_notifications | OutboxNotification | other | id | booking_id->slots.id | ix_outbox_correlation(correlation_id); ix_outbox_status_created(status,created_at); ix_outbox_status_retry(status,next_retry_at) | - |
| recruiters | Recruiter | operations | id | - | - | col_unique(tg_chat_id); unnamed(tg_chat_id) |
| slot_assignments | SlotAssignment | operations | id | candidate_id->users.candidate_id; recruiter_id->recruiters.id; slot_id->slots.id | ix_slot_assignments_candidate_status(candidate_id,status); ix_slot_assignments_recruiter_status(recruiter_id,status); ix_slot_assignments_slot_status(slot_id,status); uq_slot_assignments_candidate_active(candidate_id) | - |
| slot_reschedule_requests | RescheduleRequest | operations | id | alternative_slot_id->slots.id; slot_assignment_id->slot_assignments.id | ix_slot_reschedule_assignment_status(slot_assignment_id,status); uq_slot_reschedule_pending(slot_assignment_id) | - |
| slots | Slot | operations | id | candidate_city_id->cities.id; candidate_id->users.candidate_id; city_id->cities.id; recruiter_id->recruiters.id | ix_slots_candidate_id(candidate_id); ix_slots_city_id(city_id); ix_slots_recruiter_start(recruiter_id,start_utc); ix_slots_status(status) | - |
| users | User | candidates | id | responsible_recruiter_id->recruiters.id | ix_users_candidate_id(candidate_id); ix_users_candidate_status(candidate_status); ix_users_phone_normalized(phone_normalized); ix_users_responsible_recruiter(responsible_recruiter_id); ix_users_telegram_id(telegram_id); ix_users_telegram_user_id(telegram_user_id); ix_users_username(username); ix_users_workflow_status(workflow_status) | col_unique(candidate_id); col_unique(telegram_id); col_unique(telegram_user_id) |
| vacancies | Vacancy | operations | id | city_id->cities.id | ix_vacancies_city_id(city_id) | uq_vacancy_slug(slug) |

### Как сейчас хранятся данные

- Персональные данные кандидата в основном сосредоточены в `users` и `chat_messages`.
- Сообщения: `chat_messages` (контент и channel metadata) + `outbox_notifications` (очередь/доставка/reties).
- AI результаты: `ai_outputs`, `ai_request_logs`, `candidate_hh_resumes`, `ai_interview_script_feedback`, `ai_agent_threads/messages`.
- Audit trail: `audit_log` есть, но покрытие не универсально для всех бизнес-действий.
- Event log: `analytics_events` и `candidate_journey_events` существуют, но не являются единым canonical source of truth.
- Защита от дублей: strong only for some identities (`telegram_id`, `telegram_user_id`, HH external identities). Для `phone_normalized` есть индекс, но нет unique/merge contract.

### Связи и enum/status observations

- `users` остаётся перегруженной таблицей: candidate profile + workflow state + channel ids + HH fields.
- Slot layer в целом зрелый: `slots` и `slot_assignments` хорошо отделяют availability и candidate-specific reservation lifecycle.
- AI layer хранится отдельно и уже имеет indexes/uniques для cache/logs.
- HH foundation выглядит системно лучше, чем старый compatibility sync слой: есть connection, webhook delivery log, negotiations, jobs, external identities.

### Потенциальные проблемы БД

- нет explicit `application`/`requisition`;
- status fields дублируют друг друга;
- history/eventing разнесены по нескольким таблицам и частично overlapping;
- delivery analytics для messages не first-class;
- hard dedupe/merge pipeline отсутствует;
- vacancy/source analytics ограничены текущей связностью схемы.

### Рекомендуемая целевая модель данных

Рекомендую двигаться к следующей модели без попытки “патчить users бесконечно”:

1. `candidates`
- Личный профиль, контакты, consent/PII flags, canonical person identity.

2. `candidate_channel_identities`
- `candidate_id`, `channel`, `external_user_id`, `username/handle`, `linked_at`, `is_primary`, `last_seen_at`.
- Заменяет Telegram/Max-specific поля в `users` как core identity surface.

3. `requisitions`
- Заявка на подбор / hiring request: владелец, город, вакансия, SLA, funnel target, priority.

4. `applications`
- Связь кандидат ↔ вакансия/заявка.
- На этом уровне должны жить lifecycle, source attribution, final outcome, rejection reasons, recruiter owner.

5. `application_events`
- Единый immutable event log переходов, автоматизаций, AI suggestions, recruiter actions.

6. `interviews`
- Отдельная сущность интервью/ознакомительного дня, отвязанная от raw slots.
- Поля: `application_id`, `slot_id`, `kind`, `status`, `result`, `reason`, `feedback_json`, `interviewer_id`.

7. `tasks`
- Explicit recruiter task model: owner, due_at, SLA breach, resolution, origin event.

8. `message_threads` + `message_deliveries`
- Thread history отдельно от provider delivery attempts and receipts.

9. `dedup_candidates`
- Suspected duplicates, match score, operator decision, merge audit.

10. `ai_decision_records`
- Structured AI input/output + acceptance/rejection by human, linked to `application_events`.

## 7. n8n workflows

Экспортированных n8n workflow JSON/YAML в репозитории не найдено. Анализ строится по call sites и callback endpoints.

| Workflow | Trigger | Что делает | Входные данные | Выходные данные | Риски | Что улучшить |
| --- | --- | --- | --- | --- | --- | --- |
| hh_status_sync | Outbox event -> webhook to N8N_HH_SYNC_WEBHOOK_URL | Передаёт HH sync задачу во внешний automation layer. | candidate_id, target HH status, payload from outbox | Callback to /api/hh-sync/callback | Workflow logic невидима в repo; retry/idempotency partly split между code и n8n. | Экспортировать workflow и version it рядом с кодом. |
| hh_negotiation_resolve | Resume/HH resolution flow -> webhook to N8N_HH_RESOLVE_WEBHOOK_URL | Пытается разрешить negotiation/vacancy по HH context. | candidate_id, resume_id/negotiation context | Callback to /api/hh-sync/resolve-callback | Нет repo-local source of truth; сложно ревьюить edge cases. | Сделать explicit contract, timeout/retry policy и versioned workflow export. |
| hh_webhook_ingestion | HH sends webhook to /api/hh-integration/webhooks/{webhook_key} | Пишет delivery log и enqueue reimport jobs. | HH delivery envelope | hh_webhook_deliveries + hh_sync_jobs | Auth строится на webhook key in path; нужна governance around key lifecycle. | Добавить lifecycle management and monitoring for webhook keys/subscriptions. |

## 8. AI-часть

### Что реализовано

- Candidate summary / coach / coach drafts.
- Chat reply drafts.
- Dashboard insights.
- City candidate recommendations.
- Internal AI agent chat.
- Interview script generation with stronger schema discipline.
- HH resume normalization and AI-assisted interview feedback capture.

### Какие модели и provider path используются

- Provider abstraction: `backend/core/ai/providers`.
- `OpenAIProvider` использует Responses API для GPT-5 family и fallback на Chat Completions для older model surface.
- В compose/settings есть env variables: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `AI_*` budget/quota flags.

### Где лежат промпты и схемы

- Prompts: `backend/core/ai/prompts.py`.
- Schemas: `backend/core/ai/schemas.py`.
- Interview script generation: `backend/core/ai/llm_script_generator.py`.
- Logging/cache: `backend/core/ai/service.py`.

### Structured output / validation / fallback

- Плюс: есть JSON-object mode, repair pass и cache/quota logging.
- Минус: многие schemas **намеренно permissive** и допускают пустые/default-heavy payloads.
- Исключение в лучшую сторону: interview script flow имеет строгую Pydantic/JSON schema и выраженный fallback builder.

### Логирование и governance

- Есть `ai_request_logs` и `ai_outputs`.
- Есть `ai_interview_script_feedback`, что уже приближает human-in-the-loop.
- Но нет единого decision trail “AI suggestion -> recruiter accepted/edited/rejected -> final action” для всех high-impact AI flows.

### Human-in-the-loop и risk assessment

- По текущему коду AI mostly advisory: summaries, drafts, recommendations.
- Явного автоматического отказа кандидату solely by AI не найдено.
- Основной риск не в “AI auto-reject”, а в том, что permissive output schema может silently ухудшать recommendations/UX без явного падения.

### Вывод по AI

Что можно оставить:
- provider abstraction;
- request logging + quota/budget controls;
- interview script flow как наиболее зрелый пример structured AI.

Что нужно усилить:
- strict JSON schemas для summary/coach/drafts/insights;
- linking AI result to final recruiter action;
- clear acceptance markers and audit trail.

Что опасно:
- permissive default-heavy schemas на high-impact recruiter decisions;
- отсутствие unified governance around AI acceptance/use.

Что перевести на строгую JSON-схему в первую очередь:
- candidate summary;
- candidate coach;
- chat drafts / coach drafts;
- dashboard insights;
- city candidate recommendations.

## 9. Качество кода

### Общая оценка

- Архитектура: сильная доменная насыщенность, но границы эволюционировали неравномерно; есть mature areas и слои с историческим drift.
- Читаемость: в среднем нормальная, но есть очень крупные router/service файлы (`api_misc.py`, candidates-related surfaces).
- Дублирование: заметное на уровне status fields, docs, old/new channel contracts.
- Связанность: высокая между candidate core, scheduling, Telegram and analytics.
- Error handling: есть много defensive fallback/degraded responses, но местами они скрывают structural problems.
- Типизация: сильная в TS client surface и Pydantic/SQLAlchemy, слабее в cross-module state semantics.
- Безопасность: auth/session/CSRF в admin surface в целом продуманы; webhook/channel/config surface требует дополнительной discipline.
- Тестируемость: хорошая база тестов есть, но current dirty workspace создаёт coverage uncertainty around removed flows.
- Производительность/масштабируемость: operational queues/Redis/async stack есть, но часть hot paths ещё telegram-centric и not application-centric.

### Top-20 технических проблем

| Приоритет | Проблема | Где | Почему важно | Как исправить |
| --- | --- | --- | --- | --- |
| P0 | max_bot runtime сломан: compose и entrypoint ссылаются на удалённый backend.apps.max_bot.app. | docker-compose.yml; max_bot.py; backend/apps/max_bot/ | Включение профиля max приводит к мгновенному падению сервиса и ложному ощущению готовности канала. | Либо восстановить реализацию Max bot, либо удалить сервис, env surface и документацию из runtime-контура. |
| P0 | frontend/app/openapi.json устарел относительно live admin_ui app. | frontend/app/openapi.json; backend/apps/admin_ui/app.py | Клиентская типизация и интеграционный контракт расходятся с текущим backend; возможны неверные автогенерированные типы и ложные ожидания QA. | Генерировать OpenAPI из текущего app в CI и падать при drift; удалить мёртвые candidate portal paths. |
| P0 | Candidate portal удалён из runtime, но следы остаются в schema/docs/DTO. | frontend/app/openapi.json; docs/frontend/route-map.md; frontend/app/src/api/services/candidates.ts | Команда видит несуществующий публичный канал и может строить процессы/интеграции поверх нерабочего контракта. | Принять явное продуктовое решение: Telegram-first only или восстановление portal; затем зачистить оставшийся контракт. |
| P1 | Канонические docs устарели и описывают удалённые candidate portal / Max bot потоки. | docs/frontend/route-map.md; docs/security/*; docs/qa/* | Аудит, онбординг и change planning опираются на неверную карту системы. | Пересобрать docs from code: runtime topology, route map, trust boundaries, critical flows. |
| P1 | Нет отдельной сущности application/requisition; кандидат и отклик смешаны в users. | backend/domain/candidates/models.py; backend/domain/models.py | Нельзя нормально вести одного кандидата на несколько вакансий, строить pipeline per vacancy и считать конверсию. | Добавить Application и HiringRequest/Requisition как first-class сущности. |
| P1 | Статусная модель фрагментирована: candidate_status, workflow_status, lifecycle_state, final_outcome. | backend/domain/candidates/models.py; backend/domain/candidates/status_service.py | Легко получить расхождение между operational status, archival state и итогом найма. | Оставить один canonical lifecycle + отдельную историю переходов/event log. |
| P1 | Дедупликация кандидатов неполная: phone_normalized индексируется, но не защищён уникальным правилом и merge-flow отсутствует. | backend/domain/candidates/models.py; backend/domain/hh_integration/importer.py | При повторных лидах и мультиканальном intake будут появляться дубли и разъезжаться коммуникации. | Ввести dedup_keys, review queue и controlled merge process. |
| P1 | RBAC coarse-grained: только admin/recruiter, без fine-grained permissions и team scoping. | backend/domain/auth_account.py; frontend/app/src/app/components/RoleGuard.tsx | Трудно безопасно разделять доступ к аналитике, шаблонам, справочникам и системным операциям. | Добавить permission matrix и policy layer server-side. |
| P1 | Messenger health и часть доменной логики всё ещё Telegram-centric. | backend/apps/admin_ui/services/messenger_health.py; backend/domain/candidates/status_service.py | Переход к multi-channel будет дорогим и рискованным; observability уже искажена. | Вынести channel identity и channel health в channel-agnostic model. |
| P1 | n8n workflows не versioned в repo; есть только webhook call sites. | backend/domain/hh_sync/*; backend/apps/admin_api/hh_sync.py | Нельзя полноценно ревьюить и воспроизводить интеграционную логику. | Экспортировать workflow JSON/YAML и ввести owner/versioning/rollback policy. |
| P1 | OpenAPI generation and some boot paths зависят от состояния БД даже для read-only introspection. | backend/apps/admin_ui/app.py startup path; question warmup | Инструменты документации/CI могут деградировать на пустой БД и скрывать реальный API contract. | Изолировать schema export from startup warmup, make docs generation side-effect free. |
| P1 | README ссылается на отсутствующий VERIFICATION_COMMANDS.md. | README.md | Снижает воспроизводимость verification flow и доверие к canonical docs. | Либо восстановить документ, либо убрать ссылку и описать команды напрямую. |
| P2 | Большинство AI schemas намеренно permissive; строгая JSON schema применена не везде. | backend/core/ai/schemas.py; backend/core/ai/providers/openai.py | Malformed output может тихо ухудшать UX или рекомендации без явного фейла. | Перевести high-impact AI flows на strict JSON schema + explicit validator/fallback. |
| P2 | AI output logging есть, но human-in-the-loop и audit of final recruiter actions не доведены до единого decision trail. | backend/core/ai/service.py; backend/domain/ai/models.py | Сложно доказать, что AI не принимал значимые решения автоматически. | Связать AIOutput/AIRequestLog с final recruiter action/event log and explicit acceptance markers. |
| P2 | Analytics per vacancy/source/recruiter неполные из-за отсутствия canonical application entity и fragmented state. | backend/domain/analytics.py; backend/domain/analytics_models.py | Head of recruiting не получит надёжную funnel analytics по вакансиям и каналам. | Пересобрать event taxonomy around application lifecycle and candidate-source attribution. |
| P2 | No-show и reactivation flows частично реализованы, но не оформлены как отдельные управляемые процессы. | backend/apps/bot/handlers/attendance.py; backend/apps/admin_ui/services/detailization.py | Потери на последних шагах воронки трудно системно вытаскивать. | Выделить explicit no-show recovery and reactivation tasks/templates/SLA. |
| P2 | Коммуникации хранятся на уровне chat_messages, но нет отдельной message thread / delivery attempt модели для multi-channel аналитики. | backend/domain/candidates/models.py; backend/apps/admin_ui/services/chat.py | Трудно анализировать доставку, повторные попытки и channel conversion. | Добавить message_threads, message_deliveries, provider receipts, campaign/source tags. |
| P2 | В workspace есть локальный .env.local; файл игнорируется git, но требуется строгая secret hygiene around examples and tooling. | .env.local (ignored); .env.example; docker-compose.env.example | Есть риск случайного использования placeholder defaults и leakage через tooling/docs. | Сохранить .env.local в ignore, не читать его в audit, зачистить примеры до safe placeholders only. |
| P2 | Rate limiting в dev/test часто уходит в in-memory fallback, что не соответствует production-grade distributed control. | backend/apps/admin_ui/security.py | При неверной prod конфигурации limits будут частичными и неравномерными между workers. | Сделать hard fail for production without Redis-backed rate limiter. |
| P2 | В SPA остались DTO/стили/контракты для удалённых candidate portal/MAX flows. | frontend/app/src/api/services/candidates.ts; frontend/app/src/app/routes/candidate-portal.css | Усложняет поддержку и мешает понять реальный supported surface. | Удалить dead frontend contracts after product decision on supported channels. |
| P2 | Большой объём удалений portal/MAX-related tests в dirty workspace создаёт coverage gap до стабилизации ветки. | git status --short; tests/* related deletions | После стабилизации ветки можно потерять regression coverage по каналам и auth flows. | Перед merge провести explicit coverage review и обновить critical flow catalog. |

## 10. Безопасность и данные кандидатов

### Что проверено

- где лежат PII;
- auth/authz;
- публичные endpoints;
- webhook protection;
- session/csrf;
- rate limit;
- env surface;
- audit/logging.

### Наблюдения

- PII кандидата хранится прежде всего в `users`, `chat_messages`, `candidate_hh_resumes`, иногда в HH payload snapshots.
- Admin surface использует session cookie + bearer token + CSRF on mutations.
- `admin_api` Telegram mini-app использует `X-Telegram-Init-Data` validation.
- CORS middleware явным образом не найден; для same-origin admin SPA это нормально, но при появлении новых browser surfaces нужна явная policy.
- Публичные/особые endpoints:
  - `/auth/token`, `/auth/login` — login surface;
  - `/api/webapp/*` — Telegram-signed surface;
  - `/api/hh-sync/*` — header secret protected callbacks;
  - `/api/hh-integration/webhooks/{webhook_key}` — path-key protected HH ingress.
- `.env.local` существует в workspace, но игнорируется git; значения не инспектировались.
- Tracked examples присутствуют: `.env.example`, `.env.local.example`, `.env.development.example`.

### Критические риски

- P0: Max runtime advertised but broken.
- P0: stale public/API contract around candidate portal.
- P1: coarse RBAC without fine-grained authorization.
- P1: n8n/webhook governance not versioned in repo.
- P2: message/channel model makes PII governance harder across future multi-channel growth.

## 11. UX и продуктовая логика

### Как система выглядит для руководителя рекрутинга

Что уже есть:
- единая admin SPA;
- dashboard/funnel/KPI surfaces;
- candidate list/detailization/incoming worklists;
- calendar/tasks;
- messaging and reminders;
- AI copilot as helper.

Где видно боль:
- Воронка есть, но каноническая модель статусов не единая.
- Next action partly присутствует в контрактах, но не является universal operational source of truth.
- SLA как first-class concept не найден.
- Search/filters есть на candidate surfaces, массовые действия ограничены.
- История взаимодействий есть через chat and partial journey events.
- Причины отказа есть частично, но часто не встроены в единую outcome model.
- Аналитика по рекрутерам присутствует лучше всего.
- Аналитика по источникам и вакансиям ограничена отсутствием application/requisition model.

### Продуктовый вывод

Система уже пригодна как operational CRM для текущей команды рекрутеров, но пока плохо масштабируется в сторону:
- много вакансий на одного кандидата;
- точной аналитики по источникам/вакансиям;
- multi-channel candidate communication;
- прозрачного SLA/ownership management.

## 12. Сильные стороны текущей системы

- FastAPI + React monorepo уже содержит зрелый operational surface, а не только прототип.
- Scheduling / slot assignment / reminders — одна из сильнейших частей системы.
- Telegram webapp auth и bot-oriented flows реализованы достаточно глубоко.
- HH integration foundation (`hh_connections`, `hh_webhook_deliveries`, `hh_negotiations`, jobs) выглядит архитектурно перспективно.
- AI layer уже отделён через provider abstraction, cache, quotas и logging; это хорошая основа для дальнейшего hardening.
- В коде видно внимание к CSRF, rate limiting, audit logging, bot notification observability.
- SPA достаточно богата по operational screens: candidates, incoming, calendar, system, copilot, detailization.

## 13. Рекомендуемый roadmap

### Этап 1 — стабилизация фундамента
- Цель: Данные, статусы, дедупликация, безопасность, event log.
- Задачи: Убрать runtime/documentation drift по candidate portal и Max bot.; Ввести canonical lifecycle model и status history/event log.; Сделать dedup review queue по телефону/HH/channel identity.; Нормализовать secrets/config surface и production guards.; Перегенерировать OpenAPI/docs из live code и зафиксировать в CI.
- Ожидаемый эффект: Система снова описывается одним контрактом; меньше дублей и ручного разруливания.
- Сложность: Высокая.
- Риски: Потребуются data migration strategy и careful backward compatibility for UI/API.
- Зависимости: Нужны owner decisions: поддерживаемые candidate channels и target lifecycle.

### Этап 2 — автоматизация операционных процессов
- Цель: Первое касание, квалификация, запись на интервью, напоминания, no-show recovery.
- Задачи: Выделить Application/Interview/Task как first-class entities.; Сделать SLA/next action/worklist на canonical event model.; Усилить reminder/no-show/recovery сценарии и шаблоны коммуникаций.; Сделать multi-channel-ready messaging delivery model.; Версионировать n8n workflows и интеграционные контракты.
- Ожидаемый эффект: Рекрутеру проще понимать, что делать дальше, а руководителю — видеть where process is burning.
- Сложность: Высокая.
- Риски: Потребуется перепривязка analytics и UI к новым сущностям.
- Зависимости: Этап 1 должен завершить canonical data model.

### Этап 3 — интеллектуальный слой
- Цель: AI matching, аналитика, прогноз найма, рекомендации руководителю, реактивация базы.
- Задачи: Перевести high-impact AI flows на strict JSON schema и acceptance logging.; Добавить vacancy/application-level recommendations и source analytics.; Построить reactivation segments и recruiter recommendations по базе.; Сделать management dashboards по recruiter/source/vacancy with forecast metrics.; Добавить human-in-the-loop controls and model governance.
- Ожидаемый эффект: AI начинает усиливать операционку, а не подменять слабую базовую модель данных.
- Сложность: Средняя/высокая.
- Риски: Без strong data foundation AI layer будет давать ложную уверенность.
- Зависимости: Нужны clean lifecycle data, event log и stable application model.

## 14. Первые задачи для разработки

### 1. Синхронизировать runtime-контур каналов кандидата
Название: Синхронизировать runtime-контур каналов кандидата
Цель: Убрать расхождение между кодом, OpenAPI, docs и compose.
Контекст: Candidate portal и Max bot частично удалены из runtime, но остаются в контрактах и документации.
Что сделать: Принять supported-channel matrix; удалить/восстановить соответствующие route/docs/schema/env surfaces.
Критерии готовности: Нет stale route/docs/schema references; CI проверяет drift.
Файлы/модули: backend/apps/admin_ui/app.py, frontend/app/openapi.json, docs/frontend/route-map.md, docker-compose.yml, max_bot.py
Риски: Нужна продуктовая фиксация по portal/MAX.
Приоритет: P0

### 2. Ввести canonical candidate lifecycle
Название: Ввести canonical candidate lifecycle
Цель: Свести статусы к одной управляемой модели.
Контекст: users содержит candidate_status, workflow_status, lifecycle_state, final_outcome.
Что сделать: Описать state machine, таблицу переходов и history table.
Критерии готовности: Один canonical lifecycle + event/history model + миграционный план.
Файлы/модули: backend/domain/candidates/models.py, backend/domain/candidates/status_service.py
Риски: Потребуется обратная совместимость для UI и analytics.
Приоритет: P0

### 3. Добавить application entity
Название: Добавить application entity
Цель: Развязать кандидата и отклик/вакансию.
Контекст: Сейчас vacancy linkage mostly implicit.
Что сделать: Спроектировать Application(candidacy) и привязать slots/interviews/messages/analytics к application_id.
Критерии готовности: Target schema и migration design approved.
Файлы/модули: backend/domain/candidates/models.py, backend/domain/models.py, frontend/app/src/api/services/candidates.ts
Риски: Затрагивает почти все recruiter flows.
Приоритет: P0

### 4. Сделать dedup review queue
Название: Сделать dedup review queue
Цель: Остановить разрастание дублей.
Контекст: Phone normalized только индексирован; merge flow отсутствует.
Что сделать: Определить matching rules, suspicion score, operator review and merge actions.
Критерии готовности: Есть модель dedup candidate pairs и безопасный merge policy.
Файлы/модули: backend/domain/candidates/models.py, backend/domain/hh_integration/importer.py
Риски: Ошибочный merge может портить историю кандидата.
Приоритет: P0

### 5. Построить единый event log
Название: Построить единый event log
Цель: Сделать воронку и действия воспроизводимыми.
Контекст: Есть audit_log, analytics_events, candidate_journey_events, но нет единого canonical trail.
Что сделать: Определить event taxonomy и запись ключевых recruiter/system/AI events.
Критерии готовности: Любой переход кандидата объясняется цепочкой событий.
Файлы/модули: backend/core/audit.py, backend/domain/analytics.py, backend/domain/candidates/models.py
Риски: Нельзя перезасорить лог без retention policy.
Приоритет: P0

### 6. Production guard для rate limiting
Название: Production guard для rate limiting
Цель: Исключить in-memory fallback в проде.
Контекст: security._build_limiter умеет fallback to memory.
Что сделать: Сделать hard fail when production/staging without Redis-backed limiter.
Критерии готовности: Прод не стартует без корректного rate limiter storage.
Файлы/модули: backend/apps/admin_ui/security.py, backend/core/settings.py
Риски: Потребует явного обновления deploy env.
Приоритет: P1

### 7. Усилить webhook security contracts
Название: Усилить webhook security contracts
Цель: Сделать входящие интеграции более проверяемыми и audit-friendly.
Контекст: HH callbacks защищены header secret / webhook_key, но contracts не унифицированы.
Что сделать: Описать signature policy, replay protection, observability и documented error model.
Критерии готовности: Все webhook endpoints имеют единый security checklist.
Файлы/модули: backend/apps/admin_api/hh_sync.py, backend/apps/hh_integration_webhooks.py
Риски: Нужно не сломать действующие интеграции.
Приоритет: P1

### 8. Версионировать n8n workflows
Название: Версионировать n8n workflows
Цель: Убрать чёрный ящик вокруг HH orchestration.
Контекст: В repo есть только webhook URLs/env names and callback handlers.
Что сделать: Экспортировать workflows и привязать их к code owners/change management.
Критерии готовности: Любой n8n flow доступен для review и rollback.
Файлы/модули: backend/domain/hh_sync/*, docs/hh/*
Риски: Потребуется дисциплина на стороне ops.
Приоритет: P1

### 9. Нормализовать channel identities
Название: Нормализовать channel identities
Цель: Убрать Telegram-centric assumptions from candidate core.
Контекст: users содержит telegram_id, telegram_user_id, max_user_id и messenger_platform.
Что сделать: Ввести candidate_channel_identities с channel, external_user_id, linkage status, last_seen.
Критерии готовности: Core services не завязаны на telegram_id как primary key.
Файлы/модули: backend/domain/candidates/models.py, backend/domain/candidates/status_service.py
Риски: Затрагивает bot/webapp paths.
Приоритет: P1

### 10. Выделить interview entity
Название: Выделить interview entity
Цель: Отделить интервью как событие оценки от slots и notes.
Контекст: Сейчас interview_notes и slot statuses смешивают scheduling и evaluation.
Что сделать: Добавить Interview/InterviewOutcome/InterviewerFeedback model.
Критерии готовности: Есть отдельная сущность интервью с исходом и причинами.
Файлы/модули: backend/domain/candidates/models.py, backend/domain/models.py
Риски: Потребуется UI redesign карточки кандидата.
Приоритет: P1

### 11. Сделать task/SLA model для recruiters
Название: Сделать task/SLA model для recruiters
Цель: Показывать next action и дедлайны не как derived guess, а как операционный контракт.
Контекст: candidate_next_action already exists in client contract, but logic fragmented.
Что сделать: Ввести explicit recruiter tasks, SLA timers, escalations.
Критерии готовности: Любой активный кандидат имеет owner, next action, due_at.
Файлы/модули: frontend/app/src/api/services/candidates.ts, backend/apps/admin_ui/services/dashboard.py
Риски: Нужно не задушить интерфейс бюрократией.
Приоритет: P1

### 12. Пересобрать analytics taxonomy
Название: Пересобрать analytics taxonomy
Цель: Сделать надёжные KPI по vacancy/source/recruiter.
Контекст: analytics_events table есть, но source-of-truth слабый.
Что сделать: Определить canonical event names and dimensions around application lifecycle.
Критерии готовности: Воронка по вакансиям и источникам воспроизводится из событий.
Файлы/модули: backend/domain/analytics.py, backend/domain/analytics_models.py
Риски: Может потребоваться backfill strategy.
Приоритет: P1

### 13. Сделать no-show recovery workflow
Название: Сделать no-show recovery workflow
Цель: Уменьшить потери после назначения интервью/ОД.
Контекст: No-show зафиксирован как статус, но recovery flow не выделен.
Что сделать: Добавить templates, timers, retry windows, owner actions and reporting.
Критерии готовности: No-show candidates попадают в отдельную worklist и имеют scripted recovery.
Файлы/модули: backend/apps/bot/handlers/attendance.py, backend/apps/admin_ui/services/detailization.py
Риски: Потребуется аккуратно настроить частоту коммуникаций.
Приоритет: P1

### 14. Поднять strict JSON schemas для AI high-impact flows
Название: Поднять strict JSON schemas для AI high-impact flows
Цель: Снизить риск malformed AI outputs.
Контекст: Сейчас strict schema по-настоящему сильна только в interview script flow.
Что сделать: Перевести summary/coach/drafts/insights на explicit schema + repair/fallback policy.
Критерии готовности: Невалидный AI payload не попадает в UI silently.
Файлы/модули: backend/core/ai/schemas.py, backend/core/ai/providers/openai.py, backend/core/ai/service.py
Риски: Может вырасти latency / error rate until prompts tuned.
Приоритет: P1

### 15. Связать AI output с final recruiter action
Название: Связать AI output с final recruiter action
Цель: Сделать AI decision trail audit-friendly.
Контекст: AI logs and feedback exist, but acceptance markers are not universal.
Что сделать: Логировать whether draft/summary/recommendation was used, edited or rejected.
Критерии готовности: Для high-impact AI flows доступен human-in-the-loop audit.
Файлы/модули: backend/domain/ai/models.py, backend/core/ai/service.py
Риски: Нужно не перегрузить рекрутера дополнительными полями.
Приоритет: P1

### 16. Усилить message delivery model
Название: Усилить message delivery model
Цель: Разделить thread/message/delivery attempt/outbox.
Контекст: chat_messages и outbox_notifications покрывают разные слои, но аналитика доставки fragmented.
Что сделать: Добавить message_threads, deliveries, provider receipts and campaign/source tags.
Критерии готовности: Можно ответить, что было отправлено, через какой канал и с каким результатом.
Файлы/модули: backend/domain/candidates/models.py, backend/apps/admin_ui/services/chat.py, backend/domain/models.py
Риски: Потребует миграции existing message history.
Приоритет: P1

### 17. Пересобрать system/channel health dashboard
Название: Пересобрать system/channel health dashboard
Цель: Показывать реальное состояние всех каналов.
Контекст: messenger_health currently Telegram only, despite historical MAX surface.
Что сделать: Сделать channel registry and health adapters per active channel.
Критерии готовности: System page показывает only supported channels and truthful degradation reasons.
Файлы/модули: backend/apps/admin_ui/services/messenger_health.py, frontend/app/src/api/services/system.ts
Риски: Нужно синхронизировать с supported-channel matrix.
Приоритет: P2

### 18. Очистить dead frontend contracts
Название: Очистить dead frontend contracts
Цель: Упростить поддержку SPA и API client.
Контекст: candidates.ts still carries portal/MAX oriented DTO surface.
Что сделать: Удалить неиспользуемые DTO, orphan CSS and stale route helpers after contract decision.
Критерии готовности: API client отражает только supported flows.
Файлы/модули: frontend/app/src/api/services/candidates.ts, frontend/app/src/app/routes/candidate-portal.css
Риски: Нельзя удалить то, что still used in another branch.
Приоритет: P2

### 19. Пересобрать canonical docs from code
Название: Пересобрать canonical docs from code
Цель: Сделать README/docs снова trustworthy.
Контекст: Docs drift now materially affects onboarding and architecture decisions.
Что сделать: Regenerate route map, trust boundaries, critical flows, verification docs.
Критерии готовности: Docs referenced in README/AGENTS reflect current runtime.
Файлы/модули: README.md, docs/frontend/route-map.md, docs/security/*, docs/qa/*
Риски: Нужен owner процесса поддержания docs актуальными.
Приоритет: P2

## 15. Финальный executive summary

### Что система уже умеет

- вести кандидатов в recruiter/admin интерфейсе;
- назначать и подтверждать слоты;
- вести Telegram-коммуникации и напоминания;
- импортировать и синхронизировать HH контекст;
- давать AI-assisted summaries/drafts/scripts;
- показывать dashboard/KPI/recruiter views.

### Что мешает масштабированию

- нет явной модели `application / requisition`;
- статусная модель раздроблена;
- candidate channel / portal / Max surface в drift состоянии;
- аналитика не опирается на единый application/event model;
- docs/OpenAPI/contracts не синхронизированы с live current code.

### 5 доработок с максимальным эффектом

1. Принять supported-channel matrix и зачистить runtime/docs/schema drift.
2. Ввести canonical lifecycle + history/event log.
3. Добавить application/requisition model.
4. Запустить dedup review/merge process.
5. Перевести high-impact AI flows на strict JSON schema + acceptance logging.

### Что делать первым

Сначала закрыть фундамент: channel/runtime drift, data model, lifecycle, dedup, event log, webhook/config governance. Без этого любая “умная автоматизация” будет усиливать шум, а не систему.

### Что нельзя автоматизировать без контроля человека

- финальный отказ кандидату;
- merge дублей кандидатов;
- решение о переводе в ключевой этап воронки при неполных данных;
- правки системных шаблонов и интеграционных маршрутов;
- high-impact AI recommendations без explicit recruiter acceptance.

## Appendix: что ещё надо проверить дополнительно

- После стабилизации dirty ветки повторно сравнить удалённые tests/docs against intended product decision.
- Проверить, не живут ли внешние n8n workflows вне репозитория как единственный source of truth.
- Пересчитать frontend route map после регенерации live OpenAPI/docs.
- После восстановления clean env прогнать full gates: backend tests, frontend lint/typecheck/test/build, smoke e2e.
