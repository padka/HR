import type { MutableRefObject } from 'react'

import { normalizeTextLinks, splitMessageText, messageAuthorLabel, formatFullDateTime, threadAvatar } from './messenger.utils'
import { URL_RE } from './messenger.constants'
import type { CandidateChatTemplate, CandidateChatThread, GroupedMessageRow } from './messenger.types'

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
  cityLabel?: string | null
  isMobile: boolean
  isLoading: boolean
  isError: boolean
  groupedMessages: GroupedMessageRow[]
  messagesRef: MutableRefObject<HTMLDivElement | null>
  onMessagesScroll: (gap: number) => void
  onBack: () => void
  onOpenDetails: () => void
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
  cityLabel,
  isMobile,
  isLoading,
  isError,
  groupedMessages,
  messagesRef,
  onMessagesScroll,
  onBack,
  onOpenDetails,
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
  return (
    <section className="glass panel messenger-chat-pane app-page__section" aria-label="Чат с кандидатом">
      {!activeThread && (
        <div className="messenger-empty-state messenger-empty-state--hero">
          <strong>Выберите диалог слева</strong>
          <span>Откроются переписка, score кандидата и рабочий контекст для следующего действия.</span>
        </div>
      )}

      {activeThread && (
        <>
          <header className="messenger-chat-pane__header app-page__section-head">
            <div className="messenger-chat-pane__identity">
              {isMobile && (
                <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onBack}>
                  ← К чатам
                </button>
              )}
              <div className="messenger-thread-card__avatar messenger-chat-pane__avatar">{threadAvatar(activeThread)}</div>
              <div className="messenger-chat-pane__identity-main">
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
                {cityLabel ? <div className="messenger-chat-pane__subtitle">{cityLabel}</div> : null}
              </div>
            </div>
            <div className="messenger-chat-pane__actions">
              <button className="ui-btn ui-btn--primary ui-btn--sm" onClick={onOpenDetails}>
                Детали
              </button>
              {activeThread.profile_url ? (
                <a className="ui-btn ui-btn--ghost ui-btn--sm" href={activeThread.profile_url}>
                  Карточка
                </a>
              ) : null}
            </div>
          </header>

          <div className="messenger-conversation">
            <div
              className="messenger-messages"
              ref={messagesRef}
              onScroll={(event) => {
                const node = event.currentTarget
                const gap = node.scrollHeight - node.scrollTop - node.clientHeight
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
                    <div className="messenger-event-card__meta">
                      <span>{messageAuthorLabel(row.message)}</span>
                      <span>{formatFullDateTime(row.message.created_at)}</span>
                    </div>
                    <div className="messenger-event-card__text">{renderMessageText(row.message.text)}</div>
                  </div>
                ) : (
                  <div
                    key={row.message.id}
                    className={`messenger-bubble ${row.message.direction === 'outbound' ? 'is-own' : 'is-peer'}`}
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

            <div className="messenger-composer" data-testid="messenger-composer">
              <div className="messenger-composer__tools">
                <button className={`messenger-template-chip ${showTemplateTray ? 'is-active' : ''}`} onClick={onToggleTemplateTray}>
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
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              )}

              <div className="messenger-composer__input-row">
                <textarea
                  rows={2}
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
                >
                  {sendPending ? 'Отправка…' : 'Отправить'}
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
