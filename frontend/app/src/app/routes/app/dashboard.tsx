import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '@/api/client'
import { useProfile } from '@/app/hooks/useProfile'
import { ScheduleCalendar, type SlotExtendedProps } from '@/app/components/Calendar/ScheduleCalendar'
import { browserTimeZone, buildSlotTimePreview, formatTzOffset } from '@/app/lib/timezonePreview'
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

type RescheduleTarget = {
  slotId: number
  candidateName: string
  recruiterTz: string
  candidateTz: string
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
  availability_note?: string | null
  telegram_id?: number | null
  telegram_username?: string | null
  last_message?: string | null
  last_message_at?: string | null
  responsible_recruiter_id?: number | null
  responsible_recruiter_name?: string | null
  profile_url?: string | null
  ai_relevance_score?: number | null
  ai_relevance_level?: 'high' | 'medium' | 'low' | 'unknown' | null
  ai_relevance_updated_at?: string | null
}

type IncomingPayload = {
  items: IncomingCandidate[]
}

const AI_LEVEL_LABELS: Record<'high' | 'medium' | 'low' | 'unknown', string> = {
  high: 'Высокая',
  medium: 'Средняя',
  low: 'Низкая',
  unknown: 'Не определена',
}

const INTERVIEW_CAL_STATUSES = ['confirmed_by_candidate']

