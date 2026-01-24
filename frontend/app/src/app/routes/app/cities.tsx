import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '@/api/client'

type City = {
  id: number
  name: string
  tz?: string | null
  active?: boolean | null
  owner_recruiter_id?: number | null
  plan_week?: number | null
  plan_month?: number | null
  criteria?: string | null
  experts?: string | null
  recruiter_ids?: number[]
  recruiters?: Array<{ id: number; name: string }>
  recruiter_count?: number
}

type StageItem = {
  key: string
  title: string
  value: string
  default: string
  is_custom: boolean
}

type TemplatesOverview = {
  cities: Array<{ city: { id: number; name: string }; stages: StageItem[] }>
}

type TemplatesPayload = {
  overview?: TemplatesOverview
}

export function CitiesPage() {
  const queryClient = useQueryClient()
  const [edits, setEdits] = useState<Record<number, { plan_week?: string; plan_month?: string; active?: boolean }>>({})
  const [rowError, setRowError] = useState<Record<number, string>>({})
  const { data, isLoading, isError, error } = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })
  const templatesQuery = useQuery<TemplatesPayload>({
    queryKey: ['templates-overview'],
    queryFn: () => apiFetch('/templates/list'),
  })

  const stageByCityId = new Map<number, StageItem[]>()
  templatesQuery.data?.overview?.cities?.forEach((entry) => {
    stageByCityId.set(entry.city.id, entry.stages || [])
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { city: City; plan_week?: string; plan_month?: string; active?: boolean }) => {
      const { city, plan_week, plan_month, active } = payload
      const parsedWeek = plan_week === '' ? null : plan_week ? Number(plan_week) : city.plan_week ?? null
      const parsedMonth = plan_month === '' ? null : plan_month ? Number(plan_month) : city.plan_month ?? null
      if (plan_week && Number.isNaN(parsedWeek)) {
        throw new Error('План/нед должен быть числом')
      }
      if (plan_month && Number.isNaN(parsedMonth)) {
        throw new Error('План/мес должен быть числом')
      }
      const body = {
        name: city.name,
        tz: city.tz || 'Europe/Moscow',
        active: active ?? city.active ?? true,
        plan_week: Number.isFinite(parsedWeek) ? parsedWeek : null,
        plan_month: Number.isFinite(parsedMonth) ? parsedMonth : null,
        criteria: city.criteria || null,
        experts: city.experts || null,
        recruiter_ids: city.recruiter_ids || [],
      }
      return apiFetch(`/cities/${city.id}`, { method: 'PUT', body: JSON.stringify(body) })
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['cities'] })
      setRowError((prev) => {
        const next = { ...prev }
        delete next[variables.city.id]
        return next
      })
    },
    onError: (err, variables) => {
      const message = err instanceof Error ? err.message : 'Ошибка обновления'
      setRowError((prev) => ({ ...prev, [variables.city.id]: message }))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (cityId: number) =>
      apiFetch(`/cities/${cityId}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cities'] })
    },
    onError: (err, cityId) => {
      const message = err instanceof Error ? err.message : 'Ошибка удаления'
      setRowError((prev) => ({ ...prev, [cityId]: message }))
    },
  })

  return (
    <div className="page">
      <div className="glass panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <h1 className="title">Города</h1>
          <Link to="/app/cities/new" className="glass action-link">+ Добавить</Link>
        </div>
        {isLoading && <p className="subtitle">Загрузка…</p>}
        {isError && <p style={{ color: '#f07373' }}>Ошибка: {(error as Error).message}</p>}
        {data && (
          <>
            {data.length === 0 && (
              <div className="glass panel--tight" style={{ marginTop: 12 }}>
                <p className="subtitle">Пока нет городов. Добавьте первый, чтобы начать работу.</p>
              </div>
            )}
          <div style={{ marginTop: 12, display: 'grid', gap: 12 }}>
            {data.map((c) => {
              const stages = stageByCityId.get(c.id) || []
              const customCount = stages.filter((s) => s.is_custom).length
              const responsibles = c.recruiters || []
              return (
                <div key={c.id} className="glass" style={{ padding: 16, display: 'grid', gap: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div>
                      <h3 style={{ margin: 0 }}>{c.name}</h3>
                      {c.criteria && <p className="subtitle">{c.criteria}</p>}
                    </div>
                    <span className="chip">{(edits[c.id]?.active ?? c.active) ? 'Активен' : 'В архиве'}</span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    <span className="chip">TZ: {c.tz || '—'}</span>
                    <span className="chip">Нед.: {edits[c.id]?.plan_week ?? c.plan_week ?? '—'}</span>
                    <span className="chip">Мес.: {edits[c.id]?.plan_month ?? c.plan_month ?? '—'}</span>
                  </div>
                  <div>
                    <div className="subtitle" style={{ fontWeight: 600 }}>Ответственные</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                      {responsibles.length > 0 ? (
                        responsibles.map((r) => <span key={r.id} className="chip">{r.name}</span>)
                      ) : (
                        <span className="subtitle">Не назначены</span>
                      )}
                    </div>
                  </div>
                  {c.experts && (
                    <div className="subtitle">Эксперты: {c.experts}</div>
                  )}
                  {stages.length > 0 && (
                    <details>
                      <summary>Этапы найма: {stages.length} {customCount ? `(кастомных ${customCount})` : ''}</summary>
                      <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                        {stages.map((s) => (
                          <div key={s.key} className="glass" style={{ padding: 10 }}>
                            <div style={{ fontWeight: 600 }}>{s.title}</div>
                            <div className="subtitle">{s.value || s.default || '—'}</div>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                  <div className="action-row" style={{ flexWrap: 'wrap' }}>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <input
                        type="checkbox"
                        checked={Boolean(edits[c.id]?.active ?? c.active)}
                        onChange={(e) =>
                          setEdits((prev) => ({ ...prev, [c.id]: { ...prev[c.id], active: e.target.checked } }))
                        }
                      />
                      <span>{(edits[c.id]?.active ?? c.active) ? 'Активен' : 'Не активен'}</span>
                    </label>
                    <input
                      style={{ maxWidth: 120 }}
                      placeholder="План/нед"
                      value={edits[c.id]?.plan_week ?? (c.plan_week ?? '')}
                      onChange={(e) =>
                        setEdits((prev) => ({ ...prev, [c.id]: { ...prev[c.id], plan_week: e.target.value } }))
                      }
                    />
                    <input
                      style={{ maxWidth: 120 }}
                      placeholder="План/мес"
                      value={edits[c.id]?.plan_month ?? (c.plan_month ?? '')}
                      onChange={(e) =>
                        setEdits((prev) => ({ ...prev, [c.id]: { ...prev[c.id], plan_month: e.target.value } }))
                      }
                    />
                    <button
                      className="ui-btn ui-btn--ghost"
                      onClick={() =>
                        updateMutation.mutate({
                          city: c,
                          plan_week: edits[c.id]?.plan_week,
                          plan_month: edits[c.id]?.plan_month,
                          active: edits[c.id]?.active,
                        })
                      }
                      disabled={updateMutation.isPending}
                    >
                      Сохранить
                    </button>
                    <Link to="/app/cities/$cityId/edit" params={{ cityId: String(c.id) }}>
                      Настроить →
                    </Link>
                    <button
                      className="ui-btn ui-btn--danger"
                      onClick={() =>
                        window.confirm(`Удалить город ${c.name}?`) && deleteMutation.mutate(c.id)
                      }
                      disabled={deleteMutation.isPending}
                    >
                      Удалить
                    </button>
                    {rowError[c.id] && (
                      <div style={{ color: '#f07373', fontSize: 12 }}>{rowError[c.id]}</div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          </>
        )}
      </div>
    </div>
  )
}
