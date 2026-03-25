# Screen Inventory

## Purpose
Инвентаризация основных экранов и рабочих поверхностей фронтенда. Фокус - что видит пользователь, откуда берется состояние и где находится граница ответственности.

## Owner
Frontend platform / UI engineering.

## Status
Canonical.

## Last Reviewed
2026-03-25.

## Source Paths
- `frontend/app/src/app/routes/app/*`
- `frontend/app/src/app/routes/candidate/*`
- `frontend/app/src/app/routes/tg-app/*`
- `frontend/app/src/app/components/*`
- `frontend/app/src/theme/*`

## Related Diagrams
- `docs/frontend/route-map.md`
- `docs/frontend/state-flows.md`

## Change Policy
- При изменении экрана обновляйте этот инвентарь вместе с соответствующим route/module.
- Если экран получает новый подэкран, drawer или modal, это должно отражаться здесь и в `state-flows.md`.

## Screen Families

| Screen | Route(s) | Main surface | State sources | Primary user task |
| --- | --- | --- | --- | --- |
| App shell | all `/app/*` except `/app/login` | Desktop header, mobile header, mobile tab bar, more sheet | `useProfile`, unread chat polling, local shell state | Навигация, выбор раздела, доступ по роли. |
| Login | `/app/login` | Auth card/page | Form state, auth redirect params | Войти в систему. |
| Dashboard | `/app/dashboard` | KPI blocks, incoming queue, recruiter leaderboard, calendar/intake widgets | React Query dashboard endpoints, profile role | Быстрый обзор метрик и обработка входящих. |
| Candidates list | `/app/candidates` | Table/board/calendar views, filters, bulk actions | React Query list payload, persisted filters, profile | Найти и сгруппировать кандидатов. |
| Candidate detail | `/app/candidates/$candidateId` | Profile hero, pipeline, actions, channel health card, tests, AI blocks, chat/insights drawers, modals | Candidate detail query, candidate channel health query, AI query, local UI state, query invalidation | Вести конкретного кандидата от карточки до действий и channel recovery. |
| Slots | `/app/slots` | Table/cards/agenda, filters, sheet, booking/reschedule modals | Slots query, persisted filters, profile, city/recruiter options | Управлять слотами и их статусами. |
| Calendar | `/app/calendar` | Calendar-centric schedule view | Calendar queries, profile, local view state | Оценивать загрузку и окна времени. |
| Incoming | `/app/incoming` | Queue/list, filters, scheduling modal, test preview modal | Dashboard incoming query, candidate detail query, recruiter/city options | Обработать новых кандидатов и назначить слот. |
| Messenger | `/app/messenger` | Thread list, conversation pane, template tray, message composer | Threads/messages/templates queries, draft persistence | Вести переписку и использовать шаблоны. |
| Copilot | `/app/copilot` | AI workbench / generated assistance | Copilot queries, local draft state | Получить AI-подсказку и применить её в работе. |
| Profile cabinet | `/app/profile` | Avatar, settings, theme toggle, password form, KPI snippets | Profile query, timezone query, KPI query, local theme state | Управлять профилем и локальными настройками. |
| System | `/app/system` | Health, bot integration, reminder policy, Telegram/MAX delivery health, outbox triage, HH section | System queries, mutations, polling | Проверять состояние платформы, каналов доставки и интеграций. |
| Admin CRUD | `/app/recruiters`, `/app/cities`, `/app/templates`, `/app/questions`, `/app/test-builder*`, `/app/message-templates` | Lists + editors + previews | Entity queries/mutations, profile role, local editor state | Админский CRUD и настройка шаблонов/вопросов. |
| Detailization | `/app/detailization` | Record list, summary, create form, inline edits | Detailization query, cities/recruiters/candidates queries, dirty patch state | Вести учет закрепления/не-закрепления. |
| Simulator | `/app/simulator` | Feature/demo surface | Feature flag, local demo state | Отладка и демонстрации. |

## Candidate Detail Breakdown

| Subsurface | Responsibility | Source path |
| --- | --- | --- |
| `CandidateHeader` | Hero, status, summary, high-level actions | `frontend/app/src/app/routes/app/candidate-detail/CandidateHeader.tsx` |
| `CandidatePipeline` | Workflow visualization and stage summary | `frontend/app/src/app/components/CandidatePipeline/*` |
| `CandidateActions` | Schedule, reject, MAX/Telegram, channel health and MAX invite rotation | `frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx` |
| `CandidateTests` | Test sections and related results | `frontend/app/src/app/routes/app/candidate-detail/CandidateTests.tsx` |
| `CandidateDrawer` | Insights drawer | `frontend/app/src/app/routes/app/candidate-detail/CandidateDrawer.tsx` |
| `CandidateChatDrawer` | Chat drawer and draft insertion target | `frontend/app/src/app/routes/app/candidate-detail/CandidateChatDrawer.tsx` |
| `CandidateModals` | Schedule slot, intro day, reject, report previews | `frontend/app/src/app/routes/app/candidate-detail/CandidateModals.tsx` |
| `InterviewScript` | Persistent interview script panel/sheet | `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx` |
| `RecruitmentScript` | Recruitment script surface and floating FAB | `frontend/app/src/app/components/RecruitmentScript/RecruitmentScript.tsx` |

## Candidate Portal Screens

| Screen | Route(s) | Main surface | State sources | Notes |
| --- | --- | --- | --- | --- |
| Portal start | `/candidate/start`, `/candidate/start/$token` | Loading card | Token resolution, token exchange, journey prefetch | Entry bridge between external link and journey. |
| Portal journey | `/candidate/journey` | Candidate portal work area | Journey query, profile form, screening draft, slot reservation state, message text | Candidate self-service flow. |

## Telegram Mini App Screens

| Screen | Route(s) | Main surface | State sources | Notes |
| --- | --- | --- | --- | --- |
| TG dashboard | `/tg-app` | Native-styled Telegram card layout | Telegram initData, dashboard API | Recruiter dashboard inside Telegram. |
| TG incoming | `/tg-app/incoming` | Incoming list/cards | Telegram initData, queue API | Quick triage inside Telegram. |
| TG candidate | `/tg-app/candidates/$candidateId` | Candidate summary card | Telegram initData, candidate API | Lightweight candidate detail and status actions. |

## Observations
- Desktop/admin screens share a common shell and navigation; mobile screens use the same route modules but with tab bars, sheets and narrower layouts.
- Candidate portal and Telegram Mini App intentionally avoid the admin shell.
- Most screens keep server state in React Query and local UI state in component-level `useState`.
