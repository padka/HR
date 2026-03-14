# PROJECT AUDIT 03 — Dependencies, Types, API, Env
## Дата: 2026-03-14

## 4. Карта зависимостей

### Страницы → компоненты / hooks / API

- `frontend/app/src/app/routes/__root.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/__root.ui-mode.test.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/app/calendar.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/hooks/useCalendarWebSocket.ts`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/candidate-detail.tsx` использует:
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`
  - `frontend/app/src/app/components/CandidateTimeline/CandidateTimeline.tsx`
  - `frontend/app/src/app/components/CohortComparison/CohortComparison.tsx`
  - `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`
  - `frontend/app/src/app/components/QuickNotes/QuickNotes.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/routes/app/candidate-new.test.tsx` использует:
  - `frontend/app/src/app/routes/app/candidate-new.tsx`
- `frontend/app/src/app/routes/app/candidate-new.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/candidates.test.tsx` использует:
  - `frontend/app/src/app/routes/app/candidates.tsx`
- `frontend/app/src/app/routes/app/candidates.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/cities.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/city-edit.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/routes/app/template_meta.ts`
- `frontend/app/src/app/routes/app/city-new.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/copilot.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/dashboard.tsx` использует:
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
  - `frontend/app/src/app/hooks/useProfile.ts`
  - `frontend/app/src/app/routes/app/incoming-demo.ts`
  - `frontend/app/src/app/routes/app/incoming.tsx`
- `frontend/app/src/app/routes/app/detailization.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/incoming.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/api/services/candidates.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
  - `frontend/app/src/app/hooks/useProfile.ts`
  - `frontend/app/src/app/routes/app/incoming-demo.ts`
- `frontend/app/src/app/routes/app/index.tsx` использует:
  - Явных локальных зависимостей не обнаружено
- `frontend/app/src/app/routes/app/login.tsx` использует:
  - Явных локальных зависимостей не обнаружено
- `frontend/app/src/app/routes/app/message-templates.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/messenger.tsx` использует:
  - `frontend/app/src/app/hooks/useIsMobile.ts`
  - `frontend/app/src/app/routes/app/messenger/useMessageDraft.ts`
- `frontend/app/src/app/routes/app/profile.tsx` использует:
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/question-edit.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/question-new.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/questions.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/routes/app/recruiter-edit.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/routes/app/recruiter-form.ts`
- `frontend/app/src/app/routes/app/recruiter-new.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/routes/app/recruiter-form.ts`
- `frontend/app/src/app/routes/app/recruiters.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/reminder-ops.tsx` использует:
  - `frontend/app/src/api/client.ts`
- `frontend/app/src/app/routes/app/simulator.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/slots-create.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/slots.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/ApiErrorBanner.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
  - `frontend/app/src/app/hooks/useProfile.ts`
- `frontend/app/src/app/routes/app/system.tsx` использует:
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/template-edit.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/routes/app/template_meta.ts`
- `frontend/app/src/app/routes/app/template-list.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/hooks/useIsMobile.ts`
- `frontend/app/src/app/routes/app/template-new.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/RoleGuard.tsx`
  - `frontend/app/src/app/routes/app/template_meta.ts`
- `frontend/app/src/app/routes/app/test-builder-graph.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/test-builder.tsx` использует:
  - `frontend/app/src/api/client.ts`
  - `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
  - `frontend/app/src/app/components/RoleGuard.tsx`
- `frontend/app/src/app/routes/app/ui-cosmetics.test.tsx` использует:
  - `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`
  - `frontend/app/src/app/routes/app/candidate-detail.tsx`
  - `frontend/app/src/app/routes/app/dashboard.tsx`
  - `frontend/app/src/app/routes/app/incoming.tsx`
  - `frontend/app/src/app/routes/app/slots.tsx`
- `frontend/app/src/app/routes/app/vacancies.tsx` использует:
  - `frontend/app/src/api/client.ts`
- `frontend/app/src/app/routes/tg-app/candidate.tsx` использует:
  - Явных локальных зависимостей не обнаружено
- `frontend/app/src/app/routes/tg-app/incoming.tsx` использует:
  - Явных локальных зависимостей не обнаружено
- `frontend/app/src/app/routes/tg-app/index.tsx` использует:
  - Явных локальных зависимостей не обнаружено
- `frontend/app/src/app/routes/tg-app/layout.tsx` использует:
  - Явных локальных зависимостей не обнаружено

### Shared компоненты (используются в 3+ местах)

- `frontend/app/src/app/components/RoleGuard.tsx` → 25 импортов
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
- `frontend/app/src/app/components/ApiErrorBanner.tsx` → 11 импортов
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
- `frontend/app/src/app/components/QuestionPayloadEditor.tsx` → 4 импортов
  - `frontend/app/src/app/routes/app/question-edit.tsx`
  - `frontend/app/src/app/routes/app/question-new.tsx`
  - `frontend/app/src/app/routes/app/test-builder-graph.tsx`
  - `frontend/app/src/app/routes/app/test-builder.tsx`

## 5. Каталог типов

### `frontend/app/src/api/schema.ts`
- `export interface paths` — строка ~6
- `export type webhooks` — строка ~1535
- `export interface components` — строка ~1536
- `export interface operations` — строка ~1904

### `frontend/app/src/api/services/candidates.ts`
- `export type CityOption` — строка ~3
- `export type CandidateAction` — строка ~9
- `export type CandidateSlot` — строка ~22
- `export type TestQuestionAnswer` — строка ~32
- `export type TestStats` — строка ~43
- `export type TestAttempt` — строка ~52
- `export type TestSection` — строка ~64
- `export type CandidateDetail` — строка ~80
- `export type CandidateFinalOutcome` — строка ~147
- `export type CandidateArchive` — строка ~149
- `export type CandidatePendingSlotRequest` — строка ~158
- `export type CandidateJourneyEvent` — строка ~168
- `export type CandidateJourney` — строка ~180
- `export type CandidateTimelineEntry` — строка ~196
- `export type ChatMessage` — строка ~216
- `export type ChatPayload` — строка ~226
- `export type CandidateHHSummary` — строка ~233
- `export type AIRiskItem` — строка ~282
- `export type AINextActionItem` — строка ~289
- `export type AIFit` — строка ~296
- `export type AIEvidenceItem` — строка ~303
- `export type AICriterionChecklistItem` — строка ~309
- `export type AIScorecardMetricItem` — строка ~316
- `export type AIScorecardFlagItem` — строка ~325
- `export type AIScorecard` — строка ~331
- `export type AIVacancyFitEvidence` — строка ~341
- `export type AIVacancyFit` — строка ~347
- `export type AISummary` — строка ~355
- `export type AISummaryResponse` — строка ~369
- `export type AIDraftItem` — строка ~376
- `export type AIDraftsResponse` — строка ~381
- `export type AICoach` — строка ~390
- `export type AICoachResponse` — строка ~402
- `export type CandidateAiResumeUpsertResponse` — строка ~409
- `export type InterviewRiskFlag` — строка ~416
- `export type InterviewScriptIfAnswer` — строка ~424
- `export type InterviewScriptBlock` — строка ~429
- `export type InterviewObjection` — строка ~438
- `export type InterviewCtaTemplate` — строка ~444
- `export type InterviewScriptPayload` — строка ~449
- `export type InterviewScriptResponse` — строка ~482
- `export type InterviewScriptFeedbackPayload` — строка ~492
- `export type CandidateCohortComparison` — строка ~516
- `export type CandidateSearchResult` — строка ~678

### `frontend/app/src/api/services/dashboard.ts`
- `export type SummaryPayload` — строка ~3
- `export type KPITrend` — строка ~16
- `export type KPICard` — строка ~21
- `export type KPIResponse` — строка ~31
- `export type RecruiterOption` — строка ~41
- `export type LeaderboardItem` — строка ~46
- `export type LeaderboardPayload` — строка ~60
- `export type IncomingCandidate` — строка ~65
- `export type IncomingPayload` — строка ~95

### `frontend/app/src/api/services/messenger.ts`
- `export type CandidateChatFolder` — строка ~3
- `export type CandidateChatThread` — строка ~5
- `export type CandidateChatThreadsPayload` — строка ~42
- `export type CandidateChatMessage` — строка ~48
- `export type CandidateChatWorkspaceState` — строка ~59
- `export type CandidateChatPayload` — строка ~67
- `export type CandidateChatTemplate` — строка ~74

### `frontend/app/src/api/services/profile.ts`
- `export type ProfileResponse` — строка ~3
- `export type TimezoneOption` — строка ~61
- `export type KpiTrend` — строка ~68
- `export type KpiDetailRow` — строка ~75
- `export type KpiMetric` — строка ~82
- `export type ProfileKpiResponse` — строка ~93
- `export type ProfileSettingsPayload` — строка ~101
- `export type ProfileSettingsResponse` — строка ~107
- `export type ChangePasswordPayload` — строка ~118
- `export type AvatarUploadResponse` — строка ~123
- `export type AvatarDeleteResponse` — строка ~124

### `frontend/app/src/api/services/slots.ts`
- `export type CandidateSearchItem` — строка ~3
- `export type CandidateSearchPayload` — строка ~12
- `export type SlotsBulkActionPayload` — строка ~16
- `export type ManualSlotBookingPayload` — строка ~22
- `export type ManualSlotBookingResponse` — строка ~34

### `frontend/app/src/api/services/system.ts`
- `export type HealthPayload` — строка ~3
- `export type BotStatus` — строка ~16
- `export type ReminderKindConfig` — строка ~26
- `export type ReminderPolicy` — строка ~31
- `export type ReminderPolicyPayload` — строка ~43
- `export type ReminderPolicyUpdatePayload` — строка ~53
- `export type ReminderJob` — строка ~61
- `export type ReminderJobsPayload` — строка ~74
- `export type ReminderResyncPayload` — строка ~80
- `export type OutboxItem` — строка ~86
- `export type OutboxFeedPayload` — строка ~101
- `export type NotificationLogItem` — строка ~107
- `export type NotificationLogsPayload` — строка ~121
- `export type QuestionGroup` — строка ~127

### `frontend/app/src/app/components/ApiErrorBanner.tsx`
- `type ApiErrorBannerProps` — строка ~2

### `frontend/app/src/app/components/Calendar/ScheduleCalendar.tsx`
- `export interface SlotExtendedProps` — строка ~14
- `export interface TaskExtendedProps` — строка ~35
- `type CalendarExtendedProps` — строка ~50
- `interface CalendarEvent` — строка ~52
- `interface CalendarResource` — строка ~56
- `interface CalendarApiResponse` — строка ~65
- `interface ScheduleCalendarProps` — строка ~78

### `frontend/app/src/app/components/CandidatePipeline/CandidatePipeline.tsx`
- `type CandidatePipelineProps` — строка ~10

### `frontend/app/src/app/components/CandidatePipeline/PipelineConnector.tsx`
- `type PipelineConnectorProps` — строка ~4

### `frontend/app/src/app/components/CandidatePipeline/PipelineStage.tsx`
- `type PipelineStageProps` — строка ~9

### `frontend/app/src/app/components/CandidatePipeline/StageBadge.tsx`
- `type StageBadgeProps` — строка ~3

### `frontend/app/src/app/components/CandidatePipeline/StageDetailPanel.tsx`
- `type StageDetailPanelProps` — строка ~7

### `frontend/app/src/app/components/CandidatePipeline/StageIndicator.tsx`
- `type StageIndicatorProps` — строка ~6

### `frontend/app/src/app/components/CandidatePipeline/pipeline.types.ts`
- `export type PipelineStageStatus` — строка ~1
- `export type StageDetailEvent` — строка ~3
- `export type StageDetail` — строка ~11
- `export type PipelineStage` — строка ~22

### `frontend/app/src/app/components/CandidateTimeline/CandidateTimeline.tsx`
- `type CandidateTimelineProps` — строка ~7

### `frontend/app/src/app/components/CandidateTimeline/TimelineEvent.tsx`
- `type TimelineEventProps` — строка ~2

### `frontend/app/src/app/components/CandidateTimeline/timeline.types.ts`
- `export type TimelineTone` — строка ~1
- `export type TimelineEvent` — строка ~3

### `frontend/app/src/app/components/CohortComparison/CohortBar.tsx`
- `type CohortBarProps` — строка ~1

### `frontend/app/src/app/components/CohortComparison/CohortComparison.tsx`
- `type CohortComparisonProps` — строка ~6

### `frontend/app/src/app/components/ErrorBoundary.tsx`
- `interface Props` — строка ~2
- `interface State` — строка ~7

### `frontend/app/src/app/components/InterviewScript/InterviewScript.tsx`
- `type InterviewScriptProps` — строка ~24

### `frontend/app/src/app/components/InterviewScript/RatingScale.tsx`
- `type RatingScaleProps` — строка ~2

### `frontend/app/src/app/components/InterviewScript/ScriptBriefing.tsx`
- `type ScriptBriefingProps` — строка ~1

### `frontend/app/src/app/components/InterviewScript/ScriptNotes.tsx`
- `type ScriptNotesProps` — строка ~1

### `frontend/app/src/app/components/InterviewScript/ScriptQuestion.tsx`
- `type ScriptQuestionProps` — строка ~4

### `frontend/app/src/app/components/InterviewScript/ScriptScorecard.tsx`
- `type ScriptScorecardProps` — строка ~6

### `frontend/app/src/app/components/InterviewScript/ScriptStepper.tsx`
- `type ScriptStepperProps` — строка ~2

### `frontend/app/src/app/components/InterviewScript/ScriptTimer.tsx`
- `type ScriptTimerProps` — строка ~1

### `frontend/app/src/app/components/InterviewScript/script.types.ts`
- `export type InterviewScriptQuestionView` — строка ~3
- `export type InterviewScriptViewModel` — строка ~14
- `export type InterviewScriptStep` — строка ~27
- `export type InterviewScriptQuestionState` — строка ~34
- `export type InterviewScriptDraft` — строка ~40
- `export type InterviewScriptBaseContext` — строка ~51

### `frontend/app/src/app/components/QuestionPayloadEditor.tsx`
- `type BuilderState` — строка ~2
- `type PreviewItem` — строка ~13
- `type PayloadEditorProps` — строка ~150

### `frontend/app/src/app/components/QuickNotes/QuickNotes.tsx`
- `type QuickNotesProps` — строка ~2
- `type StoredQuickNote` — строка ~6

### `frontend/app/src/app/components/RoleGuard.tsx`
- `type RoleGuardProps` — строка ~4

### `frontend/app/src/app/hooks/useCalendarWebSocket.ts`
- `interface SlotChangeEvent` — строка ~3
- `type WebSocketMessage` — строка ~12
- `interface UseCalendarWebSocketOptions` — строка ~14

### `frontend/app/src/app/hooks/useIsMobile.ts`
- `type MobileState` — строка ~12

### `frontend/app/src/app/lib/timezonePreview.ts`
- `export type SlotTimePreview` — строка ~1

### `frontend/app/src/app/routes/__root.tsx`
- `type BubblePopFx` — строка ~6
- `type BubblePopSplash` — строка ~11
- `type MotionMode` — строка ~38
- `type ThreadItem` — строка ~383
- `type ThreadsPayload` — строка ~401
- `type NavItem` — строка ~478

### `frontend/app/src/app/routes/app/calendar.tsx`
- `type City` — строка ~13
- `type RecruiterOption` — строка ~18
- `type TaskModalState` — строка ~23
- `type TaskDraft` — строка ~27
- `type TaskPayload` — строка ~36

### `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `type City` — строка ~43
- `type CandidateAction` — строка ~49
- `type CandidateSlot` — строка ~62
- `type TestQuestionAnswer` — строка ~72
- `type TestStats` — строка ~83
- `type TestAttempt` — строка ~92
- `type TestSection` — строка ~104
- `type ReportPreviewState` — строка ~120
- `type IntroDayTemplateContext` — строка ~125
- `type CandidateDetail` — строка ~136
- `type JourneyEventRecord` — строка ~190
- `type FunnelStageKey` — строка ~191
- `type FunnelTone` — строка ~192
- `type FunnelStageItem` — строка ~194
- `type ChatMessage` — строка ~716
- `type ChatPayload` — строка ~726
- `type AIRiskItem` — строка ~733
- `type AINextActionItem` — строка ~740
- `type AIFit` — строка ~747
- `type AIEvidenceItem` — строка ~754
- `type AICriterionChecklistItem` — строка ~760
- `type AIScorecardMetricItem` — строка ~767
- `type AIScorecardFlagItem` — строка ~776
- `type AIScorecard` — строка ~782
- `type AIVacancyFitEvidence` — строка ~792
- `type AIVacancyFit` — строка ~798
- `type AISummary` — строка ~806
- `type AISummaryResponse` — строка ~820
- `type AIDraftItem` — строка ~827
- `type AICoach` — строка ~832
- `type AICoachResponse` — строка ~844
- `type ReportPreviewModalProps` — строка ~892
- `type TestAttemptModalProps` — строка ~1003
- `type ScheduleSlotModalProps` — строка ~1083
- `type ScheduleIntroDayModalProps` — строка ~1352
- `type RejectModalProps` — строка ~1532

