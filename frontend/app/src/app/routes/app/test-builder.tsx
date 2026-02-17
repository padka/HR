import { useMemo, useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { RoleGuard } from '@/app/components/RoleGuard'
import { apiFetch, queryClient } from '@/api/client'

type QuestionRow = {
  id: number
  index: number
  title: string
  prompt: string
  kind: 'choice' | 'text'
  options_count: number
  correct_label: string | null
  is_active: boolean
  updated_at: string | null
}

type QuestionGroup = {
  test_id: string
  title: string
  questions: QuestionRow[]
}

function moveItem<T>(items: T[], from: number, to: number): T[] {
  const next = items.slice()
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

function reorderById(items: number[], sourceId: number, targetId: number): number[] {
  const from = items.indexOf(sourceId)
  const to = items.indexOf(targetId)
  if (from === -1 || to === -1 || from === to) return items
  return moveItem(items, from, to)
}

export function TestBuilderPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['questions'],
    queryFn: () => apiFetch<QuestionGroup[]>('/questions'),
  })

  const [activeTest, setActiveTest] = useState<string>('')
  const groups = useMemo(() => data || [], [data])

  useEffect(() => {
    if (!activeTest && groups.length) {
      setActiveTest(groups[0].test_id)
    }
  }, [activeTest, groups])

  const group = useMemo(() => groups.find((g) => g.test_id === activeTest) || null, [groups, activeTest])

  const [order, setOrder] = useState<number[]>([])
  const [dirty, setDirty] = useState(false)
  const [dragId, setDragId] = useState<number | null>(null)
  const [message, setMessage] = useState<string>('')

  useEffect(() => {
    if (!group) return
    setOrder(group.questions.map((q) => q.id))
    setDirty(false)
    setMessage('')
  }, [group])

  const byId = useMemo(() => {
    const map = new Map<number, QuestionRow>()
    if (!group) return map
    group.questions.forEach((q) => map.set(q.id, q))
    return map
  }, [group])

  const reorderMutation = useMutation({
    mutationFn: async () => {
      if (!group) throw new Error('Test not selected')
      return apiFetch<{ ok: boolean; error?: string }>('/questions/reorder', {
        method: 'POST',
        body: JSON.stringify({ test_id: group.test_id, order }),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['questions'] })
      setDirty(false)
      setMessage('Порядок сохранён. Бот обновит вопросы автоматически.')
      window.setTimeout(() => setMessage(''), 2500)
    },
    onError: (err) => {
      setMessage(err instanceof Error ? err.message : 'Не удалось сохранить порядок')
    },
  })

  const cloneMutation = useMutation({
    mutationFn: async (questionId: number) => {
      return apiFetch<{ ok: boolean; id?: number }>(`/questions/${questionId}/clone`, { method: 'POST' })
    },
    onSuccess: (payload) => {
      if (payload?.id) {
        queryClient.invalidateQueries({ queryKey: ['questions'] })
        navigate({ to: '/app/questions/$questionId/edit', params: { questionId: String(payload.id) } })
      }
    },
  })

  const handleMove = (id: number, delta: number) => {
    const idx = order.indexOf(id)
    if (idx === -1) return
    const nextIdx = idx + delta
    if (nextIdx < 0 || nextIdx >= order.length) return
    setOrder(moveItem(order, idx, nextIdx))
    setDirty(true)
  }

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <div style={{ display: 'grid', gap: 4 }}>
            <h1 className="title" style={{ margin: 0 }}>Конструктор тестов</h1>
            <div className="subtitle" style={{ margin: 0 }}>
              Линейный режим v1: блоки-вопросы + порядок. Ветвления будут добавлены следующим этапом.
            </div>
          </div>
          <div className="toolbar toolbar--compact">
            <Link to="/app/system" className="ui-btn ui-btn--ghost">Bot Center</Link>
            <Link to="/app/questions/new" className="ui-btn ui-btn--primary">+ Новый вопрос</Link>
          </div>
        </header>

        <section className="glass page-section">
          <div className="toolbar" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
            <div className="toolbar toolbar--compact">
              {groups.map((g) => (
                <button
                  key={g.test_id}
                  type="button"
                  className={`slot-create-tab ${activeTest === g.test_id ? 'is-active' : ''}`}
                  onClick={() => setActiveTest(g.test_id)}
                >
                  {g.title}
                </button>
              ))}
            </div>
            <div className="toolbar toolbar--compact">
              <button
                type="button"
                className="ui-btn ui-btn--primary ui-btn--sm"
                onClick={() => reorderMutation.mutate()}
                disabled={!dirty || reorderMutation.isPending || !group}
              >
                {reorderMutation.isPending ? 'Сохраняем…' : 'Сохранить порядок'}
              </button>
              {dirty && <span className="subtitle" style={{ margin: 0 }}>Есть несохранённые изменения</span>}
            </div>
          </div>

          {message && <p className="subtitle" style={{ marginTop: 0 }}>{message}</p>}

          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p className="text-danger">Ошибка: {(error as Error).message}</p>}

          {group && (
            <div className="page-section__content">
              {order.map((id, idx) => {
                const q = byId.get(id)
                if (!q) return null
                const disabled = !q.is_active
                return (
                  <article
                    key={id}
                    className="glass list-item"
                    style={{
                      padding: 14,
                      borderRadius: 18,
                      opacity: disabled ? 0.6 : 1,
                      display: 'flex',
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 12,
                    }}
                    draggable
                    onDragStart={(e) => {
                      setDragId(id)
                      e.dataTransfer.effectAllowed = 'move'
                      e.dataTransfer.setData('text/plain', String(id))
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault()
                      const raw = e.dataTransfer.getData('text/plain')
                      const source = dragId ?? Number(raw)
                      if (!source || source === id) return
                      setOrder(reorderById(order, source, id))
                      setDirty(true)
                      setDragId(null)
                    }}
                  >
                    <div
                      style={{
                        width: 46,
                        height: 46,
                        borderRadius: 18,
                        display: 'grid',
                        placeItems: 'center',
                        background: 'rgba(255,255,255,0.06)',
                        border: '1px solid rgba(255,255,255,0.10)',
                        fontWeight: 700,
                      }}
                      title="Перетащите блок, чтобы поменять порядок"
                    >
                      {idx + 1}
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                        <div style={{ fontWeight: 700, fontSize: 16, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {q.title}
                        </div>
                        <span className={`status-badge status-badge--${q.kind === 'choice' ? 'info' : 'muted'}`}>
                          {q.kind === 'choice' ? `choice · ${q.options_count}` : 'text'}
                        </span>
                        {!q.is_active && (
                          <span className="status-badge status-badge--muted">Отключён</span>
                        )}
                      </div>
                      <div className="subtitle" style={{ margin: '6px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {q.prompt || '—'}
                      </div>
                    </div>

                    <div className="toolbar toolbar--compact" style={{ flexWrap: 'nowrap' }}>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        onClick={() => handleMove(id, -1)}
                        disabled={idx === 0}
                        aria-label="Вверх"
                      >
                        ↑
                      </button>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        onClick={() => handleMove(id, +1)}
                        disabled={idx === order.length - 1}
                        aria-label="Вниз"
                      >
                        ↓
                      </button>
                      <Link
                        to="/app/questions/$questionId/edit"
                        params={{ questionId: String(id) }}
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                      >
                        Редактировать
                      </Link>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        onClick={() => cloneMutation.mutate(id)}
                        disabled={cloneMutation.isPending}
                      >
                        Клон
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          )}

          {!group && !isLoading && (
            <p className="subtitle">Нет данных. Создайте вопросы или выберите тест.</p>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
