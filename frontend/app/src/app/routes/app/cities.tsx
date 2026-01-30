import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

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
    <RoleGuard allow={['admin']}>
      <div className="page">
      <header className="glass glass--elevated page-header page-header--row">
        <h1 className="title">Города</h1>
        <Link to="/app/cities/new" className="ui-btn ui-btn--primary">+ Добавить</Link>
      </header>

      <section className="glass page-section">
        {isLoading && <p className="subtitle">Загрузка…</p>}
        {isError && <p className="text-danger">Ошибка: {(error as Error).message}</p>}
        {data && (
          <>
            {data.length === 0 && (
              <div className="empty-state">
                <p className="empty-state__text">Пока нет городов. Добавьте первый, чтобы начать работу.</p>
              </div>
            )}
            <div className="page-section__content">
              {data.map((c) => {
                const stages = stageByCityId.get(c.id) || []
                const customCount = stages.filter((s) => s.is_custom).length
                const responsibles = c.recruiters || []
                return (
                  <article key={c.id} className="glass glass--interactive list-item">
                    <div className="list-item__header">
                      <div className="list-item__info">
                        <h3 className="list-item__title">{c.name}</h3>
                        {c.criteria && <p className="list-item__subtitle">{c.criteria}</p>}
                      </div>
                      <span className={`status-badge status-badge--${(edits[c.id]?.active ?? c.active) ? 'success' : 'muted'}`}>
                        {(edits[c.id]?.active ?? c.active) ? 'Активен' : 'В архиве'}
                      </span>
                    </div>
                    <div className="list-item__chips">
                      <span className="chip">TZ: {c.tz || '—'}</span>
                      <span className="chip">Нед.: {edits[c.id]?.plan_week ?? c.plan_week ?? '—'}</span>
                      <span className="chip">Мес.: {edits[c.id]?.plan_month ?? c.plan_month ?? '—'}</span>
                    </div>
                    <div className="list-item__meta">
                      <div className="list-item__meta-label">Ответственные</div>
                      <div className="list-item__chips">
                        {responsibles.length > 0 ? (
                          responsibles.map((r) => <span key={r.id} className="chip chip--accent">{r.name}</span>)
                        ) : (
                          <span className="text-muted">Не назначены</span>
                        )}
                      </div>
                    </div>
                    {c.experts && (
                      <div className="text-muted text-sm">Эксперты: {c.experts}</div>
                    )}
                    {stages.length > 0 && (
                      <details className="details-summary">
                        <summary>Этапы найма: {stages.length} {customCount ? `(кастомных ${customCount})` : ''}</summary>
                        <div className="details-summary__content">
                          {stages.map((s) => (
                            <div key={s.key} className="glass glass--subtle details-summary__item">
                              <div className="font-semibold">{s.title}</div>
                              <div className="text-muted">{s.value || s.default || '—'}</div>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                    <div className="toolbar">
                      <label className="form-group__checkbox">
                        <input
                          type="checkbox"
                          checked={Boolean(edits[c.id]?.active ?? c.active)}
                          onChange={(e) =>
                            setEdits((prev) => ({ ...prev, [c.id]: { ...prev[c.id], active: e.target.checked } }))
                          }
                        />
                        <span>{(edits[c.id]?.active ?? c.active) ? 'Активен' : 'Не активен'}</span>
                      </label>
                      <Link to="/app/cities/$cityId/edit" params={{ cityId: String(c.id) }} className="ui-btn ui-btn--ghost">
                        Настроить
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
                        <span className="text-danger text-sm">{rowError[c.id]}</span>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          </>
        )}
      </section>
      </div>
    </RoleGuard>
  )
}
