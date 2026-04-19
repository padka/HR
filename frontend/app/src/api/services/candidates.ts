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

export type CandidateMaxRolloutActionKind = 'preview' | 'send' | 'reissue' | 'revoke'

export type CandidateMaxRolloutAction = CandidateAction & {
  kind?: CandidateMaxRolloutActionKind
}

export type CandidateMaxRolloutPreview = {
  max_launch_url?: string | null
  max_chat_url?: string | null
  message_preview?: string | null
  expires_at?: string | null
  dry_run?: boolean
}

export type CandidateMaxLaunchArtifact = {
  launch_url?: string | null
  launch_url_redacted?: string | null
  chat_url_redacted?: string | null
}

export type CandidateMaxLaunchObservation = {
  launched?: boolean
  launched_at?: string | null
  access_session_id?: number | null
  provider_bound?: boolean
}

export type CandidateMaxLaunchInviteRequest = {
  application_id?: number | null
  dry_run?: boolean
  send?: boolean
  reuse_policy?: 'reuse_active' | 'rotate_active'
}

export type CandidateMaxLaunchInviteResponse = {
  ok?: boolean
  status?: 'preview_ready' | 'issued' | 'sent' | 'send_failed' | 'revoked' | string
  dry_run?: boolean
  send_requested?: boolean
  reused_existing?: boolean
  invite_state?: 'active' | 'launched' | 'revoked' | 'expired' | string
  send_state?: 'preview_only' | 'sent' | 'failed' | 'not_sent' | string
  launch_state?: 'not_launched' | 'launched' | string
  message_preview?: string | null
  expires_at?: string | null
  revoked_at?: string | null
  access_token_id?: number | null
  correlation_id?: string | null
  application_id?: number | null
  launch_observation?: CandidateMaxLaunchObservation | null
  launch_artifact?: CandidateMaxLaunchArtifact | null
  summary?: CandidateMaxRollout | null
}

export type CandidateMaxRollout = {
  enabled?: boolean
  status?: string | null
  status_label?: string | null
  summary?: string | null
  hint?: string | null
  issued_at?: string | null
  sent_at?: string | null
  expires_at?: string | null
  revoked_at?: string | null
  dry_run?: boolean
  application_id?: number | null
  max_launch_url?: string | null
  max_chat_url?: string | null
  message_preview?: string | null
  preview?: CandidateMaxRolloutPreview | null
  actions?: Partial<Record<CandidateMaxRolloutActionKind, CandidateMaxRolloutAction | null>> | null
  preview_action?: CandidateMaxRolloutAction | null
  send_action?: CandidateMaxRolloutAction | null
  reissue_action?: CandidateMaxRolloutAction | null
  revoke_action?: CandidateMaxRolloutAction | null
  preview_action_key?: string | null
  send_action_key?: string | null
  reissue_action_key?: string | null
  revoke_action_key?: string | null
  invite_state?: 'active' | 'launched' | 'revoked' | 'expired' | 'not_issued' | string
  send_state?: 'preview_only' | 'sent' | 'failed' | 'not_sent' | string
  launch_state?: 'not_launched' | 'launched' | string
  launch_observation?: CandidateMaxLaunchObservation | null
  access_token_id?: number | null
  correlation_id?: string | null
  flow_statuses?: Array<{
    key?: string | null
    label?: string | null
    status?: string | null
    status_label?: string | null
    detail?: string | null
  }>
}

