import { memo, useEffect, useRef, useState, type MutableRefObject } from 'react'

import type { CandidateChannelHealth } from '@/api/services/candidates'
import {
  compactPriorityLabel,
  formatFullDateTime,
  normalizeTextLinks,
  previewText,
  quietRelevanceScore,
  relevanceScoreTitle,
  splitMessageText,
  messageAuthorLabel,
  threadAvatar,
} from './messenger.utils'
import { URL_RE } from './messenger.constants'
import type { CandidateChatTemplate, CandidateChatThread, GroupedMessageRow } from './messenger.types'

type MessageRow = Extract<GroupedMessageRow, { type: 'message' }>

function SendIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.85" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 14.75V5.5" />
      <path d="m5.75 9.75 4.25-4.25 4.25 4.25" />
    </svg>
  )
}

const MessengerDayDivider = memo(function MessengerDayDivider({ label }: { label: string }) {
  return (
    <div className="messenger-day-divider">
      <span>{label}</span>
    </div>
  )
})

const MessengerEventCard = memo(function MessengerEventCard({ row }: { row: MessageRow }) {
  return (
    <div
      className={`messenger-event-card is-${row.message.kind || 'system'}`}
      data-unread-anchor={row.unreadAnchor ? 'true' : 'false'}
    >
      {row.unreadAnchor ? <div className="messenger-unread-divider">Непрочитанные</div> : null}
      <div className="messenger-event-card__top">
        <div className="messenger-event-card__meta">
          <span>{messageAuthorLabel(row.message)}</span>
          <span>{formatFullDateTime(row.message.created_at)}</span>
        </div>
        {row.message.kind === 'bot' ? <span className="messenger-ai-badge">AI</span> : null}
      </div>
      <div className="messenger-event-card__text">{renderMessageText(row.message.text)}</div>
    </div>
  )
})

