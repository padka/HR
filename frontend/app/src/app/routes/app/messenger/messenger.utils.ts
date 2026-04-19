import { URL_RE } from './messenger.constants'
import type {
  CandidateChatMessage,
  CandidateChatThread,
  CandidateChatThreadsPayload,
  GroupedMessageRow,
  MessengerChannelFilter,
  MessengerFolderMeta,
  MessengerFolderSummary,
  MessengerQuickFilter,
  MessengerStageFolder,
  ThreadTone,
} from './messenger.types'

export const MESSENGER_STAGE_FOLDERS: MessengerFolderMeta[] = [
  { key: 'all', label: 'Все' },
  { key: 'lead', label: 'Лиды' },
  { key: 'waiting_slot', label: 'Ожидают слот' },
  { key: 'interview', label: 'Собеседование' },
  { key: 'test2', label: 'Тест 2' },
  { key: 'intro_day', label: 'Ознакомительный день' },
  { key: 'closed', label: 'Закрытые' },
]

export const MESSENGER_QUICK_FILTERS: Array<{ key: MessengerQuickFilter; label: string }> = [
  { key: 'all', label: 'Все' },
  { key: 'needs_reply', label: 'Нужен ответ' },
  { key: 'overdue', label: 'Просрочено' },
  { key: 'unread', label: 'Непрочитано' },
]

export const MESSENGER_CHANNEL_FILTERS: Array<{ key: MessengerChannelFilter; label: string }> = [
  { key: 'all', label: 'Все каналы' },
  { key: 'telegram', label: 'Telegram' },
  { key: 'max', label: 'MAX' },
]

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

