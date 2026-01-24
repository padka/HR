import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'

export type ProfileResponse = {
  principal: { type: 'admin' | 'recruiter'; id: number }
  recruiter?: {
    id: number
    name: string
    tz: string
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
}

export function useProfile(enabled = true) {
  return useQuery<ProfileResponse>({
    queryKey: ['profile'],
    queryFn: () => apiFetch<ProfileResponse>('/profile'),
    staleTime: 15_000,
    enabled,
  })
}
