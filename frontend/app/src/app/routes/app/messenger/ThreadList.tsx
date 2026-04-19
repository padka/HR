import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

import { fadeIn, listItem, stagger } from '@/shared/motion'

import {
  MESSENGER_CHANNEL_FILTERS,
  MESSENGER_QUICK_FILTERS,
  compactPriorityLabel,
  formatThreadTime,
  folderStatusLabel,
  matchesQuickFilter,
  previewText,
  priorityLabel,
  priorityTone,
  quietRelevanceScore,
  relevanceScoreTitle,
  threadAvatar,
} from './messenger.utils'
import type {
  CandidateChatThread,
  MessengerChannelFilter,
  MessengerFolderSummary,
  MessengerQuickFilter,
  MessengerStageFolder,
} from './messenger.types'

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
  const preview = previewText(thread)
  const statusLabel = folderStatusLabel(thread)
  const priorityText = compactPriorityLabel(thread.priority_bucket) || priorityLabel(thread.priority_bucket)
  const scoreLabel = quietRelevanceScore(thread)
  const hasUnread = (thread.unread_count || 0) > 0

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
          <div className="messenger-thread-card__title-stack">
            <strong className="messenger-thread-card__title">{thread.title}</strong>
            <span className="messenger-thread-card__meta-item">{thread.city || 'Без города'}</span>
          </div>
          <div className="messenger-thread-card__signals">
            <span className="messenger-thread-card__score" title={relevanceScoreTitle(thread)}>
              {scoreLabel}
            </span>
            {hasUnread ? (
              <span className="messenger-thread-card__unread" aria-label={`${thread.unread_count} непрочитанных`}>
                <span className="messenger-thread-card__unread-dot" aria-hidden="true" />
                <span className="messenger-thread-card__badge">{thread.unread_count}</span>
              </span>
            ) : null}
          </div>
        </div>
        <div className="messenger-thread-card__status-line">
          <span className="messenger-inline-chip messenger-thread-card__chip is-status">{statusLabel}</span>
          {priorityText && !['В работе', 'Ждём кандидата'].includes(priorityText) ? (
            <span className={`messenger-inline-chip messenger-thread-card__chip messenger-thread-card__priority is-${bucketTone}`}>
              {priorityText}
            </span>
          ) : null}
          {thread.preferred_channel ? (
            <span className="messenger-inline-chip messenger-thread-card__chip messenger-thread-card__channel">
              {thread.preferred_channel === 'max' ? 'MAX' : 'Telegram'}
            </span>
          ) : null}
        </div>
        <div className="messenger-thread-card__preview-row">
          <span className={`messenger-thread-card__preview is-${thread.last_message_kind || 'candidate'}`}>{preview}</span>
        </div>
        <div className="messenger-thread-card__bottom">
          <span className="messenger-thread-card__meta-item">{formatThreadTime(thread.last_message_at || thread.created_at)}</span>
          {thread.requires_reply ? <span className="messenger-thread-card__reply-flag">Нужен ответ</span> : null}
        </div>
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
  allThreads: CandidateChatThread[]
  folderScopedThreads: CandidateChatThread[]
  folderCounts: MessengerFolderSummary[]
  activeCandidateId: number | null
  activeFolder: MessengerStageFolder
  quickFilter: MessengerQuickFilter
  channelFilter: MessengerChannelFilter
  searchValue: string
  isLoading: boolean
  isError: boolean
  archivePendingCandidateId: number | null
  onFolderChange: (folder: MessengerStageFolder) => void
  onQuickFilterChange: (filter: MessengerQuickFilter) => void
  onChannelFilterChange: (filter: MessengerChannelFilter) => void
  onSearchChange: (value: string) => void
  onRefresh: () => void
  onArchive: (candidateId: number) => void
  onSelect: (candidateId: number) => void
}

