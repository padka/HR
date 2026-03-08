import { apiFetch } from '@/api/client'

export type CandidateChatThread = {
  id: number
  candidate_id: number
  type: 'candidate'
  title: string
  city?: string | null
  status_label?: string | null
  profile_url?: string | null
  telegram_username?: string | null
  created_at: string
  last_message_at?: string | null
  last_message?: {
    text?: string | null
    created_at?: string | null
    direction?: string | null
  }
  unread_count?: number
}

export type CandidateChatThreadsPayload = {
  threads: CandidateChatThread[]
  latest_event_at?: string | null
  updated?: boolean
}

export type CandidateChatMessage = {
  id: number
  direction: string
  text: string
  status?: string | null
  created_at: string
  author?: string | null
  can_retry?: boolean
}

export type CandidateChatPayload = {
  messages: CandidateChatMessage[]
  has_more: boolean
}

export function fetchCandidateChatThreads() {
  return apiFetch<CandidateChatThreadsPayload>('/candidate-chat/threads')
}

export function fetchCandidateChatMessages(candidateId: number, limit = 80) {
  return apiFetch<CandidateChatPayload>(`/candidates/${candidateId}/chat?limit=${limit}`)
}

export function markCandidateChatThreadRead(candidateId: number) {
  return apiFetch(`/candidate-chat/threads/${candidateId}/read`, {
    method: 'POST',
  })
}

export function sendCandidateThreadMessage(candidateId: number, payload: { text: string; client_request_id?: string }) {
  return apiFetch<{ message?: CandidateChatMessage; status?: string }>(`/candidates/${candidateId}/chat`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
