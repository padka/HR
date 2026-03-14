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
  ai_recommendation?: 'od_recommended' | 'clarify_before_od' | 'not_recommended' | null
  ai_risk_hint?: string | null
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

export type AvailableSlot = {
  slot_id: number
  start_utc: string | null
  city_id?: number | null
  city_name?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  slot_tz?: string | null
  recruiter_tz?: string | null
}

export type AvailableSlotsPayload = {
  ok: boolean
  items: AvailableSlot[]
  candidate_city_id?: number | null
}

export type ScheduleIncomingPayload = {
  candidate: IncomingCandidate
  date?: string
  time?: string
  message?: string
  slotId?: number
}

export type ActionResponse = {
  message?: string
}
