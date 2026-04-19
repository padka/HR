import type {
  AICoach,
  AICoachResponse,
  AIDraftItem,
  AIDraftsResponse,
  AIScorecard,
  AIScorecardMetricItem,
  AISummary,
  AISummaryResponse,
  CandidateAction,
  CandidateArchive,
  CandidateCohortComparison,
  CandidateDetail,
  CandidateFinalOutcome,
  CandidateHHSummary,
  CandidateMaxLaunchInviteResponse,
  CandidateMaxRollout,
  CandidateJourney,
  CandidatePendingSlotRequest,
  CandidateSlot,
  CandidateTimelineEntry,
  ChatPayload,
  CityOption,
  TestAttempt,
  TestSection,
} from '@/api/services/candidates'
import type { PipelineStage as CandidatePipelineStageData } from '@/app/components/CandidatePipeline/pipeline.types'
import type { TimelineEvent as CandidateTimelineEvent } from '@/app/components/CandidateTimeline/timeline.types'

export type {
  AICoach,
  AICoachResponse,
  AIDraftItem,
  AIDraftsResponse,
  AIScorecard,
  AIScorecardMetricItem,
  AISummary,
  AISummaryResponse,
  CandidateAction,
  CandidateArchive,
  CandidateCohortComparison,
  CandidateDetail,
  CandidateFinalOutcome,
  CandidateHHSummary,
  CandidateMaxLaunchInviteResponse,
  CandidateMaxRollout,
  CandidateJourney,
  CandidatePendingSlotRequest,
  CandidateSlot,
  CandidateTimelineEntry,
  ChatPayload,
  TestAttempt,
  TestSection,
}

export type City = CityOption
export type IntroDayTemplateContext = NonNullable<CandidateDetail['intro_day_template_context']>
export type JourneyEventRecord = NonNullable<CandidateJourney['events']>[number]
export type CandidatePipelineStage = CandidatePipelineStageData
export type CandidateDrawerTimelineEvent = CandidateTimelineEvent

export type FunnelStageKey = 'lead' | 'slot' | 'interview' | 'test2' | 'intro_day' | 'outcome'
export type FunnelTone = 'accent' | 'success' | 'warning' | 'danger' | 'muted'

export type FunnelStageItem = {
  key: FunnelStageKey
  label: string
  state: string
  stateLabel: string
  tone: FunnelTone
  summary: string
  note?: string | null
  events: JourneyEventRecord[]
}

export type ReportPreviewState = {
  title: string
  url: string
}

export type TestAttemptPreview = {
  testTitle: string
  attempt: TestAttempt
}

export type MaxRolloutPreviewState = {
  title: string
  rollout: CandidateMaxRollout
}

export type MaxRolloutResultState = {
  title: string
  ok: boolean
  message?: string | null
  response?: CandidateMaxLaunchInviteResponse | null
}

export type RejectState = {
  actionKey: string
  title?: string
}

export type StatusDisplay = {
  label: string
  tone: string
}
