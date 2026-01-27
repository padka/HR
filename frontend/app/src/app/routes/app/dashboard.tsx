import { useQuery, useMutation } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '@/api/client'
import { useProfile } from '@/app/hooks/useProfile'
import { Link } from '@tanstack/react-router'

type SummaryPayload = {
  recruiters: number
  cities: number
  slots_total: number
  slots_free: number
  slots_pending: number
  slots_booked: number
  waiting_candidates_total: number
  test1_rejections_total: number
  test1_total_seen: number
  test1_rejections_percent: number
}

type CalendarDay = {
  date: string
  label: string
  weekday: string
  count: number
  is_today: boolean
  is_selected: boolean
}

type CalendarEvent = {
  id: number
  status: string
  status_label: string
  status_variant: string
  start_time: string
  end_time: string
  duration: number
  recruiter: { id: number | null; name: string }
  city: { id: number | null; name: string }
  candidate: {
    id?: number | null
    name: string
    profile_url?: string | null
    telegram_id?: number | null
    status_slug?: string | null
  }
}

type CalendarPayload = {
  selected_date: string
  selected_label: string
  selected_human: string
  timezone: string
  days: CalendarDay[]
  events: CalendarEvent[]
  events_total: number
  status_summary: Record<string, number>
  meta: string
  updated_label: string
}

type KPITrend = {
  display: string
  label: string
}

type KPICard = {
  key: string
  label: string
  tone: string
  icon: string
  value: number
  previous: number
  trend: KPITrend
}

type KPIResponse = {
  current: {
    label: string
    metrics: KPICard[]
  }
  previous: {
    label: string
  }
}

type RecruiterOption = {
  id: number
  name: string
}

type LeaderboardItem = {
  recruiter_id: number
  name: string
  score: number
  rank: number
  conversion_interview: number
  confirmation_rate: number
  fill_rate: number
  throughput: number
  candidates_total: number
  hired_total: number
  declined_total: number
}

type LeaderboardPayload = {
  window: { from: string; to: string; days: number }
  items: LeaderboardItem[]
}

type PlanEntry = {
  id: number
  last_name: string
  created_at?: string | null
}

type RecruiterCityPlan = {
  city_id: number
  city_name: string
  tz?: string | null
  plan_week?: number | null
  plan_month?: number | null
  filled_count: number
  remaining_week?: number | null
  remaining_month?: number | null
  entries: PlanEntry[]
}

type IncomingCandidate = {
  id: number
  name: string | null
  city: string | null
  city_id?: number | null
  status_display?: string | null
  status_slug?: string | null
  waiting_hours?: number | null
  availability_window?: string | null
  profile_url?: string | null
}

type IncomingPayload = {
  items: IncomingCandidate[]
}

function toIsoDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

function getDefaultRange() {
  const today = new Date()
  const from = new Date(today)
  from.setDate(from.getDate() - 6)
  return {
    from: toIsoDate(from),
    to: toIsoDate(today),
  }
}

function ModalPortal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}