### `frontend/app/src/app/routes/app/candidate-new.tsx`
- `type City` — строка ~6
- `type Recruiter` — строка ~12
- `type CandidateCreateResponse` — строка ~19
- `type ScheduleSlotResponse` — строка ~26
- `type SubmitResult` — строка ~31

### `frontend/app/src/app/routes/app/candidates.tsx`
- `type CityOption` — строка ~9
- `type AICityCandidateRecommendation` — строка ~16
- `type AICityRecommendationsResponse` — строка ~24
- `type Candidate` — строка ~33
- `type CandidateCard` — строка ~44
- `type KanbanWorkflowColumn` — строка ~55
- `type CalendarDay` — строка ~63
- `type CandidateListPayload` — строка ~74
- `type CandidateKanbanMoveResponse` — строка ~89
- `type KanbanMoveVariables` — строка ~96

### `frontend/app/src/app/routes/app/cities.tsx`
- `type City` — строка ~7
- `type StageItem` — строка ~23
- `type TemplatesOverview` — строка ~31
- `type TemplatesPayload` — строка ~35

### `frontend/app/src/app/routes/app/city-edit.tsx`
- `type Recruiter` — строка ~8
- `type TimezoneOption` — строка ~9
- `type CityExpertItem` — строка ~10
- `type CityDetail` — строка ~11
- `type CityHhVacancyItem` — строка ~27
- `type CityHhVacanciesResponse` — строка ~45
- `type TemplateItem` — строка ~53
- `type ReminderPolicy` — строка ~98

### `frontend/app/src/app/routes/app/city-new.tsx`
- `type Recruiter` — строка ~6
- `type TimezoneOption` — строка ~7
- `type CityExpertItem` — строка ~8

### `frontend/app/src/app/routes/app/copilot.tsx`
- `type ChatMessage` — строка ~7
- `type ChatState` — строка ~15
- `type KBDocItem` — строка ~21
- `type KBDocsList` — строка ~31
- `type KBDocument` — строка ~36
- `type KBDocGet` — строка ~47
- `type KBReindexResponse` — строка ~52

### `frontend/app/src/app/routes/app/dashboard.tsx`
- `type IncomingFilter` — строка ~33

### `frontend/app/src/app/routes/app/detailization.tsx`
- `type FinalOutcome` — строка ~7
- `type DetailizationItem` — строка ~9
- `type DetailizationAggregateRow` — строка ~23
- `type DetailizationResponse` — строка ~30
- `type City` — строка ~45
- `type Recruiter` — строка ~53
- `type CandidateSearchItem` — строка ~59
- `type CandidateSearchResponse` — строка ~65
- `type DirtyPatch` — строка ~69

### `frontend/app/src/app/routes/app/incoming-demo.ts`
- `export type IncomingCandidateLike` — строка ~1
- `export type IncomingCityOption` — строка ~25

### `frontend/app/src/app/routes/app/incoming.filters.ts`
- `export type IncomingStatusFilter` — строка ~1
- `export type IncomingOwnerFilter` — строка ~8
- `export type IncomingWaitingFilter` — строка ~9
- `export type IncomingAiFilter` — строка ~10
- `export type IncomingPersistedFilters` — строка ~12

### `frontend/app/src/app/routes/app/incoming.tsx`
- `type IncomingCandidate` — строка ~21
- `type IncomingPayload` — строка ~51
- `type AvailableSlot` — строка ~55
- `type AvailableSlotsPayload` — строка ~66
- `type ScheduleIncomingPayload` — строка ~72
- `type IncomingTestPreviewModalProps` — строка ~220

### `frontend/app/src/app/routes/app/message-templates.tsx`
- `type MessageTemplate` — строка ~8
- `type TemplateCatalogItem` — строка ~28
- `type TemplateHistoryItem` — строка ~37
- `type MessageTemplatesPayload` — строка ~45
- `type PreviewResponse` — строка ~60
- `type EditorState` — строка ~66

### `frontend/app/src/app/routes/app/messenger.tsx`
- `type ThreadTone` — строка ~40
- `type NextAction` — строка ~42
- `type IntroDayTemplateContext` — строка ~51
- `type JourneyStep` — строка ~53

### `frontend/app/src/app/routes/app/question-edit.tsx`
- `type QuestionDetail` — строка ~7

### `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- `type City` — строка ~8
- `type TimezoneOption` — строка ~9
- `type RecruiterDetail` — строка ~10
- `type RecruiterSummary` — строка ~19
- `type ResetPasswordResponse` — строка ~34

### `frontend/app/src/app/routes/app/recruiter-form.ts`
- `export type RecruiterFormState` — строка ~1
- `export type RecruiterFormErrors` — строка ~10

### `frontend/app/src/app/routes/app/recruiter-new.tsx`
- `type City` — строка ~7
- `type TimezoneOption` — строка ~8
- `type RecruiterCreateResponse` — строка ~9

### `frontend/app/src/app/routes/app/recruiters.tsx`
- `type Recruiter` — строка ~7

### `frontend/app/src/app/routes/app/reminder-ops.tsx`
- `type ReminderJob` — строка ~4
- `type ReminderJobsResponse` — строка ~17

### `frontend/app/src/app/routes/app/simulator.tsx`
- `type SimulatorStep` — строка ~6
- `type SimulatorRun` — строка ~18
- `type SimulatorRunResponse` — строка ~35
- `type SimulatorReportResponse` — строка ~40

### `frontend/app/src/app/routes/app/slots-create.tsx`
- `type RecruiterPayload` — строка ~9
- `type CityPayload` — строка ~18
- `type FormValues` — строка ~32

### `frontend/app/src/app/routes/app/slots.filters.ts`
- `export type SlotSortField` — строка ~3
- `export type SlotSortDir` — строка ~4
- `export type SlotsPersistedFilters` — строка ~6

### `frontend/app/src/app/routes/app/slots.tsx`
- `type CityOption` — строка ~45
- `type RecruiterOption` — строка ~52
- `type BookingModalProps` — строка ~73
- `type RescheduleModalProps` — строка ~231
- `type ManualBookingModalProps` — строка ~260

### `frontend/app/src/app/routes/app/slots.utils.ts`
- `export type SlotApiItem` — строка ~1
- `export type SlotUiStatus` — строка ~20
- `export type SlotStatusFilter` — строка ~27
- `export type SlotStatusCounts` — строка ~29

### `frontend/app/src/app/routes/app/system.tsx`
- `type BotCenterTab` — строка ~27

### `frontend/app/src/app/routes/app/template-edit.tsx`
- `type City` — строка ~7
- `type TemplateDetail` — строка ~8

### `frontend/app/src/app/routes/app/template-list.tsx`
- `type MessageTemplate` — строка ~15
- `type MessageTemplatesPayload` — строка ~27
- `type TemplateIndexEntry` — строка ~34

### `frontend/app/src/app/routes/app/template-new.tsx`
- `type City` — строка ~7

### `frontend/app/src/app/routes/app/template_meta.ts`
- `export type TemplateStage` — строка ~9
- `export type TemplateMeta` — строка ~18

### `frontend/app/src/app/routes/app/test-builder-graph.tsx`
- `type QuestionMeta` — строка ~25
- `type QuestionGroup` — строка ~39
- `type GraphPayload` — строка ~45
- `type QuestionDetailPayload` — строка ~52
- `type GraphPreviewQuestion` — строка ~61
- `type GraphPreviewStep` — строка ~72
- `type GraphPreviewPayload` — строка ~87
- `type BranchMatchMode` — строка ~99
- `type BranchAction` — строка ~100
- `type BranchEdgeData` — строка ~102

### `frontend/app/src/app/routes/app/test-builder.tsx`
- `type QuestionRow` — строка ~7
- `type QuestionGroup` — строка ~19
- `type QuestionDetailPayload` — строка ~25

### `frontend/app/src/app/routes/app/vacancies.tsx`
- `type Vacancy` — строка ~3
- `type VacanciesResponse` — строка ~17

### `frontend/app/src/app/routes/tg-app/candidate.tsx`
- `interface CandidateDetail` — строка ~7

### `frontend/app/src/app/routes/tg-app/incoming.tsx`
- `interface Candidate` — строка ~7

### `frontend/app/src/app/routes/tg-app/index.tsx`
- `interface DashboardData` — строка ~7

### `frontend/app/tests/e2e/smoke.spec.ts`
- `type SmokeRoute` — строка ~2

## 6. Каталог API-эндпоинтов

