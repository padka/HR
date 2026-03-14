import { useState, useMemo, useEffect } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { formatTzOffset, getTomorrowDate } from '@/shared/utils/formatters'
import { getNextWeekDate, getTodayDate } from '@/shared/utils/timezone'

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

type CandidateCreateResponse = {
  id: number
  fio?: string
  city?: string | null
  slot_scheduled?: boolean
}

type ScheduleSlotResponse = {
  status?: string
  message?: string
}

type SubmitResult = {
  candidate: CandidateCreateResponse
  schedule:
    | { status: 'skipped' }
    | { status: 'success'; message: string }
    | { status: 'warning'; message: string }
}

function extractError(err: unknown): { code: string; message: string } {
  if (err instanceof Error) {
    const data = (err as Error & { data?: { error?: string; message?: string } }).data
    const code = data?.error || ''
    const message = data?.message || err.message || 'Ошибка'
    return { code, message }
  }
  return { code: '', message: 'Ошибка' }
}

export function CandidateNewPage() {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    fio: '',
    phone: '',
    telegram_id: '',
    city_id: '',
    recruiter_id: '',
    interview_date: getTomorrowDate(),
    interview_time: '10:00',
    schedule_now: true,
  })

  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ tone: 'success' | 'warning'; message: string; candidateId?: number } | null>(null)

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
    mutationFn: async (): Promise<SubmitResult> => {
      const telegramId = form.telegram_id.trim()
      const payload: {
        fio: string
        phone: string | null
        telegram_id: number | null
        city_id: number | null
        recruiter_id: number | null
        interview_date?: string
        interview_time?: string
      } = {
        fio: form.fio.trim(),
        phone: form.phone.trim() || null,
        telegram_id: telegramId ? Number(telegramId) : null,
        city_id: form.city_id ? Number(form.city_id) : null,
        recruiter_id: form.recruiter_id ? Number(form.recruiter_id) : null,
      }
      if (form.schedule_now && form.interview_date && form.interview_time) {
        payload.interview_date = form.interview_date
        payload.interview_time = form.interview_time
      }

      const candidate = await apiFetch<CandidateCreateResponse>('/candidates', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      if (!form.schedule_now || !form.interview_date || !form.interview_time) {
        return {
          candidate,
          schedule: { status: 'skipped' },
        }
      }

      try {
        const schedule = await apiFetch<ScheduleSlotResponse>(`/candidates/${candidate.id}/schedule-slot`, {
          method: 'POST',
          body: JSON.stringify({
            recruiter_id: payload.recruiter_id,
            city_id: payload.city_id,
            date: form.interview_date,
            time: form.interview_time,
          }),
        })
        return {
          candidate,
          schedule: {
            status: 'success',
            message: schedule.message || 'Собеседование назначено',
          },
        }
      } catch (err) {
        const { code, message } = extractError(err)
        if (code === 'candidate_telegram_missing' || code === 'slot_conflict') {
          return {
            candidate,
            schedule: {
              status: 'warning',
              message,
            },
          }
        }
        throw err
      }
    },
    onSuccess: (result: SubmitResult) => {
      if (result.schedule.status === 'warning') {
        setNotice({
          tone: 'warning',
          message: `Кандидат создан. ${result.schedule.message} Назначьте слот позже из карточки кандидата.`,
          candidateId: result.candidate.id,
        })
        return
      }
      if (result.schedule.status === 'success') {
        setNotice({
          tone: 'success',
          message: `Кандидат создан. ${result.schedule.message}.`,
          candidateId: result.candidate.id,
        })
      } else {
        setNotice({
          tone: 'success',
          message: 'Кандидат успешно создан.',
          candidateId: result.candidate.id,
        })
      }
      navigate({ to: '/app/candidates/$candidateId', params: { candidateId: String(result.candidate.id) } })
    },
    onError: (err: Error) => {
      const parsed = extractError(err)
      setError(parsed.message)
    },
  })

  const canSubmit =
    form.fio.trim() &&
    form.city_id &&
    form.recruiter_id &&
    (!form.schedule_now || (form.interview_date && form.interview_time))

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (canSubmit) {
      setError(null)
      setNotice(null)
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
          <div className="glass panel ui-form-shell candidate-new">
            <div className="ui-form-header">
              <div>
                <h1 className="title">Новый кандидат</h1>
                <p className="subtitle">Создайте лид и назначьте собеседование</p>
              </div>
              <Link to="/app/candidates" className="glass action-link">
                ← К списку
              </Link>
            </div>

            {(citiesQuery.isLoading || recruitersQuery.isLoading) && (
              <p className="ui-message ui-message--muted">Загрузка данных...</p>
            )}

            {cities.length === 0 && !citiesQuery.isLoading && (
              <div className="glass panel--tight ui-state ui-state--error">
                <p className="ui-message ui-message--error">
                  Нет доступных городов. Обратитесь к администратору, чтобы продолжить работу.
                </p>
              </div>
            )}

            {recruiters.length === 0 && !recruitersQuery.isLoading && (
              <div className="glass panel--tight ui-state ui-state--error">
                <p className="ui-message ui-message--error">
                  Нет активных рекрутёров. <Link to="/app/recruiters/new">Добавьте рекрутёра</Link>.
                </p>
              </div>
            )}

            {error && (
              <div className="glass panel--tight ui-state ui-state--error">
                <p className="ui-message ui-message--error">Ошибка: {error}</p>
              </div>
            )}

            <section>
              <h2 className="title candidate-new__section-title">Карточка кандидата</h2>
              <div className="ui-form-grid ui-form-grid--lg candidate-new__secondary-grid">
                <label className="ui-field">
                  <span>ФИО <span className="ui-required">*</span></span>
                  <input
                    type="text"
                    value={form.fio}
                    onChange={(e) => setForm({ ...form, fio: e.target.value })}
                    placeholder="Иван Иванов"
                    required
                  />
                </label>
                <label className="ui-field">
                  <span>Телефон</span>
                  <input
                    type="text"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    placeholder="+7 900 000-00-00"
                  />
                </label>
                <label className="ui-field">
                  <span>Telegram ID</span>
                  <input
                    type="text"
                    value={form.telegram_id}
                    onChange={(e) => setForm({ ...form, telegram_id: e.target.value.replace(/[^\d]/g, '') })}
                    placeholder="79991234567"
                  />
                </label>
              </div>

              <div className="ui-form-grid ui-form-grid--lg">
                <label className="ui-field">
                  <span>Город <span className="ui-required">*</span></span>
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
                <label className="ui-field">
                  <span>Ответственный рекрутёр <span className="ui-required">*</span></span>
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
              <h2 className="title candidate-new__section-title">Назначение собеседования</h2>
              {selectedCity && (
                <p className="subtitle candidate-new__section-note">
                  Часовой пояс города: <strong>{cityTz}</strong> ({tzLabel})
                </p>
              )}
              <label className="ui-inline-checkbox candidate-new__toggle">
                <input
                  type="checkbox"
                  checked={form.schedule_now}
                  onChange={(e) => setForm({ ...form, schedule_now: e.target.checked })}
                />
                <span>Назначить собеседование сразу</span>
              </label>
              <div className="ui-form-grid ui-form-grid--md">
                <label className="ui-field">
                  <span>
                    Дата собеседования {form.schedule_now ? <span className="ui-required">*</span> : null}
                  </span>
                  <input
                    type="date"
                    value={form.interview_date}
                    onChange={(e) => setForm({ ...form, interview_date: e.target.value })}
                    required={form.schedule_now}
                    disabled={!form.schedule_now}
                  />
                  <div className="ui-inline-controls">
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost candidate-new__quick-btn"
                      disabled={!form.schedule_now}
                      onClick={() => setForm({ ...form, interview_date: getTodayDate() })}
                    >
                      Сегодня
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost candidate-new__quick-btn"
                      disabled={!form.schedule_now}
                      onClick={() => setForm({ ...form, interview_date: getTomorrowDate() })}
                    >
                      Завтра
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost candidate-new__quick-btn"
                      disabled={!form.schedule_now}
                      onClick={() => setForm({ ...form, interview_date: getNextWeekDate() })}
                    >
                      Через неделю
                    </button>
                  </div>
                </label>
                <label className="ui-field">
                  <span>
                    Время собеседования {form.schedule_now ? <span className="ui-required">*</span> : null}
                  </span>
                  <input
                    type="time"
                    value={form.interview_time}
                    onChange={(e) => setForm({ ...form, interview_time: e.target.value })}
                    required={form.schedule_now}
                    disabled={!form.schedule_now}
                  />
                  <div className="ui-inline-controls">
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost candidate-new__quick-btn"
                      disabled={!form.schedule_now}
                      onClick={() => setForm({ ...form, interview_time: '10:00' })}
                    >
                      10:00
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost candidate-new__quick-btn"
                      disabled={!form.schedule_now}
                      onClick={() => setForm({ ...form, interview_time: '14:00' })}
                    >
                      14:00
                    </button>
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost candidate-new__quick-btn"
                      disabled={!form.schedule_now}
                      onClick={() => setForm({ ...form, interview_time: '16:30' })}
                    >
                      16:30
                    </button>
                  </div>
                </label>
              </div>
              {!form.schedule_now && (
                <div className="ui-field__support">
                  <p className="ui-field__note">Собеседование можно назначить позже в карточке кандидата.</p>
                </div>
              )}
            </section>

            {notice && (
              <div
                className={`glass panel--tight candidate-new__notice ${
                  notice.tone === 'warning' ? 'candidate-new__notice--warning' : 'candidate-new__notice--success'
                }`}
              >
                <p className="ui-message">{notice.message}</p>
                {notice.candidateId ? (
                  <div>
                    <Link to="/app/candidates/$candidateId" params={{ candidateId: String(notice.candidateId) }} className="ui-btn ui-btn--ghost">
                      Открыть карточку кандидата
                    </Link>
                  </div>
                ) : null}
              </div>
            )}

            {canSubmit && (
              <div className="glass panel--tight candidate-new__preview">
                <h3 className="candidate-new__preview-title">Превью</h3>
                <div className="candidate-new__preview-list">
                  <div><strong>ФИО:</strong> {form.fio}</div>
                  {form.phone && <div><strong>Телефон:</strong> {form.phone}</div>}
                  {form.telegram_id && <div><strong>Telegram ID:</strong> {form.telegram_id}</div>}
                  <div><strong>Город:</strong> {selectedCity?.name || '—'}</div>
                  <div><strong>Рекрутёр:</strong> {selectedRecruiter?.name || '—'}</div>
                  <div>
                    <strong>Интервью:</strong>{' '}
                    {form.schedule_now ? `${formatPreviewDate()} (${tzLabel})` : 'Назначение позже'}
                  </div>
                </div>
              </div>
            )}

            <div className="ui-form-actions ui-form-actions--end">
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