const MessengerMessageBubble = memo(function MessengerMessageBubble({ row }: { row: MessageRow }) {
  const links = normalizeTextLinks(row.message.text)

  return (
    <div
      className={`messenger-bubble message-bubble ${row.message.direction === 'outbound' ? 'is-own message-bubble--outgoing' : 'is-peer message-bubble--incoming'}`}
      data-unread-anchor={row.unreadAnchor ? 'true' : 'false'}
    >
      {row.unreadAnchor ? <div className="messenger-unread-divider">Непрочитанные</div> : null}
      <div className="messenger-bubble__meta">
        <span>{messageAuthorLabel(row.message)}</span>
        <span>{formatFullDateTime(row.message.created_at)}</span>
      </div>
      <div className="messenger-bubble__text">{renderMessageText(row.message.text)}</div>
      {links.length > 0 && (
        <div className="messenger-message__links">
          {links.map((link) => (
            <a key={link} href={link} target="_blank" rel="noreferrer" className="messenger-attachment-card">
              <strong>{link.replace(/^https?:\/\//, '')}</strong>
              <span>Открыть ссылку</span>
            </a>
          ))}
        </div>
      )}
    </div>
  )
})

const MessengerContextPanel = memo(function MessengerContextPanel({
  activeThread,
  channelHealth,
  isMobile,
  onClose,
}: {
  activeThread: CandidateChatThread
  channelHealth?: CandidateChannelHealth | null
  isMobile: boolean
  onClose: () => void
}) {
  const relevance = quietRelevanceScore(activeThread)
  const nextAction = compactPriorityLabel(activeThread.priority_bucket) || 'Открыть карточку'
  const preferredChannel =
    activeThread.preferred_channel === 'max'
      ? 'MAX'
      : activeThread.preferred_channel === 'telegram'
        ? 'Telegram'
        : channelHealth?.preferred_channel === 'max'
          ? 'MAX'
          : channelHealth?.preferred_channel === 'telegram'
            ? 'Telegram'
            : 'Не указан'
  const telegramUsername = activeThread.telegram_username || channelHealth?.telegram?.telegram_username || null
  const deliveryStatus = channelHealth?.last_outbound_delivery?.status || null
  const deliveryError = channelHealth?.last_outbound_delivery?.error || null

  return (
    <aside
      className={`messenger-context-panel ${isMobile ? 'is-mobile' : ''}`}
      data-testid="messenger-context-panel"
      aria-label="Контекст кандидата"
    >
      <div className="messenger-context-panel__header">
        <div>
          <div className="messenger-card__eyebrow">Контекст кандидата</div>
          <strong>{activeThread.title}</strong>
        </div>
        <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onClose} type="button">
          Закрыть
        </button>
      </div>

      <div className="messenger-context-panel__meta">
        <div className="messenger-context-panel__cell">
          <span>Город</span>
          <strong>{activeThread.city || 'Без города'}</strong>
        </div>
        <div className="messenger-context-panel__cell">
          <span>Этап</span>
          <strong>{activeThread.status_label || 'Без статуса'}</strong>
        </div>
        <div className="messenger-context-panel__cell">
          <span>AI relevance</span>
          <strong title={relevanceScoreTitle(activeThread)}>{relevance}</strong>
        </div>
        <div className="messenger-context-panel__cell">
          <span>Следующий шаг</span>
          <strong>{nextAction}</strong>
        </div>
      </div>

      <div className="messenger-context-panel__section">
        <span className="messenger-context-panel__label">Канал</span>
        <div className="messenger-context-panel__chips">
          <span className="messenger-inline-chip messenger-thread-card__chip messenger-thread-card__channel">{preferredChannel}</span>
          {activeThread.unread_count ? (
            <span className="messenger-inline-chip messenger-thread-card__chip is-info">
              {activeThread.unread_count} непрочит.
            </span>
          ) : null}
        </div>
      </div>

      {activeThread.risk_hint ? (
        <div className="messenger-context-panel__section">
          <span className="messenger-context-panel__label">Сигнал</span>
          <p>{activeThread.risk_hint}</p>
        </div>
      ) : null}

      {deliveryStatus || deliveryError ? (
        <div className="messenger-context-panel__section">
          <span className="messenger-context-panel__label">Доставка</span>
          <p>
            {deliveryStatus ? `Статус: ${deliveryStatus}.` : null}
            {deliveryError ? ` ${deliveryError}` : null}
          </p>
        </div>
      ) : null}

      <div className="messenger-context-panel__section">
        <span className="messenger-context-panel__label">Последний входящий</span>
        <p>{previewText(activeThread)}</p>
        <small>{formatFullDateTime(activeThread.last_message_at || activeThread.last_message?.created_at || activeThread.created_at)}</small>
      </div>

      <div className="messenger-context-panel__links">
        {activeThread.profile_url ? (
          <a className="ui-btn ui-btn--ghost ui-btn--sm" href={activeThread.profile_url}>
            Открыть карточку
          </a>
        ) : null}
        {telegramUsername ? (
          <a className="ui-btn ui-btn--ghost ui-btn--sm" href={`https://t.me/${telegramUsername.replace(/^@/, '')}`} target="_blank" rel="noreferrer">
            Telegram
          </a>
        ) : null}
        {preferredChannel === 'MAX' ? (
          <span className="ui-btn ui-btn--ghost ui-btn--sm is-static">MAX подключён</span>
        ) : null}
      </div>
    </aside>
  )
})

function renderMessageText(text?: string | null) {
  const value = splitMessageText(text)
  return (
    <>
      {value.map((segment, index) => {
        if (!segment) return null
        if (segment.match(URL_RE)) {
          return (
            <a
              key={`${segment}-${index}`}
              href={segment}
              target="_blank"
              rel="noreferrer"
              className="messenger-inline-link"
            >
              {segment}
            </a>
          )
        }
        return <span key={`${index}-${segment.slice(0, 8)}`}>{segment}</span>
      })}
    </>
  )
}

type ThreadViewProps = {
  activeThread: CandidateChatThread | null
  channelHealth?: CandidateChannelHealth | null
  isMobile: boolean
  isLoading: boolean
  isError: boolean
  groupedMessages: GroupedMessageRow[]
  messagesRef: MutableRefObject<HTMLDivElement | null>
  shouldStickToBottomRef: MutableRefObject<boolean>
  onMessagesScroll: (gap: number) => void
  onBack: () => void
  showContextPanel: boolean
  onToggleContextPanel: () => void
  onCloseContextPanel: () => void
  showTemplateTray: boolean
  selectedTemplateKey: string
  templates: CandidateChatTemplate[]
  onToggleTemplateTray: () => void
  onApplyTemplate: (template: CandidateChatTemplate) => void
  messageText: string
  onMessageTextChange: (value: string) => void
  onSend: () => void
  sendPending: boolean
  sendError: string | null
}

export function ThreadView({
  activeThread,
  channelHealth,
  isMobile,
  isLoading,
  isError,
  groupedMessages,
  messagesRef,
  shouldStickToBottomRef,
  onMessagesScroll,
  onBack,
  showContextPanel,
  onToggleContextPanel,
  onCloseContextPanel,
  showTemplateTray,
  selectedTemplateKey,
  templates,
  onToggleTemplateTray,
  onApplyTemplate,
  messageText,
  onMessageTextChange,
  onSend,
  sendPending,
  sendError,
}: ThreadViewProps) {
  const [hasHistoryAbove, setHasHistoryAbove] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const activeCandidateId = activeThread?.candidate_id ?? null
  const preferredChannel = channelHealth?.preferred_channel || activeThread?.preferred_channel || null

  useEffect(() => {
    setHasHistoryAbove(false)
  }, [activeCandidateId])

  useEffect(() => {
    const container = messagesRef.current
    if (!container || !activeCandidateId) return

    const frame = requestAnimationFrame(() => {
      const unreadAnchor = container.querySelector('[data-unread-anchor="true"]')
      if (unreadAnchor instanceof HTMLElement && typeof unreadAnchor.scrollIntoView === 'function') {
        unreadAnchor.scrollIntoView({ block: 'center', behavior: 'smooth' })
        return
      }

      if (shouldStickToBottomRef.current && typeof messagesEndRef.current?.scrollIntoView === 'function') {
        messagesEndRef.current.scrollIntoView({ block: 'end', behavior: 'smooth' })
      }
    })

    return () => {
      cancelAnimationFrame(frame)
    }
  }, [activeCandidateId, groupedMessages.length, messagesRef, shouldStickToBottomRef])

  return (
    <section className="messenger-thread-view messenger-chat messenger-chat-pane" aria-label="Чат с кандидатом">
      {!activeThread && (
        <div className="messenger-empty-state messenger-empty-state--hero">
          <strong>Выберите диалог слева</strong>
          <span>Откроется переписка с кандидатом и рабочие шаблоны для быстрого ответа.</span>
        </div>
      )}

      {activeThread && (
        <>
          <header className="messenger-thread-header messenger-chat-pane__header app-page__section-head">
            <div className="messenger-chat-pane__identity">
              {isMobile && (
                <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onBack} type="button">
                  ← К чатам
                </button>
              )}
              <div className="messenger-thread-card__avatar messenger-chat-pane__avatar">{threadAvatar(activeThread)}</div>
              <div className="messenger-chat-pane__identity-main">
                <div className="messenger-card__eyebrow messenger-chat-pane__eyebrow">Активный диалог</div>
                <div className="messenger-chat-pane__title-row">
                  <h2 className="section-title">
                    {activeThread.profile_url ? (
                      <a href={activeThread.profile_url} className="messenger-chat__title-link">
                        {activeThread.title}
                      </a>
                    ) : (
                      activeThread.title
                    )}
                  </h2>
                  {preferredChannel ? (
                    <span className={`status-badge status-badge--${preferredChannel === 'max' ? 'info' : 'success'}`}>
                      {preferredChannel === 'max' ? 'MAX' : 'Telegram'}
                    </span>
                  ) : null}
                </div>
                {activeThread.city || activeThread.status_label ? (
                  <div className="messenger-chat-pane__subtitle">
                    {activeThread.city ? <span>{activeThread.city}</span> : null}
                    {activeThread.city && activeThread.status_label ? <span className="messenger-chat-pane__subtitle-divider" aria-hidden="true" /> : null}
                    {activeThread.status_label ? <span>{activeThread.status_label}</span> : null}
                  </div>
                ) : null}
              </div>
            </div>
            <div className="messenger-chat-pane__actions">
              {activeThread.profile_url ? (
                <a className="ui-btn ui-btn--ghost ui-btn--sm" href={activeThread.profile_url}>
                  Карточка
                </a>
              ) : null}
              <button className="ui-btn ui-btn--ghost ui-btn--sm" type="button" onClick={onToggleContextPanel}>
                {showContextPanel ? 'Скрыть контекст' : 'Контекст'}
              </button>
            </div>
          </header>

          <div className={`messenger-chat__shell ${showContextPanel ? 'is-context-open' : ''}`}>
            <div className="messenger-conversation">
              <div
                className={`messenger-messages ${hasHistoryAbove ? 'is-scrolled' : ''}`}
                data-testid="messenger-messages"
                ref={messagesRef}
                onScroll={(event) => {
                  const node = event.currentTarget
                  const gap = node.scrollHeight - node.scrollTop - node.clientHeight
                  setHasHistoryAbove(node.scrollTop > 12)
                  onMessagesScroll(gap)
                }}
              >
                <div className="messenger-messages-inner">
                  {isLoading && <p className="subtitle">Загрузка переписки…</p>}
                  {isError && <p className="text-danger">Не удалось загрузить сообщения</p>}
                  {!isLoading && groupedMessages.length === 0 && (
                    <div className="messenger-empty-state messenger-empty-state--compact">
                      <strong>История пока пуста</strong>
                      <span>Отправьте первое сообщение или дождитесь ответа кандидата.</span>
                    </div>
                  )}

                  {groupedMessages.map((row) =>
                    row.type === 'divider' ? (
                      <MessengerDayDivider key={row.key} label={row.label} />
                    ) : row.message.kind === 'bot' || row.message.kind === 'system' ? (
                      <MessengerEventCard key={row.message.id} row={row} />
                    ) : (
                      <MessengerMessageBubble key={row.message.id} row={row} />
                    ),
                  )}
                  <div ref={messagesEndRef} className="messenger-messages-anchor" aria-hidden="true" />
                </div>
              </div>

              <div
                className={`messenger-input-area messenger-composer message-input-area ${messageText.trim() ? 'is-typing' : ''}`}
                data-testid="messenger-composer"
              >
                <div className="messenger-composer__tools">
                  <button className={`messenger-template-chip ${showTemplateTray ? 'is-active' : ''}`} onClick={onToggleTemplateTray} type="button">
                    Шаблоны
                  </button>
                </div>

                {showTemplateTray && (
                  <div className="messenger-composer__templates">
                    {templates.slice(0, 6).map((item) => (
                      <button
                        key={item.key}
                        className={`messenger-template-chip ${selectedTemplateKey === item.key ? 'is-active' : ''}`}
                        onClick={() => onApplyTemplate(item)}
                        type="button"
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                )}

                <div className="messenger-composer__input-row">
                  <textarea
                    className="message-input"
                    rows={1}
                    value={messageText}
                    onChange={(event) => onMessageTextChange(event.target.value)}
                    placeholder="Написать кандидату…"
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        if (messageText.trim()) onSend()
                      }
                    }}
                  />
                  <button
                    className="ui-btn ui-btn--primary messenger-composer__send"
                    onClick={onSend}
                    disabled={sendPending || !messageText.trim()}
                    aria-label={sendPending ? 'Отправка сообщения' : 'Отправить сообщение'}
                    title={sendPending ? 'Отправка...' : 'Отправить'}
                    data-state={sendPending ? 'pending' : 'idle'}
                    type="button"
                  >
                    <SendIcon />
                  </button>
                </div>
                {sendError ? <div className="messenger-error">{sendError}</div> : null}
              </div>

              {showContextPanel ? (
                <MessengerContextPanel
                  activeThread={activeThread}
                  channelHealth={channelHealth}
                  isMobile={isMobile}
                  onClose={onCloseContextPanel}
                />
              ) : null}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