export function ThreadList({
  threads,
  allThreads,
  folderScopedThreads,
  folderCounts,
  activeCandidateId,
  activeFolder,
  quickFilter,
  channelFilter,
  searchValue,
  isLoading,
  isError,
  archivePendingCandidateId,
  onFolderChange,
  onQuickFilterChange,
  onChannelFilterChange,
  onSearchChange,
  onRefresh,
  onArchive,
  onSelect,
}: ThreadListProps) {
  const prefersReducedMotion = useReducedMotion()
  const [isFolderDrawerOpen, setIsFolderDrawerOpen] = useState(false)
  const [hasAnimatedOnce, setHasAnimatedOnce] = useState(false)

  useEffect(() => {
    setHasAnimatedOnce(true)
  }, [])

  useEffect(() => {
    if (!isFolderDrawerOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsFolderDrawerOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isFolderDrawerOpen])

  useEffect(() => {
    if (searchValue.trim()) setIsFolderDrawerOpen(false)
  }, [searchValue])

  const searchQuery = searchValue.trim()
  const isSearching = searchQuery.length > 0
  const activeFolderSummary = useMemo(
    () => folderCounts.find((folder) => folder.key === activeFolder) || folderCounts[0],
    [activeFolder, folderCounts],
  )
  const allFolderSummary = useMemo(
    () => folderCounts.find((folder) => folder.key === 'all') || folderCounts[0],
    [folderCounts],
  )
  const quickFilterCounts = useMemo(
    () => ({
      all: folderScopedThreads.length,
      needs_reply: folderScopedThreads.filter((thread) => matchesQuickFilter(thread, 'needs_reply')).length,
      overdue: folderScopedThreads.filter((thread) => matchesQuickFilter(thread, 'overdue')).length,
      unread: folderScopedThreads.filter((thread) => matchesQuickFilter(thread, 'unread')).length,
    }),
    [folderScopedThreads],
  )
  const animationKey = `${searchQuery}|${threads.length}`
  const firstRenderAnimation = !hasAnimatedOnce && !prefersReducedMotion
  const visibleCountLabel = isSearching ? `Найдено ${threads.length}` : `${threads.length} диалогов`
  const scopeLabel = isSearching
    ? 'Поиск по всем чатам'
    : activeFolderSummary
      ? `${activeFolderSummary.label} · ${activeFolderSummary.count}`
      : 'Все чаты'

  return (
    <aside className="messenger-thread-list-panel messenger-sidebar messenger-inbox-rail" aria-label="Чаты кандидатов">
      <div className={`messenger-inbox-workspace ${isFolderDrawerOpen ? 'is-folder-drawer-open' : ''}`}>
        <button
          type="button"
          className={`messenger-folder-backdrop ${isFolderDrawerOpen ? 'is-open' : ''}`}
          onClick={() => setIsFolderDrawerOpen(false)}
          aria-label="Закрыть меню папок"
          tabIndex={isFolderDrawerOpen ? 0 : -1}
        />

        <nav
          id="messenger-folder-drawer"
          className="messenger-folder-rail"
          aria-label="Папки чатов"
          aria-hidden={!isFolderDrawerOpen}
        >
          <div className="messenger-folder-rail__scroller" data-testid="messenger-folder-rail">
            {folderCounts.map((folder) => (
              <button
                key={folder.key}
                type="button"
                className={`messenger-folder-pill ${folder.key === activeFolder ? 'is-active' : ''}`}
                onClick={() => {
                  onFolderChange(folder.key)
                  setIsFolderDrawerOpen(false)
                }}
                aria-pressed={folder.key === activeFolder}
              >
                <span className="messenger-folder-pill__label">{folder.label}</span>
                <span className="messenger-folder-pill__count">{folder.count}</span>
                {folder.attentionCount > 0 ? (
                  <span className="messenger-folder-pill__alert" aria-label={`${folder.attentionCount} требуют ответа`}>
                    {folder.attentionCount}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        </nav>

        <div className="messenger-inbox-shell">
          <div className="messenger-thread-list-header messenger-sidebar__toolbar">
            <div className="messenger-thread-toolbar__row messenger-thread-toolbar__row--top">
              <button
                className={`messenger-folder-trigger ${isFolderDrawerOpen ? 'is-active' : ''}`}
                type="button"
                onClick={() => setIsFolderDrawerOpen((prev) => !prev)}
                aria-expanded={isFolderDrawerOpen}
                aria-controls="messenger-folder-drawer"
              >
                <span className="messenger-folder-trigger__eyebrow">Папки</span>
                <span className="messenger-folder-trigger__body">
                  <strong>{isSearching ? 'Все чаты' : activeFolderSummary?.label || 'Все'}</strong>
                  <span>{scopeLabel}</span>
                </span>
                <span className="messenger-folder-trigger__count">
                  {isSearching ? allFolderSummary?.count || allThreads.length : activeFolderSummary?.count || 0}
                </span>
              </button>
              <button
                className="ui-btn ui-btn--ghost ui-btn--sm messenger-sidebar__refresh"
                onClick={onRefresh}
                type="button"
                aria-label="Обновить список чатов"
              >
                Обновить
              </button>
            </div>

            <div className="messenger-sidebar__search-slot">
              <input
                className="thread-search"
                type="search"
                value={searchValue}
                onChange={(event) => onSearchChange(event.target.value)}
                placeholder="Поиск по ФИО, городу или сообщению"
                aria-label="Поиск по чатам"
              />
            </div>

            <div className="messenger-thread-toolbar__meta">
              <strong>{visibleCountLabel}</strong>
              <span>{scopeLabel}</span>
            </div>

            <div className="messenger-thread-toolbar__row" data-testid="messenger-quick-filters">
              {MESSENGER_QUICK_FILTERS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`messenger-filter-chip ${item.key === quickFilter ? 'is-active' : ''}`}
                  onClick={() => onQuickFilterChange(item.key)}
                  aria-pressed={item.key === quickFilter}
                  disabled={isSearching}
                  title={isSearching ? 'Фильтры временно отключены во время глобального поиска' : undefined}
                >
                  <span>{item.label}</span>
                  <strong>{quickFilterCounts[item.key]}</strong>
                </button>
              ))}
            </div>
            <div className="messenger-thread-toolbar__row messenger-thread-toolbar__row--channels">
              {MESSENGER_CHANNEL_FILTERS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`messenger-filter-chip messenger-filter-chip--channel ${item.key === channelFilter ? 'is-active' : ''}`}
                  onClick={() => onChannelFilterChange(item.key)}
                  aria-pressed={item.key === channelFilter}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="messenger-thread-list-body">
            {isLoading && <p className="subtitle">Загрузка диалогов…</p>}
            {isError && <p className="text-danger">Не удалось загрузить список чатов</p>}
            {!isLoading && threads.length === 0 && (
              <div className="messenger-empty-state messenger-empty-state--compact">
                <strong>
                  {isSearching
                    ? 'По запросу ничего не найдено'
                    : allThreads.length === 0
                      ? 'Диалоги пока не появились'
                      : 'В текущей папке ничего не найдено'}
                </strong>
                <span>
                  {isSearching
                    ? 'Попробуйте другое ФИО, город или фрагмент сообщения.'
                    : allThreads.length === 0
                      ? 'Когда появятся новые сообщения кандидатов, они отобразятся здесь.'
                      : 'Смените папку или фильтр, чтобы увидеть другие диалоги.'}
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
                {threads.map((thread) => (
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
        </div>
      </div>
    </aside>
  )
}
