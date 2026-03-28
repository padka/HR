import { apiFetch } from './client'
import {
  clearCandidatePortalAccessToken,
  readCandidatePortalAccessToken,
} from '@/shared/candidate-portal-session'

export const CANDIDATE_API_URL = '/api/candidate'

export type CandidatePortalStepStatus = 'pending' | 'in_progress' | 'completed' | 'skipped'
export type CandidatePortalRecoveryState = 'recoverable' | 'needs_new_link' | 'blocked'
export type CandidateEntryChannel = 'web' | 'max' | 'telegram'

export type CandidateSharedAccessChallengeResponse = {
  ok: boolean
  challenge_token: string
  expires_in_seconds: number
  retry_after_seconds: number
  message: string
  delivery_hint?: string | null
}

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
  conversation_id?: string | null
  direction: 'inbound' | 'outbound'
  channel?: string | null
  origin_channel?: string | null
  delivery_channels?: string[]
  delivery_state?: string | null
  author_role?: 'candidate' | 'recruiter' | 'system' | 'bot' | null
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
    entry_url?: string | null
    portal_url?: string | null
  }
  company?: {
    name?: string | null
    summary?: string | null
    highlights?: string[]
    faq?: Array<{
      question: string
      answer: string
    }>
    documents?: Array<{
      key: string
      title: string
      summary: string
    }>
    contacts?: Array<{
      label: string
      value: string
    }>
  }
  dashboard?: {
    primary_action?: {
      key?: string | null
      label?: string | null
      description?: string | null
      target?: string | null
    } | null
    alerts?: Array<{
      level?: 'info' | 'warning' | 'success' | 'danger' | string
      title?: string | null
      body?: string | null
    }>
    last_activity_at?: string | null
    upcoming_items?: Array<{
      kind?: string | null
      title?: string | null
      scheduled_at?: string | null
      timezone?: string | null
      state?: string | null
    }>
  }
  tests?: {
    items?: Array<{
      key: string
      title: string
      status?: CandidatePortalStepStatus | 'completed' | 'in_progress' | 'pending'
      status_label?: string | null
      summary?: string | null
      question_count?: number | null
      completed_at?: string | null
      final_score?: number | null
      raw_score?: number | null
      total_time?: number | null
    }>
  }
  feedback?: {
    items?: Array<{
      kind?: string | null
      title?: string | null
      body?: string | null
      created_at?: string | null
      author_role?: 'candidate' | 'recruiter' | 'system' | 'bot' | null
    }>
    last_feedback_sent_at?: string | null
  }
  resources?: {
    faq?: Array<{
      question: string
      answer: string
    }>
    documents?: Array<{
      key: string
      title: string
      summary: string
    }>
    contacts?: Array<{
      label: string
      value: string
    }>
  }
  journey: {
    session_id: number
    journey_key: string
    journey_version: string
    entry_channel: string
    last_entry_channel?: string | null
    available_channels?: string[]
    channel_options?: Partial<Record<CandidateEntryChannel, CandidateEntryGatewayOption>>
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
    inbox?: {
      conversation_id?: string | null
      unread_count?: number | null
      read_tracking_supported?: boolean
      latest_message?: CandidatePortalMessage | null
      delivery_state?: string | null
      available_channels?: string[]
    }
    cities: Array<{
      id: number
      name: string
      tz?: string | null
    }>
  }
}

export type CandidateEntryGatewayOption = {
  channel: CandidateEntryChannel
  enabled: boolean
  launch_url?: string | null
  reason_if_blocked?: string | null
  requires_bot_start?: boolean
  type?: 'cabinet' | 'external' | null
}

export type CandidateEntryGatewayResponse = {
  candidate: {
    id: number
    candidate_id: string
    fio?: string | null
    city?: string | null
    vacancy_label?: string | null
    company?: string | null
  }
  journey: {
    session_id: number
    current_step?: string | null
    current_step_label?: string | null
    status?: string | null
    status_label?: string | null
    next_action?: string | null
    last_entry_channel?: string | null
    available_channels?: string[]
  }
  options: Record<CandidateEntryChannel, CandidateEntryGatewayOption>
  company_preview?: {
    summary?: string | null
    highlights?: string[]
  }
  suggested_channel?: CandidateEntryChannel | null
  fallback_policy?: string | null
}

export type CandidateEntrySelectResponse = {
  channel: CandidateEntryChannel
  recorded: boolean
  launch: {
    type: 'cabinet' | 'external'
    url?: string | null
    requires_bot_start?: boolean
  }
  cabinet_url?: string | null
  delivery_status?: {
    status?: string | null
    source?: string | null
    blocked_reason?: string | null
  } | null
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

export const resolveCandidateEntryGateway = async (entryToken: string) => {
  const query = new URLSearchParams({ entry: entryToken })
  return await candidateFetch<CandidateEntryGatewayResponse>(`/entry/resolve?${query.toString()}`, {
    skipStoredPortalToken: true,
  })
}

export const startCandidateSharedAccessChallenge = async (phone: string) =>
  await candidateFetch<CandidateSharedAccessChallengeResponse>('/access/challenge', {
    method: 'POST',
    json: { phone },
    skipStoredPortalToken: true,
  })

export const verifyCandidateSharedAccessCode = async (challengeToken: string, code: string) =>
  await candidateFetch<CandidatePortalJourneyResponse>('/access/verify', {
    method: 'POST',
    json: { challenge_token: challengeToken, code },
    skipStoredPortalToken: true,
  })

export const selectCandidateEntryChannel = async (entryToken: string, channel: CandidateEntryChannel) =>
  await candidateFetch<CandidateEntrySelectResponse>(`/entry/select?${new URLSearchParams({
    entry: entryToken,
    channel,
  }).toString()}`, {
    method: 'POST',
    body: new URLSearchParams({
      entry_token: entryToken,
      channel,
    }),
    skipStoredPortalToken: true,
  })

export const switchCandidateEntryChannel = async (channel: CandidateEntryChannel) =>
  await candidateFetch<CandidateEntrySelectResponse>('/entry/switch', {
    method: 'POST',
    json: { channel },
  })

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