export type CandidateMaxRolloutSnapshot = {
  enabled?: boolean
  invite_state?: 'active' | 'launched' | 'revoked' | 'expired' | 'not_issued' | string
  send_state?: 'preview_only' | 'sent' | 'failed' | 'not_sent' | string
  launch_state?: 'not_launched' | 'launched' | string
  launched_at?: string | null
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

export type CandidateChannelHealth = {
  candidate_id: number
  source?: string | null
  source_label?: string | null
  preferred_channel?: string | null
  telegram_linked?: boolean
  max_linked?: boolean
  linked_channels?: {
    telegram?: boolean
    max?: boolean
  } | null
  telegram?: {
    linked?: boolean
    telegram_id?: number | null
    telegram_username?: string | null
  } | null
  max?: {
    linked?: boolean
    max_user_id?: string | null
  } | null
  active_invite?: {
    status?: string | null
    channel?: string | null
    created_at?: string | null
    used_at?: string | null
    superseded_at?: string | null
    used_by_external_id?: string | null
    conflict?: boolean
  } | null
  last_inbound_at?: string | null
  last_outbound_at?: string | null
  last_outbound_delivery?: {
    status?: string | null
    delivery_stage?: string | null
    error?: string | null
    channel?: string | null
    created_at?: string | null
  } | null
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

export type CandidateLifecycleStage =
  | 'lead'
  | 'screening'
  | 'waiting_interview_slot'
  | 'interview'
  | 'test2'
  | 'waiting_intro_day'
  | 'intro_day'
  | 'closed'

export type CandidateRecordState = 'active' | 'closed'

export type CandidateContractFinalOutcome = 'hired' | 'not_hired' | 'not_counted'

export type CandidateContractIssue = {
  code?: string | null
  severity?: 'warning' | 'error' | 'critical' | string
  message?: string | null
}

export type CandidateLifecycleSummary = {
  stage?: CandidateLifecycleStage | null
  stage_label?: string | null
  record_state?: CandidateRecordState | null
  final_outcome?: CandidateContractFinalOutcome | null
  final_outcome_label?: string | null
  archive_reason?: string | null
  legacy_status_slug?: string | null
  updated_at?: string | null
}

export type CandidateSchedulingSummary = {
  source?: 'slot_assignment' | 'legacy_slot' | 'none' | string
  stage?: 'interview' | 'intro_day' | null
  status?: 'offered' | 'selected' | 'scheduled' | 'confirmed' | 'reschedule_requested' | 'cancelled' | 'completed' | 'no_show' | null
  status_label?: string | null
  active?: boolean
  requested_reschedule?: boolean
  slot_id?: number | null
  slot_assignment_id?: number | null
  slot_status?: string | null
  slot_assignment_status?: string | null
  start_utc?: string | null
  candidate_tz?: string | null
  issues?: CandidateContractIssue[]
}

export type CandidateNextActionPrimary = {
  type?: string | null
  label?: string | null
  enabled?: boolean
  owner_role?: string | null
  blocking_reasons?: string[]
  deadline_at?: string | null
  source_ref?: { kind?: string | null; id?: number | string | null } | null
  ui_action?: 'open_schedule_slot_modal' | 'open_schedule_intro_day_modal' | 'open_chat' | 'invoke_candidate_action' | null
  legacy_action_key?: string | null
}

export type CandidateNextAction = {
  version?: number
  candidate_id?: string | null
  lifecycle_stage?: CandidateLifecycleStage | null
  record_state?: CandidateRecordState | null
  worklist_bucket?: 'incoming' | 'today' | 'awaiting_candidate' | 'awaiting_recruiter' | 'blocked' | 'closed' | string
  worklist_bucket_label?: string | null
  urgency?: 'normal' | 'attention' | 'urgent' | 'blocked' | string
  stale_since?: string | null
  primary_action?: CandidateNextActionPrimary | null
  secondary_actions?: CandidateNextActionPrimary[]
  blocking_reasons?: string[]
  explanation?: string | null
}

export type CandidateStateReconciliation = {
  issues?: CandidateContractIssue[]
  has_blockers?: boolean
}

export type CandidateBlockingState = {
  code?: string | null
  category?: string | null
  severity?: 'info' | 'warning' | 'error' | 'critical' | string
  retryable?: boolean
  recoverable?: boolean
  manual_resolution_required?: boolean
  issue_codes?: string[]
}

export type CandidateOperationalSummary = {
  worklist_bucket?: 'incoming' | 'today' | 'awaiting_candidate' | 'awaiting_recruiter' | 'blocked' | 'closed' | string
  worklist_bucket_label?: string | null
  kanban_column?: string | null
  kanban_column_label?: string | null
  kanban_column_icon?: string | null
  kanban_target_status?: string | null
  queue_state?: string | null
  queue_state_label?: string | null
  dominant_signal?: string | null
  dominant_signal_label?: string | null
  requested_reschedule?: boolean
  pending_approval?: boolean
  stalled?: boolean
  has_reconciliation_issues?: boolean
  has_scheduling_conflict?: boolean
}

export type CandidateStateFilterOption = {
  value: string
  label: string
  kind?: 'all' | 'kanban' | 'lifecycle' | 'worklist' | string
  icon?: string | null
  target_status?: string | null
}

export type CandidateStatusView = {
  slug?: string | null
  label?: string | null
  tone?: string | null
  icon?: string | null
  rank?: number | null
}

export type CandidateListCard = {
  id: number
  candidate_id?: string | null
  fio?: string | null
  city?: string | null
  telegram_id?: number | string | null
  telegram_user_id?: number | string | null
  telegram_username?: string | null
  telegram_linked_at?: string | null
  linked_channels?: {
    telegram?: boolean
    max?: boolean
  } | null
  max?: {
    linked?: boolean
    max_user_id?: string | null
  } | null
  preferred_channel?: string | null
  max_rollout?: CandidateMaxRolloutSnapshot | null
  status?: CandidateStatusView | null
  journey?: CandidateJourney | null
  archive?: CandidateArchive | null
  final_outcome?: CandidateFinalOutcome | null
  final_outcome_reason?: string | null
  pending_slot_request?: CandidatePendingSlotRequest | null
  manual_mode?: boolean
  state_contract_version?: number
  lifecycle_summary?: CandidateLifecycleSummary | null
  scheduling_summary?: CandidateSchedulingSummary | null
  candidate_next_action?: CandidateNextAction | null
  operational_summary?: CandidateOperationalSummary | null
  state_reconciliation?: CandidateStateReconciliation | null
  tests?: {
    test1?: { status?: string | null; label?: string | null; icon?: string | null } | null
    test2?: { status?: string | null; label?: string | null; icon?: string | null } | null
  } | null
  stage?: string | null
  upcoming_slot?: { start_utc?: string | null } | null
  latest_slot?: { start_utc?: string | null } | null
  slots?: CandidateSlot[]
  messages_total?: number | null
  primary_event_at?: string | null
  group?: { key?: string | null; label?: string | null } | null
  average_score?: number | null
  avg_score?: number | null
  ai_relevance_score?: number | null
  ai_relevance_level?: 'high' | 'medium' | 'low' | 'unknown' | null
  ai_relevance_updated_at?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
  candidate_actions?: CandidateAction[]
}

export type CandidateListItem = {
  id: number
  fio?: string | null
  city?: string | null
  status?: CandidateStatusView | null
  telegram_id?: number | string | null
  telegram_username?: string | null
  telegram_linked_at?: string | null
  linked_channels?: {
    telegram?: boolean
    max?: boolean
  } | null
  max?: {
    linked?: boolean
    max_user_id?: string | null
  } | null
  preferred_channel?: string | null
  max_rollout?: CandidateMaxRolloutSnapshot | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
  average_score?: number | null
  ai_relevance_score?: number | null
  ai_relevance_level?: 'high' | 'medium' | 'low' | 'unknown' | null
  ai_relevance_updated_at?: string | null
  tests_total?: number | null
  primary_event_at?: string | null
  latest_message?: { created_at?: string | null } | null
  latest_slot?: { start_utc?: string | null } | null
  upcoming_slot?: { start_utc?: string | null } | null
  candidate_actions?: CandidateAction[]
}

export type CandidateCalendarDay = {
  date: string
  label: string
  events: Array<{
    candidate?: CandidateListCard
    slot?: { start_utc?: string | null }
    status?: CandidateStatusView
  }>
  totals?: Record<string, number>
}

export type CandidateListPayload = {
  items: CandidateListItem[]
  total: number
  page: number
  pages_total: number
  filters?: Record<string, unknown> & {
    state?: string[]
    state_options?: CandidateStateFilterOption[]
  }
  pipeline?: string
  pipeline_options?: Array<{ slug: string; label: string }>
  views?: {
    kanban?: {
      columns: Array<{
        slug: string
        label: string
        icon?: string | null
        tone?: string | null
        target_status?: string | null
        total?: number
        droppable?: boolean
        candidates: CandidateListCard[]
      }>
      status_totals?: Record<string, number>
    }
    calendar?: { days: CandidateCalendarDay[] }
    candidates?: CandidateListCard[]
  }
}

export type CandidateActionState = {
  id?: number | null
  candidate_status_slug?: string | null
  candidate_status_display?: string | null
  candidate_status_color?: string | null
  lifecycle_summary?: CandidateLifecycleSummary | null
  scheduling_summary?: CandidateSchedulingSummary | null
  candidate_next_action?: CandidateNextAction | null
  operational_summary?: CandidateOperationalSummary | null
  state_reconciliation?: CandidateStateReconciliation | null
  candidate_actions?: CandidateAction[]
  allowed_next_statuses?: Array<{ slug: string; label: string; color?: string; is_terminal?: boolean }>
  status_is_terminal?: boolean
}

export type CandidateActionErrorCode =
  | 'action_not_allowed'
  | 'invalid_transition'
  | 'scheduling_conflict'
  | 'missing_interview_scheduling'
  | 'missing_interview_slot'
  | 'test2_not_passed'
  | 'partial_transition_requires_repair'
  | 'candidate_not_found'
  | string

export type CandidateActionResponse = {
  ok: boolean
  message?: string | null
  status?: string | null
  action?: string | null
  candidate_id?: number | null
  error?: CandidateActionErrorCode | null
  intent?: Record<string, unknown> | null
  candidate_state?: CandidateActionState | null
  blocking_state?: CandidateBlockingState | null
}

export type CandidateDetail = {
  id: number
  created_at?: string | null
  last_activity_at?: string | null
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
  source?: string | null
  source_label?: string | null
  messenger_platform?: string | null
  linked_channels?: {
    telegram?: boolean
    max?: boolean
  } | null
  max?: {
    linked?: boolean
    max_user_id?: string | null
  } | null
  channel_health?: CandidateChannelHealth | null
  max_rollout?: CandidateMaxRollout | null
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
  state_contract_version?: number
  lifecycle_summary?: CandidateLifecycleSummary | null
  scheduling_summary?: CandidateSchedulingSummary | null
  candidate_next_action?: CandidateNextAction | null
  operational_summary?: CandidateOperationalSummary | null
  state_reconciliation?: CandidateStateReconciliation | null
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

export function issueCandidateMaxLaunchInvite(
  candidateId: number,
  payload: CandidateMaxLaunchInviteRequest,
) {
  return apiFetch<CandidateMaxLaunchInviteResponse>(
    `/candidates/${candidateId}/max-launch-invite`,
    {
      method: 'POST',
      body: payload,
    },
  )
}

export function revokeCandidateMaxLaunchInvite(
  candidateId: number,
  applicationId?: number | null,
) {
  const search = applicationId ? `?application_id=${encodeURIComponent(String(applicationId))}` : ''
  return apiFetch<CandidateMaxLaunchInviteResponse>(
    `/candidates/${candidateId}/max-launch-invite/revoke${search}`,
    {
      method: 'POST',
    },
  )
}

export function fetchCandidateChannelHealth(candidateId: number) {
  return apiFetch<CandidateChannelHealth>(`/candidates/${candidateId}/channel-health`)
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
  return apiFetch<CandidateActionResponse>(`/candidates/${candidateId}/actions/${actionKey}`, {
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