function formatAiRelevance(candidate: IncomingCandidate): string {
  if (typeof candidate.ai_relevance_score === 'number') {
    const score = Math.min(100, Math.max(0, Math.round(candidate.ai_relevance_score)))
    return `${score}/100`
  }
  if (candidate.ai_relevance_level && AI_LEVEL_LABELS[candidate.ai_relevance_level]) {
    return AI_LEVEL_LABELS[candidate.ai_relevance_level]
  }
  return '—'
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
  const queryClient = useQueryClient()
  const profileReady = profile.isSuccess
  const isAdmin = profile.data?.principal.type === 'admin'
  const initialRange = useMemo(() => getDefaultRange(), [])
  const [rangeFrom, setRangeFrom] = useState(initialRange.from)
  const [rangeTo, setRangeTo] = useState(initialRange.to)
  const [recruiterId, setRecruiterId] = useState('')
  const [planInputs, setPlanInputs] = useState<Record<number, string>>({})
  const [toast, setToast] = useState<string | null>(null)
  const [interviewTarget, setInterviewTarget] = useState<SlotExtendedProps | null>(null)
  const [rescheduleTarget, setRescheduleTarget] = useState<RescheduleTarget | null>(null)
  const [rescheduleDate, setRescheduleDate] = useState('')
  const [rescheduleTime, setRescheduleTime] = useState('')
  const [rescheduleReason, setRescheduleReason] = useState('')
  const [incomingTarget, setIncomingTarget] = useState<IncomingCandidate | null>(null)
  const [incomingDate, setIncomingDate] = useState('')
  const [incomingTime, setIncomingTime] = useState('')
  const [incomingMessage, setIncomingMessage] = useState('')
  const [incomingSearch, setIncomingSearch] = useState('')
  const [incomingFilter, setIncomingFilter] = useState<'all' | 'new' | 'stalled'>('all')
  const [incomingSort, setIncomingSort] = useState<'waiting' | 'recent' | 'name'>('waiting')
  const recruiterTz = profile.data?.recruiter?.tz || browserTimeZone()

  const showToast = (message: string) => {
    setToast(message)
    window.clearTimeout((showToast as any)._t)
    ;(showToast as any)._t = window.setTimeout(() => setToast(null), 2400)
  }

  const summaryQuery = useQuery<SummaryPayload>({
    queryKey: ['dashboard-summary'],
    queryFn: () => apiFetch('/dashboard/summary'),
    enabled: profileReady && Boolean(isAdmin),
  })

  const recruitersQuery = useQuery<RecruiterOption[]>({
    queryKey: ['dashboard-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: profileReady && Boolean(isAdmin),
    staleTime: 60_000,
  })

  const planQuery = useQuery<RecruiterCityPlan[]>({
    queryKey: ['recruiter-plan'],
    queryFn: () => apiFetch('/recruiter-plan'),
    enabled: profileReady && !isAdmin,
  })

  const incomingQuery = useQuery<IncomingPayload>({
    queryKey: ['dashboard-incoming'],
    queryFn: () => apiFetch('/dashboard/incoming'),
    enabled: profileReady && !isAdmin,
    refetchInterval: 20000,
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
    enabled: profileReady && Boolean(isAdmin),
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
    enabled: profileReady && Boolean(isAdmin),
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

  const rescheduleSlot = useMutation({
    mutationFn: async (payload: { slotId: number; date: string; time: string; reason?: string }) =>
      apiFetch(`/slots/${payload.slotId}/reschedule`, {
        method: 'POST',
        body: JSON.stringify({ date: payload.date, time: payload.time, reason: payload.reason || '' }),
      }),
    onSuccess: (data: any) => {
      showToast(data?.message || 'Слот перенесён')
      setRescheduleTarget(null)
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
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
      showToast(data?.message || 'Предложение отправлено кандидату')
      setIncomingTarget(null)
      incomingQuery.refetch()
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
    },
    onError: (error: Error) => showToast(error.message),
  })

  const openRescheduleFromSlot = (slot: SlotExtendedProps) => {
    setRescheduleTarget({
      slotId: slot.slot_id,
      candidateName: slot.candidate_name || 'Без имени',
      recruiterTz: slot.recruiter_tz || recruiterTz,
      candidateTz: slot.candidate_tz || slot.city_tz || slot.recruiter_tz || recruiterTz,
    })
    setRescheduleDate(slot.local_date || toIsoDate(new Date()))
    setRescheduleTime(slot.local_start || '09:00')
    setRescheduleReason('')
  }

  const openIncomingSchedule = (candidate: IncomingCandidate) => {
    const selected = toIsoDate(new Date())
    setIncomingTarget(candidate)
    setIncomingDate(selected)
    setIncomingTime('10:00')
    setIncomingMessage('')
  }

  const handleInterviewClick = (_slotId: number, slot: SlotExtendedProps) => {
    setInterviewTarget(slot)
  }

  const cityTzMap = useMemo(() => {
    const map = new Map<number, string>()
    const options = profile.data?.profile?.city_options || []
    for (const city of options) {
      if (city?.id && city?.tz) map.set(city.id, city.tz)
    }
    return map
  }, [profile.data?.profile?.city_options])

  const incomingCandidateTz = useMemo(() => {
    if (!incomingTarget) return recruiterTz
    const byCity = incomingTarget.city_id ? cityTzMap.get(incomingTarget.city_id) : null
    return byCity || recruiterTz
  }, [incomingTarget, cityTzMap, recruiterTz])

  const reschedulePreview = useMemo(
    () =>
      rescheduleTarget
        ? buildSlotTimePreview(
            rescheduleDate,
            rescheduleTime,
            rescheduleTarget.recruiterTz || recruiterTz,
            rescheduleTarget.candidateTz || recruiterTz,
          )
        : null,
    [rescheduleDate, rescheduleTime, rescheduleTarget, recruiterTz],
  )

  const incomingPreview = useMemo(
    () => buildSlotTimePreview(incomingDate, incomingTime, recruiterTz, incomingCandidateTz),
    [incomingDate, incomingTime, recruiterTz, incomingCandidateTz],
  )

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

  const incomingItems = useMemo(() => {
    const base = [...(incomingQuery.data?.items || [])]
    const search = incomingSearch.trim().toLowerCase()
    const now = Date.now()

    const filtered = base.filter((candidate) => {
      if (incomingFilter === 'new') {
        if (!candidate.last_message_at) return false
        const ageMs = now - new Date(candidate.last_message_at).getTime()
        if (!Number.isFinite(ageMs) || ageMs > 24 * 60 * 60 * 1000) return false
      }

      if (incomingFilter === 'stalled') {
        const stalledByStatus = candidate.status_slug === 'stalled_waiting_slot'
        const stalledByTime = (candidate.waiting_hours || 0) >= 24
        if (!stalledByStatus && !stalledByTime) return false
      }

      if (!search) return true
      const haystack = [
        candidate.name,
        candidate.city,
        candidate.status_display,
        candidate.telegram_username,
        candidate.last_message,
        candidate.availability_note,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return haystack.includes(search)
    })

    filtered.sort((a, b) => {
      if (incomingSort === 'name') {
        return (a.name || '').localeCompare(b.name || '', 'ru')
      }
      if (incomingSort === 'recent') {
        const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0
        const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0
        return bTime - aTime
      }
      const aw = a.waiting_hours ?? -1
      const bw = b.waiting_hours ?? -1
      if (bw !== aw) return bw - aw
      const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0
      const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0
      return bTime - aTime
    })

    return filtered
  }, [incomingFilter, incomingQuery.data?.items, incomingSearch, incomingSort])

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
              <div>
                <p className="subtitle">Нет кандидатов, ожидающих слот.</p>
                {profile.data?.recruiter?.cities?.length ? (
                  <p className="text-muted text-sm">
                    Ваши города: {profile.data.recruiter.cities.map((c) => c.name).join(', ')}. Кандидаты из других городов не попадут в список.
                  </p>
                ) : (
                  <p className="text-muted text-sm">
                    Проверьте, что к вашему профилю привязаны города — иначе входящие не появятся.
                  </p>
                )}
              </div>
            )}
            {incomingQuery.data && incomingQuery.data.items.length > 0 && (
              <>
                <div className="incoming-toolbar">
                  <div className="incoming-toolbar__stats">
                    <strong>{incomingItems.length}</strong>
                    <span className="text-muted text-sm">из {incomingQuery.data.items.length} кандидатов</span>
                  </div>
                  <div className="incoming-toolbar__controls">
                    <input
                      className="incoming-toolbar__search"
                      type="search"
                      placeholder="Поиск: имя, город…"
                      value={incomingSearch}
                      onChange={(e) => setIncomingSearch(e.target.value)}
                    />
                    <select
                      className="incoming-toolbar__select"
                      value={incomingFilter}
                      onChange={(e) => setIncomingFilter(e.target.value as 'all' | 'new' | 'stalled')}
                    >
                      <option value="all">Все</option>
                      <option value="new">Только NEW (24ч)</option>
                      <option value="stalled">Застрявшие</option>
                    </select>
                    <select
                      className="incoming-toolbar__select"
                      value={incomingSort}
                      onChange={(e) => setIncomingSort(e.target.value as 'waiting' | 'recent' | 'name')}
                    >
                      <option value="waiting">Сначала кто дольше ждёт</option>
                      <option value="recent">Последние сообщения</option>
                      <option value="name">По имени</option>
                    </select>
                  </div>
                </div>

                {incomingItems.length === 0 ? (
                  <p className="subtitle">По текущим фильтрам кандидатов нет.</p>
                ) : (
                  <div className="incoming-list">
                    {incomingItems.map((candidate) => (
                      <article key={candidate.id} className="incoming-min-card">
                        <div className="incoming-min-card__head">
                          <div className="incoming-min-card__name">{candidate.name || 'Без имени'}</div>
                          <div className="incoming-min-card__city">{candidate.city || 'Город не указан'}</div>
                        </div>

                        <div className="incoming-min-card__chips">
                          <span className="incoming-min-chip incoming-min-chip--time">
                            Предпочтение: {candidate.availability_window || 'не указано'}
                          </span>
                          <span className="incoming-min-chip incoming-min-chip--wait">
                            Ждёт: {candidate.waiting_hours != null ? `${candidate.waiting_hours} ч` : '—'}
                          </span>
                          <span className="incoming-min-chip incoming-min-chip--ai">
                            AI: {formatAiRelevance(candidate)}
                          </span>
                        </div>

                        <div className="incoming-min-card__actions">
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
                            Согласовать время
                          </button>
                          <button
                            className="ui-btn ui-btn--danger ui-btn--sm"
                            type="button"
                            onClick={() => rejectCandidate.mutate(candidate.id)}
                          >
                            Отказать
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {profileReady && !isAdmin && (
          <div className="glass panel dashboard-panel">
            <div className="dashboard-section-header">
              <div>
                <h2 className="section-title">Календарь интервью</h2>
                <p className="subtitle">Подтверждённые интервью. Клик по событию открывает действия.</p>
              </div>
              <button
                className="ui-btn ui-btn--ghost"
                onClick={() => queryClient.invalidateQueries({ queryKey: ['calendar-events'] })}
              >
                Обновить
              </button>
            </div>
            <ScheduleCalendar
              recruiterId={profile.data?.recruiter?.id || undefined}
              statuses={INTERVIEW_CAL_STATUSES}
              onSlotClick={handleInterviewClick}
              editable={false}
              embedded={true}
            />
          </div>
        )}
      </div>

      {interviewTarget && (
        <ModalPortal>
          <div
            className="modal-overlay"
            onClick={(e) => e.target === e.currentTarget && setInterviewTarget(null)}
            role="dialog"
            aria-modal="true"
          >
            <div className="glass glass--elevated modal modal--sm" onClick={(e) => e.stopPropagation()}>
              <div className="modal__header">
                <div>
                  <h2 className="modal__title">{interviewTarget.candidate_name || 'Интервью'}</h2>
                  <p className="modal__subtitle">
                    {interviewTarget.city_name ? `${interviewTarget.city_name} · ` : ''}
                    {interviewTarget.local_date} · {interviewTarget.local_start}–{interviewTarget.local_end}
                  </p>
                </div>
                <button className="ui-btn ui-btn--ghost" onClick={() => setInterviewTarget(null)}>
                  Закрыть
                </button>
              </div>
              <div className="modal__body">
                <span className="status-pill status-pill--success">{interviewTarget.status_label}</span>
              </div>
              <div className="modal__footer">
                {interviewTarget.candidate_id ? (
                  <Link
                    className="ui-btn ui-btn--ghost"
                    to="/app/candidates/$candidateId"
                    params={{ candidateId: String(interviewTarget.candidate_id) }}
                    onClick={() => setInterviewTarget(null)}
                  >
                    Профиль
                  </Link>
                ) : (
                  <button className="ui-btn ui-btn--ghost" disabled>
                    Профиль
                  </button>
                )}
                <button
                  className="ui-btn ui-btn--primary"
                  onClick={() => {
                    openRescheduleFromSlot(interviewTarget)
                    setInterviewTarget(null)
                  }}
                >
                  Перенести
                </button>
              </div>
            </div>
          </div>
        </ModalPortal>
      )}

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
                  <p className="modal__subtitle">{rescheduleTarget.candidateName}</p>
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
                    Время ({rescheduleTarget.recruiterTz} · {formatTzOffset(rescheduleTarget.recruiterTz)})
                    <input
                      type="time"
                      value={rescheduleTime}
                      onChange={(e) => setRescheduleTime(e.target.value)}
                    />
                  </label>
                </div>
                {reschedulePreview && (
                  <div className="glass slot-preview">
                    <div>
                      <div className="slot-preview__label">Вы вводите (ваша TZ)</div>
                      <div className="slot-preview__value">{reschedulePreview.recruiterLabel}</div>
                      <div className="slot-preview__hint">
                        {reschedulePreview.recruiterTz} · {formatTzOffset(reschedulePreview.recruiterTz)}
                      </div>
                    </div>
                    <div>
                      <div className="slot-preview__label">Кандидат увидит</div>
                      <div className="slot-preview__value">{reschedulePreview.candidateLabel}</div>
                      <div className="slot-preview__hint">
                        {reschedulePreview.candidateTz} · {formatTzOffset(reschedulePreview.candidateTz)}
                      </div>
                    </div>
                  </div>
                )}
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
                      slotId: rescheduleTarget.slotId,
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
                  <h2 className="modal__title">Предложить время собеседования</h2>
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
                    Время ({recruiterTz} · {formatTzOffset(recruiterTz)})
                    <input type="time" value={incomingTime} onChange={(e) => setIncomingTime(e.target.value)} />
                  </label>
                </div>
                {incomingPreview && (
                  <div className="glass slot-preview">
                    <div>
                      <div className="slot-preview__label">Вы вводите (ваша TZ)</div>
                      <div className="slot-preview__value">{incomingPreview.recruiterLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingPreview.recruiterTz} · {formatTzOffset(incomingPreview.recruiterTz)}
                      </div>
                    </div>
                    <div>
                      <div className="slot-preview__label">Кандидат увидит</div>
                      <div className="slot-preview__value">{incomingPreview.candidateLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingPreview.candidateTz} · {formatTzOffset(incomingPreview.candidateTz)}
                      </div>
                    </div>
                  </div>
                )}
                <label>
                  Сообщение кандидату (необязательно)
                  <textarea
                    rows={3}
                    value={incomingMessage}
                    onChange={(e) => setIncomingMessage(e.target.value)}
                    placeholder="Например: Мы предлагаем собеседование в это время. Подойдёт ли вам?"
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
                  {scheduleIncoming.isPending ? 'Отправка…' : 'Отправить предложение'}
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
