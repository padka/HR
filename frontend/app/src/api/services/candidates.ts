import { apiFetch } from '@/api/client'

export type CityOption = {
  id: number
  name: string
  tz?: string | null
}

export type CandidateAction = {
  key: string
  label: string
  url?: string | null
  method?: string
  icon?: string | null
  variant?: string | null
  confirmation?: string | null
  target_status?: string | null
  requires_test2_passed?: boolean
  requires_slot?: boolean
}

export type CandidateSlot = {
  id: number
  status?: string | null
  purpose?: string | null
  start_utc?: string | null
  recruiter_name?: string | null
  city_name?: string | null
  candidate_tz?: string | null
}

export type CandidateMaxLinkPayload = {
  public_link: string
  invite_token: string
  deep_link: string
  mini_app_link?: string | null
}

export type TestQuestionAnswer = {
  question_index?: number
  question_text?: string | null
  user_answer?: string | null
  correct_answer?: string | null
  attempts_count?: number | null
  time_spent?: number | null
  is_correct?: boolean | null
  overtime?: boolean | null
}

export type TestStats = {
  total_questions?: number
  correct_answers?: number
  overtime_questions?: number
  raw_score?: number
  final_score?: number
  total_time?: number
}

export type TestAttempt = {
  id: number
  completed_at?: string | null
  raw_score?: number
  final_score?: number
  source?: string
  details?: {
    stats?: TestStats
    questions?: TestQuestionAnswer[]
  }
}

export type TestSection = {
  key: string
  title: string
  status?: string
  status_label?: string
  summary?: string
  completed_at?: string | null
  pending_since?: string | null
  report_url?: string | null
  details?: {
    stats?: TestStats
    questions?: TestQuestionAnswer[]
  }
  history?: TestAttempt[]
}

export type CandidateDetail = {
  id: number
  created_at?: string | null
  fio?: string | null
  city?: string | null
  telegram_id?: number | null
  telegram_username?: string | null
  hh_profile_url?: string | null
  hh_resume_id?: string | null
  hh_negotiation_id?: string | null
  hh_vacancy_id?: string | null
  hh_sync_status?: string | null
  hh_sync_error?: string | null
  messenger_platform?: string | null
  max_user_id?: string | null
  phone?: string | null
  is_active?: boolean
  stage?: string | null
  workflow_status?: string | null
  workflow_status_label?: string | null
  workflow_status_color?: string | null
  candidate_status_display?: string | null
  candidate_status_slug?: string | null
  candidate_status_color?: string | null
  telemost_url?: string | null
  telemost_source?: string | null
  responsible_recruiter?: { id?: number | null; name?: string | null } | null
  reschedule_request?: {
    requested_at?: string | null
    requested_start_utc?: string | null
    requested_end_utc?: string | null
    requested_tz?: string | null
    candidate_comment?: string | null
    source?: string | null
  } | null
  candidate_actions?: CandidateAction[]
  allowed_next_statuses?: Array<{ slug: string; label: string; color?: string; is_terminal?: boolean }>
  pipeline_stages?: Array<{ key: string; label: string; state?: string }>
  status_is_terminal?: boolean
  needs_intro_day?: boolean
  can_schedule_intro_day?: boolean
  candidate_status_options?: Array<{ slug: string; label: string }>
  legacy_status_enabled?: boolean
  slots?: CandidateSlot[]
  journey?: CandidateJourney | null
  archive?: CandidateArchive | null
  final_outcome?: CandidateFinalOutcome | null
  final_outcome_reason?: string | null
  pending_slot_request?: CandidatePendingSlotRequest | null
  manual_mode?: boolean
  test_sections?: TestSection[]
  test_results?: Record<string, TestSection>
  timeline?: CandidateTimelineEntry[]
  stats?: { tests_total?: number; average_score?: number | null }
  intro_day_template?: string | null
  intro_day_template_context?: {
    city_name?: string | null
    intro_address?: string | null
    address?: string | null
    city_address?: string | null
    intro_contact?: string | null
    recruiter_contact?: string | null
    contact_name?: string | null
    contact_phone?: string | null
  } | null
}

export type CandidateFinalOutcome = 'attached' | 'not_attached' | 'not_counted'

export type CandidateArchive = {
  state?: 'archived'
  label?: string | null
  stage?: string | null
  stage_label?: string | null
  reason?: string | null
  archived_at?: string | null
}

export type CandidatePendingSlotRequest = {
  requested?: boolean
  requested_at?: string | null
  requested_start_utc?: string | null
  requested_end_utc?: string | null
  requested_tz?: string | null
  candidate_comment?: string | null
  source?: string | null
}

