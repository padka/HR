import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { apiFetch } from '@/api/client'
import { useProfile } from '@/app/hooks/useProfile'

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

type FunnelStep = {
  key: string
  title: string
  count: number
  conversion_from_prev?: number
  dropoff_count?: number | null
}

type FunnelPayload = {
  steps: FunnelStep[]
  summary: {
    conversion_total: number
    range_days: number
  }
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
  candidate: { name: string; profile_url?: string | null; telegram_id?: number | null }
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

export function DashboardPage() {
  const profile = useProfile()
  const isAdmin = profile.data?.principal.type === 'admin'
  const initialRange = useMemo(() => getDefaultRange(), [])
  const [rangeFrom, setRangeFrom] = useState(initialRange.from)
  const [rangeTo, setRangeTo] = useState(initialRange.to)
  const [calendarDate, setCalendarDate] = useState(initialRange.to)
  const [recruiterId, setRecruiterId] = useState('')

  const summaryQuery = useQuery<SummaryPayload>({
    queryKey: ['dashboard-summary'],
    queryFn: () => apiFetch('/dashboard/summary'),
  })

  const recruitersQuery = useQuery<RecruiterOption[]>({
    queryKey: ['dashboard-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
    staleTime: 60_000,
  })

  const funnelParams = useMemo(() => {
    const params = new URLSearchParams()
    if (rangeFrom) params.set('from', rangeFrom)
    if (rangeTo) params.set('to', rangeTo)
    if (recruiterId) params.set('recruiter', recruiterId)
    return params.toString()
  }, [rangeFrom, rangeTo, recruiterId])

  const funnelQuery = useQuery<FunnelPayload>({
    queryKey: ['dashboard-funnel', funnelParams],
    queryFn: () => apiFetch(`/dashboard/funnel?${funnelParams}`),
    enabled: Boolean(rangeFrom && rangeTo),
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
  })

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

  const funnelSteps = funnelQuery.data?.steps || []
  const maxFunnel = Math.max(...funnelSteps.map((step) => step.count || 0), 1)

  return (
    <div className="page">
      <div className="glass panel dashboard-header">
        <div>
          <h1 className="title">Дашборд</h1>
          <p className="subtitle">Сводка работы, динамика кандидатов и расписание интервью.</p>
        </div>
        <div className="dashboard-filters">
          <label className="filter-field">
            <span>Период от</span>
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
            <span>Период до</span>
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
          {isAdmin && (
            <label className="filter-field">
              <span>Рекрутёр</span>
              <select
                value={recruiterId}
                onChange={(e) => setRecruiterId(e.target.value)}
              >
                <option value="">Все</option>
                {(recruitersQuery.data || []).map((rec) => (
                  <option key={rec.id} value={rec.id}>
                    {rec.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>

      <div className="glass panel">
        <h2 className="section-title">Сводка</h2>
        {summaryQuery.isLoading && <p className="subtitle">Загрузка…</p>}
        {summaryQuery.isError && (
          <p style={{ color: '#f07373' }}>Ошибка: {(summaryQuery.error as Error).message}</p>
        )}
        {summaryCards.length > 0 && (
          <div className="grid-cards" style={{ marginTop: 12 }}>
            {summaryCards.map((card) => (
              <Metric key={card.label} title={card.label} value={card.value} />
            ))}
          </div>
        )}
      </div>

      <div className="dashboard-grid">
        <div className="glass panel">
          <div className="dashboard-section-header">
            <div>
              <h2 className="section-title">Воронка кандидатов</h2>
              <p className="subtitle">
                Конверсия за {funnelQuery.data?.summary?.range_days ?? '—'} дней · общий итог{' '}
                {funnelQuery.data?.summary?.conversion_total ?? '—'}%
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={() => funnelQuery.refetch()}>
              Обновить
            </button>
          </div>
          {funnelQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {funnelQuery.isError && (
            <p style={{ color: '#f07373' }}>Ошибка: {(funnelQuery.error as Error).message}</p>
          )}
          {funnelSteps.length > 0 && (
            <div className="funnel-steps">
              {funnelSteps.map((step, index) => {
                const width = Math.max((step.count / maxFunnel) * 100, 6)
                const conversion =
                  index === 0 ? '—' : `${step.conversion_from_prev ?? 0}%`
                return (
                  <div key={step.key} className="funnel-step">
                    <div className="funnel-step__label">
                      <a href={`/app/candidates?status=${step.key}`}>{step.title}</a>
                      <span className="funnel-step__meta">{step.count} кандидатов</span>
                    </div>
                    <div className="funnel-step__bar">
                      <span style={{ width: `${width}%` }} />
                    </div>
                    <div className="funnel-step__conversion">{conversion}</div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="glass panel">
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
                <span>FREE: {calendarQuery.data.status_summary?.FREE ?? 0}</span>
                <span>PENDING: {calendarQuery.data.status_summary?.PENDING ?? 0}</span>
                <span>BOOKED: {calendarQuery.data.status_summary?.BOOKED ?? 0}</span>
                <span>CONFIRMED: {calendarQuery.data.status_summary?.CONFIRMED_BY_CANDIDATE ?? 0}</span>
              </div>
              <div className="calendar-events">
                {calendarQuery.data.events.length === 0 && (
                  <p className="subtitle">Нет слотов на выбранную дату.</p>
                )}
                {calendarQuery.data.events.map((event) => (
                  <div key={event.id} className="calendar-event">
                    <div>
                      <div className="calendar-event__time">
                        {event.start_time}–{event.end_time}
                      </div>
                      <div className="calendar-event__meta">
                        {event.candidate.name} · {event.recruiter.name || '—'} · {event.city.name || '—'}
                      </div>
                    </div>
                    <a className="ui-btn ui-btn--ghost" href={`/app/slots?date=${calendarQuery.data?.selected_date}`}>
                      Открыть слоты
                    </a>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="glass panel">
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
    </div>
  )
}

function Metric({ title, value }: { title: string; value: number | string }) {
  return (
    <div className="glass stat-card">
      <div className="stat-label">{title}</div>
      <div className="stat-value">{value ?? '—'}</div>
    </div>
  )
}
