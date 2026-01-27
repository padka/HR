import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type Recruiter = {
  id: number
  name: string
  tz?: string | null
  tg_chat_id?: string | null
  telemost_url?: string | null
  active?: boolean | null
  last_seen_at?: string | null
  is_online?: boolean | null
  city_ids?: number[]
  cities?: Array<{ name: string; tz?: string | null }>
  stats?: { total: number; free: number; pending: number; booked: number }
  next_free_local?: string | null
  next_is_future?: boolean
}

export function RecruitersPage() {
  const queryClient = useQueryClient()
  const [rowError, setRowError] = useState<Record<number, string>>({})
  const { data, isLoading, isError, error } = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
  })

  const toggleMutation = useMutation({
    mutationFn: async (payload: { recruiter: Recruiter; active: boolean }) => {
      const { recruiter, active } = payload
      const body = {
        name: recruiter.name,
        tz: recruiter.tz || 'Europe/Moscow',
        tg_chat_id: recruiter.tg_chat_id ? Number(recruiter.tg_chat_id) : null,
        telemost_url: recruiter.telemost_url || null,
        active,
        city_ids: recruiter.city_ids || [],
      }
      return apiFetch(`/recruiters/${recruiter.id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      })
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['recruiters'] })
      setRowError((prev) => {
        const next = { ...prev }
        delete next[variables.recruiter.id]
        return next
      })
    },
    onError: (err, variables) => {
      const message = err instanceof Error ? err.message : 'Ошибка обновления'
      setRowError((prev) => ({ ...prev, [variables.recruiter.id]: message }))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (recruiterId: number) =>
      apiFetch(`/recruiters/${recruiterId}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recruiters'] })
    },
    onError: (err, recruiterId) => {
      const message = err instanceof Error ? err.message : 'Ошибка удаления'
      setRowError((prev) => ({ ...prev, [recruiterId]: message }))
    },
  })

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <h1 className="title">Рекрутёры</h1>
          <Link to="/app/recruiters/new" className="glass action-link">+ Добавить</Link>
        </div>
          {isLoading && <p className="subtitle">Загрузка…</p>}
          {isError && <p style={{ color: '#f07373' }}>Ошибка: {(error as Error).message}</p>}
          {data && (
            <>
            {data.length === 0 && (
              <div className="glass panel--tight" style={{ marginTop: 12 }}>
                <p className="subtitle">Пока нет рекрутёров. Добавьте первого, чтобы начать работу.</p>
              </div>
            )}
            <div className="recruiter-cards">
              {data.map((r) => {
                const stats = r.stats || { total: 0, free: 0, pending: 0, booked: 0 }
                const loadPercent = stats.total ? Math.round((stats.booked / stats.total) * 100) : 0
                const initials = r.name
                  .split(' ')
                  .filter(Boolean)
                  .slice(0, 2)
                  .map((part) => part[0]?.toUpperCase())
                  .join('')
                const presenceClass = r.active
                  ? (r.is_online ? 'is-online' : 'is-away')
                  : 'is-inactive'
                return (
                  <div key={r.id} className="glass recruiter-card">
                    <div className="recruiter-card__header">
                      <div className="recruiter-card__identity">
                        <div className={`recruiter-avatar ${presenceClass}`} aria-hidden="true">
                          {initials || 'RS'}
                        </div>
                        <div>
                          <h3 className="recruiter-card__name">{r.name}</h3>
                          <div className="recruiter-card__meta">ID #{r.id} · {r.tz || '—'}</div>
                        </div>
                      </div>
                      <span className={`recruiter-card__status ${r.active ? 'is-active' : 'is-inactive'}`}>
                        {r.active ? 'Активен' : 'Отключен'}
                      </span>
                    </div>

                    <div className="recruiter-card__stats">
                      <div className="recruiter-stat">
                        <span>Свободно</span>
                        <strong>{stats.free}</strong>
                      </div>
                      <div className="recruiter-stat">
                        <span>Ожидают</span>
                        <strong>{stats.pending}</strong>
                      </div>
                      <div className="recruiter-stat">
                        <span>Занято</span>
                        <strong>{stats.booked}</strong>
                      </div>
                      <div className="recruiter-stat">
                        <span>Всего</span>
                        <strong>{stats.total}</strong>
                      </div>
                    </div>

                    <div className="recruiter-card__load">
                      <div className="recruiter-card__load-header">
                        <span>Занятость</span>
                        <strong>{loadPercent}%</strong>
                      </div>
                      <div className="recruiter-card__load-bar">
                        <span style={{ width: `${Math.min(loadPercent, 100)}%` }} />
                      </div>
                    </div>

                    <div className="recruiter-card__next">
                      <span>Ближайший слот</span>
                      <strong>{r.next_free_local || 'Нет свободных'}</strong>
                    </div>

                    <div className="recruiter-card__cities">
                      <div className="recruiter-card__section-title">Города</div>
                      <div className="recruiter-card__chips">
                        {r.cities && r.cities.length > 0 ? (
                          r.cities.slice(0, 6).map((city) => (
                            <span key={city.name} className="chip">{city.name}</span>
                          ))
                        ) : (
                          <span className="subtitle">Города не назначены</span>
                        )}
                        {r.cities && r.cities.length > 6 && (
                          <span className="chip">+{r.cities.length - 6}</span>
                        )}
                      </div>
                    </div>

                    <div className="recruiter-card__actions">
                      <label className="recruiter-card__toggle">
                        <input
                          type="checkbox"
                          checked={Boolean(r.active)}
                          onChange={(e) => toggleMutation.mutate({ recruiter: r, active: e.target.checked })}
                          disabled={toggleMutation.isPending}
                        />
                        <span>{r.active ? 'Активен' : 'Не активен'}</span>
                      </label>
                      <Link to="/app/recruiters/$recruiterId/edit" params={{ recruiterId: String(r.id) }}>
                        Редактировать →
                      </Link>
                      <button
                        className="ui-btn ui-btn--danger"
                        onClick={() =>
                          window.confirm(`Удалить рекрутёра ${r.name}?`) && deleteMutation.mutate(r.id)
                        }
                        disabled={deleteMutation.isPending}
                      >
                        Удалить
                      </button>
                      {rowError[r.id] && (
                        <div style={{ color: '#f07373', fontSize: 12 }}>{rowError[r.id]}</div>
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
    </RoleGuard>
  )
}
