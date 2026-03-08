import { apiFetch } from '@/api/client'

export type SummaryPayload = {
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

export type KPITrend = {
  display: string
  label: string
}

export type KPICard = {
  key: string
  label: string
  tone: string
  icon: string
  value: number
  previous: number
  trend: KPITrend
}

export type KPIResponse = {
  current: {
    label: string
    metrics: KPICard[]
  }
  previous: {
    label: string
  }
}

export type RecruiterOption = {
  id: number
  name: string
}

export type LeaderboardItem = {
  recruiter_id: number
  name: string
  score: number
  rank: number
  conversion_interview: number
  confirmation_rate: number
  fill_rate: number
  throughput: number
  candidates_total: number
  hired_total: number
  declined_total: number
}

export type LeaderboardPayload = {
  window: { from: string; to: string; days: number }
  items: LeaderboardItem[]
}

export type IncomingCandidate = {
  id: number
  name: string | null
  city: string | null
  city_id?: number | null
  status_display?: string | null
  status_slug?: string | null
  waiting_hours?: number | null
  availability_window?: string | null
  availability_note?: string | null
  telegram_id?: number | null
  telegram_username?: string | null
  last_message?: string | null
  last_message_at?: string | null
  responsible_recruiter_id?: number | null
  responsible_recruiter_name?: string | null
  profile_url?: string | null
  ai_relevance_score?: number | null
  ai_relevance_level?: 'high' | 'medium' | 'low' | 'unknown' | null
  ai_relevance_updated_at?: string | null
  requested_another_time?: boolean
  requested_another_time_at?: string | null
  requested_another_time_comment?: string | null
  requested_another_time_from?: string | null
  requested_another_time_to?: string | null
  incoming_substatus?: string | null
}

export type IncomingPayload = {
  items: IncomingCandidate[]
}

export function fetchDashboardSummary() {
  return apiFetch<SummaryPayload>('/dashboard/summary')
}

export function fetchDashboardRecruiters() {
  return apiFetch<RecruiterOption[]>('/recruiters')
}

export function fetchDashboardIncoming(limit: number) {
  return apiFetch<IncomingPayload>(`/dashboard/incoming?limit=${limit}`)
}

export function fetchCurrentKpis(querySuffix = '') {
  return apiFetch<KPIResponse>(`/kpis/current${querySuffix}`)
}

export function fetchRecruiterPerformance(queryString: string) {
  return apiFetch<LeaderboardPayload>(`/dashboard/recruiter-performance?${queryString}`)
}

export function rejectDashboardCandidate(candidateId: number) {
  return apiFetch<{ message?: string }>(`/candidates/${candidateId}/actions/reject`, { method: 'POST' })
}

export function scheduleDashboardIncomingSlot(
  candidateId: number,
  payload: {
    recruiter_id: number
    city_id: number
    date: string
    time: string
    custom_message?: string
  },
) {
  return apiFetch<{ message?: string }>(`/candidates/${candidateId}/schedule-slot`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
