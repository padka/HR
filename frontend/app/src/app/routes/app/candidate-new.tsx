import { useState, useMemo, useEffect } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type City = {
  id: number
  name: string
  tz?: string | null
}

type Recruiter = {
  id: number
  name: string
  tz?: string | null
  active?: boolean
}

function formatTzOffset(tz: string): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    })
    const parts = formatter.formatToParts(new Date())
    const offsetPart = parts.find((p) => p.type === 'timeZoneName')
    return offsetPart?.value || tz
  } catch {
    return tz
  }
}

function getTomorrowDate(): string {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

function getNextWeekDate(): string {
  const d = new Date()
  d.setDate(d.getDate() + 7)
  return d.toISOString().slice(0, 10)
}

function getTodayDate(): string {
  return new Date().toISOString().slice(0, 10)
}

export function CandidateNewPage() {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    fio: '',
    phone: '',
    city_id: '',
    recruiter_id: '',
    interview_date: getTomorrowDate(),
    interview_time: '10:00',
  })

  const [error, setError] = useState<string | null>(null)

  const citiesQuery = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })

  const recruitersQuery = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
  })

  const cities = useMemo(() => citiesQuery.data ?? [], [citiesQuery.data])
  const recruiters = (recruitersQuery.data || []).filter((r) => r.active !== false)

  // Auto-select single options
  useEffect(() => {
    if (cities.length === 1 && !form.city_id) {
      setForm((f) => ({ ...f, city_id: String(cities[0].id) }))
    }
  }, [cities, form.city_id])

  useEffect(() => {
    if (recruiters.length === 1 && !form.recruiter_id) {
      setForm((f) => ({ ...f, recruiter_id: String(recruiters[0].id) }))
    }
  }, [recruiters, form.recruiter_id])

  const selectedCity = useMemo(() => {
    return cities.find((c) => String(c.id) === form.city_id)
  }, [cities, form.city_id])

  const selectedRecruiter = useMemo(() => {
    return recruiters.find((r) => String(r.id) === form.recruiter_id)
  }, [recruiters, form.recruiter_id])

  const cityTz = selectedCity?.tz || selectedRecruiter?.tz || 'Europe/Moscow'
  const tzLabel = formatTzOffset(cityTz)

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        fio: form.fio.trim(),
        phone: form.phone.trim() || null,
        city_id: form.city_id ? Number(form.city_id) : null,
        recruiter_id: form.recruiter_id ? Number(form.recruiter_id) : null,
        interview_date: form.interview_date,
        interview_time: form.interview_time,
      }
      return apiFetch<{ id: number }>('/candidates', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    onSuccess: (data: { id: number }) => {
      navigate({ to: '/app/candidates/$candidateId', params: { candidateId: String(data.id) } })
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const canSubmit =
    form.fio.trim() &&
    form.city_id &&
    form.recruiter_id &&
    form.interview_date &&
    form.interview_time

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (canSubmit) {
      setError(null)
      mutation.mutate()
    }
  }

  const formatPreviewDate = () => {
    if (!form.interview_date || !form.interview_time) return null
    try {
      const d = new Date(`${form.interview_date}T${form.interview_time}`)
      return new Intl.DateTimeFormat('ru-RU', {
        dateStyle: 'long',
        timeStyle: 'short',
      }).format(d)
    } catch {
      return null
    }
  }

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page">
        <form onSubmit={handleSubmit}>
          <div className="glass panel" style={{ display: 'grid', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div>
                <h1 className="title">Новый кандидат</h1>
                <p className="subtitle">Создайте лид и назначьте собеседование</p>
              </div>
              <Link to="/app/candidates" className="glass action-link">
                ← К списку
              </Link>
            </div>

            {(citiesQuery.isLoading || recruitersQuery.isLoading) && (
              <p className="subtitle">Загрузка данных...</p>
            )}

            {cities.length === 0 && !citiesQuery.isLoading && (
              <div className="glass panel--tight" style={{ background: 'rgba(240, 115, 115, 0.1)', border: '1px solid rgba(240, 115, 115, 0.3)' }}>
                <p style={{ color: '#f07373', margin: 0 }}>
                  Нет доступных городов. Обратитесь к администратору, чтобы продолжить работу.
                </p>
              </div>
            )}

            {recruiters.length === 0 && !recruitersQuery.isLoading && (
              <div className="glass panel--tight" style={{ background: 'rgba(240, 115, 115, 0.1)', border: '1px solid rgba(240, 115, 115, 0.3)' }}>
                <p style={{ color: '#f07373', margin: 0 }}>
                  Нет активных рекрутёров. <Link to="/app/recruiters/new">Добавьте рекрутёра</Link>.
                </p>
              </div>
            )}

            {error && (
              <div className="glass panel--tight" style={{ background: 'rgba(240, 115, 115, 0.1)', border: '1px solid rgba(240, 115, 115, 0.3)' }}>
                <p style={{ color: '#f07373', margin: 0 }}>Ошибка: {error}</p>
              </div>
            )}

            <section>
              <h2 className="title" style={{ fontSize: 18, marginBottom: 12 }}>Карточка кандидата</h2>
              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>ФИО <span style={{ color: '#f07373' }}>*</span></span>
                  <input
                    type="text"
                    value={form.fio}
                    onChange={(e) => setForm({ ...form, fio: e.target.value })}
                    placeholder="Иван Иванов"
                    required
                  />
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>Телефон</span>
                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    placeholder="+7 900 000-00-00"
                  />
                </label>
              </div>

              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', marginTop: 12 }}>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>Город <span style={{ color: '#f07373' }}>*</span></span>
                  <select
                    value={form.city_id}
                    onChange={(e) => setForm({ ...form, city_id: e.target.value })}
                    required
                    disabled={cities.length === 0}
                  >
                    <option value="">— выберите город —</option>
                    {cities.map((city) => (
                      <option key={city.id} value={city.id}>
                        {city.name} {city.tz ? `(${formatTzOffset(city.tz)})` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>Ответственный рекрутёр <span style={{ color: '#f07373' }}>*</span></span>
                  <select
                    value={form.recruiter_id}
                    onChange={(e) => setForm({ ...form, recruiter_id: e.target.value })}
                    required
                    disabled={recruiters.length === 0}
                  >
                    <option value="">— выберите рекрутёра —</option>
                    {recruiters.map((rec) => (
                      <option key={rec.id} value={rec.id}>
                        {rec.name} {rec.tz ? `(${formatTzOffset(rec.tz)})` : ''}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <section>
              <h2 className="title" style={{ fontSize: 18, marginBottom: 12 }}>Назначение собеседования</h2>
              {selectedCity && (
                <p className="subtitle" style={{ marginBottom: 8 }}>
                  Часовой пояс города: <strong>{cityTz}</strong> ({tzLabel})
                </p>
              )}
              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>Дата собеседования <span style={{ color: '#f07373' }}>*</span></span>
                  <input
                    type="date"
                    value={form.interview_date}
                    onChange={(e) => setForm({ ...form, interview_date: e.target.value })}
                    required
                  />
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ fontSize: 12, padding: '4px 8px' }}
                      onClick={() => setForm({ ...form, interview_date: getTodayDate() })}
                    >
                      Сегодня
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ fontSize: 12, padding: '4px 8px' }}
                      onClick={() => setForm({ ...form, interview_date: getTomorrowDate() })}
                    >
                      Завтра
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ fontSize: 12, padding: '4px 8px' }}
                      onClick={() => setForm({ ...form, interview_date: getNextWeekDate() })}
                    >
                      Через неделю
                    </button>
                  </div>
                </label>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>Время собеседования <span style={{ color: '#f07373' }}>*</span></span>
                  <input
                    type="time"
                    value={form.interview_time}
                    onChange={(e) => setForm({ ...form, interview_time: e.target.value })}
                    required
                  />
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ fontSize: 12, padding: '4px 8px' }}
                      onClick={() => setForm({ ...form, interview_time: '10:00' })}
                    >
                      10:00
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ fontSize: 12, padding: '4px 8px' }}
                      onClick={() => setForm({ ...form, interview_time: '14:00' })}
                    >
                      14:00
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ fontSize: 12, padding: '4px 8px' }}
                      onClick={() => setForm({ ...form, interview_time: '16:30' })}
                    >
                      16:30
                    </button>
                  </div>
                </label>
              </div>
            </section>

            {canSubmit && (
              <div className="glass panel--tight" style={{ background: 'rgba(105, 183, 255, 0.1)' }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>Превью</h3>
                <div style={{ fontSize: 13, display: 'grid', gap: 4 }}>
                  <div><strong>ФИО:</strong> {form.fio}</div>
                  {form.phone && <div><strong>Телефон:</strong> {form.phone}</div>}
                  <div><strong>Город:</strong> {selectedCity?.name || '—'}</div>
                  <div><strong>Рекрутёр:</strong> {selectedRecruiter?.name || '—'}</div>
                  <div><strong>Интервью:</strong> {formatPreviewDate()} ({tzLabel})</div>
                </div>
              </div>
            )}

            <div className="action-row">
              <button
                type="submit"
                className="ui-btn ui-btn--primary"
                disabled={!canSubmit || mutation.isPending}
              >
                {mutation.isPending ? 'Сохраняем...' : 'Создать кандидата'}
              </button>
              <Link to="/app/candidates" className="ui-btn ui-btn--ghost">
                Отмена
              </Link>
            </div>
          </div>
        </form>
      </div>
    </RoleGuard>
  )
}
