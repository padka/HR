import type { InterviewScriptPayload, TestSection } from '@/api/services/candidates'

export type InterviewScriptQuestionView = {
  id: string
  text: string
  type: 'personalized' | 'standard'
  source?: string | null
  why: string
  goodAnswer: string
  redFlags: string
  estimatedMinutes: number
}

export type InterviewScriptViewModel = {
  title: string
  goal: string
  briefingFocusAreas: string[]
  briefingFlags: string[]
  greeting: string
  icebreakers: string[]
  questions: InterviewScriptQuestionView[]
  closingChecklist: string[]
  closingPhrase: string
  rawScript: InterviewScriptPayload
}

export type InterviewScriptStep =
  | { id: 'briefing'; label: string; kind: 'briefing' }
  | { id: 'opening'; label: string; kind: 'opening' }
  | { id: string; label: string; kind: 'question'; questionId: string }
  | { id: 'closing'; label: string; kind: 'closing' }
  | { id: 'scorecard'; label: string; kind: 'scorecard' }

export type InterviewScriptQuestionState = {
  notes: string
  rating: number | null
  skipped: boolean
}

export type InterviewScriptDraft = {
  script: InterviewScriptPayload
  viewModel: InterviewScriptViewModel
  currentStep: number
  startedAt: number
  savedAt?: string | null
  questionState: Record<string, InterviewScriptQuestionState>
  overallRecommendation: 'recommend' | 'doubt' | 'not_recommend'
  finalComment: string
}

export type InterviewScriptBaseContext = {
  candidateName: string
  statusLabel: string
  test1Section?: TestSection | null
}
