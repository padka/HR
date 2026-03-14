import { URL_RE } from './messenger.constants'
import type {
  CandidateChatMessage,
  CandidateChatThread,
  CandidateChatThreadsPayload,
  GroupedMessageRow,
  ThreadTone,
} from './messenger.types'

export function priorityTone(bucket?: CandidateChatThread['priority_bucket'] | null): ThreadTone {
  switch (bucket) {
    case 'overdue':
      return 'danger'
    case 'needs_reply':
    case 'blocked':
    case 'follow_up':
      return 'warning'
    case 'waiting_candidate':
      return 'info'
    case 'system':
      return 'neutral'
    case 'terminal':
      return 'danger'
    default:
      return 'success'
  }
}

export function priorityLabel(bucket?: CandidateChatThread['priority_bucket'] | null): string {
  switch (bucket) {
    case 'overdue':
      return 'Просрочен ответ'
    case 'needs_reply':
      return 'Нужен ответ'
    case 'blocked':
      return 'Подтверждение / блокер'
    case 'waiting_candidate':
      return 'Ждём кандидата'
    case 'follow_up':
      return 'Нужен follow-up'
    case 'system':
      return 'Системный'
    case 'terminal':
      return 'Закрытый статус'
    default:
      return 'В работе'
  }
}

export function formatThreadTime(value?: string | null): string {
  if (!value) return ''
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return ''
  const today = new Date()
  if (dt.toDateString() === today.toDateString()) {
    return dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }
  return dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

export function formatFullDateTime(value?: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDayLabel(value: string): string {
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return 'Сегодня'
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (dt.toDateString() === today.toDateString()) return 'Сегодня'
  if (dt.toDateString() === yesterday.toDateString()) return 'Вчера'
  return dt.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long' })
}

export function previewText(thread?: CandidateChatThread | null): string {
  return thread?.last_message_preview?.trim() || thread?.last_message?.preview?.trim() || thread?.last_message?.text?.trim() || 'Переписка ещё не началась'
}

export function compactThreadStatusLabel(
  status?: string | null,
  bucket?: CandidateChatThread['priority_bucket'] | null,
): string {
  const normalized = (status || '').toLowerCase()
  if (!normalized) return priorityLabel(bucket)
  if (normalized.includes('отказ')) return 'Отказ'
  if (normalized.includes('собесед')) return 'Собеседование'
  if (normalized.includes('ознаком')) return 'Ознакомление'
  if (normalized.includes('подтверж')) return 'Подтверждён'
  if (normalized.includes('перенос')) return 'Перенос'
  if (normalized.includes('ожид')) return 'Ожидание'
  return status!.length > 24 ? `${status!.slice(0, 24).trim()}…` : status!
}

export function messageAuthorLabel(message: CandidateChatMessage): string {
  if (message.kind === 'candidate' || message.direction === 'inbound') return message.author || 'Кандидат'
  if (message.kind === 'bot') return 'Бот'
  if (message.kind === 'system') return 'Система'
  return message.author || 'Вы'
}

export function readThreadCache(
  payload: CandidateChatThreadsPayload | undefined,
  candidateId: number,
): CandidateChatThreadsPayload | undefined {
  if (!payload) return payload
  return {
    ...payload,
    threads: (payload.threads || []).map((thread) =>
      thread.candidate_id === candidateId ? { ...thread, unread_count: 0 } : thread,
    ),
  }
}

export function scoreTone(score?: number | null, level?: string | null): ThreadTone {
  if (typeof score === 'number') {
    if (score >= 80) return 'success'
    if (score >= 60) return 'info'
    if (score >= 40) return 'warning'
    return 'danger'
  }
  if (level === 'high') return 'success'
  if (level === 'medium') return 'info'
  if (level === 'low') return 'warning'
  return 'neutral'
}

export function normalizeTextLinks(text?: string | null): string[] {
  if (!text) return []
  const matches = text.match(URL_RE) || []
  return Array.from(new Set(matches))
}

export function splitMessageText(text?: string | null): string[] {
  return (text || '…').split(URL_RE)
}

export function threadAvatar(thread?: CandidateChatThread | null): string {
  return (thread?.title || 'К').slice(0, 2).toUpperCase()
}

export function groupedMessagesWithUnread(
  messages: CandidateChatMessage[],
  unreadCount: number,
): GroupedMessageRow[] {
  const groups: GroupedMessageRow[] = []
  const inboundIds = messages.filter((message) => message.direction === 'inbound').map((message) => message.id)
  const firstUnreadId = unreadCount > 0 ? inboundIds[Math.max(0, inboundIds.length - unreadCount)] : null
  let currentDayKey = ''
  for (const message of messages) {
    const dayKey = new Date(message.created_at).toDateString()
    if (dayKey !== currentDayKey) {
      currentDayKey = dayKey
      groups.push({ type: 'divider', key: `${dayKey}-${message.id}`, label: formatDayLabel(message.created_at) })
    }
    groups.push({ type: 'message', message, unreadAnchor: firstUnreadId === message.id })
  }
  return groups
}
