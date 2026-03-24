import { apiFetch } from './client'
import { readCandidatePortalAccessToken } from '@/shared/candidate-portal-session'

export const CANDIDATE_API_URL = '/api/candidate'

export type CandidatePortalStepStatus = 'pending' | 'in_progress' | 'completed' | 'skipped'

export type CandidatePortalQuestion = {
  index: number
  id: string
  prompt: string
  placeholder?: string | null
  helper?: string | null
  options?: string[]
  input_type: 'text' | 'number' | 'single_choice'
  required: boolean
}

export type CandidatePortalSlot = {
  id: number
  status?: string | null
  purpose?: string | null
  start_utc?: string | null
  end_utc?: string | null
  duration_min?: number | null
  city_id?: number | null
  city_name?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  candidate_tz?: string | null
  tz_name?: string | null
}

export type CandidatePortalMessage = {
  id: number
  direction: 'inbound' | 'outbound'
  channel?: string | null
  text?: string | null
  status?: string | null
  author_label?: string | null
  created_at?: string | null
}

export type CandidatePortalJourneyResponse = {
  candidate: {
    id: number
    candidate_id: string
    fio?: string | null
    phone?: string | null
    city?: string | null
    city_id?: number | null
    vacancy_label?: string | null
    vacancy_reference?: string | null
    vacancy_position?: string | null
    status?: string | null
    status_label?: string | null
    source?: string | null
    portal_url?: string | null
  }
  company?: {
    name?: string | null
    summary?: string | null
    highlights?: string[]
  }
  journey: {
    session_id: number
    journey_key: string
    journey_version: string
    entry_channel: string
    current_step: 'profile' | 'screening' | 'slot_selection' | 'status'
    current_step_label: string
    next_action: string
    next_step_at?: string | null
    next_step_timezone?: string | null
    steps: Array<{
      key: string
      label: string
      status: CandidatePortalStepStatus
    }>
    profile: {
      fio?: string | null
      phone?: string | null
      city_id?: number | null
      city_name?: string | null
    }
    screening: {
      questions: CandidatePortalQuestion[]
      draft_answers: Record<string, string>
      completed: boolean
      completed_at?: string | null
    }
    slots: {
      available: CandidatePortalSlot[]
      active?: CandidatePortalSlot | null
    }
    messages: CandidatePortalMessage[]
    cities: Array<{
      id: number
      name: string
      tz?: string | null
    }>
  }
}

type CandidateFetchInit = RequestInit & {
  json?: unknown
}

export async function candidateFetch<T>(path: string, init?: CandidateFetchInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.json !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const portalToken = readCandidatePortalAccessToken()
  if (portalToken && !headers.has('x-candidate-portal-token')) {
    headers.set('x-candidate-portal-token', portalToken)
  }
  const apiPath = `${CANDIDATE_API_URL.replace(/^\/api/, '')}${path}`

  return apiFetch<T>(apiPath, {
    ...init,
    skipCsrf: true,
    headers,
    body: init?.json !== undefined ? init.json : init?.body,
  })
}

export const exchangeCandidatePortalToken = async (token: string) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/session/exchange', {
    method: 'POST',
    json: { token },
  })

export const fetchCandidatePortalJourney = async () =>
  await candidateFetch<CandidatePortalJourneyResponse>('/journey')

export const saveCandidatePortalProfile = async (payload: {
  fio: string
  phone: string
  city_id: number
}) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/profile', {
    method: 'POST',
    json: payload,
  })

export const saveCandidatePortalScreeningDraft = async (answers: Record<string, string>) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/screening/save', {
    method: 'POST',
    json: { answers },
  })

export const completeCandidatePortalScreening = async (answers: Record<string, string>) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/screening/complete', {
    method: 'POST',
    json: { answers },
  })

export const reserveCandidatePortalSlot = async (slotId: number) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/slots/reserve', {
    method: 'POST',
    json: { slot_id: slotId },
  })

export const confirmCandidatePortalSlot = async () =>
  await candidateFetch<CandidatePortalJourneyResponse>('/slots/confirm', {
    method: 'POST',
  })

export const cancelCandidatePortalSlot = async () =>
  await candidateFetch<CandidatePortalJourneyResponse>('/slots/cancel', {
    method: 'POST',
  })

export const rescheduleCandidatePortalSlot = async (newSlotId: number) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/slots/reschedule', {
    method: 'POST',
    json: { new_slot_id: newSlotId },
  })

export const sendCandidatePortalMessage = async (text: string) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/messages', {
    method: 'POST',
    json: { text },
  })

export const logoutCandidatePortalSession = async () =>
  await candidateFetch<void>('/session/logout', {
    method: 'POST',
  })
