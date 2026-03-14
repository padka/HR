import { formatThreadTime, previewText, compactThreadStatusLabel, priorityTone, scoreTone, threadAvatar } from './messenger.utils'
import type { CandidateChatThread } from './messenger.types'

function InboxThreadCard({
  thread,
  isActive,
  onSelect,
}: {
  thread: CandidateChatThread
  isActive: boolean
  onSelect: () => void
}) {
  const bucketTone = priorityTone(thread.priority_bucket)
  const aiTone = scoreTone(thread.relevance_score, thread.relevance_level)
  const preview = previewText(thread)
  const statusLabel = compactThreadStatusLabel(thread.status_label, thread.priority_bucket)
  return (
    <button
      className={`messenger-thread-card ${isActive ? 'is-active' : ''} ${thread.last_message_kind === 'bot' || thread.last_message_kind === 'system' ? 'is-system-thread' : ''}`}
      onClick={onSelect}
      data-priority={thread.priority_bucket || 'waiting_candidate'}
    >
      <span className={`messenger-thread-card__indicator tone-${bucketTone}`} />
      <div className="messenger-thread-card__avatar">{threadAvatar(thread)}</div>
      <div className="messenger-thread-card__body">
        <div className="messenger-thread-card__top">
          <strong className="messenger-thread-card__title">{thread.title}</strong>
          <span className="messenger-thread-card__time">{formatThreadTime(thread.last_message_at || thread.created_at)}</span>
        </div>
        <div className="messenger-thread-card__preview-row">
          <span className={`messenger-thread-card__preview is-${thread.last_message_kind || 'candidate'}`}>{preview}</span>
          {thread.unread_count ? <span className="messenger-thread-card__badge">{thread.unread_count}</span> : null}
        </div>
        <div className="messenger-thread-card__chips">
          <span className="messenger-inline-chip messenger-thread-card__chip">{thread.city || 'Без города'}</span>
          <span className={`messenger-inline-chip messenger-thread-card__chip is-${aiTone}`}>
            AI {typeof thread.relevance_score === 'number' ? `${Math.round(thread.relevance_score)}/100` : thread.relevance_level || '—'}
          </span>
          <span className="messenger-inline-chip messenger-thread-card__chip is-status">{statusLabel}</span>
        </div>
      </div>
    </button>
  )
}

type ThreadListProps = {
  threads: CandidateChatThread[]
  activeCandidateId: number | null
  isLoading: boolean
  isError: boolean
  onRefresh: () => void
  onSelect: (candidateId: number) => void
}

export function ThreadList({
  threads,
  activeCandidateId,
  isLoading,
  isError,
  onRefresh,
  onSelect,
}: ThreadListProps) {
  return (
    <aside className="glass panel messenger-inbox-rail app-page__section" aria-label="Чаты кандидатов">
      <div className="messenger-sidebar__header app-page__section-head">
        <div className="messenger-sidebar__header-copy">
          <h1 className="section-title">Чаты кандидатов</h1>
          <p className="subtitle">{threads.length} кандидатов в общем списке</p>
        </div>
        <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onRefresh}>
          Обновить
        </button>
      </div>

      {isLoading && <p className="subtitle">Загрузка диалогов…</p>}
      {isError && <p className="text-danger">Не удалось загрузить список чатов</p>}
      {!isLoading && threads.length === 0 && (
        <div className="messenger-empty-state messenger-empty-state--compact">
          <strong>Ничего не найдено</strong>
          <span>Когда появятся кандидаты или новые сообщения, они появятся здесь.</span>
        </div>
      )}

      <div className="messenger-thread-list" data-testid="messenger-thread-list">
        {threads.map((thread) => (
          <InboxThreadCard
            key={thread.candidate_id}
            thread={thread}
            isActive={thread.candidate_id === activeCandidateId}
            onSelect={() => onSelect(thread.candidate_id)}
          />
        ))}
      </div>
    </aside>
  )
}
