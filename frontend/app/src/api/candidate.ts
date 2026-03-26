import { apiFetch } from './client'
import {
  clearCandidatePortalAccessToken,
  readCandidatePortalAccessToken,
} from '@/shared/candidate-portal-session'

export const CANDIDATE_API_URL = '/api/candidate'

export type CandidatePortalStepStatus = 'pending' | 'in_progress' | 'completed' | 'skipped'
export type CandidatePortalRecoveryState = 'recoverable' | 'needs_new_link' | 'blocked'

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
  skipStoredPortalToken?: boolean
}

export type CandidatePortalErrorInfo = {
  status?: number
  code?: string
  state?: CandidatePortalRecoveryState
  message: string
  canResume?: boolean
  requiresFreshLink?: boolean
}

export async function candidateFetch<T>(path: string, init?: CandidateFetchInit): Promise<T> {
  const { skipStoredPortalToken = false, ...requestInit } = init ?? {}
  const headers = new Headers(requestInit.headers)
  if (requestInit.json !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const portalToken = skipStoredPortalToken ? '' : readCandidatePortalAccessToken()
  if (portalToken && !headers.has('x-candidate-portal-token')) {
    headers.set('x-candidate-portal-token', portalToken)
  }
  const apiPath = `${CANDIDATE_API_URL.replace(/^\/api/, '')}${path}`

  return apiFetch<T>(apiPath, {
    ...requestInit,
    skipCsrf: true,
    headers,
    body: requestInit.json !== undefined ? requestInit.json : requestInit.body,
  })
}

export function parseCandidatePortalError(error: unknown): CandidatePortalErrorInfo | null {
  if (!error || typeof error !== 'object') return null
  const record = error as {
    status?: number
    data?: unknown
    message?: string
  }

  let detail: unknown = record.data
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const payload = detail as { detail?: unknown; message?: unknown; error?: unknown }
    detail = payload.detail ?? payload.error ?? detail
  }

  let message = record.message || ''
  let code: string | undefined
  let state: CandidatePortalRecoveryState | undefined
  let canResume: boolean | undefined
  let requiresFreshLink: boolean | undefined

  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const payload = detail as Record<string, unknown>
    if (typeof payload.message === 'string') message = payload.message
    if (typeof payload.code === 'string') code = payload.code
    if (
      typeof payload.state === 'string'
      && ['recoverable', 'needs_new_link', 'blocked'].includes(payload.state)
    ) {
      state = payload.state as CandidatePortalRecoveryState
    }
    if (typeof payload.can_resume === 'boolean') canResume = payload.can_resume
    if (typeof payload.requires_fresh_link === 'boolean') requiresFreshLink = payload.requires_fresh_link
  } else if (typeof detail === 'string' && !message) {
    message = detail
  }

  if (!message) message = 'Не удалось открыть кабинет.'
  if (!state && record.status === 401) {
    state = 'recoverable'
  }

  return {
    status: record.status,
    code,
    state,
    message,
    canResume,
    requiresFreshLink,
  }
}

export const exchangeCandidatePortalToken = async (token: string) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/session/exchange', {
    method: 'POST',
    json: { token },
    skipStoredPortalToken: true,
  })

export const fetchCandidatePortalJourney = async (options?: { skipStoredPortalToken?: boolean }) => {
  const skipStoredPortalToken = Boolean(options?.skipStoredPortalToken)
  const storedToken = skipStoredPortalToken ? '' : readCandidatePortalAccessToken()
  try {
    return await candidateFetch<CandidatePortalJourneyResponse>('/journey', {
      skipStoredPortalToken,
    })
  } catch (error) {
    const parsed = parseCandidatePortalError(error)
    if (storedToken && parsed?.status === 401) {
      clearCandidatePortalAccessToken()
      return await candidateFetch<CandidatePortalJourneyResponse>('/journey', {
        skipStoredPortalToken: true,
      })
    }
    throw error
  }
}

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