| Метод | Endpoint | Файл | Функция | Строка | Auth |
|---|---|---|---|---:|---|
| GET | `` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_list` | 160 | Да |
| GET | `` | `backend/apps/admin_ui/routers/cities.py` | `cities_list` | 187 | Неочевидно |
| GET | `` | `backend/apps/admin_ui/routers/detailization.py` | `api_detailization_list` | 64 | Да |
| GET | `` | `backend/apps/admin_ui/routers/message_templates.py` | `message_templates_list` | 12 | Неочевидно |
| GET | `` | `backend/apps/admin_ui/routers/profile.py` | `profile` | 12 | Да |
| GET | `` | `backend/apps/admin_ui/routers/questions.py` | `questions_list` | 8 | Неочевидно |
| GET | `` | `backend/apps/admin_ui/routers/recruiters.py` | `recruiters_list` | 8 | Неочевидно |
| GET | `` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `list_recruiters` | 81 | Да |
| GET | `` | `backend/apps/admin_ui/routers/reschedule_requests.py` | `list_reschedule_requests` | 21 | Да |
| GET | `` | `backend/apps/admin_ui/routers/slots.py` | `slots_list` | 196 | Да |
| POST | `` | `backend/apps/admin_ui/routers/detailization.py` | `api_detailization_create` | 114 | Да |
| POST | `` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `create_recruiter` | 132 | Да |
| POST | `` | `backend/apps/admin_ui/routers/slots.py` | `slots_api_create` | 296 | Да |
| GET | `/` | `backend/apps/admin_ui/routers/dashboard.py` | `index` | 92 | Да |
| GET | `/.well-known/appspecific/com.chrome.devtools.json` | `backend/apps/admin_ui/routers/system.py` | `devtools_probe` | 33 | Неочевидно |
| POST | `/booking` | `backend/apps/admin_api/webapp/routers.py` | `create_booking` | 280 | Да |
| POST | `/bot/cities/refresh` | `backend/apps/admin_ui/routers/api.py` | `api_bot_cities_refresh` | 1943 | Да |
| GET | `/bot/integration` | `backend/apps/admin_ui/routers/api.py` | `api_bot_integration_status` | 1885 | Да |
| POST | `/bot/integration` | `backend/apps/admin_ui/routers/api.py` | `api_bot_integration_update` | 1905 | Да |
| DELETE | `/bot/reminder-jobs/{job_id:path}` | `backend/apps/admin_ui/routers/api.py` | `api_cancel_reminder_job` | 2076 | Да |
| GET | `/bot/reminder-policy` | `backend/apps/admin_ui/routers/api.py` | `api_bot_reminder_policy` | 1963 | Да |
| PUT | `/bot/reminder-policy` | `backend/apps/admin_ui/routers/api.py` | `api_bot_reminder_policy_update` | 1981 | Да |
| GET | `/bot/reminders/jobs` | `backend/apps/admin_ui/routers/api.py` | `api_bot_reminder_jobs` | 2018 | Да |
| POST | `/bot/reminders/resync` | `backend/apps/admin_ui/routers/api.py` | `api_bot_reminder_resync` | 2042 | Да |
| POST | `/bulk` | `backend/apps/admin_ui/routers/slots.py` | `slots_bulk_action` | 534 | Да |
| POST | `/bulk_create` | `backend/apps/admin_ui/routers/slots.py` | `slots_bulk_create` | 253 | Да |
| GET | `/calendar/events` | `backend/apps/admin_ui/routers/api.py` | `api_calendar_events` | 706 | Да |
| POST | `/calendar/tasks` | `backend/apps/admin_ui/routers/api.py` | `api_calendar_task_create` | 774 | Да |
| DELETE | `/calendar/tasks/{task_id}` | `backend/apps/admin_ui/routers/api.py` | `api_calendar_task_delete` | 843 | Да |
| PATCH | `/calendar/tasks/{task_id}` | `backend/apps/admin_ui/routers/api.py` | `api_calendar_task_update` | 807 | Да |
| POST | `/callback` | `backend/apps/admin_api/hh_sync.py` | `hh_sync_callback` | 58 | Да |
| POST | `/cancel` | `backend/apps/admin_api/webapp/routers.py` | `cancel_booking` | 568 | Да |
| GET | `/candidate-chat/templates` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_templates` | 433 | Да |
| GET | `/candidate-chat/threads` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_threads` | 392 | Да |
| GET | `/candidate-chat/threads/updates` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_threads_updates` | 410 | Да |
| POST | `/candidate-chat/threads/{candidate_id}/archive` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_archive` | 450 | Да |
| POST | `/candidate-chat/threads/{candidate_id}/read` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_mark_read` | 441 | Да |
| POST | `/candidate-chat/threads/{candidate_id}/unarchive` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_unarchive` | 459 | Да |
| GET | `/candidate-chat/threads/{candidate_id}/workspace` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_workspace` | 468 | Да |
| PUT | `/candidate-chat/threads/{candidate_id}/workspace` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_chat_workspace_update` | 477 | Да |
| GET | `/candidates` | `backend/apps/admin_ui/routers/api.py` | `api_candidates_list` | 2340 | Да |
| POST | `/candidates` | `backend/apps/admin_ui/routers/api.py` | `api_create_candidate` | 2605 | Да |
| DELETE | `/candidates/{candidate_id}` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_delete` | 2328 | Да |
| GET | `/candidates/{candidate_id}` | `backend/apps/admin_api/webapp/recruiter_routers.py` | `recruiter_candidate_detail` | 170 | Да |
| GET | `/candidates/{candidate_id}` | `backend/apps/admin_ui/routers/api.py` | `api_candidate` | 2295 | Да |
| GET | `/candidates/{candidate_id}/actions` | `backend/apps/admin_ui/routers/hh_integration.py` | `get_hh_candidate_actions` | 486 | Да |
| POST | `/candidates/{candidate_id}/actions/{action_id}` | `backend/apps/admin_ui/routers/hh_integration.py` | `execute_hh_candidate_action` | 510 | Да |
| POST | `/candidates/{candidate_id}/actions/{action_key}` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_action` | 2424 | Да |
| POST | `/candidates/{candidate_id}/assign-recruiter` | `backend/apps/admin_ui/routers/api.py` | `api_assign_candidate_recruiter` | 2579 | Да |
| GET | `/candidates/{candidate_id}/available-slots` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_available_slots` | 2705 | Да |
| GET | `/candidates/{candidate_id}/chat` | `backend/apps/admin_ui/routers/api.py` | `api_chat_history` | 2143 | Да |
| POST | `/candidates/{candidate_id}/chat` | `backend/apps/admin_ui/routers/api.py` | `api_chat_send` | 2175 | Да |
| POST | `/candidates/{candidate_id}/chat/drafts` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_chat_drafts` | 267 | Да |
| POST | `/candidates/{candidate_id}/chat/quick-action` | `backend/apps/admin_ui/routers/api.py` | `api_chat_quick_action` | 2210 | Да |
| GET | `/candidates/{candidate_id}/chat/updates` | `backend/apps/admin_ui/routers/api.py` | `api_chat_history_updates` | 2156 | Да |
| POST | `/candidates/{candidate_id}/chat/{message_id}/retry` | `backend/apps/admin_ui/routers/api.py` | `api_chat_retry` | 2282 | Да |
| GET | `/candidates/{candidate_id}/coach` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_coach` | 97 | Да |
| POST | `/candidates/{candidate_id}/coach/drafts` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_coach_drafts` | 129 | Да |
| POST | `/candidates/{candidate_id}/coach/refresh` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_coach_refresh` | 112 | Да |
| GET | `/candidates/{candidate_id}/cohort-comparison` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_cohort_comparison` | 2318 | Да |
| GET | `/candidates/{candidate_id}/hh` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_hh_summary` | 2307 | Да |
| PUT | `/candidates/{candidate_id}/hh-resume` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_hh_resume_upsert` | 207 | Да |
| GET | `/candidates/{candidate_id}/interview-script` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_interview_script` | 152 | Да |
| POST | `/candidates/{candidate_id}/interview-script/feedback` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_interview_script_feedback` | 248 | Да |
| POST | `/candidates/{candidate_id}/interview-script/refresh` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_interview_script_refresh` | 179 | Да |
| POST | `/candidates/{candidate_id}/kanban-status` | `backend/apps/admin_ui/routers/api.py` | `api_candidate_kanban_status` | 2531 | Да |
| POST | `/candidates/{candidate_id}/message` | `backend/apps/admin_api/webapp/recruiter_routers.py` | `recruiter_send_message` | 248 | Да |
| POST | `/candidates/{candidate_id}/notes` | `backend/apps/admin_api/webapp/recruiter_routers.py` | `recruiter_save_note` | 281 | Да |
| POST | `/candidates/{candidate_id}/schedule-intro-day` | `backend/apps/admin_ui/routers/api.py` | `api_schedule_intro_day` | 3163 | Да |
| POST | `/candidates/{candidate_id}/schedule-slot` | `backend/apps/admin_ui/routers/api.py` | `api_schedule_slot` | 2788 | Да |
| POST | `/candidates/{candidate_id}/status` | `backend/apps/admin_api/webapp/recruiter_routers.py` | `recruiter_update_status` | 210 | Да |
| GET | `/candidates/{candidate_id}/summary` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_summary` | 62 | Да |
| POST | `/candidates/{candidate_id}/summary/refresh` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_candidate_summary_refresh` | 79 | Да |
| GET | `/chat` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_agent_chat_state` | 359 | Да |
| POST | `/chat/message` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_agent_chat_send` | 373 | Да |
| GET | `/cities` | `backend/apps/admin_ui/routers/directory.py` | `api_cities` | 157 | Да |
| POST | `/cities` | `backend/apps/admin_ui/routers/directory.py` | `api_create_city` | 227 | Да |
| DELETE | `/cities/{city_id}` | `backend/apps/admin_ui/routers/directory.py` | `api_delete_city` | 319 | Да |
| GET | `/cities/{city_id}` | `backend/apps/admin_ui/routers/directory.py` | `api_city_detail` | 188 | Да |
| PUT | `/cities/{city_id}` | `backend/apps/admin_ui/routers/directory.py` | `api_update_city` | 279 | Да |
| GET | `/cities/{city_id}/candidates/recommendations` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_city_candidate_recommendations` | 394 | Да |
| POST | `/cities/{city_id}/candidates/recommendations/refresh` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_city_candidate_recommendations_refresh` | 418 | Да |
| GET | `/cities/{city_id}/hh-vacancies` | `backend/apps/admin_ui/routers/directory.py` | `api_city_hh_vacancies` | 216 | Да |
| DELETE | `/cities/{city_id}/reminder-policy` | `backend/apps/admin_ui/routers/directory.py` | `api_delete_city_reminder_policy` | 398 | Да |
| GET | `/cities/{city_id}/reminder-policy` | `backend/apps/admin_ui/routers/directory.py` | `api_get_city_reminder_policy` | 332 | Да |
| PUT | `/cities/{city_id}/reminder-policy` | `backend/apps/admin_ui/routers/directory.py` | `api_upsert_city_reminder_policy` | 354 | Да |
| GET | `/city_owners` | `backend/apps/admin_ui/routers/api.py` | `api_city_owners` | 1786 | Да |
| GET | `/connection` | `backend/apps/admin_ui/routers/hh_integration.py` | `get_hh_connection` | 123 | Да |
| POST | `/create` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_create` | 214 | Да |
| POST | `/create` | `backend/apps/admin_ui/routers/cities.py` | `cities_create` | 207 | Неочевидно |
| POST | `/create` | `backend/apps/admin_ui/routers/message_templates.py` | `message_templates_create` | 40 | Неочевидно |
| POST | `/create` | `backend/apps/admin_ui/routers/recruiters.py` | `recruiters_create` | 18 | Неочевидно |
| POST | `/create` | `backend/apps/admin_ui/routers/slots.py` | `slots_create` | 219 | Да |
| GET | `/csrf` | `backend/apps/admin_ui/routers/api.py` | `api_csrf` | 210 | Да |
| GET | `/dashboard` | `backend/apps/admin_api/webapp/recruiter_routers.py` | `recruiter_dashboard` | 112 | Да |
| GET | `/dashboard` | `backend/apps/admin_ui/routers/dashboard.py` | `dashboard_alias` | 97 | Да |
| GET | `/dashboard/calendar` | `backend/apps/admin_ui/routers/api.py` | `api_dashboard_calendar` | 686 | Да |
| GET | `/dashboard/funnel` | `backend/apps/admin_ui/routers/api.py` | `api_dashboard_funnel` | 859 | Да |
| GET | `/dashboard/funnel` | `backend/apps/admin_ui/routers/dashboard.py` | `dashboard_funnel` | 103 | Да |
| GET | `/dashboard/funnel/step` | `backend/apps/admin_ui/routers/dashboard.py` | `dashboard_funnel_step` | 137 | Да |
| GET | `/dashboard/incoming` | `backend/apps/admin_ui/routers/api.py` | `api_dashboard_incoming` | 304 | Да |
| POST | `/dashboard/insights` | `backend/apps/admin_ui/routers/ai.py` | `api_ai_dashboard_insights` | 292 | Да |
| GET | `/dashboard/recruiter-performance` | `backend/apps/admin_ui/routers/api.py` | `api_dashboard_recruiter_performance` | 328 | Да |
| GET | `/dashboard/summary` | `backend/apps/admin_ui/routers/api.py` | `api_dashboard_summary` | 284 | Да |
| POST | `/delete-all` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_delete_all` | 863 | Да |
| POST | `/delete_all` | `backend/apps/admin_ui/routers/slots.py` | `slots_delete_all` | 503 | Да |
| GET | `/detailization` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_detailization` | 191 | Да |
| GET | `/documents` | `backend/apps/admin_ui/routers/knowledge_base.py` | `api_kb_documents_list` | 135 | Да |
| POST | `/documents` | `backend/apps/admin_ui/routers/knowledge_base.py` | `api_kb_document_create` | 215 | Да |
| DELETE | `/documents/{document_id}` | `backend/apps/admin_ui/routers/knowledge_base.py` | `api_kb_document_delete` | 327 | Да |
| GET | `/documents/{document_id}` | `backend/apps/admin_ui/routers/knowledge_base.py` | `api_kb_document_get` | 184 | Да |
| PUT | `/documents/{document_id}` | `backend/apps/admin_ui/routers/knowledge_base.py` | `api_kb_document_update` | 289 | Да |
| POST | `/documents/{document_id}/reindex` | `backend/apps/admin_ui/routers/knowledge_base.py` | `api_kb_document_reindex` | 345 | Да |
| GET | `/export.csv` | `backend/apps/admin_ui/routers/detailization.py` | `api_detailization_export` | 79 | Да |
| GET | `/favicon.ico` | `backend/apps/admin_ui/routers/system.py` | `favicon_redirect` | 26 | Неочевидно |
| GET | `/health` | `backend/apps/admin_ui/routers/api.py` | `api_health` | 278 | Да |
| GET | `/health` | `backend/apps/admin_ui/routers/system.py` | `health_check` | 62 | Неочевидно |
| GET | `/health/bot` | `backend/apps/admin_ui/routers/system.py` | `bot_health` | 126 | Неочевидно |
| GET | `/health/notifications` | `backend/apps/admin_ui/routers/system.py` | `notifications_health` | 223 | Неочевидно |
| GET | `/healthz` | `backend/apps/admin_ui/routers/system.py` | `liveness_probe` | 38 | Неочевидно |
| POST | `/import/negotiations` | `backend/apps/admin_ui/routers/hh_integration.py` | `import_hh_negotiations_route` | 383 | Да |
| POST | `/import/vacancies` | `backend/apps/admin_ui/routers/hh_integration.py` | `import_hh_vacancies_route` | 353 | Да |
| GET | `/incoming` | `backend/apps/admin_api/webapp/recruiter_routers.py` | `recruiter_incoming` | 133 | Да |
| GET | `/intro_day` | `backend/apps/admin_api/webapp/routers.py` | `get_intro_day_info` | 666 | Да |
| GET | `/jobs` | `backend/apps/admin_ui/routers/hh_integration.py` | `get_hh_sync_jobs` | 415 | Да |
| POST | `/jobs/import/negotiations` | `backend/apps/admin_ui/routers/hh_integration.py` | `enqueue_hh_negotiations_import_job` | 448 | Да |
| POST | `/jobs/import/vacancies` | `backend/apps/admin_ui/routers/hh_integration.py` | `enqueue_hh_vacancies_import_job` | 429 | Да |
| POST | `/jobs/{job_id}/retry` | `backend/apps/admin_ui/routers/hh_integration.py` | `retry_hh_job` | 470 | Да |
| GET | `/kpis/current` | `backend/apps/admin_ui/routers/api.py` | `api_weekly_kpis` | 1754 | Да |
| GET | `/kpis/history` | `backend/apps/admin_ui/routers/api.py` | `api_weekly_history` | 1773 | Да |
| GET | `/login` | `backend/apps/admin_ui/routers/auth.py` | `login_form` | 310 | Да |
| POST | `/login` | `backend/apps/admin_ui/routers/auth.py` | `login` | 188 | Да |
| POST | `/logout` | `backend/apps/admin_ui/routers/auth.py` | `logout` | 294 | Да |
| GET | `/me` | `backend/apps/admin_api/webapp/routers.py` | `get_me` | 149 | Да |
| GET | `/message-templates` | `backend/apps/admin_ui/routers/content_api.py` | `api_message_templates` | 149 | Да |
| POST | `/message-templates` | `backend/apps/admin_ui/routers/content_api.py` | `api_create_message_template` | 190 | Да |
| GET | `/message-templates/context-keys` | `backend/apps/admin_ui/routers/content_api.py` | `api_message_template_context_keys` | 725 | Да |
| POST | `/message-templates/preview` | `backend/apps/admin_ui/routers/content_api.py` | `api_message_template_preview` | 735 | Да |
| DELETE | `/message-templates/{template_id}` | `backend/apps/admin_ui/routers/content_api.py` | `api_delete_message_template` | 278 | Да |
| PUT | `/message-templates/{template_id}` | `backend/apps/admin_ui/routers/content_api.py` | `api_update_message_template` | 230 | Да |
| GET | `/message-templates/{template_id}/history` | `backend/apps/admin_ui/routers/content_api.py` | `api_message_template_history` | 296 | Да |
| GET | `/metrics` | `backend/apps/admin_ui/routers/metrics.py` | `metrics` | 46 | Да |
| GET | `/metrics/notifications` | `backend/apps/admin_ui/routers/system.py` | `notifications_metrics` | 340 | Неочевидно |
| GET | `/new` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_new` | 206 | Да |
| GET | `/new` | `backend/apps/admin_ui/routers/cities.py` | `cities_new` | 192 | Неочевидно |
| GET | `/new` | `backend/apps/admin_ui/routers/message_templates.py` | `message_templates_new` | 35 | Неочевидно |
| GET | `/new` | `backend/apps/admin_ui/routers/recruiters.py` | `recruiters_new` | 13 | Неочевидно |
| GET | `/new` | `backend/apps/admin_ui/routers/slots.py` | `slots_new` | 212 | Да |
| GET | `/notifications/feed` | `backend/apps/admin_ui/routers/api.py` | `api_notifications_feed` | 1793 | Да |
| GET | `/notifications/logs` | `backend/apps/admin_ui/routers/api.py` | `api_notifications_logs` | 1815 | Да |
| POST | `/notifications/{notification_id}/cancel` | `backend/apps/admin_ui/routers/api.py` | `api_notifications_cancel` | 1863 | Да |
| POST | `/notifications/{notification_id}/retry` | `backend/apps/admin_ui/routers/api.py` | `api_notifications_retry` | 1841 | Да |
| GET | `/oauth/authorize` | `backend/apps/admin_ui/routers/hh_integration.py` | `get_hh_authorize_url` | 207 | Да |
| GET | `/oauth/callback` | `backend/apps/admin_ui/routers/hh_integration.py` | `hh_oauth_callback` | 219 | Да |
| POST | `/oauth/refresh` | `backend/apps/admin_ui/routers/hh_integration.py` | `refresh_hh_connection_tokens` | 254 | Да |
| GET | `/profile` | `backend/apps/admin_ui/routers/profile_api.py` | `api_profile` | 322 | Да |
| DELETE | `/profile/avatar` | `backend/apps/admin_ui/routers/profile_api.py` | `api_profile_avatar_delete` | 516 | Да |
| GET | `/profile/avatar` | `backend/apps/admin_ui/routers/profile_api.py` | `api_profile_avatar` | 475 | Да |
| POST | `/profile/avatar` | `backend/apps/admin_ui/routers/profile_api.py` | `api_profile_avatar_upload` | 483 | Да |
| POST | `/profile/change-password` | `backend/apps/admin_ui/routers/profile_api.py` | `api_profile_change_password` | 431 | Да |
| PATCH | `/profile/settings` | `backend/apps/admin_ui/routers/profile_api.py` | `api_profile_settings_update` | 366 | Да |
| GET | `/questions` | `backend/apps/admin_ui/routers/content_api.py` | `api_questions` | 321 | Да |
| POST | `/questions` | `backend/apps/admin_ui/routers/content_api.py` | `api_question_create` | 326 | Да |
| POST | `/questions/reorder` | `backend/apps/admin_ui/routers/content_api.py` | `api_questions_reorder` | 406 | Да |
| GET | `/questions/{question_id}` | `backend/apps/admin_ui/routers/content_api.py` | `api_question_detail` | 347 | Да |
| PUT | `/questions/{question_id}` | `backend/apps/admin_ui/routers/content_api.py` | `api_question_update` | 369 | Да |
| POST | `/questions/{question_id}/clone` | `backend/apps/admin_ui/routers/content_api.py` | `api_question_clone` | 392 | Да |
| GET | `/ready` | `backend/apps/admin_ui/routers/system.py` | `readiness_probe` | 44 | Неочевидно |
| GET | `/recruiter-plan` | `backend/apps/admin_ui/routers/api.py` | `api_recruiter_plan` | 1712 | Да |
| DELETE | `/recruiter-plan/entries/{entry_id}` | `backend/apps/admin_ui/routers/api.py` | `api_recruiter_plan_delete` | 1739 | Да |
| POST | `/recruiter-plan/{city_id}/entries` | `backend/apps/admin_ui/routers/api.py` | `api_recruiter_plan_add` | 1720 | Да |
| GET | `/recruiters` | `backend/apps/admin_ui/routers/directory.py` | `api_recruiters` | 36 | Да |
| POST | `/recruiters` | `backend/apps/admin_ui/routers/directory.py` | `api_create_recruiter` | 55 | Да |
| DELETE | `/recruiters/{recruiter_id}` | `backend/apps/admin_ui/routers/directory.py` | `api_delete_recruiter` | 143 | Да |
| GET | `/recruiters/{recruiter_id}` | `backend/apps/admin_ui/routers/directory.py` | `api_recruiter_detail` | 44 | Да |
| PUT | `/recruiters/{recruiter_id}` | `backend/apps/admin_ui/routers/directory.py` | `api_update_recruiter` | 93 | Да |
| POST | `/recruiters/{recruiter_id}/reset-password` | `backend/apps/admin_ui/routers/directory.py` | `api_reset_recruiter_password` | 129 | Да |
| POST | `/reschedule` | `backend/apps/admin_api/webapp/routers.py` | `reschedule_booking` | 386 | Да |
| POST | `/resolve-callback` | `backend/apps/admin_api/hh_sync.py` | `hh_resolve_callback` | 84 | Да |
| GET | `/rest/oauth2-credential/callback` | `backend/apps/admin_ui/routers/hh_integration.py` | `hh_oauth_callback_compat` | 237 | Да |
| POST | `/runs` | `backend/apps/admin_ui/routers/simulator.py` | `simulator_create_run` | 86 | Да |
| GET | `/runs/{run_id}` | `backend/apps/admin_ui/routers/simulator.py` | `simulator_get_run` | 184 | Да |
| GET | `/runs/{run_id}/report` | `backend/apps/admin_ui/routers/simulator.py` | `simulator_get_report` | 206 | Да |
| GET | `/simple` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `list_recruiters_simple` | 54 | Да |
| POST | `/slot-assignments` | `backend/apps/admin_ui/routers/slot_assignments.py` | `api_create_slot_assignment` | 68 | Да |
| POST | `/slot-assignments/{assignment_id}/approve-reschedule` | `backend/apps/admin_ui/routers/slot_assignments.py` | `api_approve_reschedule` | 120 | Да |
| POST | `/slot-assignments/{assignment_id}/confirm` | `backend/apps/admin_api/slot_assignments.py` | `api_confirm_slot_assignment` | 44 | Неочевидно |
| POST | `/slot-assignments/{assignment_id}/decline-reschedule` | `backend/apps/admin_ui/routers/slot_assignments.py` | `api_decline_reschedule` | 161 | Да |
| POST | `/slot-assignments/{assignment_id}/propose-alternative` | `backend/apps/admin_ui/routers/slot_assignments.py` | `api_propose_alternative` | 140 | Да |
| POST | `/slot-assignments/{assignment_id}/request-reschedule` | `backend/apps/admin_api/slot_assignments.py` | `api_request_reschedule` | 59 | Неочевидно |
| GET | `/slots` | `backend/apps/admin_api/webapp/routers.py` | `get_available_slots` | 197 | Да |
| GET | `/slots` | `backend/apps/admin_ui/routers/api.py` | `api_slots` | 885 | Да |
| POST | `/slots/bulk` | `backend/apps/admin_ui/routers/api.py` | `api_slots_bulk` | 1692 | Да |
| POST | `/slots/bulk_create` | `backend/apps/admin_ui/routers/api.py` | `api_slots_bulk_create` | 919 | Да |
| POST | `/slots/manual-bookings` | `backend/apps/admin_ui/routers/api.py` | `api_slots_manual_booking` | 1542 | Да |
| DELETE | `/slots/{slot_id}` | `backend/apps/admin_ui/routers/api.py` | `api_slot_delete` | 1668 | Да |
| POST | `/slots/{slot_id}/approve_booking` | `backend/apps/admin_ui/routers/api.py` | `api_slot_approve` | 1111 | Да |
| POST | `/slots/{slot_id}/book` | `backend/apps/admin_ui/routers/api.py` | `api_slot_book` | 1420 | Да |
| POST | `/slots/{slot_id}/outcome` | `backend/apps/admin_ui/routers/api.py` | `api_slot_outcome` | 1393 | Да |
| POST | `/slots/{slot_id}/propose` | `backend/apps/admin_ui/routers/api.py` | `api_slot_propose` | 1346 | Да |
| POST | `/slots/{slot_id}/reject_booking` | `backend/apps/admin_ui/routers/api.py` | `api_slot_reject` | 1123 | Да |
| POST | `/slots/{slot_id}/reschedule` | `backend/apps/admin_ui/routers/api.py` | `api_slot_reschedule` | 1135 | Да |
| GET | `/staff/attachments/{attachment_id}` | `backend/apps/admin_ui/routers/api.py` | `api_staff_attachment` | 606 | Да |
| POST | `/staff/messages/{message_id}/candidate/accept` | `backend/apps/admin_ui/routers/api.py` | `api_staff_candidate_task_accept` | 666 | Да |
| POST | `/staff/messages/{message_id}/candidate/decline` | `backend/apps/admin_ui/routers/api.py` | `api_staff_candidate_task_decline` | 676 | Да |
| GET | `/staff/threads` | `backend/apps/admin_ui/routers/api.py` | `api_staff_threads` | 387 | Да |
| POST | `/staff/threads` | `backend/apps/admin_ui/routers/api.py` | `api_staff_threads_create` | 504 | Да |
| GET | `/staff/threads/updates` | `backend/apps/admin_ui/routers/api.py` | `api_staff_threads_updates` | 529 | Да |
| POST | `/staff/threads/{thread_id}/candidate` | `backend/apps/admin_ui/routers/api.py` | `api_staff_candidate_task` | 656 | Да |
| GET | `/staff/threads/{thread_id}/members` | `backend/apps/admin_ui/routers/api.py` | `api_staff_thread_members` | 622 | Да |
| POST | `/staff/threads/{thread_id}/members` | `backend/apps/admin_ui/routers/api.py` | `api_staff_thread_members_add` | 631 | Да |
| DELETE | `/staff/threads/{thread_id}/members/{member_type}/{member_id}` | `backend/apps/admin_ui/routers/api.py` | `api_staff_thread_member_remove` | 645 | Да |
| GET | `/staff/threads/{thread_id}/messages` | `backend/apps/admin_ui/routers/api.py` | `api_staff_messages` | 540 | Да |
| POST | `/staff/threads/{thread_id}/messages` | `backend/apps/admin_ui/routers/api.py` | `api_staff_send_message` | 551 | Да |
| POST | `/staff/threads/{thread_id}/read` | `backend/apps/admin_ui/routers/api.py` | `api_staff_mark_read` | 597 | Да |
| GET | `/staff/threads/{thread_id}/updates` | `backend/apps/admin_ui/routers/api.py` | `api_staff_messages_updates` | 585 | Да |
| GET | `/template_keys` | `backend/apps/admin_ui/routers/content_api.py` | `api_template_keys` | 707 | Да |
| GET | `/template_presets` | `backend/apps/admin_ui/routers/content_api.py` | `api_template_presets` | 712 | Да |
| POST | `/templates` | `backend/apps/admin_ui/routers/content_api.py` | `api_template_create` | 606 | Да |
| GET | `/templates/list` | `backend/apps/admin_ui/routers/content_api.py` | `api_templates_list` | 496 | Да |
| DELETE | `/templates/{template_id:int}` | `backend/apps/admin_ui/routers/content_api.py` | `api_template_delete` | 588 | Да |
| GET | `/templates/{template_id:int}` | `backend/apps/admin_ui/routers/content_api.py` | `api_template_detail` | 527 | Да |
| PUT | `/templates/{template_id:int}` | `backend/apps/admin_ui/routers/content_api.py` | `api_template_update` | 546 | Да |
| GET | `/test-builder/graph` | `backend/apps/admin_ui/routers/content_api.py` | `api_test_builder_graph` | 428 | Да |
| POST | `/test-builder/graph/apply` | `backend/apps/admin_ui/routers/content_api.py` | `api_test_builder_graph_apply` | 447 | Да |
| POST | `/test-builder/graph/preview` | `backend/apps/admin_ui/routers/content_api.py` | `api_test_builder_graph_preview` | 466 | Да |
| GET | `/timezones` | `backend/apps/admin_ui/routers/api.py` | `api_timezones` | 1781 | Да |
| POST | `/token` | `backend/apps/admin_ui/routers/auth.py` | `login_for_access_token` | 94 | Да |
| GET | `/vacancies` | `backend/apps/admin_ui/routers/api.py` | `api_list_vacancies` | 3513 | Да |
| POST | `/vacancies` | `backend/apps/admin_ui/routers/api.py` | `api_create_vacancy` | 3543 | Да |
| DELETE | `/vacancies/{vacancy_id}` | `backend/apps/admin_ui/routers/api.py` | `api_delete_vacancy` | 3599 | Да |
| PUT | `/vacancies/{vacancy_id}` | `backend/apps/admin_ui/routers/api.py` | `api_update_vacancy` | 3569 | Да |
| GET | `/vacancies/{vacancy_id}/questions/{test_id}` | `backend/apps/admin_ui/routers/api.py` | `api_get_vacancy_questions` | 3610 | Да |
| GET | `/webhooks` | `backend/apps/admin_ui/routers/hh_integration.py` | `list_hh_webhooks` | 288 | Да |
| POST | `/webhooks/register` | `backend/apps/admin_ui/routers/hh_integration.py` | `register_hh_webhooks` | 312 | Да |
| POST | `/webhooks/{webhook_key}` | `backend/apps/hh_integration_webhooks.py` | `receive_hh_webhook` | 28 | Да |
| POST | `/{assignment_id}/confirm` | `backend/apps/admin_ui/routers/assignments.py` | `confirm_assignment` | 21 | Неочевидно |
| POST | `/{assignment_id}/confirm` | `backend/apps/admin_ui/routers/slot_assignments_api.py` | `confirm_assignment` | 85 | Неочевидно |
| POST | `/{assignment_id}/decline` | `backend/apps/admin_ui/routers/slot_assignments_api.py` | `decline_assignment` | 221 | Неочевидно |
| POST | `/{assignment_id}/request-reschedule` | `backend/apps/admin_ui/routers/assignments.py` | `request_reschedule` | 32 | Неочевидно |
| POST | `/{assignment_id}/request-reschedule` | `backend/apps/admin_ui/routers/slot_assignments_api.py` | `request_reschedule` | 172 | Неочевидно |
| GET | `/{candidate_id}` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_detail` | 335 | Да |
| POST | `/{candidate_id}/actions/approve_upcoming_slot` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_approve_upcoming_slot` | 812 | Да |
| POST | `/{candidate_id}/actions/{action_key}` | `backend/apps/admin_ui/routers/candidates.py` | `api_candidate_action` | 1351 | Да |
| POST | `/{candidate_id}/actions/{action}` | `backend/apps/admin_ui/routers/workflow.py` | `apply_action` | 45 | Неочевидно |
| POST | `/{candidate_id}/assign-city` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_assign_city` | 1061 | Да |
| POST | `/{candidate_id}/delete` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_delete` | 857 | Да |
| POST | `/{candidate_id}/interview-notes` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_save_interview_notes` | 675 | Да |
| GET | `/{candidate_id}/interview-notes/download` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_download_interview_notes` | 728 | Да |
| POST | `/{candidate_id}/invite-token` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_invite_token` | 313 | Да |
| GET | `/{candidate_id}/reports/{report_key}` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_download_report` | 872 | Да |
| GET | `/{candidate_id}/resend-test2` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_resend_test2` | 581 | Да |
| GET | `/{candidate_id}/schedule-intro-day` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_schedule_intro_day_form` | 1052 | Да |
| POST | `/{candidate_id}/schedule-intro-day` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_schedule_intro_day_submit` | 1071 | Да |
| GET | `/{candidate_id}/schedule-slot` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_schedule_slot_form` | 907 | Да |
| POST | `/{candidate_id}/schedule-slot` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_schedule_slot_submit` | 916 | Да |
| POST | `/{candidate_id}/slots/{slot_id}/approve` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_approve_slot` | 779 | Да |
| GET | `/{candidate_id}/state` | `backend/apps/admin_ui/routers/workflow.py` | `get_candidate_state` | 34 | Неочевидно |
| POST | `/{candidate_id}/status` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_set_status` | 390 | Да |
| POST | `/{candidate_id}/toggle` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_toggle` | 381 | Да |
| POST | `/{candidate_id}/update` | `backend/apps/admin_ui/routers/candidates.py` | `candidates_update` | 344 | Да |
| POST | `/{city_id}/delete` | `backend/apps/admin_ui/routers/cities.py` | `cities_delete` | 401 | Неочевидно |
| GET | `/{city_id}/edit` | `backend/apps/admin_ui/routers/cities.py` | `cities_edit_page` | 197 | Неочевидно |
| POST | `/{city_id}/edit` | `backend/apps/admin_ui/routers/cities.py` | `cities_edit_submit` | 202 | Неочевидно |
| POST | `/{city_id}/owner` | `backend/apps/admin_ui/routers/cities.py` | `update_city_owner` | 339 | Неочевидно |
| POST | `/{city_id}/settings` | `backend/apps/admin_ui/routers/cities.py` | `update_city_settings` | 212 | Неочевидно |
| POST | `/{city_id}/status` | `backend/apps/admin_ui/routers/cities.py` | `update_city_status_api` | 373 | Неочевидно |
| DELETE | `/{entry_id}` | `backend/apps/admin_ui/routers/detailization.py` | `api_detailization_delete` | 125 | Да |
| PATCH | `/{entry_id}` | `backend/apps/admin_ui/routers/detailization.py` | `api_detailization_update` | 102 | Да |
| GET | `/{question_id}/edit` | `backend/apps/admin_ui/routers/questions.py` | `questions_edit` | 13 | Неочевидно |
| POST | `/{question_id}/update` | `backend/apps/admin_ui/routers/questions.py` | `questions_update` | 18 | Неочевидно |
| POST | `/{rec_id}/delete` | `backend/apps/admin_ui/routers/recruiters.py` | `recruiters_delete` | 33 | Неочевидно |
| GET | `/{rec_id}/edit` | `backend/apps/admin_ui/routers/recruiters.py` | `recruiters_edit` | 23 | Неочевидно |
| POST | `/{rec_id}/update` | `backend/apps/admin_ui/routers/recruiters.py` | `recruiters_update` | 28 | Неочевидно |
| DELETE | `/{recruiter_id}` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `delete_recruiter` | 207 | Да |
| GET | `/{recruiter_id}` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `get_recruiter` | 107 | Да |
| PATCH | `/{recruiter_id}` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `update_recruiter` | 163 | Да |
| GET | `/{recruiter_id}/cities` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `get_recruiter_cities` | 236 | Да |
| GET | `/{recruiter_id}/slots/free` | `backend/apps/admin_ui/routers/recruiters_api_example.py` | `count_free_slots` | 261 | Да |
| GET | `/{region_id}/timezone` | `backend/apps/admin_ui/routers/regions.py` | `region_timezone` | 11 | Неочевидно |
| POST | `/{request_id}/approve` | `backend/apps/admin_ui/routers/reschedule_requests.py` | `approve_reschedule_request` | 38 | Да |
| POST | `/{request_id}/propose-new` | `backend/apps/admin_ui/routers/reschedule_requests.py` | `propose_new_time` | 102 | Да |
| DELETE | `/{slot_id}` | `backend/apps/admin_ui/routers/slots.py` | `slots_delete` | 480 | Да |
| GET | `/{slot_id}` | `backend/apps/admin_ui/routers/slots.py` | `slots_api_detail` | 442 | Да |
| PUT | `/{slot_id}` | `backend/apps/admin_ui/routers/slots.py` | `slots_api_update` | 373 | Да |
| POST | `/{slot_id}/approve_booking` | `backend/apps/admin_ui/routers/slots.py` | `slots_approve_booking` | 645 | Да |
| POST | `/{slot_id}/book` | `backend/apps/admin_ui/routers/slots.py` | `slots_book_candidate` | 702 | Да |
| POST | `/{slot_id}/delete` | `backend/apps/admin_ui/routers/slots.py` | `slots_delete_form` | 464 | Да |
| POST | `/{slot_id}/outcome` | `backend/apps/admin_ui/routers/slots.py` | `slots_set_outcome` | 588 | Да |
| POST | `/{slot_id}/propose` | `backend/apps/admin_ui/routers/slots.py` | `slots_propose_candidate` | 664 | Да |
| POST | `/{slot_id}/reject_booking` | `backend/apps/admin_ui/routers/slots.py` | `slots_reject_booking` | 633 | Да |
| POST | `/{slot_id}/reschedule` | `backend/apps/admin_ui/routers/slots.py` | `slots_reschedule` | 621 | Да |
| POST | `/{template_id}/delete` | `backend/apps/admin_ui/routers/message_templates.py` | `message_templates_delete` | 55 | Неочевидно |
| GET | `/{template_id}/edit` | `backend/apps/admin_ui/routers/message_templates.py` | `message_templates_edit` | 45 | Неочевидно |
| POST | `/{template_id}/update` | `backend/apps/admin_ui/routers/message_templates.py` | `message_templates_update` | 50 | Неочевидно |

