import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { ModalPortal } from '@/shared/components/ModalPortal'
import { fadeIn, slideInRight } from '@/shared/motion'
import { useCandidateChat, useCandidateAi } from './candidate-detail.api'

type CandidateChatDrawerProps = {
  candidateId: number
  isOpen: boolean
  onClose: () => void
  initialDraftText?: { text: string; nonce: number } | null
}

export function CandidateChatDrawer({
  candidateId,
  isOpen,
  onClose,
  initialDraftText,
}: CandidateChatDrawerProps) {
  const { query, sendMutation, markReadMutation, waitForUpdates } = useCandidateChat(candidateId, isOpen)
  const ai = useCandidateAi(candidateId)
  const reduceMotion = useReducedMotion()
  const [chatText, setChatText] = useState('')
  const [aiDraftsOpen, setAiDraftsOpen] = useState(false)
  const [aiDraftMode, setAiDraftMode] = useState<'short' | 'neutral' | 'supportive'>('neutral')
  const chatMessagesRef = useRef<HTMLDivElement | null>(null)
  const chatTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const chatMessages = (query.data?.messages || []).slice().reverse()

  useEffect(() => {
    if (!initialDraftText) return
    setChatText(initialDraftText.text)
    requestAnimationFrame(() => chatTextareaRef.current?.focus())
  }, [initialDraftText])

  useEffect(() => {
    if (!isOpen) return
    void query.refetch()
  }, [isOpen, query])

  useEffect(() => {
    if (!isOpen) return
    let active = true
    let since = query.data?.latest_message_at || null
    const controller = new AbortController()

    const loop = async () => {
      while (active) {
        try {
          const payload = await waitForUpdates({
            since,
            timeout: 25,
            limit: 50,
            signal: controller.signal,
          })
          if (!active) return
          if (payload.latest_message_at) since = payload.latest_message_at
          if (payload.updated) {
            await query.refetch()
          }
        } catch (error) {
          if (!active) return
          if ((error as Error).name === 'AbortError') return
          await new Promise((resolve) => window.setTimeout(resolve, 1000))
        }
      }
    }

    void loop()
    return () => {
      active = false
      controller.abort()
    }
  }, [isOpen, query, waitForUpdates])

  useEffect(() => {
    if (!isOpen) return
    markReadMutation.mutate(candidateId)
  }, [candidateId, isOpen, markReadMutation])

  useEffect(() => {
    if (!isOpen || chatMessages.length === 0) return
    markReadMutation.mutate(candidateId)
  }, [candidateId, chatMessages.length, isOpen, markReadMutation])

  useEffect(() => {
    if (!isOpen) return
    const container = chatMessagesRef.current
    if (!container) return
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight
    })
  }, [chatMessages.length, isOpen])

  return (
    <ModalPortal>
      <AnimatePresence>
        {isOpen ? (
          <motion.div
            className="drawer-overlay candidate-drawer-overlay candidate-drawer-overlay--chat"
            onClick={(event) => event.target === event.currentTarget && onClose()}
            initial={reduceMotion ? false : fadeIn.initial}
            animate={reduceMotion ? undefined : fadeIn.animate}
            exit={reduceMotion ? undefined : fadeIn.exit}
            transition={reduceMotion ? { duration: 0 } : fadeIn.transition}
          >
            <motion.aside
              className="candidate-chat-drawer candidate-chat-drawer--chat glass"
              onClick={(event) => event.stopPropagation()}
              data-testid="candidate-chat-drawer"
              initial={reduceMotion ? false : slideInRight.initial}
              animate={reduceMotion ? undefined : slideInRight.animate}
              exit={reduceMotion ? undefined : slideInRight.exit}
              transition={reduceMotion ? { duration: 0 } : slideInRight.transition}
            >
              <header className="candidate-chat-drawer__header">
                <div>
                  <h3 className="candidate-chat-drawer__title">Чат с кандидатом</h3>
                  <p className="subtitle">Ответ будет отправлен через Telegram</p>
                </div>
                <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
              </header>

              <div className="candidate-chat-drawer__body">
                {query.isLoading && <p className="subtitle">Загрузка сообщений…</p>}
                {query.isError && (
                  <ApiErrorBanner
                    error={query.error}
                    title="Не удалось загрузить сообщения"
                    onRetry={() => query.refetch()}
                    className="glass panel"
                  />
                )}
                {chatMessages.length === 0 && !query.isLoading && <p className="subtitle">Сообщений пока нет.</p>}
                {chatMessages.length > 0 && (
                  <div className="candidate-chat-drawer__messages" ref={chatMessagesRef}>
                    {chatMessages.map((message) => {
                      const isOutbound = message.direction === 'outbound'
                      const isBot = isOutbound && (message.author || '').trim().toLowerCase() === 'bot'
                      const authorLabel = isBot ? 'Бот' : isOutbound ? (message.author || 'Вы') : (message.author || 'Кандидат')

                      return (
                        <div
                          key={message.id}
                          className={`candidate-chat-message ${isOutbound ? 'candidate-chat-message--outbound' : 'candidate-chat-message--inbound'} ${isBot ? 'candidate-chat-message--bot' : ''}`}
                        >
                          <div className="candidate-chat-message__text">{message.text}</div>
                          <div className="candidate-chat-message__meta">
                            <span className="candidate-chat-message__author">{authorLabel}</span>
                            <span>{new Date(message.created_at).toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}</span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="candidate-chat-drawer__footer">
                {aiDraftsOpen && (
                  <div className="cd-ai-drafts glass">
                    <div className="cd-ai-drafts__header">
                      <div className="cd-ai-drafts__title">Черновики ответа</div>
                      <div className="cd-ai-drafts__modes">
                        {(['short', 'neutral', 'supportive'] as const).map((mode) => (
                          <button
                            key={mode}
                            type="button"
                            className={`cd-ai-drafts__mode ${aiDraftMode === mode ? 'cd-ai-drafts__mode--active' : ''}`}
                            onClick={() => {
                              setAiDraftMode(mode)
                              ai.draftsMutation.mutate(mode)
                            }}
                            disabled={ai.draftsMutation.isPending}
                          >
                            {mode === 'short' ? 'Коротко' : mode === 'neutral' ? 'Нейтр.' : 'Поддерж.'}
                          </button>
                        ))}
                      </div>
                      <button type="button" className="ui-btn ui-btn--ghost" onClick={() => setAiDraftsOpen(false)}>
                        Закрыть
                      </button>
                    </div>

                    {ai.draftsMutation.isPending && <p className="subtitle">Генерация…</p>}
                    {ai.draftsMutation.error && (
                      <p className="subtitle subtitle--danger">
                        AI: {(ai.draftsMutation.error as Error).message}
                      </p>
                    )}
                    {ai.draftsMutation.data?.analysis && (
                      <div className="cd-ai-drafts__analysis">
                        <div className="cd-ai-drafts__analysis-label">Анализ переписки</div>
                        <div className="cd-ai-drafts__analysis-text">{ai.draftsMutation.data.analysis}</div>
                      </div>
                    )}
                    {ai.draftsMutation.data?.drafts?.length ? (
                      <div className="cd-ai-drafts__list">
                        {ai.draftsMutation.data.drafts.map((draft, index) => (
                          <div key={`${index}-${draft.reason}`} className="cd-ai-drafts__item">
                            <div className="cd-ai-drafts__text">{draft.text}</div>
                            <div className="cd-ai-drafts__actions">
                              <span className="cd-ai-drafts__reason">{draft.reason}</span>
                              <button
                                type="button"
                                className="ui-btn ui-btn--primary"
                                onClick={() => {
                                  setChatText(draft.text)
                                  setAiDraftsOpen(false)
                                  requestAnimationFrame(() => chatTextareaRef.current?.focus())
                                }}
                              >
                                Вставить
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
                <div className="candidate-chat-drawer__composer">
                  <textarea
                    ref={chatTextareaRef}
                    rows={3}
                    value={chatText}
                    onChange={(event) => setChatText(event.target.value)}
                    placeholder="Написать сообщение…"
                    className="candidate-chat-drawer__input"
                    data-testid="chat-textarea"
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        const text = chatText.trim()
                        if (!text) return
                        sendMutation.mutate(text, {
                          onSuccess: () => {
                            setChatText('')
                            void query.refetch()
                          },
                        })
                      }
                    }}
                  />
                  <div className="candidate-chat-drawer__actions">
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      onClick={() => {
                        const next = !aiDraftsOpen
                        setAiDraftsOpen(next)
                        if (next) ai.draftsMutation.mutate(aiDraftMode)
                      }}
                      disabled={ai.draftsMutation.isPending}
                    >
                      Черновики ответа
                    </button>
                    <button
                      className="ui-btn ui-btn--primary"
                      onClick={() => {
                        const text = chatText.trim()
                        if (!text) return
                        sendMutation.mutate(text, {
                          onSuccess: () => {
                            setChatText('')
                            void query.refetch()
                          },
                        })
                      }}
                      disabled={sendMutation.isPending}
                    >
                      {sendMutation.isPending ? 'Отправка…' : 'Отправить'}
                    </button>
                  </div>
                </div>
              </div>
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </ModalPortal>
  )
}