export type CandidateJourneyEvent = {
  id: number
  event_key?: string | null
  stage?: string | null
  status_slug?: string | null
  actor_type?: string | null
  actor_id?: number | null
  summary?: string | null
  payload?: Record<string, unknown> | null
  created_at?: string | null
}

export type CandidateJourney = {
  state?: string | null
  state_label?: string | null
  lifecycle_state?: string | null
  lifecycle_label?: string | null
  archive?: CandidateArchive | null
  final_outcome?: CandidateFinalOutcome | null
  final_outcome_label?: string | null
  final_outcome_reason?: string | null
  manual_mode?: boolean
  pending_slot_request?: CandidatePendingSlotRequest | null
  current_owner?: { type?: string | null; id?: number | null; name?: string | null } | null
  next_slot_at?: string | null
  events?: CandidateJourneyEvent[]
}

export type CandidateTimelineEntry = {
  kind?: 'journey' | 'slot' | 'test' | 'message' | 'interview_feedback'
  dt?: string | null
  event_key?: string | null
  status?: string | null
  summary?: string | null
  rating?: string | null
  score?: number | null
  test_key?: string | null
  recruiter?: string | null
  city?: string | null
  send_time?: string | null
  text?: string | null
  is_active?: boolean
  outcome?: string | null
  outcome_reason?: string | null
  scorecard?: Record<string, unknown> | null
  payload?: Record<string, unknown> | null
}

export type ChatMessage = {
  id: number
  direction: string
  text: string
  status?: string
  created_at: string
  author?: string | null
  can_retry?: boolean
}

export type ChatPayload = {
  messages: ChatMessage[]
  has_more: boolean
  latest_message_at?: string | null
  updated?: boolean
}

export type CandidateHHSummary = {
  linked: boolean
  source: 'hh'
  sync_status?: string | null
  sync_error?: string | null
  last_hh_sync_at?: string | null
  resume?: {
    id?: string | null
    url?: string | null
    title?: string | null
    source_updated_at?: string | null
    fetched_at?: string | null
  }
  vacancy?: {
    id?: string | null
    title?: string | null
    url?: string | null
    last_hh_sync_at?: string | null
    area_name?: string | null
  }
  negotiation?: {
    id?: string | null
    collection_name?: string | null
    employer_state?: string | null
    applicant_state?: string | null
    last_hh_sync_at?: string | null
  }
  available_actions?: Array<{
    id?: string | null
    name?: string | null
    method?: string | null
    enabled?: boolean
    hidden?: boolean
    resulting_employer_state?: {
      id?: string | null
      name?: string | null
    }
  }>
  recent_jobs?: Array<{
    id: number
    job_type: string
    status: string
    attempts: number
    last_error?: string | null
    created_at?: string | null
    finished_at?: string | null
  }>
}

export type AIRiskItem = {
  key: string
  severity: 'low' | 'medium' | 'high'
  label: string
  explanation: string
}

export type AINextActionItem = {
  key: string
  label: string
  rationale: string
  cta?: string | null
}

export type AIFit = {
  score?: number | null
  level?: 'high' | 'medium' | 'low' | 'unknown'
  rationale?: string
  criteria_used?: boolean
}

export type AIEvidenceItem = {
  key: string
  label: string
  evidence: string
}

export type AICriterionChecklistItem = {
  key: string
  status: 'met' | 'not_met' | 'unknown'
  label: string
  evidence: string
}

export type AIScorecardMetricItem = {
  key: string
  label: string
  score?: number | null
  weight?: number | null
  status: 'met' | 'not_met' | 'unknown'
  evidence: string
}

export type AIScorecardFlagItem = {
  key: string
  label: string
  evidence: string
}

export type AIScorecard = {
  final_score?: number | null
  objective_score?: number | null
  semantic_score?: number | null
  recommendation?: 'od_recommended' | 'clarify_before_od' | 'not_recommended'
  metrics?: AIScorecardMetricItem[]
  blockers?: AIScorecardFlagItem[]
  missing_data?: AIScorecardFlagItem[]
}

export type AIVacancyFitEvidence = {
  factor: string
  assessment: 'positive' | 'negative' | 'neutral' | 'unknown'
  detail: string
}

export type AIVacancyFit = {
  score?: number | null
  level: 'high' | 'medium' | 'low' | 'unknown'
  summary: string
  evidence?: AIVacancyFitEvidence[]
  criteria_source?: string
}

