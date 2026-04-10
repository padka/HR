import type { IncomingCandidate, IncomingPayload } from '@/api/services/dashboard'

export type { IncomingCandidate, IncomingPayload }

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
