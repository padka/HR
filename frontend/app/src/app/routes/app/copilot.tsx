import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useProfile } from '@/app/hooks/useProfile'
import { ModalPortal } from '@/shared/components/ModalPortal'

type ChatMessage = {
  id: number
  role: 'user' | 'assistant'
  text: string
  created_at?: string | null
  meta?: Record<string, unknown>
}

type ChatState = {
  ok: boolean
  thread_id: number
  messages: ChatMessage[]
}

type KBDocItem = {
  id: number
  title: string
  filename?: string
  mime_type?: string
  is_active: boolean
  updated_at?: string | null
  chunks_total?: number
}

type KBDocsList = {
  ok: boolean
  items: KBDocItem[]
}

type KBDocument = {
  id: number
  title: string
  filename?: string
  mime_type?: string
  is_active: boolean
  updated_at?: string | null
  chunks_total?: number
  content_text: string
}

type KBDocGet = {
  ok: boolean
  document: KBDocument
}

type KBReindexResponse = { ok: boolean; document_id: number; chunks_total?: number }
type ActionMessageError = { message?: string }

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  if (error && typeof error === 'object' && typeof (error as ActionMessageError).message === 'string') {
    return (error as ActionMessageError).message || fallback
  }
  return fallback
}

function formatTime(value?: string | null) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function CopilotPage() {
  const profile = useProfile()
  const isAdmin = profile.data?.principal.type === 'admin'

  const [toast, setToast] = useState<string | null>(null)
  const [chatText, setChatText] = useState('')
  const chatEndRef = useRef<HTMLDivElement | null>(null)
  const toastTimeoutRef = useRef<number | null>(null)

  const showToast = (message: string) => {
    setToast(message)
    if (toastTimeoutRef.current != null) {
      window.clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = window.setTimeout(() => setToast(null), 2600)
  }

  const chatQuery = useQuery<ChatState>({
    queryKey: ['ai-agent-chat'],
    queryFn: () => apiFetch('/ai/chat'),
    staleTime: 5_000,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (!chatQuery.data?.messages?.length) return
    requestAnimationFrame(() => chatEndRef.current?.scrollIntoView({ block: 'end' }))
  }, [chatQuery.data?.messages?.length])

  const sendMutation = useMutation({
    mutationFn: async (text: string) => apiFetch('/ai/chat/message', { method: 'POST', body: JSON.stringify({ text }) }),
    onSuccess: async () => {
      setChatText('')
      await chatQuery.refetch()
    },
    onError: (error: unknown) => {
      showToast(getErrorMessage(error, 'Не удалось отправить'))
    },
  })

  const docsQuery = useQuery<KBDocsList>({
    queryKey: ['kb-documents'],
    queryFn: () => apiFetch('/kb/documents'),
    staleTime: 10_000,
  })

  const [kbTitle, setKbTitle] = useState('Регламенты рекрутинга')
  const [kbText, setKbText] = useState('')
  const [kbFile, setKbFile] = useState<File | null>(null)
  const [activeDocId, setActiveDocId] = useState<number | null>(null)

  const docQuery = useQuery<KBDocGet>({
    queryKey: ['kb-document', activeDocId],
    queryFn: () => apiFetch(`/kb/documents/${activeDocId}`),
    enabled: activeDocId != null,
  })

  const createDocMutation = useMutation({
    mutationFn: async () =>
      apiFetch('/kb/documents', {
        method: 'POST',
        body: JSON.stringify({ title: kbTitle, content_text: kbText }),
      }),
    onSuccess: async () => {
      setKbText('')
      await docsQuery.refetch()
      showToast('Документ добавлен')
    },
    onError: (error: unknown) => showToast(getErrorMessage(error, 'Не удалось добавить документ')),
  })

  const uploadDocMutation = useMutation({
    mutationFn: async () => {
      if (!kbFile) throw new Error('Выберите файл')
      const form = new FormData()
      form.append('file', kbFile)
      if (kbTitle) form.append('title', kbTitle)
      return apiFetch('/kb/documents', { method: 'POST', body: form })
    },
    onSuccess: async () => {
      setKbFile(null)
      await docsQuery.refetch()
      showToast('Файл загружен')
    },
    onError: (error: unknown) => showToast(getErrorMessage(error, 'Не удалось загрузить файл')),
  })

  const deleteDocMutation = useMutation({
    mutationFn: async (id: number) => apiFetch(`/kb/documents/${id}`, { method: 'DELETE' }),
    onSuccess: async () => {
      await docsQuery.refetch()
      showToast('Документ отключён')
    },
    onError: (error: unknown) => showToast(getErrorMessage(error, 'Не удалось отключить документ')),
  })

  const enableDocMutation = useMutation({
    mutationFn: async (id: number) =>
      apiFetch(`/kb/documents/${id}`, { method: 'PUT', body: JSON.stringify({ is_active: true }) }),
    onSuccess: async () => {
      await docsQuery.refetch()
      showToast('Документ включён')
    },
    onError: (error: unknown) => showToast(getErrorMessage(error, 'Не удалось включить документ')),
  })

  const reindexDocMutation = useMutation({
    mutationFn: async (id: number) => apiFetch<KBReindexResponse>(`/kb/documents/${id}/reindex`, { method: 'POST' }),
    onSuccess: async () => {
      await docsQuery.refetch()
      if (activeDocId != null) await docQuery.refetch()
      showToast('Переиндексация выполнена')
    },
    onError: (error: unknown) => showToast(getErrorMessage(error, 'Не удалось переиндексировать')),
  })

  const messages = chatQuery.data?.messages || []

  const docsActive = useMemo(() => (docsQuery.data?.items || []).filter((d) => d.is_active), [docsQuery.data])
  const docsInactive = useMemo(() => (docsQuery.data?.items || []).filter((d) => !d.is_active), [docsQuery.data])

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <h1 className="title">Copilot</h1>
          <div className="subtitle">Чат с AI и база знаний.</div>
        </header>

        <section className="copilot-grid">
          <div className="glass page-section copilot-chat">
            <div className="copilot-chat__header">
              <div>
                <h2 className="section-title copilot-section-title">AI чат</h2>
                <p className="subtitle copilot-section-subtitle">
                  AI опирается на базу знаний и контекст системы.
                </p>
              </div>
              <button
                className="ui-btn ui-btn--ghost ui-btn--sm"
                type="button"
                onClick={() => chatQuery.refetch()}
                disabled={chatQuery.isFetching}
              >
                {chatQuery.isFetching ? 'Обновляем…' : 'Обновить'}
              </button>
            </div>

            <div className="copilot-chat__body">
              {chatQuery.isLoading && <p className="subtitle">Загрузка…</p>}
              {chatQuery.isError && <p className="ui-message ui-message--error">Ошибка: {(chatQuery.error as Error).message}</p>}
              {!chatQuery.isLoading && messages.length === 0 && (
                <div className="subtitle">Задайте вопрос: например, “Какие объективные причины отказа допустимы после интервью?”</div>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`copilot-msg copilot-msg--${m.role}`}>
                  <div className="copilot-msg__bubble">
                    <div className="copilot-msg__text">{m.text}</div>
                    {m.created_at && <div className="copilot-msg__meta">{formatTime(m.created_at)}</div>}
                  </div>
                </div>
              ))}
              {sendMutation.isPending && (
                <div className="copilot-msg copilot-msg--assistant">
                  <div className="copilot-msg__bubble copilot-msg__bubble--typing">
                    <div className="copilot-msg__text copilot-msg__typing">
                      AI думает…
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="copilot-chat__footer">
              <textarea
                rows={3}
                value={chatText}
                onChange={(e) => setChatText(e.target.value)}
                placeholder="Написать вопрос…"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    const t = chatText.trim()
                    if (t) sendMutation.mutate(t)
                  }
                }}
              />
              <div className="copilot-chat__actions">
                <button
                  type="button"
                  className="ui-btn ui-btn--primary"
                  disabled={!chatText.trim() || sendMutation.isPending}
                  onClick={() => chatText.trim() && sendMutation.mutate(chatText.trim())}
                >
                  {sendMutation.isPending ? 'Отправка…' : 'Отправить'}
                </button>
              </div>
            </div>
          </div>

          <div className="glass page-section copilot-kb">
            <div className="copilot-kb__header">
              <h2 className="section-title copilot-section-title">База знаний</h2>
              <p className="subtitle copilot-section-subtitle">
                Документы используются для оценок кандидатов и ответов в AI чате.
              </p>
            </div>

            {docsQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {docsQuery.isError && <p className="ui-message ui-message--error">Ошибка: {(docsQuery.error as Error).message}</p>}

            {docsQuery.data && (
              <div className="copilot-kb__list">
                {docsActive.length === 0 && <div className="subtitle">Активных документов пока нет.</div>}
                {docsActive.map((d) => (
                  <div key={d.id} className="copilot-doc glass glass--interactive">
                    <button type="button" className="copilot-doc__main" onClick={() => setActiveDocId(d.id)}>
                      <div className="copilot-doc__title">{d.title || 'Документ'}</div>
                      <div className="copilot-doc__meta">
                        {d.chunks_total != null ? `${d.chunks_total} фрагм.` : ''}
                        {d.updated_at ? ` · ${formatTime(d.updated_at)}` : ''}
                      </div>
                    </button>
                    {isAdmin && (
                      <button
                        type="button"
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        onClick={() => window.confirm('Отключить документ?') && deleteDocMutation.mutate(d.id)}
                        disabled={deleteDocMutation.isPending}
                      >
                        Отключить
                      </button>
                    )}
                  </div>
                ))}

                {docsInactive.length > 0 && (
                  <details className="copilot-kb__inactive">
                    <summary>Отключённые ({docsInactive.length})</summary>
                    <div className="copilot-kb__list">
                      {docsInactive.map((d) => (
                        <div key={d.id} className="copilot-doc glass">
                          <button type="button" className="copilot-doc__main" onClick={() => setActiveDocId(d.id)}>
                            <div className="copilot-doc__title">{d.title || 'Документ'}</div>
                            <div className="copilot-doc__meta">
                              {d.chunks_total != null ? `${d.chunks_total} фрагм.` : ''}
                              {d.updated_at ? ` · ${formatTime(d.updated_at)}` : ''}
                            </div>
                          </button>
                          {isAdmin && (
                            <button
                              type="button"
                              className="ui-btn ui-btn--primary ui-btn--sm"
                              onClick={() => enableDocMutation.mutate(d.id)}
                              disabled={enableDocMutation.isPending}
                            >
                              Включить
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}

            {isAdmin && (
              <div className="copilot-kb__admin">
                <h3 className="section-title copilot-section-title">Добавить документ</h3>
                <label className="form-group">
                  <span className="form-group__label">Заголовок</span>
                  <input value={kbTitle} onChange={(e) => setKbTitle(e.target.value)} placeholder="Например: Регламенты рекрутинга" />
                </label>
                <div className="copilot-kb__admin-grid">
                  <label className="form-group">
                    <span className="form-group__label">Вставить текст (markdown/текст)</span>
                    <textarea rows={8} value={kbText} onChange={(e) => setKbText(e.target.value)} placeholder="Вставьте текст документа сюда…" />
                    <button
                      type="button"
                      className="ui-btn ui-btn--primary ui-btn--sm copilot-kb__submit"
                      onClick={() => createDocMutation.mutate()}
                      disabled={!kbTitle.trim() || !kbText.trim() || createDocMutation.isPending}
                    >
                      {createDocMutation.isPending ? 'Сохраняем…' : 'Сохранить'}
                    </button>
                  </label>

                  <label className="form-group">
                    <span className="form-group__label">Или загрузить файл (.txt/.md/.docx/.pdf)</span>
                    <input
                      type="file"
                      accept=".txt,.md,.docx,.pdf,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      onChange={(e) => setKbFile(e.target.files?.[0] || null)}
                    />
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost ui-btn--sm copilot-kb__upload"
                      onClick={() => uploadDocMutation.mutate()}
                      disabled={!kbFile || uploadDocMutation.isPending}
                    >
                      {uploadDocMutation.isPending ? 'Загрузка…' : 'Загрузить'}
                    </button>
                    <div className="subtitle copilot-kb__hint">
                      После загрузки документ автоматически индексируется на фрагменты.
                    </div>
                  </label>
                </div>
              </div>
            )}
            {!isAdmin && (
              <div className="subtitle copilot-kb__readonly-note">
                Добавлять и отключать документы может только администратор.
              </div>
            )}
          </div>
        </section>

        {activeDocId != null && (
          <ModalPortal>
            <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setActiveDocId(null)} role="dialog" aria-modal="true">
              <div className="glass glass--elevated modal modal--lg">
                <div className="modal__header">
                  <div>
                    <h2 className="modal__title">{docQuery.data?.document?.title || 'Документ'}</h2>
                    <p className="modal__subtitle">
                      {docQuery.data?.document?.updated_at ? formatTime(docQuery.data.document.updated_at) : ''}
                      {docQuery.data?.document?.chunks_total != null ? ` · ${docQuery.data.document.chunks_total} фрагм.` : ''}
                    </p>
                  </div>
                  <div className="copilot-modal-actions">
                    {isAdmin && (
                      <button
                        className="ui-btn ui-btn--ghost"
                        onClick={() => reindexDocMutation.mutate(activeDocId)}
                        disabled={reindexDocMutation.isPending}
                        title="Пересобрать фрагменты (chunks) для поиска"
                      >
                        {reindexDocMutation.isPending ? 'Индексируем…' : 'Переиндексировать'}
                      </button>
                    )}
                    <button className="ui-btn ui-btn--ghost" onClick={() => setActiveDocId(null)}>Закрыть</button>
                  </div>
                </div>
                <div className="modal__body">
                  {docQuery.isLoading && <p className="subtitle">Загрузка…</p>}
                  {docQuery.isError && <p className="ui-message ui-message--error">Ошибка: {(docQuery.error as Error).message}</p>}
                  {docQuery.data && (
                    <pre className="copilot-doc-preview">{docQuery.data.document.content_text || ''}</pre>
                  )}
                </div>
              </div>
            </div>
          </ModalPortal>
        )}

        {toast && (
          <div className="toast copilot-toast" data-tone="success">
            <strong className="copilot-toast__title">Copilot</strong>
            <span className="copilot-toast__text">{toast}</span>
          </div>
        )}
      </div>
    </RoleGuard>
  )
}
