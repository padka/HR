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

export type GroupedMessageRow =
  | { type: 'divider'; key: string; label: string }
  | { type: 'message'; message: CandidateChatMessage; unreadAnchor: boolean }
