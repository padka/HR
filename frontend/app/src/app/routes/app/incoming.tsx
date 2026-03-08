import { useQuery, useMutation } from '@tanstack/react-query'
import { useMemo, useState, useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { fetchCandidateDetail, type CandidateDetail, type TestQuestionAnswer, type TestSection } from '@/api/services/candidates'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { RoleGuard } from '@/app/components/RoleGuard'
import { browserTimeZone, buildSlotTimePreview, formatTzOffset } from '@/app/lib/timezonePreview'
import { resolveIncomingDemoCount, withDemoIncomingCandidates } from './incoming-demo'
import {
  clearIncomingPersistedFilters,
  loadIncomingPersistedFilters,
  saveIncomingPersistedFilters,
  type IncomingAiFilter,
  type IncomingOwnerFilter,
  type IncomingStatusFilter,
  type IncomingWaitingFilter,
} from './incoming.filters'

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
  requested_another_time?: boolean
  requested_another_time_at?: string | null
  requested_another_time_comment?: string | null
  requested_another_time_from?: string | null
  requested_another_time_to?: string | null
  incoming_substatus?: string | null
}

type IncomingPayload = {
  items: IncomingCandidate[]
}

type AvailableSlot = {
  slot_id: number
  start_utc: string | null
  city_id?: number | null
  city_name?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  slot_tz?: string | null
  recruiter_tz?: string | null
}

type AvailableSlotsPayload = {
  ok: boolean
  items: AvailableSlot[]
  candidate_city_id?: number | null
}

type ScheduleIncomingPayload = {
  candidate: IncomingCandidate
  date?: string
  time?: string
  message?: string
  slotId?: number
}

function ModalPortal({ children }: { children: ReactNode }) {
  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}

function toIsoDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

function formatSlotOption(slot: AvailableSlot) {
  const tz = slot.recruiter_tz || slot.slot_tz || 'Europe/Moscow'
  const dateLabel = slot.start_utc
    ? new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz,
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(slot.start_utc))
    : '—'
  return `${dateLabel} · ${slot.recruiter_name || 'Рекрутер'} · ${slot.city_name || 'Город'}`
}

function formatInTz(utcIso: string, tz: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: tz,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(utcIso))
}

