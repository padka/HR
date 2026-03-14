# PROJECT AUDIT 02 — Components and Code
## Дата: 2026-03-14

Ниже — покомпонентный аудит исходного кода. Для однородных файлов используются сокращённые карточки, но каждый файл перечислен отдельно.

## 3.1 Frontend страницы

### `frontend/app/src/app/routes/__root.tsx`

**Тип:** Страница
**Строк кода:** ~1368
**Назначение:** SPA-страница `__root`.

**Экспорты:**
- `RootLayout` — строка ~533

**Ключевые функции:**
- `resolveLiquidGlassV2Enabled()` — строка ~57
- `resolveMotionMode()` — строка ~65
- `createBubblePopFx()` — строка ~80
- `RootLayout()` — строка ~533
- `clamp()` — строка ~41
- `clamp01()` — строка ~42
- `lerp()` — строка ~43
- `smoothstep01()` — строка ~44
- `easeOutCubic()` — строка ~49
- `easeOutQuint()` — строка ~50
- `randRange()` — строка ~52
- `randInt()` — строка ~53
- `sampleNoiseLoop()` — строка ~70
- `normalizePathname()` — строка ~514
- `isPathActive()` — строка ~516
- `isDetailRoute()` — строка ~522
- `getMobileTitle()` — строка ~528

**Внутреннее состояние:**
- `liquidGlassV2Enabled`
- `motionMode`
- `chatToast`
- `chatUnreadCount`
- `isMoreSheetOpen`
- `mobileTransition`

**Используемые хуки:**
- `useEffect()`
- `useIsMobile()`
- `useProfile()`
- `useRef()`
- `useRouterState()`
- `useState()`

**API / сетевые вызовы:**
- `createBubblePopFx()`
- `createElement()`
- `createGain()`
- `createOscillator()`
- `createRadialGradient()`
- `refreshLayers()`
- `scheduleTone()`

**Дочерние компоненты:**
- `<AudioContext />`
- `<HTMLButtonElement />`
- `<HTMLElement />`
- `<HTMLSpanElement />`
- `<Link />`
- `<MotionMode />`
- `<Outlet />`
- `<Record />`
- `<ThreadsPayload />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/hooks/useProfile.ts`

**Используется в:**
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/__root.ui-mode.test.tsx`

**Состояние / проблемы:**
- `any`: 1

### `frontend/app/src/app/routes/__root.ui-mode.test.tsx`

**Тип:** Страница
**Строк кода:** ~264
**Назначение:** SPA-страница `__root.ui-mode.test`.

**Используемые хуки:**
- `useIsMobileMock()`
- `useProfileMock()`
- `useRouterStateMock()`

**Дочерние компоненты:**
- `<RootLayout />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/routes/__root.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/calendar.tsx`

**Тип:** Страница
**Строк кода:** ~963
**Назначение:** SPA-страница `calendar`.

**Экспорты:**
- `CalendarPage` — строка ~76

**Ключевые функции:**
- `toLocalInputValue()` — строка ~46
- `isoToLocalInput()` — строка ~51
- `localInputToIso()` — строка ~58
- `buildTaskDraft()` — строка ~65
- `CalendarPage()` — строка ~76

**Внутреннее состояние:**
- `selectedCity`
- `selectedRecruiter`
- `selectedStatuses`
- `mobileViewMode`
- `selectedSlot`
- `taskModal`
- `taskDraft`
- `taskError`

**Используемые хуки:**
- `useCalendarWebSocket()`
- `useCallback()`
- `useEffect()`
- `useIsMobile()`
- `useMutation()`
- `useProfile()`
- `useQueryClient()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<City />`
- `<RecruiterOption />`
- `<ScheduleCalendar />`
- `<SlotExtendedProps />`
- `<TaskDraft />`
- `<TaskModalState />`
- `<TaskPayload />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/hooks/useCalendarWebSocket.ts`
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/hooks/useProfile.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/candidate-detail.tsx`

**Тип:** Страница
**Строк кода:** ~3458
**Назначение:** SPA-страница `candidate-detail`.

**Экспорты:**
- `CandidateDetailPage` — строка ~1593

**Ключевые функции:**
- `getStatusDisplay()` — строка ~369
- `resolveFunnelStageKey()` — строка ~374
- `funnelStageStateLabel()` — строка ~380
- `funnelToneForState()` — строка ~388
- `formatSlotTime()` — строка ~396
- `formatDateTime()` — строка ~413
- `buildCandidateTimeline()` — строка ~426
- `fitLevelLabel()` — строка ~526
- `fitLevelFromScore()` — строка ~533
- `scorecardRecommendationLabel()` — строка ~540
- `scorecardRecommendationShortLabel()` — строка ~547
- `scorecardMetricStatusLabel()` — строка ~554
- `formatRescheduleRequest()` — строка ~560
- `finalOutcomeLabel()` — строка ~599
- `normalizeJourneyCopy()` — строка ~606
- `journeyStageLabel()` — строка ~615
- `journeyActorLabel()` — строка ~626
- `journeyEventTitle()` — строка ~636
- `journeyEventMeta()` — строка ~661
- `getHhSyncBadge()` — строка ~681
- `formatSecondsToMinutes()` — строка ~692
- `normalizeTelegramUsername()` — строка ~697
- `normalizeConferenceUrl()` — строка ~703
- `formatTzOffset()` — строка ~852
- `getTomorrowDate()` — строка ~866

**Внутреннее состояние:**
- `status`
- `contentType`
- `text`
- `blobUrl`
- `error`
- `form`
- `resolvedCityId`
- `error`
- `form`
- `error`
- `template`
- `reason`
- `error`
- `mobileTab`
- `chatText`
- `actionMessage`
- `showScheduleSlotModal`
- `showScheduleIntroDayModal`
- `showRejectModal`
- `reportPreview`

**Используемые хуки:**
- `useEffect()`
- `useIsMobile()`
- `useMemo()`
- `useMutation()`
- `useParams()`
- `useQueryClient()`
- `useState()`

**API / сетевые вызовы:**
- `createObjectURL()`
- `createPortal()`
- `fetchCandidateAiCoach()`
- `fetchCandidateAiSummary()`
- `fetchCandidateChat()`
- `fetchCandidateChatDrafts()`
- `fetchCandidateCoachDrafts()`
- `fetchCandidateCohortComparison()`
- `fetchCandidateDetail()`
- `fetchCandidateHHSummary()`
- `markChatRead()`
- `refreshCandidateAiCoach()`
- `refreshCandidateAiSummary()`
- `scheduleCandidateInterview()`
- `scheduleCandidateIntroDay()`
- `sendCandidateChatMessage()`
- `waitForCandidateChat()`

**Дочерние компоненты:**
- `<AICoachResponse />`
- `<AIDraftItem />`
- `<AISummaryResponse />`
- `<ApiErrorBanner />`
- `<CandidateCohortComparison />`
- `<CandidateDetail />`
- `<CandidateDrawerTimelineEvent />`
- `<CandidateHHSummary />`
- `<CandidateJourney />`
- `<CandidatePipeline />`
- `<CandidatePipelineStageData />`
- `<CandidateTimeline />`
- `<ChatPayload />`
- `<City />`
- `<CohortComparison />`
- `<FunnelStageItem />`
- `<FunnelStageKey />`
- `<HTMLDivElement />`
- `<HTMLTextAreaElement />`
- `<InterviewScript />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`
- `frontend/app/src/app/components/CandidateTimeline/CandidateTimeline.tsx`
- `frontend/app/src/app/components/CohortComparison/CohortComparison.tsx`
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`
- `frontend/app/src/app/components/QuickNotes/QuickNotes.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/lib/timezonePreview.ts`

**Используется в:**
- `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx`

**Комментарии / явные подсказки в файле:**
- ── Header Card ──
- Contacts row
- ── Tests ──
- Modals

**Состояние / проблемы:**
- `any`: 1
- console/print: 1

### `frontend/app/src/app/routes/app/candidate-new.test.tsx`

**Тип:** Страница
**Строк кода:** ~143
**Назначение:** SPA-страница `candidate-new.test`.

**Используемые хуки:**
- `useMutationMock()`
- `useQueryMock()`

**Дочерние компоненты:**
- `<CandidateNewPage />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/routes/app/candidate-new.tsx`

**Состояние / проблемы:**
- `any`: 2

### `frontend/app/src/app/routes/app/candidate-new.tsx`

**Тип:** Страница
**Строк кода:** ~520
**Назначение:** SPA-страница `candidate-new`.

**Экспорты:**
- `CandidateNewPage` — строка ~80

**Ключевые функции:**
- `formatTzOffset()` — строка ~40
- `getTomorrowDate()` — строка ~54
- `getNextWeekDate()` — строка ~60
- `getTodayDate()` — строка ~66
- `extractError()` — строка ~70
- `CandidateNewPage()` — строка ~80

**Внутреннее состояние:**
- `form`
- `error`
- `notice`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<CandidateCreateResponse />`
- `<City />`
- `<Link />`
- `<Recruiter />`
- `<RoleGuard />`
- `<ScheduleSlotResponse />`
- `<SubmitResult />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-new.test.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/candidates.test.tsx`

**Тип:** Страница
**Строк кода:** ~230
**Назначение:** SPA-страница `candidates.test`.

**Используемые хуки:**
- `useMutationMock()`
- `useQueryMock()`

**Дочерние компоненты:**
- `<CandidatesPage />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/routes/app/candidates.tsx`

**Состояние / проблемы:**
- `any`: 3

### `frontend/app/src/app/routes/app/candidates.tsx`

**Тип:** Страница
**Строк кода:** ~832
**Назначение:** SPA-страница `candidates`.

**Экспорты:**
- `CandidatesPage` — строка ~191

**Ключевые функции:**
- `CandidatesPage()` — строка ~191

**Внутреннее состояние:**
- `search`
- `status`
- `page`
- `perPage`
- `pipeline`
- `view`
- `aiCityId`
- `deletingCandidateId`
- `deleteCandidateError`
- `kanbanMoveError`
- `kanbanStatusOverrides`
- `draggingCardId`
- `dragOverColumn`
- `movingCandidateId`
- `calendarFrom`
- `calendarTo`

**Используемые хуки:**
- `useEffect()`
- `useIsMobile()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useQueryClient()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`
- `deleteCandidate()`

**Дочерние компоненты:**
- `<AICityRecommendationsResponse />`
- `<ApiErrorBanner />`
- `<CandidateKanbanMoveResponse />`
- `<CandidateListPayload />`
- `<CityOption />`
- `<Error />`
- `<HTMLDivElement />`
- `<Link />`
- `<Record />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/hooks/useProfile.ts`

**Используется в:**
- `frontend/app/src/app/routes/app/candidates.test.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/cities.tsx`

**Тип:** Страница
**Строк кода:** ~211
**Назначение:** SPA-страница `cities`.

**Экспорты:**
- `CitiesPage` — строка ~40

**Ключевые функции:**
- `CitiesPage()` — строка ~40

**Внутреннее состояние:**
- `edits`
- `rowError`

**Используемые хуки:**
- `useMutation()`
- `useQueryClient()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<City />`
- `<Link />`
- `<Record />`
- `<RoleGuard />`
- `<TemplatesPayload />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/city-edit.tsx`

**Тип:** Страница
**Строк кода:** ~1158
**Назначение:** SPA-страница `city-edit`.

**Экспорты:**
- `CityEditPage` — строка ~270

**Ключевые функции:**
- `isValidTimezone()` — строка ~74
- `formatTimeInTz()` — строка ~83
- `ReminderPolicySection()` — строка ~110
- `CityEditPage()` — строка ~270

**Внутреннее состояние:**
- `useCustom`
- `form`
- `form`
- `expertsItems`
- `recruiterSearch`
- `collapsedStages`
- `formError`
- `fieldError`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useParams()`
- `useQuery()`
- `useQueryClient()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<CityDetail />`
- `<CityExpertItem />`
- `<CityHhVacanciesResponse />`
- `<Link />`
- `<Omit />`
- `<Record />`
- `<Recruiter />`
- `<ReminderPolicy />`
- `<ReminderPolicySection />`
- `<RoleGuard />`
- `<TemplateStage />`
- `<TimezoneOption />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/template_meta.ts`

**Комментарии / явные подсказки в файле:**
- Summary hero card
- Quick nav
- City message templates
- Basic parameters
- Plan section
- Additional info
- Intro day section
- Recruiters section
- Selected recruiters preview pills

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/city-new.tsx`

**Тип:** Страница
**Строк кода:** ~449
**Назначение:** SPA-страница `city-new`.

**Экспорты:**
- `CityNewPage` — строка ~57

**Ключевые функции:**
- `isValidTimezone()` — строка ~33
- `formatTimeInTz()` — строка ~42
- `CityNewPage()` — строка ~57

**Внутреннее состояние:**
- `form`
- `expertsItems`
- `tzTouched`
- `recruiterSearch`
- `formError`
- `fieldError`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<CityExpertItem />`
- `<Link />`
- `<Recruiter />`
- `<RoleGuard />`
- `<TimezoneOption />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Комментарии / явные подсказки в файле:**
- Basic parameters
- Plan section
- Additional info
- Recruiters section

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/copilot.tsx`

**Тип:** Страница
**Строк кода:** ~433
**Назначение:** SPA-страница `copilot`.

**Экспорты:**
- `CopilotPage` — строка ~69

**Ключевые функции:**
- `ModalPortal()` — строка ~55
- `formatTime()` — строка ~60
- `CopilotPage()` — строка ~69

**Внутреннее состояние:**
- `toast`
- `chatText`
- `kbTitle`
- `kbText`
- `kbFile`
- `activeDocId`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`
- `createPortal()`

**Дочерние компоненты:**
- `<ChatState />`
- `<File />`
- `<HTMLDivElement />`
- `<KBDocGet />`
- `<KBDocsList />`
- `<KBReindexResponse />`
- `<ModalPortal />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useProfile.ts`

**Состояние / проблемы:**
- `any`: 9

### `frontend/app/src/app/routes/app/dashboard.tsx`

**Тип:** Страница
**Строк кода:** ~1063
**Назначение:** SPA-страница `dashboard`.

**Экспорты:**
- `DashboardPage` — строка ~77

**Ключевые функции:**
- `formatAiRelevance()` — строка ~40
- `formatAiRecommendation()` — строка ~51
- `toIsoDate()` — строка ~58
- `getDefaultRange()` — строка ~62
- `ModalPortal()` — строка ~72
- `DashboardPage()` — строка ~77
- `Metric()` — строка ~1055

**Внутреннее состояние:**
- `rangeFrom`
- `rangeTo`
- `recruiterId`
- `toast`
- `incomingTarget`
- `incomingDate`
- `incomingTime`
- `incomingMessage`
- `incomingSearch`
- `incomingCityFilter`
- `incomingFilter`
- `incomingSort`
- `incomingPage`
- `incomingPageSize`
- `showIncomingAdvancedFilters`
- `expandedIncomingCards`

**Используемые хуки:**
- `useEffect()`
- `useIsMobile()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useState()`

**API / сетевые вызовы:**
- `createPortal()`
- `fetchCurrentKpis()`
- `fetchDashboardIncoming()`
- `fetchRecruiterPerformance()`
- `scheduleDashboardIncomingSlot()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<IncomingCandidate />`
- `<IncomingFilter />`
- `<IncomingPage />`
- `<IncomingPayload />`
- `<KPIResponse />`
- `<LeaderboardPayload />`
- `<Link />`
- `<Metric />`
- `<ModalPortal />`
- `<Record />`
- `<RecruiterOption />`
- `<SummaryPayload />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/lib/timezonePreview.ts`
- `frontend/app/src/app/routes/app/incoming-demo.ts`
- `frontend/app/src/app/routes/app/incoming.tsx`

**Используется в:**
- `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx`

**Состояние / проблемы:**
- `any`: 2

### `frontend/app/src/app/routes/app/detailization.tsx`

**Тип:** Страница
**Строк кода:** ~588
**Назначение:** SPA-страница `detailization`.

**Экспорты:**
- `DetailizationPage` — строка ~107

**Ключевые функции:**
- `fmtDateTime()` — строка ~72
- `isoDate()` — строка ~85
- `outcomeLabel()` — строка ~89
- `outcomeTone()` — строка ~96
- `summaryValue()` — строка ~103
- `DetailizationPage()` — строка ~107

**Внутреннее состояние:**
- `dateFrom`
- `dateTo`
- `showCreate`
- `candidateQuery`
- `selectedCandidate`
- `createRecruiterId`
- `createCityId`
- `createAssignedAt`
- `createConductedAt`
- `createExpertName`
- `createFinalOutcome`
- `createFinalOutcomeReason`
- `createError`
- `dirty`

**Используемые хуки:**
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useQuery()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<CandidateSearchItem />`
- `<CandidateSearchResponse />`
- `<City />`
- `<DetailizationItem />`
- `<DetailizationResponse />`
- `<Link />`
- `<Pick />`
- `<Record />`
- `<Recruiter />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/hooks/useProfile.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/incoming-demo.test.ts`

**Тип:** Страница
**Строк кода:** ~49
**Назначение:** SPA-страница `incoming-demo.test`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/incoming-demo.ts`

**Тип:** Страница
**Строк кода:** ~209
**Назначение:** SPA-страница `incoming-demo`.

**Экспорты:**
- `resolveIncomingDemoCount` — строка ~121
- `withDemoIncomingCandidates` — строка ~144
- `IncomingCandidateLike` — строка ~1
- `IncomingCityOption` — строка ~25

**Ключевые функции:**
- `parsePositiveInt()` — строка ~101
- `normalizeHost()` — строка ~106
- `buildName()` — строка ~110
- `selectCity()` — строка ~116
- `resolveIncomingDemoCount()` — строка ~121

**Используется в:**
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/incoming.filters.test.ts`

**Тип:** Страница
**Строк кода:** ~87
**Назначение:** SPA-страница `incoming.filters.test`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/incoming.filters.ts`

**Тип:** Страница
**Строк кода:** ~94
**Назначение:** SPA-страница `incoming.filters`.

**Экспорты:**
- `parseIncomingPersistedFilters` — строка ~51
- `loadIncomingPersistedFilters` — строка ~70
- `saveIncomingPersistedFilters` — строка ~78
- `clearIncomingPersistedFilters` — строка ~87
- `INCOMING_FILTERS_STORAGE_KEY` — строка ~22
- `IncomingStatusFilter` — строка ~1
- `IncomingOwnerFilter` — строка ~8
- `IncomingWaitingFilter` — строка ~9
- `IncomingAiFilter` — строка ~10
- `IncomingPersistedFilters` — строка ~12

**Ключевые функции:**
- `isObject()` — строка ~35
- `pickString()` — строка ~43
- `pickBoolean()` — строка ~47
- `parseIncomingPersistedFilters()` — строка ~51
- `loadIncomingPersistedFilters()` — строка ~70
- `saveIncomingPersistedFilters()` — строка ~78
- `clearIncomingPersistedFilters()` — строка ~87

**Дочерние компоненты:**
- `<IncomingPersistedFilters />`
- `<Storage />`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/incoming.tsx`

**Тип:** Страница
**Строк кода:** ~1135
**Назначение:** SPA-страница `incoming`.

**Экспорты:**
- `IncomingPage` — строка ~357

**Ключевые функции:**
- `ModalPortal()` — строка ~81
- `toIsoDate()` — строка ~86
- `formatSlotOption()` — строка ~90
- `formatInTz()` — строка ~104
- `formatDateTime()` — строка ~115
- `formatAiRecommendation()` — строка ~126
- `resolveAiScoreTone()` — строка ~133
- `formatRequestedAnotherTime()` — строка ~144
- `formatDuration()` — строка ~173
- `resolveTestTone()` — строка ~183
- `TestScoreBar()` — строка ~198
- `resolveTest1Section()` — строка ~214
- `IncomingTestPreviewModal()` — строка ~233
- `IncomingPage()` — строка ~357

**Внутреннее состояние:**
- `toast`
- `incomingTarget`
- `testPreviewTarget`
- `incomingDate`
- `incomingTime`
- `incomingMessage`
- `incomingMode`
- `selectedSlotId`
- `search`
- `cityFilter`
- `statusFilter`
- `ownerFilter`
- `waitingFilter`
- `aiFilter`
- `showAdvancedFilters`
- `expandedCards`
- `assignTargets`

**Используемые хуки:**
- `useEffect()`
- `useIsMobile()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`
- `createPortal()`
- `fetchCandidateDetail()`

**Дочерние компоненты:**
- `<AvailableSlotsPayload />`
- `<CandidateDetail />`
- `<IncomingAiFilter />`
- `<IncomingCandidate />`
- `<IncomingOwnerFilter />`
- `<IncomingPayload />`
- `<IncomingStatusFilter />`
- `<IncomingTestPreviewModal />`
- `<IncomingWaitingFilter />`
- `<Link />`
- `<ModalPortal />`
- `<Record />`
- `<RoleGuard />`
- `<TestScoreBar />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/api/services/candidates.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/lib/timezonePreview.ts`
- `frontend/app/src/app/routes/app/incoming-demo.ts`

**Используется в:**
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx`

**Состояние / проблемы:**
- `any`: 4

### `frontend/app/src/app/routes/app/index.tsx`

**Тип:** Страница
**Строк кода:** ~12
**Назначение:** SPA-страница `index`.

**Экспорты:**
- `IndexPage` — строка ~1

**Ключевые функции:**
- `IndexPage()` — строка ~1

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/login.tsx`

**Тип:** Страница
**Строк кода:** ~80
**Назначение:** SPA-страница `login`.

**Экспорты:**
- `LoginPage` — строка ~3

**Ключевые функции:**
- `LoginPage()` — строка ~3

**Внутреннее состояние:**
- `form`
- `error`
- `loading`

**Используемые хуки:**
- `useState()`

**Используется в:**
- `frontend/app/src/app/main.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/message-templates.tsx`

**Тип:** Страница
**Строк кода:** ~625
**Назначение:** SPA-страница `message-templates`.

**Экспорты:**
- `MessageTemplatesPage` — строка ~111

**Ключевые функции:**
- `extractApiError()` — строка ~89
- `stageLabelFor()` — строка ~102
- `MessageTemplatesPage()` — строка ~111

**Внутреннее состояние:**
- `filters`
- `editor`
- `formError`
- `previewError`
- `previewHtml`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<EditorState />`
- `<Link />`
- `<MessageTemplatesPayload />`
- `<PreviewResponse />`
- `<Record />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useProfile.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/messenger.tsx`

**Тип:** Страница
**Строк кода:** ~1612
**Назначение:** SPA-страница `messenger`.

**Экспорты:**
- `MessengerPage` — строка ~955

**Ключевые функции:**
- `ModalPortal()` — строка ~63
- `priorityTone()` — строка ~68
- `priorityLabel()` — строка ~87
- `formatThreadTime()` — строка ~108
- `formatFullDateTime()` — строка ~119
- `formatDayLabel()` — строка ~132
- `previewText()` — строка ~143
- `compactThreadStatusLabel()` — строка ~147
- `messageAuthorLabel()` — строка ~162
- `readThreadCache()` — строка ~169
- `scoreTone()` — строка ~182
- `normalizeTextLinks()` — строка ~195
- `renderMessageText()` — строка ~201
- `formatRescheduleRequest()` — строка ~227
- `upcomingSlot()` — строка ~263
- `scorecardRecommendationLabel()` — строка ~275
- `slotConfirmationLabel()` — строка ~284
- `testSection()` — строка ~293
- `findPurposeSlot()` — строка ~297
- `findUpcomingPurposeSlot()` — строка ~305
- `pipelineState()` — строка ~313
- `isFieldFormatQuestion()` — строка ~320
- `fieldFormatAnswer()` — строка ~334
- `buildNextAction()` — строка ~340
- `buildJourneySteps()` — строка ~478

**Внутреннее состояние:**
- `expandedStageKey`
- `activeCandidateId`
- `isDetailsOpen`
- `isIntroDayModalOpen`
- `showTemplateTray`
- `selectedTemplateKey`
- `sendError`
- `toast`
- `form`
- `template`
- `error`

**Используемые хуки:**
- `useEffect()`
- `useIsMobile()`
- `useMemo()`
- `useMessageDraft()`
- `useMutation()`
- `useQueryClient()`
- `useRef()`
- `useState()`

**API / сетевые вызовы:**
- `createPortal()`
- `fetchCandidateAiSummary()`
- `fetchCandidateChatMessages()`
- `fetchCandidateChatThreads()`
- `fetchCandidateChatWorkspace()`
- `fetchCandidateDetail()`
- `scheduleCandidateIntroDay()`
- `sendCandidateThreadMessage()`
- `waitForCandidateChatMessages()`
- `waitForCandidateChatThreads()`

**Дочерние компоненты:**
- `<AISummaryResponse />`
- `<CandidateChatPayload />`
- `<CandidateChatThreadsPayload />`
- `<CandidateChatWorkspaceState />`
- `<CandidateDetail />`
- `<CityOption />`
- `<DetailsDrawer />`
- `<HTMLDivElement />`
- `<InboxThreadCard />`
- `<ModalPortal />`
- `<ScheduleIntroDayModal />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/lib/timezonePreview.ts`
- `frontend/app/src/app/routes/app/messenger/useMessageDraft.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/messenger/useMessageDraft.ts`

**Тип:** Страница
**Строк кода:** ~24
**Назначение:** SPA-страница `useMessageDraft`.

**Экспорты:**
- `useMessageDraft` — строка ~10

**Ключевые функции:**
- `readDraft()` — строка ~5
- `useMessageDraft()` — строка ~10

**Внутреннее состояние:**
- `draft`

**Используемые хуки:**
- `useEffect()`
- `useMessageDraft()`
- `useState()`

**Используется в:**
- `frontend/app/src/app/routes/app/messenger.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/profile.tsx`

**Тип:** Страница
**Строк кода:** ~676
**Назначение:** SPA-страница `profile`.

**Экспорты:**
- `ProfilePage` — строка ~82

**Ключевые функции:**
- `CameraIcon()` — строка ~18
- `TrashIcon()` — строка ~27
- `formatMinutes()` — строка ~39
- `formatHours()` — строка ~47
- `trendClass()` — строка ~52
- `mergeProfileRecruiter()` — строка ~58
- `formatDateShort()` — строка ~76
- `ProfilePage()` — строка ~82
- `HealthItem()` — строка ~666

**Внутреннее состояние:**
- `theme`
- `settings`
- `passwordForm`
- `passwordError`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useQuery()`
- `useQueryClient()`
- `useState()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<CameraIcon />`
- `<HealthItem />`
- `<KpiDetailRow />`
- `<Link />`
- `<ProfileResponse />`
- `<ProfileSettingsPayload />`
- `<TrashIcon />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/hooks/useProfile.ts`

**Используется в:**
- `frontend/app/src/app/main.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/question-edit.tsx`

**Тип:** Страница
**Строк кода:** ~146
**Назначение:** SPA-страница `question-edit`.

**Экспорты:**
- `QuestionEditPage` — строка ~18

**Ключевые функции:**
- `QuestionEditPage()` — строка ~18

**Внутреннее состояние:**
- `form`
- `formError`
- `payloadValid`

**Используемые хуки:**
- `useEffect()`
- `useMutation()`
- `useNavigate()`
- `useParams()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<Link />`
- `<QuestionDetail />`
- `<QuestionPayloadEditor />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/question-new.tsx`

**Тип:** Страница
**Строк кода:** ~125
**Назначение:** SPA-страница `question-new`.

**Экспорты:**
- `QuestionNewPage` — строка ~13

**Ключевые функции:**
- `QuestionNewPage()` — строка ~13

**Внутреннее состояние:**
- `form`
- `formError`
- `payloadValid`

**Используемые хуки:**
- `useMutation()`
- `useNavigate()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<Link />`
- `<QuestionPayloadEditor />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/questions.tsx`

**Тип:** Страница
**Строк кода:** ~127
**Назначение:** SPA-страница `questions`.

**Экспорты:**
- `QuestionsPage` — строка ~7

**Ключевые функции:**
- `QuestionsPage()` — строка ~7

**Используемые хуки:**
- `useIsMobile()`
- `useMutation()`
- `useNavigate()`
- `useQuery()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<Link />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useIsMobile.ts`

**Состояние / проблемы:**
- `any`: 5

### `frontend/app/src/app/routes/app/recruiter-edit.tsx`

**Тип:** Страница
**Строк кода:** ~568
**Назначение:** SPA-страница `recruiter-edit`.

**Экспорты:**
- `RecruiterEditPage` — строка ~42

**Ключевые функции:**
- `RecruiterEditPage()` — строка ~42

**Внутреннее состояние:**
- `form`
- `citySearch`
- `formError`
- `fieldError`
- `resetCredentials`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useParams()`
- `useRef()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<City />`
- `<Link />`
- `<RecruiterDetail />`
- `<RecruiterSummary />`
- `<ResetPasswordResponse />`
- `<RoleGuard />`
- `<TimezoneOption />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/recruiter-form.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/recruiter-form.ts`

**Тип:** Страница
**Строк кода:** ~47
**Назначение:** SPA-страница `recruiter-form`.

**Экспорты:**
- `validateRecruiterForm` — строка ~17
- `getTzPreview` — строка ~34
- `RecruiterFormState` — строка ~1
- `RecruiterFormErrors` — строка ~10

**Ключевые функции:**
- `validateRecruiterForm()` — строка ~17
- `getTzPreview()` — строка ~34

**Используется в:**
- `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- `frontend/app/src/app/routes/app/recruiter-new.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/recruiter-new.tsx`

**Тип:** Страница
**Строк кода:** ~457
**Назначение:** SPA-страница `recruiter-new`.

**Экспорты:**
- `RecruiterNewPage` — строка ~19

**Ключевые функции:**
- `RecruiterNewPage()` — строка ~19

**Внутреннее состояние:**
- `form`
- `citySearch`
- `formError`
- `createdCredentials`
- `fieldError`

**Используемые хуки:**
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useRef()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<City />`
- `<Link />`
- `<RecruiterCreateResponse />`
- `<RoleGuard />`
- `<TimezoneOption />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/recruiter-form.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/recruiters.tsx`

**Тип:** Страница
**Строк кода:** ~211
**Назначение:** SPA-страница `recruiters`.

**Экспорты:**
- `RecruitersPage` — строка ~24

**Ключевые функции:**
- `RecruitersPage()` — строка ~24

**Внутреннее состояние:**
- `rowError`

**Используемые хуки:**
- `useMutation()`
- `useQueryClient()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<Link />`
- `<Record />`
- `<Recruiter />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/reminder-ops.tsx`

**Тип:** Страница
**Строк кода:** ~198
**Назначение:** SPA-страница `reminder-ops`.

**Экспорты:**
- `ReminderOpsPage` — строка ~56

**Ключевые функции:**
- `formatDt()` — строка ~39

**Внутреннее состояние:**
- `kindFilter`
- `autoRefresh`

**Используемые хуки:**
- `useMutation()`
- `useQuery()`
- `useQueryClient()`
- `useState()`

**API / сетевые вызовы:**
- `fetchReminderJobs()`

**Дочерние компоненты:**
- `<ReminderJobsResponse />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/simulator.tsx`

**Тип:** Страница
**Строк кода:** ~174
**Назначение:** SPA-страница `simulator`.

**Экспорты:**
- `SimulatorPage` — строка ~62

**Ключевые функции:**
- `fmtMs()` — строка ~57
- `SimulatorPage()` — строка ~62

**Внутреннее состояние:**
- `scenario`
- `runId`

**Используемые хуки:**
- `useMemo()`
- `useMutation()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<RoleGuard />`
- `<SimulatorReportResponse />`
- `<SimulatorRunResponse />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/slots-create.tsx`

**Тип:** Страница
**Строк кода:** ~633
**Назначение:** SPA-страница `slots-create`.

**Экспорты:**
- `SlotsCreateForm` — строка ~72

**Ключевые функции:**
- `SlotsCreateForm()` — строка ~72
- `BulkCreateForm()` — строка ~289
- `computeBulkPreview()` — строка ~527
- `formatInTz()` — строка ~568
- `getOffsetMinutes()` — строка ~582
- `localToUtc()` — строка ~606
- `dateTimeInTz()` — строка ~616

**Внутреннее состояние:**
- `serverError`
- `toast`
- `mode`
- `successMessage`
- `serverError`
- `successMessage`
- `toast`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useQueryClient()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<BulkCreateForm />`
- `<CityPayload />`
- `<FormValues />`
- `<Link />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useProfile.ts`

**Состояние / проблемы:**
- `any`: 5

### `frontend/app/src/app/routes/app/slots.filters.test.ts`

**Тип:** Страница
**Строк кода:** ~94
**Назначение:** SPA-страница `slots.filters.test`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/slots.filters.ts`

**Тип:** Страница
**Строк кода:** ~107
**Назначение:** SPA-страница `slots.filters`.

**Экспорты:**
- `parseSlotsPersistedFilters` — строка ~57
- `loadSlotsPersistedFilters` — строка ~83
- `saveSlotsPersistedFilters` — строка ~91
- `clearSlotsPersistedFilters` — строка ~100
- `SLOTS_FILTERS_STORAGE_KEY` — строка ~23
- `SlotSortField` — строка ~3
- `SlotSortDir` — строка ~4
- `SlotsPersistedFilters` — строка ~6

**Ключевые функции:**
- `isObject()` — строка ~34
- `pickString()` — строка ~42
- `pickNumber()` — строка ~46
- `pickPositiveInt()` — строка ~51
- `parseSlotsPersistedFilters()` — строка ~57
- `loadSlotsPersistedFilters()` — строка ~83
- `saveSlotsPersistedFilters()` — строка ~91
- `clearSlotsPersistedFilters()` — строка ~100

**Дочерние компоненты:**
- `<SlotsPersistedFilters />`
- `<Storage />`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/slots.tsx`

**Тип:** Страница
**Строк кода:** ~1559
**Назначение:** SPA-страница `slots`.

**Экспорты:**
- `SlotsPage` — строка ~571

**Ключевые функции:**
- `statusLabel()` — строка ~59
- `ModalPortal()` — строка ~81
- `BookingModal()` — строка ~86
- `getDateTimeParts()` — строка ~239
- `ManualBookingModal()` — строка ~273
- `RescheduleModal()` — строка ~487
- `SlotsPage()` — строка ~571

**Внутреннее состояние:**
- `search`
- `debouncedSearch`
- `selectedCandidate`
- `search`
- `debouncedSearch`
- `selectedCandidate`
- `fio`
- `phone`
- `comment`
- `date`
- `time`
- `error`
- `cityId`
- `recruiterId`
- `date`
- `time`
- `reason`
- `error`
- `statusFilter`
- `purposeFilter`

**Используемые хуки:**
- `useCallback()`
- `useEffect()`
- `useIsMobile()`
- `useMemo()`
- `useMutation()`
- `useProfile()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`
- `createManualSlotBooking()`
- `createPortal()`
- `deleteSlot()`
- `deleteSlotRequest()`
- `submitSlotsBulkAction()`

**Дочерние компоненты:**
- `<ApiErrorBanner />`
- `<BookingModal />`
- `<CandidateSearchItem />`
- `<CityOption />`
- `<Link />`
- `<ManualBookingModal />`
- `<ModalPortal />`
- `<RecruiterOption />`
- `<RescheduleModal />`
- `<RoleGuard />`
- `<Set />`
- `<SlotApiItem />`
- `<SlotSortDir />`
- `<SlotSortField />`
- `<SlotStatusFilter />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/hooks/useProfile.ts`

**Используется в:**
- `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/slots.utils.test.ts`

**Тип:** Страница
**Строк кода:** ~62
**Назначение:** SPA-страница `slots.utils.test`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/slots.utils.ts`

**Тип:** Страница
**Строк кода:** ~152
**Назначение:** SPA-страница `slots.utils`.

**Экспорты:**
- `normalizeSlotStatus` — строка ~38
- `slotPurpose` — строка ~49
- `slotHasCandidate` — строка ~53
- `slotRecruiterTz` — строка ~57
- `slotRegionTz` — строка ~61
- `slotRecruiterTimeLabel` — строка ~96
- `slotRegionTimeLabel` — строка ~100
- `slotRecruiterTimestamp` — строка ~106
- `slotRegionTimestamp` — строка ~111
- `slotDateForFilter` — строка ~116
- `buildStatusCounts` — строка ~120
- `matchesStatusFilter` — строка ~144
- `SlotApiItem` — строка ~1
- `SlotUiStatus` — строка ~20
- `SlotStatusFilter` — строка ~27
- `SlotStatusCounts` — строка ~29

**Ключевые функции:**
- `normalizeSlotStatus()` — строка ~38
- `slotPurpose()` — строка ~49
- `slotHasCandidate()` — строка ~53
- `slotRecruiterTz()` — строка ~57
- `slotRegionTz()` — строка ~61
- `formatInZone()` — строка ~65
- `formatDateOnlyInZone()` — строка ~80
- `slotRecruiterTimeLabel()` — строка ~96
- `slotRegionTimeLabel()` — строка ~100
- `slotRecruiterTimestamp()` — строка ~106
- `slotRegionTimestamp()` — строка ~111
- `slotDateForFilter()` — строка ~116
- `buildStatusCounts()` — строка ~120
- `matchesStatusFilter()` — строка ~144

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/system.tsx`

**Тип:** Страница
**Строк кода:** ~798
**Назначение:** SPA-страница `system`.

**Экспорты:**
- `SystemPage` — строка ~30

**Ключевые функции:**
- `SystemPage()` — строка ~30

**Внутреннее состояние:**
- `activeTab`
- `resyncResult`
- `outboxStatusFilter`
- `outboxTypeFilter`
- `logStatusFilter`
- `logTypeFilter`
- `logCandidateFilter`
- `refreshingCities`
- `refreshResult`
- `policyDraft`
- `savingPolicy`
- `policyResult`

**Используемые хуки:**
- `useEffect()`
- `useMutation()`
- `useQuery()`
- `useState()`

**API / сетевые вызовы:**
- `fetchNotificationLogs()`
- `fetchNotificationsFeed()`
- `fetchReminderJobs()`
- `refreshBotCitiesRequest()`
- `updateInterviewPolicy()`
- `updateIntroPolicy()`
- `updateReminderPolicy()`

**Дочерние компоненты:**
- `<BotCenterTab />`
- `<BotStatus />`
- `<HealthPayload />`
- `<Link />`
- `<NotificationLogsPayload />`
- `<OutboxFeedPayload />`
- `<QuestionGroup />`
- `<ReminderPolicy />`
- `<ReminderPolicyPayload />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/RoleGuard.tsx`

**Используется в:**
- `frontend/app/src/app/main.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/template-edit.tsx`

**Тип:** Страница
**Строк кода:** ~335
**Назначение:** SPA-страница `template-edit`.

**Экспорты:**
- `TemplateEditPage` — строка ~53

**Ключевые функции:**
- `TemplateEditPage()` — строка ~53
- `TEMPLATE_GROUPS()` — строка ~29

**Внутреннее состояние:**
- `form`
- `formError`
- `serverPreview`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useParams()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<City />`
- `<HTMLTextAreaElement />`
- `<Link />`
- `<Record />`
- `<RoleGuard />`
- `<TemplateDetail />`
- `<TemplateStage />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/template_meta.ts`

**Состояние / проблемы:**
- `any`: 2

### `frontend/app/src/app/routes/app/template-list.tsx`

**Тип:** Страница
**Строк кода:** ~531
**Назначение:** SPA-страница `template-list`.

**Экспорты:**
- `TemplateListPage` — строка ~247

**Ключевые функции:**
- `pickLatest()` — строка ~53
- `CoverageMatrix()` — строка ~61
- `TemplateListPage()` — строка ~247

**Внутреннее состояние:**
- `selectedCity`
- `search`
- `stageFilter`
- `showMatrix`

**Используемые хуки:**
- `useIsMobile()`
- `useMemo()`
- `useNavigate()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<CoverageMatrix />`
- `<Link />`
- `<MessageTemplatesPayload />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/hooks/useIsMobile.ts`

**Комментарии / явные подсказки в файле:**
- Global column
- City columns

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/template-new.tsx`

**Тип:** Страница
**Строк кода:** ~269
**Назначение:** SPA-страница `template-new`.

**Экспорты:**
- `TemplateNewPage` — строка ~65

**Ключевые функции:**
- `renderPreview()` — строка ~56
- `TemplateNewPage()` — строка ~65
- `TEMPLATE_GROUPS()` — строка ~32

**Внутреннее состояние:**
- `form`
- `formError`
- `preview`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useSearch()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<City />`
- `<HTMLTextAreaElement />`
- `<Link />`
- `<RoleGuard />`
- `<TemplateStage />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/template_meta.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/template_meta.ts`

**Тип:** Страница
**Строк кода:** ~355
**Назначение:** SPA-страница `template_meta`.

**Экспорты:**
- `templateTitle` — строка ~342
- `templateStage` — строка ~347
- `templateDesc` — строка ~352
- `STAGE_LABELS` — строка ~24
- `TEMPLATE_META` — строка ~55
- `TemplateStage` — строка ~9
- `TemplateMeta` — строка ~18

**Ключевые функции:**
- `templateTitle()` — строка ~342
- `templateStage()` — строка ~347
- `templateDesc()` — строка ~352

**Дочерние компоненты:**
- `<TemplateStage />`

**Используется в:**
- `frontend/app/src/app/routes/app/city-edit.tsx`
- `frontend/app/src/app/routes/app/template-edit.tsx`
- `frontend/app/src/app/routes/app/template-new.tsx`

**Комментарии / явные подсказки в файле:**
- *
- * Look up title for a key; fall back to the raw key.
- * Look up stage for a key; fall back to 'service'.
- * Look up description for a key.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/test-builder-graph.tsx`

**Тип:** Страница
**Строк кода:** ~1148
**Назначение:** SPA-страница `test-builder-graph`.

**Экспорты:**
- `TestBuilderGraphPage` — строка ~277

**Ключевые функции:**
- `readQuestionId()` — строка ~114
- `readQuestionKey()` — строка ~125
- `normalizeEdgeData()` — строка ~133
- `edgeLabel()` — строка ~169
- `stripNode()` — строка ~184
- `stripEdge()` — строка ~193
- `formatPrompt()` — строка ~205
- `StartNode()` — строка ~212
- `EndNode()` — строка ~222
- `QuestionNode()` — строка ~232
- `makeBranchEdge()` — строка ~261
- `TestBuilderGraphPage()` — строка ~277

**Внутреннее состояние:**
- `activeTest`
- `message`
- `selectedQuestionId`
- `selectedEdgeId`
- `editTitle`
- `editPayload`
- `editActive`
- `payloadValid`
- `edgeMatch`
- `edgeWhen`
- `edgeFallback`
- `edgeAction`
- `edgeReason`
- `edgeTemplateKey`
- `edgePriority`
- `edgeCustomLabel`
- `previewAnswers`
- `previewInput`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useQuery()`
- `useState()`

**Дочерние компоненты:**
- `<Background />`
- `<BranchAction />`
- `<BranchEdgeData />`
- `<BranchMatchMode />`
- `<Controls />`
- `<Edge />`
- `<GraphPayload />`
- `<GraphPreviewPayload />`
- `<Handle />`
- `<Link />`
- `<MiniMap />`
- `<Node />`
- `<QuestionDetailPayload />`
- `<QuestionGroup />`
- `<QuestionPayloadEditor />`
- `<ReactFlow />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- `any`: 13

### `frontend/app/src/app/routes/app/test-builder.tsx`

**Тип:** Страница
**Строк кода:** ~447
**Назначение:** SPA-страница `test-builder`.

**Экспорты:**
- `TestBuilderPage` — строка ~49

**Ключевые функции:**
- `reorderById()` — строка ~42
- `TestBuilderPage()` — строка ~49

**Внутреннее состояние:**
- `activeTest`
- `order`
- `dirty`
- `dragId`
- `message`
- `selectedId`
- `editTitle`
- `editPayload`
- `editActive`
- `payloadValid`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useNavigate()`
- `useQuery()`
- `useState()`

**Дочерние компоненты:**
- `<Link />`
- `<QuestionDetailPayload />`
- `<QuestionGroup />`
- `<QuestionPayloadEditor />`
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx`

**Тип:** Страница
**Строк кода:** ~826
**Назначение:** SPA-страница `ui-cosmetics.test`.

**Используемые хуки:**
- `useMutationMock()`
- `useProfileMock()`
- `useQueryMock()`

**Дочерние компоненты:**
- `<CandidateDetailPage />`
- `<CandidatePipeline />`
- `<DashboardPage />`
- `<HTMLButtonElement />`
- `<IncomingPage />`
- `<MessengerPage />`
- `<SlotsPage />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`

**Состояние / проблемы:**
- `any`: 1

### `frontend/app/src/app/routes/app/vacancies.tsx`

**Тип:** Страница
**Строк кода:** ~193
**Назначение:** SPA-страница `vacancies`.

**Экспорты:**
- `VacanciesPage` — строка ~106

**Ключевые функции:**
- `QuestionCountBadge()` — строка ~39
- `VacancyCard()` — строка ~47

**Используемые хуки:**
- `useMutation()`
- `useQuery()`
- `useQueryClient()`

**API / сетевые вызовы:**
- `deleteVacancy()`
- `fetchVacancies()`

**Дочерние компоненты:**
- `<QuestionCountBadge />`
- `<Record />`
- `<VacanciesResponse />`
- `<VacancyCard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/routes/tg-app/candidate.tsx`

**Тип:** Страница
**Строк кода:** ~140
**Назначение:** SPA-страница `candidate`.

**Экспорты:**
- `TgCandidatePage` — строка ~26

**Ключевые функции:**
- `useTgInitData()` — строка ~18
- `TgCandidatePage()` — строка ~26

**Внутреннее состояние:**
- `candidate`
- `loading`
- `error`
- `statusMsg`

**Используемые хуки:**
- `useEffect()`
- `useParams()`
- `useState()`
- `useTgInitData()`

**Дочерние компоненты:**
- `<CandidateDetail />`

**Комментарии / явные подсказки в файле:**
- *

**Состояние / проблемы:**
- `any`: 2

### `frontend/app/src/app/routes/tg-app/incoming.tsx`

**Тип:** Страница
**Строк кода:** ~111
**Назначение:** SPA-страница `incoming`.

**Экспорты:**
- `TgIncomingPage` — строка ~25

**Ключевые функции:**
- `useTgInitData()` — строка ~17
- `TgIncomingPage()` — строка ~25
- `CandidateCard()` — строка ~82

**Внутреннее состояние:**
- `candidates`
- `total`
- `loading`
- `error`

**Используемые хуки:**
- `useEffect()`
- `useState()`
- `useTgInitData()`

**Дочерние компоненты:**
- `<Candidate />`
- `<CandidateCard />`
- `<Link />`

**Комментарии / явные подсказки в файле:**
- *

**Состояние / проблемы:**
- `any`: 1

### `frontend/app/src/app/routes/tg-app/index.tsx`

**Тип:** Страница
**Строк кода:** ~100
**Назначение:** SPA-страница `index`.

**Экспорты:**
- `TgDashboardPage` — строка ~32

**Ключевые функции:**
- `useTgInitData()` — строка ~15
- `TgDashboardPage()` — строка ~32
- `KpiCard()` — строка ~83

**Внутреннее состояние:**
- `data`
- `error`

**Используемые хуки:**
- `useEffect()`
- `useState()`
- `useTgInitData()`

**API / сетевые вызовы:**
- `fetchDashboard()`

**Дочерние компоненты:**
- `<DashboardData />`
- `<KpiCard />`
- `<Link />`

**Комментарии / явные подсказки в файле:**
- *

**Состояние / проблемы:**
- `any`: 1

### `frontend/app/src/app/routes/tg-app/layout.tsx`

**Тип:** Страница
**Строк кода:** ~21
**Назначение:** SPA-страница `layout`.

**Экспорты:**
- `TgAppLayout` — строка ~6

**Ключевые функции:**
- `TgAppLayout()` — строка ~6

**Дочерние компоненты:**
- `<Outlet />`

**Комментарии / явные подсказки в файле:**
- *

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

## 3.2 Frontend компоненты

### `frontend/app/src/app/components/ApiErrorBanner.tsx`

**Тип:** Компонент
**Строк кода:** ~52
**Назначение:** UI/feature-компонент `ApiErrorBanner`.

**Экспорты:**
- `ApiErrorBanner` — строка ~22

**Ключевые функции:**
- `extractErrorMessage()` — строка ~12
- `ApiErrorBanner()` — строка ~22

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/cities.tsx`
- `frontend/app/src/app/routes/app/city-edit.tsx`
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/detailization.tsx`
- `frontend/app/src/app/routes/app/message-templates.tsx`
- `frontend/app/src/app/routes/app/profile.tsx`
- `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- `frontend/app/src/app/routes/app/recruiters.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/Calendar/ScheduleCalendar.tsx`

**Тип:** Компонент
**Строк кода:** ~434
**Назначение:** UI/feature-компонент `ScheduleCalendar`.

**Экспорты:**
- `ScheduleCalendar` — строка ~98
- `SlotExtendedProps` — строка ~14
- `TaskExtendedProps` — строка ~35

**Ключевые функции:**
- `isTaskEvent()` — строка ~94
- `ScheduleCalendar()` — строка ~98

**Внутреннее состояние:**
- `dateRange`

**Используемые хуки:**
- `useCallback()`
- `useEffect()`
- `useMemo()`
- `useMutation()`
- `useQueryClient()`
- `useState()`

**API / сетевые вызовы:**
- `apiFetch()`

**Дочерние компоненты:**
- `<CalendarApiResponse />`
- `<FullCalendar />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/Calendar/calendar.css`

**Тип:** Компонент
**Строк кода:** ~357
**Назначение:** UI/feature-компонент `calendar`.

**Комментарии / явные подсказки в файле:**
- FullCalendar Glassmorphism Theme for RecruitSmart
- CSS Custom Properties for theming
- Use when the calendar is rendered inside an existing glass panel (e.g. Dashboard).
- Loading overlay
- Error state
- Toolbar styling
- Table header
- Time grid
- Day grid
- Events

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`

**Тип:** Компонент
**Строк кода:** ~136
**Назначение:** UI/feature-компонент `CandidatePipeline`.

**Экспорты:**
- `CandidatePipeline` — строка ~19

**Внутреннее состояние:**
- `openStageId`

**Используемые хуки:**
- `useEffect()`
- `useMemo()`
- `useReducedMotion()`

**Дочерние компоненты:**
- `<Fragment />`
- `<HTMLDivElement />`
- `<LayoutGroup />`
- `<PipelineConnector />`
- `<PipelineStage />`
- `<StageDetailPanel />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/CandidatePipeline/PipelineConnector.tsx`
- `frontend/app/src/app/components/CandidatePipeline/PipelineStage.tsx`
- `frontend/app/src/app/components/CandidatePipeline/StageDetailPanel.tsx`

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/PipelineConnector.tsx`

**Тип:** Компонент
**Строк кода:** ~37
**Назначение:** UI/feature-компонент `PipelineConnector`.

**Экспорты:**
- `PipelineConnector` — строка ~12

**Используется в:**
- `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/PipelineStage.tsx`

**Тип:** Компонент
**Строк кода:** ~76
**Назначение:** UI/feature-компонент `PipelineStage`.

**Экспорты:**
- `PipelineStage` — строка ~20

**Дочерние компоненты:**
- `<StageBadge />`
- `<StageIndicator />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/CandidatePipeline/StageBadge.tsx`
- `frontend/app/src/app/components/CandidatePipeline/StageIndicator.tsx`

**Используется в:**
- `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/StageBadge.tsx`

**Тип:** Компонент
**Строк кода:** ~29
**Назначение:** UI/feature-компонент `StageBadge`.

**Экспорты:**
- `StageBadge` — строка ~8

**Используется в:**
- `frontend/app/src/app/components/CandidatePipeline/PipelineStage.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/StageDetailPanel.tsx`

**Тип:** Компонент
**Строк кода:** ~107
**Назначение:** UI/feature-компонент `StageDetailPanel`.

**Экспорты:**
- `StageDetailPanel` — строка ~15

**Дочерние компоненты:**
- `<AnimatePresence />`

**Используется в:**
- `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/StageIndicator.tsx`

**Тип:** Компонент
**Строк кода:** ~49
**Назначение:** UI/feature-компонент `StageIndicator`.

**Экспорты:**
- `StageIndicator` — строка ~12

**Дочерние компоненты:**
- `<Check />`

**Используется в:**
- `frontend/app/src/app/components/CandidatePipeline/PipelineStage.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/candidate-pipeline.css`

**Тип:** Компонент
**Строк кода:** ~536
**Назначение:** UI/feature-компонент `candidate-pipeline`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/pipeline.types.ts`

**Тип:** Компонент
**Строк кода:** ~31
**Назначение:** UI/feature-компонент `pipeline.types`.

**Экспорты:**
- `PipelineStageStatus` — строка ~1
- `StageDetailEvent` — строка ~3
- `StageDetail` — строка ~11
- `PipelineStage` — строка ~22

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/pipeline.utils.ts`

**Тип:** Компонент
**Строк кода:** ~86
**Назначение:** UI/feature-компонент `pipeline.utils`.

**Экспорты:**
- `translateSystemMessage` — строка ~24
- `translateSystemMessageList` — строка ~38
- `getStageBadgeLabel` — строка ~44
- `getStageAriaLabel` — строка ~50
- `getConnectorFill` — строка ~68
- `getCurrentStageIndex` — строка ~78

**Ключевые функции:**
- `escapeRegExp()` — строка ~20
- `translateSystemMessage()` — строка ~24
- `translateSystemMessageList()` — строка ~38
- `getStageBadgeLabel()` — строка ~44
- `getStageAriaLabel()` — строка ~50
- `getConnectorFill()` — строка ~68
- `getCurrentStageIndex()` — строка ~78

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidatePipeline/pipeline.variants.ts`

**Тип:** Компонент
**Строк кода:** ~60
**Назначение:** UI/feature-компонент `pipeline.variants`.

**Экспорты:**
- `pipelineMotion` — строка ~1
- `pipelineCardVariants` — строка ~13
- `pipelinePanelVariants` — строка ~27
- `pipelineRailVariants` — строка ~49

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidateTimeline/CandidateTimeline.tsx`

**Тип:** Компонент
**Строк кода:** ~42
**Назначение:** UI/feature-компонент `CandidateTimeline`.

**Экспорты:**
- `CandidateTimeline` — строка ~12

**Внутреннее состояние:**
- `expanded`

**Используемые хуки:**
- `useState()`

**Дочерние компоненты:**
- `<TimelineEvent />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/CandidateTimeline/TimelineEvent.tsx`

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-detail.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidateTimeline/TimelineEvent.tsx`

**Тип:** Компонент
**Строк кода:** ~22
**Назначение:** UI/feature-компонент `TimelineEvent`.

**Экспорты:**
- `TimelineEvent` — строка ~7

**Используется в:**
- `frontend/app/src/app/components/CandidateTimeline/CandidateTimeline.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidateTimeline/candidate-timeline.css`

**Тип:** Компонент
**Строк кода:** ~116
**Назначение:** UI/feature-компонент `candidate-timeline`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CandidateTimeline/timeline.types.ts`

**Тип:** Компонент
**Строк кода:** ~11
**Назначение:** UI/feature-компонент `timeline.types`.

**Экспорты:**
- `TimelineTone` — строка ~1
- `TimelineEvent` — строка ~3

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CohortComparison/CohortBar.tsx`

**Тип:** Компонент
**Строк кода:** ~40
**Назначение:** UI/feature-компонент `CohortBar`.

**Экспорты:**
- `CohortBar` — строка ~8

**Используется в:**
- `frontend/app/src/app/components/CohortComparison/CohortComparison.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CohortComparison/CohortComparison.tsx`

**Тип:** Компонент
**Строк кода:** ~70
**Назначение:** UI/feature-компонент `CohortComparison`.

**Экспорты:**
- `CohortComparison` — строка ~16

**Ключевые функции:**
- `formatMinutes()` — строка ~12

**Дочерние компоненты:**
- `<CohortBar />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/services/candidates.ts`
- `frontend/app/src/app/components/CohortComparison/CohortBar.tsx`

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-detail.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/CohortComparison/cohort-comparison.css`

**Тип:** Компонент
**Строк кода:** ~107
**Назначение:** UI/feature-компонент `cohort-comparison`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/ErrorBoundary.test.tsx`

**Тип:** Компонент
**Строк кода:** ~32
**Назначение:** UI/feature-компонент `ErrorBoundary.test`.

**Ключевые функции:**
- `Bomb()` — строка ~5

**Дочерние компоненты:**
- `<Bomb />`
- `<ErrorBoundary />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/ErrorBoundary.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/ErrorBoundary.tsx`

**Тип:** Компонент
**Строк кода:** ~71
**Назначение:** UI/feature-компонент `ErrorBoundary`.

**Экспорты:**
- `useErrorHandler` — строка ~62
- `ErrorBoundary` — строка ~13

**Ключевые функции:**
- `useErrorHandler()` — строка ~62

**Используемые хуки:**
- `useCallback()`
- `useErrorHandler()`

**Дочерние компоненты:**
- `<Error />`
- `<Props />`

**Используется в:**
- `frontend/app/src/app/components/ErrorBoundary.test.tsx`
- `frontend/app/src/app/main.tsx`

**Состояние / проблемы:**
- console/print: 1

### `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`

**Тип:** Компонент
**Строк кода:** ~368
**Назначение:** UI/feature-компонент `InterviewScript`.

**Экспорты:**
- `InterviewScript` — строка ~38

**Внутреннее состояние:**
- `panelWidth`

**Используемые хуки:**
- `useEffect()`
- `useInterviewScript()`
- `useMemo()`
- `useReducedMotion()`
- `useState()`

**API / сетевые вызовы:**
- `createPortal()`

**Дочерние компоненты:**
- `<AnimatePresence />`
- `<HTMLButtonElement />`
- `<HTMLDivElement />`
- `<ScriptBriefing />`
- `<ScriptQuestion />`
- `<ScriptScorecard />`
- `<ScriptStepper />`
- `<ScriptTimer />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/services/candidates.ts`
- `frontend/app/src/app/components/InterviewScript/ScriptBriefing.tsx`
- `frontend/app/src/app/components/InterviewScript/ScriptQuestion.tsx`
- `frontend/app/src/app/components/InterviewScript/ScriptScorecard.tsx`
- `frontend/app/src/app/components/InterviewScript/ScriptStepper.tsx`
- `frontend/app/src/app/components/InterviewScript/ScriptTimer.tsx`
- `frontend/app/src/app/components/InterviewScript/useInterviewScript.ts`

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-detail.tsx`

**Комментарии / явные подсказки в файле:**
- Layout decision: desktop uses a persistent resizable split-panel docked to the right of the candidate page.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/RatingScale.tsx`

**Тип:** Компонент
**Строк кода:** ~43
**Назначение:** UI/feature-компонент `RatingScale`.

**Экспорты:**
- `RatingScale` — строка ~10

**Используемые хуки:**
- `useReducedMotion()`

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/ScriptQuestion.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/ScriptBriefing.tsx`

**Тип:** Компонент
**Строк кода:** ~72
**Назначение:** UI/feature-компонент `ScriptBriefing`.

**Экспорты:**
- `ScriptBriefing` — строка ~10

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/ScriptNotes.tsx`

**Тип:** Компонент
**Строк кода:** ~20
**Назначение:** UI/feature-компонент `ScriptNotes`.

**Экспорты:**
- `ScriptNotes` — строка ~6

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/ScriptQuestion.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/ScriptQuestion.tsx`

**Тип:** Компонент
**Строк кода:** ~75
**Назначение:** UI/feature-компонент `ScriptQuestion`.

**Экспорты:**
- `ScriptQuestion` — строка ~18

**Дочерние компоненты:**
- `<RatingScale />`
- `<ScriptNotes />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/InterviewScript/RatingScale.tsx`
- `frontend/app/src/app/components/InterviewScript/ScriptNotes.tsx`

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/ScriptScorecard.tsx`

**Тип:** Компонент
**Строк кода:** ~108
**Назначение:** UI/feature-компонент `ScriptScorecard`.

**Экспорты:**
- `ScriptScorecard` — строка ~20

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/ScriptStepper.tsx`

**Тип:** Компонент
**Строк кода:** ~28
**Назначение:** UI/feature-компонент `ScriptStepper`.

**Экспорты:**
- `ScriptStepper` — строка ~9

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/ScriptTimer.tsx`

**Тип:** Компонент
**Строк кода:** ~20
**Назначение:** UI/feature-компонент `ScriptTimer`.

**Экспорты:**
- `ScriptTimer` — строка ~12

**Ключевые функции:**
- `formatElapsed()` — строка ~5

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/interview-script.css`

**Тип:** Компонент
**Строк кода:** ~465
**Назначение:** UI/feature-компонент `interview-script`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/script.prompts.ts`

**Тип:** Компонент
**Строк кода:** ~168
**Назначение:** UI/feature-компонент `script.prompts`.

**Экспорты:**
- `buildInterviewScriptViewModel` — строка ~103
- `INTERVIEW_RECOMMENDATION_LABELS` — строка ~163

**Ключевые функции:**
- `shorten()` — строка ~44
- `firstName()` — строка ~51
- `questionWeight()` — строка ~56
- `personalizedQuestion()` — строка ~65
- `buildInterviewScriptViewModel()` — строка ~103

**Зависимости (локальные импорты):**
- `frontend/app/src/api/services/candidates.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/script.types.ts`

**Тип:** Компонент
**Строк кода:** ~56
**Назначение:** UI/feature-компонент `script.types`.

**Экспорты:**
- `InterviewScriptQuestionView` — строка ~3
- `InterviewScriptViewModel` — строка ~14
- `InterviewScriptStep` — строка ~27
- `InterviewScriptQuestionState` — строка ~34
- `InterviewScriptDraft` — строка ~40
- `InterviewScriptBaseContext` — строка ~51

**Зависимости (локальные импорты):**
- `frontend/app/src/api/services/candidates.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/script.variants.ts`

**Тип:** Компонент
**Строк кода:** ~47
**Назначение:** UI/feature-компонент `script.variants`.

**Экспорты:**
- `scriptMotion` — строка ~1
- `scriptPanelVariants` — строка ~7
- `scriptStepVariants` — строка ~21
- `scriptScorecardItemVariants` — строка ~35

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/InterviewScript/useInterviewScript.ts`

**Тип:** Компонент
**Строк кода:** ~335
**Назначение:** UI/feature-компонент `useInterviewScript`.

**Экспорты:**
- `useInterviewScript` — строка ~79

**Ключевые функции:**
- `storageKey()` — строка ~22
- `parseStoredDraft()` — строка ~26
- `saveStoredDraft()` — строка ~37
- `defaultQuestionState()` — строка ~47
- `buildSteps()` — строка ~60
- `clampStep()` — строка ~75
- `useInterviewScript()` — строка ~79

**Внутреннее состояние:**
- `phase`
- `errorMessage`
- `viewModel`
- `rawScript`
- `questionState`
- `currentStep`
- `startedAt`
- `lastSavedAt`
- `overallRecommendation`
- `finalComment`
- `elapsedSec`

**Используемые хуки:**
- `useEffect()`
- `useInterviewScript()`
- `useMemo()`
- `useMutation()`
- `useQueryClient()`
- `useState()`

**API / сетевые вызовы:**
- `refreshCandidateInterviewScript()`
- `submitCandidateInterviewScriptFeedback()`

**Дочерние компоненты:**
- `<InterviewScriptPayload />`
- `<InterviewScriptViewModel />`
- `<Record />`

**Используется в:**
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/QuestionPayloadEditor.tsx`

**Тип:** Компонент
**Строк кода:** ~535
**Назначение:** UI/feature-компонент `QuestionPayloadEditor`.

**Экспорты:**
- `QuestionPayloadEditor` — строка ~157

**Ключевые функции:**
- `normalizeOption()` — строка ~38
- `convertPayloadToState()` — строка ~47
- `buildPayloadFromState()` — строка ~98
- `buildPreview()` — строка ~130
- `QuestionPayloadEditor()` — строка ~157

**Внутреннее состояние:**
- `status`
- `previewItems`
- `builderState`
- `builderEnabled`
- `builderMessage`

**Используемые хуки:**
- `useCallback()`
- `useEffect()`
- `useMemo()`
- `useRef()`
- `useState()`

**API / сетевые вызовы:**
- `updateFromBuilder()`

**Дочерние компоненты:**
- `<BuilderState />`
- `<PreviewItem />`

**Используется в:**
- `frontend/app/src/app/routes/app/question-edit.tsx`
- `frontend/app/src/app/routes/app/question-new.tsx`
- `frontend/app/src/app/routes/app/test-builder-graph.tsx`
- `frontend/app/src/app/routes/app/test-builder.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/QuickNotes/QuickNotes.tsx`

**Тип:** Компонент
**Строк кода:** ~76
**Назначение:** UI/feature-компонент `QuickNotes`.

**Экспорты:**
- `QuickNotes` — строка ~27

**Ключевые функции:**
- `readStoredNote()` — строка ~12

**Внутреннее состояние:**
- `text`
- `savedAt`

**Используемые хуки:**
- `useEffect()`
- `useState()`

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-detail.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/RoleGuard.test.tsx`

**Тип:** Компонент
**Строк кода:** ~96
**Назначение:** UI/feature-компонент `RoleGuard.test`.

**Используемые хуки:**
- `useProfileMock()`

**Дочерние компоненты:**
- `<RoleGuard />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/components/RoleGuard.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/components/RoleGuard.tsx`

**Тип:** Компонент
**Строк кода:** ~69
**Назначение:** UI/feature-компонент `RoleGuard`.

**Экспорты:**
- `RoleGuard` — строка ~10

**Ключевые функции:**
- `RoleGuard()` — строка ~10

**Используемые хуки:**
- `useEffect()`
- `useNavigate()`
- `useProfile()`

**Дочерние компоненты:**
- `<Link />`

**Зависимости (локальные импорты):**
- `frontend/app/src/app/hooks/useProfile.ts`

**Используется в:**
- `frontend/app/src/app/components/RoleGuard.test.tsx`
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/app/routes/app/candidate-new.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/cities.tsx`
- `frontend/app/src/app/routes/app/city-edit.tsx`
- `frontend/app/src/app/routes/app/city-new.tsx`
- `frontend/app/src/app/routes/app/copilot.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/message-templates.tsx`
- `frontend/app/src/app/routes/app/question-edit.tsx`
- `frontend/app/src/app/routes/app/question-new.tsx`
- `frontend/app/src/app/routes/app/questions.tsx`
- `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- `frontend/app/src/app/routes/app/recruiter-new.tsx`
- `frontend/app/src/app/routes/app/recruiters.tsx`
- `frontend/app/src/app/routes/app/simulator.tsx`
- `frontend/app/src/app/routes/app/slots-create.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`
- `frontend/app/src/app/routes/app/system.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

## 3.3 Frontend hooks / lib / API

### `frontend/app/src/api/client.ts`

**Тип:** API-модуль
**Строк кода:** ~134
**Назначение:** Клиентский API-модуль `client`.

**Экспорты:**
- `API_URL` — строка ~3
- `queryClient` — строка ~5

**API / сетевые вызовы:**
- `fetchCsrfToken()`

**Используется в:**
- `frontend/app/src/api/services/candidates.ts`
- `frontend/app/src/api/services/dashboard.ts`
- `frontend/app/src/api/services/messenger.ts`
- `frontend/app/src/api/services/profile.ts`
- `frontend/app/src/api/services/slots.ts`
- `frontend/app/src/api/services/system.ts`
- `frontend/app/src/app/components/Calendar/ScheduleCalendar.tsx`
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/__root.ui-mode.test.tsx`
- `frontend/app/src/app/routes/app/calendar.tsx`
- `frontend/app/src/app/routes/app/candidate-new.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/cities.tsx`
- `frontend/app/src/app/routes/app/city-edit.tsx`
- `frontend/app/src/app/routes/app/city-new.tsx`
- `frontend/app/src/app/routes/app/copilot.tsx`
- `frontend/app/src/app/routes/app/detailization.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/message-templates.tsx`

**Состояние / проблемы:**
- `any`: 2

### `frontend/app/src/api/schema.ts`

**Тип:** API-модуль
**Строк кода:** ~4828
**Назначение:** Клиентский API-модуль `schema`.

**Экспорты:**
- `webhooks` — строка ~1535
- `paths` — строка ~6
- `components` — строка ~1536
- `operations` — строка ~1904

**Комментарии / явные подсказки в файле:**
- *
- * Login Form
- * Login
- * Logout
- * Index
- *
- * Dashboard Funnel
- * Dashboard Funnel Step
- * Slots List
- * Slots Api Create

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/api/services/candidates.ts`

**Тип:** API-сервис
**Строк кода:** ~690
**Назначение:** Клиентский API-модуль `candidates`.

**Экспорты:**
- `fetchCities` — строка ~536
- `fetchCandidateDetail` — строка ~540
- `fetchCandidateHHSummary` — строка ~544
- `fetchCandidateCohortComparison` — строка ~548
- `fetchCandidateChat` — строка ~552
- `waitForCandidateChat` — строка ~556
- `sendCandidateChatMessage` — строка ~570
- `markCandidateChatRead` — строка ~577
- `scheduleCandidateSlot` — строка ~583
- `scheduleCandidateInterview` — строка ~590
- `scheduleCandidateIntroDay` — строка ~600
- `applyCandidateAction` — строка ~610
- `fetchCandidateInterviewScript` — строка ~617
- `refreshCandidateInterviewScript` — строка ~621
- `submitCandidateInterviewScriptFeedback` — строка ~625
- `fetchCandidateAiSummary` — строка ~632
- `refreshCandidateAiSummary` — строка ~636
- `fetchCandidateAiCoach` — строка ~640
- `refreshCandidateAiCoach` — строка ~644
- `upsertCandidateAiResume` — строка ~648

**Ключевые функции:**
- `fetchCities()` — строка ~536
- `fetchCandidateDetail()` — строка ~540
- `fetchCandidateHHSummary()` — строка ~544
- `fetchCandidateCohortComparison()` — строка ~548
- `fetchCandidateChat()` — строка ~552
- `waitForCandidateChat()` — строка ~556
- `sendCandidateChatMessage()` — строка ~570
- `markCandidateChatRead()` — строка ~577
- `scheduleCandidateSlot()` — строка ~583
- `scheduleCandidateInterview()` — строка ~590
- `scheduleCandidateIntroDay()` — строка ~600
- `applyCandidateAction()` — строка ~610
- `fetchCandidateInterviewScript()` — строка ~617
- `refreshCandidateInterviewScript()` — строка ~621
- `submitCandidateInterviewScriptFeedback()` — строка ~625
- `fetchCandidateAiSummary()` — строка ~632
- `refreshCandidateAiSummary()` — строка ~636
- `fetchCandidateAiCoach()` — строка ~640
- `refreshCandidateAiCoach()` — строка ~644
- `upsertCandidateAiResume()` — строка ~648
- `fetchCandidateChatDrafts()` — строка ~658
- `fetchCandidateCoachDrafts()` — строка ~665
- `fetchTemplateByKey()` — строка ~672
- `searchCandidates()` — строка ~687

**API / сетевые вызовы:**
- `apiFetch()`
- `fetchCandidateAiCoach()`
- `fetchCandidateAiSummary()`
- `fetchCandidateChat()`
- `fetchCandidateChatDrafts()`
- `fetchCandidateCoachDrafts()`
- `fetchCandidateCohortComparison()`
- `fetchCandidateDetail()`
- `fetchCandidateHHSummary()`
- `fetchCandidateInterviewScript()`
- `fetchCities()`
- `fetchTemplateByKey()`
- `markCandidateChatRead()`
- `refreshCandidateAiCoach()`
- `refreshCandidateAiSummary()`
- `refreshCandidateInterviewScript()`
- `scheduleCandidateInterview()`
- `scheduleCandidateIntroDay()`
- `scheduleCandidateSlot()`
- `sendCandidateChatMessage()`

**Дочерние компоненты:**
- `<AICoachResponse />`
- `<AIDraftsResponse />`
- `<AISummaryResponse />`
- `<CandidateAiResumeUpsertResponse />`
- `<CandidateCohortComparison />`
- `<CandidateDetail />`
- `<CandidateHHSummary />`
- `<CandidateSearchResult />`
- `<ChatPayload />`
- `<CityOption />`
- `<InterviewScriptResponse />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Используется в:**
- `frontend/app/src/app/components/CohortComparison/CohortComparison.tsx`
- `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`
- `frontend/app/src/app/components/InterviewScript/script.prompts.ts`
- `frontend/app/src/app/components/InterviewScript/script.types.ts`
- `frontend/app/src/app/routes/app/incoming.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/api/services/dashboard.ts`

**Тип:** API-сервис
**Строк кода:** ~138
**Назначение:** Клиентский API-модуль `dashboard`.

**Экспорты:**
- `fetchDashboardSummary` — строка ~99
- `fetchDashboardRecruiters` — строка ~103
- `fetchDashboardIncoming` — строка ~107
- `fetchCurrentKpis` — строка ~111
- `fetchRecruiterPerformance` — строка ~115
- `rejectDashboardCandidate` — строка ~119
- `scheduleDashboardIncomingSlot` — строка ~123
- `SummaryPayload` — строка ~3
- `KPITrend` — строка ~16
- `KPICard` — строка ~21
- `KPIResponse` — строка ~31
- `RecruiterOption` — строка ~41
- `LeaderboardItem` — строка ~46
- `LeaderboardPayload` — строка ~60
- `IncomingCandidate` — строка ~65
- `IncomingPayload` — строка ~95

**Ключевые функции:**
- `fetchDashboardSummary()` — строка ~99
- `fetchDashboardRecruiters()` — строка ~103
- `fetchDashboardIncoming()` — строка ~107
- `fetchCurrentKpis()` — строка ~111
- `fetchRecruiterPerformance()` — строка ~115
- `rejectDashboardCandidate()` — строка ~119
- `scheduleDashboardIncomingSlot()` — строка ~123

**API / сетевые вызовы:**
- `fetchCurrentKpis()`
- `fetchDashboardIncoming()`
- `fetchDashboardRecruiters()`
- `fetchDashboardSummary()`
- `fetchRecruiterPerformance()`
- `scheduleDashboardIncomingSlot()`

**Дочерние компоненты:**
- `<IncomingPayload />`
- `<KPIResponse />`
- `<LeaderboardPayload />`
- `<RecruiterOption />`
- `<SummaryPayload />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/api/services/messenger.ts`

**Тип:** API-сервис
**Строк кода:** ~198
**Назначение:** Клиентский API-модуль `messenger`.

**Экспорты:**
- `fetchCandidateChatThreads` — строка ~80
- `waitForCandidateChatThreads` — строка ~95
- `fetchCandidateChatMessages` — строка ~117
- `waitForCandidateChatMessages` — строка ~121
- `markCandidateChatThreadRead` — строка ~135
- `archiveCandidateChatThread` — строка ~141
- `unarchiveCandidateChatThread` — строка ~147
- `fetchCandidateChatTemplates` — строка ~153
- `fetchCandidateChatWorkspace` — строка ~157
- `updateCandidateChatWorkspace` — строка ~161
- `sendCandidateThreadMessage` — строка ~175
- `applyCandidateChatQuickAction` — строка ~182
- `CandidateChatFolder` — строка ~3
- `CandidateChatThread` — строка ~5
- `CandidateChatThreadsPayload` — строка ~42
- `CandidateChatMessage` — строка ~48
- `CandidateChatWorkspaceState` — строка ~59
- `CandidateChatPayload` — строка ~67
- `CandidateChatTemplate` — строка ~74

**Ключевые функции:**
- `fetchCandidateChatThreads()` — строка ~80
- `waitForCandidateChatThreads()` — строка ~95
- `fetchCandidateChatMessages()` — строка ~117
- `waitForCandidateChatMessages()` — строка ~121
- `markCandidateChatThreadRead()` — строка ~135
- `archiveCandidateChatThread()` — строка ~141
- `unarchiveCandidateChatThread()` — строка ~147
- `fetchCandidateChatTemplates()` — строка ~153
- `fetchCandidateChatWorkspace()` — строка ~157
- `updateCandidateChatWorkspace()` — строка ~161
- `sendCandidateThreadMessage()` — строка ~175
- `applyCandidateChatQuickAction()` — строка ~182

**API / сетевые вызовы:**
- `apiFetch()`
- `fetchCandidateChatMessages()`
- `fetchCandidateChatTemplates()`
- `fetchCandidateChatThreads()`
- `fetchCandidateChatWorkspace()`
- `markCandidateChatThreadRead()`
- `sendCandidateThreadMessage()`
- `updateCandidateChatWorkspace()`
- `waitForCandidateChatMessages()`
- `waitForCandidateChatThreads()`

**Дочерние компоненты:**
- `<CandidateChatPayload />`
- `<CandidateChatThreadsPayload />`
- `<CandidateChatWorkspaceState />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/api/services/profile.ts`

**Тип:** API-сервис
**Строк кода:** ~157
**Назначение:** Клиентский API-модуль `profile`.

**Экспорты:**
- `fetchProfile` — строка ~57
- `fetchProfileTimezones` — строка ~126
- `fetchProfileKpis` — строка ~130
- `updateProfileSettings` — строка ~134
- `changeProfilePassword` — строка ~141
- `uploadProfileAvatar` — строка ~148
- `deleteProfileAvatar` — строка ~154
- `profileQueryKey` — строка ~55
- `ProfileResponse` — строка ~3
- `TimezoneOption` — строка ~61
- `KpiTrend` — строка ~68
- `KpiDetailRow` — строка ~75
- `KpiMetric` — строка ~82
- `ProfileKpiResponse` — строка ~93
- `ProfileSettingsPayload` — строка ~101
- `ProfileSettingsResponse` — строка ~107
- `ChangePasswordPayload` — строка ~118
- `AvatarUploadResponse` — строка ~123
- `AvatarDeleteResponse` — строка ~124

**Ключевые функции:**
- `fetchProfile()` — строка ~57
- `fetchProfileTimezones()` — строка ~126
- `fetchProfileKpis()` — строка ~130
- `updateProfileSettings()` — строка ~134
- `changeProfilePassword()` — строка ~141
- `uploadProfileAvatar()` — строка ~148
- `deleteProfileAvatar()` — строка ~154

**API / сетевые вызовы:**
- `deleteProfileAvatar()`
- `fetchProfile()`
- `fetchProfileKpis()`
- `fetchProfileTimezones()`
- `updateProfileSettings()`

**Дочерние компоненты:**
- `<AvatarDeleteResponse />`
- `<AvatarUploadResponse />`
- `<ProfileKpiResponse />`
- `<ProfileResponse />`
- `<ProfileSettingsResponse />`
- `<TimezoneOption />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Используется в:**
- `frontend/app/src/app/hooks/useProfile.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/api/services/slots.ts`

**Тип:** API-сервис
**Строк кода:** ~96
**Назначение:** Клиентский API-модуль `slots`.

**Экспорты:**
- `fetchSlots` — строка ~43
- `searchSlotCandidates` — строка ~47
- `assignCandidateToSlot` — строка ~51
- `assignCandidateToSlotSilently` — строка ~58
- `createManualSlotBooking` — строка ~65
- `rescheduleSlot` — строка ~72
- `rejectSlotBooking` — строка ~82
- `deleteSlot` — строка ~86
- `submitSlotsBulkAction` — строка ~90
- `CandidateSearchItem` — строка ~3
- `CandidateSearchPayload` — строка ~12
- `SlotsBulkActionPayload` — строка ~16
- `ManualSlotBookingPayload` — строка ~22
- `ManualSlotBookingResponse` — строка ~34

**Ключевые функции:**
- `searchSlotCandidates()` — строка ~47
- `assignCandidateToSlot()` — строка ~51
- `assignCandidateToSlotSilently()` — строка ~58
- `createManualSlotBooking()` — строка ~65
- `rescheduleSlot()` — строка ~72
- `rejectSlotBooking()` — строка ~82
- `deleteSlot()` — строка ~86
- `submitSlotsBulkAction()` — строка ~90

**API / сетевые вызовы:**
- `apiFetch()`
- `createManualSlotBooking()`
- `deleteSlot()`
- `submitSlotsBulkAction()`

**Дочерние компоненты:**
- `<CandidateSearchPayload />`
- `<ManualSlotBookingResponse />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/api/services/system.ts`

**Тип:** API-сервис
**Строк кода:** ~188
**Назначение:** Клиентский API-модуль `system`.

**Экспорты:**
- `fetchSystemHealth` — строка ~138
- `fetchBotIntegration` — строка ~142
- `fetchQuestionGroups` — строка ~146
- `fetchReminderPolicy` — строка ~150
- `fetchReminderJobs` — строка ~154
- `fetchNotificationsFeed` — строка ~158
- `fetchNotificationLogs` — строка ~162
- `retryNotification` — строка ~166
- `cancelNotification` — строка ~170
- `refreshBotCities` — строка ~174
- `resyncReminderJobs` — строка ~178
- `updateReminderPolicy` — строка ~182
- `HealthPayload` — строка ~3
- `BotStatus` — строка ~16
- `ReminderKindConfig` — строка ~26
- `ReminderPolicy` — строка ~31
- `ReminderPolicyPayload` — строка ~43
- `ReminderPolicyUpdatePayload` — строка ~53
- `ReminderJob` — строка ~61
- `ReminderJobsPayload` — строка ~74

**Ключевые функции:**
- `fetchSystemHealth()` — строка ~138
- `fetchBotIntegration()` — строка ~142
- `fetchQuestionGroups()` — строка ~146
- `fetchReminderPolicy()` — строка ~150
- `fetchReminderJobs()` — строка ~154
- `fetchNotificationsFeed()` — строка ~158
- `fetchNotificationLogs()` — строка ~162
- `retryNotification()` — строка ~166
- `cancelNotification()` — строка ~170
- `refreshBotCities()` — строка ~174
- `resyncReminderJobs()` — строка ~178
- `updateReminderPolicy()` — строка ~182

**API / сетевые вызовы:**
- `apiFetch()`
- `fetchBotIntegration()`
- `fetchNotificationLogs()`
- `fetchNotificationsFeed()`
- `fetchQuestionGroups()`
- `fetchReminderJobs()`
- `fetchReminderPolicy()`
- `fetchSystemHealth()`
- `refreshBotCities()`
- `updateReminderPolicy()`

**Дочерние компоненты:**
- `<BotStatus />`
- `<HealthPayload />`
- `<NotificationLogsPayload />`
- `<OutboxFeedPayload />`
- `<QuestionGroup />`
- `<ReminderJobsPayload />`
- `<ReminderPolicyPayload />`
- `<ReminderPolicyUpdatePayload />`
- `<ReminderResyncPayload />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/hooks/useCalendarWebSocket.ts`

**Тип:** Хук
**Строк кода:** ~130
**Назначение:** Кастомный хук `useCalendarWebSocket`.

**Экспорты:**
- `useCalendarWebSocket` — строка ~20

**Ключевые функции:**
- `useCalendarWebSocket()` — строка ~20

**Используемые хуки:**
- `useCalendarWebSocket()`
- `useCallback()`
- `useEffect()`
- `useQueryClient()`
- `useRef()`

**Дочерние компоненты:**
- `<ReturnType />`
- `<WebSocket />`

**Используется в:**
- `frontend/app/src/app/routes/app/calendar.tsx`

**Состояние / проблемы:**
- console/print: 8

### `frontend/app/src/app/hooks/useIsMobile.ts`

**Тип:** Хук
**Строк кода:** ~88
**Назначение:** Кастомный хук `useIsMobile`.

**Экспорты:**
- `useIsMobile` — строка ~74

**Ключевые функции:**
- `ensureListener()` — строка ~33
- `useIsMobile()` — строка ~74
- `resolveIsMobile()` — строка ~6
- `getInitialIsMobile()` — строка ~20

**Используемые хуки:**
- `useEffect()`
- `useIsMobile()`
- `useIsMobileStore()`

**Дочерние компоненты:**
- `<MobileState />`

**Используется в:**
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/app/calendar.tsx`
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/messenger.tsx`
- `frontend/app/src/app/routes/app/questions.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`
- `frontend/app/src/app/routes/app/template-list.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/hooks/useProfile.ts`

**Тип:** Хук
**Строк кода:** ~14
**Назначение:** Кастомный хук `useProfile`.

**Экспорты:**
- `useProfile` — строка ~6

**Ключевые функции:**
- `useProfile()` — строка ~6

**Используемые хуки:**
- `useProfile()`

**Дочерние компоненты:**
- `<ProfileResponse />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/services/profile.ts`

**Используется в:**
- `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/app/calendar.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/copilot.tsx`
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/detailization.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/message-templates.tsx`
- `frontend/app/src/app/routes/app/profile.tsx`
- `frontend/app/src/app/routes/app/slots-create.tsx`
- `frontend/app/src/app/routes/app/slots.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/lib/timezonePreview.ts`

**Тип:** Файл
**Строк кода:** ~88
**Назначение:** Назначение требует ручного ревью.

**Экспорты:**
- `browserTimeZone` — строка ~55
- `formatTzOffset` — строка ~59
- `buildSlotTimePreview` — строка ~73
- `SlotTimePreview` — строка ~1

**Ключевые функции:**
- `getOffsetMinutes()` — строка ~8
- `localToUtc()` — строка ~32
- `formatInTz()` — строка ~44
- `browserTimeZone()` — строка ~55
- `formatTzOffset()` — строка ~59
- `buildSlotTimePreview()` — строка ~73

**Используется в:**
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/messenger.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/app/main.tsx`

**Тип:** Файл
**Строк кода:** ~369
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `PageLoader()` — строка ~66

**API / сетевые вызовы:**
- `createRoot()`
- `createRootRoute()`
- `createRoute()`
- `createRouter()`

**Дочерние компоненты:**
- `<Component />`
- `<ErrorBoundary />`
- `<PageLoader />`
- `<QueryClientProvider />`
- `<React />`
- `<RouterProvider />`
- `<Suspense />`

**Зависимости (локальные импорты):**
- `frontend/app/src/api/client.ts`
- `frontend/app/src/app/components/ErrorBoundary.tsx`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/app/login.tsx`
- `frontend/app/src/app/routes/app/profile.tsx`
- `frontend/app/src/app/routes/app/system.tsx`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/src/test/setup.ts`

**Тип:** Файл
**Строк кода:** ~15
**Назначение:** Назначение требует ручного ревью.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

## 3.4 Backend routers / handlers

### `backend/apps/admin_api/__init__.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~6
**Назначение:** Назначение требует ручного ревью.

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/main.py`

**Комментарии / явные подсказки в файле:**
- Admin API application exports.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/admin.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~125
**Назначение:** Назначение требует ручного ревью.

**Классы:**
- `AdminAuth` — строка ~13
- `RecruiterAdmin` — строка ~38
- `CityExpertAdmin` — строка ~49
- `CityExecutiveAdmin` — строка ~57
- `CityAdmin` — строка ~65
- `SlotAdmin` — строка ~76

**Ключевые функции:**
- `mount_admin()` — строка ~113

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/views/tests.py`
- `backend/core/settings.py`
- `backend/domain/cities/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_api/main.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/hh_integration.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~6
**Назначение:** Назначение требует ручного ревью.

**Зависимости (локальные импорты):**
- `backend/apps/hh_integration_webhooks.py`

**Используется в:**
- `backend/apps/admin_api/main.py`

**Комментарии / явные подсказки в файле:**
- Direct HH webhook receiver endpoints.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/hh_sync.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~109
**Назначение:** FastAPI-роутер для операций: POST.

**Классы:**
- `SyncCallbackRequest` — строка ~22
- `ResolveCallbackRequest` — строка ~32

**Ключевые функции:**
- `_verify_webhook_secret()` — строка ~43
- `hh_sync_callback()` — строка ~58
- `hh_resolve_callback()` — строка ~84

**Эндпоинты / обработчики:**
- `POST /callback` → `hh_sync_callback()` — строка ~58
- `POST /resolve-callback` → `hh_resolve_callback()` — строка ~84

**Зависимости (локальные импорты):**
- `backend/core/dependencies.py`
- `backend/core/settings.py`
- `backend/domain/hh_sync/worker.py`

**Используется в:**
- `backend/apps/admin_api/main.py`

**Комментарии / явные подсказки в файле:**
- hh.ru sync callback endpoints.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/main.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~181
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `lifespan()` — строка ~25
- `create_app()` — строка ~65

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/admin.py`
- `backend/apps/admin_api/hh_integration.py`
- `backend/apps/admin_api/hh_sync.py`
- `backend/apps/admin_api/slot_assignments.py`
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_api/webapp/routers.py`
- `backend/core/cache.py`
- `backend/core/db.py`
- `backend/core/settings.py`

**Используется в:**
- `backend/apps/admin_api/__init__.py`
- `tests/test_hh_integration_foundation.py`
- `tests/test_webapp_booking_api.py`
- `tests/test_webapp_recruiter.py`
- `tests/test_webapp_smoke.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/slot_assignments.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~77
**Назначение:** FastAPI-роутер для операций: POST.

**Классы:**
- `SlotAssignmentConfirmRequest` — строка ~21
- `SlotAssignmentRescheduleRequest` — строка ~26

**Ключевые функции:**
- `_respond()` — строка ~35
- `api_confirm_slot_assignment()` — строка ~44
- `api_request_reschedule()` — строка ~59

**Эндпоинты / обработчики:**
- `POST /slot-assignments/{assignment_id}/confirm` → `api_confirm_slot_assignment()` — строка ~44
- `POST /slot-assignments/{assignment_id}/request-reschedule` → `api_request_reschedule()` — строка ~59

**Зависимости (локальные импорты):**
- `backend/core/time_utils.py`
- `backend/domain/slot_assignment_service.py`

**Используется в:**
- `backend/apps/admin_api/main.py`

**Комментарии / явные подсказки в файле:**
- Public bot-facing slot assignment endpoints.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/webapp/__init__.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~7
**Назначение:** Назначение требует ручного ревью.

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/webapp/auth.py`
- `backend/apps/admin_api/webapp/recruiter_routers.py`

**Комментарии / явные подсказки в файле:**
- Telegram WebApp API module.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/webapp/auth.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~244
**Назначение:** Назначение требует ручного ревью.

**Классы:**
- `TelegramUser` — строка ~24
- `TelegramWebAppAuth` — строка ~179

**Ключевые функции:**
- `_parse_user_from_init_data()` — строка ~47
- `validate_init_data()` — строка ~83
- `get_telegram_webapp_auth()` — строка ~232

**Зависимости (локальные импорты):**
- `backend/core/settings.py`

**Используется в:**
- `backend/apps/admin_api/webapp/__init__.py`
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_api/webapp/routers.py`
- `tests/test_webapp_auth.py`
- `tests/test_webapp_recruiter.py`

**Комментарии / явные подсказки в файле:**
- Telegram WebApp authentication and initData validation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/webapp/recruiter_routers.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~335
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Классы:**
- `DashboardResponse` — строка ~56
- `CandidateItem` — строка ~63
- `IncomingResponse` — строка ~73
- `CandidateDetailResponse` — строка ~78
- `StatusUpdateRequest` — строка ~89
- `MessageRequest` — строка ~93
- `NoteRequest` — строка ~97
- `SuccessResponse` — строка ~101

**Ключевые функции:**
- `_get_recruiter_for_tg_user()` — строка ~30
- `get_recruiter_webapp_auth()` — строка ~43
- `recruiter_dashboard()` — строка ~112
- `recruiter_incoming()` — строка ~133
- `recruiter_candidate_detail()` — строка ~170
- `recruiter_update_status()` — строка ~210
- `recruiter_send_message()` — строка ~248
- `recruiter_save_note()` — строка ~281

**Эндпоинты / обработчики:**
- `GET /dashboard` → `recruiter_dashboard()` — строка ~112
- `GET /incoming` → `recruiter_incoming()` — строка ~133
- `GET /candidates/{candidate_id}` → `recruiter_candidate_detail()` — строка ~170
- `POST /candidates/{candidate_id}/status` → `recruiter_update_status()` — строка ~210
- `POST /candidates/{candidate_id}/message` → `recruiter_send_message()` — строка ~248
- `POST /candidates/{candidate_id}/notes` → `recruiter_save_note()` — строка ~281

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/webapp/auth.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/recruiter_access.py`
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/domain/candidate_status_service.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Используется в:**
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_api/webapp/__init__.py`
- `tests/test_webapp_recruiter.py`

**Комментарии / явные подсказки в файле:**
- FastAPI routers for Recruiter Telegram Mini App.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_api/webapp/routers.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~729
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Классы:**
- `CandidateInfo` — строка ~49
- `SlotInfo` — строка ~61
- `BookingInfo` — строка ~74
- `IntroDayInfo` — строка ~88
- `CreateBookingRequest` — строка ~106
- `RescheduleBookingRequest` — строка ~112
- `CancelBookingRequest` — строка ~119

**Ключевые функции:**
- `_safe_text()` — строка ~39
- `_booking_conflict_error()` — строка ~126
- `get_me()` — строка ~149
- `get_available_slots()` — строка ~197
- `create_booking()` — строка ~280
- `reschedule_booking()` — строка ~386
- `cancel_booking()` — строка ~568
- `get_intro_day_info()` — строка ~666

**Эндпоинты / обработчики:**
- `GET /me` → `get_me()` — строка ~149
- `GET /slots` → `get_available_slots()` — строка ~197
- `POST /booking` → `create_booking()` — строка ~280
- `POST /reschedule` → `reschedule_booking()` — строка ~386
- `POST /cancel` → `cancel_booking()` — строка ~568
- `GET /intro_day` → `get_intro_day_info()` — строка ~666

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/webapp/auth.py`
- `backend/core/dependencies.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`
- `backend/domain/slot_service.py`

**Используется в:**
- `backend/apps/admin_api/main.py`

**Комментарии / явные подсказки в файле:**
- FastAPI routers for Telegram WebApp API.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/__init__.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~40
**Назначение:** Назначение требует ручного ревью.

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/__init__.py`

**Используется в:**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/routers/__init__.py`
- `backend/apps/admin_ui/routers/api.py`
- `tests/test_admin_state_nullbot.py`
- `tests/test_admin_surface_hardening.py`
- `tests/test_cities_settings_api.py`
- `tests/test_perf_metrics_endpoint.py`

**Комментарии / явные подсказки в файле:**
- Exports for admin UI routers.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/ai.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~446
**Назначение:** FastAPI-роутер для операций: GET, POST, PUT.

**Ключевые функции:**
- `_parse_date_param()` — строка ~40
- `_disabled()` — строка ~51
- `_rate_limited()` — строка ~56
- `api_ai_candidate_summary()` — строка ~62
- `api_ai_candidate_summary_refresh()` — строка ~79
- `api_ai_candidate_coach()` — строка ~97
- `api_ai_candidate_coach_refresh()` — строка ~112
- `api_ai_candidate_coach_drafts()` — строка ~129
- `api_ai_candidate_interview_script()` — строка ~152
- `api_ai_candidate_interview_script_refresh()` — строка ~179
- `api_ai_candidate_hh_resume_upsert()` — строка ~207
- `api_ai_candidate_interview_script_feedback()` — строка ~248
- `api_ai_chat_drafts()` — строка ~267
- `api_ai_dashboard_insights()` — строка ~292
- `api_ai_agent_chat_state()` — строка ~359
- `api_ai_agent_chat_send()` — строка ~373
- `api_ai_city_candidate_recommendations()` — строка ~394
- `api_ai_city_candidate_recommendations_refresh()` — строка ~418

**Эндпоинты / обработчики:**
- `GET /candidates/{candidate_id}/summary` → `api_ai_candidate_summary()` — строка ~62
- `POST /candidates/{candidate_id}/summary/refresh` → `api_ai_candidate_summary_refresh()` — строка ~79
- `GET /candidates/{candidate_id}/coach` → `api_ai_candidate_coach()` — строка ~97
- `POST /candidates/{candidate_id}/coach/refresh` → `api_ai_candidate_coach_refresh()` — строка ~112
- `POST /candidates/{candidate_id}/coach/drafts` → `api_ai_candidate_coach_drafts()` — строка ~129
- `GET /candidates/{candidate_id}/interview-script` → `api_ai_candidate_interview_script()` — строка ~152
- `POST /candidates/{candidate_id}/interview-script/refresh` → `api_ai_candidate_interview_script_refresh()` — строка ~179
- `PUT /candidates/{candidate_id}/hh-resume` → `api_ai_candidate_hh_resume_upsert()` — строка ~207
- `POST /candidates/{candidate_id}/interview-script/feedback` → `api_ai_candidate_interview_script_feedback()` — строка ~248
- `POST /candidates/{candidate_id}/chat/drafts` → `api_ai_chat_drafts()` — строка ~267
- `POST /dashboard/insights` → `api_ai_dashboard_insights()` — строка ~292
- `GET /chat` → `api_ai_agent_chat_state()` — строка ~359
- `POST /chat/message` → `api_ai_agent_chat_send()` — строка ~373
- `GET /cities/{city_id}/candidates/recommendations` → `api_ai_city_candidate_recommendations()` — строка ~394
- `POST /cities/{city_id}/candidates/recommendations/refresh` → `api_ai_city_candidate_recommendations_refresh()` — строка ~418

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/core/ai/service.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/api.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~3638
**Назначение:** FastAPI-роутер для операций: DELETE, GET, PATCH, POST.

**Классы:**
- `CandidateKanbanMovePayload` — строка ~180
- `CandidateChatQuickActionPayload` — строка ~184
- `CandidateChatWorkspacePayload` — строка ~191
- `ManualSlotBookingPayload` — строка ~197
- `StaffMemberPayload` — строка ~344
- `StaffThreadCreatePayload` — строка ~349
- `StaffThreadMembersPayload` — строка ~355
- `StaffCandidateTaskPayload` — строка ~359
- `StaffCandidateDecisionPayload` — строка ~364
- `CalendarTaskCreatePayload` — строка ~368
- `CalendarTaskUpdatePayload` — строка ~377
- `SlotsBulkCreatePayload` — строка ~904
- `SlotOutcomePayload` — строка ~947
- `SlotBookPayload` — строка ~951
- `SlotProposePayload` — строка ~956
- `SlotReschedulePayload` — строка ~960
- `SlotsBulkPayload` — строка ~966
- `PlanEntryPayload` — строка ~972

**Ключевые функции:**
- `api_template_keys()` — строка ~143
- `api_template_presets()` — строка ~147
- `_empty_weekly_kpis()` — строка ~159
- `api_csrf()` — строка ~210
- `_parse_bool()` — строка ~223
- `_parse_date_param()` — строка ~234
- `_parse_datetime_param()` — строка ~248
- `_normalize_candidate_chat_folder()` — строка ~260
- `_chat_template_text()` — строка ~267
- `api_health()` — строка ~278
- `api_dashboard_summary()` — строка ~284
- `api_dashboard_incoming()` — строка ~304
- `api_dashboard_recruiter_performance()` — строка ~328
- `api_staff_threads()` — строка ~387
- `api_candidate_chat_threads()` — строка ~392
- `api_candidate_chat_threads_updates()` — строка ~410
- `api_candidate_chat_templates()` — строка ~433
- `api_candidate_chat_mark_read()` — строка ~441
- `api_candidate_chat_archive()` — строка ~450
- `api_candidate_chat_unarchive()` — строка ~459
- `api_candidate_chat_workspace()` — строка ~468
- `api_candidate_chat_workspace_update()` — строка ~477
- `api_staff_threads_create()` — строка ~504
- `api_staff_threads_updates()` — строка ~529
- `api_staff_messages()` — строка ~540

**Эндпоинты / обработчики:**
- `GET /csrf` → `api_csrf()` — строка ~210
- `GET /health` → `api_health()` — строка ~278
- `GET /dashboard/summary` → `api_dashboard_summary()` — строка ~284
- `GET /dashboard/incoming` → `api_dashboard_incoming()` — строка ~304
- `GET /dashboard/recruiter-performance` → `api_dashboard_recruiter_performance()` — строка ~328
- `GET /staff/threads` → `api_staff_threads()` — строка ~387
- `GET /candidate-chat/threads` → `api_candidate_chat_threads()` — строка ~392
- `GET /candidate-chat/threads/updates` → `api_candidate_chat_threads_updates()` — строка ~410
- `GET /candidate-chat/templates` → `api_candidate_chat_templates()` — строка ~433
- `POST /candidate-chat/threads/{candidate_id}/read` → `api_candidate_chat_mark_read()` — строка ~441
- `POST /candidate-chat/threads/{candidate_id}/archive` → `api_candidate_chat_archive()` — строка ~450
- `POST /candidate-chat/threads/{candidate_id}/unarchive` → `api_candidate_chat_unarchive()` — строка ~459
- `GET /candidate-chat/threads/{candidate_id}/workspace` → `api_candidate_chat_workspace()` — строка ~468
- `PUT /candidate-chat/threads/{candidate_id}/workspace` → `api_candidate_chat_workspace_update()` — строка ~477
- `POST /staff/threads` → `api_staff_threads_create()` — строка ~504
- `GET /staff/threads/updates` → `api_staff_threads_updates()` — строка ~529
- `GET /staff/threads/{thread_id}/messages` → `api_staff_messages()` — строка ~540
- `POST /staff/threads/{thread_id}/messages` → `api_staff_send_message()` — строка ~551
- `GET /staff/threads/{thread_id}/updates` → `api_staff_messages_updates()` — строка ~585
- `POST /staff/threads/{thread_id}/read` → `api_staff_mark_read()` — строка ~597

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/perf/cache/__init__.py`
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- `backend/apps/admin_ui/perf/metrics/__init__.py`
- `backend/apps/admin_ui/routers/__init__.py`
- `backend/apps/admin_ui/routers/directory.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/calendar_events.py`
- `backend/apps/admin_ui/services/calendar_tasks.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/dashboard_calendar.py`
- `backend/apps/admin_ui/services/kpis.py`
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/apps/admin_ui/services/notifications_ops.py`
- `backend/apps/admin_ui/services/recruiter_plan.py`

**Используется в:**
- `tests/test_admin_template_keys.py`
- `tests/test_api_presets.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/assignments.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~40
**Назначение:** FastAPI-роутер для операций: POST.

**Ключевые функции:**
- `confirm_assignment()` — строка ~21
- `request_reschedule()` — строка ~32

**Эндпоинты / обработчики:**
- `POST /{assignment_id}/confirm` → `confirm_assignment()` — строка ~21
- `POST /{assignment_id}/request-reschedule` → `request_reschedule()` — строка ~32

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/auth.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~502
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `_get_audit_context()` — строка ~37
- `_login_key_func()` — строка ~46
- `_principal_login_key()` — строка ~50
- `_is_locked()` — строка ~55
- `_register_failure()` — строка ~65
- `_register_success()` — строка ~75
- `_is_bruteforce_enabled()` — строка ~80
- `login_for_access_token()` — строка ~94
- `_resolve_principal()` — строка ~179
- `login()` — строка ~188
- `logout()` — строка ~294
- `login_form()` — строка ~310

**Эндпоинты / обработчики:**
- `POST /token` → `login_for_access_token()` — строка ~94
- `POST /login` → `login()` — строка ~188
- `POST /logout` → `logout()` — строка ~294
- `GET /login` → `login_form()` — строка ~310

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/audit.py`
- `backend/core/auth.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/auth_account.py`
- `backend/domain/models.py`

**Используется в:**
- `tests/test_security_auth_hardening.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/candidates.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~1422
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `set_status_interview_declined()` — строка ~78
- `_parse_bool()` — строка ~86
- `_parse_date()` — строка ~97
- `_parse_int()` — строка ~112
- `_load_city_with_recruiters()` — строка ~121
- `_list_active_cities()` — строка ~142
- `_select_primary_recruiter()` — строка ~150
- `candidates_list()` — строка ~160
- `candidates_detailization()` — строка ~191
- `candidates_new()` — строка ~206
- `candidates_create()` — строка ~214
- `candidates_invite_token()` — строка ~313
- `candidates_detail()` — строка ~335
- `candidates_update()` — строка ~344
- `candidates_toggle()` — строка ~381
- `candidates_set_status()` — строка ~390
- `candidates_resend_test2()` — строка ~581
- `candidates_save_interview_notes()` — строка ~675
- `candidates_download_interview_notes()` — строка ~728
- `_format_interview_notes()` — строка ~748
- `candidates_approve_slot()` — строка ~779
- `candidates_approve_upcoming_slot()` — строка ~812
- `candidates_delete()` — строка ~857
- `candidates_delete_all()` — строка ~863
- `candidates_download_report()` — строка ~872

**Эндпоинты / обработчики:**
- `GET ` → `candidates_list()` — строка ~160
- `GET /detailization` → `candidates_detailization()` — строка ~191
- `GET /new` → `candidates_new()` — строка ~206
- `POST /create` → `candidates_create()` — строка ~214
- `POST /{candidate_id}/invite-token` → `candidates_invite_token()` — строка ~313
- `GET /{candidate_id}` → `candidates_detail()` — строка ~335
- `POST /{candidate_id}/update` → `candidates_update()` — строка ~344
- `POST /{candidate_id}/toggle` → `candidates_toggle()` — строка ~381
- `POST /{candidate_id}/status` → `candidates_set_status()` — строка ~390
- `GET /{candidate_id}/resend-test2` → `candidates_resend_test2()` — строка ~581
- `POST /{candidate_id}/interview-notes` → `candidates_save_interview_notes()` — строка ~675
- `GET /{candidate_id}/interview-notes/download` → `candidates_download_interview_notes()` — строка ~728
- `POST /{candidate_id}/slots/{slot_id}/approve` → `candidates_approve_slot()` — строка ~779
- `POST /{candidate_id}/actions/approve_upcoming_slot` → `candidates_approve_upcoming_slot()` — строка ~812
- `POST /{candidate_id}/delete` → `candidates_delete()` — строка ~857
- `POST /delete-all` → `candidates_delete_all()` — строка ~863
- `GET /{candidate_id}/reports/{report_key}` → `candidates_download_report()` — строка ~872
- `GET /{candidate_id}/schedule-slot` → `candidates_schedule_slot_form()` — строка ~907
- `POST /{candidate_id}/schedule-slot` → `candidates_schedule_slot_submit()` — строка ~916
- `GET /{candidate_id}/schedule-intro-day` → `candidates_schedule_intro_day_form()` — строка ~1052

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/timezones.py`
- `backend/apps/admin_ui/utils.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services.py`
- `backend/core/audit.py`
- `backend/core/db.py`
- `backend/core/guards.py`
- `backend/core/sanitizers.py`
- `backend/core/settings.py`
- `backend/core/time_utils.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`
- `backend/domain/slot_assignment_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/cities.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~411
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `_primary_recruiter()` — строка ~28
- `_primary_recruiter_id()` — строка ~38
- `_responsible_key()` — строка ~43
- `_dedupe_responsibles()` — строка ~58
- `_parse_plan_value()` — строка ~83
- `_coerce_bool()` — строка ~104
- `_build_city_form_state()` — строка ~122
- `_prepare_city_edit_context()` — строка ~150
- `cities_list()` — строка ~187
- `cities_new()` — строка ~192
- `cities_edit_page()` — строка ~197
- `cities_edit_submit()` — строка ~202
- `cities_create()` — строка ~207
- `update_city_settings()` — строка ~212
- `update_city_owner()` — строка ~339
- `update_city_status_api()` — строка ~373
- `cities_delete()` — строка ~401

**Эндпоинты / обработчики:**
- `GET ` → `cities_list()` — строка ~187
- `GET /new` → `cities_new()` — строка ~192
- `GET /{city_id}/edit` → `cities_edit_page()` — строка ~197
- `POST /{city_id}/edit` → `cities_edit_submit()` — строка ~202
- `POST /create` → `cities_create()` — строка ~207
- `POST /{city_id}/settings` → `update_city_settings()` — строка ~212
- `POST /{city_id}/owner` → `update_city_owner()` — строка ~339
- `POST /{city_id}/status` → `update_city_status_api()` — строка ~373
- `POST /{city_id}/delete` → `cities_delete()` — строка ~401

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/message_templates.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `backend/core/sanitizers.py`
- `backend/domain/template_stages.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/content_api.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~764
**Назначение:** FastAPI-роутер для операций: DELETE, GET, POST, PUT.

**Ключевые функции:**
- `_recruiter_template_city_ids()` — строка ~69
- `_check_template_access()` — строка ~81
- `_load_template_or_404()` — строка ~106
- `_template_updated_by()` — строка ~114
- `_template_permissions_payload()` — строка ~121
- `_template_can_edit()` — строка ~134
- `api_message_templates()` — строка ~149
- `api_create_message_template()` — строка ~190
- `api_update_message_template()` — строка ~230
- `api_delete_message_template()` — строка ~278
- `api_message_template_history()` — строка ~296
- `api_questions()` — строка ~321
- `api_question_create()` — строка ~326
- `api_question_detail()` — строка ~347
- `api_question_update()` — строка ~369
- `api_question_clone()` — строка ~392
- `api_questions_reorder()` — строка ~406
- `api_test_builder_graph()` — строка ~428
- `api_test_builder_graph_apply()` — строка ~447
- `api_test_builder_graph_preview()` — строка ~466
- `api_templates_list()` — строка ~496
- `api_template_detail()` — строка ~527
- `api_template_update()` — строка ~546
- `api_template_delete()` — строка ~588
- `api_template_create()` — строка ~606

**Эндпоинты / обработчики:**
- `GET /message-templates` → `api_message_templates()` — строка ~149
- `POST /message-templates` → `api_create_message_template()` — строка ~190
- `PUT /message-templates/{template_id}` → `api_update_message_template()` — строка ~230
- `DELETE /message-templates/{template_id}` → `api_delete_message_template()` — строка ~278
- `GET /message-templates/{template_id}/history` → `api_message_template_history()` — строка ~296
- `GET /questions` → `api_questions()` — строка ~321
- `POST /questions` → `api_question_create()` — строка ~326
- `GET /questions/{question_id}` → `api_question_detail()` — строка ~347
- `PUT /questions/{question_id}` → `api_question_update()` — строка ~369
- `POST /questions/{question_id}/clone` → `api_question_clone()` — строка ~392
- `POST /questions/reorder` → `api_questions_reorder()` — строка ~406
- `GET /test-builder/graph` → `api_test_builder_graph()` — строка ~428
- `POST /test-builder/graph/apply` → `api_test_builder_graph_apply()` — строка ~447
- `POST /test-builder/graph/preview` → `api_test_builder_graph_preview()` — строка ~466
- `GET /templates/list` → `api_templates_list()` — строка ~496
- `GET /templates/{template_id:int}` → `api_template_detail()` — строка ~527
- `PUT /templates/{template_id:int}` → `api_template_update()` — строка ~546
- `DELETE /templates/{template_id:int}` → `api_template_delete()` — строка ~588
- `POST /templates` → `api_template_create()` — строка ~606
- `GET /template_keys` → `api_template_keys()` — строка ~707

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/builder_graph.py`
- `backend/apps/admin_ui/services/message_templates.py`
- `backend/apps/admin_ui/services/message_templates_presets.py`
- `backend/apps/admin_ui/services/questions.py`
- `backend/apps/admin_ui/services/test_builder_preview.py`
- `backend/core/audit.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/template_contexts.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/dashboard.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~164
**Назначение:** FastAPI-роутер для операций: GET.

**Ключевые функции:**
- `_parse_date_param()` — строка ~33
- `_empty_weekly_kpis()` — строка ~47
- `_empty_calendar()` — строка ~68
- `index()` — строка ~92
- `dashboard_alias()` — строка ~97
- `dashboard_funnel()` — строка ~103
- `dashboard_funnel_step()` — строка ~137

**Эндпоинты / обработчики:**
- `GET /` → `index()` — строка ~92
- `GET /dashboard` → `dashboard_alias()` — строка ~97
- `GET /dashboard/funnel` → `dashboard_funnel()` — строка ~103
- `GET /dashboard/funnel/step` → `dashboard_funnel_step()` — строка ~137

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/dashboard_calendar.py`
- `backend/apps/admin_ui/services/kpis.py`
- `backend/apps/admin_ui/utils.py`
- `backend/core/settings.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/detailization.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~133
**Назначение:** FastAPI-роутер для операций: DELETE, GET, PATCH, POST.

**Классы:**
- `DetailizationUpdatePayload` — строка ~40
- `DetailizationCreatePayload` — строка ~51

**Ключевые функции:**
- `_parse_query_datetime()` — строка ~24
- `api_detailization_list()` — строка ~64
- `api_detailization_export()` — строка ~79
- `api_detailization_update()` — строка ~102
- `api_detailization_create()` — строка ~114
- `api_detailization_delete()` — строка ~125

**Эндпоинты / обработчики:**
- `GET ` → `api_detailization_list()` — строка ~64
- `GET /export.csv` → `api_detailization_export()` — строка ~79
- `PATCH /{entry_id}` → `api_detailization_update()` — строка ~102
- `POST ` → `api_detailization_create()` — строка ~114
- `DELETE /{entry_id}` → `api_detailization_delete()` — строка ~125

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/detailization.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/directory.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~405
**Назначение:** FastAPI-роутер для операций: DELETE, GET, POST, PUT.

**Ключевые функции:**
- `api_recruiters()` — строка ~36
- `api_recruiter_detail()` — строка ~44
- `api_create_recruiter()` — строка ~55
- `api_update_recruiter()` — строка ~93
- `api_reset_recruiter_password()` — строка ~129
- `api_delete_recruiter()` — строка ~143
- `api_cities()` — строка ~157
- `api_city_detail()` — строка ~188
- `api_city_hh_vacancies()` — строка ~216
- `api_create_city()` — строка ~227
- `api_update_city()` — строка ~279
- `api_delete_city()` — строка ~319
- `api_get_city_reminder_policy()` — строка ~332
- `api_upsert_city_reminder_policy()` — строка ~354
- `api_delete_city_reminder_policy()` — строка ~398

**Эндпоинты / обработчики:**
- `GET /recruiters` → `api_recruiters()` — строка ~36
- `GET /recruiters/{recruiter_id}` → `api_recruiter_detail()` — строка ~44
- `POST /recruiters` → `api_create_recruiter()` — строка ~55
- `PUT /recruiters/{recruiter_id}` → `api_update_recruiter()` — строка ~93
- `POST /recruiters/{recruiter_id}/reset-password` → `api_reset_recruiter_password()` — строка ~129
- `DELETE /recruiters/{recruiter_id}` → `api_delete_recruiter()` — строка ~143
- `GET /cities` → `api_cities()` — строка ~157
- `GET /cities/{city_id}` → `api_city_detail()` — строка ~188
- `GET /cities/{city_id}/hh-vacancies` → `api_city_hh_vacancies()` — строка ~216
- `POST /cities` → `api_create_city()` — строка ~227
- `PUT /cities/{city_id}` → `api_update_city()` — строка ~279
- `DELETE /cities/{city_id}` → `api_delete_city()` — строка ~319
- `GET /cities/{city_id}/reminder-policy` → `api_get_city_reminder_policy()` — строка ~332
- `PUT /cities/{city_id}/reminder-policy` → `api_upsert_city_reminder_policy()` — строка ~354
- `DELETE /cities/{city_id}/reminder-policy` → `api_delete_city_reminder_policy()` — строка ~398

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/cities_hh.py`
- `backend/apps/admin_ui/services/city_reminder_policy.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `backend/core/sanitizers.py`
- `backend/domain/errors.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/hh_integration.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~564
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Классы:**
- `HHActionExecuteRequest` — строка ~51

**Ключевые функции:**
- `_iter_hh_actions()` — строка ~55
- `_serialize_hh_action()` — строка ~62
- `_find_hh_action()` — строка ~85
- `_get_candidate_hh_context()` — строка ~98
- `get_hh_connection()` — строка ~123
- `_finalize_hh_oauth_callback()` — строка ~141
- `get_hh_authorize_url()` — строка ~207
- `hh_oauth_callback()` — строка ~219
- `hh_oauth_callback_compat()` — строка ~237
- `refresh_hh_connection_tokens()` — строка ~254
- `list_hh_webhooks()` — строка ~288
- `register_hh_webhooks()` — строка ~312
- `import_hh_vacancies_route()` — строка ~353
- `import_hh_negotiations_route()` — строка ~383
- `get_hh_sync_jobs()` — строка ~415
- `enqueue_hh_vacancies_import_job()` — строка ~429
- `enqueue_hh_negotiations_import_job()` — строка ~448
- `retry_hh_job()` — строка ~470
- `get_hh_candidate_actions()` — строка ~486
- `execute_hh_candidate_action()` — строка ~510

**Эндпоинты / обработчики:**
- `GET /connection` → `get_hh_connection()` — строка ~123
- `GET /oauth/authorize` → `get_hh_authorize_url()` — строка ~207
- `GET /oauth/callback` → `hh_oauth_callback()` — строка ~219
- `GET /rest/oauth2-credential/callback` → `hh_oauth_callback_compat()` — строка ~237
- `POST /oauth/refresh` → `refresh_hh_connection_tokens()` — строка ~254
- `GET /webhooks` → `list_hh_webhooks()` — строка ~288
- `POST /webhooks/register` → `register_hh_webhooks()` — строка ~312
- `POST /import/vacancies` → `import_hh_vacancies_route()` — строка ~353
- `POST /import/negotiations` → `import_hh_negotiations_route()` — строка ~383
- `GET /jobs` → `get_hh_sync_jobs()` — строка ~415
- `POST /jobs/import/vacancies` → `enqueue_hh_vacancies_import_job()` — строка ~429
- `POST /jobs/import/negotiations` → `enqueue_hh_negotiations_import_job()` — строка ~448
- `POST /jobs/{job_id}/retry` → `retry_hh_job()` — строка ~470
- `GET /candidates/{candidate_id}/actions` → `get_hh_candidate_actions()` — строка ~486
- `POST /candidates/{candidate_id}/actions/{action_id}` → `execute_hh_candidate_action()` — строка ~510

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/ai/service.py`
- `backend/core/dependencies.py`
- `backend/core/settings.py`
- `backend/domain/hh_integration/__init__.py`
- `backend/domain/hh_integration/contracts.py`
- `backend/domain/hh_integration/importer.py`
- `backend/domain/hh_integration/jobs.py`
- `backend/domain/hh_integration/models.py`

**Комментарии / явные подсказки в файле:**
- Admin endpoints for direct HH integration management.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/knowledge_base.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~354
**Назначение:** FastAPI-роутер для операций: DELETE, GET, POST, PUT.

**Ключевые функции:**
- `_normalize_kb_category()` — строка ~26
- `_iso()` — строка ~33
- `_extract_docx_text()` — строка ~44
- `_extract_pdf_text()` — строка ~70
- `_decode_upload_to_text()` — строка ~121
- `api_kb_documents_list()` — строка ~135
- `api_kb_document_get()` — строка ~184
- `api_kb_document_create()` — строка ~215
- `api_kb_document_update()` — строка ~289
- `api_kb_document_delete()` — строка ~327
- `api_kb_document_reindex()` — строка ~345

**Эндпоинты / обработчики:**
- `GET /documents` → `api_kb_documents_list()` — строка ~135
- `GET /documents/{document_id}` → `api_kb_document_get()` — строка ~184
- `POST /documents` → `api_kb_document_create()` — строка ~215
- `PUT /documents/{document_id}` → `api_kb_document_update()` — строка ~289
- `DELETE /documents/{document_id}` → `api_kb_document_delete()` — строка ~327
- `POST /documents/{document_id}/reindex` → `api_kb_document_reindex()` — строка ~345

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/ai/knowledge_base.py`
- `backend/core/ai/llm_script_generator.py`
- `backend/core/db.py`
- `backend/domain/ai/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/message_templates.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~58
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `message_templates_list()` — строка ~12
- `message_templates_new()` — строка ~35
- `message_templates_create()` — строка ~40
- `message_templates_edit()` — строка ~45
- `message_templates_update()` — строка ~50
- `message_templates_delete()` — строка ~55

**Эндпоинты / обработчики:**
- `GET ` → `message_templates_list()` — строка ~12
- `GET /new` → `message_templates_new()` — строка ~35
- `POST /create` → `message_templates_create()` — строка ~40
- `GET /{template_id}/edit` → `message_templates_edit()` — строка ~45
- `POST /{template_id}/update` → `message_templates_update()` — строка ~50
- `POST /{template_id}/delete` → `message_templates_delete()` — строка ~55

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/metrics.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~55
**Назначение:** FastAPI-роутер для операций: GET.

**Ключевые функции:**
- `_metrics_enabled()` — строка ~19
- `_metrics_allowlisted_ips()` — строка ~28
- `_is_metrics_client_allowlisted()` — строка ~40
- `metrics()` — строка ~46

**Эндпоинты / обработчики:**
- `GET /metrics` → `metrics()` — строка ~46

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/perf/metrics/__init__.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/settings.py`

**Комментарии / явные подсказки в файле:**
- Prometheus metrics endpoint (non-breaking, gated by env).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/profile.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~18
**Назначение:** FastAPI-роутер для операций: GET.

**Ключевые функции:**
- `profile()` — строка ~12

**Эндпоинты / обработчики:**
- `GET ` → `profile()` — строка ~12

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/profile_api.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~531
**Назначение:** FastAPI-роутер для операций: DELETE, GET, PATCH, POST.

**Классы:**
- `ProfileSettingsUpdatePayload` — строка ~44
- `ProfilePasswordChangePayload` — строка ~50

**Ключевые функции:**
- `_normalize_profile_http_url()` — строка ~33
- `_avatar_dir()` — строка ~55
- `_avatar_prefix()` — строка ~61
- `_find_avatar_file()` — строка ~65
- `_profile_snapshot()` — строка ~74
- `api_profile()` — строка ~322
- `api_profile_settings_update()` — строка ~366
- `api_profile_change_password()` — строка ~431
- `api_profile_avatar()` — строка ~475
- `api_profile_avatar_upload()` — строка ~483
- `api_profile_avatar_delete()` — строка ~516

**Эндпоинты / обработчики:**
- `GET /profile` → `api_profile()` — строка ~322
- `PATCH /profile/settings` → `api_profile_settings_update()` — строка ~366
- `POST /profile/change-password` → `api_profile_change_password()` — строка ~431
- `GET /profile/avatar` → `api_profile_avatar()` — строка ~475
- `POST /profile/avatar` → `api_profile_avatar_upload()` — строка ~483
- `DELETE /profile/avatar` → `api_profile_avatar_delete()` — строка ~516

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/perf/cache/__init__.py`
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/bot/reminders.py`
- `backend/core/audit.py`
- `backend/core/auth.py`
- `backend/core/db.py`
- `backend/core/passwords.py`
- `backend/core/sanitizers.py`
- `backend/domain/auth_account.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/questions.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~23
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `questions_list()` — строка ~8
- `questions_edit()` — строка ~13
- `questions_update()` — строка ~18

**Эндпоинты / обработчики:**
- `GET ` → `questions_list()` — строка ~8
- `GET /{question_id}/edit` → `questions_edit()` — строка ~13
- `POST /{question_id}/update` → `questions_update()` — строка ~18

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/recruiters.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~35
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `recruiters_list()` — строка ~8
- `recruiters_new()` — строка ~13
- `recruiters_create()` — строка ~18
- `recruiters_edit()` — строка ~23
- `recruiters_update()` — строка ~28
- `recruiters_delete()` — строка ~33

**Эндпоинты / обработчики:**
- `GET ` → `recruiters_list()` — строка ~8
- `GET /new` → `recruiters_new()` — строка ~13
- `POST /create` → `recruiters_create()` — строка ~18
- `GET /{rec_id}/edit` → `recruiters_edit()` — строка ~23
- `POST /{rec_id}/update` → `recruiters_update()` — строка ~28
- `POST /{rec_id}/delete` → `recruiters_delete()` — строка ~33

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/recruiters_api_example.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~296
**Назначение:** FastAPI-роутер для операций: DELETE, GET, PATCH, POST.

**Классы:**
- `RecruiterResponse` — строка ~28
- `RecruiterCreate` — строка ~38
- `RecruiterUpdate` — строка ~44

**Ключевые функции:**
- `list_recruiters_simple()` — строка ~54
- `list_recruiters()` — строка ~81
- `get_recruiter()` — строка ~107
- `create_recruiter()` — строка ~132
- `update_recruiter()` — строка ~163
- `delete_recruiter()` — строка ~207
- `get_recruiter_cities()` — строка ~236
- `count_free_slots()` — строка ~261

**Эндпоинты / обработчики:**
- `GET /simple` → `list_recruiters_simple()` — строка ~54
- `GET ` → `list_recruiters()` — строка ~81
- `GET /{recruiter_id}` → `get_recruiter()` — строка ~107
- `POST ` → `create_recruiter()` — строка ~132
- `PATCH /{recruiter_id}` → `update_recruiter()` — строка ~163
- `DELETE /{recruiter_id}` → `delete_recruiter()` — строка ~207
- `GET /{recruiter_id}/cities` → `get_recruiter_cities()` — строка ~236
- `GET /{recruiter_id}/slots/free` → `count_free_slots()` — строка ~261

**Зависимости (локальные импорты):**
- `backend/core/dependencies.py`
- `backend/core/result.py`
- `backend/core/uow.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Example API router demonstrating FastAPI Dependency Injection.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/regions.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~21
**Назначение:** FastAPI-роутер для операций: GET.

**Ключевые функции:**
- `region_timezone()` — строка ~11

**Эндпоинты / обработчики:**
- `GET /{region_id}/timezone` → `region_timezone()` — строка ~11

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/reschedule_requests.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~136
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Классы:**
- `NewProposalPayload` — строка ~16

**Ключевые функции:**
- `list_reschedule_requests()` — строка ~21
- `approve_reschedule_request()` — строка ~38
- `propose_new_time()` — строка ~102

**Эндпоинты / обработчики:**
- `GET ` → `list_reschedule_requests()` — строка ~21
- `POST /{request_id}/approve` → `approve_reschedule_request()` — строка ~38
- `POST /{request_id}/propose-new` → `propose_new_time()` — строка ~102

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Используется в:**
- `tests/test_reschedule_requests_scoping.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/simulator.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~228
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `_ensure_enabled()` — строка ~52
- `_serialize_step()` — строка ~57
- `_serialize_run()` — строка ~71
- `simulator_create_run()` — строка ~86
- `simulator_get_run()` — строка ~184
- `simulator_get_report()` — строка ~206

**Эндпоинты / обработчики:**
- `POST /runs` → `simulator_create_run()` — строка ~86
- `GET /runs/{run_id}` → `simulator_get_run()` — строка ~184
- `GET /runs/{run_id}/report` → `simulator_get_report()` — строка ~206

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/simulator/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/slot_assignments.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~178
**Назначение:** FastAPI-роутер для операций: POST.

**Классы:**
- `SlotAssignmentCreateRequest` — строка ~29
- `RescheduleDecisionRequest` — строка ~36
- `AlternativeProposalRequest` — строка ~40

**Ключевые функции:**
- `_respond()` — строка ~45
- `_ensure_assignment_scope()` — строка ~53
- `api_create_slot_assignment()` — строка ~68
- `api_approve_reschedule()` — строка ~120
- `api_propose_alternative()` — строка ~140
- `api_decline_reschedule()` — строка ~161

**Эндпоинты / обработчики:**
- `POST /slot-assignments` → `api_create_slot_assignment()` — строка ~68
- `POST /slot-assignments/{assignment_id}/approve-reschedule` → `api_approve_reschedule()` — строка ~120
- `POST /slot-assignments/{assignment_id}/propose-alternative` → `api_propose_alternative()` — строка ~140
- `POST /slot-assignments/{assignment_id}/decline-reschedule` → `api_decline_reschedule()` — строка ~161

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/core/time_utils.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`
- `backend/domain/slot_assignment_service.py`

**Комментарии / явные подсказки в файле:**
- API endpoints for slot assignments (recruiter/admin actions).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/slot_assignments_api.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~259
**Назначение:** FastAPI-роутер для операций: POST.

**Классы:**
- `ActionPayload` — строка ~21
- `ReschedulePayload` — строка ~25

**Ключевые функции:**
- `_validate_token()` — строка ~31
- `_resolve_candidate_for_assignment()` — строка ~50
- `_known_candidate_tg_ids()` — строка ~68
- `confirm_assignment()` — строка ~85
- `request_reschedule()` — строка ~172
- `decline_assignment()` — строка ~221

**Эндпоинты / обработчики:**
- `POST /{assignment_id}/confirm` → `confirm_assignment()` — строка ~85
- `POST /{assignment_id}/request-reschedule` → `request_reschedule()` — строка ~172
- `POST /{assignment_id}/decline` → `decline_assignment()` — строка ~221

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/core/time_utils.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/services.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`
- `backend/domain/slot_assignment_service.py`

**Используется в:**
- `tests/test_slot_assignment_reschedule_replace.py`
- `tests/test_slot_assignment_slot_sync.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/slots.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~754
**Назначение:** FastAPI-роутер для операций: DELETE, GET, POST, PUT.

**Классы:**
- `SlotPayloadBase` — строка ~152
- `SlotCreatePayload` — строка ~185
- `SlotUpdatePayload` — строка ~190
- `BulkDeletePayload` — строка ~498
- `SlotsBulkAction` — строка ~512
- `SlotsBulkPayload` — строка ~518
- `OutcomePayload` — строка ~583
- `ProposeSlotPayload` — строка ~659
- `BookSlotPayload` — строка ~696

**Ключевые функции:**
- `_parse_checkbox()` — строка ~71
- `_recruiter_has_city()` — строка ~80
- `_pop_flash()` — строка ~97
- `_set_flash()` — строка ~113
- `_slot_payload()` — строка ~132
- `slots_list()` — строка ~196
- `slots_new()` — строка ~212
- `slots_create()` — строка ~219
- `slots_bulk_create()` — строка ~253
- `slots_api_create()` — строка ~296
- `slots_api_update()` — строка ~373
- `slots_api_detail()` — строка ~442
- `slots_delete_form()` — строка ~464
- `slots_delete()` — строка ~480
- `slots_delete_all()` — строка ~503
- `slots_bulk_action()` — строка ~534
- `slots_set_outcome()` — строка ~588
- `slots_reschedule()` — строка ~621
- `slots_reject_booking()` — строка ~633
- `slots_approve_booking()` — строка ~645
- `slots_propose_candidate()` — строка ~664
- `slots_book_candidate()` — строка ~702

**Эндпоинты / обработчики:**
- `GET ` → `slots_list()` — строка ~196
- `GET /new` → `slots_new()` — строка ~212
- `POST /create` → `slots_create()` — строка ~219
- `POST /bulk_create` → `slots_bulk_create()` — строка ~253
- `POST ` → `slots_api_create()` — строка ~296
- `PUT /{slot_id}` → `slots_api_update()` — строка ~373
- `GET /{slot_id}` → `slots_api_detail()` — строка ~442
- `POST /{slot_id}/delete` → `slots_delete_form()` — строка ~464
- `DELETE /{slot_id}` → `slots_delete()` — строка ~480
- `POST /delete_all` → `slots_delete_all()` — строка ~503
- `POST /bulk` → `slots_bulk_action()` — строка ~534
- `POST /{slot_id}/outcome` → `slots_set_outcome()` — строка ~588
- `POST /{slot_id}/reschedule` → `slots_reschedule()` — строка ~621
- `POST /{slot_id}/reject_booking` → `slots_reject_booking()` — строка ~633
- `POST /{slot_id}/approve_booking` → `slots_approve_booking()` — строка ~645
- `POST /{slot_id}/propose` → `slots_propose_candidate()` — строка ~664
- `POST /{slot_id}/book` → `slots_book_candidate()` — строка ~702

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `backend/apps/admin_ui/services/slots/bot.py`
- `backend/apps/admin_ui/services/slots/core.py`
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`
- `backend/core/guards.py`
- `backend/core/settings.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`
- `backend/domain/slot_assignment_service.py`
- `backend/domain/slot_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/system.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~450
**Назначение:** FastAPI-роутер для операций: GET.

**Ключевые функции:**
- `favicon_redirect()` — строка ~26
- `devtools_probe()` — строка ~33
- `liveness_probe()` — строка ~38
- `readiness_probe()` — строка ~44
- `health_check()` — строка ~62
- `bot_health()` — строка ~126
- `notifications_health()` — строка ~223
- `_format_prometheus_labels()` — строка ~324
- `notifications_metrics()` — строка ~340

**Эндпоинты / обработчики:**
- `GET /favicon.ico` → `favicon_redirect()` — строка ~26
- `GET /.well-known/appspecific/com.chrome.devtools.json` → `devtools_probe()` — строка ~33
- `GET /healthz` → `liveness_probe()` — строка ~38
- `GET /ready` → `readiness_probe()` — строка ~44
- `GET /health` → `health_check()` — строка ~62
- `GET /health/bot` → `bot_health()` — строка ~126
- `GET /health/notifications` → `notifications_health()` — строка ~223
- `GET /metrics/notifications` → `notifications_metrics()` — строка ~340

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/core/settings.py`

**Используется в:**
- `tests/test_cache_integration.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/routers/workflow.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~89
**Назначение:** FastAPI-роутер для операций: GET, POST.

**Ключевые функции:**
- `_serialize_state()` — строка ~25
- `get_candidate_state()` — строка ~34
- `apply_action()` — строка ~45

**Эндпоинты / обработчики:**
- `GET /{candidate_id}/state` → `get_candidate_state()` — строка ~34
- `POST /{candidate_id}/actions/{action}` → `apply_action()` — строка ~45

**Зависимости (локальные импорты):**
- `backend/core/audit.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/workflow.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/__init__.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~25
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `register_routers()` — строка ~12

**Зависимости (локальные импорты):**
- `backend/apps/bot/handlers/__init__.py`

**Используется в:**
- `backend/apps/bot/app.py`
- `backend/apps/bot/handlers/__init__.py`
- `tests/handlers/test_common_free_text.py`
- `tests/test_bot_confirmation_flows.py`

**Комментарии / явные подсказки в файле:**
- Router registrations for bot handlers.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/attendance.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~21
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `attendance_yes()` — строка ~14
- `attendance_no()` — строка ~19

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Комментарии / явные подсказки в файле:**
- Handlers for attendance confirmation callbacks.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/common.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~228
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `cmd_start()` — строка ~23
- `cmd_admin()` — строка ~70
- `cmd_invite()` — строка ~92
- `cmd_intro()` — строка ~116
- `cb_home_start()` — строка ~121
- `cb_contact_manual()` — строка ~126
- `cb_noop_hint()` — строка ~140
- `free_text()` — строка ~161

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/services.py`
- `backend/domain/candidates/__init__.py`

**Комментарии / явные подсказки в файле:**
- Common command handlers and fallbacks.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/interview.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~107
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `on_interview_success()` — строка ~22
- `start_test2_callback()` — строка ~91

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/events.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Handlers for interview lifecycle events.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/recruiter.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~37
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `approve()` — строка ~15
- `send_slot_message()` — строка ~20
- `reschedule()` — строка ~25
- `reject()` — строка ~30
- `cmd_iam()` — строка ~35

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Комментарии / явные подсказки в файле:**
- Handlers for recruiter confirmation callbacks.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/recruiter_actions.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~55
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `recruiter_candidate_action()` — строка ~16
- `cmd_inbox()` — строка ~22
- `cmd_find()` — строка ~37

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/services.py`

**Комментарии / явные подсказки в файле:**
- Handlers for recruiter candidate action callbacks and commands.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/slot_assignments.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~25
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `handle_slot_assignment_callback()` — строка ~14
- `handle_slot_assignment_reschedule_choice()` — строка ~21

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Комментарии / явные подсказки в файле:**
- Handlers for slot assignment offer callbacks.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/slots.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~26
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `pick_recruiter()` — строка ~14
- `refresh_slots()` — строка ~19
- `pick_slot()` — строка ~24

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Комментарии / явные подсказки в файле:**
- Handlers for recruiter and slot selection.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/test1.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~16
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `handle_option()` — строка ~14

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Комментарии / явные подсказки в файле:**
- Handlers for Test 1 (mini questionnaire).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/bot/handlers/test2.py`

**Тип:** Роутер/обработчик
**Строк кода:** ~16
**Назначение:** Назначение требует ручного ревью.

**Ключевые функции:**
- `handle_test2()` — строка ~14

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Комментарии / явные подсказки в файле:**
- Handlers for Test 2 multiple choice flow.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

## 3.5 Backend services

### `backend/apps/admin_ui/services/__init__.py`

**Тип:** Сервис
**Строк кода:** ~75
**Назначение:** Сервисный модуль `__init__`.

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/questions.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `backend/apps/admin_ui/services/slots.py`

**Используется в:**
- `tests/services/test_slot_outcome.py`
- `tests/test_admin_slots_api.py`
- `tests/test_chat_messages.py`
- `tests/test_chat_rate_limit.py`
- `tests/test_staff_chat_updates.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/bot_service.py`

**Тип:** Сервис
**Строк кода:** ~553
**Назначение:** Сервисный модуль `bot_service`.

**Классы:**
- `IntegrationSwitch` — строка ~105
- `BotSendResult` — строка ~151
- `BotService` — строка ~162

**Ключевые функции:**
- `_create_null_bot_service()` — строка ~468
- `configure_bot_service()` — строка ~494
- `get_bot_service()` — строка ~501
- `provide_bot_service()` — строка ~522
- `_is_transient_error()` — строка ~548

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/config.py`
- `backend/apps/bot/events.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/dashboard.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/routers/system.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/services/slots/bot.py`
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/recruiter_service.py`
- `tests/services/test_slot_outcome.py`
- `tests/test_admin_candidate_chat_actions.py`
- `tests/test_admin_slots_api.py`
- `tests/test_bot_integration_toggle.py`
- `tests/test_webapp_recruiter.py`

**Комментарии / явные подсказки в файле:**
- Bot client integration helpers for launching Test 2.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/builder_graph.py`

**Тип:** Сервис
**Строк кода:** ~452
**Назначение:** Сервисный модуль `builder_graph`.

**Классы:**
- `_GraphNode` — строка ~114
- `_GraphEdge` — строка ~121

**Ключевые функции:**
- `_graph_key()` — строка ~20
- `_is_xyflow_graph()` — строка ~24
- `_load_test_questions_ids()` — строка ~32
- `get_test_builder_graph()` — строка ~47
- `save_test_builder_graph()` — строка ~88
- `_parse_graph_nodes_edges()` — строка ~128
- `_has_cycle()` — строка ~199
- `validate_test_builder_graph()` — строка ~216
- `extract_question_ids_from_graph()` — строка ~284
- `_compile_linear_question_order()` — строка ~303
- `apply_test_builder_graph()` — строка ~409

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/questions.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/tests/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/content_api.py`
- `backend/apps/admin_ui/services/test_builder_preview.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/calendar_events.py`

**Тип:** Сервис
**Строк кода:** ~419
**Назначение:** Сервисный модуль `calendar_events`.

**Ключевые функции:**
- `_normalize_status()` — строка ~64
- `_get_status_config()` — строка ~72
- `get_calendar_events()` — строка ~86

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/perf/cache/__init__.py`
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Комментарии / явные подсказки в файле:**
- Calendar events service for FullCalendar integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/calendar_tasks.py`

**Тип:** Сервис
**Строк кода:** ~208
**Назначение:** Сервисный модуль `calendar_tasks`.

**Ключевые функции:**
- `_ensure_aware_utc()` — строка ~22
- `_normalize_title()` — строка ~28
- `_normalize_description()` — строка ~35
- `_serialize_task()` — строка ~42
- `_resolve_recruiter_id()` — строка ~58
- `_assert_task_scope()` — строка ~77
- `list_calendar_tasks_for_range()` — строка ~84
- `create_calendar_task()` — строка ~110
- `update_calendar_task()` — строка ~150
- `delete_calendar_task()` — строка ~199

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`
- `backend/core/sanitizers.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/candidate_chat_threads.py`

**Тип:** Сервис
**Строк кода:** ~766
**Назначение:** Сервисный модуль `candidate_chat_threads`.

**Ключевые функции:**
- `_normalize_principal()` — строка ~47
- `_as_utc()` — строка ~53
- `_iso()` — строка ~61
- `_hours_since()` — строка ~66
- `_status_slug()` — строка ~73
- `_is_terminal()` — строка ~81
- `_default_risk_hint()` — строка ~86
- `_priority_payload()` — строка ~109
- `_normalize_ai_fit()` — строка ~163
- `_serialize_workspace()` — строка ~204
- `_recruiter_city_ids()` — строка ~227
- `_is_accessible_user()` — строка ~239
- `_load_accessible_user()` — строка ~261
- `_load_thread_rows()` — строка ~288
- `list_threads()` — строка ~433
- `wait_for_thread_updates()` — строка ~583
- `get_workspace()` — строка ~618
- `update_workspace()` — строка ~637
- `mark_read()` — строка ~685
- `set_archived()` — строка ~720

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/chat_meta.py`
- `backend/core/ai/candidate_scorecard.py`
- `backend/core/db.py`
- `backend/domain/ai/models.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/candidates.py`

**Тип:** Сервис
**Строк кода:** ~3984
**Назначение:** Сервисный модуль `candidates`.

**Классы:**
- `CandidateRow` — строка ~67

**Ключевые функции:**
- `_cohort_stage_key_for_candidate()` — строка ~159
- `_latest_test_result_by_rating()` — строка ~178
- `_intro_day_first_name()` — строка ~196
- `render_intro_day_invitation()` — строка ~205
- `build_intro_day_template_context()` — строка ~259
- `resolve_intro_day_template_source()` — строка ~280
- `get_candidate_actions_for_status()` — строка ~646
- `_has_passed_test2()` — строка ~853
- `_build_field_types()` — строка ~865
- `_ensure_aware()` — строка ~875
- `_serialize_answer()` — строка ~883
- `_serialize_interview_note()` — строка ~896
- `_latest_test2_sent()` — строка ~912
- `_resolve_telemost_url()` — строка ~922
- `_status_labels()` — строка ~949
- `_status_label()` — строка ~958
- `_status_icon()` — строка ~962
- `_status_tone()` — строка ~966
- `_build_pipeline_stages()` — строка ~1000
- `_map_to_workflow_status()` — строка ~1100
- `_workflow_actions_ui()` — строка ~1123
- `_build_test_sections()` — строка ~1159
- `_stage_label()` — строка ~1289
- `_distinct_ratings()` — строка ~1305
- `_distinct_cities()` — строка ~1312

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/reschedule_intents.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/timezones.py`
- `backend/apps/admin_ui/utils.py`
- `backend/apps/bot/config.py`
- `backend/apps/bot/services.py`
- `backend/core/ai/service.py`
- `backend/core/audit.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/ai/models.py`
- `backend/domain/candidate_status_service.py`
- `backend/domain/candidates/actions.py`
- `backend/domain/candidates/journey.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/services.py`
- `backend/domain/candidates/status.py`
- `backend/domain/candidates/status_service.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/services/__init__.py`
- `tests/test_admin_candidates_service.py`
- `tests/test_candidate_lead_and_invite.py`
- `tests/test_candidate_rejection_reason.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/chat.py`

**Тип:** Сервис
**Строк кода:** ~500
**Назначение:** Сервисный модуль `chat`.

**Ключевые функции:**
- `get_chat_templates()` — строка ~78
- `_chat_rate_limit_key()` — строка ~82
- `_clear_rate_limit_state()` — строка ~86
- `_get_rate_limit_redis_client()` — строка ~94
- `_check_rate_limit()` — строка ~126
- `_record_message_sent()` — строка ~145
- `_check_rate_limit_async()` — строка ~151
- `_record_message_sent_async()` — строка ~173
- `_delivery_stage()` — строка ~193
- `serialize_chat_message()` — строка ~204
- `list_chat_history()` — строка ~225
- `_latest_chat_message_at()` — строка ~238
- `wait_for_chat_history_updates()` — строка ~252
- `_load_candidate()` — строка ~278
- `_existing_message()` — строка ~290
- `send_chat_message()` — строка ~308
- `_resolve_recruiter_link()` — строка ~396
- `_fill_dynamic_fields()` — строка ~417
- `_fetch_message_by_id()` — строка ~426
- `retry_chat_message()` — строка ~434

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/chat_meta.py`
- `backend/core/db.py`
- `backend/core/redis_factory.py`
- `backend/core/settings.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/services.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/bot/recruiter_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/chat_meta.py`

**Тип:** Сервис
**Строк кода:** ~53
**Назначение:** Сервисный модуль `chat_meta`.

**Ключевые функции:**
- `derive_chat_message_kind()` — строка ~18
- `compact_chat_preview()` — строка ~46

**Зависимости (локальные импорты):**
- `backend/domain/candidates/models.py`

**Используется в:**
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/chat.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/cities.py`

**Тип:** Сервис
**Строк кода:** ~544
**Назначение:** Сервисный модуль `cities`.

**Ключевые функции:**
- `_clean_expert_name()` — строка ~41
- `parse_experts_text()` — строка ~46
- `city_experts_items()` — строка ~65
- `_sync_city_experts_from_items()` — строка ~87
- `_sync_city_experts_from_text()` — строка ~152
- `list_cities()` — строка ~157
- `get_city()` — строка ~185
- `normalize_city_timezone()` — строка ~214
- `create_city()` — строка ~227
- `update_city_settings()` — строка ~261
- `update_city_owner()` — строка ~363
- `set_city_active()` — строка ~389
- `delete_city()` — строка ~404
- `api_cities_payload()` — строка ~418
- `api_city_owners_payload()` — строка ~456
- `_primary_recruiter()` — строка ~472
- `get_city_capacity()` — строка ~481

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/ai/service.py`
- `backend/core/cache.py`
- `backend/core/db.py`
- `backend/core/sanitizers.py`
- `backend/domain/cities/models.py`
- `backend/domain/errors.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/cities.py`
- `backend/apps/admin_ui/routers/directory.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/services/__init__.py`
- `tests/test_city_experts_sync.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/cities_hh.py`

**Тип:** Сервис
**Строк кода:** ~384
**Назначение:** Сервисный модуль `cities_hh`.

**Ключевые функции:**
- `_string()` — строка ~22
- `_normalized_city_names()` — строка ~27
- `_binding_area_name()` — строка ~35
- `_binding_title()` — строка ~44
- `_live_vacancy_area_names()` — строка ~54
- `_vacancy_publication_status()` — строка ~64
- `_load_active_hh_vacancies()` — строка ~88
- `_load_active_hh_vacancies_for_city()` — строка ~147
- `get_city_hh_vacancy_statuses()` — строка ~206

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/domain/hh_integration/__init__.py`
- `backend/domain/hh_integration/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/directory.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/city_reminder_policy.py`

**Тип:** Сервис
**Строк кода:** ~115
**Назначение:** Сервисный модуль `city_reminder_policy`.

**Классы:**
- `ReminderPolicyData` — строка ~19

**Ключевые функции:**
- `get_city_reminder_policy()` — строка ~42
- `upsert_city_reminder_policy()` — строка ~62
- `delete_city_reminder_policy()` — строка ~104

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/directory.py`
- `backend/apps/bot/reminders.py`
- `tests/test_city_reminder_policy.py`

**Комментарии / явные подсказки в файле:**
- Per-city reminder policy service.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/dashboard.py`

**Тип:** Сервис
**Строк кода:** ~2292
**Назначение:** Сервисный модуль `dashboard`.

**Классы:**
- `SmartCreateError` — строка ~153

**Ключевые функции:**
- `normalize_waiting_candidates_limit()` — строка ~145
- `format_dashboard_candidate()` — строка ~157
- `_format_waiting_window()` — строка ~180
- `dashboard_counts()` — строка ~201
- `get_recent_candidates()` — строка ~270
- `get_waiting_candidates()` — строка ~287
- `_format_delta()` — строка ~644
- `get_upcoming_interviews()` — строка ~667
- `get_quick_slots()` — строка ~765
- `get_hiring_funnel_stats()` — строка ~803
- `_normalize_funnel_range()` — строка ~896
- `_clean_filter_value()` — строка ~914
- `_apply_funnel_filters()` — строка ~921
- `_subject_key()` — строка ~937
- `_fetch_funnel_events()` — строка ~945
- `_collect_event_stats()` — строка ~979
- `_avg_time_between()` — строка ~1003
- `_percentile()` — строка ~1032
- `_time_deltas_between()` — строка ~1048
- `_step_counts_from_sets()` — строка ~1075
- `get_bot_funnel_stats()` — строка ~1085
- `get_pipeline_snapshot()` — строка ~1421
- `get_funnel_step_candidates()` — строка ~1500
- `get_recruiter_performance()` — строка ~1708
- `_normalize_score()` — строка ~1802

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/perf/cache/__init__.py`
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/reschedule_intents.py`
- `backend/apps/admin_ui/timezones.py`
- `backend/apps/admin_ui/utils.py`
- `backend/apps/bot/metrics.py`
- `backend/core/ai/candidate_scorecard.py`
- `backend/core/ai/service.py`
- `backend/core/cache.py`
- `backend/core/db.py`
- `backend/core/scoping.py`
- `backend/domain/ai/models.py`
- `backend/domain/analytics.py`
- `backend/domain/analytics_models.py`
- `backend/domain/candidate_status_service.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/routers/ai.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/dashboard.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/services/__init__.py`
- `backend/apps/bot/recruiter_service.py`
- `backend/apps/bot/services.py`
- `tests/services/test_dashboard_and_slots.py`
- `tests/services/test_dashboard_funnel.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/dashboard_calendar.py`

**Тип:** Сервис
**Строк кода:** ~208
**Назначение:** Сервисный модуль `dashboard_calendar`.

**Ключевые функции:**
- `_normalize_status()` — строка ~34
- `_selected_label()` — строка ~40
- `dashboard_calendar_snapshot()` — строка ~48

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/dashboard.py`
- `tests/services/test_dashboard_calendar.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/detailization.py`

**Тип:** Сервис
**Строк кода:** ~597
**Назначение:** Сервисный модуль `detailization`.

**Классы:**
- `DetailizationItem` — строка ~114

**Ключевые функции:**
- `_normalize_text()` — строка ~36
- `_exclude_reason()` — строка ~40
- `_derive_is_attached()` — строка ~60
- `_derive_final_outcome_reason()` — строка ~75
- `_derive_final_outcome()` — строка ~87
- `_outcome_from_is_attached()` — строка ~96
- `_is_attached_from_outcome()` — строка ~104
- `_summary_outcome_bucket()` — строка ~130
- `_build_summary()` — строка ~141
- `_parse_datetime_utc()` — строка ~199
- `_ensure_auto_rows()` — строка ~222
- `list_detailization()` — строка ~338
- `export_detailization_csv()` — строка ~421
- `update_detailization_entry()` — строка ~467
- `create_manual_detailization_entry()` — строка ~528
- `delete_detailization_entry()` — строка ~580

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/domain/candidates/journey.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/detailization/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/detailization.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/kpis.py`

**Тип:** Сервис
**Строк кода:** ~739
**Назначение:** Сервисный модуль `kpis`.

**Классы:**
- `WeekWindow` — строка ~50
- `WeeklySnapshot` — строка ~60

**Ключевые функции:**
- `_ensure_kpi_model()` — строка ~110
- `_normalize_timezone_name()` — строка ~115
- `_resolve_timezone()` — строка ~123
- `_ensure_aware()` — строка ~132
- `get_week_window()` — строка ~138
- `_window_for_week_start()` — строка ~159
- `_query_metrics()` — строка ~172
- `_format_event()` — строка ~247
- `_safe_zone()` — строка ~255
- `_test_details()` — строка ~266
- `_slot_details()` — строка ~311
- `_collect_details()` — строка ~388
- `_trend()` — строка ~444
- `_trend_info()` — строка ~453
- `_serialize_cards()` — строка ~484
- `_load_previous_metrics()` — строка ~509
- `_week_label()` — строка ~539
- `_current_time()` — строка ~544
- `_compute_payload()` — строка ~556
- `get_weekly_kpis()` — строка ~607
- `_set_cache()` — строка ~649
- `list_weekly_history()` — строка ~664
- `compute_weekly_snapshot()` — строка ~693
- `store_weekly_snapshot()` — строка ~709
- `reset_weekly_cache()` — строка ~736

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/dashboard.py`
- `tests/services/test_weekly_kpis.py`
- `tools/recompute_weekly_kpis.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/max_sales_handoff.py`

**Тип:** Сервис
**Строк кода:** ~323
**Назначение:** Сервисный модуль `max_sales_handoff`.

**Классы:**
- `IntroDayHandoffContext` — строка ~20
- `_RouteConfig` — строка ~35

**Ключевые функции:**
- `_is_enabled()` — строка ~42
- `_normalize_targets()` — строка ~49
- `_parse_routes()` — строка ~73
- `_resolve_targets()` — строка ~136
- `_format_slot_local()` — строка ~167
- `_build_message()` — строка ~178
- `_ensure_max_adapter()` — строка ~199
- `dispatch_intro_day_handoff_to_max()` — строка ~227

**Зависимости (локальные импорты):**
- `backend/core/messenger/bootstrap.py`
- `backend/core/messenger/protocol.py`
- `backend/core/messenger/registry.py`
- `backend/core/settings.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `tests/test_max_sales_handoff.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/message_templates.py`

**Тип:** Сервис
**Строк кода:** ~878
**Назначение:** Сервисный модуль `message_templates`.

**Классы:**
- `MessageTemplateSummary` — строка ~193
- `_TelegramHTMLValidator` — строка ~746

**Ключевые функции:**
- `_is_intro_template()` — строка ~104
- `_compose_intro_contact()` — строка ~110
- `build_preview_context()` — строка ~122
- `render_message_template_preview()` — строка ~180
- `_infer_stage()` — строка ~211
- `_preview_text()` — строка ~224
- `_coverage_gaps()` — строка ~231
- `list_message_templates()` — строка ~264
- `get_message_template()` — строка ~426
- `get_template_history()` — строка ~431
- `create_message_template()` — строка ~442
- `update_message_template()` — строка ~583
- `delete_message_template()` — строка ~712
- `_invalidate_cache()` — строка ~730
- `_validate_template_markup()` — строка ~793
- `_find_unknown_placeholders()` — строка ~803
- `_normalize_actor()` — строка ~809
- `_append_history()` — строка ~818
- `set_active_state()` — строка ~836

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates_presets.py`
- `backend/apps/bot/services.py`
- `backend/core/content_updates.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/models.py`
- `backend/utils/jinja_renderer.py`

**Используется в:**
- `backend/apps/admin_ui/routers/cities.py`
- `backend/apps/admin_ui/routers/content_api.py`
- `backend/apps/admin_ui/routers/message_templates.py`
- `scripts/update_notification_templates.py`
- `tests/reproduce_issue_1.py`
- `tests/test_admin_message_templates.py`
- `tests/test_admin_message_templates_sms.py`
- `tests/test_admin_message_templates_update.py`
- `tests/test_e2e_notification_flow.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/message_templates_presets.py`

**Тип:** Сервис
**Строк кода:** ~58
**Назначение:** Сервисный модуль `message_templates_presets`.

**Ключевые функции:**
- `list_known_template_keys()` — строка ~31
- `known_template_presets()` — строка ~37

**Зависимости (локальные импорты):**
- `backend/apps/bot/defaults.py`
- `backend/domain/template_stages.py`

**Используется в:**
- `backend/apps/admin_ui/routers/content_api.py`
- `backend/apps/admin_ui/services/message_templates.py`
- `tests/test_admin_template_keys.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/notifications.py`

**Тип:** Сервис
**Строк кода:** ~42
**Назначение:** Сервисный модуль `notifications`.

**Ключевые функции:**
- `notification_feed()` — строка ~11

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Используется в:**
- `tests/test_admin_notifications_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/notifications_ops.py`

**Тип:** Сервис
**Строк кода:** ~177
**Назначение:** Сервисный модуль `notifications_ops`.

**Ключевые функции:**
- `_normalize_filter()` — строка ~19
- `list_outbox_notifications()` — строка ~26
- `list_notification_logs()` — строка ~85
- `retry_outbox_notification()` — строка ~147
- `cancel_outbox_notification()` — строка ~159

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/questions.py`

**Тип:** Сервис
**Строк кода:** ~523
**Назначение:** Сервисный модуль `questions`.

**Классы:**
- `QuestionRecord` — строка ~35

**Ключевые функции:**
- `_parse_question_payload()` — строка ~43
- `_question_kind()` — строка ~53
- `_sorted_options()` — строка ~57
- `_correct_option_label()` — строка ~64
- `_payload_from_question()` — строка ~71
- `_ensure_test()` — строка ~91
- `list_test_questions()` — строка ~101
- `get_test_question_detail()` — строка ~160
- `_normalize_payload_fields()` — строка ~188
- `update_test_question()` — строка ~226
- `create_test_question()` — строка ~314
- `clone_test_question()` — строка ~405
- `reorder_test_questions()` — строка ~465

**Зависимости (локальные импорты):**
- `backend/core/content_updates.py`
- `backend/core/db.py`
- `backend/domain/tests/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/content_api.py`
- `backend/apps/admin_ui/services/__init__.py`
- `backend/apps/admin_ui/services/builder_graph.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/recruiter_access.py`

**Тип:** Сервис
**Строк кода:** ~99
**Назначение:** Сервисный модуль `recruiter_access`.

**Ключевые функции:**
- `_recruiter_can_access_city()` — строка ~14
- `recruiter_can_access_candidate()` — строка ~33
- `get_candidate_for_recruiter()` — строка ~74

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/bot/recruiter_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/recruiter_plan.py`

**Тип:** Сервис
**Строк кода:** ~122
**Назначение:** Сервисный модуль `recruiter_plan`.

**Ключевые функции:**
- `get_recruiter_plan()` — строка ~14
- `add_recruiter_plan_entry()` — строка ~73
- `delete_recruiter_plan_entry()` — строка ~109

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/core/sanitizers.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/recruiters.py`

**Тип:** Сервис
**Строк кода:** ~524
**Назначение:** Сервисный модуль `recruiters`.

**Классы:**
- `RecruiterValidationError` — строка ~507

**Ключевые функции:**
- `list_recruiters()` — строка ~38
- `create_recruiter()` — строка ~140
- `reset_recruiter_password()` — строка ~218
- `get_recruiter_detail()` — строка ~266
- `update_recruiter()` — строка ~285
- `delete_recruiter()` — строка ~343
- `build_recruiter_payload()` — строка ~363
- `_pick_field()` — строка ~408
- `_integrity_error_payload()` — строка ~415
- `_parse_city_ids()` — строка ~429
- `api_recruiters_payload()` — строка ~448
- `api_get_recruiter()` — строка ~487
- `_is_valid_url()` — строка ~513

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/utils.py`
- `backend/core/audit.py`
- `backend/core/db.py`
- `backend/core/passwords.py`
- `backend/core/sanitizers.py`
- `backend/domain/auth_account.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/cities.py`
- `backend/apps/admin_ui/routers/directory.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/services/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/reminders_ops.py`

**Тип:** Сервис
**Строк кода:** ~67
**Назначение:** Сервисный модуль `reminders_ops`.

**Ключевые функции:**
- `_normalize_filter()` — строка ~14
- `list_reminder_jobs()` — строка ~21

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/reschedule_intents.py`

**Тип:** Сервис
**Строк кода:** ~219
**Назначение:** Сервисный модуль `reschedule_intents`.

**Классы:**
- `RescheduleIntent` — строка ~29

**Ключевые функции:**
- `get_reschedule_intent_map()` — строка ~39
- `get_bot_state_reschedule_intent()` — строка ~126
- `get_candidate_reschedule_intent()` — строка ~195

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/domain/candidates/journey.py`
- `tests/services/test_dashboard_and_slots.py`
- `tests/test_admin_candidates_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/slots.py`

**Тип:** Сервис
**Строк кода:** ~2041
**Назначение:** Сервисный модуль `slots`.

**Классы:**
- `ManualSlotError` — строка ~117
- `BotDispatchPlan` — строка ~1219
- `BotDispatch` — строка ~1234

**Ключевые функции:**
- `_resolve_hook()` — строка ~73
- `_ensure_recruiter_city_link()` — строка ~121
- `_notification_feedback()` — строка ~128
- `get_state_manager()` — строка ~157
- `generate_default_day_slots()` — строка ~163
- `list_slots()` — строка ~279
- `recruiters_for_slot_form()` — строка ~433
- `create_slot()` — строка ~461
- `delete_slot()` — строка ~560
- `delete_all_slots()` — строка ~604
- `delete_past_free_slots()` — строка ~669
- `_reservation_error_message()` — строка ~724
- `_log_manual_slot_assignment()` — строка ~735
- `schedule_manual_candidate_slot()` — строка ~779
- `schedule_manual_candidate_slot_silent()` — строка ~938
- `_finalize_manual_silent_booking()` — строка ~1056
- `assign_existing_candidate_slot_silent()` — строка ~1155
- `set_slot_outcome()` — строка ~1239
- `_plan_test2_dispatch()` — строка ~1318
- `_plan_rejection_dispatch()` — строка ~1348
- `_format_outcome_message()` — строка ~1384
- `execute_bot_dispatch()` — строка ~1409
- `_map_test2_status()` — строка ~1462
- `_mark_dispatch_state()` — строка ~1468
- `_hydrate_slot_candidate_binding()` — строка ~1481

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/utils.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services.py`
- `backend/core/audit.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/core/time_utils.py`
- `backend/domain/candidate_status_service.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/errors.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`
- `backend/domain/slot_assignment_service.py`
- `backend/domain/slot_service.py`

**Используется в:**
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/services/__init__.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/slots/__init__.py`
- `tests/services/test_dashboard_and_slots.py`
- `tests/services/test_slots_delete.py`
- `tests/test_bulk_slots_timezone_moscow_novosibirsk.py`
- `tests/test_delete_past_free_slots.py`
- `tests/test_manual_slot_assignment.py`
- `tests/test_recruiter_timezone_conversion.py`
- `tests/test_slot_cleanup_strict.py`
- `tests/test_slot_creation_timezone_validation.py`
- `tests/test_slot_overlap_handling.py`
- `tests/test_slot_past_validation.py`
- `tests/test_slot_timezone_moscow_novosibirsk.py`
- `tests/test_slot_timezones.py`
- `tests/test_slots_generation.py`
- `tests/test_slots_timezone_handling.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/slots/__init__.py`

**Тип:** Сервис
**Строк кода:** ~9
**Назначение:** Сервисный модуль `__init__`.

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/services/slots/core.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/slots/bot.py`

**Тип:** Сервис
**Строк кода:** ~522
**Назначение:** Сервисный модуль `bot`.

**Классы:**
- `BotDispatchPlan` — строка ~43
- `BotDispatch` — строка ~58

**Ключевые функции:**
- `get_state_manager()` — строка ~63
- `set_slot_outcome()` — строка ~69
- `_plan_test2_dispatch()` — строка ~139
- `_plan_rejection_dispatch()` — строка ~169
- `_format_outcome_message()` — строка ~206
- `execute_bot_dispatch()` — строка ~231
- `_map_test2_status()` — строка ~300
- `_mark_dispatch_state()` — строка ~306
- `_trigger_test2()` — строка ~319
- `reschedule_slot_booking()` — строка ~355
- `approve_slot_booking()` — строка ~397
- `reject_slot_booking()` — строка ~452
- `_trigger_rejection()` — строка ~494

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_ui/routers/slots.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/slots/bulk.py`

**Тип:** Сервис
**Строк кода:** ~164
**Назначение:** Сервисный модуль `bulk`.

**Ключевые функции:**
- `_normalize_utc()` — строка ~15
- `_as_utc()` — строка ~23
- `bulk_create_slots()` — строка ~31

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/slots/core.py`

**Тип:** Сервис
**Строк кода:** ~135
**Назначение:** Сервисный модуль `core`.

**Ключевые функции:**
- `_load_module()` — строка ~20
- `_collect_exports()` — строка ~36
- `bulk_assign_slots()` — строка ~55
- `bulk_schedule_reminders()` — строка ~73
- `bulk_delete_slots()` — строка ~102

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/services/slots/__init__.py`
- `tests/services/test_slots_bulk.py`

**Комментарии / явные подсказки в файле:**
- Compatibility bridge to the legacy slots module.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/slots/crud.py`

**Тип:** Сервис
**Строк кода:** ~525
**Назначение:** Сервисный модуль `crud`.

**Ключевые функции:**
- `list_slots()` — строка ~37
- `recruiters_for_slot_form()` — строка ~89
- `create_slot()` — строка ~118
- `delete_slot()` — строка ~164
- `delete_all_slots()` — строка ~191
- `_ensure_utc()` — строка ~240
- `_slot_local_time()` — строка ~247
- `api_slots_payload()` — строка ~262

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/utils.py`
- `backend/apps/bot/reminders.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/staff_chat.py`

**Тип:** Сервис
**Строк кода:** ~1129
**Назначение:** Сервисный модуль `staff_chat`.

**Ключевые функции:**
- `_principal_label()` — строка ~44
- `_load_recruiter()` — строка ~52
- `_member_filter()` — строка ~60
- `_member_key()` — строка ~72
- `_merge_read_map()` — строка ~78
- `_format_member_label()` — строка ~92
- `_format_candidate_card()` — строка ~96
- `_serialize_member()` — строка ~114
- `_serialize_message()` — строка ~126
- `_ensure_member()` — строка ~185
- `_ensure_default_threads()` — строка ~202
- `list_threads()` — строка ~313
- `create_or_get_direct_thread()` — строка ~426
- `create_group_thread()` — строка ~494
- `list_messages()` — строка ~524
- `_store_attachment()` — строка ~616
- `send_message()` — строка ~645
- `get_message_payload()` — строка ~712
- `list_thread_members()` — строка ~774
- `add_thread_members()` — строка ~790
- `remove_thread_member()` — строка ~817
- `_as_utc()` — строка ~831
- `wait_for_thread_updates()` — строка ~839
- `wait_for_message_updates()` — строка ~863
- `send_candidate_task()` — строка ~983

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/audit.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/test_builder_preview.py`

**Тип:** Сервис
**Строк кода:** ~569
**Назначение:** Сервисный модуль `test_builder_preview`.

**Классы:**
- `_NodeInfo` — строка ~18
- `_EdgeRule` — строка ~26

**Ключевые функции:**
- `_sorted_options()` — строка ~41
- `_question_to_payload()` — строка ~48
- `_virtual_question_to_payload()` — строка ~74
- `_template_text()` — строка ~93
- `_validation_feedback()` — строка ~99
- `_parse_graph_runtime()` — строка ~120
- `_load_db_questions()` — строка ~240
- `_edge_matches()` — строка ~271
- `_pick_edge()` — строка ~285
- `_question_payload_for_node()` — строка ~308
- `preview_test_builder_graph()` — строка ~320

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/builder_graph.py`
- `backend/apps/bot/defaults.py`
- `backend/apps/bot/test1_validation.py`
- `backend/core/db.py`
- `backend/domain/tests/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/content_api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/apps/admin_ui/services/vacancies.py`

**Тип:** Сервис
**Строк кода:** ~257
**Назначение:** Сервисный модуль `vacancies`.

**Классы:**
- `VacancySummary` — строка ~23

**Ключевые функции:**
- `list_vacancies()` — строка ~37
- `get_vacancy()` — строка ~85
- `_validate_vacancy_fields()` — строка ~90
- `create_vacancy()` — строка ~105
- `update_vacancy()` — строка ~135
- `delete_vacancy()` — строка ~174
- `get_vacancy_questions()` — строка ~185
- `resolve_questions_for_city()` — строка ~201

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `tests/test_vacancy_api.py`
- `tests/test_vacancy_service.py`

**Комментарии / явные подсказки в файле:**
- Vacancy CRUD service — manages named question-sets for Test1/Test2.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

## 3.6 Backend core / domain / repositories

### `backend/core/__init__.py`

**Тип:** Core-модуль
**Строк кода:** ~0
**Назначение:** Core-инфраструктура `__init__`.

**Используется в:**
- `scripts/formal_gate_sprint12.py`
- `tests/conftest.py`
- `tests/test_admin_auth_form_admin_env.py`
- `tests/test_admin_auth_no_basic_challenge.py`
- `tests/test_admin_candidate_chat_actions.py`
- `tests/test_admin_candidate_schedule_slot.py`
- `tests/test_admin_candidate_status_update.py`
- `tests/test_admin_notifications_feed_api.py`
- `tests/test_admin_slots_api.py`
- `tests/test_admin_surface_hardening.py`
- `tests/test_admin_ui_auth_startup.py`
- `tests/test_ai_copilot.py`
- `tests/test_bot_integration_toggle.py`
- `tests/test_bot_reminder_jobs_api.py`
- `tests/test_candidate_chat_threads_api.py`
- `tests/test_city_hh_vacancies_api.py`
- `tests/test_hh_integration_actions.py`
- `tests/test_hh_integration_foundation.py`
- `tests/test_hh_integration_import.py`
- `tests/test_hh_integration_jobs.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/__init__.py`

**Тип:** Core-модуль
**Строк кода:** ~11
**Назначение:** Core-инфраструктура `__init__`.

**Зависимости (локальные импорты):**
- `backend/core/ai/service.py`

**Комментарии / явные подсказки в файле:**
- AI Copilot subsystem (LLM integration).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/candidate_scorecard.py`

**Тип:** Core-модуль
**Строк кода:** ~600
**Назначение:** Core-инфраструктура `candidate_scorecard`.

**Классы:**
- `ScorecardState` — строка ~133

**Ключевые функции:**
- `fit_level_from_score()` — строка ~143
- `_points_for_status()` — строка ~156
- `_normalize_text()` — строка ~164
- `_has_any()` — строка ~169
- `_classify_field_format_answer()` — строка ~173
- `_append_missing()` — строка ~186
- `_append_blocker()` — строка ~192
- `_objective_metric()` — строка ~198
- `_semantic_metric()` — строка ~215
- `_parse_semantic_metric()` — строка ~234
- `_normalize_flag_items()` — строка ~260
- `_dedupe_flag_items()` — строка ~280
- `build_candidate_scorecard()` — строка ~296

**Используется в:**
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/core/ai/service.py`
- `tests/test_ai_copilot.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/context.py`

**Тип:** Core-модуль
**Строк кода:** ~790
**Назначение:** Core-инфраструктура `context`.

**Ключевые функции:**
- `compute_input_hash()` — строка ~39
- `_iso()` — строка ~44
- `_parse_int()` — строка ~52
- `_derive_candidate_signals()` — строка ~65
- `_ensure_candidate_scope()` — строка ~150
- `build_candidate_ai_context()` — строка ~174
- `_attach_kb_excerpts()` — строка ~627
- `build_city_candidate_recommendations_context()` — строка ~649
- `get_last_inbound_message_text()` — строка ~771

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/ai/knowledge_base.py`
- `backend/core/ai/redaction.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/core/ai/service.py`
- `tests/test_ai_copilot.py`

**Комментарии / явные подсказки в файле:**
- AI context builders — assemble anonymized data for AI prompts.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/interview_script_builder.py`

**Тип:** Core-модуль
**Строк кода:** ~259
**Назначение:** Core-инфраструктура `interview_script_builder`.

**Ключевые функции:**
- `_shorten()` — строка ~6
- `_first_name()` — строка ~13
- `_question_score()` — строка ~18
- `_personalized_question_text()` — строка ~33
- `_personalized_question_why()` — строка ~49
- `_good_answer()` — строка ~58
- `_red_flags()` — строка ~67
- `_build_focus_areas()` — строка ~74
- `_build_key_flags()` — строка ~106
- `build_structured_interview_script()` — строка ~134

**Используется в:**
- `backend/core/ai/service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/knowledge_base.py`

**Тип:** Core-модуль
**Строк кода:** ~323
**Назначение:** Core-инфраструктура `knowledge_base`.

**Ключевые функции:**
- `_sha256()` — строка ~62
- `_clean_text()` — строка ~66
- `_iso()` — строка ~70
- `chunk_text()` — строка ~81
- `extract_query_tokens()` — строка ~107
- `reindex_document()` — строка ~124
- `_candidate_chunks_for_terms()` — строка ~153
- `_rank_chunks()` — строка ~187
- `search_excerpts()` — строка ~218
- `list_active_documents()` — строка ~277
- `kb_state_snapshot()` — строка ~305

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/ai/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/knowledge_base.py`
- `backend/core/ai/context.py`
- `backend/core/ai/service.py`
- `tests/test_kb_active_documents_list.py`

**Комментарии / явные подсказки в файле:**
- Knowledge Base chunking, indexing, and search.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/llm_script_generator.py`

**Тип:** Core-модуль
**Строк кода:** ~1107
**Назначение:** Core-инфраструктура `llm_script_generator`.

**Классы:**
- `ScriptGenerationResult` — строка ~539

**Ключевые функции:**
- `derive_stage_strategy()` — строка ~107
- `interview_script_json_schema()` — строка ~160
- `hash_resume_content()` — строка ~280
- `_extract_total_exp_years()` — строка ~290
- `normalize_hh_resume()` — строка ~303
- `income_mismatch()` — строка ~397
- `schedule_mismatch()` — строка ~420
- `dedupe_and_sort()` — строка ~432
- `build_base_risk_flags()` — строка ~442
- `_build_clarifying_question()` — строка ~472
- `_build_recommended_phrase()` — строка ~484
- `merge_with_llm_flags()` — строка ~496
- `_normalize_script_block()` — строка ~544
- `_clean_sentence()` — строка ~568
- `_sanitize_conversation_script()` — строка ~573
- `_looks_fragmented_conversation()` — строка ~615
- `_conversation_paragraph_from_block()` — строка ~627
- `_compose_conversation_script()` — строка ~647
- `_normalize_script_payload()` — строка ~729
- `build_interview_script_fallback()` — строка ~814
- `generate_interview_script()` — строка ~1024

**Зависимости (локальные импорты):**
- `backend/core/ai/prompts.py`
- `backend/core/ai/providers/base.py`
- `backend/core/ai/schemas.py`

**Используется в:**
- `backend/apps/admin_ui/routers/knowledge_base.py`
- `backend/core/ai/service.py`
- `tests/test_interview_script_ai.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/prompts.py`

**Тип:** Core-модуль
**Строк кода:** ~423
**Назначение:** Core-инфраструктура `prompts`.

**Ключевые функции:**
- `_json_block()` — строка ~22
- `_pii_rule()` — строка ~27
- `_smart_service_script_excerpt()` — строка ~37
- `_smart_service_script_exemplar_excerpt()` — строка ~52
- `_style_guide_excerpt()` — строка ~64
- `candidate_summary_prompts()` — строка ~76
- `candidate_coach_prompts()` — строка ~142
- `interview_script_prompts()` — строка ~182
- `candidate_coach_drafts_prompts()` — строка ~271
- `chat_reply_drafts_prompts()` — строка ~302
- `dashboard_insight_prompts()` — строка ~344
- `city_candidate_recommendations_prompts()` — строка ~367
- `agent_chat_reply_prompts()` — строка ~393

**Используется в:**
- `backend/core/ai/llm_script_generator.py`
- `backend/core/ai/service.py`

**Комментарии / явные подсказки в файле:**
- AI prompt templates for all LLM-powered features.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/providers/__init__.py`

**Тип:** Core-модуль
**Строк кода:** ~14
**Назначение:** Core-инфраструктура `__init__`.

**Зависимости (локальные импорты):**
- `backend/core/ai/providers/base.py`
- `backend/core/ai/providers/fake.py`
- `backend/core/ai/providers/openai.py`

**Используется в:**
- `backend/core/ai/service.py`

**Комментарии / явные подсказки в файле:**
- AI provider implementations (pluggable LLM backends).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/providers/base.py`

**Тип:** Core-модуль
**Строк кода:** ~34
**Назначение:** Core-инфраструктура `base`.

**Классы:**
- `AIProviderError` — строка ~7
- `Usage` — строка ~12
- `AIProvider` — строка ~17

**Используется в:**
- `backend/core/ai/llm_script_generator.py`
- `backend/core/ai/providers/__init__.py`
- `backend/core/ai/providers/fake.py`
- `backend/core/ai/providers/openai.py`
- `tests/test_interview_script_ai.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/providers/fake.py`

**Тип:** Core-модуль
**Строк кода:** ~341
**Назначение:** Core-инфраструктура `fake`.

**Классы:**
- `FakeProvider` — строка ~9

**Зависимости (локальные импорты):**
- `backend/core/ai/providers/base.py`

**Используется в:**
- `backend/core/ai/providers/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/providers/openai.py`

**Тип:** Core-модуль
**Строк кода:** ~273
**Назначение:** Core-инфраструктура `openai`.

**Классы:**
- `OpenAIProvider` — строка ~97

**Ключевые функции:**
- `_extract_json()` — строка ~20
- `_should_use_responses_api()` — строка ~30
- `_token_param_name_for_model()` — строка ~42
- `_supports_temperature()` — строка ~56
- `_extract_text_from_responses()` — строка ~64

**Зависимости (локальные импорты):**
- `backend/core/ai/providers/base.py`
- `backend/core/settings.py`

**Используется в:**
- `backend/core/ai/providers/__init__.py`
- `tests/test_openai_provider_params.py`
- `tests/test_openai_provider_responses_api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/redaction.py`

**Тип:** Core-модуль
**Строк кода:** ~107
**Назначение:** Core-инфраструктура `redaction`.

**Классы:**
- `RedactionResult` — строка ~31

**Ключевые функции:**
- `_replace_known_name()` — строка ~39
- `redact_text()` — строка ~60

**Используется в:**
- `backend/core/ai/context.py`
- `backend/core/ai/service.py`
- `scripts/export_interview_script_dataset.py`
- `tests/test_ai_copilot.py`

**Комментарии / явные подсказки в файле:**
- PII redaction utilities for AI prompts.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/schemas.py`

**Тип:** Core-модуль
**Строк кода:** ~352
**Назначение:** Core-инфраструктура `schemas`.

**Классы:**
- `RiskItem` — строка ~28
- `NextActionItem` — строка ~37
- `FitAssessment` — строка ~46
- `EvidenceItem` — строка ~55
- `CriterionChecklistItem` — строка ~63
- `ScorecardMetricItem` — строка ~72
- `ScorecardFlagItem` — строка ~81
- `CandidateScorecard` — строка ~87
- `VacancyFitEvidence` — строка ~101
- `VacancyFit` — строка ~109
- `CandidateSummaryV1` — строка ~119
- `DraftItem` — строка ~139
- `ChatReplyDraftsV1` — строка ~146
- `DashboardInsightV1` — строка ~157
- `CandidateRecommendationItem` — строка ~168
- `CityCandidateRecommendationsV1` — строка ~178
- `KBSourceItem` — строка ~189
- `AgentChatReplyV1` — строка ~197
- `CandidateCoachV1` — строка ~209
- `InterviewScriptIfAnswer` — строка ~221

**Используется в:**
- `backend/core/ai/llm_script_generator.py`
- `backend/core/ai/service.py`

**Комментарии / явные подсказки в файле:**
- Pydantic schemas for AI provider JSON responses.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/ai/service.py`

**Тип:** Core-модуль
**Строк кода:** ~2478
**Назначение:** Core-инфраструктура `service`.

**Классы:**
- `AIDisabledError` — строка ~91
- `AIRateLimitedError` — строка ~95
- `AIResult` — строка ~100
- `AIService` — строка ~890

**Ключевые функции:**
- `_iso()` — строка ~108
- `_provider_for_settings()` — строка ~119
- `_count_today_requests()` — строка ~128
- `_estimate_today_spend_usd()` — строка ~144
- `_log_request()` — строка ~169
- `_get_cached_output()` — строка ~204
- `_store_output()` — строка ~229
- `_normalized_resume_context()` — строка ~287
- `_scorecard_payload()` — строка ~304
- `_criteria_used_from_context()` — строка ~316
- `_scorecard_fit_rationale()` — строка ~322
- `_apply_candidate_summary_scorecard()` — строка ~341
- `_apply_candidate_coach_score()` — строка ~383
- `_scorecard_risk_items()` — строка ~401
- `_summary_tldr_from_scorecard()` — строка ~438
- `_build_candidate_summary_fallback()` — строка ~459
- `_questions_from_scorecard()` — строка ~583
- `_build_candidate_coach_fallback()` — строка ~618
- `build_candidate_live_score_snapshot()` — строка ~674
- `invalidate_candidate_ai_outputs()` — строка ~702
- `invalidate_candidates_ai_outputs()` — строка ~710
- `_warm_candidate_ai_outputs()` — строка ~739
- `warm_candidate_ai_outputs()` — строка ~768
- `warm_candidates_ai_outputs()` — строка ~783
- `schedule_warm_candidate_ai_outputs()` — строка ~799

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/ai/candidate_scorecard.py`
- `backend/core/ai/context.py`
- `backend/core/ai/interview_script_builder.py`
- `backend/core/ai/knowledge_base.py`
- `backend/core/ai/llm_script_generator.py`
- `backend/core/ai/prompts.py`
- `backend/core/ai/providers/__init__.py`
- `backend/core/ai/redaction.py`
- `backend/core/ai/schemas.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/ai/models.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/ai.py`
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/core/ai/__init__.py`
- `backend/domain/candidates/services.py`
- `backend/domain/hh_integration/jobs.py`
- `tests/test_interview_script_ai.py`

**Комментарии / явные подсказки в файле:**
- AIService — central facade for all AI Copilot operations.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/audit.py`

**Тип:** Core-модуль
**Строк кода:** ~96
**Назначение:** Core-инфраструктура `audit`.

**Классы:**
- `AuditContext` — строка ~18

**Ключевые функции:**
- `set_audit_context()` — строка ~29
- `_build_context_from_request()` — строка ~34
- `get_audit_context()` — строка ~45
- `_normalize_changes()` — строка ~55
- `log_audit_action()` — строка ~65

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/auth.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/content_api.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/routers/workflow.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/services/staff_chat.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/auth.py`

**Тип:** Core-модуль
**Строк кода:** ~57
**Назначение:** Core-инфраструктура `auth`.

**Ключевые функции:**
- `verify_password()` — строка ~16
- `get_password_hash()` — строка ~26
- `create_access_token()` — строка ~31

**Зависимости (локальные импорты):**
- `backend/core/passwords.py`
- `backend/core/settings.py`

**Используется в:**
- `backend/apps/admin_ui/routers/auth.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `scripts/verify_jwt.py`
- `tests/test_profile_settings_api.py`
- `tests/test_security_auth_hardening.py`

**Комментарии / явные подсказки в файле:**
- Authentication core utilities.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/bootstrap.py`

**Тип:** Core-модуль
**Строк кода:** ~115
**Назначение:** Core-инфраструктура `bootstrap`.

**Ключевые функции:**
- `ensure_database_ready()` — строка ~29
- `_ensure_schema()` — строка ~50
- `_seed_defaults()` — строка ~60
- `_seed_cities()` — строка ~77
- `_seed_recruiters()` — строка ~91

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/ai/models.py`
- `backend/domain/base.py`
- `backend/domain/default_data.py`
- `backend/domain/detailization/models.py`
- `backend/domain/models.py`
- `backend/domain/simulator/models.py`

**Используется в:**
- `audit/run_smoke_checks.py`
- `tools/recompute_weekly_kpis.py`

**Комментарии / явные подсказки в файле:**
- Application bootstrap helpers ensuring the database is ready.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/cache.py`

**Тип:** Core-модуль
**Строк кода:** ~431
**Назначение:** Core-инфраструктура `cache`.

**Классы:**
- `CacheConfig` — строка ~27
- `CacheClient` — строка ~51
- `CacheKeys` — строка ~371
- `CacheTTL` — строка ~424

**Ключевые функции:**
- `get_cache()` — строка ~330
- `init_cache()` — строка ~338
- `connect_cache()` — строка ~354
- `disconnect_cache()` — строка ~360

**Зависимости (локальные импорты):**
- `backend/core/result.py`

**Используется в:**
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/bot/app.py`
- `backend/core/cache_decorators.py`
- `backend/repositories/recruiter.py`
- `backend/repositories/slot.py`
- `tests/test_cache_integration.py`

**Комментарии / явные подсказки в файле:**
- Cache infrastructure for performance optimization.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/cache_decorators.py`

**Тип:** Core-модуль
**Строк кода:** ~240
**Назначение:** Core-инфраструктура `cache_decorators`.

**Классы:**
- `CacheInvalidator` — строка ~191

**Ключевые функции:**
- `cached()` — строка ~27
- `invalidate_cache()` — строка ~104
- `_resolve_pattern()` — строка ~153

**Зависимости (локальные импорты):**
- `backend/core/cache.py`
- `backend/core/result.py`

**Используется в:**
- `backend/repositories/recruiter.py`
- `backend/repositories/slot.py`

**Комментарии / явные подсказки в файле:**
- Cache decorators for repository methods.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/content_updates.py`

**Тип:** Core-модуль
**Строк кода:** ~191
**Назначение:** Core-инфраструктура `content_updates`.

**Классы:**
- `ContentUpdateEvent` — строка ~36

**Ключевые функции:**
- `build_content_update()` — строка ~44
- `parse_content_update()` — строка ~58
- `publish_content_update()` — строка ~82
- `run_content_updates_subscriber()` — строка ~126

**Зависимости (локальные импорты):**
- `backend/core/redis_factory.py`
- `backend/core/settings.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/services/message_templates.py`
- `backend/apps/admin_ui/services/questions.py`
- `backend/apps/bot/app.py`
- `tests/test_bot_reminder_policy_api.py`
- `tests/test_content_updates.py`

**Комментарии / явные подсказки в файле:**
- Cross-process notifications for bot/admin content changes.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/db.py`

**Тип:** Core-модуль
**Строк кода:** ~198
**Назначение:** Core-инфраструктура `db`.

**Ключевые функции:**
- `_preflight_database_backend()` — строка ~27
- `init_models()` — строка ~129
- `new_async_session()` — строка ~155
- `async_session()` — строка ~161
- `new_sync_session()` — строка ~172
- `sync_session()` — строка ~178

**Зависимости (локальные импорты):**
- `backend/core/settings.py`
- `backend/core/sqlite_dev_schema.py`
- `backend/domain/ai/__init__.py`
- `backend/domain/base.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/hh_integration/__init__.py`
- `backend/migrations/__init__.py`

**Используется в:**
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/perf/metrics/db.py`
- `backend/apps/admin_ui/routers/ai.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/auth.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/content_api.py`
- `backend/apps/admin_ui/routers/knowledge_base.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/routers/regions.py`
- `backend/apps/admin_ui/routers/reschedule_requests.py`
- `backend/apps/admin_ui/routers/simulator.py`
- `backend/apps/admin_ui/routers/slot_assignments.py`
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/routers/system.py`
- `backend/apps/admin_ui/routers/workflow.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/dependencies.py`

**Тип:** Core-модуль
**Строк кода:** ~82
**Назначение:** Core-инфраструктура `dependencies`.

**Ключевые функции:**
- `get_async_session()` — строка ~16
- `get_uow()` — строка ~44

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/uow.py`

**Используется в:**
- `backend/apps/admin_api/hh_sync.py`
- `backend/apps/admin_api/webapp/routers.py`
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/apps/admin_ui/routers/recruiters_api_example.py`
- `backend/apps/hh_integration_webhooks.py`
- `backend/domain/analytics.py`
- `tests/test_dependency_injection.py`

**Комментарии / явные подсказки в файле:**
- FastAPI dependency injection for database access.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/env.py`

**Тип:** Core-модуль
**Строк кода:** ~79
**Назначение:** Core-инфраструктура `env`.

**Ключевые функции:**
- `load_env()` — строка ~8
- `_load_env_file()` — строка ~35
- `_default_env_path()` — строка ~68
- `_strip_quotes()` — строка ~72

**Используется в:**
- `backend/core/settings.py`
- `scripts/seed_message_templates.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/error_handler.py`

**Тип:** Core-модуль
**Строк кода:** ~209
**Назначение:** Core-инфраструктура `error_handler`.

**Классы:**
- `GracefulShutdown` — строка ~165

**Ключевые функции:**
- `setup_global_exception_handler()` — строка ~21
- `resilient_task()` — строка ~53
- `log_unhandled_exceptions()` — строка ~121
- `safe_background_task()` — строка ~133

**Используется в:**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/background_tasks.py`

**Комментарии / явные подсказки в файле:**
- Global error handling and resilience mechanisms.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/guards.py`

**Тип:** Core-модуль
**Строк кода:** ~22
**Назначение:** Core-инфраструктура `guards`.

**Ключевые функции:**
- `ensure_candidate_scope()` — строка ~10
- `ensure_slot_scope()` — строка ~17

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/slots.py`
- `tests/test_scoping_guards.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/logging.py`

**Тип:** Core-модуль
**Строк кода:** ~301
**Назначение:** Core-инфраструктура `logging`.

**Классы:**
- `StandardFormatter` — строка ~33
- `JsonFormatter` — строка ~46
- `PIIFilter` — строка ~101
- `PhoneMaskingFilter` — строка ~126
- `SecretsFilter` — строка ~182

**Ключевые функции:**
- `set_request_id()` — строка ~18
- `get_request_id()` — строка ~23
- `reset_request_id()` — строка ~28
- `_default_log_file()` — строка ~86
- `pseudonymize()` — строка ~92
- `configure_logging()` — строка ~211

**Зависимости (локальные импорты):**
- `backend/core/settings.py`

**Используется в:**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/middleware.py`
- `backend/apps/bot/app.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/messenger/__init__.py`

**Тип:** Core-модуль
**Строк кода:** ~28
**Назначение:** Core-инфраструктура `__init__`.

**Зависимости (локальные импорты):**
- `backend/core/messenger/protocol.py`
- `backend/core/messenger/registry.py`

**Комментарии / явные подсказки в файле:**
- Messenger abstraction layer.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/messenger/bootstrap.py`

**Тип:** Core-модуль
**Строк кода:** ~61
**Назначение:** Core-инфраструктура `bootstrap`.

**Ключевые функции:**
- `bootstrap_messenger_adapters()` — строка ~14

**Зависимости (локальные импорты):**
- `backend/core/messenger/max_adapter.py`
- `backend/core/messenger/protocol.py`
- `backend/core/messenger/registry.py`
- `backend/core/messenger/telegram_adapter.py`

**Используется в:**
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/app.py`
- `backend/apps/max_bot/app.py`
- `tests/test_messenger.py`

**Комментарии / явные подсказки в файле:**
- Bootstrap messenger adapters at application startup.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/messenger/max_adapter.py`

**Тип:** Core-модуль
**Строк кода:** ~189
**Назначение:** Core-инфраструктура `max_adapter`.

**Классы:**
- `MaxAdapter` — строка ~29

**Зависимости (локальные импорты):**
- `backend/core/messenger/protocol.py`

**Используется в:**
- `backend/core/messenger/bootstrap.py`
- `tests/test_messenger.py`

**Комментарии / явные подсказки в файле:**
- VK Max adapter — MessengerProtocol implementation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/messenger/protocol.py`

**Тип:** Core-модуль
**Строк кода:** ~98
**Назначение:** Core-инфраструктура `protocol`.

**Классы:**
- `MessengerPlatform` — строка ~10
- `InlineButton` — строка ~35
- `SendResult` — строка ~43
- `MessengerProtocol` — строка ~52

**Используется в:**
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/apps/bot/services.py`
- `backend/apps/max_bot/app.py`
- `backend/core/messenger/__init__.py`
- `backend/core/messenger/bootstrap.py`
- `backend/core/messenger/max_adapter.py`
- `backend/core/messenger/registry.py`
- `backend/core/messenger/telegram_adapter.py`
- `tests/test_max_sales_handoff.py`
- `tests/test_messenger.py`

**Комментарии / явные подсказки в файле:**
- Messenger protocol — abstract interface for all messenger adapters.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/messenger/registry.py`

**Тип:** Core-модуль
**Строк кода:** ~139
**Назначение:** Core-инфраструктура `registry`.

**Классы:**
- `MessengerRegistry` — строка ~24

**Ключевые функции:**
- `get_registry()` — строка ~76
- `register_adapter()` — строка ~84
- `get_adapter()` — строка ~89
- `resolve_adapter_for_candidate()` — строка ~94

**Зависимости (локальные импорты):**
- `backend/core/messenger/protocol.py`

**Используется в:**
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/apps/bot/services.py`
- `backend/apps/max_bot/app.py`
- `backend/core/messenger/__init__.py`
- `backend/core/messenger/bootstrap.py`
- `tests/test_max_sales_handoff.py`
- `tests/test_messenger.py`

**Комментарии / явные подсказки в файле:**
- Messenger adapter registry — singleton lookup for platform adapters.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/messenger/telegram_adapter.py`

**Тип:** Core-модуль
**Строк кода:** ~126
**Назначение:** Core-инфраструктура `telegram_adapter`.

**Классы:**
- `TelegramAdapter` — строка ~19

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/core/messenger/protocol.py`

**Используется в:**
- `backend/core/messenger/bootstrap.py`
- `tests/test_messenger.py`

**Комментарии / явные подсказки в файле:**
- Telegram adapter — wraps aiogram Bot into MessengerProtocol.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/metrics.py`

**Тип:** Core-модуль
**Строк кода:** ~325
**Назначение:** Core-инфраструктура `metrics`.

**Классы:**
- `RequestMetrics` — строка ~23
- `QueryMetrics` — строка ~37
- `CacheMetrics` — строка ~47
- `PerformanceStats` — строка ~71
- `PerformanceTimer` — строка ~235

**Ключевые функции:**
- `get_metrics()` — строка ~221
- `reset_metrics()` — строка ~229
- `timed()` — строка ~273
- `log_performance_summary()` — строка ~305

**Комментарии / явные подсказки в файле:**
- Performance monitoring and metrics collection.

**Состояние / проблемы:**
- console/print: 1

### `backend/core/microcache.py`

**Тип:** Core-модуль
**Строк кода:** ~60
**Назначение:** Core-инфраструктура `microcache`.

**Классы:**
- `_Entry` — строка ~22

**Ключевые функции:**
- `_enabled()` — строка ~30
- `get()` — строка ~35
- `set()` — строка ~47
- `clear()` — строка ~58

**Используется в:**
- `backend/apps/admin_ui/perf/cache/microcache.py`

**Комментарии / явные подсказки в файле:**
- Tiny in-process TTL cache for ultra-hot paths.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/passwords.py`

**Тип:** Core-модуль
**Строк кода:** ~46
**Назначение:** Core-инфраструктура `passwords`.

**Ключевые функции:**
- `_pbkdf2_hash()` — строка ~13
- `hash_password()` — строка ~17
- `verify_password()` — строка ~28
- `make_legacy_hash()` — строка ~42

**Используется в:**
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `backend/core/auth.py`
- `scripts/seed_auth_accounts.py`
- `scripts/verify_jwt.py`
- `tests/test_profile_settings_api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/query_optimization.py`

**Тип:** Core-модуль
**Строк кода:** ~341
**Назначение:** Core-инфраструктура `query_optimization`.

**Классы:**
- `QueryOptimizer` — строка ~25
- `BatchLoader` — строка ~151
- `QueryCache` — строка ~201
- `OptimizedQueries` — строка ~253
- `QueryStats` — строка ~303

**Зависимости (локальные импорты):**
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/repositories/slot.py`

**Комментарии / явные подсказки в файле:**
- Query optimization utilities for improved performance.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/redis_factory.py`

**Тип:** Core-модуль
**Строк кода:** ~47
**Назначение:** Core-инфраструктура `redis_factory`.

**Классы:**
- `RedisTarget` — строка ~14

**Ключевые функции:**
- `parse_redis_target()` — строка ~21
- `create_redis_client()` — строка ~39

**Используется в:**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/state_store.py`
- `backend/core/content_updates.py`

**Комментарии / явные подсказки в файле:**
- Shared helpers for Redis client creation and logging.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/repository/__init__.py`

**Тип:** Core-модуль
**Строк кода:** ~12
**Назначение:** Core-инфраструктура `__init__`.

**Зависимости (локальные импорты):**
- `backend/core/repository/base.py`
- `backend/core/repository/protocols.py`

**Комментарии / явные подсказки в файле:**
- Repository pattern implementation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/repository/base.py`

**Тип:** Core-модуль
**Строк кода:** ~324
**Назначение:** Core-инфраструктура `base`.

**Классы:**
- `BaseRepository` — строка ~33

**Зависимости (локальные импорты):**
- `backend/core/result.py`
- `backend/domain/base.py`

**Используется в:**
- `backend/core/repository/__init__.py`
- `backend/repositories/city.py`
- `backend/repositories/recruiter.py`
- `backend/repositories/slot.py`
- `backend/repositories/template.py`
- `backend/repositories/user.py`

**Комментарии / явные подсказки в файле:**
- Base Repository implementation with common CRUD operations.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/repository/protocols.py`

**Тип:** Core-модуль
**Строк кода:** ~72
**Назначение:** Core-инфраструктура `protocols`.

**Классы:**
- `IRepository` — строка ~19
- `IUnitOfWork` — строка ~49

**Зависимости (локальные импорты):**
- `backend/core/result.py`

**Используется в:**
- `backend/core/repository/__init__.py`

**Комментарии / явные подсказки в файле:**
- Protocol definitions for repository and unit of work interfaces.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/result.py`

**Тип:** Core-модуль
**Строк кода:** ~197
**Назначение:** Core-инфраструктура `result`.

**Классы:**
- `Success` — строка ~31
- `Failure` — строка ~69
- `NotFoundError` — строка ~119
- `ValidationError` — строка ~133
- `DatabaseError` — строка ~147
- `ConflictError` — строка ~159

**Ключевые функции:**
- `success()` — строка ~107
- `failure()` — строка ~112
- `async_success()` — строка ~173
- `async_failure()` — строка ~178
- `collect_results()` — строка ~184

**Используется в:**
- `backend/apps/admin_ui/routers/recruiters_api_example.py`
- `backend/core/cache.py`
- `backend/core/cache_decorators.py`
- `backend/core/repository/base.py`
- `backend/core/repository/protocols.py`
- `backend/repositories/city.py`
- `backend/repositories/recruiter.py`
- `backend/repositories/slot.py`
- `backend/repositories/template.py`
- `backend/repositories/user.py`
- `tests/test_slot_repository.py`

**Комментарии / явные подсказки в файле:**
- Result Pattern implementation for type-safe error handling.

**Состояние / проблемы:**
- console/print: 2

### `backend/core/sanitizers.py`

**Тип:** Core-модуль
**Строк кода:** ~41
**Назначение:** Core-инфраструктура `sanitizers`.

**Ключевые функции:**
- `sanitize_plain_text()` — строка ~9

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/cities.py`
- `backend/apps/admin_ui/routers/directory.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/services/calendar_tasks.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/recruiter_plan.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/scoping.py`

**Тип:** Core-модуль
**Строк кода:** ~32
**Назначение:** Core-инфраструктура `scoping`.

**Ключевые функции:**
- `scope_candidates()` — строка ~11
- `scope_slots()` — строка ~17
- `scope_cities()` — строка ~23

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/services/dashboard.py`
- `tests/test_scoping_guards.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/settings.py`

**Тип:** Core-модуль
**Строк кода:** ~824
**Назначение:** Core-инфраструктура `settings`.

**Классы:**
- `Settings` — строка ~17

**Ключевые функции:**
- `_get_int()` — строка ~113
- `_get_float()` — строка ~126
- `_default_data_dir()` — строка ~142
- `_get_bool()` — строка ~151
- `_get_bool_default_by_env()` — строка ~158
- `_get_bool_with_fallback()` — строка ~165
- `_get_repo_root()` — строка ~174
- `_validate_production_settings()` — строка ~195
- `get_settings()` — строка ~436

**Зависимости (локальные импорты):**
- `backend/core/env.py`

**Используется в:**
- `backend/apps/admin_api/admin.py`
- `backend/apps/admin_api/hh_sync.py`
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_api/webapp/auth.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- `backend/apps/admin_ui/perf/metrics/db.py`
- `backend/apps/admin_ui/perf/metrics/http.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/auth.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/dashboard.py`
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/apps/admin_ui/routers/metrics.py`
- `backend/apps/admin_ui/routers/simulator.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/routers/system.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/candidates.py`

**Состояние / проблемы:**
- console/print: 8

### `backend/core/sqlite_dev_schema.py`

**Тип:** Core-модуль
**Строк кода:** ~85
**Назначение:** Core-инфраструктура `sqlite_dev_schema`.

**Ключевые функции:**
- `_quoted()` — строка ~13
- `_default_sql()` — строка ~17
- `_column_sql()` — строка ~40
- `repair_sqlite_schema()` — строка ~61

**Используется в:**
- `backend/core/db.py`
- `tests/test_sqlite_dev_schema.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/time_utils.py`

**Тип:** Core-модуль
**Строк кода:** ~73
**Назначение:** Core-инфраструктура `time_utils`.

**Ключевые функции:**
- `_safe_zone()` — строка ~19
- `ensure_aware_utc()` — строка ~32
- `local_to_utc()` — строка ~41
- `parse_form_datetime()` — строка ~50

**Зависимости (локальные импорты):**
- `backend/core/settings.py`
- `backend/core/timezone_utils.py`

**Используется в:**
- `backend/apps/admin_api/slot_assignments.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/slot_assignments.py`
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/utils.py`
- `backend/domain/slot_service.py`
- `tests/test_manual_slot_assignment.py`
- `tests/test_slot_cleanup_strict.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/timezone.py`

**Тип:** Core-модуль
**Строк кода:** ~71
**Назначение:** Core-инфраструктура `timezone`.

**Классы:**
- `InvalidTimezoneError` — строка ~22

**Ключевые функции:**
- `safe_zone()` — строка ~26
- `validate_timezone_name()` — строка ~36
- `ensure_timezone()` — строка ~51
- `local_naive_to_utc()` — строка ~57
- `utc_to_local_naive()` — строка ~66

**Используется в:**
- `backend/apps/admin_ui/utils.py`

**Комментарии / явные подсказки в файле:**
- Centralised timezone utilities used across the backend.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/timezone_service.py`

**Тип:** Core-модуль
**Строк кода:** ~348
**Назначение:** Core-инфраструктура `timezone_service`.

**Классы:**
- `DSTTransitionType` — строка ~18
- `DSTTransitionInfo` — строка ~27
- `MultiTimezoneView` — строка ~41
- `TimezoneService` — строка ~82

**Используется в:**
- `backend/domain/models.py`
- `tests/test_timezone_service.py`

**Комментарии / явные подсказки в файле:**
- Timezone service for handling timezone conversions and DST transitions.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/timezone_utils.py`

**Тип:** Core-модуль
**Строк кода:** ~302
**Назначение:** Core-инфраструктура `timezone_utils`.

**Ключевые функции:**
- `parse_timezone()` — строка ~38
- `ensure_aware()` — строка ~80
- `normalize_to_utc()` — строка ~111
- `to_local_time()` — строка ~144
- `format_for_ui()` — строка ~172
- `get_offset_minutes()` — строка ~208
- `is_same_moment()` — строка ~240
- `datetime_range_overlap()` — строка ~265

**Используется в:**
- `backend/core/time_utils.py`
- `tests/test_timezone_utils.py`

**Комментарии / явные подсказки в файле:**
- Timezone utilities for consistent datetime handling across the application.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/core/uow.py`

**Тип:** Core-модуль
**Строк кода:** ~235
**Назначение:** Core-инфраструктура `uow`.

**Классы:**
- `UnitOfWork` — строка ~42

**Ключевые функции:**
- `create_uow()` — строка ~224

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`
- `backend/repositories/__init__.py`

**Используется в:**
- `backend/apps/admin_ui/routers/recruiters_api_example.py`
- `backend/core/dependencies.py`
- `tests/test_cache_integration.py`
- `tests/test_dependency_injection.py`
- `tests/test_slot_repository.py`

**Комментарии / явные подсказки в файле:**
- Unit of Work pattern implementation for transaction management.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/ai/__init__.py`

**Тип:** Domain-модуль
**Строк кода:** ~24
**Назначение:** Domain-модуль `__init__`.

**Зависимости (локальные импорты):**
- `backend/domain/ai/models.py`

**Используется в:**
- `backend/core/db.py`
- `tests/test_sqlite_dev_schema.py`

**Комментарии / явные подсказки в файле:**
- AI domain models and helpers.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/ai/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~235
**Назначение:** Domain-модуль `models`.

**Классы:**
- `AIOutput` — строка ~22
- `AIRequestLog` — строка ~48
- `KnowledgeBaseDocument` — строка ~75
- `KnowledgeBaseChunk` — строка ~103
- `AIAgentThread` — строка ~124
- `AIAgentMessage` — строка ~148
- `CandidateHHResume` — строка ~168
- `AIInterviewScriptFeedback` — строка ~201

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/apps/admin_ui/routers/knowledge_base.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/core/ai/knowledge_base.py`
- `backend/core/ai/service.py`
- `backend/core/bootstrap.py`
- `backend/domain/ai/__init__.py`
- `scripts/export_interview_script_dataset.py`
- `tests/services/test_dashboard_and_slots.py`
- `tests/test_interview_script_feedback.py`
- `tests/test_kb_active_documents_list.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/analytics.py`

**Тип:** Domain-модуль
**Строк кода:** ~354
**Назначение:** Domain-модуль `analytics`.

**Классы:**
- `FunnelEvent` — строка ~28

**Ключевые функции:**
- `log_event()` — строка ~41
- `log_funnel_event()` — строка ~124
- `log_slot_viewed()` — строка ~152
- `log_slot_booked()` — строка ~168
- `log_slot_rescheduled()` — строка ~188
- `log_slot_canceled()` — строка ~210
- `log_reminder_sent()` — строка ~233
- `log_reminder_clicked()` — строка ~254
- `log_no_show()` — строка ~274
- `log_arrived_confirmed()` — строка ~291
- `log_calendar_downloaded()` — строка ~307
- `log_map_opened()` — строка ~323

**Зависимости (локальные импорты):**
- `backend/core/dependencies.py`

**Используется в:**
- `backend/apps/admin_ui/services/dashboard.py`
- `tests/services/test_dashboard_funnel.py`

**Комментарии / явные подсказки в файле:**
- Analytics events logging system.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/analytics_models.py`

**Тип:** Domain-модуль
**Строк кода:** ~35
**Назначение:** Domain-модуль `analytics_models`.

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/apps/admin_ui/services/dashboard.py`

**Комментарии / явные подсказки в файле:**
- SQLAlchemy table metadata for analytics_events.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/auth_account.py`

**Тип:** Domain-модуль
**Строк кода:** ~39
**Назначение:** Domain-модуль `auth_account`.

**Классы:**
- `AuthAccount` — строка ~14

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/apps/admin_ui/routers/auth.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/recruiters.py`
- `scripts/seed_auth_accounts.py`
- `tests/test_profile_settings_api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/base.py`

**Тип:** Domain-модуль
**Строк кода:** ~8
**Назначение:** Domain-модуль `base`.

**Классы:**
- `Base` — строка ~4

**Используется в:**
- `backend/core/bootstrap.py`
- `backend/core/db.py`
- `backend/core/repository/base.py`
- `backend/domain/ai/models.py`
- `backend/domain/analytics_models.py`
- `backend/domain/auth_account.py`
- `backend/domain/candidates/models.py`
- `backend/domain/cities/models.py`
- `backend/domain/detailization/models.py`
- `backend/domain/hh_integration/models.py`
- `backend/domain/hh_sync/models.py`
- `backend/domain/models.py`
- `backend/domain/simulator/models.py`
- `backend/domain/tests/models.py`
- `tests/conftest.py`
- `tests/test_admin_candidate_chat_actions.py`
- `tests/test_sqlite_dev_schema.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidate_status_service.py`

**Тип:** Domain-модуль
**Строк кода:** ~147
**Назначение:** Domain-модуль `candidate_status_service`.

**Классы:**
- `CandidateStatusTransitionError` — строка ~17
- `CandidateStatusService` — строка ~24

**Зависимости (локальные импорты):**
- `backend/domain/candidates/journey.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Используется в:**
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/bot/recruiter_service.py`
- `backend/domain/candidates/status_service.py`

**Комментарии / явные подсказки в файле:**
- Domain service for candidate status transitions.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/__init__.py`

**Тип:** Domain-модуль
**Строк кода:** ~42
**Назначение:** Domain-модуль `__init__`.

**Ключевые функции:**
- `__getattr__()` — строка ~33
- `__dir__()` — строка ~40

**Зависимости (локальные импорты):**
- `backend/domain/candidates/__init__.py`

**Используется в:**
- `backend/apps/bot/handlers/common.py`
- `backend/apps/bot/middleware.py`
- `backend/apps/bot/services.py`
- `backend/apps/max_bot/app.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `tests/test_admin_candidate_chat_actions.py`
- `tests/test_admin_candidate_schedule_slot.py`
- `tests/test_admin_candidate_status_update.py`
- `tests/test_admin_candidates_service.py`
- `tests/test_admin_slots_api.py`
- `tests/test_candidate_chat_threads_api.py`
- `tests/test_candidate_lead_and_invite.py`
- `tests/test_candidate_reports.py`
- `tests/test_candidate_services.py`
- `tests/test_chat_messages.py`
- `tests/test_intro_day_recruiter_scope.py`
- `tests/test_manual_slot_assignment.py`
- `tests/test_sqlite_dev_schema.py`
- `tests/test_telegram_identity.py`

**Комментарии / явные подсказки в файле:**
- Domain package for candidate onboarding and test-related models/services.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/actions.py`

**Тип:** Domain-модуль
**Строк кода:** ~399
**Назначение:** Domain-модуль `actions`.

**Классы:**
- `CandidateAction` — строка ~16

**Ключевые функции:**
- `get_candidate_actions()` — строка ~315

**Зависимости (локальные импорты):**
- `backend/domain/candidates/status.py`

**Используется в:**
- `backend/apps/admin_ui/services/candidates.py`
- `tests/test_action_endpoint.py`
- `tests/test_candidate_actions.py`

**Комментарии / явные подсказки в файле:**
- Candidate action configuration based on current status.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/journey.py`

**Тип:** Domain-модуль
**Строк кода:** ~429
**Назначение:** Domain-модуль `journey`.

**Ключевые функции:**
- `_normalized_reason()` — строка ~85
- `stage_for_status()` — строка ~93
- `normalize_status_slug()` — строка ~110
- `is_not_counted_reason()` — строка ~117
- `final_outcome_for_status()` — строка ~133
- `final_outcome_label()` — строка ~154
- `lifecycle_label()` — строка ~159
- `archive_stage_label()` — строка ~164
- `journey_state_label()` — строка ~169
- `_safe_zone()` — строка ~176
- `_normalize_intro_day_status()` — строка ~183
- `manual_mode_for_candidate()` — строка ~205
- `append_journey_event()` — строка ~210
- `serialize_journey_event()` — строка ~244
- `serialize_pending_slot_request()` — строка ~260
- `sync_candidate_lifecycle()` — строка ~276
- `derive_candidate_journey_state()` — строка ~335
- `build_archive_payload()` — строка ~362
- `build_candidate_journey()` — строка ~378

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/reschedule_intents.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/detailization.py`
- `backend/domain/candidate_status_service.py`
- `tests/test_intro_day_status.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~480
**Назначение:** Domain-модуль `models`.

**Классы:**
- `User` — строка ~33
- `TestResult` — строка ~154
- `CandidateJourneyEvent` — строка ~180
- `QuestionAnswer` — строка ~212
- `Test2InviteStatus` — строка ~238
- `Test2Invite` — строка ~246
- `AutoMessage` — строка ~271
- `Notification` — строка ~289
- `InterviewNote` — строка ~308
- `ChatMessageDirection` — строка ~328
- `ChatMessageStatus` — строка ~333
- `ChatMessage` — строка ~340
- `CandidateChatRead` — строка ~370
- `CandidateChatWorkspace` — строка ~424
- `CandidateInviteToken` — строка ~462

**Зависимости (локальные импорты):**
- `backend/domain/base.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/routers/slot_assignments.py`
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/routers/workflow.py`
- `backend/apps/admin_ui/services/calendar_events.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/chat_meta.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/dashboard_calendar.py`
- `backend/apps/admin_ui/services/detailization.py`
- `backend/apps/admin_ui/services/kpis.py`
- `backend/apps/admin_ui/services/recruiter_access.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/services.py`

**Тип:** Domain-модуль
**Строк кода:** ~656
**Назначение:** Domain-модуль `services`.

**Ключевые функции:**
- `create_or_update_user()` — строка ~31
- `save_test_result()` — строка ~104
- `get_user_by_telegram_id()` — строка ~149
- `get_user_by_candidate_id()` — строка ~162
- `get_all_active_users()` — строка ~175
- `get_test_statistics()` — строка ~184
- `create_auto_message()` — строка ~210
- `get_active_auto_messages()` — строка ~225
- `create_notification()` — строка ~233
- `mark_notification_sent()` — строка ~248
- `update_chat_message_status()` — строка ~257
- `log_inbound_chat_message()` — строка ~276
- `log_outbound_chat_message()` — строка ~331
- `_generate_invite_token()` — строка ~369
- `create_candidate_invite_token()` — строка ~373
- `bind_telegram_to_candidate()` — строка ~397
- `list_chat_messages()` — строка ~464
- `set_conversation_mode()` — строка ~492
- `is_chat_mode_active()` — строка ~516
- `link_telegram_identity()` — строка ~535
- `update_candidate_reports()` — строка ~589
- `mark_manual_slot_requested()` — строка ~610
- `save_manual_slot_response()` — строка ~629

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/ai/service.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Используется в:**
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/domain/repositories.py`
- `scripts/generate_waiting_candidates.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/status.py`

**Тип:** Domain-модуль
**Строк кода:** ~365
**Назначение:** Domain-модуль `status`.

**Классы:**
- `CandidateStatus` — строка ~13
- `StatusCategory` — строка ~99

**Ключевые функции:**
- `get_status_label()` — строка ~263
- `get_status_color()` — строка ~270
- `get_status_category()` — строка ~277
- `can_transition()` — строка ~282
- `get_next_statuses()` — строка ~292
- `is_terminal_status()` — строка ~301
- `is_status_retreat()` — строка ~306
- `get_funnel_stages()` — строка ~313

**Используется в:**
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/detailization.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/services/staff_chat.py`
- `backend/apps/bot/recruiter_service.py`
- `backend/apps/bot/services.py`
- `backend/domain/candidate_status_service.py`
- `backend/domain/candidates/actions.py`
- `backend/domain/candidates/journey.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/services.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/hh_sync/dispatcher.py`
- `backend/domain/hh_sync/mapping.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Candidate status tracking system.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/status_service.py`

**Тип:** Domain-модуль
**Строк кода:** ~388
**Назначение:** Domain-модуль `status_service`.

**Классы:**
- `StatusTransitionError` — строка ~33

**Ключевые функции:**
- `update_candidate_status()` — строка ~42
- `get_candidate_status()` — строка ~153
- `set_status_test1_completed()` — строка ~171
- `set_status_waiting_slot()` — строка ~186
- `set_status_slot_pending()` — строка ~197
- `set_status_interview_scheduled()` — строка ~208
- `set_status_interview_confirmed()` — строка ~219
- `set_status_interview_declined()` — строка ~230
- `set_status_test2_sent()` — строка ~241
- `set_status_test2_completed()` — строка ~252
- `set_status_test2_failed()` — строка ~263
- `set_status_intro_day_scheduled()` — строка ~274
- `set_status_intro_day_confirmed_preliminary()` — строка ~285
- `set_status_intro_day_declined_invitation()` — строка ~296
- `set_status_intro_day_confirmed_day_of()` — строка ~307
- `set_status_intro_day_declined_day_of()` — строка ~318
- `set_status_hired()` — строка ~329
- `set_status_not_hired()` — строка ~348

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidate_status_service.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/services/slots/bot.py`
- `backend/apps/bot/handlers/interview.py`
- `backend/apps/bot/services.py`
- `backend/domain/repositories.py`
- `tests/test_status_service_transitions.py`

**Комментарии / явные подсказки в файле:**
- Service layer for candidate status management.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/candidates/workflow.py`

**Тип:** Domain-модуль
**Строк кода:** ~261
**Назначение:** Domain-модуль `workflow`.

**Классы:**
- `WorkflowStatus` — строка ~11
- `WorkflowAction` — строка ~22
- `CandidateStateDTO` — строка ~81
- `WorkflowConflict` — строка ~87
- `CandidateWorkflowService` — строка ~96
- `UnifiedStatus` — строка ~155

**Ключевые функции:**
- `_utcnow()` — строка ~76
- `unified_status()` — строка ~208

**Зависимости (локальные импорты):**
- `backend/domain/candidates/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/workflow.py`
- `backend/apps/admin_ui/services/candidates.py`
- `tests/test_admin_candidates_service.py`
- `tests/test_workflow_api.py`
- `tests/test_workflow_contract.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/cities/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~32
**Назначение:** Domain-модуль `models`.

**Классы:**
- `CityExpert` — строка ~7
- `CityExecutive` — строка ~21

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/apps/admin_api/admin.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/domain/models.py`
- `tests/test_city_experts_sync.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/default_data.py`

**Тип:** Domain-модуль
**Строк кода:** ~57
**Назначение:** Domain-модуль `default_data`.

**Ключевые функции:**
- `should_seed_default_recruiters()` — строка ~36
- `default_recruiters()` — строка ~44

**Используется в:**
- `backend/core/bootstrap.py`
- `backend/migrations/versions/0002_seed_defaults.py`

**Комментарии / явные подсказки в файле:**
- Shared default datasets used for seeding and migrations.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/detailization/__init__.py`

**Тип:** Domain-модуль
**Строк кода:** ~7
**Назначение:** Domain-модуль `__init__`.

**Зависимости (локальные импорты):**
- `backend/domain/detailization/models.py`

**Комментарии / явные подсказки в файле:**
- Detailization (reporting) domain models.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/detailization/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~125
**Назначение:** Domain-модуль `models`.

**Классы:**
- `DetailizationEntry` — строка ~21

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/apps/admin_ui/services/detailization.py`
- `backend/core/bootstrap.py`
- `backend/domain/detailization/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/errors.py`

**Тип:** Domain-модуль
**Строк кода:** ~24
**Назначение:** Domain-модуль `errors`.

**Классы:**
- `CityAlreadyExistsError` — строка ~1
- `SlotOverlapError` — строка ~7

**Используется в:**
- `backend/apps/admin_ui/routers/directory.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/slots.py`
- `tests/test_slot_overlap_handling.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/__init__.py`

**Тип:** Domain-модуль
**Строк кода:** ~40
**Назначение:** Domain-модуль `__init__`.

**Зависимости (локальные импорты):**
- `backend/domain/hh_integration/client.py`
- `backend/domain/hh_integration/importer.py`
- `backend/domain/hh_integration/oauth.py`
- `backend/domain/hh_integration/service.py`

**Используется в:**
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/apps/admin_ui/services/cities_hh.py`
- `backend/apps/hh_integration_webhooks.py`
- `backend/core/db.py`
- `tests/test_sqlite_dev_schema.py`

**Комментарии / явные подсказки в файле:**
- Direct HeadHunter integration domain.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/client.py`

**Тип:** Domain-модуль
**Строк кода:** ~285
**Назначение:** Domain-модуль `client`.

**Классы:**
- `HHApiError` — строка ~15
- `HHOAuthTokens` — строка ~23
- `HHApiClient` — строка ~34

**Зависимости (локальные импорты):**
- `backend/core/settings.py`
- `backend/domain/hh_integration/contracts.py`

**Используется в:**
- `backend/domain/hh_integration/__init__.py`
- `backend/domain/hh_integration/importer.py`
- `backend/domain/hh_integration/jobs.py`
- `backend/domain/hh_integration/service.py`
- `tests/test_city_hh_vacancies_api.py`
- `tests/test_hh_integration_client.py`
- `tests/test_hh_integration_foundation.py`

**Комментарии / явные подсказки в файле:**
- Thin HH API client wrapper for direct integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/contracts.py`

**Тип:** Domain-модуль
**Строк кода:** ~48
**Назначение:** Domain-модуль `contracts`.

**Классы:**
- `HHConnectionStatus` — строка ~16
- `HHWebhookDeliveryStatus` — строка ~22
- `HHSyncJobStatus` — строка ~28
- `HHSyncDirection` — строка ~36
- `HHIdentitySyncStatus` — строка ~41

**Используется в:**
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/domain/hh_integration/client.py`
- `backend/domain/hh_integration/importer.py`
- `backend/domain/hh_integration/jobs.py`
- `backend/domain/hh_integration/models.py`
- `backend/domain/hh_integration/service.py`

**Комментарии / явные подсказки в файле:**
- Contracts and constants for direct HH integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/crypto.py`

**Тип:** Domain-модуль
**Строк кода:** ~28
**Назначение:** Domain-модуль `crypto`.

**Классы:**
- `HHSecretCipher` — строка ~12

**Зависимости (локальные импорты):**
- `backend/core/settings.py`

**Используется в:**
- `backend/domain/hh_integration/service.py`
- `tests/test_city_hh_vacancies_api.py`
- `tests/test_hh_integration_actions.py`
- `tests/test_hh_integration_foundation.py`
- `tests/test_hh_integration_import.py`
- `tests/test_hh_integration_jobs.py`

**Комментарии / явные подсказки в файле:**
- Encryption helpers for HH OAuth tokens.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/importer.py`

**Тип:** Domain-модуль
**Строк кода:** ~612
**Назначение:** Domain-модуль `importer`.

**Классы:**
- `HHVacancyImportResult` — строка ~38
- `HHNegotiationImportResult` — строка ~45

**Ключевые функции:**
- `_utcnow()` — строка ~56
- `_string()` — строка ~60
- `_parse_hh_datetime()` — строка ~65
- `_payload_hash()` — строка ~78
- `_normalize_phone()` — строка ~83
- `_resume_snippet()` — строка ~91
- `_extract_resume_id()` — строка ~96
- `_extract_vacancy_id()` — строка ~104
- `_extract_vacancy_id_from_collection_url()` — строка ~113
- `_extract_resume_url()` — строка ~119
- `_extract_fio()` — строка ~129
- `_extract_city()` — строка ~148
- `_extract_position()` — строка ~160
- `_extract_phone()` — строка ~170
- `_extract_collection_refs()` — строка ~192
- `_find_candidate_by_phone()` — строка ~249
- `_find_candidate_for_resume()` — строка ~259
- `_upsert_candidate_identity()` — строка ~288
- `import_hh_vacancies()` — строка ~324
- `import_hh_negotiations()` — строка ~396
- `serialize_import_result()` — строка ~610

**Зависимости (локальные импорты):**
- `backend/domain/candidates/models.py`
- `backend/domain/hh_integration/client.py`
- `backend/domain/hh_integration/contracts.py`
- `backend/domain/hh_integration/models.py`
- `backend/domain/hh_integration/service.py`

**Используется в:**
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/domain/hh_integration/__init__.py`
- `backend/domain/hh_integration/jobs.py`

**Комментарии / явные подсказки в файле:**
- Import services for direct HH integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/jobs.py`

**Тип:** Domain-модуль
**Строк кода:** ~251
**Назначение:** Domain-модуль `jobs`.

**Ключевые функции:**
- `_utcnow()` — строка ~27
- `serialize_hh_sync_job()` — строка ~31
- `enqueue_hh_sync_job()` — строка ~50
- `list_hh_sync_jobs()` — строка ~93
- `retry_hh_sync_job()` — строка ~107
- `_claim_hh_sync_jobs()` — строка ~124
- `_complete_job()` — строка ~158
- `_fail_job()` — строка ~174
- `_execute_hh_sync_job()` — строка ~191
- `process_pending_hh_sync_jobs()` — строка ~233

**Зависимости (локальные импорты):**
- `backend/core/ai/service.py`
- `backend/core/db.py`
- `backend/domain/hh_integration/client.py`
- `backend/domain/hh_integration/contracts.py`
- `backend/domain/hh_integration/importer.py`
- `backend/domain/hh_integration/models.py`

**Используется в:**
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/routers/hh_integration.py`
- `tests/test_hh_integration_jobs.py`

**Комментарии / явные подсказки в файле:**
- Queue and worker helpers for HH integration sync jobs.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~210
**Назначение:** Domain-модуль `models`.

**Классы:**
- `HHConnection` — строка ~28
- `CandidateExternalIdentity` — строка ~60
- `ExternalVacancyBinding` — строка ~88
- `HHNegotiation` — строка ~114
- `HHResumeSnapshot` — строка ~143
- `HHSyncJob` — строка ~162
- `HHWebhookDelivery` — строка ~189

**Зависимости (локальные импорты):**
- `backend/domain/base.py`
- `backend/domain/hh_integration/contracts.py`

**Используется в:**
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/apps/admin_ui/services/cities_hh.py`
- `backend/apps/hh_integration_webhooks.py`
- `backend/domain/hh_integration/importer.py`
- `backend/domain/hh_integration/jobs.py`
- `backend/domain/hh_integration/service.py`
- `backend/domain/hh_integration/summary.py`
- `tests/test_city_hh_vacancies_api.py`
- `tests/test_hh_integration_actions.py`
- `tests/test_hh_integration_foundation.py`
- `tests/test_hh_integration_import.py`
- `tests/test_hh_integration_jobs.py`

**Комментарии / явные подсказки в файле:**
- ORM models for direct HH integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/oauth.py`

**Тип:** Domain-модуль
**Строк кода:** ~72
**Назначение:** Domain-модуль `oauth`.

**Классы:**
- `HHOAuthState` — строка ~16

**Ключевые функции:**
- `_serializer()` — строка ~22
- `sign_hh_oauth_state()` — строка ~27
- `parse_hh_oauth_state()` — строка ~37
- `build_hh_authorize_url()` — строка ~52

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/settings.py`

**Используется в:**
- `backend/domain/hh_integration/__init__.py`
- `tests/test_hh_integration_foundation.py`

**Комментарии / явные подсказки в файле:**
- OAuth helpers for HH employer integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/service.py`

**Тип:** Domain-модуль
**Строк кода:** ~191
**Назначение:** Domain-модуль `service`.

**Ключевые функции:**
- `_manager_name_from_profile()` — строка ~18
- `_employer_info()` — строка ~25
- `_manager_info()` — строка ~34
- `_manager_account_id()` — строка ~42
- `get_connection_for_principal()` — строка ~47
- `get_connection_for_webhook_key()` — строка ~72
- `_resolve_public_base_url()` — строка ~79
- `build_connection_summary()` — строка ~89
- `decrypt_access_token()` — строка ~120
- `decrypt_refresh_token()` — строка ~124
- `apply_refreshed_tokens()` — строка ~128
- `build_webhook_target_url()` — строка ~138
- `upsert_hh_connection()` — строка ~150

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/domain/hh_integration/client.py`
- `backend/domain/hh_integration/contracts.py`
- `backend/domain/hh_integration/crypto.py`
- `backend/domain/hh_integration/models.py`

**Используется в:**
- `backend/domain/hh_integration/__init__.py`
- `backend/domain/hh_integration/importer.py`
- `tests/test_hh_integration_foundation.py`

**Комментарии / явные подсказки в файле:**
- Persistence services for direct HH integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_integration/summary.py`

**Тип:** Domain-модуль
**Строк кода:** ~178
**Назначение:** Domain-модуль `summary`.

**Ключевые функции:**
- `_serialize_hh_action()` — строка ~17
- `_resume_title()` — строка ~29
- `_resume_updated_at()` — строка ~37
- `build_candidate_hh_summary()` — строка ~42

**Зависимости (локальные импорты):**
- `backend/domain/hh_integration/models.py`

**Используется в:**
- `backend/apps/admin_ui/routers/api.py`

**Комментарии / явные подсказки в файле:**
- Read models for HH-linked candidate summaries.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_sync/__init__.py`

**Тип:** Domain-модуль
**Строк кода:** ~2
**Назначение:** Domain-модуль `__init__`.

**Комментарии / явные подсказки в файле:**
- hh.ru integration: status sync, resume resolve, and audit logging.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_sync/dispatcher.py`

**Тип:** Domain-модуль
**Строк кода:** ~103
**Назначение:** Domain-модуль `dispatcher`.

**Ключевые функции:**
- `dispatch_hh_status_sync()` — строка ~19

**Зависимости (локальные импорты):**
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/hh_sync/mapping.py`
- `backend/domain/hh_sync/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_ui/services/candidates.py`
- `tests/test_hh_sync.py`

**Комментарии / явные подсказки в файле:**
- Dispatch hh.ru sync events to the outbox for processing via n8n.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_sync/mapping.py`

**Тип:** Domain-модуль
**Строк кода:** ~42
**Назначение:** Domain-модуль `mapping`.

**Ключевые функции:**
- `get_hh_target_status()` — строка ~27
- `should_sync_status()` — строка ~32

**Зависимости (локальные импорты):**
- `backend/domain/candidates/status.py`

**Используется в:**
- `backend/domain/hh_sync/dispatcher.py`
- `tests/test_hh_sync.py`

**Комментарии / явные подсказки в файле:**
- Status mapping between RecruiterSmart and hh.ru negotiation statuses.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_sync/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~45
**Назначение:** Domain-модуль `models`.

**Классы:**
- `HHSyncLog` — строка ~14

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/domain/hh_sync/dispatcher.py`
- `backend/domain/hh_sync/resolver.py`
- `backend/domain/hh_sync/worker.py`
- `tests/test_hh_sync.py`

**Комментарии / явные подсказки в файле:**
- SQLAlchemy ORM model for hh_sync_log table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_sync/resolver.py`

**Тип:** Domain-модуль
**Строк кода:** ~97
**Назначение:** Domain-модуль `resolver`.

**Ключевые функции:**
- `parse_resume_id()` — строка ~22
- `request_resolve_negotiation()` — строка ~37

**Зависимости (локальные импорты):**
- `backend/domain/hh_sync/models.py`
- `backend/domain/models.py`

**Используется в:**
- `tests/test_hh_sync.py`

**Комментарии / явные подсказки в файле:**
- Parse hh.ru resume URLs and resolve negotiation IDs via n8n webhook.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/hh_sync/worker.py`

**Тип:** Domain-модуль
**Строк кода:** ~238
**Назначение:** Domain-модуль `worker`.

**Ключевые функции:**
- `process_hh_outbox_entry()` — строка ~23
- `_log_error()` — строка ~90
- `handle_sync_callback()` — строка ~109
- `handle_resolve_callback()` — строка ~169

**Зависимости (локальные импорты):**
- `backend/domain/candidates/models.py`
- `backend/domain/hh_sync/models.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_api/hh_sync.py`
- `tests/test_hh_sync.py`

**Комментарии / явные подсказки в файле:**
- Worker for processing hh.ru outbox entries via n8n webhooks.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~1250
**Назначение:** Domain-модуль `models`.

**Классы:**
- `Recruiter` — строка ~113
- `City` — строка ~146
- `RecruiterPlanEntry` — строка ~222
- `CalendarTask` — строка ~242
- `SlotStatus` — строка ~304
- `SlotAssignmentStatus` — строка ~314
- `RescheduleRequestStatus` — строка ~325
- `SlotStatusTransitionError` — строка ~332
- `Slot` — строка ~377
- `SlotReservationLock` — строка ~531
- `SlotReminderJob` — строка ~548
- `SlotAssignment` — строка ~573
- `RescheduleRequest` — строка ~641
- `ActionToken` — строка ~691
- `MessageLog` — строка ~716
- `TestQuestion` — строка ~747
- `Vacancy` — строка ~780
- `CityReminderPolicy` — строка ~813
- `BotRuntimeConfig` — строка ~841
- `NotificationLog` — строка ~857

**Ключевые функции:**
- `validate_timezone_name()` — строка ~41
- `validate_slot_duration()` — строка ~71
- `_set_city_owner()` — строка ~292
- `_clear_city_owner()` — строка ~299
- `normalize_slot_status()` — строка ~336
- `enforce_slot_transition()` — строка ~343
- `_normalize_slot_start()` — строка ~471
- `_enforce_slot_overlap()` — строка ~480

**Зависимости (локальные импорты):**
- `backend/core/sanitizers.py`
- `backend/core/timezone_service.py`
- `backend/domain/base.py`
- `backend/domain/cities/models.py`

**Используется в:**
- `backend/apps/admin_api/admin.py`
- `backend/apps/admin_api/webapp/routers.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/routers/ai.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/auth.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/content_api.py`
- `backend/apps/admin_ui/routers/profile_api.py`
- `backend/apps/admin_ui/routers/recruiters_api_example.py`
- `backend/apps/admin_ui/routers/regions.py`
- `backend/apps/admin_ui/routers/reschedule_requests.py`
- `backend/apps/admin_ui/routers/slot_assignments.py`
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/builder_graph.py`
- `backend/apps/admin_ui/services/calendar_events.py`
- `backend/apps/admin_ui/services/calendar_tasks.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/repositories.py`

**Тип:** Domain-модуль
**Строк кода:** ~1583
**Назначение:** Domain-модуль `repositories`.

**Классы:**
- `ReservationResult` — строка ~505
- `OutboxItem` — строка ~511
- `CandidateConfirmationResult` — строка ~527

**Ключевые функции:**
- `slot_status_free_clause()` — строка ~54
- `slot_status_free_sql()` — строка ~59
- `_to_aware_utc()` — строка ~63
- `get_active_recruiters()` — строка ~69
- `get_active_recruiters_for_city()` — строка ~77
- `get_candidate_cities()` — строка ~127
- `get_recruiter()` — строка ~196
- `get_recruiter_by_chat_id()` — строка ~201
- `get_recruiter_agenda_by_chat_id()` — строка ~209
- `get_city_by_name()` — строка ~243
- `_normalize_city_part()` — строка ~253
- `_city_variants()` — строка ~265
- `find_city_by_plain_name()` — строка ~280
- `_get_city_lookup()` — строка ~296
- `resolve_city_id_and_tz_by_plain_name()` — строка ~342
- `city_has_available_slots()` — строка ~362
- `get_city()` — строка ~381
- `get_free_slots_by_recruiter()` — строка ~391
- `get_recruiters_free_slots_summary()` — строка ~418
- `get_slot()` — строка ~460
- `get_message_template()` — строка ~471
- `register_callback()` — строка ~532
- `_log_candidate_clause()` — строка ~554
- `_outbox_candidate_clause()` — строка ~560
- `notification_log_exists()` — строка ~566

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/sanitizers.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/services.py`
- `backend/domain/candidates/status.py`
- `backend/domain/candidates/status_service.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/apps/admin_api/webapp/routers.py`
- `backend/apps/admin_ui/background_tasks.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/services/candidate_chat_threads.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/cities.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/notifications_ops.py`
- `backend/apps/admin_ui/services/recruiter_access.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/services/slots/bot.py`
- `backend/apps/bot/city_registry.py`
- `backend/apps/bot/handlers/interview.py`
- `backend/apps/bot/keyboards.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/slot_assignment_flow.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/simulator/__init__.py`

**Тип:** Domain-модуль
**Строк кода:** ~4
**Назначение:** Domain-модуль `__init__`.

**Зависимости (локальные импорты):**
- `backend/domain/simulator/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/simulator/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~64
**Назначение:** Domain-модуль `models`.

**Классы:**
- `SimulatorRun` — строка ~10
- `SimulatorStep` — строка ~37

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/apps/admin_ui/routers/simulator.py`
- `backend/core/bootstrap.py`
- `backend/domain/simulator/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/slot_assignment_service.py`

**Тип:** Domain-модуль
**Строк кода:** ~1119
**Назначение:** Domain-модуль `slot_assignment_service`.

**Классы:**
- `ServiceResult` — строка ~57

**Ключевые функции:**
- `_now()` — строка ~65
- `_resolve_candidate_tg_id()` — строка ~69
- `cancel_active_interview_slots_for_candidate()` — строка ~73
- `_create_action_token()` — строка ~185
- `_invalidate_action_tokens()` — строка ~202
- `_consume_action_token()` — строка ~212
- `_peek_action_token()` — строка ~232
- `create_slot_assignment()` — строка ~250
- `confirm_slot_assignment()` — строка ~489
- `request_reschedule()` — строка ~566
- `begin_reschedule_request()` — строка ~729
- `approve_reschedule()` — строка ~787
- `propose_alternative()` — строка ~915
- `decline_reschedule()` — строка ~1058

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`
- `backend/domain/slot_service.py`

**Используется в:**
- `backend/apps/admin_api/slot_assignments.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/candidates.py`
- `backend/apps/admin_ui/routers/slot_assignments.py`
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/bot/slot_assignment_flow.py`
- `tests/test_admin_candidate_schedule_slot.py`
- `tests/test_slot_assignment_slot_sync.py`

**Комментарии / явные подсказки в файле:**
- Slot assignment flow services (offer/confirm/reschedule) with action tokens.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/slot_service.py`

**Тип:** Domain-модуль
**Строк кода:** ~117
**Назначение:** Domain-модуль `slot_service`.

**Классы:**
- `SlotValidationError` — строка ~38

**Ключевые функции:**
- `ensure_slot_not_in_past()` — строка ~42
- `reserve_slot()` — строка ~65
- `approve_slot()` — строка ~95
- `reject_slot()` — строка ~99
- `confirm_slot_by_candidate()` — строка ~103
- `get_slot()` — строка ~107
- `get_free_slots_by_recruiter()` — строка ~111
- `city_has_available_slots()` — строка ~115

**Зависимости (локальные импорты):**
- `backend/core/time_utils.py`
- `backend/domain/repositories.py`

**Используется в:**
- `backend/apps/admin_api/webapp/routers.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/routers/slots.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/bot/services.py`
- `backend/domain/slot_assignment_service.py`

**Комментарии / явные подсказки в файле:**
- Domain-level slot operations extracted from bot services.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/template_contexts.py`

**Тип:** Domain-модуль
**Строк кода:** ~48
**Назначение:** Domain-модуль `template_contexts`.

**Ключевые функции:**
- `get_context_variables()` — строка ~36

**Используется в:**
- `backend/apps/admin_ui/routers/content_api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/template_stages.py`

**Тип:** Domain-модуль
**Строк кода:** ~89
**Назначение:** Domain-модуль `template_stages`.

**Классы:**
- `TemplateStage` — строка ~8

**Используется в:**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/routers/cities.py`
- `backend/apps/admin_ui/services/message_templates_presets.py`
- `backend/apps/bot/defaults.py`
- `tests/test_bot_template_copy_quality.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/test_questions/__init__.py`

**Тип:** Domain-модуль
**Строк кода:** ~6
**Назначение:** Domain-модуль `__init__`.

**Зависимости (локальные импорты):**
- `backend/domain/test_questions/services.py`

**Используется в:**
- `backend/apps/bot/config.py`

**Комментарии / явные подсказки в файле:**
- Helpers for working with test questions.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/test_questions/services.py`

**Тип:** Domain-модуль
**Строк кода:** ~125
**Назначение:** Domain-модуль `services`.

**Ключевые функции:**
- `load_test_questions()` — строка ~16
- `load_all_test_questions()` — строка ~49
- `_format_question()` — строка ~78

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/tests/models.py`

**Используется в:**
- `backend/domain/test_questions/__init__.py`

**Комментарии / явные подсказки в файле:**
- Synchronous helpers for reading question bank entries.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/tests/bootstrap.py`

**Тип:** Domain-модуль
**Строк кода:** ~212
**Назначение:** Domain-модуль `bootstrap`.

**Ключевые функции:**
- `bootstrap_test_questions()` — строка ~139

**Зависимости (локальные импорты):**
- `backend/domain/tests/models.py`

**Используется в:**
- `backend/apps/admin_ui/app.py`
- `backend/apps/bot/config.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/domain/tests/models.py`

**Тип:** Domain-модуль
**Строк кода:** ~58
**Назначение:** Domain-модуль `models`.

**Классы:**
- `Test` — строка ~7
- `Question` — строка ~22
- `AnswerOption` — строка ~44

**Зависимости (локальные импорты):**
- `backend/domain/base.py`

**Используется в:**
- `backend/apps/admin_ui/services/builder_graph.py`
- `backend/apps/admin_ui/services/questions.py`
- `backend/apps/admin_ui/services/test_builder_preview.py`
- `backend/apps/admin_ui/views/tests.py`
- `backend/domain/test_questions/services.py`
- `backend/domain/tests/bootstrap.py`
- `scripts/seed_tests.py`
- `tests/test_questions_reorder_api.py`
- `tests/test_test_builder_graph_api.py`
- `tests/test_test_builder_graph_preview_api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/repositories/__init__.py`

**Тип:** Репозиторий
**Строк кода:** ~18
**Назначение:** Репозиторий доступа к данным `__init__`.

**Зависимости (локальные импорты):**
- `backend/repositories/city.py`
- `backend/repositories/recruiter.py`
- `backend/repositories/slot.py`
- `backend/repositories/template.py`
- `backend/repositories/user.py`

**Используется в:**
- `backend/core/uow.py`

**Комментарии / явные подсказки в файле:**
- Repository implementations for domain models.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/repositories/city.py`

**Тип:** Репозиторий
**Строк кода:** ~69
**Назначение:** Репозиторий доступа к данным `city`.

**Классы:**
- `CityRepository` — строка ~15

**Зависимости (локальные импорты):**
- `backend/core/repository/base.py`
- `backend/core/result.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/repositories/__init__.py`

**Комментарии / явные подсказки в файле:**
- City repository implementation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/repositories/recruiter.py`

**Тип:** Репозиторий
**Строк кода:** ~187
**Назначение:** Репозиторий доступа к данным `recruiter`.

**Классы:**
- `RecruiterRepository` — строка ~18

**Зависимости (локальные импорты):**
- `backend/core/cache.py`
- `backend/core/cache_decorators.py`
- `backend/core/repository/base.py`
- `backend/core/result.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/repositories/__init__.py`

**Комментарии / явные подсказки в файле:**
- Recruiter repository implementation with caching support.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/repositories/slot.py`

**Тип:** Репозиторий
**Строк кода:** ~174
**Назначение:** Репозиторий доступа к данным `slot`.

**Классы:**
- `SlotRepository` — строка ~20

**Зависимости (локальные импорты):**
- `backend/core/cache.py`
- `backend/core/cache_decorators.py`
- `backend/core/query_optimization.py`
- `backend/core/repository/base.py`
- `backend/core/result.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/repositories/__init__.py`
- `tests/test_cache_integration.py`

**Комментарии / явные подсказки в файле:**
- Slot repository implementation with caching and query optimization.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/repositories/template.py`

**Тип:** Репозиторий
**Строк кода:** ~43
**Назначение:** Репозиторий доступа к данным `template`.

**Классы:**
- `MessageTemplateRepository` — строка ~15

**Зависимости (локальные импорты):**
- `backend/core/repository/base.py`
- `backend/core/result.py`
- `backend/domain/models.py`

**Используется в:**
- `backend/repositories/__init__.py`

**Комментарии / явные подсказки в файле:**
- Message template repository implementation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/repositories/user.py`

**Тип:** Репозиторий
**Строк кода:** ~152
**Назначение:** Репозиторий доступа к данным `user`.

**Классы:**
- `UserRepository` — строка ~15
- `TestResultRepository` — строка ~73
- `AutoMessageRepository` — строка ~112

**Зависимости (локальные импорты):**
- `backend/core/repository/base.py`
- `backend/core/result.py`
- `backend/domain/candidates/models.py`

**Используется в:**
- `backend/repositories/__init__.py`

**Комментарии / явные подсказки в файле:**
- User and related entities repository implementation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

## 3.7 Migrations

### `backend/migrations/versions/0001_initial_schema.py`

**Тип:** Миграция
**Строк кода:** ~193
**Назначение:** Alembic-миграция `0001_initial_schema`.

**Ключевые функции:**
- `_define_tables()` — строка ~11
- `upgrade()` — строка ~183
- `downgrade()` — строка ~189

**Комментарии / явные подсказки в файле:**
- Create core database tables.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0002_seed_defaults.py`

**Тип:** Миграция
**Строк кода:** ~64
**Назначение:** Alembic-миграция `0002_seed_defaults`.

**Ключевые функции:**
- `_table()` — строка ~18
- `_ensure_entries()` — строка ~23
- `upgrade()` — строка ~33
- `downgrade()` — строка ~61

**Зависимости (локальные импорты):**
- `backend/domain/default_data.py`

**Комментарии / явные подсказки в файле:**
- Seed default cities, recruiters and test questions.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0003_add_slot_interview_outcome.py`

**Тип:** Миграция
**Строк кода:** ~30
**Назначение:** Alembic-миграция `0003_add_slot_interview_outcome`.

**Ключевые функции:**
- `_column_exists()` — строка ~15
- `upgrade()` — строка ~20
- `downgrade()` — строка ~26

**Комментарии / явные подсказки в файле:**
- Add interview outcome to slots

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0004_add_slot_bot_markers.py`

**Тип:** Миграция
**Строк кода:** ~36
**Назначение:** Alembic-миграция `0004_add_slot_bot_markers`.

**Ключевые функции:**
- `_column_exists()` — строка ~15
- `upgrade()` — строка ~20
- `downgrade()` — строка ~31

**Комментарии / явные подсказки в файле:**
- Add bot dispatch markers to slots

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0005_add_city_profile_fields.py`

**Тип:** Миграция
**Строк кода:** ~40
**Назначение:** Alembic-миграция `0005_add_city_profile_fields`.

**Ключевые функции:**
- `_column_exists()` — строка ~16
- `upgrade()` — строка ~21
- `downgrade()` — строка ~34

**Комментарии / явные подсказки в файле:**
- Add profile fields to cities.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0006_add_slots_recruiter_start_index.py`

**Тип:** Миграция
**Строк кода:** ~30
**Назначение:** Alembic-миграция `0006_add_slots_recruiter_start_index`.

**Ключевые функции:**
- `upgrade()` — строка ~18
- `downgrade()` — строка ~27

**Комментарии / явные подсказки в файле:**
- Add composite index on slots recruiter and start time.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0007_prevent_duplicate_slot_reservations.py`

**Тип:** Миграция
**Строк кода:** ~84
**Назначение:** Alembic-миграция `0007_prevent_duplicate_slot_reservations`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~79

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Prevent duplicate reservations per recruiter.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0008_add_slot_reminder_jobs.py`

**Тип:** Миграция
**Строк кода:** ~53
**Назначение:** Alembic-миграция `0008_add_slot_reminder_jobs`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~50

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add slot reminder jobs table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0009_add_missing_indexes.py`

**Тип:** Миграция
**Строк кода:** ~44
**Назначение:** Alembic-миграция `0009_add_missing_indexes`.

**Ключевые функции:**
- `upgrade()` — строка ~17
- `downgrade()` — строка ~35

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add indexes for candidate and auto message lookups.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0010_add_notification_logs.py`

**Тип:** Миграция
**Строк кода:** ~63
**Назначение:** Alembic-миграция `0010_add_notification_logs`.

**Ключевые функции:**
- `upgrade()` — строка ~17
- `downgrade()` — строка ~53

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Introduce notification and callback logs, extend slot status column.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0011_add_candidate_binding_to_notification_logs.py`

**Тип:** Миграция
**Строк кода:** ~82
**Назначение:** Alembic-миграция `0011_add_candidate_binding_to_notification_logs`.

**Ключевые функции:**
- `upgrade()` — строка ~23
- `downgrade()` — строка ~60

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add candidate_tg_id to notification_logs and update unique constraint.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0012_update_slots_candidate_recruiter_index.py`

**Тип:** Миграция
**Строк кода:** ~55
**Назначение:** Alembic-миграция `0012_update_slots_candidate_recruiter_index`.

**Ключевые функции:**
- `upgrade()` — строка ~21
- `downgrade()` — строка ~39

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Update slots unique index to include confirmed_by_candidate status.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0013_enhance_notification_logs.py`

**Тип:** Миграция
**Строк кода:** ~78
**Назначение:** Alembic-миграция `0013_enhance_notification_logs`.

**Ключевые функции:**
- `upgrade()` — строка ~24
- `downgrade()` — строка ~60

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Enhance notification_logs with retry/status tracking fields.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0014_notification_outbox_and_templates.py`

**Тип:** Миграция
**Строк кода:** ~212
**Назначение:** Alembic-миграция `0014_notification_outbox_and_templates`.

**Ключевые функции:**
- `upgrade()` — строка ~24
- `downgrade()` — строка ~200

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Create message_templates and outbox_notifications tables.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0015_add_kpi_weekly_table.py`

**Тип:** Миграция
**Строк кода:** ~63
**Назначение:** Alembic-миграция `0015_add_kpi_weekly_table`.

**Ключевые функции:**
- `upgrade()` — строка ~11
- `downgrade()` — строка ~56

**Комментарии / явные подсказки в файле:**
- Add weekly KPI snapshot table and supporting indexes.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0015_recruiter_city_links.py`

**Тип:** Миграция
**Строк кода:** ~78
**Назначение:** Alembic-миграция `0015_recruiter_city_links`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~60

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Introduce recruiter-to-city link table for managing assignments.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0016_add_slot_interview_feedback.py`

**Тип:** Миграция
**Строк кода:** ~31
**Назначение:** Alembic-миграция `0016_add_slot_interview_feedback`.

**Ключевые функции:**
- `_column_exists()` — строка ~16
- `upgrade()` — строка ~21
- `downgrade()` — строка ~27

**Комментарии / явные подсказки в файле:**
- Add interview feedback column to slots

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0016_add_slot_timezone.py`

**Тип:** Миграция
**Строк кода:** ~37
**Назначение:** Alembic-миграция `0016_add_slot_timezone`.

**Ключевые функции:**
- `_column_exists()` — строка ~16
- `upgrade()` — строка ~24
- `downgrade()` — строка ~34

**Комментарии / явные подсказки в файле:**
- Add timezone name to slots.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0017_bot_message_logs.py`

**Тип:** Миграция
**Строк кода:** ~36
**Назначение:** Alembic-миграция `0017_bot_message_logs`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~34

**Комментарии / явные подсказки в файле:**
- Create bot_message_logs table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0017_recruiter_capacity_and_pipeline.py`

**Тип:** Миграция
**Строк кода:** ~26
**Назначение:** Alembic-миграция `0017_recruiter_capacity_and_pipeline`.

**Ключевые функции:**
- `upgrade()` — строка ~13
- `downgrade()` — строка ~23

**Комментарии / явные подсказки в файле:**
- Restore missing recruiter capacity and pipeline migration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0018_candidate_report_urls.py`

**Тип:** Миграция
**Строк кода:** ~24
**Назначение:** Alembic-миграция `0018_candidate_report_urls`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~19

**Комментарии / явные подсказки в файле:**
- Add report URLs to candidate profiles.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0018_slots_candidate_fields.py`

**Тип:** Миграция
**Строк кода:** ~54
**Назначение:** Alembic-миграция `0018_slots_candidate_fields`.

**Ключевые функции:**
- `_column_exists()` — строка ~17
- `upgrade()` — строка ~22
- `downgrade()` — строка ~42

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0019_fix_notification_log_unique_index.py`

**Тип:** Миграция
**Строк кода:** ~68
**Назначение:** Alembic-миграция `0019_fix_notification_log_unique_index`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~53

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Fix notification_logs unique index to include candidate_tg_id.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0020_add_user_username.py`

**Тип:** Миграция
**Строк кода:** ~56
**Назначение:** Alembic-миграция `0020_add_user_username`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~43

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add username field to users table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0021_update_slot_unique_index_include_purpose.py`

**Тип:** Миграция
**Строк кода:** ~68
**Назначение:** Alembic-миграция `0021_update_slot_unique_index_include_purpose`.

**Ключевые функции:**
- `upgrade()` — строка ~32
- `downgrade()` — строка ~51

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Update slot unique index to include purpose field.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0022_add_candidate_status.py`

**Тип:** Миграция
**Строк кода:** ~82
**Назначение:** Alembic-миграция `0022_add_candidate_status`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~66

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add candidate_status and status_changed_at to users table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0023_add_interview_notes.py`

**Тип:** Миграция
**Строк кода:** ~38
**Назначение:** Alembic-миграция `0023_add_interview_notes`.

**Ключевые функции:**
- `upgrade()` — строка ~17
- `downgrade()` — строка ~35

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add interview_notes table for storing interview scripts and notes.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0024_remove_legacy_24h_reminders.py`

**Тип:** Миграция
**Строк кода:** ~71
**Назначение:** Alembic-миграция `0024_remove_legacy_24h_reminders`.

**Ключевые функции:**
- `upgrade()` — строка ~39
- `downgrade()` — строка ~68

**Комментарии / явные подсказки в файле:**
- Delete legacy 24-hour reminders from scheduler and outbox.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0025_add_intro_day_details.py`

**Тип:** Миграция
**Строк кода:** ~37
**Назначение:** Alembic-миграция `0025_add_intro_day_details`.

**Ключевые функции:**
- `upgrade()` — строка ~15
- `downgrade()` — строка ~25

**Комментарии / явные подсказки в файле:**
- Add intro day details fields to slots.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0026_add_recruiter_candidate_confirmed_template.py`

**Тип:** Миграция
**Строк кода:** ~63
**Назначение:** Alembic-миграция `0026_add_recruiter_candidate_confirmed_template`.

**Ключевые функции:**
- `upgrade()` — строка ~23
- `downgrade()` — строка ~53

**Комментарии / явные подсказки в файле:**
- Ensure recruiter notification template exists.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0027_add_manual_slot_audit_log.py`

**Тип:** Миграция
**Строк кода:** ~66
**Назначение:** Alembic-миграция `0027_add_manual_slot_audit_log`.

**Ключевые функции:**
- `upgrade()` — строка ~17
- `downgrade()` — строка ~63

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add manual_slot_audit_logs table for audit trail.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0028_add_candidate_profile_fields.py`

**Тип:** Миграция
**Строк кода:** ~24
**Назначение:** Alembic-миграция `0028_add_candidate_profile_fields`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~19

**Комментарии / явные подсказки в файле:**
- Add quick-create profile fields to users.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0029_add_manual_slot_availability.py`

**Тип:** Миграция
**Строк кода:** ~39
**Назначение:** Alembic-миграция `0029_add_manual_slot_availability`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~28

**Комментарии / явные подсказки в файле:**
- Add manual slot availability fields to users.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0030_add_telegram_identity_fields.py`

**Тип:** Миграция
**Строк кода:** ~58
**Назначение:** Alembic-миграция `0030_add_telegram_identity_fields`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~50

**Комментарии / явные подсказки в файле:**
- Store Telegram identity metadata for candidates.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0031_add_chat_messages.py`

**Тип:** Миграция
**Строк кода:** ~69
**Назначение:** Alembic-миграция `0031_add_chat_messages`.

**Ключевые функции:**
- `upgrade()` — строка ~26
- `downgrade()` — строка ~65

**Комментарии / явные подсказки в файле:**
- Add chat messages table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0032_add_conversation_mode.py`

**Тип:** Миграция
**Строк кода:** ~38
**Назначение:** Alembic-миграция `0032_add_conversation_mode`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~33

**Комментарии / явные подсказки в файле:**
- Add conversation mode fields for candidates.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0033_add_intro_decline_reason.py`

**Тип:** Миграция
**Строк кода:** ~27
**Назначение:** Alembic-миграция `0033_add_intro_decline_reason`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~24

**Комментарии / явные подсказки в файле:**
- Add intro decline reason field to users.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0034_message_templates_city_support.py`

**Тип:** Миграция
**Строк кода:** ~145
**Назначение:** Alembic-миграция `0034_message_templates_city_support`.

**Ключевые функции:**
- `upgrade()` — строка ~24
- `downgrade()` — строка ~142

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add city support to message_templates and create history table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0035_add_analytics_events_and_jinja_flag.py`

**Тип:** Миграция
**Строк кода:** ~97
**Назначение:** Alembic-миграция `0035_add_analytics_events_and_jinja_flag`.

**Ключевые функции:**
- `upgrade()` — строка ~23
- `downgrade()` — строка ~75

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add analytics_events table and use_jinja flag to message_templates.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0036_ensure_candidate_status_enum_values.py`

**Тип:** Миграция
**Строк кода:** ~97
**Назначение:** Alembic-миграция `0036_ensure_candidate_status_enum_values`.

**Ключевые функции:**
- `upgrade()` — строка ~43
- `downgrade()` — строка ~87

**Комментарии / явные подсказки в файле:**
- Ensure candidate_status_enum has all values from Python Enum.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0037_recruiter_portal_auth.py`

**Тип:** Миграция
**Строк кода:** ~118
**Назначение:** Alembic-миграция `0037_recruiter_portal_auth`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~100

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add recruiter portal auth tables and candidate assignment.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0038_recruiter_user_profile_link.py`

**Тип:** Миграция
**Строк кода:** ~50
**Назначение:** Alembic-миграция `0038_recruiter_user_profile_link`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~45

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Link recruiter_users to recruiters profile.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0039_allow_multiple_recruiters_per_city.py`

**Тип:** Миграция
**Строк кода:** ~37
**Назначение:** Alembic-миграция `0039_allow_multiple_recruiters_per_city`.

**Ключевые функции:**
- `upgrade()` — строка ~21
- `downgrade()` — строка ~28

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Allow attaching multiple recruiters to a single city.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0040_add_audit_log_table.py`

**Тип:** Миграция
**Строк кода:** ~63
**Назначение:** Alembic-миграция `0040_add_audit_log_table`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~58

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add generic audit_log table for admin actions.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0041_add_slot_overlap_exclusion_constraint.py`

**Тип:** Миграция
**Строк кода:** ~106
**Назначение:** Alembic-миграция `0041_add_slot_overlap_exclusion_constraint`.

**Ключевые функции:**
- `upgrade()` — строка ~29
- `downgrade()` — строка ~96

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add exclusion constraint to prevent overlapping slots for the same recruiter.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0042_add_comprehensive_slot_indexes.py`

**Тип:** Миграция
**Строк кода:** ~102
**Назначение:** Alembic-миграция `0042_add_comprehensive_slot_indexes`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~87

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add comprehensive indexes for slot queries optimization.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0043_add_candidate_uuid_and_lead_source.py`

**Тип:** Миграция
**Строк кода:** ~406
**Назначение:** Alembic-миграция `0043_add_candidate_uuid_and_lead_source`.

**Ключевые функции:**
- `_backfill_candidate_ids()` — строка ~19
- `_upgrade_users_sqlite()` — строка ~28
- `_upgrade_users()` — строка ~190
- `_upgrade_slots()` — строка ~221
- `_upgrade_slot_reservation_locks()` — строка ~252
- `_upgrade_invite_tokens()` — строка ~352
- `upgrade()` — строка ~380
- `downgrade()` — строка ~387

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add UUID candidate identity, source fields, and slot candidate linkage.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0044_add_lead_statuses_to_candidate_enum.py`

**Тип:** Миграция
**Строк кода:** ~85
**Назначение:** Alembic-миграция `0044_add_lead_statuses_to_candidate_enum`.

**Ключевые функции:**
- `upgrade()` — строка ~37
- `downgrade()` — строка ~83

**Комментарии / явные подсказки в файле:**
- Add lead-stage statuses to candidate_status_enum.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0045_add_candidate_responsible_recruiter.py`

**Тип:** Миграция
**Строк кода:** ~32
**Назначение:** Alembic-миграция `0045_add_candidate_responsible_recruiter`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~27

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add responsible recruiter reference for candidates.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0046_add_test2_invites_and_test_result_source.py`

**Тип:** Миграция
**Строк кода:** ~74
**Назначение:** Alembic-миграция `0046_add_test2_invites_and_test_result_source`.

**Ключевые функции:**
- `upgrade()` — строка ~19
- `downgrade()` — строка ~65

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add Test2 invite links and TestResult source column.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0047_fix_invite_tokens_identity.py`

**Тип:** Миграция
**Строк кода:** ~71
**Назначение:** Alembic-миграция `0047_fix_invite_tokens_identity`.

**Ключевые функции:**
- `_ensure_sequence_default()` — строка ~16
- `upgrade()` — строка ~56
- `downgrade()` — строка ~61

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Ensure invite token tables have auto-increment IDs on Postgres.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0048_fix_test2_invites_timezone_columns.py`

**Тип:** Миграция
**Строк кода:** ~68
**Назначение:** Alembic-миграция `0048_fix_test2_invites_timezone_columns`.

**Ключевые функции:**
- `_is_timestamptz()` — строка ~20
- `upgrade()` — строка ~36
- `downgrade()` — строка ~54

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Ensure Test2 invite timestamps use timezone-aware columns.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0049_allow_null_city_timezone.py`

**Тип:** Миграция
**Строк кода:** ~38
**Назначение:** Alembic-миграция `0049_allow_null_city_timezone`.

**Ключевые функции:**
- `upgrade()` — строка ~19
- `downgrade()` — строка ~29

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Allow nullable timezone for cities.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0050_align_slot_overlap_bounds_and_duration_default.py`

**Тип:** Миграция
**Строк кода:** ~108
**Назначение:** Alembic-миграция `0050_align_slot_overlap_bounds_and_duration_default`.

**Ключевые функции:**
- `_set_duration_default()` — строка ~30
- `upgrade()` — строка ~38
- `downgrade()` — строка ~88

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Align slot overlap constraint bounds and default slot duration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0051_enforce_slot_overlap_on_10min_windows.py`

**Тип:** Миграция
**Строк кода:** ~106
**Назначение:** Alembic-миграция `0051_enforce_slot_overlap_on_10min_windows`.

**Ключевые функции:**
- `upgrade()` — строка ~27
- `downgrade()` — строка ~75

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Enforce slot overlap check on fixed 10-minute windows.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0052_add_workflow_status_fields.py`

**Тип:** Миграция
**Строк кода:** ~49
**Назначение:** Alembic-миграция `0052_add_workflow_status_fields`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~42

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add workflow status fields for candidate state-machine.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0053_add_outbox_notification_indexes.py`

**Тип:** Миграция
**Строк кода:** ~65
**Назначение:** Alembic-миграция `0053_add_outbox_notification_indexes`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~59

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add indexes to outbox_notifications for efficient queue processing.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0054_restore_city_responsible_recruiter.py`

**Тип:** Миграция
**Строк кода:** ~50
**Назначение:** Alembic-миграция `0054_restore_city_responsible_recruiter`.

**Ключевые функции:**
- `upgrade()` — строка ~17
- `downgrade()` — строка ~47

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Restore city responsible recruiter column for ownership logic.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0055_add_performance_indexes.py`

**Тип:** Миграция
**Строк кода:** ~90
**Назначение:** Alembic-миграция `0055_add_performance_indexes`.

**Ключевые функции:**
- `upgrade()` — строка ~21
- `downgrade()` — строка ~81

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add performance indexes for slots and users tables.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0056_sync_workflow_status_from_legacy.py`

**Тип:** Миграция
**Строк кода:** ~75
**Назначение:** Alembic-миграция `0056_sync_workflow_status_from_legacy`.

**Ключевые функции:**
- `upgrade()` — строка ~40
- `downgrade()` — строка ~71

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Sync workflow_status from legacy candidate_status where NULL.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0057_auth_accounts.py`

**Тип:** Миграция
**Строк кода:** ~56
**Назначение:** Alembic-миграция `0057_auth_accounts`.

**Ключевые функции:**
- `upgrade()` — строка ~50
- `downgrade()` — строка ~54

**Комментарии / явные подсказки в файле:**
- Add auth_accounts table for web principals

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0058_add_recruiter_last_seen_at.py`

**Тип:** Миграция
**Строк кода:** ~40
**Назначение:** Alembic-миграция `0058_add_recruiter_last_seen_at`.

**Ключевые функции:**
- `_column_exists()` — строка ~15
- `upgrade()` — строка ~23
- `downgrade()` — строка ~34

**Комментарии / явные подсказки в файле:**
- Add recruiter last_seen_at for presence tracking.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0059_add_recruiter_plan_entries.py`

**Тип:** Миграция
**Строк кода:** ~66
**Назначение:** Alembic-миграция `0059_add_recruiter_plan_entries`.

**Ключевые функции:**
- `_table_exists()` — строка ~15
- `upgrade()` — строка ~23
- `downgrade()` — строка ~64

**Комментарии / явные подсказки в файле:**
- Add recruiter plan entries for manual city plan tracking.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0060_add_staff_messenger.py`

**Тип:** Миграция
**Строк кода:** ~171
**Назначение:** Alembic-миграция `0060_add_staff_messenger`.

**Ключевые функции:**
- `_table_exists()` — строка ~15
- `upgrade()` — строка ~23
- `downgrade()` — строка ~166

**Комментарии / явные подсказки в файле:**
- Add internal staff messenger tables (threads, messages, attachments).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0061_staff_message_tasks.py`

**Тип:** Миграция
**Строк кода:** ~82
**Назначение:** Alembic-миграция `0061_staff_message_tasks`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~75

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add staff message tasks and message types.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0062_slot_assignments.py`

**Тип:** Миграция
**Строк кода:** ~300
**Назначение:** Alembic-миграция `0062_slot_assignments`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~288

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add slot assignment flow tables and slot capacity.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0063_add_candidate_rejection_reason.py`

**Тип:** Миграция
**Строк кода:** ~29
**Назначение:** Alembic-миграция `0063_add_candidate_rejection_reason`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~25

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add rejection_reason to users table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0064_add_test_questions_tables.py`

**Тип:** Миграция
**Строк кода:** ~80
**Назначение:** Alembic-миграция `0064_add_test_questions_tables`.

**Ключевые функции:**
- `upgrade()` — строка ~11
- `downgrade()` — строка ~76

**Комментарии / явные подсказки в файле:**
- Add tests, questions, and answer_options tables.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0065_add_intro_day_template_to_city.py`

**Тип:** Миграция
**Строк кода:** ~17
**Назначение:** Alembic-миграция `0065_add_intro_day_template_to_city`.

**Ключевые функции:**
- `upgrade()` — строка ~11
- `downgrade()` — строка ~15

**Комментарии / явные подсказки в файле:**
- Add intro_day_template to City.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0066_add_city_experts_executives.py`

**Тип:** Миграция
**Строк кода:** ~44
**Назначение:** Alembic-миграция `0066_add_city_experts_executives`.

**Ключевые функции:**
- `upgrade()` — строка ~11
- `downgrade()` — строка ~41

**Комментарии / явные подсказки в файле:**
- Add CityExpert and CityExecutive.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0067_add_fk_indexes.py`

**Тип:** Миграция
**Строк кода:** ~27
**Назначение:** Alembic-миграция `0067_add_fk_indexes`.

**Ключевые функции:**
- `upgrade()` — строка ~11
- `downgrade()` — строка ~24

**Комментарии / явные подсказки в файле:**
- Add missing indexes on FK columns for query performance.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0068_add_template_description.py`

**Тип:** Миграция
**Строк кода:** ~26
**Назначение:** Alembic-миграция `0068_add_template_description`.

**Ключевые функции:**
- `upgrade()` — строка ~12
- `downgrade()` — строка ~20

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add description to message_templates.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0069_drop_legacy_templates.py`

**Тип:** Миграция
**Строк кода:** ~35
**Назначение:** Alembic-миграция `0069_drop_legacy_templates`.

**Ключевые функции:**
- `upgrade()` — строка ~12
- `downgrade()` — строка ~20

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Drop legacy templates table and city column.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0070_add_city_intro_fields.py`

**Тип:** Миграция
**Строк кода:** ~28
**Назначение:** Alembic-миграция `0070_add_city_intro_fields`.

**Ключевые функции:**
- `upgrade()` — строка ~12
- `downgrade()` — строка ~21

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add intro_address, contact_name, contact_phone to cities.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0071_add_slot_pending_candidate_status.py`

**Тип:** Миграция
**Строк кода:** ~49
**Назначение:** Alembic-миграция `0071_add_slot_pending_candidate_status`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~47

**Комментарии / явные подсказки в файле:**
- Add slot_pending to candidate_status_enum.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0072_add_bot_runtime_configs.py`

**Тип:** Миграция
**Строк кода:** ~33
**Назначение:** Alembic-миграция `0072_add_bot_runtime_configs`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~31

**Комментарии / явные подсказки в файле:**
- Add bot runtime configs table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0073_unify_test_question_sources.py`

**Тип:** Миграция
**Строк кода:** ~221
**Назначение:** Alembic-миграция `0073_unify_test_question_sources`.

**Ключевые функции:**
- `_bool_default()` — строка ~31
- `_parse_payload()` — строка ~38
- `upgrade()` — строка ~48
- `downgrade()` — строка ~208

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Unify legacy test_questions with tests/questions/answer_options schema.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0074_add_ai_outputs_and_logs.py`

**Тип:** Миграция
**Строк кода:** ~140
**Назначение:** Alembic-миграция `0074_add_ai_outputs_and_logs`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~136

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add AI Copilot cache and request log tables.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0075_add_kb_and_ai_chat.py`

**Тип:** Миграция
**Строк кода:** ~212
**Назначение:** Alembic-миграция `0075_add_kb_and_ai_chat`.

**Ключевые функции:**
- `upgrade()` — строка ~22
- `downgrade()` — строка ~206

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add knowledge base and AI agent chat tables.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0076_add_simulator_runs.py`

**Тип:** Миграция
**Строк кода:** ~124
**Назначение:** Alembic-миграция `0076_add_simulator_runs`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~121

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add simulator runs/steps tables for local scenario runner.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0077_add_detailization_entries.py`

**Тип:** Миграция
**Строк кода:** ~97
**Назначение:** Alembic-миграция `0077_add_detailization_entries`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~94

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add detailization_entries table for intro day reporting.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0078_add_vacancies.py`

**Тип:** Миграция
**Строк кода:** ~77
**Назначение:** Alembic-миграция `0078_add_vacancies`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~75

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add vacancies table and vacancy_id to test_questions.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0079_add_city_reminder_policies.py`

**Тип:** Миграция
**Строк кода:** ~58
**Назначение:** Alembic-миграция `0079_add_city_reminder_policies`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~56

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add city_reminder_policies table for per-city reminder configuration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0080_slot_overlap_per_purpose.py`

**Тип:** Миграция
**Строк кода:** ~111
**Назначение:** Alembic-миграция `0080_slot_overlap_per_purpose`.

**Ключевые функции:**
- `_ensure_slot_end_function()` — строка ~27
- `upgrade()` — строка ~43
- `downgrade()` — строка ~79

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Allow overlapping slots across different purposes for the same recruiter.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0081_add_detailization_soft_delete.py`

**Тип:** Миграция
**Строк кода:** ~45
**Назначение:** Alembic-миграция `0081_add_detailization_soft_delete`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~38

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add soft-delete flag to detailization entries.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0082_add_calendar_tasks.py`

**Тип:** Миграция
**Строк кода:** ~103
**Назначение:** Alembic-миграция `0082_add_calendar_tasks`.

**Ключевые функции:**
- `upgrade()` — строка ~20
- `downgrade()` — строка ~99

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add recruiter calendar tasks table for manual planning.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0083_sync_test1_question_bank.py`

**Тип:** Миграция
**Строк кода:** ~140
**Назначение:** Alembic-миграция `0083_sync_test1_question_bank`.

**Ключевые функции:**
- `_load_test1_question_ids()` — строка ~49
- `_sync_question_key()` — строка ~63
- `_load_option_texts()` — строка ~77
- `_replace_options()` — строка ~92
- `upgrade()` — строка ~119
- `downgrade()` — строка ~137

**Комментарии / явные подсказки в файле:**
- Sync legacy test1 questions with current bot question bank.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0084_allow_intro_day_parallel_slots.py`

**Тип:** Миграция
**Строк кода:** ~157
**Назначение:** Alembic-миграция `0084_allow_intro_day_parallel_slots`.

**Ключевые функции:**
- `_ensure_slot_end_function()` — строка ~29
- `_rebuild_active_unique_index_excluding_intro_day()` — строка ~47
- `_rebuild_active_unique_index_default()` — строка ~61
- `upgrade()` — строка ~74
- `downgrade()` — строка ~117

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Allow parallel intro-day slots at the same time.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0085_add_interview_script_feedback_and_hh_resume.py`

**Тип:** Миграция
**Строк кода:** ~189
**Назначение:** Alembic-миграция `0085_add_interview_script_feedback_and_hh_resume`.

**Ключевые функции:**
- `_add_kb_category_column()` — строка ~16
- `_create_candidate_hh_resumes()` — строка ~35
- `_create_interview_script_feedback()` — строка ~92
- `upgrade()` — строка ~171
- `downgrade()` — строка ~177

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add HH resume storage, interview-script feedback, and KB document category.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0086_update_interview_notification_templates.py`

**Тип:** Миграция
**Строк кода:** ~99
**Назначение:** Alembic-миграция `0086_update_interview_notification_templates`.

**Ключевые функции:**
- `_upsert_active_template()` — строка ~42
- `upgrade()` — строка ~89
- `downgrade()` — строка ~96

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Refresh interview notification templates for immediate and 2h reminders.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0087_update_t1_done_template.py`

**Тип:** Миграция
**Строк кода:** ~77
**Назначение:** Alembic-миграция `0087_update_t1_done_template`.

**Ключевые функции:**
- `_upsert_active_template()` — строка ~21
- `upgrade()` — строка ~68
- `downgrade()` — строка ~74

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Update t1_done template text after Test 1 completion.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0088_upgrade_candidate_template_texts.py`

**Тип:** Миграция
**Строк кода:** ~134
**Назначение:** Alembic-миграция `0088_upgrade_candidate_template_texts`.

**Ключевые функции:**
- `_upsert_active_template()` — строка ~76
- `upgrade()` — строка ~124
- `downgrade()` — строка ~131

**Зависимости (локальные импорты):**
- `backend/apps/bot/defaults.py`
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Upgrade candidate-facing Telegram templates with full production copy.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0089_add_hh_sync_fields_and_log.py`

**Тип:** Миграция
**Строк кода:** ~120
**Назначение:** Alembic-миграция `0089_add_hh_sync_fields_and_log`.

**Ключевые функции:**
- `_add_hh_fields_to_users()` — строка ~16
- `_create_hh_sync_log()` — строка ~48
- `upgrade()` — строка ~106
- `downgrade()` — строка ~111

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add hh.ru sync fields to users table and create hh_sync_log table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0090_add_messenger_fields.py`

**Тип:** Миграция
**Строк кода:** ~69
**Назначение:** Alembic-миграция `0090_add_messenger_fields`.

**Ключевые функции:**
- `_add_messenger_fields_to_users()` — строка ~22
- `_add_channel_to_outbox()` — строка ~43
- `upgrade()` — строка ~54
- `downgrade()` — строка ~59

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add messenger platform and VK Max user ID fields to users table.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0091_add_hh_integration_foundation.py`

**Тип:** Миграция
**Строк кода:** ~196
**Назначение:** Alembic-миграция `0091_add_hh_integration_foundation`.

**Ключевые функции:**
- `_tables()` — строка ~14
- `upgrade()` — строка ~184
- `downgrade()` — строка ~191

**Комментарии / явные подсказки в файле:**
- Add foundation tables for direct HeadHunter integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0092_allow_unbound_hh_vacancy_bindings.py`

**Тип:** Миграция
**Строк кода:** ~38
**Назначение:** Alembic-миграция `0092_allow_unbound_hh_vacancy_bindings`.

**Ключевые функции:**
- `upgrade()` — строка ~14
- `downgrade()` — строка ~24

**Комментарии / явные подсказки в файле:**
- Allow storing HH vacancies before they are linked to internal vacancies.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0093_reschedule_windows_and_candidate_chat_reads.py`

**Тип:** Миграция
**Строк кода:** ~309
**Назначение:** Alembic-миграция `0093_reschedule_windows_and_candidate_chat_reads`.

**Ключевые функции:**
- `_column_nullable()` — строка ~16
- `_ensure_reschedule_indexes()` — строка ~24
- `_rebuild_reschedule_requests_sqlite()` — строка ~50
- `_upgrade_reschedule_requests()` — строка ~183
- `_create_candidate_chat_reads()` — строка ~210
- `upgrade()` — строка ~274
- `downgrade()` — строка ~279

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Support free-form reschedule requests and candidate chat read states.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0094_add_candidate_chat_archive_state.py`

**Тип:** Миграция
**Строк кода:** ~121
**Назначение:** Alembic-миграция `0094_add_candidate_chat_archive_state`.

**Ключевые функции:**
- `_rebuild_candidate_chat_reads_sqlite()` — строка ~16
- `upgrade()` — строка ~87
- `downgrade()` — строка ~105

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add archive state for candidate chat threads.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0095_add_candidate_portal_journey.py`

**Тип:** Миграция
**Строк кода:** ~25
**Назначение:** Alembic-миграция `0095_add_candidate_portal_journey`.

**Ключевые функции:**
- `upgrade()` — строка ~19
- `downgrade()` — строка ~23

**Комментарии / явные подсказки в файле:**
- Compatibility shim for a locally stamped candidate portal revision.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0096_add_candidate_chat_workspaces.py`

**Тип:** Миграция
**Строк кода:** ~58
**Назначение:** Alembic-миграция `0096_add_candidate_chat_workspaces`.

**Ключевые функции:**
- `upgrade()` — строка ~16
- `downgrade()` — строка ~54

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add shared workspace state for candidate chat threads.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/0097_add_candidate_journey_archive_foundation.py`

**Тип:** Миграция
**Строк кода:** ~328
**Назначение:** Alembic-миграция `0097_add_candidate_journey_archive_foundation`.

**Ключевые функции:**
- `_add_column_if_missing()` — строка ~16
- `_create_candidate_journey_events()` — строка ~21
- `_ensure_candidate_journey_events_id_identity()` — строка ~44
- `_create_indexes()` — строка ~77
- `_backfill_users()` — строка ~108
- `_backfill_detailization()` — строка ~216
- `_backfill_slot_origins()` — строка ~235
- `_backfill_status_events()` — строка ~256
- `upgrade()` — строка ~302
- `downgrade()` — строка ~325

**Зависимости (локальные импорты):**
- `backend/migrations/utils.py`

**Комментарии / явные подсказки в файле:**
- Add candidate lifecycle, journey events, final outcomes, and reporting fields.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `backend/migrations/versions/__init__.py`

**Тип:** Миграция
**Строк кода:** ~2
**Назначение:** Alembic-миграция `__init__`.

**Комментарии / явные подсказки в файле:**
- Database schema migrations.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

## 3.8 Scripts / tools

### `bot.py`

**Тип:** Скрипт
**Строк кода:** ~22
**Назначение:** Операционный/утилитарный скрипт `bot`.

**Ключевые функции:**
- `run()` — строка ~12

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Комментарии / явные подсказки в файле:**
- CLI wrapper to launch the recruitment Telegram bot.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `conftest.py`

**Тип:** Скрипт
**Строк кода:** ~16
**Назначение:** Операционный/утилитарный скрипт `conftest`.

**Ключевые функции:**
- `pytest_addoption()` — строка ~4
- `redis_url()` — строка ~14

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `max_bot.py`

**Тип:** Скрипт
**Строк кода:** ~34
**Назначение:** Операционный/утилитарный скрипт `max_bot`.

**Ключевые функции:**
- `main()` — строка ~13

**Комментарии / явные подсказки в файле:**
- Entry point for VK Max bot webhook server.

**Состояние / проблемы:**
- console/print: 1

### `run_migrations.py`

**Тип:** Скрипт
**Строк кода:** ~14
**Назначение:** Операционный/утилитарный скрипт `run_migrations`.

**Зависимости (локальные импорты):**
- `backend/migrations/runner.py`

**Комментарии / явные подсказки в файле:**
- Apply database migrations to production/development database.

**Состояние / проблемы:**
- console/print: 3

### `scripts/check_candidate.py`

**Тип:** Скрипт
**Строк кода:** ~61
**Назначение:** Операционный/утилитарный скрипт `check_candidate`.

**Ключевые функции:**
- `check_candidate()` — строка ~15

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`

**Комментарии / явные подсказки в файле:**
- Check candidate details.

**Состояние / проблемы:**
- console/print: 20

### `scripts/check_failed_notifications.py`

**Тип:** Скрипт
**Строк кода:** ~87
**Назначение:** Операционный/утилитарный скрипт `check_failed_notifications`.

**Ключевые функции:**
- `check_failed()` — строка ~15

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Check failed notifications in detail.

**Состояние / проблемы:**
- console/print: 31

### `scripts/check_slot_2_notification.py`

**Тип:** Скрипт
**Строк кода:** ~87
**Назначение:** Операционный/утилитарный скрипт `check_slot_2_notification`.

**Ключевые функции:**
- `check_slot_notification()` — строка ~15

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Check if notification was created for slot ID 2.

**Состояние / проблемы:**
- console/print: 36

### `scripts/collect_ux.py`

**Тип:** Скрипт
**Строк кода:** ~293
**Назначение:** Операционный/утилитарный скрипт `collect_ux`.

**Классы:**
- `Event` — строка ~20
- `Session` — строка ~34

**Ключевые функции:**
- `parse_iso()` — строка ~58
- `load_events()` — строка ~68
- `iter_log_files()` — строка ~93
- `summarise_sessions()` — строка ~99
- `extract_element_label()` — строка ~130
- `write_csv_report()` — строка ~158
- `format_dt()` — строка ~202
- `write_markdown_report()` — строка ~208
- `main()` — строка ~268

**Комментарии / явные подсказки в файле:**
- Collect UX telemetry logs from previews/ux_logs into summary reports.

**Состояние / проблемы:**
- console/print: 5

### `scripts/dev_doctor.py`

**Тип:** Скрипт
**Строк кода:** ~136
**Назначение:** Операционный/утилитарный скрипт `dev_doctor`.

**Классы:**
- `CheckResult` — строка ~27

**Ключевые функции:**
- `format_status()` — строка ~37
- `check_python()` — строка ~41
- `_dist_name()` — строка ~59
- `check_module()` — строка ~64
- `check_session_secret()` — строка ~82
- `run_checks()` — строка ~102
- `main()` — строка ~110

**Комментарии / явные подсказки в файле:**
- Developer environment preflight checks.

**Состояние / проблемы:**
- console/print: 7

### `scripts/dev_server.py`

**Тип:** Скрипт
**Строк кода:** ~385
**Назначение:** Операционный/утилитарный скрипт `dev_server`.

**Классы:**
- `DevServerFatalError` — строка ~74
- `DevServer` — строка ~78

**Ключевые функции:**
- `parse_args()` — строка ~340
- `amain()` — строка ~362
- `main()` — строка ~373

**Комментарии / явные подсказки в файле:**
- Self-healing development server for the admin UI.

**Состояние / проблемы:**
- console/print: 9

### `scripts/diagnose_notifications.py`

**Тип:** Скрипт
**Строк кода:** ~132
**Назначение:** Операционный/утилитарный скрипт `diagnose_notifications`.

**Ключевые функции:**
- `diagnose()` — строка ~18

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Diagnostic script to check notification system health.

**Состояние / проблемы:**
- console/print: 39

### `scripts/diagnose_server.py`

**Тип:** Скрипт
**Строк кода:** ~99
**Назначение:** Операционный/утилитарный скрипт `diagnose_server`.

**Ключевые функции:**
- `diagnose_server()` — строка ~17

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/services.py`
- `backend/core/settings.py`

**Комментарии / явные подсказки в файле:**
- Diagnose server startup and notification system.

**Состояние / проблемы:**
- console/print: 34

### `scripts/e2e_notifications_sandbox.py`

**Тип:** Скрипт
**Строк кода:** ~284
**Назначение:** Операционный/утилитарный скрипт `e2e_notifications_sandbox`.

**Классы:**
- `TelegramSandbox` — строка ~53

**Ключевые функции:**
- `ensure_templates()` — строка ~112
- `seed_demo_entities()` — строка ~143
- `enqueue_notifications()` — строка ~181
- `fetch_logs()` — строка ~194
- `run_sandbox_flow()` — строка ~206
- `parse_args()` — строка ~257
- `main()` — строка ~269

**Зависимости (локальные импорты):**
- `backend/apps/bot/broker.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Run an end-to-end notification exercise against a lightweight Telegram sandbox.

**Состояние / проблемы:**
- console/print: 1

### `scripts/export_interview_script_dataset.py`

**Тип:** Скрипт
**Строк кода:** ~184
**Назначение:** Операционный/утилитарный скрипт `export_interview_script_dataset`.

**Ключевые функции:**
- `_mask_string()` — строка ~26
- `_mask_obj()` — строка ~38
- `_is_quality_sample()` — строка ~48
- `_to_training_row()` — строка ~60
- `_export()` — строка ~109
- `main()` — строка ~143

**Зависимости (локальные импорты):**
- `backend/core/ai/redaction.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/ai/models.py`

**Комментарии / явные подсказки в файле:**
- Export Interview Script feedback rows into a JSONL fine-tuning dataset.

**Состояние / проблемы:**
- console/print: 5

### `scripts/fix_slot_2_notification.py`

**Тип:** Скрипт
**Строк кода:** ~90
**Назначение:** Операционный/утилитарный скрипт `fix_slot_2_notification`.

**Ключевые функции:**
- `fix_slot_2()` — строка ~16

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Fix notification for slot 2 by creating a new one.

**Состояние / проблемы:**
- console/print: 24

### `scripts/formal_gate_sprint12.py`

**Тип:** Скрипт
**Строк кода:** ~691
**Назначение:** Операционный/утилитарный скрипт `formal_gate_sprint12`.

**Классы:**
- `CommandSpec` — строка ~39
- `CommandResult` — строка ~48

**Ключевые функции:**
- `ensure_runtime_python()` — строка ~23
- `temporary_env()` — строка ~61
- `_tail_summary()` — строка ~79
- `run_command()` — строка ~86
- `build_inventory()` — строка ~147
- `criterion_status_from_checks()` — строка ~338
- `aggregate_sprint_status()` — строка ~346
- `to_markdown()` — строка ~355
- `parse_args()` — строка ~412
- `main()` — строка ~457

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- console/print: 4

### `scripts/generate_waiting_candidates.py`

**Тип:** Скрипт
**Строк кода:** ~151
**Назначение:** Операционный/утилитарный скрипт `generate_waiting_candidates`.

**Ключевые функции:**
- `_apply_status()` — строка ~90
- `generate_waiting_candidates()` — строка ~111
- `main()` — строка ~138

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/services.py`
- `backend/domain/candidates/status.py`

**Комментарии / явные подсказки в файле:**
- Utility to seed demo candidates that are waiting for slot assignment.

**Состояние / проблемы:**
- console/print: 1

### `scripts/loadtest_notifications.py`

**Тип:** Скрипт
**Строк кода:** ~171
**Назначение:** Операционный/утилитарный скрипт `loadtest_notifications`.

**Ключевые функции:**
- `_build_broker()` — строка ~44
- `_percentile()` — строка ~56
- `_write_json()` — строка ~70
- `_write_csv()` — строка ~75
- `run_load()` — строка ~85
- `main()` — строка ~154

**Зависимости (локальные импорты):**
- `backend/apps/bot/broker.py`
- `backend/apps/bot/services.py`
- `backend/core/settings.py`

**Комментарии / явные подсказки в файле:**
- Generate synthetic notifications to measure enqueue/latency.

**Состояние / проблемы:**
- console/print: 1

### `scripts/loadtest_profiles/analyze_step.py`

**Тип:** Скрипт
**Строк кода:** ~577
**Назначение:** Операционный/утилитарный скрипт `analyze_step`.

**Классы:**
- `AutocannonSummary` — строка ~22

**Ключевые функции:**
- `_num()` — строка ~30
- `_int()` — строка ~37
- `_load_json()` — строка ~44
- `_aggregate_autocannon()` — строка ~51
- `_parse_labels()` — строка ~77
- `_iter_metrics_lines()` — строка ~90
- `_route_latency()` — строка ~109
- `_canonical_route()` — строка ~130
- `_estimate_p95_from_autocannon()` — строка ~141
- `_client_route_latency()` — строка ~163
- `_merge_route_latency()` — строка ~194
- `_delta_http_latency()` — строка ~218
- `_histogram_quantile()` — строка ~280
- `_finite_quantile()` — строка ~300
- `_delta_histogram_quantiles()` — строка ~313
- `_pool_acquire_p95()` — строка ~385
- `_delta_pool_acquire_p95()` — строка ~420
- `_env_float()` — строка ~470
- `main()` — строка ~480

**Состояние / проблемы:**
- console/print: 2

### `scripts/loadtest_profiles/bodies/chat_send.json`

**Тип:** Скрипт
**Строк кода:** ~3
**Назначение:** Операционный/утилитарный скрипт `chat_send`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `scripts/loadtest_profiles/summarize_profile.py`

**Тип:** Скрипт
**Строк кода:** ~141
**Назначение:** Операционный/утилитарный скрипт `summarize_profile`.

**Классы:**
- `Row` — строка ~11

**Ключевые функции:**
- `_num()` — строка ~25
- `_int()` — строка ~32
- `_load()` — строка ~39
- `_error_rate()` — строка ~46
- `main()` — строка ~51

**Состояние / проблемы:**
- console/print: 8

### `scripts/migrate_city_templates.py`

**Тип:** Скрипт
**Строк кода:** ~74
**Назначение:** Операционный/утилитарный скрипт `migrate_city_templates`.

**Ключевые функции:**
- `convert_syntax()` — строка ~13
- `main()` — строка ~26

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- console/print: 3

### `scripts/migrate_legacy_templates.py`

**Тип:** Скрипт
**Строк кода:** ~90
**Назначение:** Операционный/утилитарный скрипт `migrate_legacy_templates`.

**Ключевые функции:**
- `convert_syntax()` — строка ~14
- `main()` — строка ~36

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- console/print: 4

### `scripts/run_interview_script_finetune.py`

**Тип:** Скрипт
**Строк кода:** ~205
**Назначение:** Операционный/утилитарный скрипт `run_interview_script_finetune`.

**Ключевые функции:**
- `_env()` — строка ~17
- `_api_base_url()` — строка ~21
- `_headers()` — строка ~26
- `_upload_training_file()` — строка ~32
- `_create_finetune_job()` — строка ~62
- `_fetch_job()` — строка ~89
- `_run()` — строка ~106
- `main()` — строка ~170

**Комментарии / явные подсказки в файле:**
- Manual CLI to start Interview Script fine-tuning job in OpenAI.

**Состояние / проблемы:**
- console/print: 10

### `scripts/run_migrations.py`

**Тип:** Скрипт
**Строк кода:** ~110
**Назначение:** Операционный/утилитарный скрипт `run_migrations`.

**Ключевые функции:**
- `resolve_migration_database_url()` — строка ~38
- `main()` — строка ~71

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/settings.py`

**Используется в:**
- `tests/test_run_migrations_contract.py`

**Комментарии / явные подсказки в файле:**
- Database migration script.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `scripts/seed_auth_accounts.py`

**Тип:** Скрипт
**Строк кода:** ~108
**Назначение:** Операционный/утилитарный скрипт `seed_auth_accounts`.

**Ключевые функции:**
- `_upsert_account()` — строка ~26
- `seed_admin()` — строка ~66
- `seed_recruiters()` — строка ~74
- `main()` — строка ~97

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/passwords.py`
- `backend/domain/auth_account.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Seed auth_accounts for admin and recruiters.

**Состояние / проблемы:**
- console/print: 1

### `scripts/seed_city_templates.py`

**Тип:** Скрипт
**Строк кода:** ~21
**Назначение:** Операционный/утилитарный скрипт `seed_city_templates`.

**Ключевые функции:**
- `main()` — строка ~11

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- console/print: 1

### `scripts/seed_default_templates.py`

**Тип:** Скрипт
**Строк кода:** ~60
**Назначение:** Операционный/утилитарный скрипт `seed_default_templates`.

**Ключевые функции:**
- `main()` — строка ~13

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- console/print: 3

### `scripts/seed_incoming_candidates.py`

**Тип:** Скрипт
**Строк кода:** ~83
**Назначение:** Операционный/утилитарный скрипт `seed_incoming_candidates`.

**Ключевые функции:**
- `_guard_environment()` — строка ~26
- `_seed()` — строка ~38
- `_parse_args()` — строка ~68
- `main()` — строка ~74

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Состояние / проблемы:**
- console/print: 1

### `scripts/seed_legacy_templates.py`

**Тип:** Скрипт
**Строк кода:** ~21
**Назначение:** Операционный/утилитарный скрипт `seed_legacy_templates`.

**Ключевые функции:**
- `main()` — строка ~11

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- console/print: 1

### `scripts/seed_message_templates.py`

**Тип:** Скрипт
**Строк кода:** ~179
**Назначение:** Операционный/утилитарный скрипт `seed_message_templates`.

**Ключевые функции:**
- `seed_templates()` — строка ~107
- `main()` — строка ~168

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/env.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Seed default message templates for the Telegram bot (TG/RU, global).

**Состояние / проблемы:**
- console/print: 5

### `scripts/seed_test_candidates.py`

**Тип:** Скрипт
**Строк кода:** ~93
**Назначение:** Операционный/утилитарный скрипт `seed_test_candidates`.

**Ключевые функции:**
- `seed()` — строка ~27

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Seed 40 test candidates and attach them to recruiters via slots.

**Состояние / проблемы:**
- console/print: 2

### `scripts/seed_test_users.py`

**Тип:** Скрипт
**Строк кода:** ~130
**Назначение:** Операционный/утилитарный скрипт `seed_test_users`.

**Ключевые функции:**
- `_guard_environment()` — строка ~44
- `_resolve_status()` — строка ~56
- `_seed()` — строка ~68
- `_parse_args()` — строка ~103
- `main()` — строка ~113

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Состояние / проблемы:**
- console/print: 1

### `scripts/seed_tests.py`

**Тип:** Скрипт
**Строк кода:** ~91
**Назначение:** Операционный/утилитарный скрипт `seed_tests`.

**Ключевые функции:**
- `seed_tests()` — строка ~16

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/tests/models.py`

**Состояние / проблемы:**
- console/print: 5

### `scripts/summarize_autocannon.py`

**Тип:** Скрипт
**Строк кода:** ~99
**Назначение:** Операционный/утилитарный скрипт `summarize_autocannon`.

**Классы:**
- `Row` — строка ~11

**Ключевые функции:**
- `_num()` — строка ~23
- `main()` — строка ~30

**Состояние / проблемы:**
- console/print: 7

### `scripts/test_bot_init.py`

**Тип:** Скрипт
**Строк кода:** ~67
**Назначение:** Операционный/утилитарный скрипт `test_bot_init`.

**Ключевые функции:**
- `test_bot()` — строка ~16

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/state.py`
- `backend/core/settings.py`

**Комментарии / явные подсказки в файле:**
- Test bot initialization.

**Состояние / проблемы:**
- console/print: 24

### `scripts/test_create_intro_day.py`

**Тип:** Скрипт
**Строк кода:** ~153
**Назначение:** Операционный/утилитарный скрипт `test_create_intro_day`.

**Ключевые функции:**
- `test_create_intro_day()` — строка ~22

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Test creating intro_day slot and notification.

**Состояние / проблемы:**
- console/print: 33

### `scripts/update_notification_templates.py`

**Тип:** Скрипт
**Строк кода:** ~268
**Назначение:** Операционный/утилитарный скрипт `update_notification_templates`.

**Ключевые функции:**
- `update_existing_template()` — строка ~125
- `create_city_specific_template()` — строка ~161
- `main()` — строка ~201

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Скрипт для обновления шаблонов уведомлений.

**Состояние / проблемы:**
- console/print: 34

### `scripts/verify_jwt.py`

**Тип:** Скрипт
**Строк кода:** ~39
**Назначение:** Операционный/утилитарный скрипт `verify_jwt`.

**Ключевые функции:**
- `main()` — строка ~12

**Зависимости (локальные импорты):**
- `backend/core/auth.py`
- `backend/core/passwords.py`
- `backend/core/settings.py`

**Состояние / проблемы:**
- console/print: 7

### `tools/recompute_weekly_kpis.py`

**Тип:** Скрипт
**Строк кода:** ~76
**Назначение:** Операционный/утилитарный скрипт `recompute_weekly_kpis`.

**Ключевые функции:**
- `_recompute_range()` — строка ~19
- `main()` — строка ~25

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/kpis.py`
- `backend/core/bootstrap.py`

**Комментарии / явные подсказки в файле:**
- Management script to recompute weekly KPI snapshots.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tools/render_previews.py`

**Тип:** Скрипт
**Строк кода:** ~41
**Назначение:** Операционный/утилитарный скрипт `render_previews`.

**Классы:**
- `DummyRequest` — строка ~19

**Ключевые функции:**
- `render_all()` — строка ~27

**Комментарии / явные подсказки в файле:**
- Render demo templates to static HTML previews.

**Состояние / проблемы:**
- console/print: 1

## 3.9 Tests

### `frontend/app/tests/e2e/a11y.spec.ts`

**Тип:** Тест
**Строк кода:** ~39
**Назначение:** Тестовый модуль `a11y.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/ai-copilot.spec.ts`

**Тип:** Тест
**Строк кода:** ~46
**Назначение:** Тестовый модуль `ai-copilot.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`
- `waitForURL()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/candidates.spec.ts`

**Тип:** Тест
**Строк кода:** ~38
**Назначение:** Тестовый модуль `candidates.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`
- `waitForURL()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/focus.cities.spec.ts`

**Тип:** Тест
**Строк кода:** ~36
**Назначение:** Тестовый модуль `focus.cities.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`
- `waitForURL()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/focus.slots.spec.ts`

**Тип:** Тест
**Строк кода:** ~49
**Назначение:** Тестовый модуль `focus.slots.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/health.spec.ts`

**Тип:** Тест
**Строк кода:** ~7
**Назначение:** Тестовый модуль `health.spec`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/mobile-smoke.spec.ts`

**Тип:** Тест
**Строк кода:** ~50
**Назначение:** Тестовый модуль `mobile-smoke.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`

**Дочерние компоненты:**
- `<HTMLElement />`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/recruiters.spec.ts`

**Тип:** Тест
**Строк кода:** ~36
**Назначение:** Тестовый модуль `recruiters.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`
- `waitForURL()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/regression-flow.spec.ts`

**Тип:** Тест
**Строк кода:** ~117
**Назначение:** Тестовый модуль `regression-flow.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`
- `waitForURL()`

**Комментарии / явные подсказки в файле:**
- *

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/slots.spec.ts`

**Тип:** Тест
**Строк кода:** ~37
**Назначение:** Тестовый модуль `slots.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`
- `waitForURL()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/smoke.spec.ts`

**Тип:** Тест
**Строк кода:** ~58
**Назначение:** Тестовый модуль `smoke.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`
- `waitForURL()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/ui-cosmetics.spec.ts`

**Тип:** Тест
**Строк кода:** ~171
**Назначение:** Тестовый модуль `ui-cosmetics.spec`.

**API / сетевые вызовы:**
- `waitForLoadState()`
- `waitForTimeout()`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `frontend/app/tests/e2e/utils/keyboard.ts`

**Тип:** Тест
**Строк кода:** ~12
**Назначение:** Тестовый модуль `keyboard`.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/conftest.py`

**Тип:** Тест
**Строк кода:** ~155
**Назначение:** Тестовый модуль `conftest`.

**Ключевые функции:**
- `_choose_event_loop_policy()` — строка ~25
- `pytest_configure()` — строка ~34
- `pytest_unconfigure()` — строка ~39
- `event_loop()` — строка ~48
- `configure_backend()` — строка ~55
- `clean_database()` — строка ~112

**Зависимости (локальные импорты):**
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/base.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/handlers/test_common_free_text.py`

**Тип:** Тест
**Строк кода:** ~131
**Назначение:** Тестовый модуль `test_common_free_text`.

**Классы:**
- `DummyMessage` — строка ~11
- `DummyStateManager` — строка ~23

**Ключевые функции:**
- `test_free_text_ignores_when_state_missing()` — строка ~37
- `test_free_text_ignores_messages_without_user()` — строка ~62
- `test_free_text_delegates_to_test1_handler()` — строка ~87
- `test_free_text_handles_state_errors()` — строка ~107

**Зависимости (локальные импорты):**
- `backend/apps/bot/handlers/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/integration/__init__.py`

**Тип:** Тест
**Строк кода:** ~2
**Назначение:** Тестовый модуль `__init__`.

**Комментарии / явные подсказки в файле:**
- Integration tests for recruitsmart_admin.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/integration/test_migrations_postgres.py`

**Тип:** Тест
**Строк кода:** ~91
**Назначение:** Тестовый модуль `test_migrations_postgres`.

**Ключевые функции:**
- `test_migrations_on_clean_postgres()` — строка ~9

**Зависимости (локальные импорты):**
- `backend/migrations/runner.py`

**Комментарии / явные подсказки в файле:**
- Integration test to verify all migrations run successfully on clean PostgreSQL database.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/integration/test_notification_broker_redis.py`

**Тип:** Тест
**Строк кода:** ~94
**Назначение:** Тестовый модуль `test_notification_broker_redis`.

**Ключевые функции:**
- `redis_client()` — строка ~17
- `broker()` — строка ~35
- `drain()` — строка ~43
- `test_enqueue_dequeue_and_acknowledge()` — строка ~48
- `test_requeue_increments_not_before()` — строка ~63
- `test_dlq_receives_failed_message()` — строка ~76
- `test_claim_stale_reclaims_messages()` — строка ~86

**Зависимости (локальные импорты):**
- `backend/apps/bot/broker.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/reproduce_issue_1.py`

**Тип:** Тест
**Строк кода:** ~47
**Назначение:** Тестовый модуль `reproduce_issue_1`.

**Ключевые функции:**
- `test_update_mismatch()` — строка ~7

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates.py`

**Состояние / проблемы:**
- console/print: 2

### `tests/services/test_bot_keyboards.py`

**Тип:** Тест
**Строк кода:** ~380
**Назначение:** Тестовый модуль `test_bot_keyboards`.

**Ключевые функции:**
- `test_kb_recruiters_handles_duplicate_names_with_slots()` — строка ~69
- `test_kb_recruiters_uses_aggregated_repository()` — строка ~101
- `test_kb_recruiters_handles_uppercase_status()` — строка ~133
- `test_kb_recruiters_filters_by_city()` — строка ~163
- `test_kb_recruiters_no_slots_has_contact_button()` — строка ~211
- `_all_buttons()` — строка ~235
- `_buttons_with_text()` — строка ~240
- `test_kb_approve_without_crm_url()` — строка ~244
- `test_kb_approve_with_crm_url()` — строка ~251
- `test_kb_candidate_notification_has_action_buttons()` — строка ~260
- `test_kb_candidate_notification_no_crm_url()` — строка ~271
- `test_kb_candidate_actions_has_action_buttons()` — строка ~277
- `test_kb_recruiter_dashboard_with_waiting()` — строка ~288
- `test_kb_recruiter_dashboard_no_waiting()` — строка ~299
- `test_kb_recruiter_dashboard_no_crm_url()` — строка ~306
- `test_kb_slot_assignment_reschedule_options_has_manual_fallback()` — строка ~312
- `_webapp_buttons()` — строка ~342
- `test_kb_candidate_notification_has_webapp_button()` — строка ~347
- `test_kb_candidate_notification_no_webapp_without_crm()` — строка ~355
- `test_kb_candidate_actions_has_webapp_button()` — строка ~361
- `test_kb_recruiter_dashboard_has_webapp_button()` — строка ~368
- `test_kb_recruiter_dashboard_no_webapp_without_crm()` — строка ~376

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/config.py`
- `backend/apps/bot/keyboards.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/services/test_dashboard_and_slots.py`

**Тип:** Тест
**Строк кода:** ~742
**Назначение:** Тестовый модуль `test_dashboard_and_slots`.

**Ключевые функции:**
- `test_waiting_candidates_list_is_capped_to_hundred()` — строка ~27
- `test_waiting_candidates_marks_requested_another_time()` — строка ~61
- `test_waiting_candidates_uses_bot_state_for_reschedule_intent()` — строка ~141
- `test_waiting_candidates_ignore_expired_ai_outputs()` — строка ~220
- `test_waiting_candidates_compute_live_ai_score_when_cache_missing()` — строка ~298
- `test_dashboard_and_slot_listing()` — строка ~328
- `test_dashboard_reports_test1_metrics()` — строка ~369
- `test_slots_list_status_counts_and_api_payload_normalizes_statuses()` — строка ~382
- `test_recruiter_leaderboard_scores_and_ranking()` — строка ~443
- `test_api_slots_payload_uses_assignment_fallback_for_legacy_free_slot()` — строка ~547
- `test_api_slots_payload_keeps_recruiter_and_candidate_timezones_separate()` — строка ~596
- `test_reject_slot_cancels_active_assignment_and_disables_fallback()` — строка ~648

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/reschedule_intents.py`
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/bot/metrics.py`
- `backend/core/db.py`
- `backend/domain/ai/models.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/services/test_dashboard_calendar.py`

**Тип:** Тест
**Строк кода:** ~62
**Назначение:** Тестовый модуль `test_dashboard_calendar`.

**Ключевые функции:**
- `test_dashboard_calendar_snapshot_links_candidates()` — строка ~15

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/dashboard_calendar.py`
- `backend/apps/bot/metrics.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/services/test_dashboard_funnel.py`

**Тип:** Тест
**Строк кода:** ~156
**Назначение:** Тестовый модуль `test_dashboard_funnel`.

**Ключевые функции:**
- `_insert_event()` — строка ~15
- `test_bot_funnel_stats_counts_and_dropoffs()` — строка ~40
- `test_funnel_step_candidates_drilldown()` — строка ~114

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/core/db.py`
- `backend/domain/analytics.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/services/test_slot_outcome.py`

**Тип:** Тест
**Строк кода:** ~156
**Назначение:** Тестовый модуль `test_slot_outcome`.

**Ключевые функции:**
- `test_set_slot_outcome_triggers_test2()` — строка ~20
- `test_set_slot_outcome_validates_choice()` — строка ~94
- `test_set_slot_outcome_requires_candidate()` — строка ~103
- `test_send_rejection_reports_unconfigured_bot()` — строка ~133

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/__init__.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/services/test_slots_bulk.py`

**Тип:** Тест
**Строк кода:** ~225
**Назначение:** Тестовый модуль `test_slots_bulk`.

**Ключевые функции:**
- `test_bulk_create_slots_creates_unique_series()` — строка ~18
- `test_bulk_assign_slots_updates_recruiter()` — строка ~124
- `test_bulk_schedule_reminders_uses_service()` — строка ~154
- `test_bulk_delete_slots_respects_force()` — строка ~191

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots/core.py`
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/services/test_slots_delete.py`

**Тип:** Тест
**Строк кода:** ~132
**Назначение:** Тестовый модуль `test_slots_delete`.

**Ключевые функции:**
- `_setup_recruiter_with_city()` — строка ~12
- `test_delete_slot_allows_free_and_pending_blocks_booked()` — строка ~26
- `test_delete_slot_missing_returns_error()` — строка ~89
- `test_delete_all_slots_handles_force()` — строка ~96

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/services/test_weekly_kpis.py`

**Тип:** Тест
**Строк кода:** ~265
**Назначение:** Тестовый модуль `test_weekly_kpis`.

**Ключевые функции:**
- `test_week_window_uses_sunday_boundary()` — строка ~23
- `test_weekly_kpis_compute_unique_counts()` — строка ~35
- `test_weekly_kpis_respects_performance_budget()` — строка ~209

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/kpis.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_action_endpoint.py`

**Тип:** Тест
**Строк кода:** ~74
**Назначение:** Тестовый модуль `test_action_endpoint`.

**Ключевые функции:**
- `test_all_post_actions_use_new_api_pattern()` — строка ~12
- `test_get_actions_use_ui_pattern()` — строка ~25
- `test_action_keys_are_unique_per_status()` — строка ~40
- `test_post_actions_have_target_status()` — строка ~50
- `test_dangerous_actions_have_confirmation()` — строка ~62

**Зависимости (локальные импорты):**
- `backend/domain/candidates/actions.py`

**Комментарии / явные подсказки в файле:**
- Tests for action URL patterns in actions.py.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_auth_form_admin_env.py`

**Тип:** Тест
**Строк кода:** ~56
**Назначение:** Тестовый модуль `test_admin_auth_form_admin_env`.

**Классы:**
- `_DummyIntegration` — строка ~9

**Ключевые функции:**
- `admin_app()` — строка ~15
- `test_form_login_accepts_env_admin_credentials()` — строка ~36

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_auth_no_basic_challenge.py`

**Тип:** Тест
**Строк кода:** ~48
**Назначение:** Тестовый модуль `test_admin_auth_no_basic_challenge`.

**Классы:**
- `_DummyIntegration` — строка ~8

**Ключевые функции:**
- `admin_app()` — строка ~14
- `test_api_401_does_not_advertise_basic_challenge()` — строка ~39

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_candidate_chat_actions.py`

**Тип:** Тест
**Строк кода:** ~764
**Назначение:** Тестовый модуль `test_admin_candidate_chat_actions`.

**Классы:**
- `_DummyIntegration` — строка ~59
- `DummyBotService` — строка ~64

**Ключевые функции:**
- `configure_backend()` — строка ~25
- `admin_app()` — строка ~79
- `_async_request()` — строка ~113
- `_async_request_with_principal()` — строка ~122
- `_create_recruiter()` — строка ~143
- `_create_recruiter_pair_in_city()` — строка ~154
- `test_chat_history_and_send()` — строка ~174
- `test_chat_retry_marks_as_sent()` — строка ~202
- `test_chat_updates_endpoint_returns_latest_messages()` — строка ~237
- `test_chat_quick_action_updates_status_and_sends_template()` — строка ~273
- `test_recruiter_can_access_chat_for_scoped_candidate()` — строка ~319
- `test_recruiter_can_access_chat_for_city_scoped_candidate()` — строка ~353
- `test_recruiter_cannot_view_foreign_candidate_chat()` — строка ~380
- `test_recruiter_can_view_city_scoped_candidate_detail()` — строка ~403
- `test_recruiter_cannot_view_foreign_candidate_detail()` — строка ~432
- `test_recruiter_cannot_send_chat_to_foreign_candidate()` — строка ~455
- `test_recruiter_cannot_retry_foreign_candidate_chat()` — строка ~479
- `test_candidate_action_updates_status()` — строка ~517
- `test_recruiter_can_execute_action_for_city_scoped_candidate()` — строка ~542
- `test_recruiter_cannot_execute_action_for_foreign_candidate()` — строка ~571
- `test_recruiter_can_delete_owned_candidate()` — строка ~594
- `test_recruiter_cannot_delete_foreign_candidate()` — строка ~624
- `test_calendar_tasks_crud_and_events()` — строка ~648
- `test_calendar_confirmed_filter_includes_preconfirmed_slots()` — строка ~715

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/base.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_candidate_schedule_slot.py`

**Тип:** Тест
**Строк кода:** ~1416
**Назначение:** Тестовый модуль `test_admin_candidate_schedule_slot`.

**Классы:**
- `_DummyIntegration` — строка ~25

**Ключевые функции:**
- `admin_app()` — строка ~31
- `_async_request()` — строка ~54
- `_async_request_with_principal()` — строка ~63
- `_create_reschedule_assignment()` — строка ~82
- `_to_aware_utc()` — строка ~130
- `test_schedule_slot_conflict_returns_validation_error()` — строка ~139
- `test_api_create_candidate_create_only_without_datetime()` — строка ~192
- `test_api_create_candidate_with_datetime_without_telegram_keeps_candidate()` — строка ~232
- `test_api_create_candidate_with_telegram_id()` — строка ~275
- `test_api_delete_candidate_removes_user()` — строка ~313
- `test_api_candidates_list_includes_views_for_kanban_and_calendar()` — строка ~340
- `test_schedule_slot_reuses_active_reschedule_assignment()` — строка ~375
- `test_begin_reschedule_request_marks_assignment_before_datetime_submission()` — строка ~452
- `test_request_reschedule_accepts_exact_slot_choice()` — строка ~533
- `test_request_reschedule_accepts_availability_window_and_blocks_direct_approve()` — строка ~567
- `test_request_reschedule_accepts_free_text_without_datetime()` — строка ~610
- `test_schedule_slot_assigns_existing_free_slot()` — строка ~644
- `test_schedule_slot_manual_uses_recruiter_timezone_for_input()` — строка ~708
- `test_schedule_slot_replaces_existing_active_assignment()` — строка ~764
- `test_available_slots_endpoint_filters_by_candidate_city()` — строка ~864
- `test_api_slot_propose_assigns_candidate_and_sets_slot_pending()` — строка ~930
- `test_api_slot_propose_returns_slot_not_free()` — строка ~995
- `test_api_slot_propose_uses_telegram_user_id_fallback()` — строка ~1042
- `test_api_schedule_slot_returns_candidate_telegram_missing_when_no_identifiers()` — строка ~1096
- `test_api_slot_propose_recruiter_scope_blocks_foreign_slot()` — строка ~1146

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/slot_assignment_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_candidate_status_update.py`

**Тип:** Тест
**Строк кода:** ~92
**Назначение:** Тестовый модуль `test_admin_candidate_status_update`.

**Классы:**
- `_DummyIntegration` — строка ~8

**Ключевые функции:**
- `admin_app()` — строка ~14
- `_async_post()` — строка ~35
- `test_invalid_status_redirects_back()` — строка ~47
- `test_interview_declined_uses_status_service()` — строка ~65

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/domain/candidates/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_candidates_service.py`

**Тип:** Тест
**Строк кода:** ~1013
**Назначение:** Тестовый модуль `test_admin_candidates_service`.

**Ключевые функции:**
- `test_list_candidates_and_detail()` — строка ~31
- `test_list_candidates_includes_responsible_recruiter_fallback_fields()` — строка ~102
- `test_candidate_detail_includes_test_sections_and_telemost()` — строка ~140
- `test_candidate_cohort_comparison_groups_similar_candidates()` — строка ~238
- `test_candidate_detail_prefers_city_intro_day_template()` — строка ~308
- `test_api_candidate_detail_payload_extracts_hh_profile_url_from_answers()` — строка ~366
- `test_candidate_detail_test_history_contains_attempt_details()` — строка ~399
- `test_candidate_detail_overrides_display_when_reschedule_requested()` — строка ~469
- `test_update_candidate_status_changes_slot_and_outcome()` — строка ~512
- `test_map_to_workflow_status_prefers_candidate_status_over_stale_workflow()` — строка ~566
- `test_map_to_workflow_status_intro_day_scheduled_is_not_confirmed()` — строка ~577
- `test_list_candidates_pipeline_filters_renders_correct_stage()` — строка ~589
- `test_intro_day_candidate_not_shown_in_interview_pipeline_even_with_interview_slot()` — строка ~707
- `test_update_candidate_status_assigned_sends_notification()` — строка ~799
- `test_delete_all_candidates_resets_slots()` — строка ~848
- `test_update_candidate_status_declined_without_slot()` — строка ~890
- `test_recruiter_can_update_unassigned_candidate_in_city_scope()` — строка ~911
- `test_recruiter_can_update_candidate_owned_by_another_recruiter_in_city_scope()` — строка ~943
- `test_recruiter_cannot_update_candidate_outside_city_scope()` — строка ~979

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/candidates.py`
- `backend/apps/admin_ui/services/reschedule_intents.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/status.py`
- `backend/domain/candidates/workflow.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_message_templates.py`

**Тип:** Тест
**Строк кода:** ~73
**Назначение:** Тестовый модуль `test_admin_message_templates`.

**Ключевые функции:**
- `test_template_validation_rejects_unclosed_tag()` — строка ~13
- `test_template_validation_accepts_valid_html()` — строка ~28
- `test_preview_context_uses_city_intro_details_for_intro_templates()` — строка ~45

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_message_templates_sms.py`

**Тип:** Тест
**Строк кода:** ~16
**Назначение:** Тестовый модуль `test_admin_message_templates_sms`.

**Ключевые функции:**
- `test_create_sms_template()` — строка ~6

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_message_templates_update.py`

**Тип:** Тест
**Строк кода:** ~63
**Назначение:** Тестовый модуль `test_admin_message_templates_update`.

**Ключевые функции:**
- `test_update_message_template_optimistic_locking()` — строка ~9

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_notifications_feed_api.py`

**Тип:** Тест
**Строк кода:** ~242
**Назначение:** Тестовый модуль `test_admin_notifications_feed_api`.

**Классы:**
- `_DummyIntegration` — строка ~10

**Ключевые функции:**
- `notifications_feed_app()` — строка ~16
- `test_notifications_feed_returns_degraded_payload_when_db_unavailable()` — строка ~39
- `test_notifications_logs_returns_degraded_payload_when_db_unavailable()` — строка ~57
- `test_notifications_feed_returns_outbox_items()` — строка ~75
- `test_notifications_logs_returns_items()` — строка ~117
- `test_notifications_retry_and_cancel_endpoints()` — строка ~183

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_notifications_service.py`

**Тип:** Тест
**Строк кода:** ~66
**Назначение:** Тестовый модуль `test_admin_notifications_service`.

**Ключевые функции:**
- `test_notification_feed_returns_ordered_items()` — строка ~11

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/notifications.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_slots_api.py`

**Тип:** Тест
**Строк кода:** ~1061
**Назначение:** Тестовый модуль `test_admin_slots_api`.

**Ключевые функции:**
- `_force_ready_bot()` — строка ~24
- `_create_booked_slot()` — строка ~36
- `_create_booked_slot_no_telegram()` — строка ~63
- `_async_request()` — строка ~90
- `_async_request_with_csrf()` — строка ~109
- `admin_slots_app()` — строка ~126
- `clear_state_manager()` — строка ~154
- `test_slot_outcome_endpoint_uses_state_manager()` — строка ~166
- `test_reschedule_endpoint_falls_back_when_notifications_missing()` — строка ~260
- `test_reject_endpoint_falls_back_when_notifications_missing()` — строка ~280
- `test_reject_booking_without_telegram_id_releases_slot()` — строка ~306
- `test_reschedule_without_telegram_id_releases_slot()` — строка ~328
- `test_reschedule_reuses_existing_free_target_slot()` — строка ~350
- `test_reject_booking_handles_notification_errors()` — строка ~457
- `test_reschedule_handles_notification_errors()` — строка ~485
- `test_slot_outcome_endpoint_returns_200_when_bot_unavailable()` — строка ~513
- `test_slot_outcome_endpoint_skips_when_bot_optional()` — строка ~536
- `test_slot_outcome_success_idempotent()` — строка ~559
- `test_slot_outcome_reject_triggers_rejection()` — строка ~591
- `test_health_check_reports_ok()` — строка ~623
- `test_slots_create_returns_422_when_required_fields_missing()` — строка ~635
- `test_candidate_slot_can_be_approved_via_admin()` — строка ~664
- `test_candidate_slot_approval_validates_owner()` — строка ~726
- `test_api_slot_book_duplicate_candidate_returns_conflict()` — строка ~781
- `test_api_slot_book_maps_integrity_error_to_conflict()` — строка ~853

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/services/__init__.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/candidates/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_state_nullbot.py`

**Тип:** Тест
**Строк кода:** ~186
**Назначение:** Тестовый модуль `test_admin_state_nullbot`.

**Классы:**
- `DummySettings` — строка ~14
- `StubNotificationService` — строка ~74
- `StubReminderService` — строка ~121
- `StubBotService` — строка ~126
- `DummyTask` — строка ~133

**Ключевые функции:**
- `test_setup_bot_state_without_token()` — строка ~37
- `test_setup_bot_state_with_custom_api_base()` — строка ~54
- `test_notifications_health_endpoint_ok()` — строка ~138
- `test_notifications_health_endpoint_missing_service()` — строка ~160
- `test_notifications_metrics_endpoint_prometheus()` — строка ~176

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/__init__.py`
- `backend/apps/admin_ui/routers/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_surface_hardening.py`

**Тип:** Тест
**Строк кода:** ~232
**Назначение:** Тестовый модуль `test_admin_surface_hardening`.

**Классы:**
- `_DummyIntegration` — строка ~13

**Ключевые функции:**
- `_clear_settings_cache()` — строка ~19
- `_build_app()` — строка ~25
- `test_legacy_assignments_routes_disabled_by_default()` — строка ~53
- `test_legacy_assignments_routes_return_410_deprecation()` — строка ~60
- `test_calendar_ws_requires_authenticated_session()` — строка ~85
- `test_calendar_ws_accepts_authenticated_session()` — строка ~94
- `test_metrics_returns_404_in_production_mode()` — строка ~114
- `test_metrics_forbidden_without_auth_or_allowlist()` — строка ~124
- `test_metrics_allowed_for_authenticated_user()` — строка ~133
- `test_slot_assignments_confirm_requires_token()` — строка ~152
- `test_slot_assignments_reschedule_requires_token()` — строка ~163
- `test_protected_routes_require_auth()` — строка ~188
- `test_dev_autoadmin_rejected_in_production()` — строка ~200
- `test_legacy_basic_rejected_in_production()` — строка ~217

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/__init__.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/routers/__init__.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_template_keys.py`

**Тип:** Тест
**Строк кода:** ~85
**Назначение:** Тестовый модуль `test_admin_template_keys`.

**Ключевые функции:**
- `_stub_migrations_package()` — строка ~6
- `_ensure_slots_stub()` — строка ~25
- `_ensure_router_stubs()` — строка ~54
- `test_template_keys_endpoint_matches_runtime()` — строка ~79

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/services/message_templates_presets.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_templates_legacy_create_revive.py`

**Тип:** Тест
**Строк кода:** ~73
**Назначение:** Тестовый модуль `test_admin_templates_legacy_create_revive`.

**Ключевые функции:**
- `test_legacy_templates_create_revives_inactive_template()` — строка ~9

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/db.py`
- `backend/core/settings.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_admin_ui_auth_startup.py`

**Тип:** Тест
**Строк кода:** ~70
**Назначение:** Тестовый модуль `test_admin_ui_auth_startup`.

**Классы:**
- `_DummyIntegration` — строка ~27

**Ключевые функции:**
- `_configure_env()` — строка ~9
- `_fake_setup_bot_state()` — строка ~32
- `test_create_app_registers_auth_token_route()` — строка ~43
- `test_auth_token_endpoint_smoke()` — строка ~54

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/__init__.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_ai_copilot.py`

**Тип:** Тест
**Строк кода:** ~828
**Назначение:** Тестовый модуль `test_ai_copilot`.

**Классы:**
- `_DummyIntegration` — строка ~17

**Ключевые функции:**
- `ai_app()` — строка ~23
- `_run()` — строка ~49
- `_csrf()` — строка ~58
- `test_ai_redaction_masks_phone_email_urls_and_known_names()` — строка ~66
- `test_ai_redaction_allows_numeric_answers()` — строка ~87
- `test_ai_context_builder_excludes_pii_fields()` — строка ~98
- `test_ai_context_redacts_question_answers()` — строка ~134
- `test_ai_context_extracts_age_and_desired_income()` — строка ~188
- `test_ai_context_derives_customer_facing_signals_from_experience()` — строка ~250
- `test_ai_context_extracts_field_format_answer_from_test1()` — строка ~301
- `test_ai_context_scoping_blocks_other_recruiter()` — строка ~348
- `test_candidate_scorecard_caps_final_score_on_hard_blocker()` — строка ~387
- `test_candidate_scorecard_marks_positive_field_format_answer_as_met()` — строка ~426
- `test_candidate_scorecard_marks_conditional_field_format_answer_as_unknown_not_risk()` — строка ~457
- `test_ai_summary_cache_reuse_by_input_hash()` — строка ~487
- `test_ai_summary_and_coach_share_canonical_score()` — строка ~528
- `test_ai_resume_upsert_changes_summary_input_hash()` — строка ~587
- `test_ai_summary_uses_local_fallback_when_provider_not_needed()` — строка ~625
- `test_ai_disabled_returns_ai_disabled_error()` — строка ~655
- `test_ai_city_recommendations_cache_reuse()` — строка ~699
- `test_ai_candidate_coach_cache_reuse()` — строка ~743
- `test_ai_candidate_coach_drafts_modes_and_invalid()` — строка ~785

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/ai/candidate_scorecard.py`
- `backend/core/ai/context.py`
- `backend/core/ai/redaction.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_api_presets.py`

**Тип:** Тест
**Строк кода:** ~21
**Назначение:** Тестовый модуль `test_api_presets`.

**Ключевые функции:**
- `test_api_presets_format()` — строка ~8

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/api.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_app.py`

**Тип:** Тест
**Строк кода:** ~99
**Назначение:** Тестовый модуль `test_bot_app`.

**Классы:**
- `DummySettings` — строка ~10

**Ключевые функции:**
- `test_create_bot_uses_custom_api_base()` — строка ~15
- `test_create_bot_raises_for_missing_token()` — строка ~28
- `test_main_closes_bot_session_on_startup_failure()` — строка ~39

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_app_smoke.py`

**Тип:** Тест
**Строк кода:** ~39
**Назначение:** Тестовый модуль `test_bot_app_smoke`.

**Ключевые функции:**
- `test_create_application_smoke()` — строка ~11
- `test_state_manager_get_with_default()` — строка ~26

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_confirmation_flows.py`

**Тип:** Тест
**Строк кода:** ~946
**Назначение:** Тестовый модуль `test_bot_confirmation_flows`.

**Классы:**
- `DummyMessage` — строка ~37
- `DummyCallback` — строка ~47
- `DummyApproveCallback` — строка ~59

**Ключевые функции:**
- `test_dispatch_interview_success_sends_message_and_logs()` — строка ~72
- `test_dispatch_interview_success_logs_and_raises_on_failure()` — строка ~117
- `test_candidate_confirmation_idempotent()` — строка ~156
- `test_intro_day_confirmation_keeps_details_message_and_sends_ack()` — строка ~267
- `test_intro_day_confirmation_before_event_day_keeps_preliminary_status()` — строка ~318
- `test_intro_day_confirmation_on_event_day_sets_day_of_status()` — строка ~383
- `test_recruiter_approval_message_idempotent()` — строка ~448
- `test_notification_log_unique_constraint()` — строка ~556
- `test_notification_log_overwrite_updates_existing_entry()` — строка ~599
- `test_no_duplicate_confirm_messages()` — строка ~668
- `test_handle_pick_slot_sends_local_summary()` — строка ~771
- `test_outbox_exactly_once()` — строка ~850

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/events.py`
- `backend/apps/bot/handlers/__init__.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_html_escape.py`

**Тип:** Тест
**Строк кода:** ~18
**Назначение:** Тестовый модуль `test_bot_html_escape`.

**Ключевые функции:**
- `test_recruiter_caption_escapes_html()` — строка ~4

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_integration_toggle.py`

**Тип:** Тест
**Строк кода:** ~200
**Назначение:** Тестовый модуль `test_bot_integration_toggle`.

**Ключевые функции:**
- `test_bot_service_switch_blocks_dispatch()` — строка ~18
- `test_integration_switch_tracks_source_and_reason()` — строка ~53
- `test_api_integration_toggle()` — строка ~64
- `test_runtime_disable_reflected_in_health()` — строка ~106
- `test_disabled_bot_health_endpoints_return_200()` — строка ~168

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/apps/bot/state_store.py`
- `backend/core/__init__.py`
- `backend/core/settings.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_manual_contact.py`

**Тип:** Тест
**Строк кода:** ~352
**Назначение:** Тестовый модуль `test_bot_manual_contact`.

**Ключевые функции:**
- `test_manual_contact_links_responsible_recruiter()` — строка ~23
- `test_manual_contact_without_responsible_link()` — строка ~89
- `test_manual_availability_response_records_window()` — строка ~141
- `test_manual_availability_response_stores_note_when_unparsed()` — строка ~191
- `test_manual_availability_sets_waiting_status()` — строка ~238
- `test_manual_availability_notifies_recruiters()` — строка ~282

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/config.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_questions_refresh.py`

**Тип:** Тест
**Строк кода:** ~31
**Назначение:** Тестовый модуль `test_bot_questions_refresh`.

**Ключевые функции:**
- `test_refresh_questions_bank_updates_globals()` — строка ~5
- `test_refresh_questions_bank_fallbacks()` — строка ~20

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_reminder_jobs_api.py`

**Тип:** Тест
**Строк кода:** ~135
**Назначение:** Тестовый модуль `test_bot_reminder_jobs_api`.

**Классы:**
- `_DummyIntegration` — строка ~11
- `_DummyReminderService` — строка ~16

**Ключевые функции:**
- `reminder_jobs_app()` — строка ~22
- `test_bot_reminder_jobs_degraded_when_db_unavailable()` — строка ~45
- `test_bot_reminder_jobs_lists_upcoming_jobs()` — строка ~60
- `test_bot_reminder_jobs_resync_endpoint()` — строка ~121

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_reminder_policy_api.py`

**Тип:** Тест
**Строк кода:** ~73
**Назначение:** Тестовый модуль `test_bot_reminder_policy_api`.

**Ключевые функции:**
- `_configure_auth()` — строка ~10
- `test_bot_reminder_policy_api_roundtrip()` — строка ~18

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/content_updates.py`
- `backend/core/settings.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_reschedule_reject.py`

**Тип:** Тест
**Строк кода:** ~175
**Назначение:** Тестовый модуль `test_bot_reschedule_reject`.

**Классы:**
- `DummyMessage` — строка ~16
- `DummyCallback` — строка ~47
- `DummyBot` — строка ~58

**Ключевые функции:**
- `_prepare_slot()` — строка ~70
- `test_reschedule_slot_sends_notice()` — строка ~98
- `test_reject_slot_sends_rejection()` — строка ~139

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_runtime_config.py`

**Тип:** Тест
**Строк кода:** ~62
**Назначение:** Тестовый модуль `test_bot_runtime_config`.

**Ключевые функции:**
- `test_normalize_reminder_policy_sanitizes_payload()` — строка ~13
- `test_get_and_save_reminder_policy_roundtrip()` — строка ~34

**Зависимости (локальные импорты):**
- `backend/apps/bot/runtime_config.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_template_copy_quality.py`

**Тип:** Тест
**Строк кода:** ~59
**Назначение:** Тестовый модуль `test_bot_template_copy_quality`.

**Ключевые функции:**
- `test_candidate_templates_have_full_text_copy()` — строка ~8
- `test_stage_templates_have_no_placeholder_stubs()` — строка ~28
- `test_bot_runtime_template_keys_have_default_texts()` — строка ~36

**Зависимости (локальные импорты):**
- `backend/apps/bot/defaults.py`
- `backend/domain/template_stages.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_test1_notifications.py`

**Тип:** Тест
**Строк кода:** ~277
**Назначение:** Тестовый модуль `test_bot_test1_notifications`.

**Классы:**
- `DummyBot` — строка ~20

**Ключевые функции:**
- `_setup_template_provider()` — строка ~33
- `test_finalize_test1_notifies_recruiter()` — строка ~38
- `test_finalize_test1_deduplicates_by_chat_id()` — строка ~92
- `test_finalize_test1_prompts_candidate_to_schedule()` — строка ~163
- `test_finalize_test1_no_slots_sends_single_manual_prompt()` — строка ~226

**Зависимости (локальные импорты):**
- `backend/apps/bot/config.py`
- `backend/apps/bot/defaults.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bot_test1_validation.py`

**Тип:** Тест
**Строк кода:** ~677
**Назначение:** Тестовый модуль `test_bot_test1_validation`.

**Ключевые функции:**
- `bot_context()` — строка ~35
- `test_save_test1_answer_rejects_non_cyrillic_fio()` — строка ~51
- `test_city_validation_returns_hints()` — строка ~64
- `test_format_not_ready_triggers_rejection()` — строка ~108
- `test_study_schedule_branch_and_reject()` — строка ~152
- `test_study_schedule_hard_response_rejects()` — строка ~217
- `test_format_flexible_request_triggers_clarification()` — строка ~253
- `test_save_test1_answer_uses_dynamic_status_options()` — строка ~285
- `test_resolve_test1_options_uses_display_name()` — строка ~335
- `test_send_test1_question_uses_display_name_in_buttons()` — строка ~359
- `test_send_test1_question_resyncs_sequence_on_bank_version_change()` — строка ~421
- `test_handle_test1_answer_advances_on_success()` — строка ~471
- `test_handle_test1_answer_accepts_text_without_reply()` — строка ~531
- `test_handle_test1_answer_hint_sent_once()` — строка ~586
- `test_handle_test1_answer_ignored_in_chat_mode()` — строка ~632

**Зависимости (локальные импорты):**
- `backend/apps/bot/city_registry.py`
- `backend/apps/bot/config.py`
- `backend/apps/bot/metrics.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_broker_production_restrictions.py`

**Тип:** Тест
**Строк кода:** ~214
**Назначение:** Тестовый модуль `test_broker_production_restrictions`.

**Ключевые функции:**
- `test_inmemory_broker_forbidden_in_production()` — строка ~10
- `test_inmemory_broker_allowed_in_development()` — строка ~61
- `test_redis_required_message_in_production()` — строка ~109
- `test_environment_setting_validation()` — строка ~156

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/state.py`
- `backend/apps/bot/broker.py`
- `backend/core/settings.py`

**Комментарии / явные подсказки в файле:**
- Tests for production environment restrictions on notification broker.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_bulk_slots_timezone_moscow_novosibirsk.py`

**Тип:** Тест
**Строк кода:** ~172
**Назначение:** Тестовый модуль `test_bulk_slots_timezone_moscow_novosibirsk`.

**Ключевые функции:**
- `test_bulk_create_moscow_to_novosibirsk()` — строка ~14
- `test_bulk_create_at_9am()` — строка ~106

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Test bulk slot creation with Moscow-Novosibirsk timezone scenario.

**Состояние / проблемы:**
- console/print: 8

### `tests/test_cache_integration.py`

**Тип:** Тест
**Строк кода:** ~184
**Назначение:** Тестовый модуль `test_cache_integration`.

**Ключевые функции:**
- `test_cache_initialization()` — строка ~13
- `test_slot_repository_uses_cache()` — строка ~36
- `test_cache_health_check()` — строка ~89
- `test_cache_disabled_gracefully()` — строка ~118
- `test_cache_keys_pattern()` — строка ~154
- `test_cache_ttl_values()` — строка ~172

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/system.py`
- `backend/core/cache.py`
- `backend/core/db.py`
- `backend/core/uow.py`
- `backend/domain/models.py`
- `backend/repositories/slot.py`

**Комментарии / явные подсказки в файле:**
- Integration tests for Phase 2 Performance Cache.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_calendar_hub_scope.py`

**Тип:** Тест
**Строк кода:** ~124
**Назначение:** Тестовый модуль `test_calendar_hub_scope`.

**Классы:**
- `_StubWebSocket` — строка ~7

**Ключевые функции:**
- `_payload()` — строка ~22
- `test_recruiter_receives_only_allowed_scope_events()` — строка ~58
- `test_recruiter_payload_is_sanitized()` — строка ~84
- `test_broadcast_removes_stale_websocket_client()` — строка ~111

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/calendar_hub.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_candidate_actions.py`

**Тип:** Тест
**Строк кода:** ~213
**Назначение:** Тестовый модуль `test_candidate_actions`.

**Ключевые функции:**
- `test_status_actions_mapping_complete()` — строка ~11
- `test_terminal_statuses_have_no_actions()` — строка ~35
- `test_action_structure()` — строка ~51
- `test_get_candidate_actions_test1_completed()` — строка ~64
- `test_get_candidate_actions_test2_completed()` — строка ~85
- `test_get_candidate_actions_stalled_waiting_slot()` — строка ~114
- `test_get_candidate_actions_intro_day_confirmed()` — строка ~132
- `test_get_candidate_actions_none_status()` — строка ~153
- `test_get_candidate_actions_lead_status()` — строка ~159
- `test_get_candidate_actions_terminal_status_keeps_test2_action()` — строка ~176
- `test_confirmation_messages()` — строка ~184
- `test_url_patterns_correct()` — строка ~199

**Зависимости (локальные импорты):**
- `backend/domain/candidates/actions.py`
- `backend/domain/candidates/status.py`

**Комментарии / явные подсказки в файле:**
- Test candidate action system for simplified card.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_candidate_chat_threads_api.py`

**Тип:** Тест
**Строк кода:** ~668
**Назначение:** Тестовый модуль `test_candidate_chat_threads_api`.

**Классы:**
- `_DummyIntegration` — строка ~18

**Ключевые функции:**
- `admin_app()` — строка ~24
- `_async_request_with_principal()` — строка ~47
- `test_candidate_chat_threads_count_unread_and_mark_read()` — строка ~67
- `test_candidate_chat_threads_empty_payload_is_stable()` — строка ~147
- `test_candidate_chat_threads_updates_returns_new_activity()` — строка ~170
- `test_candidate_chat_threads_can_be_archived_and_restored()` — строка ~219
- `test_candidate_chat_threads_search_filters_by_name_and_text()` — строка ~301
- `test_candidate_chat_threads_updates_respects_search_and_unread()` — строка ~383
- `test_candidate_chat_threads_prioritize_operational_buckets()` — строка ~476
- `test_candidate_chat_workspace_roundtrip_and_scope()` — строка ~609

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_candidate_lead_and_invite.py`

**Тип:** Тест
**Строк кода:** ~140
**Назначение:** Тестовый модуль `test_candidate_lead_and_invite`.

**Ключевые функции:**
- `test_manual_candidate_creation_lead_status()` — строка ~16
- `test_reserve_slot_by_candidate_id_without_telegram()` — строка ~31
- `test_invite_token_links_telegram_to_lead()` — строка ~78
- `test_invite_token_has_id_and_persists()` — строка ~120

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/candidates.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_candidate_rejection_reason.py`

**Тип:** Тест
**Строк кода:** ~38
**Назначение:** Тестовый модуль `test_candidate_rejection_reason`.

**Ключевые функции:**
- `test_update_candidate_status_with_reason()` — строка ~9

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/candidates.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_candidate_reports.py`

**Тип:** Тест
**Строк кода:** ~97
**Назначение:** Тестовый модуль `test_candidate_reports`.

**Ключевые функции:**
- `test_finalize_test1_generates_report()` — строка ~14
- `test_finalize_test2_generates_report()` — строка ~52

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/state_store.py`
- `backend/domain/candidates/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_candidate_services.py`

**Тип:** Тест
**Строк кода:** ~142
**Назначение:** Тестовый модуль `test_candidate_services`.

**Ключевые функции:**
- `test_create_or_update_user_and_lookup()` — строка ~13
- `test_create_or_update_user_updates_responsible_recruiter()` — строка ~34
- `test_save_test_result_and_statistics()` — строка ~62
- `test_auto_messages_and_notifications()` — строка ~115

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_candidate_status_logic.py`

**Тип:** Тест
**Строк кода:** ~33
**Назначение:** Тестовый модуль `test_candidate_status_logic`.

**Ключевые функции:**
- `test_valid_forward_transitions()` — строка ~11
- `test_status_retreat_detection()` — строка ~17
- `test_next_statuses()` — строка ~30

**Зависимости (локальные импорты):**
- `backend/domain/candidates/status.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_chat_messages.py`

**Тип:** Тест
**Строк кода:** ~197
**Назначение:** Тестовый модуль `test_chat_messages`.

**Классы:**
- `_DummyBotService` — строка ~11

**Ключевые функции:**
- `clean_chat_rate_limits()` — строка ~36
- `test_log_inbound_chat_message_creates_history_record()` — строка ~43
- `test_log_outbound_chat_message_creates_history_record()` — строка ~69
- `test_send_chat_message_updates_status_and_persists()` — строка ~97
- `test_duplicate_client_request_id_returns_existing_message_even_when_limit_reached()` — строка ~126
- `test_retry_chat_message_success_counts_against_rate_limit()` — строка ~160

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_chat_rate_limit.py`

**Тип:** Тест
**Строк кода:** ~147
**Назначение:** Тестовый модуль `test_chat_rate_limit`.

**Ключевые функции:**
- `clean_rate_limit_store()` — строка ~20
- `test_rate_limit_check_allows_first_message()` — строка ~28
- `test_rate_limit_tracks_messages()` — строка ~36
- `test_rate_limit_blocks_when_exceeded()` — строка ~50
- `test_rate_limit_cleans_old_entries()` — строка ~64
- `test_rate_limit_record_adds_timestamp()` — строка ~81
- `test_rate_limit_config_values()` — строка ~95
- `test_multiple_candidates_independent()` — строка ~102
- `test_rate_limit_redis_backend_roundtrip()` — строка ~122

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/__init__.py`

**Комментарии / явные подсказки в файле:**
- Tests for chat rate limiting functionality.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_cities_settings_api.py`

**Тип:** Тест
**Строк кода:** ~86
**Назначение:** Тестовый модуль `test_cities_settings_api`.

**Ключевые функции:**
- `_build_app()` — строка ~9
- `test_update_city_settings_parses_payload()` — строка ~15
- `test_update_city_settings_rejects_invalid_plan_week()` — строка ~70

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_city_experts_sync.py`

**Тип:** Тест
**Строк кода:** ~143
**Назначение:** Тестовый модуль `test_city_experts_sync`.

**Ключевые функции:**
- `test_update_city_settings_syncs_city_experts_from_text()` — строка ~13
- `test_update_city_settings_syncs_city_experts_from_items_and_archives_missing()` — строка ~44
- `test_update_city_settings_schedules_ai_refresh_when_criteria_changed()` — строка ~110

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/cities.py`
- `backend/core/db.py`
- `backend/domain/cities/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_city_hh_vacancies_api.py`

**Тип:** Тест
**Строк кода:** ~286
**Назначение:** Тестовый модуль `test_city_hh_vacancies_api`.

**Классы:**
- `_DummyIntegration` — строка ~16
- `TestCityHHVacanciesApi` — строка ~166

**Ключевые функции:**
- `hh_env()` — строка ~22
- `admin_app()` — строка ~37
- `_seed_city_hh_binding()` — строка ~63
- `_seed_city_with_unbound_hh_vacancy()` — строка ~103
- `_seed_city_without_hh_binding()` — строка ~143

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/hh_integration/client.py`
- `backend/domain/hh_integration/crypto.py`
- `backend/domain/hh_integration/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_city_lookup_variants.py`

**Тип:** Тест
**Строк кода:** ~44
**Назначение:** Тестовый модуль `test_city_lookup_variants`.

**Ключевые функции:**
- `test_resolve_city_by_plain_name_handles_prefixes_and_separators()` — строка ~11
- `test_resolve_city_by_plain_name_normalizes_yo_to_e()` — строка ~33

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_city_reminder_policy.py`

**Тип:** Тест
**Строк кода:** ~98
**Назначение:** Тестовый модуль `test_city_reminder_policy`.

**Ключевые функции:**
- `test_city()` — строка ~16
- `test_get_returns_global_defaults_when_no_custom_policy()` — строка ~35
- `test_upsert_creates_custom_policy()` — строка ~43
- `test_get_returns_custom_policy_after_upsert()` — строка ~59
- `test_delete_resets_to_global_defaults()` — строка ~73
- `test_delete_nonexistent_returns_false()` — строка ~84
- `test_quiet_hours_clamped_to_valid_range()` — строка ~90

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/city_reminder_policy.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Tests for per-city reminder policy service.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_city_template_resolution.py`

**Тип:** Тест
**Строк кода:** ~104
**Назначение:** Тестовый модуль `test_city_template_resolution`.

**Ключевые функции:**
- `_cleanup_template()` — строка ~12
- `test_city_template_overrides_default()` — строка ~19
- `test_template_falls_back_to_default_when_city_missing()` — строка ~65
- `test_missing_template_raises_friendly_error()` — строка ~98

**Зависимости (локальные импорты):**
- `backend/apps/bot/template_provider.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_content_updates.py`

**Тип:** Тест
**Строк кода:** ~61
**Назначение:** Тестовый модуль `test_content_updates`.

**Ключевые функции:**
- `test_content_update_parse_roundtrip()` — строка ~11
- `test_content_update_parse_invalid_returns_none()` — строка ~20
- `test_notification_service_invalidate_template_cache_calls_provider()` — строка ~27

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/core/content_updates.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_delete_past_free_slots.py`

**Тип:** Тест
**Строк кода:** ~63
**Назначение:** Тестовый модуль `test_delete_past_free_slots`.

**Ключевые функции:**
- `test_delete_past_free_slots_removes_only_stale_free_interview()` — строка ~14

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Cleanup of past free interview slots.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_dependency_injection.py`

**Тип:** Тест
**Строк кода:** ~155
**Назначение:** Тестовый модуль `test_dependency_injection`.

**Ключевые функции:**
- `test_get_async_session_dependency()` — строка ~12
- `test_get_uow_dependency()` — строка ~30
- `test_uow_dependency_provides_repositories()` — строка ~55
- `test_dependency_imports()` — строка ~81
- `test_session_exception_handling()` — строка ~98
- `test_uow_no_auto_commit()` — строка ~123

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/dependencies.py`
- `backend/core/uow.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Tests for FastAPI Dependency Injection.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_detailization_report.py`

**Тип:** Тест
**Строк кода:** ~250
**Назначение:** Тестовый модуль `test_detailization_report`.

**Ключевые функции:**
- `_run()` — строка ~16
- `_seed_intro_day_assignment()` — строка ~26
- `test_detailization_autocreates_and_lists_rows()` — строка ~92
- `test_detailization_excludes_criteria_mismatch()` — строка ~115
- `test_detailization_excludes_no_show()` — строка ~130
- `test_detailization_patch_updates_manual_fields()` — строка ~145
- `test_detailization_delete_removes_row()` — строка ~179
- `test_detailization_supports_final_outcome_reason_and_export()` — строка ~209

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_domain_repositories.py`

**Тип:** Тест
**Строк кода:** ~162
**Назначение:** Тестовый модуль `test_domain_repositories`.

**Ключевые функции:**
- `test_recruiter_and_city_queries()` — строка ~28
- `test_city_helpers_cover_casefold_and_slots()` — строка ~59
- `test_city_recruiter_lookup_includes_slot_owners()` — строка ~88
- `test_candidate_cities_fallback_returns_active_entries()` — строка ~119
- `test_iam_command_updates_recruiter_chat_id()` — строка ~133

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_double_booking.py`

**Тип:** Тест
**Строк кода:** ~133
**Назначение:** Тестовый модуль `test_double_booking`.

**Ключевые функции:**
- `test_confirmed_candidate_cannot_double_book_same_recruiter()` — строка ~16
- `test_confirmed_candidate_can_book_other_recruiter()` — строка ~76

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_e2e_notification_flow.py`

**Тип:** Тест
**Строк кода:** ~73
**Назначение:** Тестовый модуль `test_e2e_notification_flow`.

**Ключевые функции:**
- `test_e2e_notification_refactor()` — строка ~9

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/message_templates.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/template_provider.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_hh_integration_actions.py`

**Тип:** Тест
**Строк кода:** ~228
**Назначение:** Тестовый модуль `test_hh_integration_actions`.

**Классы:**
- `_DummyIntegration` — строка ~37
- `TestHHActionsRoutes` — строка ~165

**Ключевые функции:**
- `hh_env()` — строка ~23
- `admin_app()` — строка ~43
- `_seed_candidate_with_hh_action()` — строка ~71

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/hh_integration/crypto.py`
- `backend/domain/hh_integration/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_hh_integration_client.py`

**Тип:** Тест
**Строк кода:** ~29
**Назначение:** Тестовый модуль `test_hh_integration_client`.

**Ключевые функции:**
- `test_list_negotiations_collection_preserves_vacancy_id_query()` — строка ~10

**Зависимости (локальные импорты):**
- `backend/domain/hh_integration/client.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_hh_integration_foundation.py`

**Тип:** Тест
**Строк кода:** ~409
**Назначение:** Тестовый модуль `test_hh_integration_foundation`.

**Классы:**
- `_DummyIntegration` — строка ~34
- `TestHHOAuthHelpers` — строка ~79
- `TestHHOAuthRoutes` — строка ~126
- `TestHHWebhookReceiver` — строка ~329

**Ключевые функции:**
- `hh_env()` — строка ~20
- `admin_app()` — строка ~40
- `admin_api_app()` — строка ~67

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/hh_integration/client.py`
- `backend/domain/hh_integration/crypto.py`
- `backend/domain/hh_integration/models.py`
- `backend/domain/hh_integration/oauth.py`
- `backend/domain/hh_integration/service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_hh_integration_import.py`

**Тип:** Тест
**Строк кода:** ~505
**Назначение:** Тестовый модуль `test_hh_integration_import`.

**Классы:**
- `_DummyIntegration` — строка ~36
- `TestHHImportRoutes` — строка ~68

**Ключевые функции:**
- `hh_env()` — строка ~22
- `admin_app()` — строка ~42

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/hh_integration/crypto.py`
- `backend/domain/hh_integration/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_hh_integration_jobs.py`

**Тип:** Тест
**Строк кода:** ~174
**Назначение:** Тестовый модуль `test_hh_integration_jobs`.

**Классы:**
- `_DummyIntegration` — строка ~37
- `TestHHJobQueue` — строка ~99
- `TestHHJobRoutes` — строка ~154

**Ключевые функции:**
- `hh_env()` — строка ~23
- `admin_app()` — строка ~43
- `_seed_connection_with_vacancy()` — строка ~69

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/hh_integration/crypto.py`
- `backend/domain/hh_integration/jobs.py`
- `backend/domain/hh_integration/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_hh_integration_migrations.py`

**Тип:** Тест
**Строк кода:** ~37
**Назначение:** Тестовый модуль `test_hh_integration_migrations`.

**Ключевые функции:**
- `test_hh_foundation_migrations_apply_on_existing_schema()` — строка ~16

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_hh_sync.py`

**Тип:** Тест
**Строк кода:** ~369
**Назначение:** Тестовый модуль `test_hh_sync`.

**Классы:**
- `TestHHStatusMapping` — строка ~29
- `TestResumeURLParser` — строка ~86
- `TestDispatcher` — строка ~143
- `TestCallbackHandlers` — строка ~260

**Ключевые функции:**
- `_create_candidate()` — строка ~120

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/hh_sync/dispatcher.py`
- `backend/domain/hh_sync/mapping.py`
- `backend/domain/hh_sync/models.py`
- `backend/domain/hh_sync/resolver.py`
- `backend/domain/hh_sync/worker.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Tests for hh.ru sync integration: mapping, resolver, dispatcher.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_interview_script_ai.py`

**Тип:** Тест
**Строк кода:** ~459
**Назначение:** Тестовый модуль `test_interview_script_ai`.

**Классы:**
- `_DummyIntegration` — строка ~22

**Ключевые функции:**
- `ai_interview_app()` — строка ~28
- `_run()` — строка ~54
- `_csrf()` — строка ~63
- `test_normalize_hh_resume_raw_text_and_json()` — строка ~71
- `test_base_risk_flags_and_merge_preserve_deterministic_flags()` — строка ~94
- `test_interview_script_ab_model_selection_is_deterministic()` — строка ~126
- `test_generate_interview_script_retries_invalid_payload_then_succeeds()` — строка ~145
- `test_generate_interview_script_suppresses_od_cta_for_not_recommended()` — строка ~227
- `test_generate_interview_script_uses_stage_aware_confirmation_flow()` — строка ~275
- `test_interview_script_generate_cache_and_refresh()` — строка ~330
- `test_interview_script_hh_resume_upsert()` — строка ~380
- `test_interview_script_route_uses_local_fallback_on_initial_load()` — строка ~430

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/ai/llm_script_generator.py`
- `backend/core/ai/providers/base.py`
- `backend/core/ai/service.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_interview_script_feedback.py`

**Тип:** Тест
**Строк кода:** ~184
**Назначение:** Тестовый модуль `test_interview_script_feedback`.

**Классы:**
- `_DummyIntegration` — строка ~16

**Ключевые функции:**
- `ai_feedback_app()` — строка ~22
- `_run()` — строка ~48
- `_csrf()` — строка ~57
- `test_interview_script_feedback_persists_and_idempotent()` — строка ~65
- `test_interview_script_feedback_requires_csrf_and_valid_payload()` — строка ~158

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/ai/models.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_intro_day_e2e.py`

**Тип:** Тест
**Строк кода:** ~236
**Назначение:** Тестовый модуль `test_intro_day_e2e`.

**Ключевые функции:**
- `test_intro_day_notification_end_to_end()` — строка ~21
- `test_notification_service_processes_intro_day()` — строка ~102
- `test_notification_broker_publishes_and_reads()` — строка ~200

**Зависимости (локальные импорты):**
- `backend/apps/bot/broker.py`
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- End-to-end test for intro_day notification flow.

**Состояние / проблемы:**
- console/print: 11

### `tests/test_intro_day_flow.py`

**Тип:** Тест
**Строк кода:** ~78
**Назначение:** Тестовый модуль `test_intro_day_flow`.

**Классы:**
- `DummyBot` — строка ~14
- `DummyMessage` — строка ~22

**Ключевые функции:**
- `test_intro_day_decline_reason_saved_and_sent()` — строка ~34

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_intro_day_notifications.py`

**Тип:** Тест
**Строк кода:** ~148
**Назначение:** Тестовый модуль `test_intro_day_notifications`.

**Ключевые функции:**
- `test_intro_day_template_defaults_without_city_specific()` — строка ~13
- `test_intro_day_template_prefers_city_specific()` — строка ~41
- `_build_slot()` — строка ~89
- `test_render_candidate_notification_uses_intro_template()` — строка ~105
- `test_render_candidate_notification_for_interview()` — строка ~130

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_intro_day_recruiter_scope.py`

**Тип:** Тест
**Строк кода:** ~581
**Назначение:** Тестовый модуль `test_intro_day_recruiter_scope`.

**Классы:**
- `_DummyIntegration` — строка ~18

**Ключевые функции:**
- `recruiter_scoped_app()` — строка ~24
- `_request_with_recruiter_principal()` — строка ~47
- `test_recruiter_can_schedule_intro_day_for_self_even_if_city_has_other_default()` — строка ~66
- `test_recruiter_can_schedule_intro_day_via_api_without_recruiter_id()` — строка ~120
- `test_candidates_route_uses_city_intro_day_template_when_custom_message_empty()` — строка ~172
- `test_api_route_uses_city_intro_day_template_when_custom_message_empty()` — строка ~252
- `test_recruiter_can_schedule_intro_day_twice_same_time_via_candidates_route()` — строка ~331
- `test_recruiter_can_schedule_intro_day_twice_same_time_via_api_route()` — строка ~391
- `test_schedule_intro_day_cancels_active_interview_slot_via_candidates_route()` — строка ~449
- `test_schedule_intro_day_cancels_active_interview_slot_via_api_route()` — строка ~517

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_intro_day_slot_isolation.py`

**Тип:** Тест
**Строк кода:** ~163
**Назначение:** Тестовый модуль `test_intro_day_slot_isolation`.

**Ключевые функции:**
- `test_intro_day_not_counted_as_available_slot()` — строка ~13
- `test_intro_day_slot_cannot_be_booked_as_interview()` — строка ~39
- `test_intro_day_slot_can_be_reserved_with_matching_purpose()` — строка ~71
- `test_intro_day_booking_blocks_interview_booking_for_same_candidate()` — строка ~106

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Intro day slots must not affect interview slot availability and bookings.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_intro_day_status.py`

**Тип:** Тест
**Строк кода:** ~78
**Назначение:** Тестовый модуль `test_intro_day_status`.

**Ключевые функции:**
- `test_intro_day_confirmation_updates_status()` — строка ~14
- `test_build_candidate_journey_downgrades_day_of_status_for_future_intro_day_slot()` — строка ~56

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/journey.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_jinja_renderer.py`

**Тип:** Тест
**Строк кода:** ~18
**Назначение:** Тестовый модуль `test_jinja_renderer`.

**Ключевые функции:**
- `test_render_simple()` — строка ~4
- `test_render_missing_var()` — строка ~9
- `test_render_complex()` — строка ~15

**Зависимости (локальные импорты):**
- `backend/utils/jinja_renderer.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_kb_active_documents_list.py`

**Тип:** Тест
**Строк кода:** ~30
**Назначение:** Тестовый модуль `test_kb_active_documents_list`.

**Ключевые функции:**
- `test_list_active_documents_returns_recent_titles()` — строка ~10

**Зависимости (локальные импорты):**
- `backend/core/ai/knowledge_base.py`
- `backend/core/db.py`
- `backend/domain/ai/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_kb_and_ai_agent_chat.py`

**Тип:** Тест
**Строк кода:** ~131
**Назначение:** Тестовый модуль `test_kb_and_ai_agent_chat`.

**Классы:**
- `_DummyIntegration` — строка ~12

**Ключевые функции:**
- `ai_kb_app()` — строка ~18
- `_csrf()` — строка ~44
- `test_kb_document_create_and_agent_chat_returns_excerpts()` — строка ~52
- `_make_docx_bytes()` — строка ~93
- `test_kb_document_upload_docx_extracts_text()` — строка ~108

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_manual_slot_assignment.py`

**Тип:** Тест
**Строк кода:** ~249
**Назначение:** Тестовый модуль `test_manual_slot_assignment`.

**Ключевые функции:**
- `test_manual_slot_scheduling_flow()` — строка ~19
- `_setup_candidate_recruiter()` — строка ~81
- `test_schedule_manual_slot_handles_naive_conflicts()` — строка ~105
- `test_schedule_manual_slot_normalizes_naive_input()` — строка ~138
- `test_schedule_manual_slot_creates_entry_without_conflicts()` — строка ~171
- `test_schedule_manual_slot_ignores_intro_day_slot_conflict()` — строка ~207

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/core/time_utils.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/status.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_manual_slot_booking_api.py`

**Тип:** Тест
**Строк кода:** ~175
**Назначение:** Тестовый модуль `test_manual_slot_booking_api`.

**Классы:**
- `_DummyIntegration` — строка ~17

**Ключевые функции:**
- `admin_app()` — строка ~23
- `_seed_recruiter_city()` — строка ~46
- `_request()` — строка ~58
- `test_manual_booking_creates_silent_candidate_without_outbox()` — строка ~65
- `test_manual_booking_can_bind_existing_free_slot_without_telegram()` — строка ~107

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_max_bot.py`

**Тип:** Тест
**Строк кода:** ~238
**Назначение:** Тестовый модуль `test_max_bot`.

**Классы:**
- `TestHealthCheck` — строка ~56
- `TestWebhookSecurity` — строка ~68
- `TestEventRouting` — строка ~124
- `TestBotStarted` — строка ~138
- `TestMessageCallback` — строка ~177
- `TestVerifySecret` — строка ~217

**Ключевые функции:**
- `_make_settings()` — строка ~19
- `mock_settings()` — строка ~36
- `client()` — строка ~43

**Зависимости (локальные импорты):**
- `backend/apps/max_bot/app.py`

**Комментарии / явные подсказки в файле:**
- Tests for the VK Max bot webhook handler (Phase 3).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_max_sales_handoff.py`

**Тип:** Тест
**Строк кода:** ~179
**Назначение:** Тестовый модуль `test_max_sales_handoff`.

**Классы:**
- `_FakeMaxAdapter` — строка ~16

**Ключевые функции:**
- `_isolated_registry()` — строка ~50
- `_context()` — строка ~56
- `test_handoff_skips_when_feature_disabled()` — строка ~75
- `test_handoff_prefers_recruiter_route()` — строка ~90
- `test_handoff_uses_city_name_route()` — строка ~121
- `test_handoff_reports_partial_failures()` — строка ~150

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/max_sales_handoff.py`
- `backend/core/messenger/protocol.py`
- `backend/core/messenger/registry.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_message_templates_rbac.py`

**Тип:** Тест
**Строк кода:** ~200
**Назначение:** Тестовый модуль `test_message_templates_rbac`.

**Классы:**
- `_DummyIntegration` — строка ~14

**Ключевые функции:**
- `admin_app()` — строка ~20
- `_request_with_principal()` — строка ~43
- `test_recruiter_template_list_is_city_scoped_and_global_read_only()` — строка ~57
- `test_recruiter_cannot_create_global_or_system_template()` — строка ~129

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_messenger.py`

**Тип:** Тест
**Строк кода:** ~488
**Назначение:** Тестовый модуль `test_messenger`.

**Классы:**
- `TestMessengerPlatform` — строка ~37
- `TestSendResult` — строка ~66
- `TestInlineButton` — строка ~87
- `_FakeAdapter` — строка ~97
- `TestMessengerRegistry` — строка ~120
- `TestResolveAdapterForCandidate` — строка ~161
- `TestTelegramAdapter` — строка ~232
- `TestMaxAdapter` — строка ~317
- `TestBootstrap` — строка ~425

**Зависимости (локальные импорты):**
- `backend/core/messenger/bootstrap.py`
- `backend/core/messenger/max_adapter.py`
- `backend/core/messenger/protocol.py`
- `backend/core/messenger/registry.py`
- `backend/core/messenger/telegram_adapter.py`

**Комментарии / явные подсказки в файле:**
- Tests for the messenger abstraction layer (Phase 2).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_migration_runner_privileges.py`

**Тип:** Тест
**Строк кода:** ~47
**Назначение:** Тестовый модуль `test_migration_runner_privileges`.

**Классы:**
- `_ScalarResult` — строка ~10
- `_FakeConnection` — строка ~18

**Ключевые функции:**
- `test_preflight_skips_non_postgres()` — строка ~33
- `test_preflight_passes_when_create_privilege_present()` — строка ~38
- `test_preflight_fails_without_create_privilege()` — строка ~43

**Зависимости (локальные импорты):**
- `backend/migrations/runner.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_notification_bootstrap.py`

**Тип:** Тест
**Строк кода:** ~25
**Назначение:** Тестовый модуль `test_notification_bootstrap`.

**Ключевые функции:**
- `test_notification_service_reinitializes_after_reset()` — строка ~8

**Зависимости (локальные импорты):**
- `backend/apps/bot/notifications/__init__.py`
- `backend/apps/bot/reminders.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_notification_log_idempotency.py`

**Тип:** Тест
**Строк кода:** ~61
**Назначение:** Тестовый модуль `test_notification_log_idempotency`.

**Ключевые функции:**
- `test_add_notification_log_is_idempotent_for_same_booking()` — строка ~11

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_notification_logs.py`

**Тип:** Тест
**Строк кода:** ~182
**Назначение:** Тестовый модуль `test_notification_logs`.

**Классы:**
- `DummyMessage` — строка ~21
- `DummyApproveCallback` — строка ~31
- `DummyBot` — строка ~43

**Ключевые функции:**
- `test_reapprove_after_reschedule_notifies_new_candidate()` — строка ~53

**Зависимости (локальные импорты):**
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_notification_retry.py`

**Тип:** Тест
**Строк кода:** ~1134
**Назначение:** Тестовый модуль `test_notification_retry`.

**Ключевые функции:**
- `test_retry_with_backoff_and_jitter()` — строка ~37
- `test_poll_once_handles_duplicate_notification_logs()` — строка ~177
- `test_candidate_rejection_uses_message_template()` — строка ~277
- `test_fatal_error_marks_outbox_failed()` — строка ~387
- `test_unauthorized_error_marks_outbox_failed_without_retry()` — строка ~472
- `test_broker_dlq_on_max_attempts()` — строка ~551
- `test_broker_bootstrap_from_outbox()` — строка ~624
- `test_direct_fallback_marks_outbox_sent()` — строка ~748
- `test_direct_fallback_failure_sets_error()` — строка ~822
- `test_reschedule_requested_recruiter_marks_failed_when_assignment_missing()` — строка ~895
- `test_reschedule_requested_recruiter_marks_sent()` — строка ~943
- `test_reschedule_requested_recruiter_marks_failed_when_candidate_missing()` — строка ~1037
- `test_notification_service_health_snapshot_reports_broker()` — строка ~1122

**Зависимости (локальные импорты):**
- `backend/apps/bot/broker.py`
- `backend/apps/bot/metrics.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_openai_provider_params.py`

**Тип:** Тест
**Строк кода:** ~21
**Назначение:** Тестовый модуль `test_openai_provider_params`.

**Ключевые функции:**
- `test_openai_provider_token_param_name_for_model_gpt5()` — строка ~6
- `test_openai_provider_token_param_name_for_model_legacy()` — строка ~12
- `test_openai_provider_supports_temperature_by_model_family()` — строка ~18

**Зависимости (локальные импорты):**
- `backend/core/ai/providers/openai.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_openai_provider_responses_api.py`

**Тип:** Тест
**Строк кода:** ~249
**Назначение:** Тестовый модуль `test_openai_provider_responses_api`.

**Классы:**
- `DummySettings` — строка ~8
- `_DummyResponse` — строка ~13

**Ключевые функции:**
- `_install_dummy_client_session()` — строка ~28
- `_install_dummy_client_session_sequence()` — строка ~48
- `test_gpt5_uses_responses_api_and_parses_output()` — строка ~70
- `test_gpt5_repairs_malformed_json_from_json_mode()` — строка ~111
- `test_gpt5_repairs_truncated_json()` — строка ~165
- `test_gpt4o_uses_chat_completions()` — строка ~219

**Зависимости (локальные импорты):**
- `backend/core/ai/providers/openai.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_outbox_deduplication.py`

**Тип:** Тест
**Строк кода:** ~287
**Назначение:** Тестовый модуль `test_outbox_deduplication`.

**Ключевые функции:**
- `test_add_outbox_notification_is_idempotent_for_sent_entries()` — строка ~20
- `test_add_outbox_notification_reuses_pending_entries()` — строка ~112
- `test_add_outbox_notification_different_types_are_separate()` — строка ~179
- `test_claim_outbox_item_by_id_is_single_consumer()` — строка ~251

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Tests for outbox notification deduplication.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_outbox_notifications.py`

**Тип:** Тест
**Строк кода:** ~75
**Назначение:** Тестовый модуль `test_outbox_notifications`.

**Ключевые функции:**
- `test_retry_marks_failed_when_exceeds_max_attempts()` — строка ~16

**Зависимости (локальные импорты):**
- `backend/apps/bot/broker.py`
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_perf_cache_keys.py`

**Тип:** Тест
**Строк кода:** ~38
**Назначение:** Тестовый модуль `test_perf_cache_keys`.

**Ключевые функции:**
- `test_dashboard_keys_are_scoped_by_principal()` — строка ~9
- `test_calendar_key_normalizes_statuses_order_and_case()` — строка ~17

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/perf/cache/__init__.py`
- `backend/apps/admin_ui/security.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_perf_cache_stale_revalidate.py`

**Тип:** Тест
**Строк кода:** ~65
**Назначение:** Тестовый модуль `test_perf_cache_stale_revalidate`.

**Ключевые функции:**
- `test_get_or_compute_serves_stale_and_refreshes_in_background()` — строка ~12

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_perf_metrics_endpoint.py`

**Тип:** Тест
**Строк кода:** ~54
**Назначение:** Тестовый модуль `test_perf_metrics_endpoint`.

**Ключевые функции:**
- `test_metrics_endpoint_disabled()` — строка ~10
- `test_metrics_endpoint_enabled()` — строка ~19
- `test_metrics_endpoint_rejects_non_allowlisted_ip_without_auth()` — строка ~34
- `test_metrics_default_disabled_in_production()` — строка ~46

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/routers/__init__.py`
- `backend/core/settings.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_prod_config_simple.py`

**Тип:** Тест
**Строк кода:** ~384
**Назначение:** Тестовый модуль `test_prod_config_simple`.

**Ключевые функции:**
- `_set_admin_credentials()` — строка ~16
- `test_prod_rejects_missing_database_url()` — строка ~23
- `test_prod_rejects_sqlite()` — строка ~45
- `test_prod_accepts_postgresql()` — строка ~67
- `test_prod_rejects_missing_redis_url()` — строка ~93
- `test_prod_rejects_non_redis_broker()` — строка ~115
- `test_prod_rejects_missing_bot_backend_url_when_bot_enabled()` — строка ~137
- `test_prod_rejects_data_dir_in_repo()` — строка ~166
- `test_dev_requires_postgresql()` — строка ~191
- `test_prod_rejects_missing_session_secret()` — строка ~211
- `test_prod_rejects_short_session_secret()` — строка ~239
- `test_prod_rejects_unwritable_data_dir()` — строка ~266
- `test_validation_skipped_in_development()` — строка ~303
- `test_validation_skipped_in_staging()` — строка ~331
- `test_validation_case_insensitive()` — строка ~355

**Зависимости (локальные импорты):**
- `backend/core/__init__.py`

**Комментарии / явные подсказки в файле:**
- Simplified tests for production configuration validation guards.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_prod_requires_redis.py`

**Тип:** Тест
**Строк кода:** ~45
**Назначение:** Тестовый модуль `test_prod_requires_redis`.

**Ключевые функции:**
- `test_prod_without_redis_url_fails_at_settings_level()` — строка ~12

**Зависимости (локальные импорты):**
- `backend/core/__init__.py`

**Комментарии / явные подсказки в файле:**
- Test that production environment requires Redis configuration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_profile_avatar_api.py`

**Тип:** Тест
**Строк кода:** ~82
**Назначение:** Тестовый модуль `test_profile_avatar_api`.

**Классы:**
- `_DummyIntegration` — строка ~8

**Ключевые функции:**
- `admin_app()` — строка ~14
- `_login_admin()` — строка ~35
- `test_profile_avatar_upload_and_delete()` — строка ~48

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_profile_settings_api.py`

**Тип:** Тест
**Строк кода:** ~317
**Назначение:** Тестовый модуль `test_profile_settings_api`.

**Классы:**
- `_DummyIntegration` — строка ~17

**Ключевые функции:**
- `profile_settings_app()` — строка ~23
- `_create_recruiter_account()` — строка ~44
- `_get_recruiter_state()` — строка ~70
- `_get_recruiter_account()` — строка ~82
- `_deactivate_recruiter_account()` — строка ~92
- `_login()` — строка ~103
- `_csrf()` — строка ~116
- `test_recruiter_can_update_profile_settings()` — строка ~124
- `test_recruiter_bearer_token_can_access_profile()` — строка ~161
- `test_recruiter_bearer_token_rejects_expired_token()` — строка ~183
- `test_recruiter_bearer_token_rejects_deactivated_account()` — строка ~198
- `test_recruiter_profile_settings_reject_invalid_telemost_url()` — строка ~220
- `test_recruiter_can_change_password()` — строка ~242
- `test_recruiter_change_password_requires_valid_current_password()` — строка ~271
- `test_profile_mutations_forbidden_for_admin()` — строка ~292

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/auth.py`
- `backend/core/db.py`
- `backend/core/passwords.py`
- `backend/domain/auth_account.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_questions_reorder_api.py`

**Тип:** Тест
**Строк кода:** ~160
**Назначение:** Тестовый модуль `test_questions_reorder_api`.

**Классы:**
- `_DummyIntegration` — строка ~13

**Ключевые функции:**
- `_run()` — строка ~18
- `questions_app()` — строка ~28
- `_csrf()` — строка ~54
- `_seed_test1_questions()` — строка ~62
- `test_questions_reorder_updates_order_and_listing()` — строка ~107
- `test_questions_reorder_rejects_partial_payload()` — строка ~129
- `test_questions_reorder_rejects_duplicate_ids()` — строка ~145

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/tests/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_rate_limiting.py`

**Тип:** Тест
**Строк кода:** ~332
**Назначение:** Тестовый модуль `test_rate_limiting`.

**Классы:**
- `_DummyIntegration` — строка ~18

**Ключевые функции:**
- `rate_limited_app()` — строка ~24
- `rate_limited_app_with_proxy_trust()` — строка ~58
- `disabled_rate_limit_app()` — строка ~91
- `_async_request()` — строка ~121
- `test_rate_limit_enforced_after_limit_exceeded()` — строка ~132
- `test_different_ips_have_independent_limits()` — строка ~163
- `test_disabled_rate_limiting_allows_unlimited_requests()` — строка ~195
- `test_x_forwarded_for_respected_when_trust_enabled()` — строка ~214
- `test_x_forwarded_for_ignored_when_trust_disabled()` — строка ~257
- `test_rate_limit_resets_after_window()` — строка ~290

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`

**Комментарии / явные подсказки в файле:**
- Tests for Redis-backed rate limiting.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_recruiter_service.py`

**Тип:** Тест
**Строк кода:** ~194
**Назначение:** Тестовый модуль `test_recruiter_service`.

**Ключевые функции:**
- `test_status_code_roundtrip()` — строка ~26
- `test_status_codes_are_short()` — строка ~34
- `test_no_duplicate_codes()` — строка ~41
- `test_crm_candidate_url_with_base()` — строка ~52
- `test_crm_candidate_url_without_base()` — строка ~61
- `test_crm_base_url_prefers_public_url()` — строка ~70
- `test_crm_base_url_falls_back_to_bot_backend_url()` — строка ~85
- `test_handle_recruiter_free_text_no_state()` — строка ~106
- `test_handle_recruiter_free_text_with_state()` — строка ~126

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/apps/bot/recruiter_service.py`
- `backend/domain/candidates/status.py`

**Комментарии / явные подсказки в файле:**
- Tests for recruiter_service.py — Phase 2 flows.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_recruiter_timezone_conversion.py`

**Тип:** Тест
**Строк кода:** ~183
**Назначение:** Тестовый модуль `test_recruiter_timezone_conversion`.

**Ключевые функции:**
- `test_recruiter_time_converts_to_candidate_timezone()` — строка ~19
- `test_same_timezone_no_conversion()` — строка ~81
- `test_ekaterinburg_timezone_conversion()` — строка ~133

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Тесты для проверки конвертации времени рекрутера в timezone города кандидата.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_reminder_service.py`

**Тип:** Тест
**Строк кода:** ~789
**Назначение:** Тестовый модуль `test_reminder_service`.

**Классы:**
- `DummyBucket` — строка ~25
- `FakeRetryAfter` — строка ~33

**Ключевые функции:**
- `_ensure_message_template()` — строка ~40
- `_create_booked_slot()` — строка ~64
- `test_reminder_service_schedules_and_reschedules()` — строка ~100
- `test_quiet_hours_adjustment_and_metrics()` — строка ~163
- `test_cancel_for_slot_removes_scheduler_jobs_after_slot_deleted()` — строка ~220
- `test_schedule_uses_candidate_city_tz_when_slot_tz_missing()` — строка ~245
- `test_reminder_service_survives_restart()` — строка ~297
- `test_reminders_sent_immediately_for_past_targets()` — строка ~340
- `test_reminder_retry_backoff_on_channel_failure()` — строка ~384
- `test_reminder_retry_honors_retry_after_hint()` — строка ~434
- `test_slot_reminder_uses_candidate_city_tz_and_link_aliases()` — строка ~481
- `test_intro_day_gets_three_hour_reminder()` — строка ~574
- `test_schedule_can_skip_confirmation_prompts()` — строка ~611
- `test_execute_job_enqueues_outbox_notification()` — строка ~657
- `test_execute_job_skips_when_policy_disables_kind()` — строка ~709
- `test_schedule_respects_non_canonical_timezone()` — строка ~776

**Зависимости (локальные импорты):**
- `backend/apps/bot/broker.py`
- `backend/apps/bot/metrics.py`
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/services.py`
- `backend/apps/bot/state_store.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_reminders_schedule.py`

**Тип:** Тест
**Строк кода:** ~80
**Назначение:** Тестовый модуль `test_reminders_schedule`.

**Ключевые функции:**
- `_service()` — строка ~10
- `test_interview_schedule_contains_2h_3h_6h()` — строка ~15
- `test_quiet_hours_adjustment_moves_to_previous_evening()` — строка ~28
- `test_policy_can_disable_interview_reminders()` — строка ~46
- `test_policy_can_adjust_reminder_offsets()` — строка ~64

**Зависимости (локальные импорты):**
- `backend/apps/bot/reminders.py`
- `backend/apps/bot/runtime_config.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_reschedule_requests_scoping.py`

**Тип:** Тест
**Строк кода:** ~135
**Назначение:** Тестовый модуль `test_reschedule_requests_scoping`.

**Ключевые функции:**
- `_seed_requests()` — строка ~18
- `test_reschedule_list_scopes_by_recruiter()` — строка ~101
- `test_reschedule_actions_block_unauthorized_recruiter()` — строка ~118

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/reschedule_requests.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_run_migrations_contract.py`

**Тип:** Тест
**Строк кода:** ~56
**Назначение:** Тестовый модуль `test_run_migrations_contract`.

**Ключевые функции:**
- `test_production_requires_migrations_database_url()` — строка ~8
- `test_production_uses_migrations_database_url()` — строка ~18
- `test_non_production_falls_back_to_database_url()` — строка ~30
- `test_migrations_database_url_has_priority_in_non_production()` — строка ~41
- `test_non_production_without_any_database_url_fails()` — строка ~53

**Зависимости (локальные импорты):**
- `scripts/run_migrations.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_scoping_guards.py`

**Тип:** Тест
**Строк кода:** ~56
**Назначение:** Тестовый модуль `test_scoping_guards`.

**Ключевые функции:**
- `_extract_values()` — строка ~12
- `test_scope_candidates_filters_by_recruiter()` — строка ~21
- `test_scope_slots_filters_by_recruiter()` — строка ~28
- `test_scope_cities_filters_by_recruiter_m2m()` — строка ~35
- `test_ensure_candidate_scope_blocks_foreign_candidate()` — строка ~43
- `test_ensure_slot_scope_allows_owner_and_admin()` — строка ~50

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/security.py`
- `backend/core/guards.py`
- `backend/core/scoping.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_security_auth_hardening.py`

**Тип:** Тест
**Строк кода:** ~163
**Назначение:** Тестовый модуль `test_security_auth_hardening`.

**Классы:**
- `_DummyIntegration` — строка ~14

**Ключевые функции:**
- `secure_app()` — строка ~20
- `test_security_headers_present()` — строка ~57
- `test_auth_token_bruteforce_lock()` — строка ~67
- `test_legacy_admin_session_is_normalized()` — строка ~93
- `test_local_session_wins_over_conflicting_bearer()` — строка ~122

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/routers/auth.py`
- `backend/apps/admin_ui/security.py`
- `backend/core/__init__.py`
- `backend/core/auth.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_session_cookie_config.py`

**Тип:** Тест
**Строк кода:** ~56
**Назначение:** Тестовый модуль `test_session_cookie_config`.

**Ключевые функции:**
- `_build_app()` — строка ~7
- `_get_session_middleware()` — строка ~36
- `test_session_cookie_not_secure_in_dev()` — строка ~40
- `test_session_cookie_not_secure_in_test()` — строка ~46
- `test_session_cookie_secure_in_prod()` — строка ~52

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_simulator_api.py`

**Тип:** Тест
**Строк кода:** ~110
**Назначение:** Тестовый модуль `test_simulator_api`.

**Классы:**
- `_DummyIntegration` — строка ~8

**Ключевые функции:**
- `simulator_app()` — строка ~14
- `disabled_simulator_app()` — строка ~40
- `test_simulator_run_and_report()` — строка ~69
- `test_simulator_disabled_returns_404()` — строка ~104

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_approval_notifications.py`

**Тип:** Тест
**Строк кода:** ~61
**Назначение:** Тестовый модуль `test_slot_approval_notifications`.

**Ключевые функции:**
- `test_force_notify_resends_for_booked_slot()` — строка ~13

**Зависимости (локальные импорты):**
- `backend/apps/bot/__init__.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_assignment_reschedule_replace.py`

**Тип:** Тест
**Строк кода:** ~106
**Назначение:** Тестовый модуль `test_slot_assignment_reschedule_replace`.

**Ключевые функции:**
- `test_confirm_assignment_replaces_existing_slot_during_reschedule()` — строка ~11

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_assignment_slot_sync.py`

**Тип:** Тест
**Строк кода:** ~146
**Назначение:** Тестовый модуль `test_slot_assignment_slot_sync`.

**Ключевые функции:**
- `test_create_slot_assignment_syncs_slot_candidate_binding()` — строка ~14
- `test_confirm_assignment_accepts_telegram_user_id_and_updates_slot()` — строка ~65

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/routers/slot_assignments_api.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/slot_assignment_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_cleanup_strict.py`

**Тип:** Тест
**Строк кода:** ~129
**Назначение:** Тестовый модуль `test_slot_cleanup_strict`.

**Ключевые функции:**
- `session()` — строка ~14
- `recruiter()` — строка ~23
- `test_slot_cleanup_logic()` — строка ~31

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/settings.py`
- `backend/core/time_utils.py`
- `backend/domain/candidates/models.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_creation_timezone_validation.py`

**Тип:** Тест
**Строк кода:** ~145
**Назначение:** Тестовый модуль `test_slot_creation_timezone_validation`.

**Ключевые функции:**
- `test_slot_creation_future_time_msk_for_novosibirsk()` — строка ~18
- `test_create_slot_rejects_past_time()` — строка ~81
- `test_slot_creation_future_time_succeeds()` — строка ~116

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Test that slot creation validation correctly handles timezone conversions.

**Состояние / проблемы:**
- console/print: 7

### `tests/test_slot_duration_validation.py`

**Тип:** Тест
**Строк кода:** ~234
**Назначение:** Тестовый модуль `test_slot_duration_validation`.

**Ключевые функции:**
- `test_slot_valid_duration()` — строка ~18
- `test_slot_duration_too_short()` — строка ~65
- `test_slot_duration_too_long()` — строка ~92
- `test_slot_duration_zero_or_negative()` — строка ~119
- `test_slot_duration_none()` — строка ~146
- `test_slot_duration_boundary_values()` — строка ~170

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Tests for slot duration validation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_overlap_constraint.py`

**Тип:** Тест
**Строк кода:** ~446
**Назначение:** Тестовый модуль `test_slot_overlap_constraint`.

**Ключевые функции:**
- `test_slot_overlap_constraint_prevents_exact_overlap()` — строка ~13
- `test_slot_overlap_constraint_prevents_partial_overlap()` — строка ~58
- `test_slot_overlap_constraint_prevents_contained_slot()` — строка ~103
- `test_slot_overlap_constraint_allows_adjacent_slots()` — строка ~148
- `test_slot_overlap_allows_touching_10_minute_slots()` — строка ~202
- `test_slot_overlap_detects_overlap_for_10_minute_slots()` — строка ~251
- `test_slot_overlap_constraint_allows_different_recruiters()` — строка ~292
- `test_slot_overlap_constraint_allows_separated_slots()` — строка ~349
- `test_slot_overlap_constraint_allows_parallel_intro_day_same_time()` — строка ~401

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Test exclusion constraint preventing overlapping slots for the same recruiter.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_overlap_handling.py`

**Тип:** Тест
**Строк кода:** ~216
**Назначение:** Тестовый модуль `test_slot_overlap_handling`.

**Ключевые функции:**
- `test_slot_overlap_raises_domain_error()` — строка ~21
- `test_slot_overlap_with_exact_same_time()` — строка ~85
- `test_non_overlapping_slots_succeed()` — строка ~131
- `test_different_recruiters_same_time()` — строка ~177

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/domain/errors.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Test proper handling of slot overlap conflicts.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_overlap_window.py`

**Тип:** Тест
**Строк кода:** ~148
**Назначение:** Тестовый модуль `test_slot_overlap_window`.

**Ключевые функции:**
- `_dt()` — строка ~10
- `test_slots_30_minutes_apart_do_not_conflict()` — строка ~17
- `test_slots_5_minutes_apart_conflict()` — строка ~50
- `test_slots_exactly_10_minutes_apart_do_not_conflict()` — строка ~84
- `test_slots_9_minutes_apart_conflict()` — строка ~117

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_past_validation.py`

**Тип:** Тест
**Строк кода:** ~67
**Назначение:** Тестовый модуль `test_slot_past_validation`.

**Ключевые функции:**
- `test_create_slot_rejects_past_time()` — строка ~15
- `test_reserve_slot_rejects_past_start()` — строка ~38

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/domain/models.py`
- `backend/domain/repositories.py`

**Комментарии / явные подсказки в файле:**
- Ensure slots cannot be created or booked in the past.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_repository.py`

**Тип:** Тест
**Строк кода:** ~172
**Назначение:** Тестовый модуль `test_slot_repository`.

**Ключевые функции:**
- `test_get_upcoming_for_candidate_uses_correct_field()` — строка ~14
- `test_get_upcoming_for_candidate_empty_result()` — строка ~111
- `test_get_free_for_recruiter()` — строка ~124

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/core/result.py`
- `backend/core/uow.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Tests for SlotRepository (Phase 1 & 2 optimized repository).

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_reservations.py`

**Тип:** Тест
**Строк кода:** ~321
**Назначение:** Тестовый модуль `test_slot_reservations`.

**Ключевые функции:**
- `test_reserve_slot_prevents_duplicate_pending()` — строка ~15
- `test_reserve_slot_idempotent_within_window()` — строка ~64
- `test_reserve_slot_concurrent_requests()` — строка ~111
- `test_unique_index_enforced()` — строка ~154
- `test_reject_slot_removes_reservation_lock()` — строка ~180
- `test_reserve_slot_syncs_candidate_directory()` — строка ~234
- `test_slot_updated_at_reflects_status_changes()` — строка ~273

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/repositories.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_status_transitions.py`

**Тип:** Тест
**Строк кода:** ~51
**Назначение:** Тестовый модуль `test_slot_status_transitions`.

**Ключевые функции:**
- `test_enforce_slot_transition_allows_valid_paths()` — строка ~29
- `test_enforce_slot_transition_blocks_invalid_paths()` — строка ~48

**Зависимости (локальные импорты):**
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_timezone_moscow_novosibirsk.py`

**Тип:** Тест
**Строк кода:** ~193
**Назначение:** Тестовый модуль `test_slot_timezone_moscow_novosibirsk`.

**Ключевые функции:**
- `test_moscow_recruiter_slot_for_novosibirsk()` — строка ~21
- `test_moscow_recruiter_slot_at_9am()` — строка ~128

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Test for timezone bug: Moscow recruiter creating slot for Novosibirsk.

**Состояние / проблемы:**
- console/print: 11

### `tests/test_slot_timezone_validation.py`

**Тип:** Тест
**Строк кода:** ~211
**Назначение:** Тестовый модуль `test_slot_timezone_validation`.

**Ключевые функции:**
- `test_slot_valid_timezone()` — строка ~12
- `test_slot_invalid_timezone()` — строка ~40
- `test_slot_empty_timezone()` — строка ~65
- `test_candidate_timezone_valid()` — строка ~89
- `test_candidate_timezone_invalid()` — строка ~117
- `test_candidate_timezone_none()` — строка ~142
- `test_recruiter_timezone_validation()` — строка ~170
- `test_recruiter_invalid_timezone()` — строка ~183
- `test_city_timezone_validation()` — строка ~192
- `test_city_invalid_timezone()` — строка ~205

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Tests for slot timezone validation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slot_timezones.py`

**Тип:** Тест
**Строк кода:** ~97
**Назначение:** Тестовый модуль `test_slot_timezones`.

**Ключевые функции:**
- `test_generate_default_day_stores_utc_times()` — строка ~13
- `test_candidate_sees_local_time_labels()` — строка ~46
- `test_slots_list_date_filter_in_msk_range()` — строка ~58

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/bot/services.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slots_api_tz.py`

**Тип:** Тест
**Строк кода:** ~251
**Назначение:** Тестовый модуль `test_slots_api_tz`.

**Ключевые функции:**
- `_async_request()` — строка ~20
- `_create_recruiter_and_city()` — строка ~31
- `test_post_slot_uses_region_timezone_moscow()` — строка ~46
- `test_post_slot_uses_region_timezone_novosibirsk()` — строка ~71
- `test_post_slot_persists_region_timezones_for_free_slot()` — строка ~96
- `test_get_slot_returns_local_time()` — строка ~122
- `test_post_requires_region_and_valid_timezone()` — строка ~144
- `test_post_allows_starts_at_utc_for_compatibility()` — строка ~182
- `test_put_slot_updates_timezones_for_free_slot()` — строка ~202

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/db.py`
- `backend/core/settings.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slots_generation.py`

**Тип:** Тест
**Строк кода:** ~78
**Назначение:** Тестовый модуль `test_slots_generation`.

**Ключевые функции:**
- `test_generate_default_day_creates_slots_visible_in_list()` — строка ~11
- `test_generate_default_day_auto_city_uses_first_recruiter_city()` — строка ~47

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_slots_timezone_handling.py`

**Тип:** Тест
**Строк кода:** ~215
**Назначение:** Тестовый модуль `test_slots_timezone_handling`.

**Ключевые функции:**
- `test_single_slot_uses_city_timezone()` — строка ~15
- `test_bulk_slots_use_city_timezone()` — строка ~76
- `test_slot_fallback_to_recruiter_timezone_if_city_has_none()` — строка ~161

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/slots.py`
- `backend/apps/admin_ui/utils.py`
- `backend/core/db.py`

**Комментарии / явные подсказки в файле:**
- Test timezone handling for slots.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_sqlite_dev_schema.py`

**Тип:** Тест
**Строк кода:** ~46
**Назначение:** Тестовый модуль `test_sqlite_dev_schema`.

**Ключевые функции:**
- `test_repair_sqlite_schema_adds_missing_columns()` — строка ~18

**Зависимости (локальные импорты):**
- `backend/core/sqlite_dev_schema.py`
- `backend/domain/ai/__init__.py`
- `backend/domain/base.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/hh_integration/__init__.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_staff_chat_file_upload.py`

**Тип:** Тест
**Строк кода:** ~74
**Назначение:** Тестовый модуль `test_staff_chat_file_upload`.

**Классы:**
- `_DummyIntegration` — строка ~11

**Ключевые функции:**
- `_fake_setup_bot_state()` — строка ~16
- `_configure_env()` — строка ~27
- `test_staff_chat_allows_file_only_message()` — строка ~44

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/__init__.py`
- `backend/core/__init__.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_staff_chat_updates.py`

**Тип:** Тест
**Строк кода:** ~74
**Назначение:** Тестовый модуль `test_staff_chat_updates`.

**Классы:**
- `_DummyIntegration` — строка ~10

**Ключевые функции:**
- `_fake_setup_bot_state()` — строка ~15
- `_configure_env()` — строка ~26
- `test_staff_threads_updates_handles_naive_latest_event_at()` — строка ~43

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/__init__.py`
- `backend/apps/admin_ui/services/__init__.py`
- `backend/core/__init__.py`
- `backend/core/db.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_state_store.py`

**Тип:** Тест
**Строк кода:** ~88
**Назначение:** Тестовый модуль `test_state_store`.

**Ключевые функции:**
- `test_state_store_roundtrip()` — строка ~20
- `test_state_store_ttl_eviction()` — строка ~39
- `test_atomic_update_parallel()` — строка ~53
- `_increment_counter()` — строка ~73
- `_make_store()` — строка ~79

**Зависимости (локальные импорты):**
- `backend/apps/bot/state_store.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_status_service_transitions.py`

**Тип:** Тест
**Строк кода:** ~139
**Назначение:** Тестовый модуль `test_status_service_transitions`.

**Ключевые функции:**
- `_create_user()` — строка ~22
- `_create_user_with_external_tg_id()` — строка ~37
- `test_invalid_jump_requires_force()` — строка ~57
- `test_force_allows_jump_to_hired()` — строка ~64
- `test_forward_pipeline_allows_test2_completion()` — строка ~74
- `test_idempotent_update_returns_true_and_keeps_status()` — строка ~87
- `test_retreating_status_is_ignored_but_not_error()` — строка ~96
- `test_update_status_falls_back_to_telegram_user_id()` — строка ~106
- `test_matrix_matches_status_transition_rules()` — строка ~118

**Зависимости (локальные импорты):**
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/candidates/status_service.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_telegram_identity.py`

**Тип:** Тест
**Строк кода:** ~49
**Назначение:** Тестовый модуль `test_telegram_identity`.

**Ключевые функции:**
- `test_middleware_creates_candidate_with_telegram_identity()` — строка ~12
- `test_identity_update_preserves_link_timestamp()` — строка ~32

**Зависимости (локальные импорты):**
- `backend/apps/bot/middleware.py`
- `backend/core/db.py`
- `backend/domain/candidates/__init__.py`
- `backend/domain/candidates/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_template_lookup_and_invalidation.py`

**Тип:** Тест
**Строк кода:** ~115
**Назначение:** Тестовый модуль `test_template_lookup_and_invalidation`.

**Ключевые функции:**
- `test_template_lookup_and_invalidation()` — строка ~12
- `test_template_provider_fallback_for_missing_template()` — строка ~91

**Зависимости (локальные импорты):**
- `backend/apps/bot/template_provider.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_template_provider.py`

**Тип:** Тест
**Строк кода:** ~50
**Назначение:** Тестовый модуль `test_template_provider`.

**Ключевые функции:**
- `test_get_template_no_fallback()` — строка ~7
- `test_render_template_jinja()` — строка ~18
- `test_render_missing_template_uses_human_fallback()` — строка ~38

**Зависимости (локальные импорты):**
- `backend/apps/bot/template_provider.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_test_builder_graph_api.py`

**Тип:** Тест
**Строк кода:** ~170
**Назначение:** Тестовый модуль `test_test_builder_graph_api`.

**Классы:**
- `_DummyIntegration` — строка ~13

**Ключевые функции:**
- `_run()` — строка ~18
- `admin_app()` — строка ~28
- `_csrf()` — строка ~54
- `_seed_test1_questions()` — строка ~62
- `_linear_graph()` — строка ~89
- `test_test_builder_graph_get_returns_default_linear_graph()` — строка ~107
- `test_test_builder_graph_apply_reorders_questions()` — строка ~122
- `test_test_builder_graph_apply_accepts_branching_and_keeps_question_order()` — строка ~145

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/tests/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_test_builder_graph_preview_api.py`

**Тип:** Тест
**Строк кода:** ~335
**Назначение:** Тестовый модуль `test_test_builder_graph_preview_api`.

**Классы:**
- `_DummyIntegration` — строка ~13

**Ключевые функции:**
- `_run()` — строка ~18
- `admin_app()` — строка ~28
- `_csrf()` — строка ~54
- `_seed_test1_questions()` — строка ~62
- `_edge()` — строка ~133
- `_status_branch_graph()` — строка ~161
- `_reject_graph()` — строка ~229
- `_preview()` — строка ~244
- `test_graph_preview_starts_from_status_question()` — строка ~257
- `test_graph_preview_branches_study_flow()` — строка ~270
- `test_graph_preview_study_schedule_is_not_blocking()` — строка ~283
- `test_graph_preview_working_branch_goes_to_notice_period()` — строка ~296
- `test_graph_preview_supports_reject_edge()` — строка ~308
- `test_graph_preview_marks_invalid_option()` — строка ~323

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/tests/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_timezone_service.py`

**Тип:** Тест
**Строк кода:** ~370
**Назначение:** Тестовый модуль `test_timezone_service`.

**Классы:**
- `TestTimezoneValidation` — строка ~14
- `TestLocalizeNaiveDatetime` — строка ~41
- `TestDSTTransitionDetection` — строка ~119
- `TestTimezoneConversion` — строка ~160
- `TestCandidateTimezoneFallback` — строка ~198
- `TestMultiTimezoneView` — строка ~250
- `TestTimezoneServiceIntegration` — строка ~338

**Зависимости (локальные импорты):**
- `backend/core/timezone_service.py`

**Комментарии / явные подсказки в файле:**
- Tests for TimezoneService.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_timezone_utils.py`

**Тип:** Тест
**Строк кода:** ~222
**Назначение:** Тестовый модуль `test_timezone_utils`.

**Ключевые функции:**
- `test_parse_timezone()` — строка ~19
- `test_ensure_aware()` — строка ~42
- `test_normalize_to_utc()` — строка ~60
- `test_to_local_time()` — строка ~81
- `test_format_for_ui()` — строка ~101
- `test_get_offset_minutes()` — строка ~118
- `test_is_same_moment()` — строка ~135
- `test_datetime_range_overlap()` — строка ~153
- `test_edge_cases()` — строка ~199

**Зависимости (локальные импорты):**
- `backend/core/timezone_utils.py`

**Комментарии / явные подсказки в файле:**
- Tests for timezone utilities.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_timezones.py`

**Тип:** Тест
**Строк кода:** ~23
**Назначение:** Тестовый модуль `test_timezones`.

**Ключевые функции:**
- `test_local_to_utc_conversion()` — строка ~15

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/utils.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_vacancy_api.py`

**Тип:** Тест
**Строк кода:** ~99
**Назначение:** Тестовый модуль `test_vacancy_api`.

**Классы:**
- `_DummyIntegration` — строка ~14

**Ключевые функции:**
- `admin_app()` — строка ~20
- `test_api_list_vacancies_empty()` — строка ~46
- `test_api_create_and_delete_vacancy()` — строка ~59
- `test_api_create_vacancy_invalid_slug()` — строка ~86

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_ui/security.py`
- `backend/apps/admin_ui/services/vacancies.py`
- `backend/core/__init__.py`

**Комментарии / явные подсказки в файле:**
- API-level tests for vacancy endpoints.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_vacancy_service.py`

**Тип:** Тест
**Строк кода:** ~165
**Назначение:** Тестовый модуль `test_vacancy_service`.

**Ключевые функции:**
- `test_create_and_list_global_vacancy()` — строка ~19
- `test_create_vacancy_validates_slug()` — строка ~42
- `test_create_vacancy_validates_duplicate_slug()` — строка ~52
- `test_update_vacancy()` — строка ~65
- `test_resolve_questions_global_fallback()` — строка ~81
- `test_resolve_questions_city_vacancy_takes_precedence()` — строка ~118

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/services/vacancies.py`
- `backend/core/db.py`
- `backend/domain/models.py`

**Комментарии / явные подсказки в файле:**
- Tests for vacancy CRUD and question resolution chain.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_webapp_auth.py`

**Тип:** Тест
**Строк кода:** ~291
**Назначение:** Тестовый модуль `test_webapp_auth`.

**Классы:**
- `TestParseUserFromInitData` — строка ~70
- `TestValidateInitData` — строка ~125
- `TestTelegramUser` — строка ~259

**Ключевые функции:**
- `_generate_valid_init_data()` — строка ~20

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/webapp/auth.py`

**Комментарии / явные подсказки в файле:**
- Tests for Telegram WebApp initData validation.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_webapp_booking_api.py`

**Тип:** Тест
**Строк кода:** ~206
**Назначение:** Тестовый модуль `test_webapp_booking_api`.

**Ключевые функции:**
- `_generate_valid_init_data()` — строка ~23
- `webapp_client()` — строка ~53
- `_seed_webapp_scenario()` — строка ~71
- `_load_slot()` — строка ~135
- `_load_candidate()` — строка ~140
- `_webapp_headers()` — строка ~145
- `test_webapp_me_accepts_valid_init_data()` — строка ~151
- `test_webapp_booking_uses_domain_reservation_and_updates_status()` — строка ~166
- `test_webapp_booking_duplicate_candidate_returns_business_conflict()` — строка ~191

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/main.py`
- `backend/core/__init__.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`
- `backend/domain/models.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_webapp_recruiter.py`

**Тип:** Тест
**Строк кода:** ~419
**Назначение:** Тестовый модуль `test_webapp_recruiter`.

**Классы:**
- `DummyBotService` — строка ~36

**Ключевые функции:**
- `app()` — строка ~31
- `recruiter_and_candidate()` — строка ~46
- `recruiter_access_matrix()` — строка ~78
- `_make_auth_override()` — строка ~130
- `test_recruiter_webapp_routes_exist()` — строка ~157
- `test_dashboard_returns_kpis()` — строка ~171
- `test_incoming_returns_candidates()` — строка ~192
- `test_candidate_detail()` — строка ~212
- `test_candidate_detail_not_found()` — строка ~230
- `test_candidate_detail_allows_unowned_candidate_from_recruiter_city()` — строка ~241
- `test_recruiter_cannot_access_other_recruiters_candidate()` — строка ~263
- `test_status_update_valid()` — строка ~291
- `test_status_update_invalid_status()` — строка ~308
- `test_send_message_persists_candidate_chat()` — строка ~327
- `test_save_note()` — строка ~363
- `test_save_note_not_found()` — строка ~394
- `test_dashboard_no_auth_returns_error()` — строка ~413

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_api/webapp/auth.py`
- `backend/apps/admin_api/webapp/recruiter_routers.py`
- `backend/apps/admin_ui/services/bot_service.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Комментарии / явные подсказки в файле:**
- Tests for Recruiter Mini App API endpoints.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_webapp_smoke.py`

**Тип:** Тест
**Строк кода:** ~50
**Назначение:** Тестовый модуль `test_webapp_smoke`.

**Классы:**
- `TestWebAppSmoke` — строка ~9

**Зависимости (локальные импорты):**
- `backend/apps/admin_api/main.py`

**Комментарии / явные подсказки в файле:**
- Smoke tests for WebApp API integration.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_workflow_api.py`

**Тип:** Тест
**Строк кода:** ~113
**Назначение:** Тестовый модуль `test_workflow_api`.

**Ключевые функции:**
- `test_workflow_state_and_actions_happy_path()` — строка ~13
- `test_workflow_reject_sets_stage_and_meta()` — строка ~54
- `test_workflow_invalid_transition_returns_conflict()` — строка ~88

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/workflow.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_workflow_contract.py`

**Тип:** Тест
**Строк кода:** ~53
**Назначение:** Тестовый модуль `test_workflow_contract`.

**Ключевые функции:**
- `_candidate()` — строка ~14
- `test_allowed_transitions_success()` — строка ~23
- `test_reject_from_any_state_sets_stage_and_meta()` — строка ~32
- `test_invalid_transition_raises_conflict()` — строка ~44

**Зависимости (локальные импорты):**
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/workflow.py`

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием

### `tests/test_workflow_hired.py`

**Тип:** Тест
**Строк кода:** ~249
**Назначение:** Тестовый модуль `test_workflow_hired`.

**Ключевые функции:**
- `test_mark_hired_from_intro_day_confirmed()` — строка ~21
- `test_mark_not_hired_from_intro_day_confirmed()` — строка ~55
- `test_mark_hired_from_preliminary_confirmed()` — строка ~89
- `test_mark_hired_invalid_status_returns_error()` — строка ~118
- `test_hired_is_terminal_state()` — строка ~145
- `test_not_hired_is_terminal_state()` — строка ~176
- `test_candidate_not_found_returns_404()` — строка ~203
- `test_full_funnel_to_hired()` — строка ~216

**Зависимости (локальные импорты):**
- `backend/apps/admin_ui/app.py`
- `backend/core/db.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/status.py`

**Комментарии / явные подсказки в файле:**
- Tests for hired/not_hired workflow actions.

**Состояние / проблемы:**
- Явных маркеров техдолга не найдено статическим сканированием
