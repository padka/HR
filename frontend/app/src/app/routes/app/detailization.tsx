import { apiFetch } from '@/api/client'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

type DetailizationItem = {
  id: number
  assigned_at: string | null
  conducted_at: string | null
  column_9: string
  expert_name: string
  is_attached: boolean | null
  recruiter: { id: number; name: string } | null
  city: { id: number; name: string } | null
  candidate: { id: number; name: string }
}

type DetailizationResponse = {
  ok: boolean
  items: DetailizationItem[]
}

function fmtDate(value: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleDateString('ru-RU')
}

function fmtTime(value: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function attachLabel(value: boolean | null): { text: string; tone: string } {
  if (value === true) return { text: 'Да', tone: 'success' }
  if (value === false) return { text: 'Нет', tone: 'danger' }
  return { text: '—', tone: 'muted' }
}

export function DetailizationPage() {
  const [dirty, setDirty] = useState<Record<number, Partial<Pick<DetailizationItem, 'column_9' | 'expert_name' | 'is_attached'>>>>(
    {},
  )
  const query = useQuery({
    queryKey: ['detailization'],
    queryFn: () => apiFetch<DetailizationResponse>('/detailization'),
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: number; patch: any }) =>
      apiFetch(`/detailization/${payload.id}`, { method: 'PATCH', body: JSON.stringify(payload.patch) }),
    onSuccess: async () => {
      setDirty({})
      await query.refetch()
    },
  })

  const items = query.data?.items || []
  const rows = useMemo(() => items, [items])

  const setRowPatch = (id: number, patch: any) => {
    setDirty((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } }))
  }

  const saveRow = async (id: number) => {
    const patch = dirty[id]
    if (!patch || Object.keys(patch).length === 0) return
    await updateMutation.mutateAsync({ id, patch })
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div className="glass" style={{ padding: 18, display: 'grid', gap: 8 }}>
        <h1 style={{ margin: 0 }}>Детализация</h1>
        <p style={{ margin: 0, color: 'var(--muted)' }}>
          Кандидаты, дошедшие до ознакомительного дня (с исключениями: «не подходит по критериям» и «не пришел»).
        </p>
      </div>

      <div className="glass detailization-table" style={{ marginTop: 16, padding: 14 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span className="text-muted text-sm">Строк: {rows.length}</span>
            {query.isFetching && <span className="text-muted text-sm">Обновление…</span>}
          </div>
          <button className="ui-btn ui-btn--secondary" onClick={() => query.refetch()} disabled={query.isFetching}>
            Обновить
          </button>
        </div>

        {query.isError && (
          <div className="glass" style={{ padding: 12, marginTop: 12 }}>
            <strong>Ошибка загрузки</strong>
            <div className="text-muted text-sm">{String((query.error as Error)?.message || query.error)}</div>
          </div>
        )}

        <div className="detailization-grid" style={{ marginTop: 12 }}>
          <div className="detailization-grid__head">
            <div>Дата назначения</div>
            <div>Column 9</div>
            <div>Рекрутер</div>
            <div>Дата проведения</div>
            <div>Город</div>
            <div>Эксперт (ФИО)</div>
            <div>Кандидат</div>
            <div>Закрепление</div>
            <div />
          </div>

          {rows.map((row) => {
            const patch = dirty[row.id] || {}
            const attached = attachLabel((patch as any).is_attached ?? row.is_attached)
            const canSave = Object.keys(patch).length > 0 && !updateMutation.isPending
            return (
              <div key={row.id} className="detailization-grid__row">
                <div className="text-sm">
                  <div>{fmtDate(row.assigned_at)}</div>
                  <div className="text-muted text-xs">{fmtTime(row.assigned_at)}</div>
                </div>

                <div>
                  <input
                    className="ui-input"
                    value={(patch as any).column_9 ?? row.column_9 ?? ''}
                    onChange={(e) => setRowPatch(row.id, { column_9: e.target.value })}
                    placeholder="—"
                  />
                </div>

                <div className="text-sm">{row.recruiter?.name || '—'}</div>

                <div className="text-sm">
                  <div>{fmtDate(row.conducted_at)}</div>
                  <div className="text-muted text-xs">{fmtTime(row.conducted_at)}</div>
                </div>

                <div className="text-sm">{row.city?.name || '—'}</div>

                <div>
                  <input
                    className="ui-input"
                    value={(patch as any).expert_name ?? row.expert_name ?? ''}
                    onChange={(e) => setRowPatch(row.id, { expert_name: e.target.value })}
                    placeholder="ФИО эксперта"
                  />
                </div>

                <div className="text-sm">
                  <Link to="/app/candidates/$candidateId" params={{ candidateId: String(row.candidate.id) }} className="action-link">
                    {row.candidate.name}
                  </Link>
                </div>

                <div>
                  <select
                    className="ui-select"
                    value={((patch as any).is_attached ?? row.is_attached) === null ? 'unknown' : ((patch as any).is_attached ?? row.is_attached) ? 'yes' : 'no'}
                    onChange={(e) => {
                      const v = e.target.value
                      setRowPatch(row.id, { is_attached: v === 'unknown' ? null : v === 'yes' })
                    }}
                    data-tone={attached.tone}
                  >
                    <option value="unknown">—</option>
                    <option value="yes">Да</option>
                    <option value="no">Нет</option>
                  </select>
                </div>

                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="ui-btn ui-btn--secondary" disabled={!canSave} onClick={() => saveRow(row.id)}>
                    Сохранить
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

