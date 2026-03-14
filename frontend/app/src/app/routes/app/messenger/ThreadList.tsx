import { useEffect, useMemo, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

import { fadeIn, listItem, stagger } from '@/shared/motion'

import {
  compactThreadStatusLabel,
  formatThreadTime,
  previewText,
  priorityLabel,
  priorityTone,
  scoreTone,
  threadAvatar,
} from './messenger.utils'
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
  const priorityText = priorityLabel(thread.priority_bucket)
  const showPriorityChip = Boolean(thread.priority_bucket && !['waiting_candidate', 'system'].includes(thread.priority_bucket))
  const aiLabel =
    typeof thread.relevance_score === 'number'
      ? `AI ${Math.round(thread.relevance_score)}`
      : thread.relevance_level
        ? `AI ${thread.relevance_level}`
        : null
  const secondaryChip = showPriorityChip
    ? { tone: bucketTone, label: priorityText, modifier: 'messenger-thread-card__priority' }
    : aiLabel
      ? { tone: aiTone, label: aiLabel, modifier: 'messenger-thread-card__ai' }
      : null

  return (
    <button
      className={`messenger-thread-card thread-item ${isActive ? 'is-active thread-item--active' : ''} ${thread.last_message_kind === 'bot' || thread.last_message_kind === 'system' ? 'is-system-thread' : ''}`}
      onClick={onSelect}
      data-priority={thread.priority_bucket || 'waiting_candidate'}
      aria-pressed={isActive}
      type="button"
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
          {thread.unread_count ? (
            <span className="messenger-thread-card__unread" aria-label={`${thread.unread_count} непрочитанных`}>
              <span className="messenger-thread-card__unread-dot" aria-hidden="true" />
              <span className="messenger-thread-card__badge">{thread.unread_count}</span>
            </span>
          ) : null}
        </div>
        <div className="messenger-thread-card__meta-line">
          <span className="messenger-thread-card__meta-item">{thread.city || 'Без города'}</span>
          <span className="messenger-thread-card__meta-separator" aria-hidden="true" />
          <span className="messenger-thread-card__meta-item">{statusLabel}</span>
        </div>
        {secondaryChip ? (
          <div className="messenger-thread-card__chips">
            <span className={`messenger-inline-chip messenger-thread-card__chip ${secondaryChip.modifier} is-${secondaryChip.tone}`}>
              {secondaryChip.label}
            </span>
          </div>
        ) : null}
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
  const prefersReducedMotion = useReducedMotion()
  const [search, setSearch] = useState('')
  const [hasAnimatedOnce, setHasAnimatedOnce] = useState(false)

  useEffect(() => {
    setHasAnimatedOnce(true)
  }, [])

  const searchValue = search.trim().toLowerCase()
  const visibleThreads = useMemo(
    () =>
      threads.filter((thread) => {
        if (!searchValue) return true
        const haystack = [
          thread.title,
          thread.city,
          thread.status_label,
          thread.last_message_preview,
          thread.last_message?.preview,
          thread.last_message?.text,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        return haystack.includes(searchValue)
      }),
    [searchValue, threads],
  )
  const animationKey = `${searchValue}|${visibleThreads.length}`
  const firstRenderAnimation = !hasAnimatedOnce && !prefersReducedMotion

  return (
    <aside className="messenger-thread-list-panel messenger-sidebar messenger-inbox-rail" aria-label="Чаты кандидатов">
      <div className="messenger-thread-list-header messenger-sidebar__toolbar">
        <div className="messenger-sidebar__search-slot">
          <input
            className="thread-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по кандидату, городу или статусу"
            aria-label="Поиск по чатам"
          />
        </div>
        <button
          className="ui-btn ui-btn--ghost ui-btn--sm messenger-sidebar__refresh"
          onClick={onRefresh}
          type="button"
          aria-label="Обновить список чатов"
        >
          Обновить
        </button>
      </div>

      <div className="messenger-thread-list-body">
        {isLoading && <p className="subtitle">Загрузка диалогов…</p>}
        {isError && <p className="text-danger">Не удалось загрузить список чатов</p>}
        {!isLoading && visibleThreads.length === 0 && (
          <div className="messenger-empty-state messenger-empty-state--compact">
            <strong>{threads.length === 0 ? 'Ничего не найдено' : 'Поиск не дал совпадений'}</strong>
            <span>
              {threads.length === 0
                ? 'Когда появятся кандидаты или новые сообщения, они появятся здесь.'
                : 'Попробуйте другое имя, город или статус.'}
            </span>
          </div>
        )}

        <div className="messenger-thread-list" data-testid="messenger-thread-list">
          <motion.div
            key={animationKey}
            className="messenger-thread-list__content"
            variants={firstRenderAnimation ? stagger(0.03) : undefined}
            initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
            animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
            transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
          >
            {visibleThreads.map((thread) => (
              <motion.div key={thread.candidate_id} variants={firstRenderAnimation ? listItem : undefined}>
                <InboxThreadCard
                  thread={thread}
                  isActive={thread.candidate_id === activeCandidateId}
                  onSelect={() => onSelect(thread.candidate_id)}
                />
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </aside>
  )
}
