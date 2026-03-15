import { memo, useEffect, useMemo, useRef, useState } from 'react'
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

function TrashIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6.5 6.75v7" />
      <path d="M10 6.75v7" />
      <path d="M13.5 6.75v7" />
      <path d="M4.75 5.25h10.5" />
      <path d="M7.25 5.25V4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1v1.25" />
      <path d="m5.75 5.25.65 9.1a1.5 1.5 0 0 0 1.49 1.4h4.22a1.5 1.5 0 0 0 1.49-1.4l.65-9.1" />
    </svg>
  )
}

const InboxThreadCard = memo(function InboxThreadCard({
  thread,
  isActive,
  isPendingArchive,
  onArchive,
  onSelect,
}: {
  thread: CandidateChatThread
  isActive: boolean
  isPendingArchive: boolean
  onArchive?: () => void
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
    <div
      className={`messenger-thread-card thread-item ${isActive ? 'is-active thread-item--active' : ''} ${thread.last_message_kind === 'bot' || thread.last_message_kind === 'system' ? 'is-system-thread' : ''}`}
      onClick={() => {
        if (isPendingArchive) return
        onSelect()
      }}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget || isPendingArchive) return
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        onSelect()
      }}
      data-priority={thread.priority_bucket || 'waiting_candidate'}
      role="button"
      tabIndex={isPendingArchive ? -1 : 0}
      aria-pressed={isActive}
      aria-disabled={isPendingArchive || undefined}
    >
      {onArchive ? (
        <button
          className="messenger-thread-card__delete"
          type="button"
          aria-label={`Удалить чат ${thread.title}`}
          disabled={isPendingArchive}
          onClick={(event) => {
            event.stopPropagation()
            if (!window.confirm(`Удалить диалог с ${thread.title}?`)) return
            onArchive()
          }}
        >
          <TrashIcon />
        </button>
      ) : null}
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
    </div>
  )
})

const THREAD_ARCHIVE_ACTION_WIDTH = 108
const THREAD_ARCHIVE_REVEAL_THRESHOLD = 44
const THREAD_ARCHIVE_COMMIT_THRESHOLD = 84

const SwipeableThreadRow = memo(function SwipeableThreadRow({
  thread,
  isActive,
  isPendingArchive,
  onArchive,
  onSelect,
}: {
  thread: CandidateChatThread
  isActive: boolean
  isPendingArchive: boolean
  onArchive: (candidateId: number) => void
  onSelect: (candidateId: number) => void
}) {
  const [offsetX, setOffsetX] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const offsetRef = useRef(0)
  const pointerStateRef = useRef<{
    pointerId: number
    startX: number
    startY: number
    dragging: boolean
    horizontalIntent: boolean
    moved: boolean
  } | null>(null)

  const resetSwipe = () => {
    pointerStateRef.current = null
    setIsDragging(false)
    setOffsetX(0)
    offsetRef.current = 0
  }

  const commitArchive = () => {
    resetSwipe()
    onArchive(thread.candidate_id)
  }

  const actionOpacity = Math.min(1, Math.abs(offsetX) / THREAD_ARCHIVE_REVEAL_THRESHOLD)

  return (
    <div className={`messenger-thread-swipe ${offsetX < 0 ? 'is-swipe-active' : ''}`}>
      <button
        className={`messenger-thread-swipe__action ${offsetX < 0 ? 'is-revealed' : ''}`}
        onClick={(event) => {
          event.stopPropagation()
          commitArchive()
        }}
        disabled={isPendingArchive}
        aria-label={`Удалить диалог ${thread.title}`}
        type="button"
        style={{ opacity: actionOpacity }}
      >
        Удалить
      </button>

      <div
        className={`messenger-thread-swipe__track ${isDragging ? 'is-dragging' : ''}`}
        data-testid={`messenger-thread-row-${thread.candidate_id}`}
        style={{ transform: `translateX(${offsetX}px)` }}
        onPointerDown={(event) => {
          if (event.pointerType === 'mouse') return
          pointerStateRef.current = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            dragging: false,
            horizontalIntent: false,
            moved: false,
          }
        }}
        onPointerMove={(event) => {
          const state = pointerStateRef.current
          if (!state || state.pointerId !== event.pointerId) return

          const deltaX = event.clientX - state.startX
          const deltaY = event.clientY - state.startY

          if (!state.horizontalIntent) {
            if (Math.abs(deltaY) > 8 && Math.abs(deltaY) > Math.abs(deltaX)) {
              resetSwipe()
              return
            }
            if (Math.abs(deltaX) < 6) return
            state.horizontalIntent = true
          }

          state.dragging = true
          state.moved = true
          setIsDragging(true)

          const nextOffset = Math.max(-THREAD_ARCHIVE_ACTION_WIDTH, Math.min(0, deltaX))
          const resolvedOffset = nextOffset > 0 ? 0 : nextOffset
          offsetRef.current = resolvedOffset
          setOffsetX(resolvedOffset)
        }}
        onPointerUp={(event) => {
          const state = pointerStateRef.current
          if (!state || state.pointerId !== event.pointerId) return

          if (!state.dragging) {
            pointerStateRef.current = null
            return
          }

          if (Math.abs(offsetRef.current) >= THREAD_ARCHIVE_COMMIT_THRESHOLD) {
            commitArchive()
            return
          }

          setIsDragging(false)
          const resolvedOffset =
            Math.abs(offsetRef.current) >= THREAD_ARCHIVE_REVEAL_THRESHOLD ? -THREAD_ARCHIVE_ACTION_WIDTH : 0
          offsetRef.current = resolvedOffset
          setOffsetX(resolvedOffset)
          pointerStateRef.current = null
        }}
        onPointerCancel={resetSwipe}
      >
        <InboxThreadCard
          thread={thread}
          isActive={isActive}
          isPendingArchive={isPendingArchive}
          onArchive={() => onArchive(thread.candidate_id)}
          onSelect={() => {
            if (pointerStateRef.current?.moved) {
              pointerStateRef.current = null
              return
            }
            if (offsetX < 0) {
              resetSwipe()
              return
            }
            onSelect(thread.candidate_id)
          }}
        />
      </div>
    </div>
  )
})

type ThreadListProps = {
  threads: CandidateChatThread[]
  activeCandidateId: number | null
  isLoading: boolean
  isError: boolean
  archivePendingCandidateId: number | null
  onRefresh: () => void
  onArchive: (candidateId: number) => void
  onSelect: (candidateId: number) => void
}

export function ThreadList({
  threads,
  activeCandidateId,
  isLoading,
  isError,
  archivePendingCandidateId,
  onRefresh,
  onArchive,
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
                <SwipeableThreadRow
                  thread={thread}
                  isActive={thread.candidate_id === activeCandidateId}
                  isPendingArchive={archivePendingCandidateId === thread.candidate_id}
                  onArchive={onArchive}
                  onSelect={onSelect}
                />
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </aside>
  )
}