export function compactPriorityLabel(bucket?: CandidateChatThread['priority_bucket'] | null): string | null {
  switch (bucket) {
    case 'overdue':
      return 'Просрочено'
    case 'needs_reply':
      return 'Нужен ответ'
    case 'blocked':
      return 'Есть блокер'
    case 'follow_up':
      return 'Нужен follow-up'
    case 'waiting_candidate':
      return 'Ждём ответ'
    case 'terminal':
      return 'Закрыт'
    default:
      return null
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

function normalizedThreadStatus(thread: CandidateChatThread): string {
  return `${thread.status_slug || ''} ${thread.status_label || ''}`.trim().toLowerCase()
}

function isWaitingSlotThread(normalizedStatus: string): boolean {
  return (
    normalizedStatus.includes('slot') ||
    normalizedStatus.includes('слот') ||
    normalizedStatus.includes('назнач') ||
    normalizedStatus.includes('согласован') ||
    normalizedStatus.includes('перенос') ||
    normalizedStatus.includes('ожидает слот') ||
    normalizedStatus.includes('ждет слот') ||
    normalizedStatus.includes('ждёт слот')
  )
}

function isInterviewThread(normalizedStatus: string): boolean {
  return (
    normalizedStatus.includes('interview') ||
    normalizedStatus.includes('собесед') ||
    normalizedStatus.includes('скрининг') ||
    normalizedStatus.includes('подтвержден') ||
    normalizedStatus.includes('подтверждён')
  )
}

function isTest2Thread(normalizedStatus: string): boolean {
  return normalizedStatus.includes('test2') || normalizedStatus.includes('тест 2') || normalizedStatus.includes('тест2')
}

function isIntroDayThread(normalizedStatus: string): boolean {
  return (
    normalizedStatus.includes('intro_day') ||
    normalizedStatus.includes('intro day') ||
    normalizedStatus.includes('ознаком')
  )
}

export function classifyThreadToFolder(thread: CandidateChatThread): MessengerStageFolder {
  const normalizedStatus = normalizedThreadStatus(thread)

  if (thread.is_archived || thread.is_terminal || thread.archived_at || normalizedStatus.includes('отказ') || normalizedStatus.includes('закрыт')) {
    return 'closed'
  }
  if (isIntroDayThread(normalizedStatus)) return 'intro_day'
  if (isTest2Thread(normalizedStatus)) return 'test2'
  if (isInterviewThread(normalizedStatus)) return 'interview'
  if (isWaitingSlotThread(normalizedStatus)) return 'waiting_slot'
  return 'lead'
}

export function matchesQuickFilter(thread: CandidateChatThread, quickFilter: MessengerQuickFilter): boolean {
  if (quickFilter === 'all') return true
  if (quickFilter === 'unread') return (thread.unread_count || 0) > 0

  const overdue = thread.priority_bucket === 'overdue' || (thread.sla_state || '').toLowerCase().includes('overdue')
  if (quickFilter === 'overdue') return overdue

  const needsReply =
    thread.requires_reply ||
    overdue ||
    ['needs_reply', 'blocked', 'follow_up'].includes(thread.priority_bucket || '')
  if (quickFilter === 'needs_reply') return Boolean(needsReply)

  return true
}

export function matchesChannelFilter(thread: CandidateChatThread, channelFilter: MessengerChannelFilter): boolean {
  if (channelFilter === 'all') return true
  return (thread.preferred_channel || '').toLowerCase() === channelFilter
}

function latestActivityTs(thread: CandidateChatThread): number {
  return new Date(thread.last_message_at || thread.last_message?.created_at || thread.created_at).getTime() || 0
}

function priorityRank(thread: CandidateChatThread): number {
  const overdue = thread.priority_bucket === 'overdue' || (thread.sla_state || '').toLowerCase().includes('overdue')
  if (overdue) return 0
  if (thread.requires_reply || ['needs_reply', 'blocked', 'follow_up'].includes(thread.priority_bucket || '')) return 1
  if ((thread.unread_count || 0) > 0) return 2
  return 3
}

export function sortThreadsForInbox(threads: CandidateChatThread[]): CandidateChatThread[] {
  return threads.slice().sort((left, right) => {
    const priorityDiff = priorityRank(left) - priorityRank(right)
    if (priorityDiff !== 0) return priorityDiff

    const unreadDiff = (right.unread_count || 0) - (left.unread_count || 0)
    if (unreadDiff !== 0) return unreadDiff

    const tsDiff = latestActivityTs(right) - latestActivityTs(left)
    if (tsDiff !== 0) return tsDiff

    return left.candidate_id - right.candidate_id
  })
}

export function buildFolderCounts(threads: CandidateChatThread[]): MessengerFolderSummary[] {
  return MESSENGER_STAGE_FOLDERS.map((folder) => {
    const folderThreads =
      folder.key === 'all' ? threads : threads.filter((thread) => classifyThreadToFolder(thread) === folder.key)

    return {
      ...folder,
      count: folderThreads.length,
      attentionCount: folderThreads.filter((thread) => matchesQuickFilter(thread, 'needs_reply')).length,
      unreadCount: folderThreads.filter((thread) => matchesQuickFilter(thread, 'unread')).length,
    }
  })
}

export function quietRelevanceScore(thread?: CandidateChatThread | null): string {
  return typeof thread?.relevance_score === 'number' ? String(Math.round(thread.relevance_score)) : '—'
}

export function relevanceScoreTitle(thread?: CandidateChatThread | null): string {
  return typeof thread?.relevance_score === 'number' ? `${Math.round(thread.relevance_score)}/100` : 'Нет оценки'
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

export function folderStatusLabel(thread: CandidateChatThread): string {
  const folder = classifyThreadToFolder(thread)
  const explicitStatus = compactThreadStatusLabel(thread.status_label, thread.priority_bucket)

  switch (folder) {
    case 'lead':
      return explicitStatus || 'Лид'
    case 'waiting_slot':
      return explicitStatus || 'Ожидает слот'
    case 'interview':
      return explicitStatus || 'Собеседование'
    case 'test2':
      return explicitStatus || 'Тест 2'
    case 'intro_day':
      return explicitStatus || 'Ознакомительный день'
    case 'closed':
      return explicitStatus || 'Закрыт'
    default:
      return explicitStatus
  }
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

export function removeThreadFromCache(
  payload: CandidateChatThreadsPayload | undefined,
  candidateId: number,
): CandidateChatThreadsPayload | undefined {
  if (!payload) return payload
  return {
    ...payload,
    threads: (payload.threads || []).filter((thread) => thread.candidate_id !== candidateId),
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
