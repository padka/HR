import { apiFetch } from '@/api/client'

export type CandidateChatFolder = 'inbox' | 'archive' | 'all'

export type CandidateChatThread = {
  id: number
  candidate_id: number
  type: 'candidate'
  title: string
  city?: string | null
  status_label?: string | null
  status_slug?: string | null
  profile_url?: string | null
  telegram_username?: string | null
  created_at: string
  last_message_at?: string | null
  archived_at?: string | null
  is_archived?: boolean
  last_message_preview?: string | null
  last_message_kind?: 'candidate' | 'recruiter' | 'bot' | 'system' | null
  priority_bucket?: 'overdue' | 'needs_reply' | 'blocked' | 'waiting_candidate' | 'follow_up' | 'system' | 'terminal' | null
  priority_rank?: number | null
  requires_reply?: boolean
  sla_state?: string | null
  is_terminal?: boolean
  vacancy_label?: string | null
  assignee_label?: string | null
  relevance_score?: number | null
  relevance_level?: 'high' | 'medium' | 'low' | 'unknown' | null
  risk_hint?: string | null
  workspace_follow_up_due_at?: string | null
  last_message?: {
    text?: string | null
    preview?: string | null
    created_at?: string | null
    direction?: string | null
    kind?: 'candidate' | 'recruiter' | 'bot' | 'system' | null
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
  kind?: 'candidate' | 'recruiter' | 'bot' | 'system'
  text: string
  status?: string | null
  created_at: string
  author?: string | null
  can_retry?: boolean
}

export type CandidateChatPayload = {
  messages: CandidateChatMessage[]
  has_more: boolean
  latest_message_at?: string | null
  updated?: boolean
}

export type CandidateChatTemplate = {
  key: string
  label: string
  text: string
}

export function fetchCandidateChatThreads(params?: {
  search?: string
  unreadOnly?: boolean
  folder?: CandidateChatFolder
  limit?: number
}) {
  const query = new URLSearchParams()
  if (params?.search?.trim()) query.set('search', params.search.trim())
  if (params?.unreadOnly) query.set('unread_only', 'true')
  if (params?.folder) query.set('folder', params.folder)
  if (params?.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiFetch<CandidateChatThreadsPayload>(`/candidate-chat/threads${suffix}`)
}

export function waitForCandidateChatThreads(params?: {
  since?: string | null
  timeout?: number
  search?: string
  unreadOnly?: boolean
  folder?: CandidateChatFolder
  limit?: number
  signal?: AbortSignal
}) {
  const query = new URLSearchParams()
  if (params?.since) query.set('since', params.since)
  if (params?.timeout) query.set('timeout', String(params.timeout))
  if (params?.search?.trim()) query.set('search', params.search.trim())
  if (params?.unreadOnly) query.set('unread_only', 'true')
  if (params?.folder) query.set('folder', params.folder)
  if (params?.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiFetch<CandidateChatThreadsPayload>(`/candidate-chat/threads/updates${suffix}`, {
    signal: params?.signal,
  })
}

export function fetchCandidateChatMessages(candidateId: number, limit = 80) {
  return apiFetch<CandidateChatPayload>(`/candidates/${candidateId}/chat?limit=${limit}`)
}

export function waitForCandidateChatMessages(
  candidateId: number,
  params?: { since?: string | null; timeout?: number; limit?: number; signal?: AbortSignal },
) {
  const query = new URLSearchParams()
  if (params?.since) query.set('since', params.since)
  if (params?.timeout) query.set('timeout', String(params.timeout))
  if (params?.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiFetch<CandidateChatPayload>(`/candidates/${candidateId}/chat/updates${suffix}`, {
    signal: params?.signal,
  })
}

export function markCandidateChatThreadRead(candidateId: number) {
  return apiFetch(`/candidate-chat/threads/${candidateId}/read`, {
    method: 'POST',
  })
}

export function archiveCandidateChatThread(candidateId: number) {
  return apiFetch<{ ok: boolean; archived: boolean }>(`/candidate-chat/threads/${candidateId}/archive`, {
    method: 'POST',
  })
}

export function fetchCandidateChatTemplates() {
  return apiFetch<{ items: CandidateChatTemplate[] }>('/candidate-chat/templates')
}

export function sendCandidateThreadMessage(candidateId: number, payload: { text: string; client_request_id?: string }) {
  return apiFetch<{ message?: CandidateChatMessage; status?: string }>(`/candidates/${candidateId}/chat`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function applyCandidateChatQuickAction(
  candidateId: number,
  payload: { status: string; send_message?: boolean; template_key?: string | null; message_text?: string | null },
) {
  return apiFetch<{
    ok: boolean
    message?: string
    status?: string | null
    chat_message?: CandidateChatMessage | null
    chat_delivery_status?: string | null
    chat_delivery_error?: string | null
  }>(`/candidates/${candidateId}/chat/quick-action`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