export type AISummary = {
  tldr: string
  fit?: AIFit | null
  vacancy_fit?: AIVacancyFit | null
  strengths?: AIEvidenceItem[]
  weaknesses?: AIEvidenceItem[]
  criteria_checklist?: AICriterionChecklistItem[]
  test_insights?: string | null
  risks?: AIRiskItem[]
  next_actions?: AINextActionItem[]
  notes?: string | null
  scorecard?: AIScorecard | null
}

export type AISummaryResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  summary: AISummary
}

export type AIDraftItem = {
  text: string
  reason: string
}

export type AIDraftsResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  analysis?: string | null
  drafts: AIDraftItem[]
  used_context?: Record<string, unknown>
}

export type AICoach = {
  relevance_score?: number | null
  relevance_level?: 'high' | 'medium' | 'low' | 'unknown'
  rationale?: string
  criteria_used?: boolean
  strengths?: AIEvidenceItem[]
  risks?: AIRiskItem[]
  interview_questions?: string[]
  next_best_action?: string
  message_drafts?: AIDraftItem[]
}

export type AICoachResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  coach: AICoach
}

export type CandidateAiResumeUpsertResponse = {
  ok: boolean
  normalized_resume?: Record<string, unknown>
  content_hash?: string
  updated_at?: string
}

export type InterviewRiskFlag = {
  code: string
  severity: 'low' | 'medium' | 'high'
  reason: string
  question: string
  recommended_phrase: string
}

export type InterviewScriptIfAnswer = {
  pattern: string
  hint: string
}

export type InterviewScriptBlock = {
  id: string
  title: string
  goal: string
  recruiter_text: string
  candidate_questions: string[]
  if_answers: InterviewScriptIfAnswer[]
}

export type InterviewObjection = {
  topic: string
  candidate_says: string
  recruiter_answer: string
}

export type InterviewCtaTemplate = {
  type: string
  text: string
}

export type InterviewScriptPayload = {
  stage_label: string
  call_goal: string
  conversation_script: string
  risk_flags: InterviewRiskFlag[]
  highlights: string[]
  checks: string[]
  objections: InterviewObjection[]
  script_blocks: InterviewScriptBlock[]
  cta_templates: InterviewCtaTemplate[]
  briefing?: {
    goal?: string
    focus_areas?: string[]
    key_flags?: string[]
  } | null
  opening?: {
    greeting?: string
    icebreakers?: string[]
  } | null
  questions?: Array<{
    id: string
    text: string
    type: 'personalized' | 'standard'
    source?: string | null
    why: string
    good_answer: string
    red_flags: string
    estimated_minutes: number
  }>
  closing_checklist?: string[]
  closing_phrase?: string
}

export type InterviewScriptResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  generated_at?: string | null
  model?: string | null
  prompt_version?: string | null
  script: InterviewScriptPayload
}

export type InterviewScriptFeedbackPayload = {
  helped?: boolean | null
  edited: boolean
  quick_reasons: string[]
  final_script?: InterviewScriptPayload | null
  outcome: 'od_assigned' | 'showed_up' | 'no_show' | 'decline' | 'unknown'
  outcome_reason?: string | null
  scorecard?: {
    completed_questions: number
    total_questions: number
    average_rating?: number | null
    overall_recommendation: 'recommend' | 'doubt' | 'not_recommend'
    final_comment?: string | null
    timer_elapsed_sec: number
    items: Array<{
      question_id: string
      rating?: number | null
      skipped: boolean
      notes?: string | null
    }>
  } | null
  idempotency_key: string
}

export type CandidateCohortComparison = {
  available?: boolean
  cohort_label?: string | null
  total_candidates?: number
  rank?: number | null
  test1?: {
    candidate?: number | null
    average?: number | null
  } | null
  completion_time_sec?: {
    candidate?: number | null
    average?: number | null
  } | null
  stage_distribution?: Array<{
    key: string
    label: string
    count: number
  }>
}

export function fetchCities() {
  return apiFetch<CityOption[]>('/cities')
}

export function fetchCandidateDetail(candidateId: number) {
  return apiFetch<CandidateDetail>(`/candidates/${candidateId}`)
}

export function fetchCandidateHHSummary(candidateId: number) {
  return apiFetch<CandidateHHSummary>(`/candidates/${candidateId}/hh`)
}

export function fetchCandidateCohortComparison(candidateId: number) {
  return apiFetch<CandidateCohortComparison>(`/candidates/${candidateId}/cohort-comparison`)
}

export function fetchCandidateChat(candidateId: number, limit = 50) {
  return apiFetch<ChatPayload>(`/candidates/${candidateId}/chat?limit=${limit}`)
}

