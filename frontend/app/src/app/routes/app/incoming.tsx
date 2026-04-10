import { useQuery, useMutation } from '@tanstack/react-query'
import { useMemo, useRef, useState, useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import '@/theme/pages/dashboard.css'
import { apiFetch } from '@/api/client'
import {
  RecruiterActionBlock,
  RecruiterRiskBanner,
  RecruiterStateContext,
} from '@/app/components/RecruiterState'
import { fetchCandidateDetail, type CandidateDetail } from '@/api/services/candidates'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { RoleGuard } from '@/app/components/RoleGuard'
import { browserTimeZone, buildSlotTimePreview, formatTzOffset } from '@/app/lib/timezonePreview'
import { ModalPortal } from '@/shared/components/ModalPortal'
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
import { IncomingTestPreviewModal } from './incoming-test-preview-modal'
import {
  formatAiRecommendation,
  formatInTz,
  formatRequestedAnotherTime,
  formatSlotOption,
  resolveAiScoreTone,
  toIsoDate,
} from './incoming.utils'
import {
  buildCandidateSurfaceState,
  compareIncomingCandidates,
  matchesIncomingStatusFilter,
  summarizeIncomingCandidates,
} from './candidate-state.adapter'
import type {
  ActionResponse,
  AvailableSlotsPayload,
  IncomingCandidate,
  IncomingPayload,
  ScheduleIncomingPayload,
} from './incoming.types'

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
  const toastTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    if (isMobile) setShowAdvancedFilters(false)
  }, [isMobile])

  const showToast = (message: string) => {
    setToast(message)
    if (toastTimeoutRef.current != null) {
      window.clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = window.setTimeout(() => setToast(null), 2400)
  }

  const incomingQuery = useQuery<IncomingPayload>({
    queryKey: ['dashboard-incoming'],
    queryFn: () => apiFetch('/dashboard/incoming?limit=100'),
    staleTime: 120_000,
    refetchInterval: 120_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const availableSlotsQuery = useQuery<AvailableSlotsPayload>({
    queryKey: ['incoming-available-slots', incomingTarget?.id],
    queryFn: () => apiFetch(`/candidates/${incomingTarget?.id}/available-slots?limit=60`),
    enabled: Boolean(incomingTarget?.id && !isAdmin),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const recruitersQuery = useQuery<{ id: number; name: string }[]>({
    queryKey: ['incoming-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const testPreviewQuery = useQuery<CandidateDetail>({
    queryKey: ['candidate-detail', testPreviewTarget?.id],
    queryFn: () => fetchCandidateDetail(Number(testPreviewTarget?.id)),
    enabled: Boolean(testPreviewTarget?.id),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
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
        return apiFetch<ActionResponse>(`/candidates/${payload.candidate.id}/schedule-slot`, {
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
      return apiFetch<ActionResponse>(`/candidates/${payload.candidate.id}/schedule-slot`, {
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
    onSuccess: (data: ActionResponse) => {
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
      apiFetch<ActionResponse>(`/candidates/${candidateId}/actions/reject`, { method: 'POST' }),
    onSuccess: (data: ActionResponse) => {
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
      items = items.filter((item) => matchesIncomingStatusFilter(item, statusFilter))
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
          item.lifecycle_summary?.stage_label,
          item.scheduling_summary?.status_label,
          item.candidate_next_action?.primary_action?.label,
          item.state_reconciliation?.issues?.map((issue) => issue.message).filter(Boolean).join(' '),
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(q))
      )
    }

    return [...items].sort((left, right) => compareIncomingCandidates(left, right, 'waiting'))
  }, [aiFilter, baseItems, cityFilter, ownerFilter, recruiterId, search, statusFilter, waitingFilter])

  const triageItems = useMemo(
    () => filteredItems.map((candidate) => ({ candidate, state: buildCandidateSurfaceState(candidate) })),
    [filteredItems],
  )

  const triageLanes = useMemo(() => {
    const lanes = {
      action_now: [] as typeof triageItems,
      waiting: [] as typeof triageItems,
      review: [] as typeof triageItems,
    }
    for (const item of triageItems) {
      lanes[item.state.triageLane].push(item)
    }
    return [
      {
        key: 'action_now' as const,
        title: 'Требует действия сейчас',
        description: 'Срочные и управляемые кандидаты, где следующий шаг уже понятен.',
        items: lanes.action_now,
      },
      {
        key: 'waiting' as const,
        title: 'Ждет кандидата / в процессе',
        description: 'Есть движение по воронке, но ручное вмешательство не горит.',
        items: lanes.waiting,
      },
      {
        key: 'review' as const,
        title: 'Требует разбора',
        description: 'Конфликты состояния, блокировки и кандидаты, которые нельзя двигать вслепую.',
        items: lanes.review,
      },
    ]
  }, [triageItems])

  const laneCounts = useMemo(
    () => triageLanes.reduce((acc, lane) => ({ ...acc, [lane.key]: lane.items.length }), { action_now: 0, waiting: 0, review: 0 }),
    [triageLanes],
  )

  const stats = useMemo(() => {
    const summary = summarizeIncomingCandidates(baseItems)
    return {
      total: summary.total,
      pending: summary.pending,
      stalled: summary.stalled,
      requested: summary.requested,
    }
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
            <span className="cd-chip">Всего: {triageItems.length}</span>
            <span className="cd-chip">Сейчас: {laneCounts.action_now}</span>
            <span className="cd-chip">В ожидании: {laneCounts.waiting}</span>
            <span className="cd-chip">Требуют разбора: {laneCounts.review}</span>
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
          {incomingQuery.data && triageItems.length === 0 && (
            <div data-testid="incoming-empty-state">
              <p className="subtitle">Нет кандидатов по выбранным фильтрам.</p>
            </div>
          )}
          {incomingQuery.data && triageItems.length > 0 && (
            <div className="incoming-lanes" data-testid="incoming-lanes">
              {triageLanes.map((lane) => (
                <section key={lane.key} className={`glass glass--subtle incoming-lane incoming-lane--${lane.key}`} data-testid={`incoming-lane-${lane.key}`}>
                  <header className="incoming-lane__header">
                    <div>
                      <h2 className="incoming-lane__title">{lane.title}</h2>
                      <p className="incoming-lane__subtitle">{lane.description}</p>
                    </div>
                    <span className="incoming-lane__count">{lane.items.length}</span>
                  </header>
                  {lane.items.length === 0 ? (
                    <div className="incoming-lane__empty">Нет кандидатов в этой зоне.</div>
                  ) : (
                    <div className="incoming-grid">
                      {lane.items.map(({ candidate, state }) => {
                const isNew = candidate.last_message_at
                  ? Date.now() - new Date(candidate.last_message_at).getTime() < 24 * 60 * 60 * 1000
                  : false
                const selectedRecruiter =
                  assignTargets[candidate.id] ??
                  (candidate.responsible_recruiter_id ? String(candidate.responsible_recruiter_id) : '')
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
                      </div>
                    </div>

                    <RecruiterActionBlock
                      label={state.nextActionLabel || 'Откройте профиль'}
                      explanation={state.nextActionExplanation || 'Следующий шаг появится в профиле кандидата.'}
                      tone={state.nextActionTone}
                      enabled={state.nextActionEnabled}
                      compact
                    />
                    <RecruiterStateContext
                      bucketLabel={state.worklistBucketLabel}
                      contextLine={state.stateContextLine}
                      schedulingLine={state.schedulingContextLine}
                      compact
                    />
                    {state.riskLevel && state.riskTitle && state.riskMessage ? (
                      <RecruiterRiskBanner
                        level={state.riskLevel}
                        title={state.riskTitle}
                        message={state.riskMessage}
                        count={state.riskCount > 0 ? state.riskCount : undefined}
                        compact
                      />
                    ) : null}
                    <div className="incoming-card__status-row toolbar toolbar--compact">
                      {(candidate.ai_relevance_score != null || candidate.ai_relevance_level) && (
                        <span className={`status-pill status-pill--${resolveAiScoreTone(candidate.ai_relevance_score, candidate.ai_recommendation)}`}>
                          AI {typeof candidate.ai_relevance_score === 'number' ? `${Math.round(candidate.ai_relevance_score)}/100` : candidate.ai_relevance_level || 'unknown'}
                        </span>
                      )}
                      {formatAiRecommendation(candidate.ai_recommendation) && (
                        <span className={`status-pill ${candidate.ai_recommendation === 'not_recommended' ? 'status-pill--danger' : candidate.ai_recommendation === 'od_recommended' ? 'status-pill--success' : 'status-pill--info'}`}>
                          {formatAiRecommendation(candidate.ai_recommendation)}
                        </span>
                      )}
                    </div>

                    {requestedAnotherTimeLabel && (
                      <div className="incoming-card__note incoming-card__note--highlight">
                        🗓 {requestedAnotherTimeLabel}
                      </div>
                    )}
                    {candidate.availability_note && isExpanded && (
                      <div className="incoming-card__note incoming-card__note--muted">
                        ✉️ {candidate.availability_note}
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
                    {candidate.ai_risk_hint && (
                      <div className="incoming-card__note incoming-card__note--muted">
                        AI: {candidate.ai_risk_hint}
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
              ))}
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
