import { apiFetch } from '@/api/client'

export type ThreadItem = {
  id: number
  type: 'direct' | 'group'
  title: string
  created_at: string
  last_message?: {
    text?: string | null
    created_at?: string | null
    sender_type?: string | null
    sender_id?: number | null
    type?: string | null
  }
  unread_count?: number
}

export type ThreadsPayload = {
  threads: ThreadItem[]
  latest_event_at?: string | null
}

export type MessageAttachment = {
  id: number
  filename: string
  mime_type?: string | null
  size?: number | null
}

export type CandidateCard = {
  id: number
  name: string
  city: string
  status_label?: string | null
  status_slug?: string | null
  telegram_id?: number | null
  profile_url?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
}

export type TaskInfo = {
  candidate_id: number
  status: 'pending' | 'accepted' | 'declined'
  created_at?: string | null
  decided_at?: string | null
  decided_by_type?: string | null
  decided_by_id?: number | null
  decision_comment?: string | null
}

export type MessageItem = {
  id: number
  thread_id: number
  sender_type: string
  sender_id: number
  sender_label?: string | null
  type?: string | null
  text?: string | null
  created_at: string
  edited_at?: string | null
  attachments: MessageAttachment[]
  read_by_count?: number
  read_by_total?: number
  task?: TaskInfo
  candidate?: CandidateCard
}

export type ThreadMember = {
  type: string
  id: number
  role?: string
  name?: string
  last_read_at?: string | null
  is_placeholder?: boolean
}

export type MessagesPayload = {
  messages: MessageItem[]
  has_more: boolean
  latest_message_at?: string | null
  latest_activity_at?: string | null
  members?: ThreadMember[]
}

export type RecruiterOption = {
  id: number
  name: string
}

export type CandidateListPayload = {
  items: Array<{
    id: number
    fio?: string | null
    city?: string | null
    status?: { label?: string | null; tone?: string | null }
  }>
}

export function fetchStaffThreads() {
  return apiFetch<ThreadsPayload>('/staff/threads')
}

export function fetchRecruiters() {
  return apiFetch<RecruiterOption[]>('/recruiters')
}

export function fetchStaffThreadMessages(threadId: number, limit = 80) {
  return apiFetch<MessagesPayload>(`/staff/threads/${threadId}/messages?limit=${limit}`)
}

export function searchMessengerCandidates(search: string, perPage: number) {
  return apiFetch<CandidateListPayload>(`/candidates?search=${encodeURIComponent(search)}&per_page=${perPage}`)
}

export function markStaffThreadRead(threadId: number) {
  return apiFetch(`/staff/threads/${threadId}/read`, { method: 'POST' })
}

export function createStaffThread(payload: {
  type: 'direct' | 'group'
  title?: string
  members?: Array<{ type: string; id: number }>
}) {
  return apiFetch('/staff/threads', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function sendStaffThreadMessage(threadId: number, payload: FormData | { text: string }) {
  return apiFetch<MessageItem>(`/staff/threads/${threadId}/messages`, {
    method: 'POST',
    body: payload instanceof FormData ? payload : JSON.stringify(payload),
  })
}

export function fetchStaffThreadUpdates(threadId: number, queryString: string, signal?: AbortSignal) {
  return apiFetch<MessagesPayload & { updated?: boolean }>(`/staff/threads/${threadId}/updates?${queryString}`, {
    signal,
  })
}

export function addStaffThreadMembers(threadId: number, memberIds: number[]) {
  return apiFetch<{ members: ThreadMember[] }>(`/staff/threads/${threadId}/members`, {
    method: 'POST',
    body: JSON.stringify({ members: memberIds.map((id) => ({ type: 'recruiter', id })) }),
  })
}

export function removeStaffThreadMember(threadId: number, member: Pick<ThreadMember, 'type' | 'id'>) {
  return apiFetch<{ members: ThreadMember[] }>(`/staff/threads/${threadId}/members/${member.type}/${member.id}`, {
    method: 'DELETE',
  })
}

export function sendStaffThreadCandidate(threadId: number, candidateId: number, note?: string | null) {
  return apiFetch<MessageItem>(`/staff/threads/${threadId}/candidate`, {
    method: 'POST',
    body: JSON.stringify({ candidate_id: candidateId, note: note || null }),
  })
}

export function acceptStaffCandidateTask(messageId: number) {
  return apiFetch<MessageItem>(`/staff/messages/${messageId}/candidate/accept`, {
    method: 'POST',
    body: JSON.stringify({ comment: null }),
  })
}

export function declineStaffCandidateTask(messageId: number, comment: string) {
  return apiFetch<MessageItem>(`/staff/messages/${messageId}/candidate/decline`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  })
}
