import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchCandidateChatMessages,
  fetchCandidateChatThreads,
  markCandidateChatThreadRead,
  sendCandidateThreadMessage,
  type CandidateChatMessage,
  type CandidateChatPayload,
  type CandidateChatThread,
  type CandidateChatThreadsPayload,
} from '@/api/services/messenger'
import { useIsMobile } from '@/app/hooks/useIsMobile'

const formatThreadTime = (value?: string | null) => {
  if (!value) return ''
  const dt = new Date(value)
  const today = new Date()
  const sameDay = dt.toDateString() === today.toDateString()
  return sameDay
    ? dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    : dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

const formatMessageTime = (value?: string | null) => {
  if (!value) return ''
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const previewText = (thread?: CandidateChatThread) => {
  const last = thread?.last_message
  if (!last) return 'Нет сообщений'
  return (last.text || '').trim() || 'Сообщение'
}

const messageAuthorLabel = (message: CandidateChatMessage) => {
  if (message.direction === 'inbound') return message.author || 'Кандидат'
  if ((message.author || '').trim().toLowerCase() === 'bot') return 'Бот'
  return 'Вы'
}

const readThreadCache = (
  payload: CandidateChatThreadsPayload | undefined,
  candidateId: number,
): CandidateChatThreadsPayload | undefined => {
  if (!payload) return payload
  return {
    ...payload,
    threads: (payload.threads || []).map((thread) =>
      thread.candidate_id === candidateId ? { ...thread, unread_count: 0 } : thread,
    ),
  }
}

export function MessengerPage() {
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()
  const [activeCandidateId, setActiveCandidateId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [messageText, setMessageText] = useState('')
  const [sendError, setSendError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ tone: 'success' | 'error'; message: string } | null>(null)
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission | 'unsupported'>(() => {
    if (typeof Notification === 'undefined') return 'unsupported'
    return Notification.permission
  })
  const messagesRef = useRef<HTMLDivElement | null>(null)

  const showToast = (message: string, tone: 'success' | 'error' = 'success') => {
    setToast({ message, tone })
    window.clearTimeout((showToast as { _timer?: number })._timer)
    ;(showToast as { _timer?: number })._timer = window.setTimeout(() => setToast(null), 2200)
  }

  const threadsQuery = useQuery<CandidateChatThreadsPayload>({
    queryKey: ['candidate-chat-threads'],
    queryFn: fetchCandidateChatThreads,
    refetchInterval: 5000,
    refetchOnWindowFocus: true,
  })

  const filteredThreads = useMemo(() => {
    const term = searchQuery.trim().toLowerCase()
    const threads = threadsQuery.data?.threads || []
    if (!term) return threads
    return threads.filter((thread) =>
      [thread.title, thread.city, thread.telegram_username, previewText(thread)]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term)),
    )
  }, [searchQuery, threadsQuery.data?.threads])

  useEffect(() => {
    if (activeCandidateId || !filteredThreads.length) return
    setActiveCandidateId(filteredThreads[0].candidate_id)
  }, [activeCandidateId, filteredThreads])

  useEffect(() => {
    if (!activeCandidateId) return
    if (filteredThreads.some((thread) => thread.candidate_id === activeCandidateId)) return
    setActiveCandidateId(filteredThreads[0]?.candidate_id ?? null)
  }, [activeCandidateId, filteredThreads])

  const activeThread = useMemo(
    () => threadsQuery.data?.threads.find((thread) => thread.candidate_id === activeCandidateId) || null,
    [activeCandidateId, threadsQuery.data?.threads],
  )

  const messagesQuery = useQuery<CandidateChatPayload>({
    queryKey: ['candidate-chat', activeCandidateId],
    queryFn: () => fetchCandidateChatMessages(activeCandidateId as number, 80),
    enabled: Boolean(activeCandidateId),
    refetchInterval: activeCandidateId ? 3000 : false,
    refetchOnWindowFocus: Boolean(activeCandidateId),
  })

  const chatMessages = useMemo(
    () => ((messagesQuery.data?.messages || []).slice().reverse()),
    [messagesQuery.data?.messages],
  )

  const markReadMutation = useMutation({
    mutationFn: markCandidateChatThreadRead,
    onSuccess: (_data, candidateId) => {
      queryClient.setQueryData<CandidateChatThreadsPayload>(
        ['candidate-chat-threads'],
        (prev) => readThreadCache(prev, candidateId),
      )
    },
  })
  const markThreadRead = markReadMutation.mutate

  useEffect(() => {
    if (!activeCandidateId) return
    if (!activeThread?.unread_count) return
    markThreadRead(activeCandidateId)
  }, [activeCandidateId, activeThread?.unread_count, markThreadRead])

  useEffect(() => {
    const container = messagesRef.current
    if (!container) return
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight
    })
  }, [chatMessages.length, activeCandidateId])

  const sendMutation = useMutation({
    mutationFn: async (text: string) => {
      if (!activeCandidateId) throw new Error('Выберите чат')
      return sendCandidateThreadMessage(activeCandidateId, {
        text,
        client_request_id: String(Date.now()),
      })
    },
    onSuccess: async () => {
      setMessageText('')
      setSendError(null)
      await Promise.all([
        messagesQuery.refetch(),
        threadsQuery.refetch(),
      ])
    },
    onError: (error: unknown) => {
      setSendError((error as Error).message || 'Не удалось отправить сообщение')
    },
  })

  const handleEnableNotifications = async () => {
    if (typeof Notification === 'undefined') return
    try {
      const permission = await Notification.requestPermission()
      setNotificationPermission(permission)
      showToast(
        permission === 'granted' ? 'Системные уведомления включены' : 'Системные уведомления недоступны',
        permission === 'granted' ? 'success' : 'error',
      )
    } catch {
      setNotificationPermission('denied')
      showToast('Не удалось включить системные уведомления', 'error')
    }
  }

  return (
    <div className={`page app-page app-page--ops messenger-page ${isMobile && activeCandidateId ? 'is-mobile-chat-open' : ''}`}>
      <header className="glass panel messenger-header app-page__hero">
        <div>
          <h1 className="title title--lg">Чаты с кандидатами</h1>
          <p className="subtitle">Здесь отображаются ответы кандидатов и история переписки по Telegram.</p>
        </div>
        <div className="ui-section-header__actions">
          {notificationPermission === 'default' && (
            <button className="ui-btn ui-btn--ghost" onClick={handleEnableNotifications}>
              Включить системные уведомления
            </button>
          )}
          <button className="ui-btn ui-btn--primary" onClick={() => threadsQuery.refetch()}>
            Обновить
          </button>
        </div>
      </header>

      <div className="messenger-layout">
        <aside className="glass panel messenger-sidebar app-page__section" aria-label="Чаты кандидатов">
          <div className="messenger-sidebar__header app-page__section-head">
            <div>
              <h2 className="section-title">Диалоги</h2>
              <p className="subtitle">{threadsQuery.data?.threads.length || 0} кандидатов</p>
            </div>
          </div>
          <div className="messenger-sidebar__search">
            <input
              placeholder="Поиск кандидата"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>
          {threadsQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {threadsQuery.isError && <p className="text-danger">Не удалось загрузить список чатов</p>}
          {!threadsQuery.isLoading && filteredThreads.length === 0 && (
            <p className="subtitle">Сообщений от кандидатов пока нет.</p>
          )}
          <div className="messenger-thread-list">
            {filteredThreads.map((thread) => (
              <button
                key={thread.candidate_id}
                className={`messenger-thread${thread.candidate_id === activeCandidateId ? ' is-active' : ''}`}
                onClick={() => setActiveCandidateId(thread.candidate_id)}
              >
                <div className="messenger-thread__avatar">
                  {(thread.title || 'К').slice(0, 2).toUpperCase()}
                </div>
                <div className="messenger-thread__info">
                  <div className="messenger-thread__row">
                    <span className="messenger-thread__title">{thread.title}</span>
                    <span className="messenger-thread__time">
                      {formatThreadTime(thread.last_message_at || thread.last_message?.created_at || thread.created_at)}
                    </span>
                  </div>
                  <div className="messenger-thread__row messenger-thread__preview">
                    <span>{thread.city || 'Город не указан'} · {previewText(thread)}</span>
                    {thread.unread_count ? <span className="messenger-thread__badge">{thread.unread_count}</span> : null}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <section className="glass panel messenger-chat app-page__section" aria-label="Чат с кандидатом">
          {!activeThread && <p className="subtitle">Выберите чат слева.</p>}
          {activeThread && (
            <>
              <div className="messenger-chat__header app-page__section-head">
                <div>
                  {isMobile && (
                    <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setActiveCandidateId(null)}>
                      ← К чатам
                    </button>
                  )}
                  <h2 className="section-title">{activeThread.title}</h2>
                  <p className="subtitle">
                    {activeThread.city || 'Город не указан'}
                    {activeThread.status_label ? ` · ${activeThread.status_label}` : ''}
                    {activeThread.telegram_username ? ` · @${activeThread.telegram_username}` : ''}
                  </p>
                </div>
                {activeThread.profile_url ? (
                  <a className="ui-btn ui-btn--ghost" href={activeThread.profile_url}>
                    Открыть карточку
                  </a>
                ) : null}
              </div>

              <div className="messenger-messages" ref={messagesRef}>
                {messagesQuery.isLoading && <p className="subtitle">Загрузка переписки…</p>}
                {messagesQuery.isError && <p className="text-danger">Не удалось загрузить сообщения</p>}
                {!messagesQuery.isLoading && chatMessages.length === 0 && (
                  <p className="subtitle">Сообщений пока нет.</p>
                )}
                {chatMessages.map((message) => {
                  const isOwn = message.direction === 'outbound'
                  return (
                    <div key={message.id} className={`messenger-message ${isOwn ? 'is-own' : ''}`}>
                      <div className="messenger-message__meta">
                        <span>{messageAuthorLabel(message)}</span>
                        <span>{formatMessageTime(message.created_at)}</span>
                      </div>
                      <div className="messenger-message__text">{message.text || '...'}</div>
                    </div>
                  )
                })}
              </div>

              <div className="messenger-composer">
                <textarea
                  rows={4}
                  value={messageText}
                  onChange={(event) => setMessageText(event.target.value)}
                  placeholder="Написать кандидату…"
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      const payload = messageText.trim()
                      if (payload) sendMutation.mutate(payload)
                    }
                  }}
                />
                <div className="messenger-composer__actions">
                  {notificationPermission === 'denied' && (
                    <span className="subtitle">Системные уведомления заблокированы браузером.</span>
                  )}
                  {sendError && <div className="messenger-error">{sendError}</div>}
                  <button
                    className="ui-btn ui-btn--primary"
                    onClick={() => {
                      const payload = messageText.trim()
                      if (payload) sendMutation.mutate(payload)
                    }}
                    disabled={sendMutation.isPending || !messageText.trim()}
                  >
                    {sendMutation.isPending ? 'Отправка…' : 'Отправить'}
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      {toast && (
        <div className="toast" data-tone={toast.tone}>
          {toast.message}
        </div>
      )}
    </div>
  )
}