export function DashboardPage() {
  const profile = useProfile()
  const isAdmin = profile.data?.principal.type === 'admin'
  const initialRange = useMemo(() => getDefaultRange(), [])
  const [rangeFrom, setRangeFrom] = useState(initialRange.from)
  const [rangeTo, setRangeTo] = useState(initialRange.to)
  const [calendarDate, setCalendarDate] = useState(initialRange.to)
  const [recruiterId, setRecruiterId] = useState('')
  const [planInputs, setPlanInputs] = useState<Record<number, string>>({})
  const [toast, setToast] = useState<string | null>(null)
  const [rescheduleTarget, setRescheduleTarget] = useState<CalendarEvent | null>(null)
  const [rescheduleDate, setRescheduleDate] = useState('')
  const [rescheduleTime, setRescheduleTime] = useState('')
  const [rescheduleReason, setRescheduleReason] = useState('')
  const [incomingTarget, setIncomingTarget] = useState<IncomingCandidate | null>(null)
  const [incomingDate, setIncomingDate] = useState('')
  const [incomingTime, setIncomingTime] = useState('')
  const [incomingMessage, setIncomingMessage] = useState('')

  const showToast = (message: string) => {
    setToast(message)
    window.clearTimeout((showToast as any)._t)
    ;(showToast as any)._t = window.setTimeout(() => setToast(null), 2400)
  }

  const summaryQuery = useQuery<SummaryPayload>({
    queryKey: ['dashboard-summary'],
    queryFn: () => apiFetch('/dashboard/summary'),
    enabled: Boolean(isAdmin),
  })

  const recruitersQuery = useQuery<RecruiterOption[]>({
    queryKey: ['dashboard-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
    staleTime: 60_000,
  })

  const calendarParams = useMemo(() => {
    const params = new URLSearchParams()
    params.set('date', calendarDate)
    params.set('days', '14')
    if (recruiterId) params.set('recruiter', recruiterId)
    return params.toString()
  }, [calendarDate, recruiterId])

  const calendarQuery = useQuery<CalendarPayload>({
    queryKey: ['dashboard-calendar', calendarParams],
    queryFn: () => apiFetch(`/dashboard/calendar?${calendarParams}`),
    enabled: !isAdmin,
  })

  const planQuery = useQuery<RecruiterCityPlan[]>({
    queryKey: ['recruiter-plan'],
    queryFn: () => apiFetch('/recruiter-plan'),
    enabled: !isAdmin,
  })

  const incomingQuery = useQuery<IncomingPayload>({
    queryKey: ['dashboard-incoming'],
    queryFn: () => apiFetch('/dashboard/incoming'),
    enabled: !isAdmin,
  })

  const kpiParams = useMemo(() => {
    if (!recruiterId) return ''
    const params = new URLSearchParams()
    params.set('recruiter', recruiterId)
    return `?${params.toString()}`
  }, [recruiterId])

  const kpiQuery = useQuery<KPIResponse>({
    queryKey: ['dashboard-kpis', kpiParams],
    queryFn: () => apiFetch(`/kpis/current${kpiParams}`),
    enabled: Boolean(isAdmin),
  })

  const leaderboardParams = useMemo(() => {
    const params = new URLSearchParams()
    if (rangeFrom) params.set('from', rangeFrom)
    if (rangeTo) params.set('to', rangeTo)
    return params.toString()
  }, [rangeFrom, rangeTo])

  const leaderboardQuery = useQuery<LeaderboardPayload>({
    queryKey: ['dashboard-leaderboard', leaderboardParams],
    queryFn: () => apiFetch(`/dashboard/recruiter-performance?${leaderboardParams}`),
    enabled: Boolean(isAdmin),
  })

  const addPlanEntry = useMutation({
    mutationFn: async (payload: { cityId: number; lastName: string }) => {
      return apiFetch(`/recruiter-plan/${payload.cityId}/entries`, {
        method: 'POST',
        body: JSON.stringify({ last_name: payload.lastName }),
      })
    },
    onSuccess: (_data, variables) => {
      setPlanInputs((prev) => ({ ...prev, [variables.cityId]: '' }))
      planQuery.refetch()
    },
  })

  const removePlanEntry = useMutation({
    mutationFn: async (entryId: number) => {
      return apiFetch(`/recruiter-plan/entries/${entryId}`, {
        method: 'DELETE',
      })
    },
    onSuccess: () => {
      planQuery.refetch()
    },
  })

  const rejectSlot = useMutation({
    mutationFn: async (slotId: number) =>
      apiFetch(`/slots/${slotId}/reject_booking`, { method: 'POST' }),
    onSuccess: (data: any) => {
      showToast(data?.message || 'Слот освобождён')
      calendarQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const rescheduleSlot = useMutation({
    mutationFn: async (payload: { slotId: number; date: string; time: string; reason?: string }) =>
      apiFetch(`/slots/${payload.slotId}/reschedule`, {
        method: 'POST',
        body: JSON.stringify({ date: payload.date, time: payload.time, reason: payload.reason || '' }),
      }),
    onSuccess: (data: any) => {
      showToast(data?.message || 'Слот перенесён')
      setRescheduleTarget(null)
      calendarQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const candidateAction = useMutation({
    mutationFn: async (payload: { candidateId: number; actionKey: string }) =>
      apiFetch(`/candidates/${payload.candidateId}/actions/${payload.actionKey}`, {
        method: 'POST',
      }),
    onSuccess: (data: any) => {
      showToast(data?.message || 'Действие выполнено')
      calendarQuery.refetch()
      incomingQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const rejectCandidate = useMutation({
    mutationFn: async (candidateId: number) =>
      apiFetch(`/candidates/${candidateId}/actions/reject`, { method: 'POST' }),
    onSuccess: (data: any) => {
      showToast(data?.message || 'Кандидат отклонён')
      incomingQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const scheduleIncoming = useMutation({
    mutationFn: async (payload: { candidate: IncomingCandidate; date: string; time: string; message?: string }) => {
      const recruiterId = profile.data?.recruiter?.id
      if (!recruiterId) {
        throw new Error('Нет данных рекрутера')
      }
      if (!payload.candidate.city_id) {
        throw new Error('Не удалось определить город кандидата')
      }
      return apiFetch(`/candidates/${payload.candidate.id}/schedule-slot`, {
        method: 'POST',
        body: JSON.stringify({
          recruiter_id: recruiterId,
          city_id: payload.candidate.city_id,
          date: payload.date,
          time: payload.time,
          custom_message: payload.message || '',
        }),
      })
    },
    onSuccess: (data: any) => {
      showToast(data?.message || 'Собеседование назначено')
      setIncomingTarget(null)
      incomingQuery.refetch()
      calendarQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const openReschedule = (event: CalendarEvent) => {
    const selected = calendarQuery.data?.selected_date || toIsoDate(new Date())
    setRescheduleTarget(event)
    setRescheduleDate(selected)
    setRescheduleTime(event.start_time || '09:00')
    setRescheduleReason('')
  }

  const openIncomingSchedule = (candidate: IncomingCandidate) => {
    const selected = calendarQuery.data?.selected_date || toIsoDate(new Date())
    setIncomingTarget(candidate)
    setIncomingDate(selected)
    setIncomingTime('10:00')
    setIncomingMessage('')
  }

  const summaryCards = useMemo(() => {
    const data = summaryQuery.data
    if (!data) return []
    return [
      { label: 'Рекрутёры', value: data.recruiters },
      { label: 'Города', value: data.cities },
      { label: 'Слоты (всего)', value: data.slots_total },
      { label: 'Свободные', value: data.slots_free },
      { label: 'Ожидают', value: data.slots_pending },
      { label: 'Забронированы', value: data.slots_booked },
      { label: 'Ждут слота', value: data.waiting_candidates_total },
      { label: 'Отказы тест1', value: data.test1_rejections_total },
      { label: '% отказов тест1', value: data.test1_rejections_percent },
    ]
  }, [summaryQuery.data])

  return (
    <div className="page dashboard-page">
      <header className="glass glass--elevated panel dashboard-header dashboard-hero">
        <div className="dashboard-hero__content">
          <h1 className="title title--lg">Дашборд</h1>
          <p className="subtitle">
            {isAdmin
              ? 'Метрики отдела, KPI и эффективность рекрутеров.'
              : 'Входящие кандидаты, план по городам и подтверждённые интервью.'}
          </p>
        </div>
        {isAdmin && (
          <div className="dashboard-filters">
            <div className="filter-group">
              <label className="filter-field">
                <span>От</span>
                <input
                  type="date"
                  value={rangeFrom}
                  onChange={(e) => {
                    const next = e.target.value
                    setRangeFrom(next)
                    if (rangeTo && next > rangeTo) setRangeTo(next)
                  }}
                />
              </label>
              <label className="filter-field">
                <span>До</span>
                <input
                  type="date"
                  value={rangeTo}
                  onChange={(e) => {
                    const next = e.target.value
                    setRangeTo(next)
                    if (rangeFrom && next < rangeFrom) setRangeFrom(next)
                  }}
                />
              </label>
            </div>
            <label className="filter-field">
              <span>Рекрутёр</span>
              <select
                value={recruiterId}
                onChange={(e) => setRecruiterId(e.target.value)}
              >
                <option value="">Все специалисты</option>
                {(recruitersQuery.data || []).map((rec) => (
                  <option key={rec.id} value={rec.id}>
                    {rec.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </header>

      {isAdmin && (
        <section className="glass panel dashboard-summary">
          <div className="dashboard-section-header">
            <h2 className="section-title">Общая сводка</h2>
            {summaryQuery.isFetching && <span className="text-muted text-xs">Обновление…</span>}
          </div>
          
          {summaryQuery.isLoading && (
            <div className="grid-cards">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="glass glass--subtle stat-card skeleton" style={{ height: 100 }} />
              ))}
            </div>
          )}
          
          {summaryQuery.isError && (
            <div className="glass panel text-danger">
              Ошибка: {(summaryQuery.error as Error).message}
            </div>
          )}
          
          {summaryCards.length > 0 && (
            <div className="grid-cards">
              {summaryCards.map((card) => (
                <Metric key={card.label} title={card.label} value={card.value} />
              ))}
            </div>
          )}
        </section>
      )}

      <div className="dashboard-main-grid">
        {isAdmin && (
          <div className="glass panel dashboard-panel dashboard-leaderboard">
            <div className="dashboard-section-header">
              <div>
                <h2 className="section-title">Лидерборд эффективности</h2>
                <p className="subtitle">
                  Оценка по конверсии, подтверждениям и загрузке слотов
                </p>
              </div>
              <button
                className="ui-btn ui-btn--ghost"
                onClick={() => leaderboardQuery.refetch()}
              >
                Обновить
              </button>
            </div>
            {leaderboardQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {leaderboardQuery.isError && (
              <p style={{ color: '#f07373' }}>
                Ошибка: {(leaderboardQuery.error as Error).message}
              </p>
            )}
            {leaderboardQuery.data?.items?.length ? (
              <div className="leaderboard-table-wrap">
                <table className="leaderboard-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Рекрутёр</th>
                      <th>Score</th>
                      <th>Конверсия</th>
                      <th>Подтв.</th>
                      <th>Заполн.</th>
                      <th>Кандидаты</th>
                      <th>Нанято</th>
                      <th>Отказ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboardQuery.data.items.map((item) => {
                      const isSelected =
                        recruiterId && Number(recruiterId) === item.recruiter_id
                      const isTop = item.rank <= 3
                      return (
                        <tr
                          key={item.recruiter_id}
                          className={`${isSelected ? 'is-selected' : ''} ${isTop ? 'is-top' : ''}`}
                        >
                          <td>{item.rank}</td>
                          <td>{item.name}</td>
                          <td>
                            <span className="leaderboard-score">{item.score}</span>
                          </td>
                          <td>{item.conversion_interview}%</td>
                          <td>{item.confirmation_rate}%</td>
                          <td>{item.fill_rate}%</td>
                          <td>{item.throughput}</td>
                          <td>{item.hired_total}</td>
                          <td>{item.declined_total}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="subtitle">Нет данных за выбранный период.</p>
            )}
          </div>
        )}

        {!isAdmin && (
          <div className="glass panel dashboard-panel recruiter-plan">
            <div className="dashboard-section-header">
              <div>
                <h2 className="section-title">План по городам</h2>
                <p className="subtitle">Добавляйте фамилии кандидатов вручную, чтобы видеть прогресс.</p>
              </div>
              <button className="ui-btn ui-btn--ghost" onClick={() => planQuery.refetch()}>
                Обновить
              </button>
            </div>
            {planQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {planQuery.isError && (
              <p style={{ color: '#f07373' }}>Ошибка: {(planQuery.error as Error).message}</p>
            )}
            {planQuery.data && planQuery.data.length === 0 && (
              <p className="subtitle">Нет назначенных городов.</p>
            )}
            {planQuery.data && planQuery.data.length > 0 && (
              <div className="plan-grid">
                {planQuery.data.map((plan) => {
                  const target = plan.plan_week ?? plan.plan_month
                  const remaining =
                    plan.plan_week != null
                      ? plan.remaining_week
                      : plan.plan_month != null
                        ? plan.remaining_month
                        : null
                  const safeTarget = target ?? 0
                  const progress =
                    safeTarget > 0 ? Math.min(100, Math.round((plan.filled_count / safeTarget) * 100)) : null
                  const inputValue = planInputs[plan.city_id] ?? ''
                  return (
                    <div key={plan.city_id} className="glass glass--subtle plan-card">
                      <div className="plan-card__header">
                        <div>
                          <div className="plan-card__title">{plan.city_name}</div>
                          <div className="plan-card__meta">{plan.tz || 'TZ не задан'}</div>
                        </div>
                        <div className="plan-card__targets">
                          {plan.plan_week != null && (
                            <span className="plan-pill">План/нед: {plan.plan_week}</span>
                          )}
                          {plan.plan_month != null && (
                            <span className="plan-pill">План/мес: {plan.plan_month}</span>
                          )}
                        </div>
                      </div>
                      <div className="plan-card__progress">
                        <div className="plan-progress__label">
                          {progress != null ? `Выполнено ${progress}%` : 'План не задан'}
                        </div>
                        <div className="plan-progress">
                          <span style={{ width: `${progress ?? 0}%` }} />
                        </div>
                      </div>
                      <div className="plan-card__stats">
                        <div>
                          <div className="plan-card__label">Внесено</div>
                          <div className="plan-card__value">{plan.filled_count}</div>
                        </div>
                        <div>
                          <div className="plan-card__label">Осталось</div>
                          <div className="plan-card__value">
                            {remaining != null ? remaining : target != null ? Math.max(target - plan.filled_count, 0) : '—'}
                          </div>
                        </div>
                      </div>
                      <div className="plan-card__form">
                        <input
                          type="text"
                          placeholder="Фамилия кандидата"
                          value={inputValue}
                          onChange={(e) =>
                            setPlanInputs((prev) => ({ ...prev, [plan.city_id]: e.target.value }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              if (inputValue.trim()) {
                                addPlanEntry.mutate({ cityId: plan.city_id, lastName: inputValue.trim() })
                              }
                            }
                          }}
                        />
                        <button
                          className="ui-btn ui-btn--primary ui-btn--sm"
                          type="button"
                          disabled={!inputValue.trim() || addPlanEntry.isPending}
                          onClick={() =>
                            addPlanEntry.mutate({ cityId: plan.city_id, lastName: inputValue.trim() })
                          }
                        >
                          Добавить
                        </button>
                      </div>
                      <div className="plan-card__entries">
                        {plan.entries.length === 0 && (
                          <span className="text-muted text-sm">Пока нет фамилий</span>
                        )}
                        {plan.entries.map((entry) => (
                          <button
                            key={entry.id}
                            type="button"
                            className="plan-chip"
                            onClick={() => removePlanEntry.mutate(entry.id)}
                          >
                            {entry.last_name}
                            <span className="plan-chip__remove">×</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {!isAdmin && (
          <div className="glass panel dashboard-panel dashboard-incoming">
            <div className="dashboard-section-header">
              <div>
                <h2 className="section-title">Входящие</h2>
                <p className="subtitle">Кандидаты прошли тест 1 и ждут свободные слоты.</p>
              </div>
              <button className="ui-btn ui-btn--ghost" onClick={() => incomingQuery.refetch()}>
                Обновить
              </button>
            </div>
            {incomingQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {incomingQuery.isError && (
              <p style={{ color: '#f07373' }}>Ошибка: {(incomingQuery.error as Error).message}</p>
            )}
            {incomingQuery.data && incomingQuery.data.items.length === 0 && (
              <p className="subtitle">Нет кандидатов, ожидающих слот.</p>
            )}
            {incomingQuery.data && incomingQuery.data.items.length > 0 && (
              <div className="incoming-grid">
                {incomingQuery.data.items.map((candidate) => (
                  <div key={candidate.id} className="glass glass--subtle incoming-card">
                    <div className="incoming-card__main">
                      <div>
                        <div className="incoming-card__name">{candidate.name || 'Без имени'}</div>
                        <div className="incoming-card__meta">
                          <span>{candidate.city || 'Город не указан'}</span>
                          {candidate.waiting_hours != null && (
                            <span>· ждёт {candidate.waiting_hours} ч</span>
                          )}
                          {candidate.availability_window && (
                            <span>· {candidate.availability_window}</span>
                          )}
                        </div>
                      </div>
                      {candidate.status_display && (
                        <span
                          className={`status-pill status-pill--${
                            candidate.status_slug === 'stalled_waiting_slot' ? 'danger' : 'warning'
                          }`}
                        >
                          {candidate.status_display}
                        </span>
                      )}
                    </div>
                    <div className="incoming-card__actions">
                      <Link
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        to="/app/candidates/$candidateId"
                        params={{ candidateId: String(candidate.id) }}
                      >
                        Профиль
                      </Link>
                      <button
                        className="ui-btn ui-btn--primary ui-btn--sm"
                        type="button"
                        onClick={() => openIncomingSchedule(candidate)}
                      >
                        Назначить
                      </button>
                      <button
                        className="ui-btn ui-btn--danger ui-btn--sm"
                        type="button"
                        onClick={() => rejectCandidate.mutate(candidate.id)}
                      >
                        Отказать
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {!isAdmin && (
          <div className="glass panel dashboard-panel">
            <div className="dashboard-section-header">
              <div>
                <h2 className="section-title">Календарь интервью</h2>
                <p className="subtitle">
                  {calendarQuery.data?.selected_human} · {calendarQuery.data?.meta}
                </p>
              </div>
              <button className="ui-btn ui-btn--ghost" onClick={() => calendarQuery.refetch()}>
                Обновить
              </button>
            </div>
            {calendarQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {calendarQuery.isError && (
              <p style={{ color: '#f07373' }}>Ошибка: {(calendarQuery.error as Error).message}</p>
            )}
            {calendarQuery.data && (
              <>
                <div className="calendar-grid">
                  {calendarQuery.data.days.map((day) => (
                    <button
                      key={day.date}
                      className={`calendar-day${day.is_selected ? ' is-selected' : ''}${day.is_today ? ' is-today' : ''}`}
                      onClick={() => setCalendarDate(day.date)}
                    >
                      <span className="calendar-day__weekday">{day.weekday}</span>
                      <span className="calendar-day__label">{day.label}</span>
                      <span className="calendar-day__count">{day.count}</span>
                    </button>
                  ))}
                </div>
                <div className="calendar-meta">
                  <span>Подтверждено: {calendarQuery.data.status_summary?.CONFIRMED_BY_CANDIDATE ?? 0}</span>
                </div>
                <div className="calendar-events">
                  {calendarQuery.data.events.length === 0 && (
                    <p className="subtitle">Нет слотов на выбранную дату.</p>
                  )}
                  {calendarQuery.data.events.map((event) => (
                    <div key={event.id} className="calendar-event">
                      <div className="calendar-event__primary">
                        <div className="calendar-event__header">
                          <div className="calendar-event__time">
                            {event.start_time}–{event.end_time}
                          </div>
                          <span
                            className={`status-pill status-pill--${
                              event.status_variant === 'accent' ? 'info' : event.status_variant
                            }`}
                          >
                            {event.status_label}
                          </span>
                        </div>
                        <div className="calendar-event__meta">
                          {event.candidate.name}
                          {event.city.name ? ` · ${event.city.name}` : ''}
                        </div>
                      </div>
                      <div className="calendar-event__actions">
                        {event.candidate.id ? (
                          <Link
                            className="ui-btn ui-btn--ghost ui-btn--sm"
                            to="/app/candidates/$candidateId"
                            params={{ candidateId: event.candidate.id }}
                          >
                            Профиль
                          </Link>
                        ) : (
                          <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled>
                            Профиль
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {rescheduleTarget && (
        <ModalPortal>
          <div
            className="modal-overlay"
            onClick={(e) => e.target === e.currentTarget && setRescheduleTarget(null)}
            role="dialog"
            aria-modal="true"
          >
            <div className="glass glass--elevated modal modal--sm" onClick={(e) => e.stopPropagation()}>
              <div className="modal__header">
                <div>
                  <h2 className="modal__title">Перенести слот</h2>
                  <p className="modal__subtitle">{rescheduleTarget.candidate.name}</p>
                </div>
                <button className="ui-btn ui-btn--ghost" onClick={() => setRescheduleTarget(null)}>
                  Закрыть
                </button>
              </div>
              <div className="modal__body">
                <div className="form-grid">
                  <label>
                    Дата
                    <input
                      type="date"
                      value={rescheduleDate}
                      onChange={(e) => setRescheduleDate(e.target.value)}
                    />
                  </label>
                  <label>
                    Время (локальное)
                    <input
                      type="time"
                      value={rescheduleTime}
                      onChange={(e) => setRescheduleTime(e.target.value)}
                    />
                  </label>
                </div>
                <label>
                  Причина
                  <textarea
                    rows={3}
                    value={rescheduleReason}
                    onChange={(e) => setRescheduleReason(e.target.value)}
                    placeholder="Коротко опишите причину переноса"
                  />
                </label>
              </div>
              <div className="modal__footer">
                <button
                  className="ui-btn ui-btn--primary"
                  onClick={() => {
                    if (!rescheduleDate || !rescheduleTime) {
                      showToast('Укажите дату и время')
                      return
                    }
                    rescheduleSlot.mutate({
                      slotId: rescheduleTarget.id,
                      date: rescheduleDate,
                      time: rescheduleTime,
                      reason: rescheduleReason,
                    })
                  }}
                  disabled={rescheduleSlot.isPending}
                >
                  {rescheduleSlot.isPending ? 'Отправка…' : 'Перенести'}
                </button>
                <button className="ui-btn ui-btn--ghost" onClick={() => setRescheduleTarget(null)}>
                  Отмена
                </button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

      {incomingTarget && (
        <ModalPortal>
          <div
            className="modal-overlay"
            onClick={(e) => e.target === e.currentTarget && setIncomingTarget(null)}
            role="dialog"
            aria-modal="true"
          >
            <div className="glass glass--elevated modal modal--sm" onClick={(e) => e.stopPropagation()}>
              <div className="modal__header">
                <div>
                  <h2 className="modal__title">Назначить собеседование</h2>
                  <p className="modal__subtitle">{incomingTarget.name || 'Кандидат'}</p>
                </div>
                <button className="ui-btn ui-btn--ghost" onClick={() => setIncomingTarget(null)}>
                  Закрыть
                </button>
              </div>
              <div className="modal__body">
                <div className="form-grid">
                  <label>
                    Дата
                    <input type="date" value={incomingDate} onChange={(e) => setIncomingDate(e.target.value)} />
                  </label>
                  <label>
                    Время (локальное)
                    <input type="time" value={incomingTime} onChange={(e) => setIncomingTime(e.target.value)} />
                  </label>
                </div>
                <label>
                  Сообщение кандидату (необязательно)
                  <textarea
                    rows={3}
                    value={incomingMessage}
                    onChange={(e) => setIncomingMessage(e.target.value)}
                    placeholder="Например: подойдёт ли это время?"
                  />
                </label>
              </div>
              <div className="modal__footer">
                <button
                  className="ui-btn ui-btn--primary"
                  onClick={() => {
                    if (!incomingDate || !incomingTime) {
                      showToast('Укажите дату и время')
                      return
                    }
                    scheduleIncoming.mutate({
                      candidate: incomingTarget,
                      date: incomingDate,
                      time: incomingTime,
                      message: incomingMessage,
                    })
                  }}
                  disabled={scheduleIncoming.isPending}
                >
                  {scheduleIncoming.isPending ? 'Отправка…' : 'Назначить'}
                </button>
                <button className="ui-btn ui-btn--ghost" onClick={() => setIncomingTarget(null)}>
                  Отмена
                </button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

      {toast && <div className="toast">{toast}</div>}

      {isAdmin && (
        <div className="glass panel dashboard-panel dashboard-kpi">
          <div className="dashboard-section-header">
            <div>
              <h2 className="section-title">Weekly KPI</h2>
              <p className="subtitle">{kpiQuery.data?.current.label}</p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={() => kpiQuery.refetch()}>
              Обновить
            </button>
          </div>
          {kpiQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {kpiQuery.isError && (
            <p style={{ color: '#f07373' }}>Ошибка: {(kpiQuery.error as Error).message}</p>
          )}
          {kpiQuery.data?.current?.metrics && (
            <div className="kpi-grid">
              {kpiQuery.data.current.metrics.map((metric) => (
                <div key={metric.key} className="glass stat-card kpi-card">
                  <div className="kpi-card__header">
                    <span className="kpi-card__icon">{metric.icon}</span>
                    <span className="kpi-card__label">{metric.label}</span>
                  </div>
                  <div className="kpi-card__value">{metric.value}</div>
                  <div className="kpi-card__trend">{metric.trend?.display || '—'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Metric({ title, value }: { title: string; value: number | string }) {
  return (
    <article className="glass stat-card dashboard-metric">
      <span className="stat-label">{title}</span>
      <span className="stat-value">{value ?? '—'}</span>
    </article>
  )
}
