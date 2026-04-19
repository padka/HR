# Screen Inventory

## Purpose
Инвентаризация основных экранов и рабочих поверхностей фронтенда для текущего mounted runtime.

## Owner
Frontend platform / UI engineering

## Status
Canonical

## Last Reviewed
2026-04-19

## Source Paths
- `frontend/app/src/app/routes/app/*`
- `frontend/app/src/app/routes/miniapp/*`
- `frontend/app/src/app/routes/tg-app/*`
- `frontend/app/src/app/components/*`
- `frontend/app/src/theme/*`

## Related Docs
- `docs/frontend/route-map.md`
- `docs/frontend/state-flows.md`

## Active Screen Families

| Screen | Route(s) | Main surface | State sources | Primary user task |
| --- | --- | --- | --- | --- |
| App shell | all `/app/*` except `/app/login` | Desktop header, mobile header, mobile tab bar, more sheet | `useProfile`, unread chat polling, local shell state | Навигация, выбор раздела, доступ по роли |
| Login | `/app/login` | Auth card/page | Form state, auth redirect params | Войти в систему |
| Dashboard | `/app/dashboard` | KPI blocks, incoming queue, recruiter leaderboard, calendar/intake widgets | React Query dashboard endpoints, profile role | Быстрый обзор метрик и обработка входящих |
| Candidates list | `/app/candidates` | Table/board/calendar views, filters, bulk actions | React Query list payload, persisted filters, profile | Найти и сгруппировать кандидатов |
| Candidate detail | `/app/candidates/$candidateId` | Profile hero, pipeline, actions, channel health card, tests, AI blocks, chat/insights drawers, modals | Candidate detail query, channel health query, AI query, local UI state, query invalidation | Вести конкретного кандидата от карточки до действий и channel recovery |
| Slots | `/app/slots` | Table/cards/agenda, filters, booking/reschedule modals | Slots query, persisted filters, profile, city/recruiter options | Управлять слотами и их статусами |
| Calendar | `/app/calendar` | Calendar-centric schedule view | Calendar queries, profile, local view state | Оценивать загрузку и окна времени |
| Incoming | `/app/incoming` | Queue/list, filters, scheduling modal, test preview modal | Dashboard incoming query, candidate detail query, recruiter/city options | Обработать новых кандидатов и назначить слот |
| Messenger | `/app/messenger` | Thread list, conversation pane, template tray, message composer | Threads/messages/templates queries, draft persistence | Вести переписку и использовать шаблоны |
| Copilot | `/app/copilot` | AI workbench / generated assistance | Copilot queries, local draft state | Получить AI-подсказку и применить её в работе |
| Profile cabinet | `/app/profile` | Avatar, settings, theme toggle, password form, KPI snippets | Profile query, timezone query, KPI query, local theme state | Управлять профилем и локальными настройками |
| System | `/app/system` | Health, bot integration, delivery health, outbox triage, HH section | System queries, mutations, polling | Проверять состояние платформы, доставку и интеграции |
| Admin CRUD | `/app/recruiters`, `/app/cities`, `/app/templates`, `/app/questions`, `/app/test-builder*`, `/app/message-templates` | Lists + editors + previews | Entity queries/mutations, profile role, local editor state | Админский CRUD и настройка шаблонов/вопросов |
| Detailization | `/app/detailization` | Record list, summary, create form, inline edits | Detailization query, cities/recruiters/candidates queries, dirty patch state | Вести учет закрепления/не-закрепления |
| Simulator | `/app/simulator` | Feature/demo surface | Feature flag, local demo state | Отладка и демонстрации |
| MAX mini-app | `/miniapp` | Candidate-first bounded pilot shell, next-step/status, Test1, booking, prep/help cards | MAX signed `initData`, bounded launch bootstrap, shared candidate-access server state, MAX bridge runtime helpers, local panel state | Провести кандидата по bounded MAX pilot без форка бизнес-логики |

## Candidate Detail Breakdown

| Subsurface | Responsibility | Source path |
| --- | --- | --- |
| `CandidateHeader` | Hero, status, summary, high-level actions | `frontend/app/src/app/routes/app/candidate-detail/CandidateHeader.tsx` |
| `CandidatePipeline` | Workflow visualization and stage summary | `frontend/app/src/app/components/CandidatePipeline/*` |
| `CandidateActions` | Supported actions, channel health and operator recovery affordances | `frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx` |
| `CandidateTests` | Test sections and related results | `frontend/app/src/app/routes/app/candidate-detail/CandidateTests.tsx` |
| `CandidateDrawer` | Insights drawer | `frontend/app/src/app/routes/app/candidate-detail/CandidateDrawer.tsx` |
| `CandidateChatDrawer` | Chat drawer and draft insertion target | `frontend/app/src/app/routes/app/candidate-detail/CandidateChatDrawer.tsx` |
| `CandidateModals` | Schedule slot, intro day, reject, report previews | `frontend/app/src/app/routes/app/candidate-detail/CandidateModals.tsx` |

## Telegram Mini App Screens

| Screen | Route(s) | Main surface | State sources | Notes |
| --- | --- | --- | --- | --- |
| TG dashboard | `/tg-app` | Native-styled Telegram card layout | Telegram initData, dashboard API | Recruiter dashboard inside Telegram |
| TG incoming | `/tg-app/incoming` | Incoming list/cards | Telegram initData, queue API | Quick triage inside Telegram |
| TG candidate | `/tg-app/candidates/$candidateId` | Candidate summary card | Telegram initData, candidate API | Lightweight candidate detail and status actions |

## MAX Mini App Screens

| Screen/state | Route | Main surface | State sources | Notes |
| --- | --- | --- | --- | --- |
| Bootstrap / intake gate | `/miniapp` | Launch loading, immediate Test1 entry for new drafts, manual-review / legacy recovery cards | `/api/max/launch`, MAX bridge runtime helpers, local panel state | Mounted for bounded controlled pilot only; global entry is intake-first, while contact restore remains legacy recovery |
| Home / status | `/miniapp` | Hero, timeline, next-step card, booking summary, prep/help/company cards | `/api/candidate-access/journey` | Shared candidate journey remains canonical |
| Test1 | `/miniapp` | One-question flow, progress, save/next controls | `/api/candidate-access/test1*`, local question state, closing confirmation runtime state | No MAX-only Test1 business logic |
| Booking selection | `/miniapp` | City, recruiter, slot panels plus empty states | `/api/candidate-access/cities`, `/recruiters`, `/slots`, `/booking-context` | Shared booking semantics only |
| Manual availability | `/miniapp` | Free-text desired dates/time form plus waiting-slot success state | `/api/candidate-access/manual-availability`, `/journey` | Activates hidden draft and keeps no-slot flow server-backed |
| Booking success / booked return | `/miniapp` | Confirmed booking card, next step, prep, secondary chat CTA | `/api/candidate-access/bookings`, `/journey` | Return visits stay server-backed |
| Chat-ready / help | `/miniapp` | Handoff success card, help/company info | `/api/candidate-access/chat-handoff`, `/journey`, MAX bridge `openMaxLink()` | Chat remains bounded fallback, not the primary runtime promise |

## Unsupported And Target-State Notes
- Legacy candidate portal implementation is unsupported and is not part of the active screen inventory.
- Future standalone candidate web flow remains a target-state surface, but it has no mounted screen contract in the current runtime.
- Historical MAX runtime is unsupported and is not part of the active screen inventory.
- Full MAX runtime/channel rollout beyond the bounded pilot remains a target-state surface, but it has no production mounted screen contract in the current runtime.
