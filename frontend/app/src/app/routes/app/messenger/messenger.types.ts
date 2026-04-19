import type {
  CandidateChatMessage,
  CandidateChatPayload,
  CandidateChatTemplate,
  CandidateChatThread,
  CandidateChatThreadsPayload,
} from '@/api/services/messenger'

export type {
  CandidateChatMessage,
  CandidateChatPayload,
  CandidateChatTemplate,
  CandidateChatThread,
  CandidateChatThreadsPayload,
}

export type ThreadTone = 'neutral' | 'info' | 'warning' | 'danger' | 'success'

export type MessengerStageFolder =
  | 'all'
  | 'lead'
  | 'waiting_slot'
  | 'interview'
  | 'test2'
  | 'intro_day'
  | 'closed'

export type MessengerQuickFilter = 'all' | 'needs_reply' | 'overdue' | 'unread'

export type MessengerChannelFilter = 'all' | 'telegram' | 'max'

export type MessengerFolderMeta = {
  key: MessengerStageFolder
  label: string
}

export type MessengerFolderSummary = MessengerFolderMeta & {
  count: number
  attentionCount: number
  unreadCount: number
}

export type GroupedMessageRow =
  | { type: 'divider'; key: string; label: string }
  | { type: 'message'; message: CandidateChatMessage; unreadAnchor: boolean }
