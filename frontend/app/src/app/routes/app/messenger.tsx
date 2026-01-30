import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiFetch, queryClient } from '@/api/client'
import { useProfile } from '@/app/hooks/useProfile'

type ThreadItem = {
  id: number
  type: 'direct' | 'group'
  title: string
  created_at: string
  last_message?: {
    text?: string | null
    created_at?: string | null
    sender_type?: string | null
    sender_id?: number | null
    type?: string | null
  }
  unread_count?: number
}

type ThreadsPayload = {
  threads: ThreadItem[]
  latest_event_at?: string | null
}

type MessageAttachment = {
  id: number
  filename: string
  mime_type?: string | null
  size?: number | null
}

type CandidateCard = {
  id: number
  name: string
  city: string
  status_label?: string | null
  status_slug?: string | null
  telegram_id?: number | null
  profile_url?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
}

type TaskInfo = {
  candidate_id: number
  status: 'pending' | 'accepted' | 'declined'
  created_at?: string | null
  decided_at?: string | null
  decided_by_type?: string | null
  decided_by_id?: number | null
  decision_comment?: string | null
}

type MessageItem = {
  id: number
  thread_id: number
  sender_type: string
  sender_id: number
  sender_label?: string | null
  type?: string | null
  text?: string | null
  created_at: string
  edited_at?: string | null
  attachments: MessageAttachment[]
  read_by_count?: number
  read_by_total?: number
  task?: TaskInfo
  candidate?: CandidateCard
}

type ThreadMember = {
  type: string
  id: number
  role?: string
  name?: string
  last_read_at?: string | null
  is_placeholder?: boolean
}

type MessagesPayload = {
  messages: MessageItem[]
  has_more: boolean
  latest_message_at?: string | null
  latest_activity_at?: string | null
  members?: ThreadMember[]
}

type RecruiterOption = {
  id: number
  name: string
}

type CandidateListPayload = {
  items: Array<{
    id: number
    fio?: string | null
    city?: string | null
    status?: { label?: string | null; tone?: string | null }
  }>
}

