import { apiFetch } from '@/api/client'

export type HealthPayload = {
  recruiters: number
  cities: number
  slots_total: number
  slots_free: number
  slots_pending: number
  slots_booked: number
  waiting_candidates_total: number
  test1_rejections_total: number
  test1_total_seen: number
  test1_rejections_percent: number
}

export type BotStatus = {
  config_enabled: boolean
  runtime_enabled: boolean
  updated_at: string | null
  switch_source: 'operator' | 'runtime'
  switch_reason: string | null
  service_health: string
  service_ready: boolean
}

export type ReminderKindConfig = {
  enabled: boolean
  offset_hours: number
}

export type ReminderPolicy = {
  interview: {
    confirm_6h: ReminderKindConfig
    confirm_3h: ReminderKindConfig
    confirm_2h: ReminderKindConfig
  }
  intro_day: {
    intro_remind_3h: ReminderKindConfig
  }
  min_time_before_immediate_hours: number
}

export type ReminderPolicyPayload = {
  policy: ReminderPolicy
  updated_at: string | null
  links: {
    questions: string
    message_templates: string
    templates: string
  }
}

export type ReminderPolicyUpdatePayload = {
  ok: boolean
  policy: ReminderPolicy
  updated_at: string
  rescheduled_slots: number
  reschedule_failed: number
}

export type ReminderJob = {
  id: number
  slot_id: number
  kind: string
  job_id: string
  scheduled_at: string | null
  slot_start_utc: string | null
  slot_status: string
  purpose: string
  candidate_tg_id: number | null
  candidate_fio: string | null
}

export type ReminderJobsPayload = {
  items: ReminderJob[]
  now_utc: string
  degraded: boolean
}

export type ReminderResyncPayload = {
  ok: boolean
  scheduled: number
  failed: number
}

export type OutboxItem = {
  id: number
  type: string
  status: string
  channel?: string | null
  attempts: number
  created_at: string | null
  locked_at: string | null
  next_retry_at: string | null
  last_error: string | null
  failure_class?: string | null
  failure_code?: string | null
  provider_message_id?: string | null
  dead_lettered_at?: string | null
  degraded_reason?: string | null
  booking_id: number | null
  candidate_tg_id: number | null
  recruiter_tg_id: number | null
  correlation_id: string | null
}

export type OutboxFeedPayload = {
  items: OutboxItem[]
  latest_id: number
  degraded: boolean
}

export type NotificationLogItem = {
  id: number
  type: string
  status: string
  channel?: string | null
  attempts: number
  attempt_no?: number | null
  created_at: string | null
  next_retry_at: string | null
  last_error: string | null
  failure_class?: string | null
  provider_message_id?: string | null
  booking_id: number
  candidate_tg_id: number | null
  template_key: string | null
  template_version: number | null
}

export type NotificationLogsPayload = {
  items: NotificationLogItem[]
  latest_id: number
  degraded: boolean
}

export type MessengerHealthChannel = {
  channel: string
  queue_depth: number
  dead_letter_count: number
  oldest_pending_age_seconds?: number | null
  degraded: boolean
  status?: string | null
  degraded_reason?: string | null
  degraded_at?: string | null
}

export type MessengerHealthPayload = {
  channels: Record<string, MessengerHealthChannel>
  portal?: {
    public_url?: string | null
    public_ready?: boolean
    public_error?: string | null
    public_message?: string | null
    max_entry_ready?: boolean
    max_entry_error?: string | null
    max_entry_message?: string | null
    max_link_base?: string | null
    token_valid?: boolean | null
    bot_profile_resolved?: boolean
    bot_profile_name?: string | null
    max_link_base_resolved?: boolean
    max_link_base_source?: 'env' | 'provider' | 'missing' | null
    webhook_public_ready?: boolean
    webhook_url?: string | null
    webhook_error?: string | null
    webhook_message?: string | null
    subscription_ready?: boolean
    subscription_error?: string | null
    subscription_message?: string | null
    shared_access?: {
      store_backend?: 'redis' | 'memory' | string
      store_ready?: boolean
      rate_limit_ready?: boolean
      production_required?: boolean
      production_ready?: boolean
      challenge_started?: number
      challenge_rate_limited?: number
      verify_success?: number
      verify_failed?: number
      verify_expired?: number
      delivery_channel_used?: Record<string, number>
      delivery_block_reason?: Record<string, number>
    } | null
  } | null
}

export type QuestionGroup = {
  test_id: string
  title: string
  questions: Array<{
    id: number
    index: number
    title: string
    is_active: boolean
  }>
}

export function fetchSystemHealth() {
  return apiFetch<HealthPayload>('/health')
}

export function fetchBotIntegration() {
  return apiFetch<BotStatus>('/bot/integration')
}

export function fetchQuestionGroups() {
  return apiFetch<QuestionGroup[]>('/questions')
}

export function fetchReminderPolicy() {
  return apiFetch<ReminderPolicyPayload>('/bot/reminder-policy')
}

export function fetchReminderJobs(limit = 50) {
  return apiFetch<ReminderJobsPayload>(`/bot/reminders/jobs?limit=${limit}`)
}

export function fetchNotificationsFeed(queryString: string) {
  return apiFetch<OutboxFeedPayload>(`/notifications/feed?${queryString}`)
}

export function fetchNotificationLogs(queryString: string) {
  return apiFetch<NotificationLogsPayload>(`/notifications/logs?${queryString}`)
}

export function fetchMessengerHealth() {
  return apiFetch<MessengerHealthPayload>('/system/messenger-health').then((payload) => ({
    channels: Object.fromEntries(
      Object.entries(payload.channels || {}).map(([channel, item]) => [
        channel,
        {
          ...item,
          status: item.degraded ? 'degraded' : 'healthy',
        },
      ]),
    ),
    portal: payload.portal || null,
  }))
}

export function retryNotification(id: number) {
  return apiFetch(`/notifications/${id}/retry`, { method: 'POST' })
}

export function cancelNotification(id: number) {
  return apiFetch(`/notifications/${id}/cancel`, { method: 'POST' })
}

export function refreshBotCities() {
  return apiFetch('/bot/cities/refresh', { method: 'POST' })
}

export function resyncReminderJobs() {
  return apiFetch<ReminderResyncPayload>('/bot/reminders/resync', { method: 'POST' })
}

export function updateReminderPolicy(policy: ReminderPolicy) {
  return apiFetch<ReminderPolicyUpdatePayload>('/bot/reminder-policy', {
    method: 'PUT',
    body: JSON.stringify({ policy }),
  })
}
