import type {
  AISummary,
  AISummaryResponse,
  CandidateDetail,
  CityOption,
} from '@/api/services/candidates'
import type {
  CandidateChatMessage,
  CandidateChatPayload,
  CandidateChatTemplate,
  CandidateChatThread,
  CandidateChatThreadsPayload,
  CandidateChatWorkspaceState,
} from '@/api/services/messenger'

export type {
  AISummary,
  AISummaryResponse,
  CandidateChatMessage,
  CandidateChatPayload,
  CandidateChatTemplate,
  CandidateChatThread,
  CandidateChatThreadsPayload,
  CandidateChatWorkspaceState,
  CandidateDetail,
  CityOption,
}

export type ThreadTone = 'neutral' | 'info' | 'warning' | 'danger' | 'success'

export type NextAction = {
  label: string
  reason: string
  outcome: string
  tone: ThreadTone
  ctaKind: 'none' | 'profile' | 'intro_day' | 'archive'
  ctaLabel?: string | null
}

export type IntroDayTemplateContext = NonNullable<CandidateDetail['intro_day_template_context']>

export type JourneyStep = {
  key: string
  label: string
  state: 'passed' | 'active' | 'pending' | 'declined'
  headline: string
  detailLines: string[]
  nextHint: string
}

export type GroupedMessageRow =
  | { type: 'divider'; key: string; label: string }
  | { type: 'message'; message: CandidateChatMessage; unreadAnchor: boolean }

export type ToastState = {
  tone: 'success' | 'error'
  message: string
}