## 7. Каталог env-переменных

| Ключ | Используется в | Назначение | Обязательная |
|---|---|---|---|
| `AB_PERCENT` | docs/AI_INTERVIEW_SCRIPT_RUNBOOK.md | Назначение требует ручного ревью | Неочевидно |
| `ACCESS_TOKEN_TTL_HOURS` | .env.example, .env.local.example, tests/test_security_auth_hardening.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `ACTION_CONFIRM` | backend/domain/slot_assignment_service.py | Назначение требует ручного ревью | Неочевидно |
| `ACTION_RESCHEDULE` | backend/domain/slot_assignment_service.py | Назначение требует ручного ревью | Неочевидно |
| `ACTION_TOKEN_TTL_HOURS` | backend/domain/slot_assignment_service.py | Назначение требует ручного ревью | Неочевидно |
| `ACTIVE` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `ACTIVE_ASSIGNMENT_STATUSES` | backend/domain/slot_assignment_service.py | Назначение требует ручного ревью | Неочевидно |
| `ACTIVE_SLOT_STATUSES` | backend/domain/slot_assignment_service.py | Назначение требует ручного ревью | Неочевидно |
| `ACTIVE_UNIQUE_INDEX` | backend/migrations/versions/0084_allow_intro_day_parallel_slots.py | Назначение требует ручного ревью | Неочевидно |
| `ADMIN_CHAT_ID` | audit/SECURITY.md, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `ADMIN_DOCS_ENABLED` | docs/archive/qa/TEST_REPORT.md | Назначение требует ручного ревью | Неочевидно |
| `ADMIN_PASSWORD` | .claude/settings.local.json, .env.example, .env.local, .env.local.example, audit/SECURITY.md, backend/core/settings.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `ADMIN_PRINCIPAL_ID` | backend/apps/admin_ui/security.py, scripts/seed_auth_accounts.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `ADMIN_USER` | .claude/settings.local.json, .env.example, .env.local, .env.local.example, audit/DIAGNOSIS.md, audit/SECURITY.md… | Используется в нескольких runtime/test слоях | Неочевидно |
| `ADMIN_USERNAME` | scripts/seed_auth_accounts.py | Назначение требует ручного ревью | Неочевидно |
| `AI_ENABLED` | .env.example, .env.local, .env.local.example, backend/core/settings.py, docs/AI_COACH_RUNBOOK.md, frontend/app/playwright.config.ts… | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_INTERVIEW_SCRIPT_AB_PERCENT` | .env.example, .env.local.example | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_INTERVIEW_SCRIPT_CACHE_TTL_HOURS` | .env.example, .env.local.example | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_INTERVIEW_SCRIPT_FT_MIN_SAMPLES` | .env.example, .env.local.example | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_INTERVIEW_SCRIPT_FT_MODEL` | .env.example, .env.local.example, backend/core/settings.py, docs/AI_INTERVIEW_SCRIPT_RUNBOOK.md, scripts/run_interview_script_finetune.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_INTERVIEW_SCRIPT_MAX_TOKENS` | .env.example, .env.local, .env.local.example | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_INTERVIEW_SCRIPT_PII_MODE` | .env.example, .env.local.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_INTERVIEW_SCRIPT_TIMEOUT_SECONDS` | .env.example, .env.local, .env.local.example | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_MAX_TOKENS` | .env.example, .env.local.example | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_PII_MODE` | .env.example, .env.local.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_PROVIDER` | .env.example, .env.local, .env.local.example, backend/core/settings.py, frontend/app/playwright.config.ts, tests/test_ai_copilot.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `AI_REASONING_EFFORT` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `AI_TIMEOUT_SECONDS` | .env.example, .env.local.example | Используется в нескольких runtime/test слоях | Неочевидно |
| `ALLOWED_MIME_TYPES` | backend/apps/admin_ui/services/staff_chat.py | Назначение требует ручного ревью | Неочевидно |
| `ALLOW_DEV_AUTOADMIN` | .env.local.example, backend/apps/admin_ui/security.py, frontend/app/playwright.config.ts, tests/conftest.py, tests/test_admin_auth_no_basic_challenge.py, tests/test_admin_surface_hardening.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `ALLOW_LEGACY_BASIC` | backend/apps/admin_ui/security.py, frontend/app/playwright.config.ts, tests/conftest.py, tests/test_admin_candidate_chat_actions.py, tests/test_admin_surface_hardening.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `AMBIENT_BACKGROUND_ROUTES` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `ANIMATION_DURATION` | docs/archive/qa/QA_COMPREHENSIVE_REPORT.md | Назначение требует ручного ревью | Неочевидно |
| `API_URL` | frontend/app/src/api/client.ts | Назначение требует ручного ревью | Неочевидно |
| `APPROVED` | backend/apps/bot/services.py, backend/domain/models.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `APSCHEDULER_AVAILABLE` | backend/apps/bot/reminders.py | Назначение требует ручного ревью | Неочевидно |
| `ARCHIVE_STAGE_BY_STATUS` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `ARCHIVE_STAGE_LABELS` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `ASSIGN` | backend/apps/admin_ui/routers/slots.py | Назначение требует ручного ревью | Неочевидно |
| `ASSIGN_SLOT` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `ATTEMPTS_COLUMN` | backend/migrations/versions/0013_enhance_notification_logs.py | Назначение требует ручного ревью | Неочевидно |
| `AUTH_BRUTE_FORCE_ENABLED` | backend/apps/admin_ui/routers/auth.py, tests/test_security_auth_hardening.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `AVAILABILITY_WINDOWS` | frontend/app/src/app/routes/app/incoming-demo.ts | Назначение требует ручного ревью | Неочевидно |
| `BACKDROP` | docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md | Назначение требует ручного ревью | Неочевидно |
| `BASE_DIR` | backend/apps/admin_ui/app.py, backend/apps/admin_ui/config.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOOKED` | backend/domain/models.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOOKING_STATES` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `BOOKING_STATES_LOWER` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `BORDER` | docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md | Назначение требует ручного ревью | Неочевидно |
| `BOT_API_BASE` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `BOT_AUTOSTART` | .env.example, .env.local, .env.local.example, tests/test_admin_ui_auth_startup.py, tests/test_staff_chat_file_upload.py, tests/test_staff_chat_updates.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOT_BACKEND_URL` | .env.example, .env.local, .env.local.example, backend/apps/bot/config.py, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOT_CALLBACK_SECRET` | .env.example, .env.local, .env.local.example, backend/core/settings.py, docs/project/DEPLOYMENT_GUIDE.md, tests/test_admin_auth_no_basic_challenge.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOT_ENABLED` | .claude/settings.local.json, .env.example, .env.local, .env.local.example, backend/core/settings.py, docs/performance/loadtesting.md… | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOT_ENTERED` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `BOT_FAILFAST` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `BOT_HEARTBEAT_FILE` | backend/apps/bot/app.py, docker-compose.yml | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOT_HEARTBEAT_MAX_AGE` | docker-compose.yml | Назначение требует ручного ревью | Неочевидно |
| `BOT_INTEGRATION_ENABLED` | .claude/settings.local.json, .env.example, .env.local, docs/performance/results_20260301_go_gate.md, tests/test_admin_slots_api.py, tests/test_bot_integration_toggle.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOT_PROVIDER` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `BOT_RUNTIME_AVAILABLE` | backend/apps/admin_ui/services/bot_service.py | Назначение требует ручного ревью | Неочевидно |
| `BOT_START` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `BOT_TEMPLATE_PROVIDER` | backend/apps/bot/services.py | Назначение требует ручного ревью | Неочевидно |
| `BOT_TOKEN` | .env.example, .env.local, .env.local.example, backend/apps/bot/app.py, backend/apps/bot/config.py, backend/core/settings.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `BOT_WEBHOOK_URL` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `BROKER_UNAVAILABLE_REASON` | backend/apps/bot/services.py | Назначение требует ручного ревью | Неочевидно |
| `BUILDER` | frontend/app/src/theme/global.css | Назначение требует ручного ревью | Неочевидно |
| `BUILDER_DISABLED_DEFAULT` | frontend/app/src/app/components/QuestionPayloadEditor.tsx | Назначение требует ручного ревью | Неочевидно |
| `CACHE_DEFAULT_TTL_SECONDS` | docs/archive/optimization/PHASE2_PERFORMANCE.md | Назначение требует ручного ревью | Неочевидно |
| `CACHE_HEALTH_INTERVAL` | backend/apps/admin_ui/app.py, docs/archive/SERVER_STABILITY.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `CACHE_RETRY_ATTEMPTS` | backend/apps/admin_ui/app.py, docs/archive/SERVER_STABILITY.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `CACHE_RETRY_BASE_DELAY` | backend/apps/admin_ui/app.py, docs/archive/SERVER_STABILITY.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `CACHE_RETRY_MAX_DELAY` | backend/apps/admin_ui/app.py, docs/archive/SERVER_STABILITY.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `CANCELED` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `CANCELLED` | backend/apps/bot/services.py, backend/domain/models.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `CANDIDATE_COLUMN` | backend/migrations/versions/0011_add_candidate_binding_to_notification_logs.py | Назначение требует ручного ревью | Неочевидно |
| `CARD_MIN_WIDTH` | docs/archive/qa/QA_COMPREHENSIVE_REPORT.md | Назначение требует ручного ревью | Неочевидно |
| `CHAT_MODE_TTL_MINUTES` | backend/apps/admin_ui/services/chat.py | Назначение требует ручного ревью | Неочевидно |
| `CHAT_RATE_LIMIT_PER_HOUR` | backend/apps/admin_ui/services/chat.py, tests/test_chat_rate_limit.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `CHAT_RATE_LIMIT_REDIS_TTL_SECONDS` | backend/apps/admin_ui/services/chat.py | Назначение требует ручного ревью | Неочевидно |
| `CHAT_RATE_LIMIT_WINDOW_SECONDS` | backend/apps/admin_ui/services/chat.py, tests/test_chat_rate_limit.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `CHOICE_TEMPLATE` | frontend/app/src/app/components/QuestionPayloadEditor.tsx | Назначение требует ручного ревью | Неочевидно |
| `CI` | frontend/app/playwright.config.ts | Назначение требует ручного ревью | Неочевидно |
| `CITY_ADDRESSES` | scripts/update_notification_templates.py | Назначение требует ручного ревью | Неочевидно |
| `CLASSES` | backend/apps/admin_ui/static/css/design-system.css, frontend/app/src/theme/global.css | Используется в нескольких runtime/test слоях | Неочевидно |
| `CODEBASE` | docs/QUALITY_SCORECARD.md | Назначение требует ручного ревью | Неочевидно |
| `COHORT_STAGE_LABELS` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `COHORT_STAGE_ORDER` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `COL` | backend/migrations/versions/0081_add_detailization_soft_delete.py | Назначение требует ручного ревью | Неочевидно |
| `COLUMN` | backend/migrations/versions/0049_allow_null_city_timezone.py | Назначение требует ручного ревью | Неочевидно |
| `COMMON_VARIABLES` | backend/domain/template_contexts.py | Назначение требует ручного ревью | Неочевидно |
| `COMPANY_TZ` | backend/apps/admin_ui/services/kpis.py, tests/services/test_weekly_kpis.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `COMPLETED` | backend/domain/candidates/models.py, backend/domain/models.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `COMPLETE_INTERVIEW` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIG_ERROR_HINTS` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRMED` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRMED_ASSIGNMENT_STATUSES` | backend/domain/slot_assignment_service.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRMED_BY_CANDIDATE` | backend/domain/models.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `CONFIRMED_SLOT_STATUSES` | frontend/app/src/app/routes/app/messenger.tsx | Назначение требует ручного ревью | Неочевидно |
| `CONFIRMED_STATUS` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRM_2H` | backend/apps/bot/reminders.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRM_3H` | backend/apps/bot/reminders.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRM_6H` | backend/apps/bot/reminders.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRM_INTERVIEW` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `CONFIRM_ONBOARDING` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `CONFLICTED` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `CONSTRAINT_NAME` | backend/migrations/versions/0039_allow_multiple_recruiters_per_city.py, backend/migrations/versions/0041_add_slot_overlap_exclusion_constraint.py, backend/migrations/versions/0050_align_slot_overlap_bounds_and_duration_default.py, backend/migrations/versions/0051_enforce_slot_overlap_on_10min_windows.py, backend/migrations/versions/0080_slot_overlap_per_purpose.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `CONTACTED` | backend/domain/candidates/status.py | Назначение требует ручного ревью | Неочевидно |
| `CONTENT_UPDATES_CHANNEL` | backend/core/content_updates.py | Назначение требует ручного ревью | Неочевидно |
| `CONVERSATION_CHAT` | backend/domain/candidates/services.py | Назначение требует ручного ревью | Неочевидно |
| `CONVERSATION_CHAT_TTL_MINUTES` | backend/domain/candidates/services.py | Назначение требует ручного ревью | Неочевидно |
| `CONVERSATION_FLOW` | backend/domain/candidates/services.py | Назначение требует ручного ревью | Неочевидно |
| `COOKIE` | .claude/settings.local.json | Назначение требует ручного ревью | Неочевидно |
| `CREATED` | backend/domain/candidates/models.py | Назначение требует ручного ревью | Неочевидно |
| `CRITICAL_ROUTES` | scripts/loadtest_profiles/analyze_step.py | Назначение требует ручного ревью | Неочевидно |
| `CRM_PUBLIC_URL` | .env.example, .env.local, .env.local.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `CSV_REPORT` | scripts/collect_ux.py | Назначение требует ручного ревью | Неочевидно |
| `DASHBOARD_INCOMING_FILTERS_KEY` | frontend/app/src/app/routes/app/dashboard.tsx | Назначение требует ручного ревью | Неочевидно |
| `DATABASE_URL` | .claude/settings.local.json, .env.development.example, .env.example, .env.local, .env.local.example, backend/core/settings.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `DATA_DIR` | .env.example, .env.local, .env.local.example, backend/core/settings.py, docs/project/DEPLOYMENT_GUIDE.md, frontend/app/playwright.config.ts… | Используется в нескольких runtime/test слоях | Неочевидно |
| `DAY_NAMES_SHORT` | backend/apps/bot/jinja_renderer.py | Назначение требует ручного ревью | Неочевидно |
| `DB_ACTIVE_CONNECTIONS` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_HEALTH_INTERVAL` | backend/apps/admin_ui/app.py | Назначение требует ручного ревью | Неочевидно |
| `DB_HEALTH_MAX_INTERVAL` | backend/apps/admin_ui/app.py | Назначение требует ручного ревью | Неочевидно |
| `DB_MAX_OVERFLOW` | .env.example, docs/archive/SERVER_STABILITY.md, docs/performance/results_20260301_go_gate.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `DB_POOL_ACQUIRE_SECONDS` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_POOL_CHECKED_OUT` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_POOL_OVERFLOW` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_POOL_RECYCLE` | docs/archive/SERVER_STABILITY.md | Назначение требует ручного ревью | Неочевидно |
| `DB_POOL_SIZE` | .env.example, backend/apps/admin_ui/perf/metrics/prometheus.py, docs/archive/SERVER_STABILITY.md, docs/performance/results_20260301_go_gate.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `DB_POOL_TIMEOUT` | .env.example, docs/archive/SERVER_STABILITY.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `DB_POOL_TIMEOUTS_TOTAL` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_PROFILE_ENABLED` | backend/apps/admin_ui/perf/metrics/db.py, docs/performance/loadtesting.md, docs/performance/results_20260217.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `DB_PROFILE_FLUSH_SECONDS` | backend/apps/admin_ui/perf/metrics/db.py, docs/performance/loadtesting.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `DB_PROFILE_MAX_KEYS` | backend/apps/admin_ui/perf/metrics/db.py | Назначение требует ручного ревью | Неочевидно |
| `DB_PROFILE_OUTPUT` | backend/apps/admin_ui/perf/metrics/db.py, docs/performance/loadtesting.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `DB_PROFILE_SAMPLE_RATE` | backend/apps/admin_ui/perf/metrics/db.py, docs/performance/loadtesting.md, docs/performance/results_20260217.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `DB_QUERIES_TOTAL` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_QUERY_DURATION_SECONDS` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_SLOW_QUERIES_TOTAL` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DB_SLOW_QUERY_SECONDS` | backend/apps/admin_ui/perf/metrics/db.py | Назначение требует ручного ревью | Неочевидно |
| `DB_TOO_MANY_CONNECTIONS_TOTAL` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `DDKA` | frontend/app/package-lock.json | Назначение требует ручного ревью | Неочевидно |
| `DEAD` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `DEBUG_UX` | docs/archive/ux/metrics-kpi.md | Назначение требует ручного ревью | Неочевидно |
| `DECLINED` | backend/domain/candidates/status.py, backend/domain/models.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `DECLINED_STATUS_SLUGS` | frontend/app/src/app/routes/app/candidate-detail.tsx | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_BOT_PROPERTIES` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_CHANNEL` | backend/apps/admin_ui/services/message_templates.py, frontend/app/src/app/routes/app/template-list.tsx, scripts/seed_message_templates.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `DEFAULT_CITIES` | scripts/seed_test_users.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_CLOSING_CHECKLIST` | frontend/app/src/app/components/InterviewScript/script.prompts.ts | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_CMD` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_COMPANY_NAME` | backend/apps/admin_ui/services/slots.py, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `DEFAULT_COMPANY_TZ` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_DELAY` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_DURATION` | backend/migrations/versions/0050_align_slot_overlap_bounds_and_duration_default.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_GROUP_TITLE` | backend/apps/admin_ui/services/staff_chat.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_INTERVIEW_DURATION_MIN` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_INTRO_DAY_DURATION_MIN` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_LOCALE` | backend/apps/admin_ui/services/message_templates.py, frontend/app/src/app/routes/app/template-list.tsx, scripts/seed_message_templates.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `DEFAULT_PIPELINE` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_PREVIEW` | frontend/app/src/app/routes/app/template-new.tsx | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_SLOT_TZ` | backend/apps/admin_ui/services/slots.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_TEST_QUESTIONS` | backend/domain/tests/bootstrap.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_TIMEZONE` | backend/core/timezone.py, backend/core/timezone_utils.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `DEFAULT_TZ` | backend/apps/admin_ui/services/bot_service.py, backend/apps/admin_ui/timezones.py, backend/apps/admin_ui/utils.py, backend/apps/bot/config.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `DEFAULT_USER_DATA_DIR` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `DEFAULT_VERSION` | backend/apps/admin_ui/services/message_templates.py, scripts/seed_message_templates.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `DEFAULT_WATCH` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `DELETE` | backend/apps/admin_ui/routers/slots.py | Назначение требует ручного ревью | Неочевидно |
| `DETAIL_ROUTE_PREFIXES` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `DEV` | frontend/app/src/app/routes/__root.tsx, frontend/app/src/app/routes/app/simulator.tsx | Используется в нескольких runtime/test слоях | Неочевидно |
| `DEVSERVER_CMD` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `DEVSERVER_RESTART_DELAY` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `DIRECT_NO_BROKER_REASON` | backend/apps/bot/services.py | Назначение требует ручного ревью | Неочевидно |
| `DONE` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `DRAFT_STORAGE_PREFIX` | frontend/app/src/app/routes/app/messenger/useMessageDraft.ts | Назначение требует ручного ревью | Неочевидно |
| `DURATION_SECONDS` | docs/performance/loadtesting.md, docs/performance/results_20260216.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `E2E_SEED_AI` | backend/apps/admin_ui/app.py, frontend/app/playwright.config.ts | Используется в нескольких runtime/test слоях | Неочевидно |
| `ELIGIBLE_ASSIGNMENT_STATUSES` | backend/apps/admin_ui/services/detailization.py | Назначение требует ручного ревью | Неочевидно |
| `ENABLE_LEGACY_ASSIGNMENTS_API` | backend/apps/admin_ui/app.py, tests/test_admin_surface_hardening.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `ENABLE_LEGACY_STATUS_API` | .env.example, backend/apps/admin_ui/routers/candidates.py, docs/archive/candidate_profile.md, frontend/app/openapi.json, frontend/app/src/api/schema.ts | Используется в нескольких runtime/test слоях | Неочевидно |
| `ENHANCEMENTS` | backend/apps/admin_ui/static/css/design-system.css | Назначение требует ручного ревью | Неочевидно |
| `ENVIRONMENT` | .claude/settings.local.json, .env.development.example, .env.example, .env.local, .env.local.example, backend/apps/admin_ui/app.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `ERROR` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `ERROR_MESSAGES` | docs/archive/features/dashboard/DASHBOARD_CHANGELOG.md | Назначение требует ручного ревью | Неочевидно |
| `EXCLUDE_DIRS` | audit/generate_inventory.py | Назначение требует ручного ревью | Неочевидно |
| `EXPIRED` | backend/domain/candidates/models.py, backend/domain/models.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `FAILED` | backend/domain/candidates/models.py, backend/domain/hh_integration/contracts.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `FALL_BACK` | backend/core/timezone_service.py | Назначение требует ручного ревью | Неочевидно |
| `FINAL_OUTCOME_ATTACHED` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `FINAL_OUTCOME_LABELS` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `FINAL_OUTCOME_NOT_ATTACHED` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `FINAL_OUTCOME_NOT_COUNTED` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `FIRST_NAMES` | frontend/app/src/app/routes/app/incoming-demo.ts | Назначение требует ручного ревью | Неочевидно |
| `FOLLOWUP_NOTICE_PERIOD` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `FOLLOWUP_STUDY_FLEX` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `FOLLOWUP_STUDY_MODE` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `FOLLOWUP_STUDY_SCHEDULE` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `FORCE_SSL` | codex/agents/devops_ci.md, docs/LOCAL_DEV.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `FREE` | backend/domain/models.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `FUNCTIONS` | docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md | Назначение требует ручного ревью | Неочевидно |
| `FUNNEL_DROP_TTL_HOURS` | backend/apps/admin_ui/services/dashboard.py | Назначение требует ручного ревью | Неочевидно |
| `FUNNEL_STATUS_EVENTS` | backend/domain/candidates/status_service.py | Назначение требует ручного ревью | Неочевидно |
| `GENERAL_NOTES` | frontend/app/src/app/routes/app/incoming-demo.ts | Назначение требует ручного ревью | Неочевидно |
| `GENERIC_MISSING_TEMPLATE_TEXT` | backend/apps/bot/template_provider.py | Назначение требует ручного ревью | Неочевидно |
| `GF_SECURITY_ADMIN_PASSWORD` | docs/archive/SERVER_STABILITY.md | Назначение требует ручного ревью | Неочевидно |
| `GLASS` | docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md | Назначение требует ручного ревью | Неочевидно |
| `GLOBAL_DEFAULTS` | backend/apps/admin_ui/services/city_reminder_policy.py | Назначение требует ручного ревью | Неочевидно |
| `GLOBAL_REFRESH_LIMITER` | backend/apps/admin_ui/perf/limits/refresh_limiter.py | Назначение требует ручного ревью | Неочевидно |
| `GRAPH_KEY_PREFIX` | backend/apps/admin_ui/services/builder_graph.py | Назначение требует ручного ревью | Неочевидно |
| `HEADER_NAME` | backend/apps/admin_ui/middleware.py | Назначение требует ручного ревью | Неочевидно |
| `HH_API_BASE_URL` | .env.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_CLIENT_ID` | .env.example, backend/core/settings.py, tests/test_city_hh_vacancies_api.py, tests/test_hh_integration_actions.py, tests/test_hh_integration_foundation.py, tests/test_hh_integration_import.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_CLIENT_SECRET` | .env.example, backend/core/settings.py, tests/test_city_hh_vacancies_api.py, tests/test_hh_integration_actions.py, tests/test_hh_integration_foundation.py, tests/test_hh_integration_import.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_INTEGRATION_ENABLED` | .env.example, tests/test_city_hh_vacancies_api.py, tests/test_hh_integration_actions.py, tests/test_hh_integration_foundation.py, tests/test_hh_integration_import.py, tests/test_hh_integration_jobs.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_OAUTH_AUTHORIZE_URL` | .env.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_OAUTH_STATE_TTL_SECONDS` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `HH_REDIRECT_URI` | .env.example, backend/core/settings.py, tests/test_city_hh_vacancies_api.py, tests/test_hh_integration_actions.py, tests/test_hh_integration_foundation.py, tests/test_hh_integration_import.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_SYNC_ENABLED` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `HH_USER_AGENT` | .env.example, backend/core/settings.py, tests/test_city_hh_vacancies_api.py, tests/test_hh_integration_actions.py, tests/test_hh_integration_foundation.py, tests/test_hh_integration_import.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_WEBHOOK_BASE_URL` | .env.example, backend/core/settings.py, tests/test_city_hh_vacancies_api.py, tests/test_hh_integration_actions.py, tests/test_hh_integration_foundation.py, tests/test_hh_integration_import.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `HH_WEBHOOK_SECRET` | .env.example, backend/core/settings.py, backend/domain/hh_sync/worker.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `HIGHLIGHT` | docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md | Назначение требует ручного ревью | Неочевидно |
| `HIRED` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `HOST` | frontend/app/playwright.config.ts | Назначение требует ручного ревью | Неочевидно |
| `HOT_READ_POLICY` | backend/apps/admin_ui/perf/cache/policy.py | Назначение требует ручного ревью | Неочевидно |
| `HR_PHONE` | scripts/update_notification_templates.py | Назначение требует ручного ревью | Неочевидно |
| `HTML` | tests/services/test_bot_keyboards.py | Назначение требует ручного ревью | Неочевидно |
| `HTTP_REQUEST_LOG_ENABLED` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `HTTP_SLOW_REQUEST_MS` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `ICONS` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `IDX` | backend/migrations/versions/0081_add_detailization_soft_delete.py | Назначение требует ручного ревью | Неочевидно |
| `IDX_RECRUITER_START` | backend/migrations/versions/0082_add_calendar_tasks.py | Назначение требует ручного ревью | Неочевидно |
| `IDX_START_END` | backend/migrations/versions/0082_add_calendar_tasks.py | Назначение требует ручного ревью | Неочевидно |
| `IMPROVEMENTS` | frontend/app/src/theme/global.css | Назначение требует ручного ревью | Неочевидно |
| `INBOUND` | backend/domain/candidates/models.py, backend/domain/hh_integration/contracts.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `INCOMING_FETCH_LIMIT` | frontend/app/src/app/routes/app/dashboard.tsx | Назначение требует ручного ревью | Неочевидно |
| `INCOMING_FILTERS_STORAGE_KEY` | frontend/app/src/app/routes/app/incoming.filters.ts | Назначение требует ручного ревью | Неочевидно |
| `INCOMING_PAGE_SIZE_OPTIONS` | frontend/app/src/app/routes/app/dashboard.tsx | Назначение требует ручного ревью | Неочевидно |
| `INDEX_NAME` | backend/migrations/versions/0006_add_slots_recruiter_start_index.py, backend/migrations/versions/0012_update_slots_candidate_recruiter_index.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTERVIEW` | backend/domain/candidates/status.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_COMPLETED` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_CONFIRMATION_2H` | scripts/update_notification_templates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_CONFIRMED` | backend/domain/candidates/status.py, backend/domain/candidates/workflow.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTERVIEW_DECLINED` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTERVIEW_FIELD_TYPES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_FORM_SECTIONS` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_INVITATION` | scripts/update_notification_templates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_PIPELINE_STATUSES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_RECOMMENDATION_CHOICES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_RECOMMENDATION_LOOKUP` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_RECOMMENDATION_VALUES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTERVIEW_SCHEDULED` | backend/domain/candidates/status.py, backend/domain/candidates/workflow.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTERVIEW_SLOT_FALLBACK_STATUSES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_ADDRESS_FALLBACK` | backend/apps/bot/services.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_ATTEND_STATES` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_ATTEND_STATES_LOWER` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_CONTACT_FALLBACK` | backend/apps/bot/services.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_DAY` | backend/domain/candidates/status.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_DAY_CONFIRMED_DAY_OF` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTRO_DAY_CONFIRMED_PRELIMINARY` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTRO_DAY_DECLINED_DAY_OF` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTRO_DAY_DECLINED_INVITATION` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTRO_DAY_INVITATION_TEMPLATE` | scripts/update_notification_templates.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_DAY_PIPELINE_STATUSES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_DAY_PURPOSE` | backend/apps/admin_ui/services/detailization.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_DAY_REMINDER` | scripts/update_notification_templates.py | Назначение требует ручного ревью | Неочевидно |
| `INTRO_DAY_SCHEDULED` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `INTRO_REMIND_3H` | backend/apps/bot/reminders.py | Назначение требует ручного ревью | Неочевидно |
| `INVITED` | backend/domain/candidates/status.py | Назначение требует ручного ревью | Неочевидно |
| `JOURNEY_STATE_LABELS` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `KANBAN_ALLOWED_TARGET_STATUSES` | backend/apps/admin_ui/routers/api.py | Назначение требует ручного ревью | Неочевидно |
| `KANBAN_INCOMING_SOURCE_STATUSES` | frontend/app/src/app/routes/app/candidates.tsx | Назначение требует ручного ревью | Неочевидно |
| `KANBAN_MAIN_PIPELINE_STATUSES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `KB_INTERVIEW_SCRIPT_CATEGORIES` | backend/core/ai/llm_script_generator.py | Назначение требует ручного ревью | Неочевидно |
| `KIND_QUESTIONS_CHANGED` | backend/core/content_updates.py | Назначение требует ручного ревью | Неочевидно |
| `KIND_REMINDERS_CHANGED` | backend/core/content_updates.py | Назначение требует ручного ревью | Неочевидно |
| `KIND_TEMPLATES_CHANGED` | backend/core/content_updates.py | Назначение требует ручного ревью | Неочевидно |
| `KPI_NOW` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `LAST_ERROR_COLUMN` | backend/migrations/versions/0013_enhance_notification_logs.py | Назначение требует ручного ревью | Неочевидно |
| `LAST_NAMES` | frontend/app/src/app/routes/app/incoming-demo.ts | Назначение требует ручного ревью | Неочевидно |
| `LEAD` | backend/domain/candidates/status.py | Назначение требует ручного ревью | Неочевидно |
| `LEGACY_ADMIN_PRINCIPAL_ID` | backend/apps/admin_ui/security.py | Назначение требует ручного ревью | Неочевидно |
| `LEGACY_DEFAULT_DURATION` | backend/migrations/versions/0050_align_slot_overlap_bounds_and_duration_default.py | Назначение требует ручного ревью | Неочевидно |
| `LEGACY_KIND` | backend/migrations/versions/0024_remove_legacy_24h_reminders.py | Назначение требует ручного ревью | Неочевидно |
| `LEGACY_LOG_TYPE` | backend/migrations/versions/0024_remove_legacy_24h_reminders.py | Назначение требует ручного ревью | Неочевидно |
| `LEGACY_STATUS_MAP` | docs/archive/qa/CRITICAL_ISSUES.md | Назначение требует ручного ревью | Неочевидно |
| `LEGACY_TO_WORKFLOW` | backend/migrations/versions/0056_sync_workflow_status_from_legacy.py | Назначение требует ручного ревью | Неочевидно |
| `LIFECYCLE_ACTIVE` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `LIFECYCLE_ARCHIVED` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `LIFECYCLE_LABELS` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `LIMIT_VALUES` | frontend/app/src/app/routes/app/slots.filters.ts | Назначение требует ручного ревью | Неочевидно |
| `LINKED` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `LIQUID_GLASS_V2_DATASET_VALUE` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `LIQUID_GLASS_V2_OVERRIDE_KEY` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `LOCKS_INDEX` | backend/migrations/versions/0007_prevent_duplicate_slot_reservations.py | Назначение требует ручного ревью | Неочевидно |
| `LOCKS_TABLE` | backend/migrations/versions/0007_prevent_duplicate_slot_reservations.py | Назначение требует ручного ревью | Неочевидно |
| `LOG_DIR` | scripts/collect_ux.py | Назначение требует ручного ревью | Неочевидно |
| `LOG_FILE` | backend/core/settings.py, docs/archive/SERVER_STABILITY.md, tests/test_admin_candidate_chat_actions.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `LOG_JSON` | .env.local, .env.local.example, docs/archive/SERVER_STABILITY.md, docs/archive/qa/TEST_REPORT.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `LOG_LEVEL` | .env.local, .env.local.example, backend/core/settings.py, docs/archive/SERVER_STABILITY.md, docs/performance/results_20260301_go_gate.md, max_bot.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `LONG` | backend/core/cache.py | Назначение требует ручного ревью | Неочевидно |
| `MAX` | backend/core/messenger/protocol.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_API_BASE` | backend/core/messenger/max_adapter.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_ATTACHMENT_SIZE_MB` | backend/apps/admin_ui/services/staff_chat.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_ATTEMPTS` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_BOT_ENABLED` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `MAX_BOT_HOST` | max_bot.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_BOT_PORT` | max_bot.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_BOT_TOKEN` | .env.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `MAX_DAYS_AHEAD` | backend/apps/bot/slot_assignment_flow.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_INTRO_DAY_GROUP_ROUTES` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `MAX_INTRO_DAY_GROUP_ROUTES_ENV` | backend/apps/admin_ui/services/max_sales_handoff.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_INTRO_DAY_HANDOFF_ENABLED` | .env.example | Назначение требует ручного ревью | Неочевидно |
| `MAX_INTRO_DAY_HANDOFF_ENABLED_ENV` | backend/apps/admin_ui/services/max_sales_handoff.py | Назначение требует ручного ревью | Неочевидно |
| `MAX_WEBHOOK_SECRET` | .env.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `MAX_WEBHOOK_URL` | .env.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `MD_REPORT` | scripts/collect_ux.py | Назначение требует ручного ревью | Неочевидно |
| `MEDIUM` | backend/core/cache.py | Назначение требует ручного ревью | Неочевидно |
| `MESSAGE_LIMIT` | frontend/app/src/app/routes/app/messenger.tsx | Назначение требует ручного ревью | Неочевидно |
| `METRICS_ENABLED` | backend/apps/admin_ui/perf/metrics/db.py, backend/apps/admin_ui/perf/metrics/http.py, backend/apps/admin_ui/routers/metrics.py, docs/performance/loadtesting.md, docs/performance/metrics.md, docs/performance/overview.md… | Используется в нескольких runtime/test слоях | Неочевидно |
| `METRICS_IP_ALLOWLIST` | backend/apps/admin_ui/routers/metrics.py, tests/test_admin_surface_hardening.py, tests/test_perf_metrics_endpoint.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `METRIC_FIELDS` | scripts/loadtest_notifications.py | Назначение требует ручного ревью | Неочевидно |
| `MFQ` | frontend/app/package-lock.json | Назначение требует ручного ревью | Неочевидно |
| `MIGRATIONS_DATABASE_URL` | .env.example, docs/MIGRATIONS.md, docs/project/DEPLOYMENT_GUIDE.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `MIGRATIONS_PACKAGE` | backend/migrations/runner.py | Назначение требует ручного ревью | Неочевидно |
| `MINUTE_STEP` | backend/apps/bot/slot_assignment_flow.py | Назначение требует ручного ревью | Неочевидно |
| `MOBILE_PRIMARY_TABS` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `MOBILE_QUERY` | frontend/app/src/app/hooks/useIsMobile.ts | Назначение требует ручного ревью | Неочевидно |
| `MODE` | backend/apps/admin_ui/static/css/design-system.css | Назначение требует ручного ревью | Неочевидно |
| `MODULE_REQUIREMENTS` | scripts/dev_doctor.py | Назначение требует ручного ревью | Неочевидно |
| `MONTH_NAMES_SHORT` | backend/apps/bot/jinja_renderer.py | Назначение требует ручного ревью | Неочевидно |
| `MOTION` | backend/apps/admin_ui/static/css/design-system.css | Назначение требует ручного ревью | Неочевидно |
| `MSK` | tests/test_bulk_slots_timezone_moscow_novosibirsk.py, tests/test_recruiter_timezone_conversion.py, tests/test_slot_creation_timezone_validation.py, tests/test_slot_overlap_handling.py, tests/test_slot_timezone_moscow_novosibirsk.py, tests/test_slot_timezones.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `N8N_HH_RESOLVE_WEBHOOK_URL` | .env.example, backend/core/settings.py, backend/domain/hh_sync/worker.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `N8N_HH_SYNC_WEBHOOK_URL` | .env.example, backend/core/settings.py, backend/domain/hh_sync/worker.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `NEGATIVE_ARCHIVE_STATUSES` | backend/domain/candidates/journey.py | Назначение требует ручного ревью | Неочевидно |
| `NEW_INDEX` | backend/migrations/versions/0011_add_candidate_binding_to_notification_logs.py, backend/migrations/versions/0019_fix_notification_log_unique_index.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `NEW_INDEX_NAME` | backend/migrations/versions/0021_update_slot_unique_index_include_purpose.py | Назначение требует ручного ревью | Неочевидно |
| `NEXT_RETRY_COLUMN` | backend/migrations/versions/0013_enhance_notification_logs.py | Назначение требует ручного ревью | Неочевидно |
| `NONE` | backend/core/timezone_service.py | Назначение требует ручного ревью | Неочевидно |
| `NOTIFICATION_BROKER` | .claude/settings.local.json, .env.development.example, .env.example, .env.local, .env.local.example, backend/apps/admin_ui/state.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `NOTIFICATION_HEALTH_INTERVAL` | backend/apps/admin_ui/state.py | Назначение требует ручного ревью | Неочевидно |
| `NOTIFICATION_RETRY_BASE` | backend/apps/admin_ui/state.py | Назначение требует ручного ревью | Неочевидно |
| `NOTIFICATION_RETRY_MAX` | backend/apps/admin_ui/state.py | Назначение требует ручного ревью | Неочевидно |
| `NOT_HIRED` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `NO_SHOW` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `OFFERED` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `OFFER_ACCEPTED` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `OLD_CONSTRAINT` | backend/migrations/versions/0011_add_candidate_binding_to_notification_logs.py, backend/migrations/versions/0019_fix_notification_log_unique_index.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `OLD_INDEX_NAME` | backend/migrations/versions/0021_update_slot_unique_index_include_purpose.py | Назначение требует ручного ревью | Неочевидно |
| `ONBOARDING_DAY_CONFIRMED` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `ONBOARDING_DAY_SCHEDULED` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `OPENAI_API_KEY` | .env.example, .env.local, .env.local.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `OPENAI_BASE_URL` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `OPENAI_MODEL` | .env.example, .env.local, .env.local.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `OPENED` | backend/domain/candidates/models.py | Назначение требует ручного ревью | Неочевидно |
| `OUTBOUND` | backend/domain/candidates/models.py, backend/domain/hh_integration/contracts.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `OUTPUT_DIR` | tools/render_previews.py | Назначение требует ручного ревью | Неочевидно |
| `OVERLAP_CONSTRAINT` | backend/migrations/versions/0084_allow_intro_day_parallel_slots.py | Назначение требует ручного ревью | Неочевидно |
| `PALETTE` | backend/apps/admin_ui/static/css/design-system.css | Назначение требует ручного ревью | Неочевидно |
| `PANEL` | docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md | Назначение требует ручного ревью | Неочевидно |
| `PANEL_WIDTH_KEY` | frontend/app/src/app/components/InterviewScript/InterviewScript.tsx | Назначение требует ручного ревью | Неочевидно |
| `PASSED` | docs/archive/features/notifications/INTRO_DAY_NOTIFICATIONS_FIX.md | Назначение требует ручного ревью | Неочевидно |
| `PASS_THRESHOLD` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `PATH` | .claude/settings.local.json, docs/archive/SERVER_STABILITY.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `PBKDF2_ITERATIONS` | backend/core/passwords.py | Назначение требует ручного ревью | Неочевидно |
| `PENDING` | backend/domain/hh_integration/contracts.py, backend/domain/models.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `PERF_CACHE_BYPASS` | backend/apps/admin_ui/perf/cache/readthrough.py, docs/performance/caching.md, docs/performance/loadtesting.md, docs/performance/results_20260217.md, tests/services/test_dashboard_and_slots.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `PERF_CACHE_REFRESH_MAX_INFLIGHT` | backend/apps/admin_ui/perf/limits/refresh_limiter.py | Назначение требует ручного ревью | Неочевидно |
| `PERF_DIAGNOSTIC_HEADERS` | backend/apps/admin_ui/perf/metrics/http.py, docs/performance/loadtesting.md, docs/performance/metrics.md, docs/performance/overview.md, docs/performance/results_20260216.md, docs/performance/results_20260217.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `PER_PAGE_VALUES` | frontend/app/src/app/routes/app/slots.filters.ts | Назначение требует ручного ревью | Неочевидно |
| `PGPASSWORD` | .claude/settings.local.json | Назначение требует ручного ревью | Неочевидно |
| `PII_FIELDS` | backend/core/logging.py | Назначение требует ручного ревью | Неочевидно |
| `PIPELINE_STAGES` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `PKQ` | frontend/app/package-lock.json | Назначение требует ручного ревью | Неочевидно |
| `PLACEHOLDERS` | frontend/app/src/app/routes/app/template-edit.tsx, frontend/app/src/app/routes/app/template-new.tsx | Используется в нескольких runtime/test слоях | Неочевидно |
| `PLAN_ERROR_MESSAGE` | backend/apps/admin_ui/routers/cities.py | Назначение требует ручного ревью | Неочевидно |
| `PORT` | frontend/app/playwright.config.ts | Назначение требует ручного ревью | Неочевидно |
| `PRESET_LABELS` | backend/apps/admin_ui/services/message_templates_presets.py | Назначение требует ручного ревью | Неочевидно |
| `PROCESSED` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `PROD` | frontend/app/src/app/main.tsx | Назначение требует ручного ревью | Неочевидно |
| `PROFILE_PATH` | docs/performance/loadtesting.md | Назначение требует ручного ревью | Неочевидно |
| `PROJECT_ROOT` | backend/core/settings.py, scripts/export_interview_script_dataset.py, scripts/seed_message_templates.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `PROMPT_VERSION_INTERVIEW_SCRIPT` | backend/core/ai/llm_script_generator.py | Назначение требует ручного ревью | Неочевидно |
| `PURPOSE_FILTERS` | frontend/app/src/app/routes/app/slots.filters.ts | Назначение требует ручного ревью | Неочевидно |
| `PYTEST_CURRENT_TEST` | backend/apps/admin_ui/app.py, backend/apps/admin_ui/routers/slots.py, backend/apps/admin_ui/routers/system.py, backend/apps/admin_ui/state.py, backend/core/microcache.py, backend/domain/repositories.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `PYTHON` | docs/LOCAL_DEV.md | Назначение требует ручного ревью | Неочевидно |
| `PYTHONPATH` | .claude/settings.local.json, docs/archive/NOTIFICATIONS_E2E.md, docs/archive/NOTIFICATIONS_LOADTEST.md, docs/performance/loadtesting.md, frontend/app/playwright.config.ts, scripts/e2e_notifications_sandbox.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `PYTHON_BIN` | frontend/app/playwright.config.ts | Назначение требует ручного ревью | Неочевидно |
| `PYTHON_REQUIRED` | scripts/dev_doctor.py | Назначение требует ручного ревью | Неочевидно |
| `QUEUED` | backend/domain/candidates/models.py | Назначение требует ручного ревью | Неочевидно |
| `RATE_LIMIT_ENABLED` | .env.example, .env.local, .env.local.example, backend/apps/admin_ui/security.py, docs/performance/loadtesting.md, tests/test_admin_ui_auth_startup.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `RATE_LIMIT_REDIS_URL` | .env.local, .env.local.example, backend/core/settings.py, tests/conftest.py, tests/test_admin_ui_auth_startup.py, tests/test_rate_limiting.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `RECEIVED` | backend/domain/candidates/models.py, backend/domain/hh_integration/contracts.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `RECRUITER_CONTACTS` | scripts/update_notification_templates.py | Назначение требует ручного ревью | Неочевидно |
| `RECRUITER_DEFAULT_PASSWORD` | .env.example, .env.local, .env.local.example, backend/apps/admin_ui/services/recruiters.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `RECRUITER_EDITABLE_TEMPLATE_KEYS` | backend/apps/admin_ui/routers/content_api.py | Назначение требует ручного ревью | Неочевидно |
| `RECRUITER_NAMES` | frontend/app/src/app/routes/app/incoming-demo.ts | Назначение требует ручного ревью | Неочевидно |
| `RECRUITER_PASSWORD` | scripts/seed_auth_accounts.py | Назначение требует ручного ревью | Неочевидно |
| `REDIS_DB` | docs/archive/optimization/PHASE2_PERFORMANCE.md | Назначение требует ручного ревью | Неочевидно |
| `REDIS_HOST` | docs/archive/optimization/PHASE2_PERFORMANCE.md | Назначение требует ручного ревью | Неочевидно |
| `REDIS_MAX_CONNECTIONS` | docs/archive/optimization/PHASE2_PERFORMANCE.md | Назначение требует ручного ревью | Неочевидно |
| `REDIS_NOTIFICATIONS_URL` | .claude/settings.local.json | Назначение требует ручного ревью | Неочевидно |
| `REDIS_PASSWORD` | docs/archive/optimization/PHASE2_PERFORMANCE.md | Назначение требует ручного ревью | Неочевидно |
| `REDIS_PORT` | docs/archive/optimization/PHASE2_PERFORMANCE.md | Назначение требует ручного ревью | Неочевидно |
| `REDIS_URL` | .claude/settings.local.json, .env.development.example, .env.example, .env.local, .env.local.example, backend/core/settings.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `REJECT` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `REJECTED` | backend/domain/candidates/workflow.py, backend/domain/models.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `REJECTION_TEMPLATE_KEY` | backend/apps/admin_ui/services/slots.py, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `REMIND` | backend/apps/admin_ui/routers/slots.py | Назначение требует ручного ревью | Неочевидно |
| `REMINDER_POLICY_KEY` | backend/apps/bot/runtime_config.py | Назначение требует ручного ревью | Неочевидно |
| `REMIND_24H` | backend/apps/bot/reminders.py | Назначение требует ручного ревью | Неочевидно |
| `REMIND_2H` | backend/apps/bot/reminders.py | Назначение требует ручного ревью | Неочевидно |
| `REQUESTED_TIME_NOTES` | frontend/app/src/app/routes/app/incoming-demo.ts | Назначение требует ручного ревью | Неочевидно |
| `REQUIRED_ENUM_VALUES` | backend/migrations/versions/0036_ensure_candidate_status_enum_values.py, backend/migrations/versions/0044_add_lead_statuses_to_candidate_enum.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `RESCHEDULE_CONFIRMED` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `RESCHEDULE_MANUAL_PREFIX` | backend/apps/bot/slot_assignment_flow.py | Назначение требует ручного ревью | Неочевидно |
| `RESCHEDULE_PICK_PREFIX` | backend/apps/bot/slot_assignment_flow.py | Назначение требует ручного ревью | Неочевидно |
| `RESCHEDULE_REQUESTED` | backend/apps/bot/services.py, backend/domain/models.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `RESTART_LIMIT` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `RESTART_WINDOW_SECONDS` | scripts/dev_server.py | Назначение требует ручного ревью | Неочевидно |
| `REVOKED` | backend/domain/candidates/models.py, backend/domain/hh_integration/contracts.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `ROOT` | audit/collect_metrics.py, audit/generate_inventory.py, scripts/generate_waiting_candidates.py, tools/render_previews.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `RUNNING` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `SALT_BYTES` | backend/core/passwords.py | Назначение требует ручного ревью | Неочевидно |
| `SANDBOX_TEMPLATE_CANDIDATE` | scripts/e2e_notifications_sandbox.py | Назначение требует ручного ревью | Неочевидно |
| `SANDBOX_TEMPLATE_RECRUITER` | scripts/e2e_notifications_sandbox.py | Назначение требует ручного ревью | Неочевидно |
| `SCALE_LABELS` | frontend/app/src/app/components/InterviewScript/RatingScale.tsx | Назначение требует ручного ревью | Неочевидно |
| `SCENARIOS` | frontend/app/src/app/routes/app/simulator.tsx | Назначение требует ручного ревью | Неочевидно |
| `SCHEDULE_ONBOARDING` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `SECRET_KEY` | backend/core/settings.py, scripts/dev_doctor.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `SECURITY` | docs/QUALITY_SCORECARD.md | Назначение требует ручного ревью | Неочевидно |
| `SEND_TEST` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `SENT` | backend/domain/candidates/models.py | Назначение требует ручного ревью | Неочевидно |
| `SENTRY_AVAILABLE` | backend/apps/admin_ui/app.py | Назначение требует ручного ревью | Неочевидно |
| `SENTRY_DSN` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `SESSION_COOKIE_SAMESITE` | .env.local, .env.local.example, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `SESSION_COOKIE_SECURE` | .env.local, .env.local.example, docs/archive/qa/TEST_REPORT.md, tests/test_prod_config_simple.py, tests/test_session_cookie_config.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `SESSION_KEY` | backend/apps/admin_ui/security.py | Назначение требует ручного ревью | Неочевидно |
| `SESSION_SECRET` | .claude/settings.local.json, .env.example, .env.local, .env.local.example, backend/core/settings.py, docs/archive/SERVER_STABILITY.md… | Используется в нескольких runtime/test слоях | Неочевидно |
| `SESSION_SECRET_KEY` | codex/reports/run_log.md, docs/LOCAL_DEV.md, docs/project/CODEX.md, scripts/dev_doctor.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `SHORT` | backend/core/cache.py | Назначение требует ручного ревью | Неочевидно |
| `SHOW_UP` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `SIGNATURE_LENGTH` | backend/apps/bot/security.py | Назначение требует ручного ревью | Неочевидно |
| `SIMULATOR_ENABLED` | .env.example, .env.local.example, docs/SIMULATOR_RUNBOOK.md, tests/test_simulator_api.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `SLOTS_FILTERS_STORAGE_KEY` | frontend/app/src/app/routes/app/slots.filters.ts | Назначение требует ручного ревью | Неочевидно |
| `SLOT_BOOKED` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `SLOT_CONFIRMED` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `SLOT_MAX_DURATION_MIN` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `SLOT_MIN_DURATION_MIN` | backend/domain/models.py | Назначение требует ручного ревью | Неочевидно |
| `SLOT_PENDING` | backend/domain/candidates/status.py | Назначение требует ручного ревью | Неочевидно |
| `SLOT_PROPOSE_404_TOTAL` | backend/apps/admin_ui/perf/metrics/prometheus.py | Назначение требует ручного ревью | Неочевидно |
| `SLOT_STATUS_LABELS` | backend/apps/admin_ui/services/dashboard.py | Назначение требует ручного ревью | Неочевидно |
| `SLOW_QUERY_THRESHOLD_MS` | docs/archive/optimization/PHASE2_PERFORMANCE.md | Назначение требует ручного ревью | Неочевидно |
| `SMART_SERVICE_BLOCK_ORDER` | backend/core/ai/llm_script_generator.py | Назначение требует ручного ревью | Неочевидно |
| `SPA_DIST_DIR` | backend/apps/admin_ui/app.py, backend/apps/admin_ui/routers/dashboard.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `SPIKE_RPS` | docs/performance/loadtesting.md | Назначение требует ручного ревью | Неочевидно |
| `SPIKE_SECONDS` | docs/performance/loadtesting.md | Назначение требует ручного ревью | Неочевидно |
| `SPRING_FORWARD` | backend/core/timezone_service.py | Назначение требует ручного ревью | Неочевидно |
| `SQL_ECHO` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `STALE` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `STALLED_WAITING_SLOT` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `STATE` | docs/archive/DESIGN_SYSTEM_CANDIDATES_PAGE.md | Назначение требует ручного ревью | Неочевидно |
| `STATE_TTL_SECONDS` | backend/core/settings.py | Назначение требует ручного ревью | Неочевидно |
| `STATE_WAITING_DATETIME` | backend/apps/bot/slot_assignment_flow.py | Назначение требует ручного ревью | Неочевидно |
| `STATIC_DIR` | backend/apps/admin_ui/config.py | Назначение требует ручного ревью | Неочевидно |
| `STATUSES` | frontend/app/src/app/routes/app/incoming-demo.ts | Назначение требует ручного ревью | Неочевидно |
| `STATUS_COLOR_TO_CLASS` | backend/apps/admin_ui/services/dashboard.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_COLUMN` | backend/migrations/versions/0013_enhance_notification_logs.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_CONFIG` | backend/apps/admin_ui/services/calendar_events.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_FAIL` | scripts/formal_gate_sprint12.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_FILTERS` | backend/apps/admin_ui/utils.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_LABELS` | backend/apps/admin_ui/services/dashboard_calendar.py, docs/archive/features/dashboard/REAL_DATA_INTEGRATION_COMPLETE.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `STATUS_OPTIONS` | frontend/app/src/app/routes/app/candidates.tsx | Назначение требует ручного ревью | Неочевидно |
| `STATUS_PASS` | scripts/formal_gate_sprint12.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_PENDING` | scripts/formal_gate_sprint12.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_POOL` | scripts/seed_test_users.py | Назначение требует ручного ревью | Неочевидно |
| `STATUS_VARIANTS` | backend/apps/admin_ui/services/dashboard_calendar.py | Назначение требует ручного ревью | Неочевидно |
| `STEADY_RPS` | docs/performance/loadtesting.md | Назначение требует ручного ревью | Неочевидно |
| `STEADY_SECONDS` | docs/performance/loadtesting.md | Назначение требует ручного ревью | Неочевидно |
| `STORAGE_VERSION` | frontend/app/src/app/components/InterviewScript/useInterviewScript.ts | Назначение требует ручного ревью | Неочевидно |
| `STYLES` | backend/apps/admin_ui/static/css/design-system.css, frontend/app/src/theme/global.css | Используется в нескольких runtime/test слоях | Неочевидно |
| `SUCCESS_OUTCOMES` | backend/apps/admin_ui/services/kpis.py | Назначение требует ручного ревью | Неочевидно |
| `SYNCED` | backend/domain/hh_integration/contracts.py | Назначение требует ручного ревью | Неочевидно |
| `SYSTEM` | backend/apps/admin_ui/static/css/design-system.css, frontend/app/src/theme/global.css | Используется в нескольких runtime/test слоях | Неочевидно |
| `SYSTEM_PAYLOAD_KINDS` | backend/apps/admin_ui/services/chat_meta.py | Назначение требует ручного ревью | Неочевидно |
| `TABLE` | backend/migrations/versions/0018_slots_candidate_fields.py, backend/migrations/versions/0048_fix_test2_invites_timezone_columns.py, backend/migrations/versions/0049_allow_null_city_timezone.py, backend/migrations/versions/0050_align_slot_overlap_bounds_and_duration_default.py, backend/migrations/versions/0051_enforce_slot_overlap_on_10min_windows.py, backend/migrations/versions/0052_add_workflow_status_fields.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `TABLE_HISTORY` | backend/migrations/versions/0034_message_templates_city_support.py | Назначение требует ручного ревью | Неочевидно |
| `TABLE_INVITES` | backend/migrations/versions/0046_add_test2_invites_and_test_result_source.py | Назначение требует ручного ревью | Неочевидно |
| `TABLE_MESSAGE_TEMPLATES` | backend/migrations/versions/0014_notification_outbox_and_templates.py | Назначение требует ручного ревью | Неочевидно |
| `TABLE_NAME` | backend/migrations/versions/0008_add_slot_reminder_jobs.py, backend/migrations/versions/0011_add_candidate_binding_to_notification_logs.py, backend/migrations/versions/0012_update_slots_candidate_recruiter_index.py, backend/migrations/versions/0013_enhance_notification_logs.py, backend/migrations/versions/0015_recruiter_city_links.py, backend/migrations/versions/0019_fix_notification_log_unique_index.py… | Используется в нескольких runtime/test слоях | Неочевидно |
| `TABLE_NEW` | backend/migrations/versions/0034_message_templates_city_support.py | Назначение требует ручного ревью | Неочевидно |
| `TABLE_NOTIFICATION_LOGS` | backend/migrations/versions/0014_notification_outbox_and_templates.py | Назначение требует ручного ревью | Неочевидно |
| `TABLE_OLD` | backend/migrations/versions/0034_message_templates_city_support.py | Назначение требует ручного ревью | Неочевидно |
| `TABLE_OUTBOX` | backend/migrations/versions/0014_notification_outbox_and_templates.py | Назначение требует ручного ревью | Неочевидно |
| `TARGET_TOTALS` | docs/performance/loadtesting.md, docs/performance/results_20260216.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `TAU` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `TELEGRAM` | backend/core/messenger/protocol.py | Назначение требует ручного ревью | Неочевидно |
| `TEMPLATES_DIR` | backend/apps/admin_ui/config.py, backend/apps/bot/jinja_renderer.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEMPLATE_BODY` | backend/migrations/versions/0026_add_recruiter_candidate_confirmed_template.py | Назначение требует ручного ревью | Неочевидно |
| `TEMPLATE_GROUPS` | frontend/app/src/app/routes/app/template-edit.tsx, frontend/app/src/app/routes/app/template-new.tsx | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEMPLATE_KEY` | backend/migrations/versions/0026_add_recruiter_candidate_confirmed_template.py | Назначение требует ручного ревью | Неочевидно |
| `TEST1_COMPLETED` | backend/domain/analytics.py, backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEST1_KEYS_BY_ORDER` | backend/migrations/versions/0083_sync_test1_question_bank.py | Назначение требует ручного ревью | Неочевидно |
| `TEST1_OPTIONS_BY_ORDER` | backend/migrations/versions/0083_sync_test1_question_bank.py | Назначение требует ручного ревью | Неочевидно |
| `TEST1_QUESTIONS` | backend/apps/bot/config.py, tests/test_bot_questions_refresh.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEST1_STARTED` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `TEST2_COMPLETED` | backend/domain/analytics.py, backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEST2_FAILED` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEST2_QUESTIONS` | backend/apps/bot/config.py, tests/test_bot_questions_refresh.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEST2_SENT` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEST2_STARTED` | backend/domain/analytics.py | Назначение требует ручного ревью | Неочевидно |
| `TEST2_TOTAL_QUESTIONS` | backend/apps/admin_ui/services/candidates.py | Назначение требует ручного ревью | Неочевидно |
| `TESTING` | backend/domain/candidates/status.py | Назначение требует ручного ревью | Неочевидно |
| `TEST_DATABASE_URL` | .claude/settings.local.json, tests/conftest.py, tests/integration/test_migrations_postgres.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `TEST_LABELS` | backend/apps/admin_ui/services/questions.py | Назначение требует ручного ревью | Неочевидно |
| `TEST_SENT` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `TEXT_TEMPLATE` | frontend/app/src/app/components/QuestionPayloadEditor.tsx | Назначение требует ручного ревью | Неочевидно |
| `TG_BASE` | scripts/seed_test_candidates.py | Назначение требует ручного ревью | Неочевидно |
| `THREAD_LIMIT` | frontend/app/src/app/routes/app/messenger.tsx | Назначение требует ручного ревью | Неочевидно |
| `TIME_FMT` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `TIME_LIMIT` | backend/apps/bot/config.py | Назначение требует ручного ревью | Неочевидно |
| `TOTAL_CANDIDATES` | scripts/seed_test_candidates.py | Назначение требует ручного ревью | Неочевидно |
| `TOTAL_RPS` | docs/performance/loadtesting.md | Назначение требует ручного ревью | Неочевидно |
| `TRUST_PROXY_HEADERS` | .env.local, .env.local.example, tests/test_perf_metrics_endpoint.py, tests/test_rate_limiting.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `TZ` | backend/apps/admin_ui/services/kpis.py, backend/core/settings.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `TZ_COLUMNS` | backend/migrations/versions/0048_fix_test2_invites_timezone_columns.py | Назначение требует ручного ревью | Неочевидно |
| `TZ_DISPLAY_NAMES` | backend/apps/bot/jinja_renderer.py | Назначение требует ручного ревью | Неочевидно |
| `UI_UX` | docs/QUALITY_SCORECARD.md | Назначение требует ручного ревью | Неочевидно |
| `UNIQUE_INDEX_NAME` | backend/migrations/versions/0007_prevent_duplicate_slot_reservations.py | Назначение требует ручного ревью | Неочевидно |
| `UNIVERSAL_TEST2_ACTION` | backend/domain/candidates/actions.py | Назначение требует ручного ревью | Неочевидно |
| `UPDATED_BY` | scripts/seed_message_templates.py | Назначение требует ручного ревью | Неочевидно |
| `URL_RE` | frontend/app/src/app/routes/app/messenger.tsx | Назначение требует ручного ревью | Неочевидно |
| `USER_ID` | tests/test_bot_manual_contact.py, tests/test_bot_test1_validation.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `UTC` | tests/test_admin_candidate_schedule_slot.py, tests/test_recruiter_timezone_conversion.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `UVICORN_RELOAD` | backend/apps/admin_ui/state.py | Назначение требует ручного ревью | Неочевидно |
| `VERSION_COLUMN` | backend/migrations/runner.py | Назначение требует ручного ревью | Неочевидно |
| `VERSION_TABLE` | backend/migrations/runner.py | Назначение требует ручного ревью | Неочевидно |
| `VERY_LONG` | backend/core/cache.py | Назначение требует ручного ревью | Неочевидно |
| `VITE_INCOMING_DEMO_COUNT` | frontend/app/src/app/routes/app/dashboard.tsx, frontend/app/src/app/routes/app/incoming.tsx | Используется в нескольких runtime/test слоях | Неочевидно |
| `VITE_LIQUID_GLASS_V2` | frontend/app/src/app/routes/__root.tsx | Назначение требует ручного ревью | Неочевидно |
| `VITE_SIMULATOR_ENABLED` | docs/SIMULATOR_RUNBOOK.md, frontend/app/src/app/routes/__root.tsx, frontend/app/src/app/routes/app/simulator.tsx | Используется в нескольких runtime/test слоях | Неочевидно |
| `VQA` | frontend/app/package-lock.json | Назначение требует ручного ревью | Неочевидно |
| `WAITING_CANDIDATES_DEFAULT_LIMIT` | backend/apps/admin_ui/services/dashboard.py | Назначение требует ручного ревью | Неочевидно |
| `WAITING_CANDIDATES_MAX_LIMIT` | backend/apps/admin_ui/services/dashboard.py | Назначение требует ручного ревью | Неочевидно |
| `WAITING_FOR_SLOT` | backend/domain/candidates/workflow.py | Назначение требует ручного ревью | Неочевидно |
| `WAITING_SLOT` | backend/domain/candidates/status.py, docs/archive/SLOTS_V2_SOURCE_OF_TRUTH.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `WEB_CONCURRENCY` | .env.example, docs/performance/loadtesting.md, docs/project/DEPLOYMENT_GUIDE.md | Используется в нескольких runtime/test слоях | Неочевидно |
| `WEEKDAY_LABELS` | backend/apps/admin_ui/services/dashboard_calendar.py | Назначение требует ручного ревью | Неочевидно |
| `WITH` | backend/migrations/versions/0041_add_slot_overlap_exclusion_constraint.py, backend/migrations/versions/0050_align_slot_overlap_bounds_and_duration_default.py, backend/migrations/versions/0051_enforce_slot_overlap_on_10min_windows.py, backend/migrations/versions/0080_slot_overlap_per_purpose.py, backend/migrations/versions/0084_allow_intro_day_parallel_slots.py | Используется в нескольких runtime/test слоях | Неочевидно |
| `WORKDAY_END` | backend/apps/bot/slot_assignment_flow.py | Назначение требует ручного ревью | Неочевидно |
| `WORKDAY_START` | backend/apps/bot/slot_assignment_flow.py | Назначение требует ручного ревью | Неочевидно |
| `Z5A` | frontend/app/package-lock.json | Назначение требует ручного ревью | Неочевидно |

### Ключи по `.env*` файлам

- `.env.development.example`: `ENVIRONMENT`, `REDIS_URL`, `NOTIFICATION_BROKER`
- `.env.example`: `ENVIRONMENT`, `DATABASE_URL`, `MIGRATIONS_DATABASE_URL`, `DATA_DIR`, `SESSION_SECRET`, `ADMIN_USER`, `ADMIN_PASSWORD`, `RECRUITER_DEFAULT_PASSWORD`, `ACCESS_TOKEN_TTL_HOURS`, `BOT_ENABLED`, `BOT_INTEGRATION_ENABLED`, `BOT_TOKEN`, `BOT_BACKEND_URL`, `CRM_PUBLIC_URL`, `BOT_CALLBACK_SECRET`, `NOTIFICATION_BROKER`, `REDIS_URL`, `BOT_AUTOSTART`, `BOT_FAILFAST`, `ENABLE_LEGACY_STATUS_API`, `SIMULATOR_ENABLED`, `RATE_LIMIT_ENABLED`, `WEB_CONCURRENCY`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `HTTP_REQUEST_LOG_ENABLED`, `HTTP_SLOW_REQUEST_MS`, `AI_ENABLED`, `AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_TIMEOUT_SECONDS`, `AI_MAX_TOKENS`, `AI_PII_MODE`, `AI_INTERVIEW_SCRIPT_TIMEOUT_SECONDS`, `AI_INTERVIEW_SCRIPT_MAX_TOKENS`, `AI_INTERVIEW_SCRIPT_CACHE_TTL_HOURS`, `AI_INTERVIEW_SCRIPT_FT_MODEL`, `AI_INTERVIEW_SCRIPT_AB_PERCENT`, `AI_INTERVIEW_SCRIPT_FT_MIN_SAMPLES`, `AI_INTERVIEW_SCRIPT_PII_MODE`, `HH_SYNC_ENABLED`, `N8N_HH_SYNC_WEBHOOK_URL`, `N8N_HH_RESOLVE_WEBHOOK_URL`, `HH_WEBHOOK_SECRET`, `HH_INTEGRATION_ENABLED`, `HH_API_BASE_URL`, `HH_OAUTH_AUTHORIZE_URL`, `HH_CLIENT_ID`, `HH_CLIENT_SECRET`, `HH_REDIRECT_URI`, `HH_USER_AGENT`, `HH_OAUTH_STATE_TTL_SECONDS`, `HH_WEBHOOK_BASE_URL`, `MAX_BOT_ENABLED`, `MAX_BOT_TOKEN`, `MAX_WEBHOOK_URL`, `MAX_WEBHOOK_SECRET`, `MAX_INTRO_DAY_HANDOFF_ENABLED`, `MAX_INTRO_DAY_GROUP_ROUTES`
- `.env.local`: `ENVIRONMENT`, `DATABASE_URL`, `REDIS_URL`, `NOTIFICATION_BROKER`, `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REDIS_URL`, `TRUST_PROXY_HEADERS`, `ADMIN_USER`, `ADMIN_PASSWORD`, `RECRUITER_DEFAULT_PASSWORD`, `SESSION_SECRET`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `BOT_ENABLED`, `BOT_TOKEN`, `BOT_BACKEND_URL`, `CRM_PUBLIC_URL`, `BOT_CALLBACK_SECRET`, `BOT_AUTOSTART`, `DATA_DIR`, `LOG_LEVEL`, `LOG_JSON`, `BOT_INTEGRATION_ENABLED`, `AI_INTERVIEW_SCRIPT_TIMEOUT_SECONDS`, `AI_INTERVIEW_SCRIPT_MAX_TOKENS`, `AI_ENABLED`, `AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- `.env.local.example`: `ENVIRONMENT`, `DATABASE_URL`, `REDIS_URL`, `NOTIFICATION_BROKER`, `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REDIS_URL`, `TRUST_PROXY_HEADERS`, `ADMIN_USER`, `ADMIN_PASSWORD`, `RECRUITER_DEFAULT_PASSWORD`, `ACCESS_TOKEN_TTL_HOURS`, `ALLOW_DEV_AUTOADMIN`, `SESSION_SECRET`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `BOT_ENABLED`, `BOT_TOKEN`, `BOT_BACKEND_URL`, `CRM_PUBLIC_URL`, `BOT_CALLBACK_SECRET`, `BOT_AUTOSTART`, `DATA_DIR`, `LOG_LEVEL`, `LOG_JSON`, `AI_ENABLED`, `AI_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_TIMEOUT_SECONDS`, `AI_MAX_TOKENS`, `AI_PII_MODE`, `AI_INTERVIEW_SCRIPT_TIMEOUT_SECONDS`, `AI_INTERVIEW_SCRIPT_MAX_TOKENS`, `AI_INTERVIEW_SCRIPT_CACHE_TTL_HOURS`, `AI_INTERVIEW_SCRIPT_FT_MODEL`, `AI_INTERVIEW_SCRIPT_AB_PERCENT`, `AI_INTERVIEW_SCRIPT_FT_MIN_SAMPLES`, `AI_INTERVIEW_SCRIPT_PII_MODE`, `SIMULATOR_ENABLED`