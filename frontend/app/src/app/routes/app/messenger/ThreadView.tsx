import { useEffect, useState, type MutableRefObject } from 'react'

import { normalizeTextLinks, splitMessageText, messageAuthorLabel, formatFullDateTime, threadAvatar } from './messenger.utils'
import { URL_RE } from './messenger.constants'
import type { CandidateChatTemplate, CandidateChatThread, GroupedMessageRow } from './messenger.types'

function SendIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4.25 10h9.5" />
      <path d="m10.75 3.75 5.5 6.25-5.5 6.25" />
    </svg>
  )
}

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
  isMobile: boolean
  isLoading: boolean
  isError: boolean
  groupedMessages: GroupedMessageRow[]
  messagesRef: MutableRefObject<HTMLDivElement | null>
  onMessagesScroll: (gap: number) => void
  onBack: () => void
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
  isMobile,
  isLoading,
  isError,
  groupedMessages,
  messagesRef,
  onMessagesScroll,
  onBack,
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

  useEffect(() => {
    setHasHistoryAbove(false)
  }, [activeThread?.candidate_id])

  return (
    <section className="messenger-chat messenger-chat-pane" aria-label="Чат с кандидатом">
      {!activeThread && (
        <div className="messenger-empty-state messenger-empty-state--hero">
          <strong>Выберите диалог слева</strong>
          <span>Откроется переписка с кандидатом и рабочие шаблоны для быстрого ответа.</span>
        </div>
      )}

      {activeThread && (
        <>
          <header className="messenger-chat-pane__header app-page__section-head">
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
            </div>
          </header>

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
                  <div key={row.key} className="messenger-day-divider">
                    <span>{row.label}</span>
                  </div>
                ) : row.message.kind === 'bot' || row.message.kind === 'system' ? (
                  <div
                    key={row.message.id}
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
                ) : (
                  <div
                    key={row.message.id}
                    className={`messenger-bubble message-bubble ${row.message.direction === 'outbound' ? 'is-own message-bubble--outgoing' : 'is-peer message-bubble--incoming'}`}
                    data-unread-anchor={row.unreadAnchor ? 'true' : 'false'}
                  >
                    {row.unreadAnchor ? <div className="messenger-unread-divider">Непрочитанные</div> : null}
                    <div className="messenger-bubble__meta">
                      <span>{messageAuthorLabel(row.message)}</span>
                      <span>{formatFullDateTime(row.message.created_at)}</span>
                    </div>
                    <div className="messenger-bubble__text">{renderMessageText(row.message.text)}</div>
                    {normalizeTextLinks(row.message.text).length > 0 && (
                      <div className="messenger-message__links">
                        {normalizeTextLinks(row.message.text).map((link) => (
                          <a key={link} href={link} target="_blank" rel="noreferrer" className="messenger-attachment-card">
                            <strong>{link.replace(/^https?:\/\//, '')}</strong>
                            <span>Открыть ссылку</span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ),
              )}
            </div>

            <div
              className={`messenger-composer message-input-area ${messageText.trim() ? 'is-typing' : ''}`}
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
          </div>
        </>
      )}
    </section>
  )
}
