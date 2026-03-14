# Candidate Channels Audit

## Scope

Аудит выполнен по живому коду backend/frontend и тестам, а не по старым markdown-описаниям. Ключевые inspected modules:

- `backend/apps/bot/*`
- `backend/apps/admin_api/webapp/*`
- `backend/apps/admin_ui/services/{candidates,chat,slots}.py`
- `backend/apps/max_bot/app.py`
- `backend/domain/{models,repositories,analytics,slot_assignment_service}.py`
- `backend/domain/candidates/{models,services,status,status_service,workflow}.py`
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/tg-app/*`
- `tests/test_candidate_lead_and_invite.py`
- `tests/test_webapp_booking_api.py`
- `tests/test_max_bot.py`

## Executive Summary

Текущая система уже содержит зачатки channel-agnostic слоя:

- у кандидата есть стабильный `candidate_id`;
- в профиле есть `messenger_platform` и `max_user_id`;
- сообщения и нотификации хранятся отдельно от Telegram API (`ChatMessage`, `OutboxNotification`);
- есть registry/adapters для нескольких мессенджеров;
- слот-бронирование можно вызвать не только из бота, но и через HTTP API.

Но фактический candidate journey по-прежнему Telegram-first и во многих местах Telegram-only:

- первый вход и основной screening живут в `backend/apps/bot/services.py`;
- состояние сценария хранится по `telegram_id` в bot state store;
- статусы, reminders, recruiter chat и значимая часть scheduling side effects адресуются через `telegram_id` / `candidate_tg_id`;
- имеющийся webapp API доступен только через Telegram WebApp `initData`, то есть это не независимый веб-канал;
- recruiter-facing SPA имеет mini-app маршрут `/tg-app/*`, но candidate-facing web portal отсутствует.

Практический вывод: system core можно эволюционно отвязать от Telegram, но первым шагом должен быть не второй бот, а вынос candidate journey в универсальный web-first слой с messenger adapters и fallback notifications.

## Current Entry Into The System

### Main as-is entry flow

1. Кандидат пишет боту `/start`.
2. Бот создает/обновляет `User` по `telegram_id`.
3. В bot state store инициализируется состояние Test1.
4. Кандидат проходит анкету/скрининг в чате.
5. После завершения Test1:
   - создается `TestResult` + `QuestionAnswer`;
   - статус продвигается в `TEST1_COMPLETED` и затем `WAITING_SLOT`;
   - если есть слоты, бот предлагает рекрутера и слоты;
   - если слотов нет, бот просит прислать диапазон времени вручную.
6. При выборе слота создается reservation со статусом `pending`, рекрутер получает Telegram-уведомление на approve/reject/reschedule.
7. После подтверждения кандидату отправляются инструкции и reminders.
8. После записи и/или handoff дальнейшая коммуникация рекрутера с кандидатом идет в CRM, но доставка снова Telegram-centric.

### Secondary entry patterns already present

- Manual lead из CRM:
  - рекрутер создает `User` без Telegram (`source="manual_call"`, статус `LEAD`);
  - может сгенерировать invite token;
  - кандидат потом привязывает Telegram через `/invite <token>`.
- Telegram WebApp booking:
  - уже есть `/api/webapp/*`;
  - позволяет смотреть слоты/бронировать/переносить;
  - но работает только для уже аутентифицированного Telegram-пользователя.
- Max webhook:
  - есть отдельный сервис и adapter bootstrap;
  - production-grade candidate flow поверх него пока отсутствует.

## Entity Map

| Business entity | Current implementation | Notes |
| --- | --- | --- |
| Candidate | `backend/domain/candidates/models.py::User` | Отдельной модели `Candidate` нет; кандидат, лид и участник воронки хранятся в `users` |
| Application / Lead | `User.source` + `User.candidate_status` | Отдельной сущности application/lead нет; lead-модель размазана по `User`, статусам и source |
| Screening / Test | `TestResult`, `QuestionAnswer`, `Test2Invite` | Test1 хранится как результат без отдельной сущности screening session |
| Slot / Interview Slot | `backend/domain/models.py::Slot` | Хранит и интервьевые, и intro day слоты |
| SlotAssignment | `SlotAssignment`, `RescheduleRequest`, `ActionToken` | Более новый scheduling workflow; пока не является основой всего candidate flow |
| Recruiter / Queue | `Recruiter`, связи recruiter-city, `responsible_recruiter_id` | Отдельной queue entity нет; очередь выражена через waiting statuses, city ownership и dashboard |
| Status / Pipeline Stage | `CandidateStatus`, `workflow_status` | Есть legacy status enum и параллельный workflow status |
| Message / Notification | `ChatMessage`, `Notification`, `MessageLog`, `NotificationLog`, `OutboxNotification` | Storage частично универсален, отправка нет |
| Event / Audit log | `analytics_events`, `AuditLog` | Funnel events есть, но в naming и metadata доминирует bot-centric модель |

## Where Logic Lives Today

### Telegram bot

- Оркестрация journey: `backend/apps/bot/services.py`
- Handlers/callbacks: `backend/apps/bot/handlers/*`
- State store: `backend/apps/bot/state_store.py`
- Validation Test1: `backend/apps/bot/test1_validation.py`
- Reminders: `backend/apps/bot/reminders.py`

### API

- Admin app/API: `backend/apps/admin_ui/*`
- Telegram WebApp candidate/recruiter API: `backend/apps/admin_api/webapp/*`
- Max webhook API: `backend/apps/max_bot/app.py`

### Frontend

- Main SPA routes: `frontend/app/src/app/main.tsx`
- Telegram mini-app recruiter UI: `frontend/app/src/app/routes/tg-app/*`
- Candidate portal routes: отсутствуют

### Workers / queues / async orchestration

- Outbox queue и retry: `backend/domain/repositories.py`
- Notification poller/processor: `backend/apps/bot/services.py`
- APScheduler reminders: `backend/apps/bot/reminders.py`

### Database / domain layer

- Candidate models: `backend/domain/candidates/models.py`
- Scheduling models: `backend/domain/models.py`
- Reservation logic: `backend/domain/repositories.py`, `backend/domain/slot_service.py`
- Slot assignment workflow: `backend/domain/slot_assignment_service.py`
- Status transitions: `backend/domain/candidates/status_service.py`, `backend/domain/candidate_status_service.py`

### Integrations

- Telegram bot: `backend/apps/bot/*`
- Max: `backend/apps/max_bot/*`, `backend/core/messenger/*`
- hh.ru sync: `backend/domain/hh_sync/*`

### Notifications

- Storage and idempotency: `OutboxNotification`, `NotificationLog`
- Dispatch core: `NotificationService` inside `backend/apps/bot/services.py`
- Channel resolution: `backend/core/messenger/registry.py`

## How Core Behaviors Work Today

### Dialogue state

- State хранится по `user_id`/`telegram_id` в `StateStore`.
- Есть Redis-backed store с TTL.
- Сценарий анкетирования зависит от chat session state, а не от универсальной journey session.
- Потеря или истечение TTL state ломает continuity candidate flow.

### Screening / test scenarios

- Test1 реализован как последовательность вопросов в боте.
- Последовательность и ответы лежат в bot state (`t1_idx`, `t1_sequence`, `test1_answers` и т.д.).
- После завершения результат сохраняется как `TestResult` + `QuestionAnswer`.
- У Test1 нет универсального web/mobile rendering engine; рендеринг и navigation завязаны на мессенджерные сообщения.

### Validation of answers

- Частичная валидация для Test1 уже есть через Pydantic (`apply_partial_validation`).
- Это хороший reuse point для web form engine.
- Но orchestration validation errors и переходов привязана к Telegram messages/callbacks.

### Deduplication

- Сильнее всего dedup работает вокруг `telegram_id` и `candidate_id`.
- В slot reservation уже есть защита от active duplicate bookings.
- Есть merge path при `bind_telegram_to_candidate`.
- Слабое место: manual/web/email/SMS channels пока не имеют нормализованной dedup стратегии по phone/email/external identifiers.

### Interview booking

- Бронирование живет в `reserve_slot`.
- Сервис умеет работать и по `candidate_id`, и по `candidate_tg_id`.
- Но downstream side effects часто используют только `candidate_tg_id`.
- Approve/reject/confirm/reminder flows исторически ориентированы на Telegram callbacks/messages.

### Rescheduling

- Есть два пласта:
  - legacy slot status flow;
  - более зрелый `SlotAssignment`/`RescheduleRequest`/`ActionToken`.
- Новый слой уже ближе к универсальной архитектуре, но на практике не является единым ядром всего candidate path.

### Pushes / reminders

- Reminder jobs строятся по `Slot.candidate_tg_id`.
- Outbox умеет хранить `messenger_channel`, но идентификатор кандидата в очереди пока все равно Telegram-centric.
- Fallback chain между каналами отсутствует.

### Handoff to recruiter

- После booking recruiter получает Telegram notice.
- CRM поддерживает candidate chat thread.
- Но отправка сообщения из CRM требует Telegram ID; если Telegram нет, recruiter thread превращается в read-only историю.

## Telegram Dependency Map

| Area | Current dependency | Consequence |
| --- | --- | --- |
| Candidate onboarding | `/start`, bot handlers, bot state | Без Telegram нет self-service entry |
| Candidate auth for webapp | Telegram `initData` | Existing webapp не работает как резервный канал при недоступном Telegram |
| Screening UX | Question-by-question bot flow | Test1 нельзя переиспользовать как web flow без нового renderer/session layer |
| Candidate identity resolution | `telegram_id`, `telegram_user_id` | Сложно строить omnichannel dedup и resume |
| Status service | `update_candidate_status(telegram_id, ...)` | Domain transitions привязаны к одному каналу |
| Reminders | `Slot.candidate_tg_id` | Нет channel-agnostic reminder orchestration |
| Recruiter chat | `send_chat_message()` требует Telegram ID | Нет универсального candidate communication layer |
| Recruiter approval loop | Telegram inline callbacks | Approval UX зависит от мессенджера |
| Candidate confirmation | Telegram message buttons | Подтверждение/отмена не вынесены в neutral action endpoints |
| Manual scheduling fallback | ForceReply in Telegram | Даже fallback path зависит от Telegram |

## Reusable Universal Layer vs Refactor Targets

### Can be reused with moderate refactor

- `User.candidate_id` как canonical candidate key
- `User.messenger_platform`, `User.max_user_id`
- `ChatMessage` как единая история коммуникации
- `OutboxNotification` + idempotency + retry
- `backend/core/messenger/*` adapters registry
- `reserve_slot` conflict rules
- `SlotAssignment` / `RescheduleRequest` / `ActionToken`
- `CandidateInviteToken` pattern for one-time access
- `analytics_events` as storage foundation
- Test1 partial validation logic

### Must be decoupled from Telegram

- bot state as primary source of journey progress
- status service API keyed by `telegram_id`
- reminder scheduling keyed by `candidate_tg_id`
- CRM outbound chat sender requiring Telegram
- Telegram-only web auth
- message templates and recruiter callbacks assuming Telegram buttons
- funnel event naming centered on `BOT_*`

## Current Candidate Journeys (As-Is)

### Scenario 1. First candidate entry

| Item | As-is |
| --- | --- |
| Entry point | Telegram bot `/start` |
| Steps | Start bot -> init flow state -> ask Test1 questions -> persist answers -> save candidate -> offer slot/manual fallback |
| Data collected | name/FIO, city, screening answers, optionally username |
| Events written | `BOT_ENTERED`, `BOT_START`, `TEST1_STARTED`, `TEST1_COMPLETED`; `ChatMessage`; `TestResult`; status transitions |
| Main drop-off points | Telegram unavailable; candidate never presses `/start`; bot delivery issues; long chat questionnaire; state TTL loss |
| Telegram dependency | Full |

### Scenario 2. Passing test / questionnaire

| Item | As-is |
| --- | --- |
| Entry point | Existing bot conversation |
| Steps | Question-by-question in chat -> per-step validation -> finalization -> report file -> recruiter share |
| Data collected | question answers, derived city/timezone hints, duration, report |
| Events written | `TEST1_STARTED`, `TEST1_COMPLETED`, `QuestionAnswer`, `TestResult` |
| Main drop-off points | Chat fatigue; reply formatting errors; partial answers; lost state; Telegram outages mid-flow |
| Telegram dependency | Full UX dependency, partial validation reusable |

### Scenario 3. Partially completed scenario

| Item | As-is |
| --- | --- |
| Entry point | Candidate exits or stops replying in Telegram |
| Steps | State remains in store until TTL -> candidate can continue if chat resumes before loss |
| Data collected | Partial answers only in state store until completion |
| Events written | Usually none beyond inbound chat history and partial analytics |
| Main drop-off points | State expiration; no universal resume link; candidate cannot continue outside Telegram |
| Telegram dependency | Full |

### Scenario 4. Re-entry / repeat entry

| Item | As-is |
| --- | --- |
| Entry point | Same Telegram account reopens bot |
| Steps | Candidate resolved by Telegram ID -> bot can continue or restart depending on status/state |
| Data collected | Updates username/last activity |
| Events written | Additional chat events, possible repeated funnel events |
| Main drop-off points | Different device/number/channel creates separate identity; no neutral access token |
| Telegram dependency | Full |

### Scenario 5. Incomplete questionnaire

| Item | As-is |
| --- | --- |
| Entry point | Candidate stops during Test1 |
| Steps | State remains ephemeral; no dedicated “resume” landing page |
| Data collected | Partial answers in state store |
| Events written | Minimal |
| Main drop-off points | Candidate forgets; reminders are not journey-aware; no next-action page |
| Telegram dependency | Full |

### Scenario 6. Interview booking

| Item | As-is |
| --- | --- |
| Entry point | After Test1 or via Telegram WebApp booking |
| Steps | Show recruiters -> show slots -> `reserve_slot()` -> recruiter approves -> candidate gets confirmation |
| Data collected | chosen slot, recruiter, city, timezone |
| Events written | slot reservation rows, notification log, outbox, `SLOT_BOOKED`, candidate status update |
| Main drop-off points | no slots; recruiter slow to approve; candidate misses confirmation; Telegram delivery failures |
| Telegram dependency | High, even when booking initiated through WebApp |

### Scenario 7. Cancel / reschedule

| Item | As-is |
| --- | --- |
| Entry point | Candidate buttons, recruiter action, or admin UI |
| Steps | cancel or reschedule request -> free slot / create request -> notify recruiter/candidate |
| Data collected | reason/comment in some flows |
| Events written | slot status changes, outbox entries, analytics for reschedule/cancel |
| Main drop-off points | candidate cannot always self-serve outside Telegram; fragmented flows between legacy slot actions and assignment workflow |
| Telegram dependency | High |

### Scenario 8. Recruiter handoff

| Item | As-is |
| --- | --- |
| Entry point | Candidate detail in CRM or recruiter Telegram notifications |
| Steps | recruiter sees candidate card -> writes in CRM -> bot sends to Telegram -> thread stored in DB |
| Data collected | notes, outbound/inbound chat messages |
| Events written | `ChatMessage`, audit entries, candidate thread read state |
| Main drop-off points | no Telegram ID => no outbound communication; no candidate-facing unified status page |
| Telegram dependency | High |

### Scenario 9. Manual relaunch / manual candidate creation

| Item | As-is |
| --- | --- |
| Entry point | Recruiter/admin manually creates lead |
| Steps | `upsert_candidate()` -> optional invite token -> candidate binds Telegram via `/invite` |
| Data collected | FIO, city, phone, recruiter ownership |
| Events written | lead status, invite token record, audit |
| Main drop-off points | candidate still needs Telegram to self-serve; no web link alternative |
| Telegram dependency | Medium to high |

### Scenario 10. Return to funnel after interruption

| Item | As-is |
| --- | --- |
| Entry point | Recruiter manually changes status or sends message |
| Steps | status reset / manual outreach / re-booking |
| Data collected | manual notes, status change |
| Events written | status transition, audit, possibly chat messages |
| Main drop-off points | no universal resume token; depends on recruiter manual effort |
| Telegram dependency | Usually high |

### Scenario 11. Duplicate candidates from different sources

| Item | As-is |
| --- | --- |
| Entry point | Manual call, bot entry, webapp booking, Max webhook |
| Steps | system tries to resolve by `telegram_id` or `candidate_id`; manual candidates may later bind Telegram |
| Data collected | source, Telegram identifiers, limited phone data |
| Events written | merge/update on Telegram bind; slot conflict protection |
| Main drop-off points | no unified contact identity model; phone/email duplicates can survive as separate `User` records |
| Telegram dependency | Telegram is the strongest dedup key today |

## Where Candidates Are Lost In The Current Telegram Flow

1. До старта screening:
   - кандидат не может/не хочет использовать Telegram;
   - deep link ведет только в бот, альтернативы нет.
2. Внутри Test1:
   - длинный chat flow на мобильном экране;
   - нет “progress saved / continue later” UX;
   - state зависит от канала и TTL.
3. После Test1:
   - если нет слотов, fallback снова в Telegram free-text;
   - нет понятного “мы получили ваши ответы, следующий шаг такой-то”.
4. Между booking и confirmation:
   - уведомление об approved slot и reminders приходят в тот же нестабильный канал;
   - резервный link не создается автоматически.
5. После записи:
   - cancel/reschedule/confirm привязаны к Telegram interaction model;
   - CRM не имеет полноценного web-facing status center для кандидата.

## Specific Architecture Risks Observed In Code

### 1. Single point of failure: Telegram as execution runtime

Telegram сейчас не просто notification channel, а runtime для:

- onboarding;
- screening UX;
- resume logic;
- booking confirmation;
- reminders;
- recruiter-candidate async chat.

### 2. Low fault tolerance of progress state

Progress Test1 хранится в bot state store. Это значит:

- нет durable business-level session;
- partial answers не являются first-class domain entity;
- восстановление зависит от конкретного чата.

### 3. Channel-specific identity model

Основные доменные операции принимают `telegram_id`, а не `candidate_id` или `channel_identity_id`.

Это создаёт технический долг:

- сложнее подключить web/SMS/email;
- сложнее делать dedup;
- сложнее строить универсальные reminders и audit.

### 4. Candidate communication not really omnichannel

Хотя в данных есть `ChatMessage.channel` и `User.messenger_platform`, outbound chat из CRM падает без Telegram ID.

### 5. Existing webapp is not a true fallback

`/api/webapp/*` выглядит как web channel, но это Telegram WebApp:

- аутентификация идет через Telegram `initData`;
- без Telegram этот “web” путь недоступен.

### 6. Max integration is infrastructural, not operational

В коде уже есть Max webhook и adapter bootstrap, но:

- нет полного candidate journey;
- тесты покрывают в основном webhook security/acknowledgement;
- `_handle_message_created()` выглядит несовместимым с текущей сигнатурой `log_inbound_chat_message()`, что указывает на незавершенность интеграции.

### 7. Analytics are funnel-aware, but bot-centric

Есть useful tracking foundation, но naming и semantics все еще bot-first:

- `BOT_ENTERED`
- `BOT_START`
- часть metadata хранит `channel="telegram"` или `source="webapp"`, но не существует единого session/channel attribution layer.

## Risk Register (Current Model)

### Product / UX

- кандидат без Telegram не имеет self-service пути;
- “resume later” UX почти отсутствует;
- нет универсального candidate-facing экрана “мой статус / следующее действие”;
- высокий drop-off на длинном chat-based screening.

### Technical

- status, reminders, outbound chat и часть scheduling logic завязаны на Telegram identifiers;
- bot state не равен durable journey state;
- duplicate resolution слабая вне Telegram;
- несколько scheduling paradigms живут параллельно.

### Operational

- recruiter handoff и подтверждение слота зависят от того же канала, что и intake;
- при деградации Telegram проседает не только acquisition, но и downstream operations;
- fallback switching не автоматизирован.

### Analytics / control

- трудно точно измерять drop-off per channel;
- нет понятной истории channel switches;
- SLA по доставке не считается по fallback chain.

## What Should Stay In Messenger vs Move To Web

### Better in messenger

- легкий first touch из рекламы/отклика;
- короткие триггерные уведомления;
- reminders;
- простой async response “подтверждаю / не смогу / откройте ссылку”.

### Better in web

- длинная анкета и screening;
- тесты с validation и progress save;
- slot picker;
- статус “что дальше”;
- документы;
- единая история шагов и resume from same place.

## Bottom Line

Текущая архитектура уже содержит reusable кирпичи для омниканальности, но candidate runtime всё ещё встроен в Telegram. Поэтому practical migration path такой:

1. не заменять Telegram вторым ботом один-в-один;
2. вынести journey/state/auth/status center в web-first candidate layer;
3. оставить мессенджеры каналами входа и уведомлений;
4. переводить slot/reminder/chat/status APIs на `candidate_id` + channel adapters;
5. только после этого добавлять второй полноценный channel adapter (MAX/VK).

## Assumptions

- Под `Candidate` в документах используется фактическая текущая модель `User`.
- Под `Application / Lead` используется текущая комбинация `User.source` + `User.candidate_status`; отдельной application-таблицы в коде нет.
- Max integration в репозитории трактуется как early-stage scaffold, а не как подтвержденный production fallback, потому что полноценный candidate journey и end-to-end tests отсутствуют.