const formatBytes = (size?: number | null) => {
  if (!size) return ''
  const units = ['Б', 'КБ', 'МБ', 'ГБ']
  let value = size
  let idx = 0
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024
    idx += 1
  }
  return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`
}

const formatTime = (value?: string | null) => {
  if (!value) return ''
  return new Date(value).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

const formatThreadTime = (value?: string | null) => {
  if (!value) return ''
  const dt = new Date(value)
  const today = new Date()
  const sameDay = dt.toDateString() === today.toDateString()
  return sameDay
    ? dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    : dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

const previewText = (thread?: ThreadItem) => {
  const last = thread?.last_message
  if (!last) return 'Нет сообщений'
  if (last.type === 'candidate_task') return 'Передан кандидат'
  if (last.type === 'system') return last.text || 'Системное сообщение'
  return last.text || 'Сообщение'
}

const messageStatusLabel = (msg: MessageItem) => {
  const total = msg.read_by_total || 0
  const read = msg.read_by_count || 0
  if (total === 0) return ''
  if (read >= total) return 'Прочитано'
  if (read > 0) return `Прочитано ${read}/${total}`
  return 'Не прочитано'
}

function ModalPortal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}

export function MessengerPage() {
  const profile = useProfile()
  const principalType = profile.data?.principal.type
  const principalId = profile.data?.principal.id
  const isAdmin = principalType === 'admin'

  const [activeThreadId, setActiveThreadId] = useState<number | null>(null)
  const [messageText, setMessageText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [sendError, setSendError] = useState<string | null>(null)
  const [newChatTarget, setNewChatTarget] = useState('')
  const [groupTitle, setGroupTitle] = useState('')
  const [groupMembers, setGroupMembers] = useState<number[]>([])
  const [memberSelection, setMemberSelection] = useState<number[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [toast, setToast] = useState<{ tone: 'success' | 'error' | 'warning'; message: string } | null>(null)
  const [showMembersModal, setShowMembersModal] = useState(false)
  const [showCandidateModal, setShowCandidateModal] = useState(false)
  const [candidateSearch, setCandidateSearch] = useState('')
  const [candidateNote, setCandidateNote] = useState('')
  const [taskDeclineTarget, setTaskDeclineTarget] = useState<MessageItem | null>(null)
  const [taskDeclineComment, setTaskDeclineComment] = useState('')

  const showToast = (message: string, tone: 'success' | 'error' | 'warning' = 'success') => {
    setToast({ message, tone })
    window.clearTimeout((showToast as any)._t)
    ;(showToast as any)._t = window.setTimeout(() => setToast(null), 2400)
  }

  const threadsQuery = useQuery<ThreadsPayload>({
    queryKey: ['staff-threads'],
    queryFn: () => apiFetch('/staff/threads'),
  })

  const recruitersQuery = useQuery<RecruiterOption[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
    staleTime: 60_000,
  })

  const activeThread = useMemo(
    () => threadsQuery.data?.threads.find((t) => t.id === activeThreadId) || null,
    [threadsQuery.data, activeThreadId],
  )

  const messagesQuery = useQuery<MessagesPayload>({
    queryKey: ['staff-messages', activeThreadId],
    queryFn: () => apiFetch(`/staff/threads/${activeThreadId}/messages?limit=80`),
    enabled: Boolean(activeThreadId),
  })

  const candidateSearchQuery = useQuery<CandidateListPayload>({
    queryKey: ['candidate-search', candidateSearch],
    queryFn: () => apiFetch(`/candidates?search=${encodeURIComponent(candidateSearch)}&per_page=8`),
    enabled: showCandidateModal && candidateSearch.trim().length > 1,
    staleTime: 10_000,
  })

  const markReadMutation = useMutation({
    mutationFn: async (threadId: number) => apiFetch(`/staff/threads/${threadId}/read`, { method: 'POST' }),
  })

  const sendMutation = useMutation({
    mutationFn: async () => {
      if (!activeThreadId) throw new Error('Выберите чат')
      const text = messageText.trim()
      if (!text && files.length === 0) throw new Error('Сообщение пустое')

      if (files.length > 0) {
        const form = new FormData()
        if (text) form.append('text', text)
        files.forEach((file) => form.append('files', file))
        return apiFetch<MessageItem>(`/staff/threads/${activeThreadId}/messages`, {
          method: 'POST',
          body: form,
        })
      }

      return apiFetch<MessageItem>(`/staff/threads/${activeThreadId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ text }),
      })
    },
    onSuccess: (data: MessageItem) => {
      setMessageText('')
      setFiles([])
      setSendError(null)
      queryClient.setQueryData(['staff-messages', activeThreadId], (prev?: MessagesPayload) => {
        if (!prev) return prev
        const existing = prev.messages.find((msg) => msg.id === data.id)
        const messages = existing ? prev.messages : [...prev.messages, data]
        return { ...prev, messages }
      })
      threadsQuery.refetch()
    },
    onError: (err) => {
      const raw = (err as Error).message || 'Ошибка отправки'
      try {
        const parsed = JSON.parse(raw)
        if (parsed?.detail?.message) {
          setSendError(parsed.detail.message)
          return
        }
        if (parsed?.detail) {
          setSendError(typeof parsed.detail === 'string' ? parsed.detail : raw)
          return
        }
      } catch {
        // ignore JSON parse errors
      }
      setSendError(raw)
    },
  })

  const createThreadMutation = useMutation({
    mutationFn: async (payload: { type: 'direct' | 'group'; title?: string; members: Array<{ type: string; id: number }> }) =>
      apiFetch('/staff/threads', { method: 'POST', body: JSON.stringify(payload) }),
    onSuccess: (data: any) => {
      threadsQuery.refetch()
      setActiveThreadId(data?.id || null)
      setNewChatTarget('')
      setGroupTitle('')
      setGroupMembers([])
    },
  })

  const addMembersMutation = useMutation({
    mutationFn: async (memberIds: number[]) => {
      if (!activeThreadId) throw new Error('Чат не выбран')
      return apiFetch<{ members: ThreadMember[] }>(`/staff/threads/${activeThreadId}/members`, {
        method: 'POST',
        body: JSON.stringify({ members: memberIds.map((id) => ({ type: 'recruiter', id })) }),
      })
    },
    onSuccess: (data: { members: ThreadMember[] }) => {
      queryClient.setQueryData(['staff-messages', activeThreadId], (prev?: MessagesPayload) =>
        prev ? { ...prev, members: data.members } : prev,
      )
      setMemberSelection([])
      showToast('Участники добавлены', 'success')
    },
    onError: () => showToast('Не удалось обновить участников', 'error'),
  })

  const removeMemberMutation = useMutation({
    mutationFn: async (member: ThreadMember) => {
      if (!activeThreadId) throw new Error('Чат не выбран')
      return apiFetch<{ members: ThreadMember[] }>(`/staff/threads/${activeThreadId}/members/${member.type}/${member.id}`, { method: 'DELETE' })
    },
    onSuccess: (data: { members: ThreadMember[] }) => {
      queryClient.setQueryData(['staff-messages', activeThreadId], (prev?: MessagesPayload) =>
        prev ? { ...prev, members: data.members } : prev,
      )
      showToast('Участник удалён', 'warning')
    },
    onError: () => showToast('Не удалось удалить участника', 'error'),
  })

  const sendCandidateMutation = useMutation({
    mutationFn: async (candidateId: number) => {
      if (!activeThreadId) throw new Error('Чат не выбран')
      return apiFetch<MessageItem>(`/staff/threads/${activeThreadId}/candidate`, {
        method: 'POST',
        body: JSON.stringify({ candidate_id: candidateId, note: candidateNote.trim() || null }),
      })
    },
    onSuccess: (data: MessageItem) => {
      queryClient.setQueryData(['staff-messages', activeThreadId], (prev?: MessagesPayload) => {
        if (!prev) return prev
        return { ...prev, messages: [...prev.messages, data] }
      })
      setCandidateNote('')
      setCandidateSearch('')
      setShowCandidateModal(false)
      showToast('Кандидат передан', 'success')
      threadsQuery.refetch()
    },
    onError: () => showToast('Не удалось отправить кандидата', 'error'),
  })

  const acceptTaskMutation = useMutation({
    mutationFn: async (messageId: number) =>
      apiFetch<MessageItem>(`/staff/messages/${messageId}/candidate/accept`, {
        method: 'POST',
        body: JSON.stringify({ comment: null }),
      }),
    onSuccess: (data: MessageItem) => {
      queryClient.setQueryData(['staff-messages', activeThreadId], (prev?: MessagesPayload) => {
        if (!prev) return prev
        const messages = prev.messages.map((msg) => (msg.id === data.id ? data : msg))
        return { ...prev, messages }
      })
      showToast('Кандидат принят', 'success')
    },
    onError: () => showToast('Не удалось принять кандидата', 'error'),
  })

  const declineTaskMutation = useMutation({
    mutationFn: async ({ messageId, comment }: { messageId: number; comment: string }) =>
      apiFetch<MessageItem>(`/staff/messages/${messageId}/candidate/decline`, {
        method: 'POST',
        body: JSON.stringify({ comment }),
      }),
    onSuccess: (data: MessageItem) => {
      queryClient.setQueryData(['staff-messages', activeThreadId], (prev?: MessagesPayload) => {
        if (!prev) return prev
        const messages = prev.messages.map((msg) => (msg.id === data.id ? data : msg))
        return { ...prev, messages }
      })
      setTaskDeclineTarget(null)
      setTaskDeclineComment('')
      showToast('Передача отклонена', 'warning')
    },
    onError: () => showToast('Не удалось отклонить задачу', 'error'),
  })

  useEffect(() => {
    if (activeThreadId) {
      markReadMutation.mutate(activeThreadId)
    }
  }, [activeThreadId])

  useEffect(() => {
    setMemberSelection([])
  }, [activeThreadId])

  useEffect(() => {
    if (!threadsQuery.data) return
    let isActive = true
    let since = threadsQuery.data.latest_event_at || new Date().toISOString()
    let controller: AbortController | null = null

    const loop = async () => {
      while (isActive) {
        controller = new AbortController()
        try {
          const params = new URLSearchParams()
          if (since) params.set('since', since)
          params.set('timeout', '25')
          const payload = await apiFetch<ThreadsPayload & { updated?: boolean }>(
            `/staff/threads/updates?${params.toString()}`,
            { signal: controller.signal },
          )
          if (payload.updated && payload.threads?.length) {
            queryClient.setQueryData(['staff-threads'], payload)
          }
          if (payload.latest_event_at) {
            since = payload.latest_event_at
          }
        } catch (err) {
          if ((err as Error).name !== 'AbortError') {
            await new Promise((resolve) => setTimeout(resolve, 1200))
          }
        }
      }
    }

    loop()
    return () => {
      isActive = false
      controller?.abort()
    }
  }, [threadsQuery.data?.latest_event_at])

  useEffect(() => {
    if (!activeThreadId || !messagesQuery.data) return
    let isActive = true
    let since =
      messagesQuery.data.latest_activity_at || messagesQuery.data.latest_message_at || new Date().toISOString()
    let controller: AbortController | null = null

    const loop = async () => {
      while (isActive) {
        controller = new AbortController()
        try {
          const params = new URLSearchParams()
          if (since) params.set('since', since)
          params.set('timeout', '25')
          const payload = await apiFetch<MessagesPayload & { updated?: boolean }>(
            `/staff/threads/${activeThreadId}/updates?${params.toString()}`,
            { signal: controller.signal },
          )
          if (payload.updated) {
            queryClient.setQueryData(['staff-messages', activeThreadId], (prev?: MessagesPayload) => {
              if (!prev) return prev
              const merged = [...prev.messages]
              payload.messages?.forEach((incoming) => {
                const idx = merged.findIndex((msg) => msg.id === incoming.id)
                if (idx >= 0) merged[idx] = incoming
                else merged.push(incoming)
              })
              merged.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
              return {
                ...prev,
                messages: merged,
                members: payload.members || prev.members,
                latest_activity_at: payload.latest_activity_at || prev.latest_activity_at,
                latest_message_at: payload.latest_message_at || prev.latest_message_at,
              }
            })
            if (payload.latest_activity_at) {
              since = payload.latest_activity_at
            }
            const hasIncoming = payload.messages?.some((msg) => msg.sender_type !== principalType)
            if (hasIncoming && activeThreadId) {
              markReadMutation.mutate(activeThreadId)
            }
          }
          if (payload.latest_activity_at) {
            since = payload.latest_activity_at
          }
        } catch (err) {
          if ((err as Error).name !== 'AbortError') {
            await new Promise((resolve) => setTimeout(resolve, 1200))
          }
        }
      }
    }

    loop()
    return () => {
      isActive = false
      controller?.abort()
    }
  }, [activeThreadId, messagesQuery.data?.latest_activity_at, messagesQuery.data?.latest_message_at, principalType])

  const handleCreateDirect = () => {
    if (!newChatTarget) return
    createThreadMutation.mutate({
      type: 'direct',
      members: [{ type: 'recruiter', id: Number(newChatTarget) }],
    })
  }

  const handleCreateGroup = () => {
    if (!groupTitle.trim() || groupMembers.length === 0) return
    createThreadMutation.mutate({
      type: 'group',
      title: groupTitle.trim(),
      members: groupMembers.map((id) => ({ type: 'recruiter', id })),
    })
  }

  const handleAdminChat = () => {
    createThreadMutation.mutate({
      type: 'direct',
      members: [{ type: 'admin', id: -1 }],
    })
  }

  const filteredThreads = useMemo(() => {
    const term = searchQuery.trim().toLowerCase()
    if (!term) return threadsQuery.data?.threads || []
    return (threadsQuery.data?.threads || []).filter((thread) =>
      [thread.title, previewText(thread)].some((val) => (val || '').toLowerCase().includes(term)),
    )
  }, [threadsQuery.data?.threads, searchQuery])

  const members = messagesQuery.data?.members || []
  const recruiterMembers = members.filter((m) => m.type === 'recruiter' && !m.is_placeholder)
  const visibleMembers = members.filter(
    (m) => !m.is_placeholder && !(m.type === principalType && m.id === principalId),
  )
  const memberNames = visibleMembers.map((m) => m.name || (m.type === 'admin' ? 'Администратор' : 'Участник'))
  const memberSummary = memberNames.length > 0 ? memberNames.slice(0, 2).join(', ') : 'Администратор'
  const memberSuffix = memberNames.length > 2 ? ` и ещё ${memberNames.length - 2}` : ''

  const availableRecruiters = (recruitersQuery.data || []).filter(
    (rec) => !recruiterMembers.some((m) => m.id === rec.id),
  )

  return (
    <div className="page messenger-page">
      <header className="glass panel messenger-header">
        <div>
          <h1 className="title title--lg">Мессенджер RecruitSmart</h1>
          <p className="subtitle">Командные чаты и передача кандидатов внутри системы.</p>
        </div>
        {!isAdmin && (
          <button className="ui-btn ui-btn--primary" onClick={handleAdminChat}>
            Написать администратору
          </button>
        )}
      </header>

      <div className="messenger-layout">
        <aside className="glass panel messenger-sidebar">
          <div className="messenger-sidebar__header">
            <div>
              <h2 className="section-title">Чаты</h2>
              <p className="subtitle">{threadsQuery.data?.threads.length || 0} активных</p>
            </div>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => threadsQuery.refetch()}>
              Обновить
            </button>
          </div>
          <div className="messenger-sidebar__search">
            <input
              placeholder="Поиск чатов"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          {threadsQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {threadsQuery.isError && <p className="text-danger">Ошибка загрузки</p>}
          <div className="messenger-thread-list">
            {filteredThreads.map((thread) => (
              <button
                key={thread.id}
                className={`messenger-thread${thread.id === activeThreadId ? ' is-active' : ''}`}
                onClick={() => setActiveThreadId(thread.id)}
              >
                <div className="messenger-thread__avatar">
                  {(thread.title || 'Чат').slice(0, 2).toUpperCase()}
                </div>
                <div className="messenger-thread__info">
                  <div className="messenger-thread__row">
                    <span className="messenger-thread__title">{thread.title}</span>
                    <span className="messenger-thread__time">
                      {formatThreadTime(thread.last_message?.created_at || thread.created_at)}
                    </span>
                  </div>
                  <div className="messenger-thread__row messenger-thread__preview">
                    <span>{previewText(thread)}</span>
                    {thread.unread_count ? (
                      <span className="messenger-thread__badge">{thread.unread_count}</span>
                    ) : null}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {isAdmin && (
            <div className="messenger-new-chat">
              <h3 className="subtitle">Новый чат</h3>
              <div className="form-grid">
                <label>
                  Личный чат с рекрутером
                  <select value={newChatTarget} onChange={(e) => setNewChatTarget(e.target.value)}>
                    <option value="">Выберите</option>
                    {(recruitersQuery.data || []).map((rec) => (
                      <option key={rec.id} value={rec.id}>
                        {rec.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button className="ui-btn ui-btn--primary ui-btn--sm" onClick={handleCreateDirect}>
                  Открыть
                </button>
              </div>

              <div className="messenger-group">
                <label>
                  Название группы
                  <input value={groupTitle} onChange={(e) => setGroupTitle(e.target.value)} />
                </label>
                <div className="messenger-group__members">
                  {(recruitersQuery.data || []).map((rec) => (
                    <label key={rec.id} className="messenger-checkbox">
                      <input
                        type="checkbox"
                        checked={groupMembers.includes(rec.id)}
                        onChange={(e) => {
                          setGroupMembers((prev) =>
                            e.target.checked ? [...prev, rec.id] : prev.filter((id) => id !== rec.id),
                          )
                        }}
                      />
                      <span>{rec.name}</span>
                    </label>
                  ))}
                </div>
                <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={handleCreateGroup}>
                  Создать группу
                </button>
              </div>
            </div>
          )}
        </aside>

        <section className="glass panel messenger-chat">
          {!activeThread && <p className="subtitle">Выберите чат слева, чтобы начать переписку.</p>}
          {activeThread && (
            <>
              <div className="messenger-chat__header">
                <div>
                  <h2 className="section-title">{activeThread.title}</h2>
                  <p className="subtitle">
                    {activeThread.type === 'group' ? 'Групповой чат' : 'Личный чат'} · {memberSummary}{memberSuffix}
                  </p>
                </div>
                <div className="messenger-chat__actions">
                  {activeThread.type === 'group' && isAdmin && (
                    <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setShowMembersModal(true)}>
                      Участники
                    </button>
                  )}
                  <button
                    className="ui-btn ui-btn--ghost ui-btn--sm"
                    onClick={() => setShowCandidateModal(true)}
                    disabled={!activeThreadId}
                  >
                    Передать кандидата
                  </button>
                </div>
              </div>
              <div className="messenger-messages">
                {messagesQuery.isLoading && <p className="subtitle">Загрузка сообщений…</p>}
                {messagesQuery.isError && <p className="text-danger">Ошибка загрузки</p>}
                {(messagesQuery.data?.messages || []).map((msg) => {
                  if (msg.type === 'system') {
                    return (
                      <div key={msg.id} className="messenger-system">
                        <span>{msg.text}</span>
                      </div>
                    )
                  }
                  const isOwn = msg.sender_type === principalType && msg.sender_id === principalId
                  const readLabel = isOwn ? messageStatusLabel(msg) : ''
                  return (
                    <div key={msg.id} className={`messenger-message ${isOwn ? 'is-own' : ''}`}>
                      <div className="messenger-message__meta">
                        <span>{msg.sender_label || (msg.sender_type === 'admin' ? 'Администратор' : 'Рекрутер')}</span>
                        <span>{formatTime(msg.created_at)}</span>
                        {readLabel && <span className="messenger-message__read">{readLabel}</span>}
                      </div>
                      {msg.type === 'candidate_task' && msg.task && msg.candidate && (
                        <div className="messenger-task">
                          <div className="messenger-task__header">
                            <div>
                              <div className="messenger-task__title">{msg.candidate.name}</div>
                              <div className="messenger-task__meta">
                                {msg.candidate.city} · {msg.candidate.status_label}
                              </div>
                            </div>
                            <span className={`messenger-task__status is-${msg.task.status}`}>
                              {msg.task.status === 'pending'
                                ? 'В ожидании'
                                : msg.task.status === 'accepted'
                                  ? 'Принято'
                                  : 'Отклонено'}
                            </span>
                          </div>
                          {msg.text && <div className="messenger-task__note">{msg.text}</div>}
                          <div className="messenger-task__footer">
                            {msg.candidate.profile_url && (
                              <a href={msg.candidate.profile_url} className="messenger-task__link">
                                Открыть профиль
                              </a>
                            )}
                            {msg.task.status === 'declined' && msg.task.decision_comment && (
                              <span className="messenger-task__comment">Причина: {msg.task.decision_comment}</span>
                            )}
                          </div>
                          {principalType === 'recruiter' && msg.task.status === 'pending' && !isOwn && (
                            <div className="messenger-task__actions">
                              <button
                                className="ui-btn ui-btn--primary ui-btn--sm"
                                onClick={() => acceptTaskMutation.mutate(msg.id)}
                              >
                                Принять
                              </button>
                              <button
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                                onClick={() => {
                                  setTaskDeclineTarget(msg)
                                  setTaskDeclineComment('')
                                }}
                              >
                                Отклонить
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                      {msg.type !== 'candidate_task' && msg.text && (
                        <div className="messenger-message__text">{msg.text}</div>
                      )}
                      {msg.attachments.length > 0 && (
                        <div className="messenger-attachments">
                          {msg.attachments.map((att) => {
                            const isImage = (att.mime_type || '').startsWith('image/')
                            return (
                              <a key={att.id} href={`/api/staff/attachments/${att.id}`} className="messenger-attachment">
                                {isImage ? (
                                  <img
                                    src={`/api/staff/attachments/${att.id}`}
                                    alt={att.filename}
                                    className="messenger-attachment__preview"
                                  />
                                ) : (
                                  <span className="messenger-attachment__icon">📎</span>
                                )}
                                <span className="messenger-attachment__info">
                                  <span className="messenger-attachment__name">{att.filename}</span>
                                  <span className="messenger-attachment__size">{formatBytes(att.size)}</span>
                                </span>
                              </a>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              <div className="messenger-composer">
                <textarea
                  rows={2}
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  placeholder="Написать сообщение…"
                />
                <div className="messenger-composer__actions">
                  <label className="messenger-upload">
                    <input
                      type="file"
                      multiple
                      onChange={(e) => {
                        const list = Array.from(e.target.files || [])
                        setFiles(list)
                      }}
                    />
                    <span>Файлы</span>
                  </label>
                  <button
                    className="ui-btn ui-btn--primary"
                    onClick={() => sendMutation.mutate()}
                    disabled={sendMutation.isPending}
                  >
                    {sendMutation.isPending ? 'Отправка…' : 'Отправить'}
                  </button>
                </div>
                {files.length > 0 && (
                  <div className="messenger-files">
                    {files.map((file) => (
                      <span key={file.name} className="messenger-file">
                        {file.name}
                      </span>
                    ))}
                  </div>
                )}
                {sendError && <div className="messenger-error">{sendError}</div>}
              </div>
            </>
          )}
        </section>
      </div>

      {showMembersModal && activeThread && (
        <ModalPortal>
          <div className="overlay" onClick={() => setShowMembersModal(false)}>
            <div className="glass sheet" onClick={(e) => e.stopPropagation()}>
              <div className="messenger-modal__header">
                <h3 className="section-title">Участники чата</h3>
                <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setShowMembersModal(false)}>
                  Закрыть
                </button>
              </div>
              <div className="messenger-modal__body">
                <div className="messenger-member-list">
                  {members
                    .filter((m) => !m.is_placeholder)
                    .map((member) => (
                      <div key={`${member.type}:${member.id}`} className="messenger-member">
                        <span>{member.name}</span>
                        {member.type === 'recruiter' && (
                          <button
                            className="ui-btn ui-btn--ghost ui-btn--sm"
                            onClick={() => removeMemberMutation.mutate(member)}
                          >
                            Удалить
                          </button>
                        )}
                      </div>
                    ))}
                </div>
                <div className="messenger-modal__section">
                  <h4 className="subtitle">Добавить участников</h4>
                  <div className="messenger-modal__grid">
                    {availableRecruiters.map((rec) => (
                      <label key={rec.id} className="messenger-checkbox">
                        <input
                          type="checkbox"
                          checked={memberSelection.includes(rec.id)}
                          onChange={(e) => {
                            setMemberSelection((prev) =>
                              e.target.checked ? [...prev, rec.id] : prev.filter((id) => id !== rec.id),
                            )
                          }}
                        />
                        <span>{rec.name}</span>
                      </label>
                    ))}
                  </div>
                  <button
                    className="ui-btn ui-btn--primary ui-btn--sm"
                    onClick={() => addMembersMutation.mutate(memberSelection)}
                    disabled={memberSelection.length === 0}
                  >
                    Добавить
                  </button>
                </div>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

      {showCandidateModal && activeThread && (
        <ModalPortal>
          <div className="overlay" onClick={() => setShowCandidateModal(false)}>
            <div className="glass sheet" onClick={(e) => e.stopPropagation()}>
              <div className="messenger-modal__header">
                <h3 className="section-title">Передать кандидата</h3>
                <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setShowCandidateModal(false)}>
                  Закрыть
                </button>
              </div>
              <div className="messenger-modal__body">
                <label>
                  Поиск кандидата
                  <input
                    placeholder="ФИО, город, Telegram"
                    value={candidateSearch}
                    onChange={(e) => setCandidateSearch(e.target.value)}
                  />
                </label>
                <div className="messenger-candidate-results">
                  {candidateSearchQuery.isLoading && <p className="subtitle">Поиск…</p>}
                  {candidateSearchQuery.data?.items?.map((candidate) => (
                    <button
                      key={candidate.id}
                      className="messenger-candidate-card"
                      onClick={() => sendCandidateMutation.mutate(candidate.id)}
                    >
                      <div>
                        <div className="messenger-candidate-card__title">{candidate.fio || 'Без имени'}</div>
                        <div className="messenger-candidate-card__meta">
                          {candidate.city || 'Город не указан'} · {candidate.status?.label || 'Без статуса'}
                        </div>
                      </div>
                      <span className="messenger-candidate-card__cta">Передать →</span>
                    </button>
                  ))}
                  {candidateSearch.trim().length > 1 && !candidateSearchQuery.data?.items?.length && (
                    <p className="subtitle">Ничего не найдено</p>
                  )}
                </div>
                <label>
                  Комментарий
                  <textarea
                    rows={3}
                    value={candidateNote}
                    onChange={(e) => setCandidateNote(e.target.value)}
                    placeholder="Кратко опишите задачу"
                  />
                </label>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

      {taskDeclineTarget && (
        <ModalPortal>
          <div className="overlay" onClick={() => setTaskDeclineTarget(null)}>
            <div className="glass sheet" onClick={(e) => e.stopPropagation()}>
              <div className="messenger-modal__header">
                <h3 className="section-title">Отклонить задачу</h3>
                <button className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setTaskDeclineTarget(null)}>
                  Закрыть
                </button>
              </div>
              <div className="messenger-modal__body">
                <label>
                  Причина отказа
                  <textarea
                    rows={3}
                    value={taskDeclineComment}
                    onChange={(e) => setTaskDeclineComment(e.target.value)}
                    placeholder="Укажите причину"
                  />
                </label>
                <button
                  className="ui-btn ui-btn--primary"
                  onClick={() =>
                    declineTaskMutation.mutate({ messageId: taskDeclineTarget.id, comment: taskDeclineComment })
                  }
                  disabled={!taskDeclineComment.trim()}
                >
                  Отправить
                </button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

      {toast && (
        <div className="toast" data-tone={toast.tone}>
          {toast.message}
        </div>
      )}
    </div>
  )
}