function formatDateTime(value?: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function formatRequestedAnotherTime(candidate: IncomingCandidate): string | null {
  const from = candidate.requested_another_time_from
  const to = candidate.requested_another_time_to
  if (from && to) {
    const start = new Date(from)
    const end = new Date(to)
    const sameDay = start.toDateString() === end.toDateString()
    const startLabel = new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(start)
    const endLabel = new Intl.DateTimeFormat('ru-RU', {
      ...(sameDay ? {} : { day: '2-digit', month: '2-digit' }),
      hour: '2-digit',
      minute: '2-digit',
    }).format(end)
    return `Хочет окно: ${startLabel}–${endLabel}`
  }
  if (from) {
    return `Хочет время: ${formatDateTime(from)}`
  }
  if (candidate.requested_another_time_comment) {
    return `Пожелание: ${candidate.requested_another_time_comment}`
  }
  return null
}

function formatDuration(totalSeconds?: number | null) {
  const total = Math.max(0, Math.round(totalSeconds || 0))
  if (total === 0) return '0 мин'
  const minutes = Math.round(total / 60)
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const restMinutes = minutes % 60
  return restMinutes > 0 ? `${hours} ч ${restMinutes} мин` : `${hours} ч`
}

function resolveTestTone(status?: string | null) {
  switch (status) {
    case 'passed':
    case 'completed':
      return 'success'
    case 'failed':
      return 'danger'
    case 'in_progress':
    case 'pending':
      return 'warning'
    default:
      return 'info'
  }
}

function TestScoreBar({ correct, total, score }: { correct: number; total: number; score?: number | null }) {
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0
  const barColor = pct >= 70 ? 'var(--success, #5BE1A5)' : pct >= 40 ? 'var(--warning, #F6C16B)' : 'var(--danger, #F07373)'
  return (
    <div className="cd-score">
      <div className="cd-score__bar">
        <div className="cd-score__fill" style={{ width: `${pct}%`, background: barColor }} />
      </div>
      <div className="cd-score__text">
        {correct}/{total}
        {typeof score === 'number' && <span className="cd-score__final"> ({score.toFixed(1)})</span>}
      </div>
    </div>
  )
}

function resolveTest1Section(detail?: CandidateDetail | null): TestSection | null {
  if (!detail) return null
  const fromSections = detail.test_sections?.find((section) => section.key === 'test1')
  if (fromSections) return fromSections
  return detail.test_results?.test1 || null
}

type IncomingTestPreviewModalProps = {
  candidate: IncomingCandidate
  detail?: CandidateDetail
  isLoading: boolean
  isError: boolean
  error: Error | null
  isMobile: boolean
  canSchedule: boolean
  onClose: () => void
  onSchedule: () => void
}

function IncomingTestPreviewModal({
  candidate,
  detail,
  isLoading,
  isError,
  error,
  isMobile,
  canSchedule,
  onClose,
  onSchedule,
}: IncomingTestPreviewModalProps) {
  const test1Section = resolveTest1Section(detail)
  const stats = test1Section?.details?.stats
  const questions = test1Section?.details?.questions || []
  const correctAnswers = stats?.correct_answers ?? questions.filter((question) => question.is_correct).length
  const totalQuestions = stats?.total_questions ?? questions.length
  const showQuestions = questions.length > 0

  return (
    <ModalPortal>
      <div
        className="modal-overlay"
        onClick={(e) => e.target === e.currentTarget && onClose()}
        role="dialog"
        aria-modal="true"
        data-testid="incoming-test-preview-modal"
      >
        <div className={`glass glass--elevated modal modal--md ${isMobile ? 'modal--sheet' : ''}`} onClick={(e) => e.stopPropagation()}>
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Результат Теста 1</h2>
              <p className="modal__subtitle">{candidate.name || 'Кандидат'}</p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>
              Закрыть
            </button>
          </div>
          <div className="modal__body">
            {isLoading && <p className="subtitle">Загружаем результаты теста…</p>}
            {isError && <div className="ui-alert ui-alert--error">{error?.message || 'Не удалось загрузить тест'}</div>}
            {!isLoading && !isError && !test1Section && (
              <div className="ui-alert ui-alert--warning">Результат Теста 1 пока недоступен.</div>
            )}
            {!isLoading && !isError && test1Section && (
              <div className="ui-stack-16">
                <div className="glass glass--subtle page-section ui-stack-12">
                  <div className="toolbar toolbar--compact">
                    <strong>Тест 1</strong>
                    <span className={`status-pill status-pill--${resolveTestTone(test1Section.status)}`}>
                      {test1Section.status_label || 'Без статуса'}
                    </span>
                  </div>
                  <p className="subtitle">{test1Section.summary || 'Результат теста доступен.'}</p>
                  <TestScoreBar
                    correct={correctAnswers}
                    total={totalQuestions}
                    score={stats?.final_score}
                  />
                  <div className="cd-test-card__extra">
                    <span>Сырые: {typeof stats?.raw_score === 'number' ? stats.raw_score : '—'}</span>
                    <span>Время: {formatDuration(stats?.total_time)}</span>
                    <span>Завершён: {formatDateTime(test1Section.completed_at)}</span>
                  </div>
                </div>

                {showQuestions && (
                  <div className="ui-stack-12">
                    {questions.map((question: TestQuestionAnswer, index) => (
                      <div key={`${candidate.id}-test1-${question.question_index ?? index}`} className="glass cd-test-attempt-question">
                        <div className="cd-test-attempt-question__header">
                          <span>Вопрос {question.question_index ?? index + 1}</span>
                          <span className={`cd-chip cd-chip--small ${question.is_correct ? 'cd-chip--success' : 'cd-chip--danger'}`}>
                            {question.is_correct ? 'Верно' : 'Неверно'}
                          </span>
                        </div>
                        <div className="cd-test-attempt-question__text">{question.question_text || '—'}</div>
                        <div className="cd-test-attempt-question__answer">
                          <strong>Ответ кандидата:</strong> {question.user_answer || '—'}
                        </div>
                        {question.correct_answer && (
                          <div className="cd-test-attempt-question__answer">
                            <strong>Эталон:</strong> {question.correct_answer}
                          </div>
                        )}
                        <div className="cd-test-attempt-question__meta">
                          <span>Попыток: {question.attempts_count ?? 1}</span>
                          <span>Время: {formatDuration(question.time_spent)}</span>
                          {question.overtime ? <span>Просрочено</span> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="modal__footer">
            {canSchedule && (
              <button
                className="ui-btn ui-btn--primary"
                type="button"
                data-testid="incoming-test-preview-schedule"
                onClick={onSchedule}
              >
                Предложить время
              </button>
            )}
            <Link
              className="ui-btn ui-btn--ghost"
              to="/app/candidates/$candidateId"
              params={{ candidateId: String(candidate.id) }}
            >
              Профиль
            </Link>
            <button className="ui-btn ui-btn--ghost" type="button" onClick={onClose}>
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

export function IncomingPage() {
  const profile = useProfile()
  const isMobile = useIsMobile()
  const isAdmin = profile.data?.principal.type === 'admin'
  const recruiterId = profile.data?.recruiter?.id ?? null
  const recruiterTz = profile.data?.recruiter?.tz || browserTimeZone()
  const incomingDemoCount = useMemo(() => {
    if (typeof window === 'undefined') return 0
    return resolveIncomingDemoCount({
      envValue: import.meta.env.VITE_INCOMING_DEMO_COUNT,
      hostname: window.location.hostname,
      search: window.location.search,
    })
  }, [])
  const persistedFilters = useMemo(() => {
    if (typeof window === 'undefined') return {}
    return loadIncomingPersistedFilters(window.localStorage)
  }, [])
  const [toast, setToast] = useState<string | null>(null)
  const [incomingTarget, setIncomingTarget] = useState<IncomingCandidate | null>(null)
  const [testPreviewTarget, setTestPreviewTarget] = useState<IncomingCandidate | null>(null)
  const [incomingDate, setIncomingDate] = useState(toIsoDate(new Date()))
  const [incomingTime, setIncomingTime] = useState('10:00')
  const [incomingMessage, setIncomingMessage] = useState('')
  const [incomingMode, setIncomingMode] = useState<'manual' | 'existing'>('manual')
  const [selectedSlotId, setSelectedSlotId] = useState<string>('')
  const [search, setSearch] = useState(() => persistedFilters.search ?? '')
  const [cityFilter, setCityFilter] = useState(() => persistedFilters.cityFilter ?? 'all')
  const [statusFilter, setStatusFilter] = useState<IncomingStatusFilter>(() => persistedFilters.statusFilter ?? 'all')
  const [ownerFilter, setOwnerFilter] = useState<IncomingOwnerFilter>(() => persistedFilters.ownerFilter ?? 'all')
  const [waitingFilter, setWaitingFilter] = useState<IncomingWaitingFilter>(() => persistedFilters.waitingFilter ?? 'all')
  const [aiFilter, setAiFilter] = useState<IncomingAiFilter>(() => persistedFilters.aiFilter ?? 'all')
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(() => persistedFilters.showAdvancedFilters ?? false)
  const [expandedCards, setExpandedCards] = useState<Record<number, boolean>>({})

  useEffect(() => {
    if (isMobile) setShowAdvancedFilters(false)
  }, [isMobile])

  const showToast = (message: string) => {
    setToast(message)
    window.clearTimeout((showToast as any)._t)
    ;(showToast as any)._t = window.setTimeout(() => setToast(null), 2400)
  }

  const incomingQuery = useQuery<IncomingPayload>({
    queryKey: ['dashboard-incoming'],
    queryFn: () => apiFetch('/dashboard/incoming?limit=100'),
    refetchInterval: 20_000,
  })

  const availableSlotsQuery = useQuery<AvailableSlotsPayload>({
    queryKey: ['incoming-available-slots', incomingTarget?.id],
    queryFn: () => apiFetch(`/candidates/${incomingTarget?.id}/available-slots?limit=60`),
    enabled: Boolean(incomingTarget?.id && !isAdmin),
    staleTime: 30_000,
  })

  const recruitersQuery = useQuery<{ id: number; name: string }[]>({
    queryKey: ['incoming-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
    staleTime: 60_000,
  })

  const testPreviewQuery = useQuery<CandidateDetail>({
    queryKey: ['candidate-detail', testPreviewTarget?.id],
    queryFn: () => fetchCandidateDetail(Number(testPreviewTarget?.id)),
    enabled: Boolean(testPreviewTarget?.id),
    staleTime: 30_000,
  })

  const [assignTargets, setAssignTargets] = useState<Record<number, string>>({})

  const assignRecruiter = useMutation({
    mutationFn: async (payload: { candidateId: number; recruiterId: number }) =>
      apiFetch(`/candidates/${payload.candidateId}/assign-recruiter`, {
        method: 'POST',
        body: JSON.stringify({ recruiter_id: payload.recruiterId }),
      }),
    onSuccess: () => {
      showToast('Рекрутёр назначен')
      incomingQuery.refetch()
    },
    onError: (error: Error) => showToast(error.message),
  })

  const scheduleIncoming = useMutation({
    mutationFn: async (payload: ScheduleIncomingPayload) => {
      if (payload.slotId) {
        return apiFetch(`/candidates/${payload.candidate.id}/schedule-slot`, {
          method: 'POST',
          body: JSON.stringify({
            slot_id: payload.slotId,
            custom_message: payload.message || '',
          }),
        })
      }

      const localRecruiterId = recruiterId
      if (!localRecruiterId) {
        throw new Error('Нет данных рекрутера')
      }
      if (!payload.candidate.city_id) {
        throw new Error('Не удалось определить город кандидата')
      }
      if (!payload.date || !payload.time) {
        throw new Error('Укажите дату и время')
      }
      return apiFetch(`/candidates/${payload.candidate.id}/schedule-slot`, {
        method: 'POST',
        body: JSON.stringify({
          recruiter_id: localRecruiterId,
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
      setIncomingMode('manual')
      setSelectedSlotId('')
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

  const openIncomingSchedule = (candidate: IncomingCandidate) => {
    setIncomingTarget(candidate)
    setIncomingDate(toIsoDate(new Date()))
    setIncomingTime('10:00')
    setIncomingMessage(candidate.requested_another_time_comment || candidate.availability_note || '')
    setIncomingMode('manual')
    setSelectedSlotId('')
  }

  const openTestPreview = (candidate: IncomingCandidate) => {
    setTestPreviewTarget(candidate)
  }

  const openScheduleFromTestPreview = () => {
    if (!testPreviewTarget) return
    const candidate = testPreviewTarget
    setTestPreviewTarget(null)
    openIncomingSchedule(candidate)
  }

  useEffect(() => {
    if (!incomingTarget) return
    const hasSlots = (availableSlotsQuery.data?.items || []).length > 0
    if (hasSlots && incomingTarget.requested_another_time) {
      setIncomingMode('existing')
    }
  }, [incomingTarget, availableSlotsQuery.data])

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
  }, [cityTzMap, incomingTarget, recruiterTz])

  const incomingManualPreview = useMemo(
    () => buildSlotTimePreview(incomingDate, incomingTime, recruiterTz, incomingCandidateTz),
    [incomingDate, incomingTime, recruiterTz, incomingCandidateTz],
  )

  const selectedExistingSlot = useMemo(() => {
    if (!selectedSlotId) return null
    return (availableSlotsQuery.data?.items || []).find((slot) => String(slot.slot_id) === selectedSlotId) || null
  }, [availableSlotsQuery.data?.items, selectedSlotId])

  const incomingExistingPreview = useMemo(() => {
    if (!selectedExistingSlot?.start_utc) return null
    const slotRecruiterTz = selectedExistingSlot.recruiter_tz || recruiterTz
    const slotCandidateTz = incomingCandidateTz || selectedExistingSlot.slot_tz || slotRecruiterTz
    return {
      recruiterTz: slotRecruiterTz,
      candidateTz: slotCandidateTz,
      recruiterLabel: formatInTz(selectedExistingSlot.start_utc, slotRecruiterTz),
      candidateLabel: formatInTz(selectedExistingSlot.start_utc, slotCandidateTz),
    }
  }, [incomingCandidateTz, recruiterTz, selectedExistingSlot])

  const cityOptions = useMemo(
    () => profile.data?.recruiter?.cities || [],
    [profile.data?.recruiter?.cities],
  )
  const baseItems = useMemo(
    () =>
      withDemoIncomingCandidates(incomingQuery.data?.items ?? [], {
        targetCount: incomingDemoCount,
        cityOptions,
      }),
    [cityOptions, incomingDemoCount, incomingQuery.data?.items],
  )
  const filteredItems = useMemo(() => {
    let items = baseItems

    if (cityFilter !== 'all') {
      const cityId = Number(cityFilter)
      items = items.filter((item) => item.city_id === cityId)
    }

    if (statusFilter !== 'all') {
      if (statusFilter === 'requested_other_time') {
        items = items.filter((item) => Boolean(item.requested_another_time))
      } else {
        items = items.filter((item) => item.status_slug === statusFilter)
      }
    }

    if (ownerFilter !== 'all') {
      if (ownerFilter === 'mine') {
        items = items.filter((item) => item.responsible_recruiter_id === recruiterId)
      } else if (ownerFilter === 'assigned') {
        items = items.filter((item) => Boolean(item.responsible_recruiter_id))
      } else if (ownerFilter === 'unassigned') {
        items = items.filter((item) => !item.responsible_recruiter_id)
      }
    }

    if (waitingFilter !== 'all') {
      const threshold = waitingFilter === '48h' ? 48 : 24
      items = items.filter((item) => (item.waiting_hours || 0) >= threshold)
    }

    if (aiFilter !== 'all') {
      items = items.filter((item) => (item.ai_relevance_level || 'unknown') === aiFilter)
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase()
      items = items.filter((item) =>
        [
          item.name,
          item.city,
          String(item.telegram_id || ''),
          item.responsible_recruiter_name,
          item.status_display,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(q))
      )
    }

    return [...items].sort((left, right) => {
      const leftRequested = left.requested_another_time ? 1 : 0
      const rightRequested = right.requested_another_time ? 1 : 0
      if (leftRequested !== rightRequested) return rightRequested - leftRequested
      const leftStalled = left.status_slug === 'stalled_waiting_slot' ? 1 : 0
      const rightStalled = right.status_slug === 'stalled_waiting_slot' ? 1 : 0
      if (leftStalled !== rightStalled) return rightStalled - leftStalled
      return (right.waiting_hours || 0) - (left.waiting_hours || 0)
    })
  }, [aiFilter, baseItems, cityFilter, ownerFilter, recruiterId, search, statusFilter, waitingFilter])

  const stats = useMemo(() => {
    const total = baseItems.length
    const pending = baseItems.filter((item) => item.status_slug === 'slot_pending').length
    const stalled = baseItems.filter((item) => item.status_slug === 'stalled_waiting_slot').length
    const requested = baseItems.filter((item) => item.requested_another_time).length
    return { total, pending, stalled, requested }
  }, [baseItems])

  useEffect(() => {
    if (typeof window === 'undefined') return
    saveIncomingPersistedFilters(window.localStorage, {
      search,
      cityFilter,
      statusFilter,
      ownerFilter,
      waitingFilter,
      aiFilter,
      showAdvancedFilters,
    })
  }, [aiFilter, cityFilter, ownerFilter, search, showAdvancedFilters, statusFilter, waitingFilter])

  const resetFilters = () => {
    setSearch('')
    setCityFilter('all')
    setStatusFilter('all')
    setOwnerFilter('all')
    setWaitingFilter('all')
    setAiFilter('all')
    setShowAdvancedFilters(false)
    if (typeof window !== 'undefined') {
      clearIncomingPersistedFilters(window.localStorage)
    }
  }

  const toggleCardExpanded = (candidateId: number) => {
    setExpandedCards((prev) => ({ ...prev, [candidateId]: !prev[candidateId] }))
  }

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page app-page app-page--ops">
        <header className="glass glass--elevated page-header page-header--row ui-hero--quiet app-page__hero">
          <div>
            <h1 className="title">Входящие</h1>
            <p className="subtitle">Единая очередь кандидатов: ожидание слота, согласование времени и переносы.</p>
          </div>
          <button className="ui-btn ui-btn--ghost" onClick={() => incomingQuery.refetch()}>
            Обновить
          </button>
        </header>

        <section className="glass page-section ui-stack-16 app-page__section">
          <div className="toolbar toolbar--compact ui-section-kpis app-page__toolbar">
            <span className="cd-chip">Всего: {stats.total}</span>
            <span className="cd-chip">На согласовании: {stats.pending}</span>
            <span className="cd-chip">Запросили другое время: {stats.requested}</span>
            <span className="cd-chip">Застряли {'>'}24ч: {stats.stalled}</span>
          </div>
          {incomingDemoCount > 0 && (
            <div className="incoming-demo-note">
              Тестовый режим: отображаем {incomingDemoCount} карточек кандидатов с разными профилями.
            </div>
          )}

          <div className="filter-bar ui-filter ui-filter-bar--compact ui-filter-spacing" data-testid="incoming-filter-bar">
            <input
              placeholder="Поиск по ФИО, городу, TG, рекрутеру..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="filter-bar__search"
            />
            <select value={cityFilter} onChange={(e) => setCityFilter(e.target.value)}>
              <option value="all">Все города</option>
              {cityOptions.map((city) => (
                <option key={city.id} value={String(city.id)}>{city.name}</option>
              ))}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as IncomingStatusFilter)}>
              <option value="all">Все статусы</option>
              <option value="waiting_slot">Ожидают слот</option>
              <option value="stalled_waiting_slot">Застряли {'>'}24ч</option>
              <option value="slot_pending">На согласовании</option>
              <option value="requested_other_time">Запросили другое время</option>
            </select>
            <button
              className="ui-btn ui-btn--ghost ui-btn--sm"
              type="button"
              data-testid="incoming-advanced-filters-toggle"
              onClick={() => setShowAdvancedFilters((prev) => !prev)}
            >
              {showAdvancedFilters ? 'Скрыть доп. фильтры' : 'Доп. фильтры'}
            </button>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" type="button" onClick={resetFilters}>
              Сбросить фильтры
            </button>
          </div>
          <div
            className={`ui-filter-bar__advanced ui-filter ${showAdvancedFilters ? 'ui-filter-bar__advanced--open' : ''}`}
            aria-hidden={!showAdvancedFilters}
          >
            <select value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value as IncomingOwnerFilter)}>
              <option value="all">Любой ответственный</option>
              <option value="mine">Мои кандидаты</option>
              <option value="assigned">Есть ответственный</option>
              <option value="unassigned">Без ответственного</option>
            </select>
            <select value={waitingFilter} onChange={(e) => setWaitingFilter(e.target.value as IncomingWaitingFilter)}>
              <option value="all">Любое ожидание</option>
              <option value="24h">Ждут {'>'}=24ч</option>
              <option value="48h">Ждут {'>'}=48ч</option>
            </select>
            <select value={aiFilter} onChange={(e) => setAiFilter(e.target.value as IncomingAiFilter)}>
              <option value="all">Любой AI level</option>
              <option value="high">AI: high</option>
              <option value="medium">AI: medium</option>
              <option value="low">AI: low</option>
              <option value="unknown">AI: unknown</option>
            </select>
          </div>

          {incomingQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {incomingQuery.isError && (
            <p className="text-danger">Ошибка: {(incomingQuery.error as Error).message}</p>
          )}
          {incomingQuery.data && filteredItems.length === 0 && (
            <div data-testid="incoming-empty-state">
              <p className="subtitle">Нет кандидатов по выбранным фильтрам.</p>
            </div>
          )}
          {incomingQuery.data && filteredItems.length > 0 && (
            <div className="incoming-grid">
              {filteredItems.map((candidate) => {
                const isNew = candidate.last_message_at
                  ? Date.now() - new Date(candidate.last_message_at).getTime() < 24 * 60 * 60 * 1000
                  : false
                const selectedRecruiter =
                  assignTargets[candidate.id] ??
                  (candidate.responsible_recruiter_id ? String(candidate.responsible_recruiter_id) : '')
                const statusTone =
                  candidate.status_slug === 'stalled_waiting_slot'
                    ? 'danger'
                    : candidate.status_slug === 'slot_pending'
                      ? 'info'
                      : 'warning'
                const isExpanded = Boolean(expandedCards[candidate.id])
                const requestedAnotherTimeLabel = formatRequestedAnotherTime(candidate)
                return (
                  <div key={candidate.id} className="glass glass--subtle incoming-card incoming-card--compact ui-reveal" data-testid="incoming-card">
                    <div className="incoming-card__main">
                      <div className="incoming-card__main-content">
                        <div className="incoming-card__name-row">
                          <div className="incoming-card__name">
                            {candidate.name || 'Без имени'}
                            {isNew && <span className="incoming-card__badge">NEW</span>}
                          </div>
                          <span className="incoming-card__waiting">
                            {candidate.waiting_hours != null ? `Ждёт ${candidate.waiting_hours} ч` : 'Без ожидания'}
                          </span>
                        </div>
                        <div className="incoming-card__meta">
                          <span>{candidate.city || 'Город не указан'}</span>
                          {candidate.availability_window && (
                            <span>· {candidate.availability_window}</span>
                          )}
                        </div>
                        {candidate.availability_note && isExpanded && (
                          <div className="incoming-card__note incoming-card__note--muted">
                            ✉️ {candidate.availability_note}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="incoming-card__status-row toolbar toolbar--compact">
                      {candidate.status_display && (
                        <span className={`status-pill status-pill--${statusTone}`}>
                          {candidate.status_display}
                        </span>
                      )}
                      {candidate.requested_another_time && (
                        <span className="status-pill status-pill--warning">Запросил другое время</span>
                      )}
                    </div>

                    {candidate.requested_another_time && (
                      <div className="incoming-card__note incoming-card__note--highlight">
                        🔁 Запросил другое время
                        {candidate.requested_another_time_at && (
                          <span className="incoming-card__note-time">
                            {new Date(candidate.requested_another_time_at).toLocaleString('ru-RU', {
                              day: '2-digit',
                              month: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        )}
                      </div>
                    )}
                    {requestedAnotherTimeLabel && (
                      <div className="incoming-card__note incoming-card__note--highlight">
                        🗓 {requestedAnotherTimeLabel}
                      </div>
                    )}
                    {candidate.requested_another_time_comment && isExpanded && requestedAnotherTimeLabel !== `Пожелание: ${candidate.requested_another_time_comment}` && (
                      <div className="incoming-card__note incoming-card__note--highlight">
                        💬 {candidate.requested_another_time_comment}
                      </div>
                    )}
                    {candidate.last_message && candidate.last_message !== candidate.availability_note && (
                      <div className={`incoming-card__note incoming-card__note--message ${!isExpanded ? 'incoming-card__meta-collapsed' : ''}`}>
                        💬 {candidate.last_message}
                        {candidate.last_message_at && (
                          <span className="incoming-card__note-time">
                            {new Date(candidate.last_message_at).toLocaleString('ru-RU', {
                              day: '2-digit',
                              month: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        )}
                      </div>
                    )}
                    {isAdmin && (
                      <div className="incoming-card__note incoming-card__note--muted">
                        Ответственный: {candidate.responsible_recruiter_name || 'не назначен'}
                      </div>
                    )}
                    <button
                      type="button"
                      className="ui-btn ui-btn--ghost ui-btn--sm incoming-card__more"
                      data-testid="incoming-card-more-toggle"
                      onClick={() => toggleCardExpanded(candidate.id)}
                    >
                      {isExpanded ? 'Скрыть детали' : 'Подробнее'}
                    </button>

                    {isAdmin && (
                      <div className="incoming-card__assign">
                        <select
                          value={selectedRecruiter}
                          onChange={(e) =>
                            setAssignTargets((prev) => ({ ...prev, [candidate.id]: e.target.value }))
                          }
                        >
                          <option value="">Выберите рекрутёра</option>
                          {(recruitersQuery.data || []).map((rec) => (
                            <option key={rec.id} value={String(rec.id)}>{rec.name}</option>
                          ))}
                        </select>
                        <button
                          className="ui-btn ui-btn--primary ui-btn--sm"
                          type="button"
                          disabled={!selectedRecruiter || assignRecruiter.isPending}
                          onClick={() =>
                            assignRecruiter.mutate({ candidateId: candidate.id, recruiterId: Number(selectedRecruiter) })
                          }
                        >
                          Назначить
                        </button>
                      </div>
                    )}
                    <div className="incoming-card__actions">
                      {!isAdmin && (
                        <button
                          className="ui-btn ui-btn--primary ui-btn--sm"
                          type="button"
                          onClick={() => openIncomingSchedule(candidate)}
                        >
                          Предложить время
                        </button>
                      )}
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        type="button"
                        data-testid="incoming-card-test-preview"
                        onClick={() => openTestPreview(candidate)}
                      >
                        Тест
                      </button>
                      <Link
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        to="/app/candidates/$candidateId"
                        params={{ candidateId: String(candidate.id) }}
                      >
                        Профиль
                      </Link>
                      <button
                        className="ui-btn ui-btn--danger ui-btn--sm"
                        type="button"
                        onClick={() => rejectCandidate.mutate(candidate.id)}
                      >
                        Отказать
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>

      {incomingTarget && !isAdmin && (
        <ModalPortal>
          <div
            className="modal-overlay"
            onClick={(e) => e.target === e.currentTarget && setIncomingTarget(null)}
            role="dialog"
            aria-modal="true"
            data-testid="incoming-schedule-modal"
          >
            <div className={`glass glass--elevated modal modal--md ${isMobile ? 'modal--sheet' : ''}`} onClick={(e) => e.stopPropagation()}>
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
                <div className="toolbar toolbar--compact incoming-schedule-mode">
                  <button
                    type="button"
                    className={incomingMode === 'manual' ? 'ui-btn ui-btn--primary ui-btn--sm' : 'ui-btn ui-btn--ghost ui-btn--sm'}
                    onClick={() => setIncomingMode('manual')}
                  >
                    Указать вручную
                  </button>
                  <button
                    type="button"
                    className={incomingMode === 'existing' ? 'ui-btn ui-btn--primary ui-btn--sm' : 'ui-btn ui-btn--ghost ui-btn--sm'}
                    onClick={() => setIncomingMode('existing')}
                    disabled={(availableSlotsQuery.data?.items || []).length === 0}
                  >
                    Выбрать свободный слот ({(availableSlotsQuery.data?.items || []).length})
                  </button>
                </div>

                {incomingMode === 'manual' ? (
                  <div className="form-grid">
                    <label>
                      Дата
                      <input type="date" value={incomingDate} onChange={(e) => setIncomingDate(e.target.value)} />
                    </label>
                    <label>
                      Время (ваше локальное: {recruiterTz} · {formatTzOffset(recruiterTz)})
                      <input type="time" value={incomingTime} onChange={(e) => setIncomingTime(e.target.value)} />
                    </label>
                  </div>
                ) : (
                  <div className="form-group">
                    <label className="form-group__label">Свободный слот</label>
                    {availableSlotsQuery.isLoading && <p className="subtitle">Ищем свободные слоты…</p>}
                    {!availableSlotsQuery.isLoading && (availableSlotsQuery.data?.items || []).length === 0 && (
                      <p className="text-muted text-sm">
                        Нет подходящих свободных слотов. Переключитесь на ручной ввод времени.
                      </p>
                    )}
                    {!availableSlotsQuery.isLoading && (availableSlotsQuery.data?.items || []).length > 0 && (
                      <select value={selectedSlotId} onChange={(e) => setSelectedSlotId(e.target.value)}>
                        <option value="">Выберите слот</option>
                        {(availableSlotsQuery.data?.items || []).map((slot) => (
                          <option key={slot.slot_id} value={String(slot.slot_id)}>
                            {formatSlotOption(slot)}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                )}
                {incomingMode === 'manual' && incomingManualPreview && (
                  <div className="glass slot-preview">
                    <div>
                      <div className="slot-preview__label">Вы назначаете</div>
                      <div className="slot-preview__value">{incomingManualPreview.recruiterLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingManualPreview.recruiterTz} · {formatTzOffset(incomingManualPreview.recruiterTz)}
                      </div>
                    </div>
                    <div>
                      <div className="slot-preview__label">Кандидат увидит</div>
                      <div className="slot-preview__value">{incomingManualPreview.candidateLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingManualPreview.candidateTz} · {formatTzOffset(incomingManualPreview.candidateTz)}
                      </div>
                    </div>
                  </div>
                )}
                {incomingMode === 'existing' && incomingExistingPreview && (
                  <div className="glass slot-preview">
                    <div>
                      <div className="slot-preview__label">Время рекрутера</div>
                      <div className="slot-preview__value">{incomingExistingPreview.recruiterLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingExistingPreview.recruiterTz} · {formatTzOffset(incomingExistingPreview.recruiterTz)}
                      </div>
                    </div>
                    <div>
                      <div className="slot-preview__label">Время кандидата</div>
                      <div className="slot-preview__value">{incomingExistingPreview.candidateLabel}</div>
                      <div className="slot-preview__hint">
                        {incomingExistingPreview.candidateTz} · {formatTzOffset(incomingExistingPreview.candidateTz)}
                      </div>
                    </div>
                  </div>
                )}
                {(incomingManualPreview || incomingExistingPreview) && (
                  <p className="text-muted text-sm">
                    Напоминание за 2 часа отправляется по времени кандидата.
                  </p>
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
                    if (incomingMode === 'existing') {
                      if (!selectedSlotId) {
                        showToast('Выберите свободный слот')
                        return
                      }
                      scheduleIncoming.mutate({
                        candidate: incomingTarget,
                        slotId: Number(selectedSlotId),
                        message: incomingMessage,
                      })
                      return
                    }
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

      {testPreviewTarget && (
        <IncomingTestPreviewModal
          candidate={testPreviewTarget}
          detail={testPreviewQuery.data}
          isLoading={testPreviewQuery.isLoading}
          isError={testPreviewQuery.isError}
          error={testPreviewQuery.error as Error | null}
          isMobile={isMobile}
          canSchedule={!isAdmin}
          onClose={() => setTestPreviewTarget(null)}
          onSchedule={openScheduleFromTestPreview}
        />
      )}

      {toast && <div className="toast">{toast}</div>}
    </RoleGuard>
  )
}

export default IncomingPage