export function waitForCandidateChat(
  candidateId: number,
  params?: { since?: string | null; timeout?: number; limit?: number; signal?: AbortSignal },
) {
  const query = new URLSearchParams()
  if (params?.since) query.set('since', params.since)
  if (params?.timeout) query.set('timeout', String(params.timeout))
  if (params?.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiFetch<ChatPayload>(`/candidates/${candidateId}/chat/updates${suffix}`, {
    signal: params?.signal,
  })
}

export function sendCandidateChatMessage(candidateId: number, text: string, clientRequestId: string) {
  return apiFetch(`/candidates/${candidateId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ text, client_request_id: clientRequestId }),
  })
}

export function markCandidateChatRead(candidateId: number) {
  return apiFetch(`/candidate-chat/threads/${candidateId}/read`, {
    method: 'POST',
  })
}

export function createCandidateMaxLink(candidateId: number) {
  return apiFetch<CandidateMaxLinkPayload>(`/candidates/${candidateId}/channels/max-link`, {
    method: 'POST',
  })
}

export function scheduleCandidateSlot(candidateId: number, slotId: number) {
  return apiFetch(`/candidates/${candidateId}/schedule-slot`, {
    method: 'POST',
    body: JSON.stringify({ slot_id: slotId }),
  })
}

export function scheduleCandidateInterview(
  candidateId: number,
  payload: { city_id?: number | null; date: string; time: string; custom_message?: string | null; mode?: 'bot' | 'manual_silent' },
) {
  return apiFetch(`/candidates/${candidateId}/schedule-slot`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function scheduleCandidateIntroDay(
  candidateId: number,
  payload: { date: string; time: string; city_id?: number | null; custom_message?: string | null },
) {
  return apiFetch(`/candidates/${candidateId}/schedule-intro-day`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function applyCandidateAction(candidateId: number, actionKey: string, payload?: unknown) {
  return apiFetch(`/candidates/${candidateId}/actions/${actionKey}`, {
    method: 'POST',
    body: payload ? JSON.stringify(payload) : undefined,
  })
}

export function fetchCandidateInterviewScript(candidateId: number) {
  return apiFetch<InterviewScriptResponse>(`/ai/candidates/${candidateId}/interview-script`)
}

export function refreshCandidateInterviewScript(candidateId: number) {
  return apiFetch<InterviewScriptResponse>(`/ai/candidates/${candidateId}/interview-script/refresh`, { method: 'POST' })
}

export function submitCandidateInterviewScriptFeedback(candidateId: number, payload: InterviewScriptFeedbackPayload) {
  return apiFetch(`/ai/candidates/${candidateId}/interview-script/feedback`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchCandidateAiSummary(candidateId: number) {
  return apiFetch<AISummaryResponse>(`/ai/candidates/${candidateId}/summary`)
}

export function refreshCandidateAiSummary(candidateId: number) {
  return apiFetch<AISummaryResponse>(`/ai/candidates/${candidateId}/summary/refresh`, { method: 'POST' })
}

export function fetchCandidateAiCoach(candidateId: number) {
  return apiFetch<AICoachResponse>(`/ai/candidates/${candidateId}/coach`)
}

export function refreshCandidateAiCoach(candidateId: number) {
  return apiFetch<AICoachResponse>(`/ai/candidates/${candidateId}/coach/refresh`, { method: 'POST' })
}

export function upsertCandidateAiResume(
  candidateId: number,
  payload: { format: 'json'; resume_json: Record<string, unknown> } | { format: 'raw_text'; resume_text: string },
) {
  return apiFetch<CandidateAiResumeUpsertResponse>(`/ai/candidates/${candidateId}/hh-resume`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function fetchCandidateChatDrafts(candidateId: number, mode: 'short' | 'neutral' | 'supportive') {
  return apiFetch<AIDraftsResponse>(`/ai/candidates/${candidateId}/chat/drafts`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

export function fetchCandidateCoachDrafts(candidateId: number, mode: 'short' | 'neutral' | 'supportive') {
  return apiFetch<AIDraftsResponse>(`/ai/candidates/${candidateId}/coach/drafts`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

export function fetchTemplateByKey(key: string) {
  return apiFetch<{ text?: string | null } | Array<{ id: number; text?: string | null; key?: string | null }>>(
    `/templates?key=${encodeURIComponent(key)}`,
  )
}

export type CandidateSearchResult = {
  items: Array<{
    id: number
    fio?: string | null
    city?: string | null
    status?: { label?: string | null; tone?: string | null }
  }>
}

export function searchCandidates(search: string, perPage: number) {
  return apiFetch<CandidateSearchResult>(`/candidates?search=${encodeURIComponent(search)}&per_page=${perPage}`)
}
