import { apiFetch } from '@/api/client'

export type ProfileResponse = {
  principal: { type: 'admin' | 'recruiter'; id: number }
  recruiter?: {
    id: number
    name: string
    tz: string
    tg_chat_id?: number | null
    telemost_url?: string | null
    active: boolean
    cities: { id: number; name: string }[]
  } | null
  stats: {
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
  profile?: {
    candidate_count: number
    slot_count: number
    city_count: number
    recruiter_count: number
    city_names: string[]
    today_meetings: Array<{ id: number; status?: string; start_utc?: string | null; city_id?: number | null }>
    upcoming_meetings: Array<{ id: number; status?: string; start_utc?: string | null; city_id?: number | null }>
    active_candidates: Array<{ id: number; name: string; city?: string | null; status?: string | null }>
    reminders: Array<{ title: string; when?: string }>
    planner_days: Array<{ date: string; entries: Array<{ id: number; time?: string; status?: string; city?: number | null }> }>
    city_options: Array<{ id: number; name: string; tz?: string | null }>
    admin_stats: {
      slots_by_status: Record<string, number>
      upcoming_global: Array<{ id: number; status?: string; start_utc?: string | null; city_id?: number | null; recruiter_id?: number | null }>
      health: Record<string, string | boolean | null>
    }
    kpi: {
      today: number
      upcoming: number
      pending: number
      conversion: number
      nearest_minutes?: number | null
      avg_lead_hours?: number | null
    }
  }
  avatar_url?: string | null
}

export const profileQueryKey = ['profile'] as const

export function fetchProfile(): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>('/profile')
}

export type TimezoneOption = {
  value: string
  label: string
  region: string
  offset: string
}

export type KpiTrend = {
  direction?: 'up' | 'down' | 'flat'
  display?: string
  label?: string
  percent?: number | null
}

export type KpiDetailRow = {
  candidate?: string
  recruiter?: string
  event_label?: string
  city?: string
}

export type KpiMetric = {
  key: string
  label: string
  tone: string
  icon?: string
  value: number
  previous: number
  trend?: KpiTrend
  details?: KpiDetailRow[]
}

export type ProfileKpiResponse = {
  timezone: string
  current: {
    label: string
    metrics: KpiMetric[]
  }
}

export type ProfileSettingsPayload = {
  name: string
  tz: string
  telemost_url?: string | null
}

export type ProfileSettingsResponse = {
  ok: boolean
  recruiter: {
    id: number
    name: string
    tz: string
    telemost_url?: string | null
    cities: { id: number; name: string }[]
  }
}

export type ChangePasswordPayload = {
  current_password: string
  new_password: string
}

export type AvatarUploadResponse = { ok: boolean; url?: string }
export type AvatarDeleteResponse = { ok: boolean; removed?: boolean }

export function fetchProfileTimezones(): Promise<TimezoneOption[]> {
  return apiFetch<TimezoneOption[]>('/timezones')
}

export function fetchProfileKpis(): Promise<ProfileKpiResponse> {
  return apiFetch<ProfileKpiResponse>('/kpis/current')
}

export function updateProfileSettings(payload: ProfileSettingsPayload): Promise<ProfileSettingsResponse> {
  return apiFetch<ProfileSettingsResponse>('/profile/settings', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function changeProfilePassword(payload: ChangePasswordPayload): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>('/profile/change-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function uploadProfileAvatar(file: File): Promise<AvatarUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return apiFetch<AvatarUploadResponse>('/profile/avatar', { method: 'POST', body: form })
}

export function deleteProfileAvatar(): Promise<AvatarDeleteResponse> {
  return apiFetch<AvatarDeleteResponse>('/profile/avatar', { method: 'DELETE' })
}
