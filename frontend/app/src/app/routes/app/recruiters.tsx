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
            <div style={{ marginTop: 12, display: 'grid', gap: 12 }}>
              {data.map((r) => {
                const stats = r.stats || { total: 0, free: 0, pending: 0, booked: 0 }
                const loadPercent = stats.total ? Math.round((stats.booked / stats.total) * 100) : 0
                return (
                  <div key={r.id} className="glass" style={{ padding: 16, display: 'grid', gap: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                      <div>
                        <h3 style={{ margin: 0 }}>{r.name}</h3>
                        <div className="subtitle">ID #{r.id} · {r.tz || '—'}</div>
                      </div>
                      <span className="chip">{r.active ? 'Активен' : 'Отключен'}</span>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      <span className="chip">Свободно: {stats.free}</span>
                      <span className="chip">Ожидают: {stats.pending}</span>
                      <span className="chip">Занято: {stats.booked}</span>
                      <span className="chip">Всего: {stats.total}</span>
                      <span className="chip">Занятость: {loadPercent}%</span>
                      <span className="chip">Ближайший слот: {r.next_free_local || 'Нет свободных'}</span>
                    </div>

                    <div>
                      <div className="subtitle" style={{ fontWeight: 600 }}>Города</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
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

                    <div className="action-row" style={{ flexWrap: 'wrap' }}>
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
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
