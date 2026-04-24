import { useQuery, useMutation } from '@tanstack/react-query'
import { useMemo, useRef, useState, useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import '@/theme/pages/dashboard.css'
import { apiFetch } from '@/api/client'
import { fetchDashboardIncomingWindow } from '@/api/services/dashboard'
import { fetchCandidateDetail, type CandidateDetail } from '@/api/services/candidates'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { RoleGuard } from '@/app/components/RoleGuard'
import { browserTimeZone, buildSlotTimePreview, formatTzOffset } from '@/app/lib/timezonePreview'
import { ModalPortal } from '@/shared/components/ModalPortal'
import {
  clearIncomingPersistedFilters,
  type IncomingChannelFilter,
  loadIncomingPersistedFilters,
  saveIncomingPersistedFilters,
  type IncomingAiFilter,
  type IncomingOwnerFilter,
  type IncomingSortMode,
  type IncomingStatusFilter,
  type IncomingWaitingFilter,
} from './incoming.filters'
import { IncomingTestPreviewModal } from './incoming-test-preview-modal'
import {
  deriveIncomingSummary,
  formatAiDetailScore,
  formatAiDetailStateLabel,
  formatAiPrimaryScore,
  formatAiRecommendation,
  formatAiUpdatedAtLabel,
  formatInTz,
  formatRequestedAnotherTime,
  formatSlotOption,
  resolveAiStateTone,
  toIsoDate,
} from './incoming.utils'
import { buildCandidateSurfaceState } from './candidate-state.adapter'
import type {
  ActionResponse,
  AvailableSlotsPayload,
  IncomingCandidate,
  IncomingPayload,
  ScheduleIncomingPayload,
} from './incoming.types'

const STATUS_FILTER_LABELS: Record<IncomingStatusFilter, string> = {
  all: 'Все статусы',
  waiting_slot: 'Ожидают слот',
  stalled_waiting_slot: 'Застряли >24ч',
  requested_other_time: 'Запросили другое время',
}

const CHANNEL_FILTER_LABELS: Record<IncomingChannelFilter, string> = {
  all: 'Все каналы',
  telegram: 'Telegram',
  max: 'MAX',
}

const OWNER_FILTER_LABELS: Record<IncomingOwnerFilter, string> = {
  all: 'Любой ответственный',
  mine: 'Мои кандидаты',
  assigned: 'Есть ответственный',
  unassigned: 'Без ответственного',
}

const WAITING_FILTER_LABELS: Record<IncomingWaitingFilter, string> = {
  all: 'Любое ожидание',
  '24h': 'Ждут >=24ч',
  '48h': 'Ждут >=48ч',
}

const AI_FILTER_LABELS: Record<IncomingAiFilter, string> = {
  all: 'Любой AI level',
  high: 'AI: high',
  medium: 'AI: medium',
  low: 'AI: low',
  unknown: 'AI: unknown',
}

const SORT_MODE_LABELS: Record<IncomingSortMode, string> = {
  priority: 'По приоритету',
  waiting_desc: 'Дольше ждут',
  recent_desc: 'Свежие сообщения',
  ai_score_desc: 'AI relevance',
  name_asc: 'По имени',
}

const DEFAULT_INCOMING_PAGE_SIZE = 50
const INCOMING_PAGE_SIZE_OPTIONS = [25, 50, 100] as const

function formatAiSummary(candidate: IncomingCandidate): string | null {
  if (typeof candidate.ai_relevance_score === 'number') {
    const recommendation = formatAiRecommendation(candidate.ai_recommendation)
    return recommendation
      ? `${Math.round(candidate.ai_relevance_score)}/100 · ${recommendation}`
      : `${Math.round(candidate.ai_relevance_score)}/100`
  }
  if (candidate.ai_relevance_level) {
    const recommendation = formatAiRecommendation(candidate.ai_recommendation)
    return recommendation
      ? `${candidate.ai_relevance_level} · ${recommendation}`
      : candidate.ai_relevance_level
  }
  return null
}

export function IncomingPage() {
  const profile = useProfile()
  const isMobile = useIsMobile()
  const isAdmin = profile.data?.principal.type === 'admin'
  const recruiterId = profile.data?.recruiter?.id ?? null
  const recruiterTz = profile.data?.recruiter?.tz || browserTimeZone()
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
  const [channelFilter, setChannelFilter] = useState<IncomingChannelFilter>(() => persistedFilters.channelFilter ?? 'all')
  const [ownerFilter, setOwnerFilter] = useState<IncomingOwnerFilter>(() => persistedFilters.ownerFilter ?? 'all')
  const [waitingFilter, setWaitingFilter] = useState<IncomingWaitingFilter>(() => persistedFilters.waitingFilter ?? 'all')
  const [aiFilter, setAiFilter] = useState<IncomingAiFilter>(() => persistedFilters.aiFilter ?? 'all')
  const [sortMode, setSortMode] = useState<IncomingSortMode>(() => persistedFilters.sortMode ?? 'priority')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_INCOMING_PAGE_SIZE)
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(() => persistedFilters.showAdvancedFilters ?? false)
  const [expandedCardId, setExpandedCardId] = useState<number | null>(null)
  const toastTimeoutRef = useRef<number | null>(null)
  const [debouncedSearch, setDebouncedSearch] = useState(() => (persistedFilters.search ?? '').trim())

  useEffect(() => {
    if (isMobile) setShowAdvancedFilters(false)
  }, [isMobile])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebouncedSearch(search.trim()), 260)
    return () => window.clearTimeout(timeoutId)
  }, [search])

  const showToast = (message: string) => {
    setToast(message)
    if (toastTimeoutRef.current != null) {
      window.clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = window.setTimeout(() => setToast(null), 2400)
  }

  const cityOptions = useMemo(
    () => profile.data?.recruiter?.cities || [],
    [profile.data?.recruiter?.cities],
  )

  const incomingQuery = useQuery<IncomingPayload>({
    queryKey: ['dashboard-incoming', {
      page,
      pageSize,
      search: debouncedSearch,
      cityFilter,
      statusFilter,
      channelFilter,
      ownerFilter,
      waitingFilter,
      aiFilter,
      sortMode,
    }],
    queryFn: () => fetchDashboardIncomingWindow({
      page,
      pageSize,
      search: debouncedSearch,
      cityId: cityFilter === 'all' ? null : Number(cityFilter),
      status: statusFilter,
      channel: channelFilter,
      owner: ownerFilter,
      waiting: waitingFilter,
      aiLevel: aiFilter,
      sort: sortMode,
    }),
    placeholderData: (previousData) => previousData,
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
  const incomingRequestedPreference = useMemo(
    () => (incomingTarget ? formatRequestedAnotherTime(incomingTarget) : null),
    [incomingTarget],
  )

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

  const surfaceItems = useMemo(
    () => (incomingQuery.data?.items ?? []).map((candidate) => ({ candidate, state: buildCandidateSurfaceState(candidate) })),
    [incomingQuery.data?.items],
  )
  const summary = useMemo(
    () => deriveIncomingSummary(incomingQuery.data, { page, pageSize }),
    [incomingQuery.data, page, pageSize],
  )

  const activeFilters = useMemo(() => {
    const filters: Array<{ key: string; label: string; clear: () => void }> = []
    const searchValue = search.trim()
    if (searchValue) {
      filters.push({
        key: `search:${searchValue}`,
        label: `Поиск: ${searchValue}`,
        clear: () => setSearch(''),
      })
    }
    if (cityFilter !== 'all') {
      const cityLabel = cityOptions.find((city) => String(city.id) === cityFilter)?.name || cityFilter
      filters.push({
        key: `city:${cityFilter}`,
        label: `Город: ${cityLabel}`,
        clear: () => setCityFilter('all'),
      })
    }
    if (statusFilter !== 'all') {
      filters.push({
        key: `status:${statusFilter}`,
        label: STATUS_FILTER_LABELS[statusFilter],
        clear: () => setStatusFilter('all'),
      })
    }
    if (channelFilter !== 'all') {
      filters.push({
        key: `channel:${channelFilter}`,
        label: `Канал: ${CHANNEL_FILTER_LABELS[channelFilter]}`,
        clear: () => setChannelFilter('all'),
      })
    }
    if (ownerFilter !== 'all') {
      filters.push({
        key: `owner:${ownerFilter}`,
        label: OWNER_FILTER_LABELS[ownerFilter],
        clear: () => setOwnerFilter('all'),
      })
    }
    if (waitingFilter !== 'all') {
      filters.push({
        key: `waiting:${waitingFilter}`,
        label: WAITING_FILTER_LABELS[waitingFilter],
        clear: () => setWaitingFilter('all'),
      })
    }
    if (aiFilter !== 'all') {
      filters.push({
        key: `ai:${aiFilter}`,
        label: AI_FILTER_LABELS[aiFilter],
        clear: () => setAiFilter('all'),
      })
    }
    return filters
  }, [aiFilter, channelFilter, cityFilter, cityOptions, ownerFilter, search, statusFilter, waitingFilter])

  useEffect(() => {
    if (typeof window === 'undefined') return
    saveIncomingPersistedFilters(window.localStorage, {
      search,
      cityFilter,
      statusFilter,
      channelFilter,
      ownerFilter,
      waitingFilter,
      aiFilter,
      sortMode,
      showAdvancedFilters,
    })
  }, [aiFilter, channelFilter, cityFilter, ownerFilter, search, showAdvancedFilters, sortMode, statusFilter, waitingFilter])

  useEffect(() => {
    if (!incomingQuery.data) return
    if (incomingQuery.data.total > 0 && incomingQuery.data.returned_count === 0 && page > 1) {
      setPage((current) => Math.max(1, current - 1))
    }
  }, [incomingQuery.data, page])

  useEffect(() => {
    if (expandedCardId == null) return
    if (!surfaceItems.some(({ candidate }) => candidate.id === expandedCardId)) {
      setExpandedCardId(null)
    }
  }, [expandedCardId, surfaceItems])

  useEffect(() => {
    setPage(1)
  }, [debouncedSearch, cityFilter, statusFilter, channelFilter, ownerFilter, waitingFilter, aiFilter, sortMode, pageSize])

  const resetFilters = () => {
    setSearch('')
    setCityFilter('all')
    setStatusFilter('all')
    setChannelFilter('all')
    setOwnerFilter('all')
    setWaitingFilter('all')
    setAiFilter('all')
    setSortMode('priority')
    setShowAdvancedFilters(false)
    setPage(1)
    if (typeof window !== 'undefined') {
      clearIncomingPersistedFilters(window.localStorage)
    }
  }

  const toggleCardExpanded = (candidateId: number) => {
    setExpandedCardId((current) => (current === candidateId ? null : candidateId))
  }

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page app-page app-page--ops app-page--incoming">
        <section className="glass page-section ui-stack-16 app-page__section incoming-page">
          <div className="incoming-page__toolbar">
            <div className="incoming-page__summary">
              <h1 className="incoming-page__title">Входящие</h1>
              <div className="incoming-page__summary-line">
                <span className="incoming-page__summary-label">Во входящих</span>
                <strong className="incoming-page__summary-value" data-testid="incoming-queue-total">{summary.queueTotal}</strong>
                <span className="incoming-page__summary-meta">кандидатов</span>
              </div>
              <div className="incoming-page__summary-detail" data-testid="incoming-summary-detail">
                <span>Показано {summary.shownStart}–{summary.shownEnd}</span>
                {activeFilters.length > 0 && <span>По фильтрам {summary.filteredTotal}</span>}
                {incomingQuery.isFetching && !incomingQuery.isLoading && <span>Обновляем…</span>}
              </div>
            </div>
            <div className="incoming-page__controls" data-testid="incoming-pagination">
              <label className="incoming-page__control">
                <span>Показывать</span>
                <select value={String(pageSize)} onChange={(e) => setPageSize(Number(e.target.value))}>
                  {INCOMING_PAGE_SIZE_OPTIONS.map((value) => (
                    <option key={value} value={value}>{value} на странице</option>
                  ))}
                </select>
              </label>
              <div className="incoming-page__pager">
                <button
                  className="ui-btn ui-btn--ghost ui-btn--sm"
                  type="button"
                  disabled={!incomingQuery.data?.has_prev || incomingQuery.isFetching}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                >
                  Назад
                </button>
                <span className="incoming-page__pager-label">
                  Страница {summary.page} из {summary.pageCount}
                </span>
                <button
                  className="ui-btn ui-btn--ghost ui-btn--sm"
                  type="button"
                  disabled={!incomingQuery.data?.has_next || incomingQuery.isFetching}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Дальше
                </button>
              </div>
            </div>
          </div>

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
              <option value="requested_other_time">Запросили другое время</option>
            </select>
            <select value={channelFilter} onChange={(e) => setChannelFilter(e.target.value as IncomingChannelFilter)}>
              <option value="all">Все каналы</option>
              <option value="telegram">Telegram</option>
              <option value="max">MAX</option>
            </select>
            <select value={sortMode} onChange={(e) => setSortMode(e.target.value as IncomingSortMode)}>
              {Object.entries(SORT_MODE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
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
          {activeFilters.length > 0 && (
            <div className="dashboard-filter-strip" data-testid="incoming-active-filters">
              {activeFilters.map((filter) => (
                <button key={filter.key} type="button" className="dashboard-filter-pill" onClick={filter.clear}>
                  <span>{filter.label}</span>
                  <span aria-hidden="true">×</span>
                </button>
              ))}
            </div>
          )}
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
          {incomingQuery.data && surfaceItems.length === 0 && (
            <div data-testid="incoming-empty-state">
              <p className="subtitle">Нет кандидатов по выбранным фильтрам.</p>
            </div>
          )}
          {incomingQuery.data && surfaceItems.length > 0 && (
            <div className="incoming-list" data-testid="incoming-list" role="list">
              {surfaceItems.map(({ candidate, state }) => {
                const isNew = candidate.last_message_at
                  ? Date.now() - new Date(candidate.last_message_at).getTime() < 24 * 60 * 60 * 1000
                  : false
                const selectedRecruiter =
                  assignTargets[candidate.id] ??
                  (candidate.responsible_recruiter_id ? String(candidate.responsible_recruiter_id) : '')
                const isExpanded = expandedCardId === candidate.id
                const requestedAnotherTimeLabel = formatRequestedAnotherTime(candidate)
                const aiSummary = formatAiSummary(candidate)
                const aiTone = resolveAiStateTone(candidate)
                const fullAiReasons = candidate.ai_reasons || []
                const statusChips: Array<{ key: string; label: string; tone: string }> = [
                  {
                    key: 'status',
                    label: state.statusLabel,
                    tone: state.statusTone,
                  },
                ]
                if (state.requestedOtherTime) {
                  statusChips.push({
                    key: 'requested-other-time',
                    label: 'Запросил другое время',
                    tone: 'warning',
                  })
                } else if (
                  state.schedulingLabel
                  && state.schedulingLabel !== state.statusLabel
                  && statusChips.length < 2
                ) {
                  statusChips.push({
                    key: 'scheduling',
                    label: state.schedulingLabel,
                    tone: state.schedulingTone || 'info',
                  })
                }
                if (state.hasReconciliationIssues) {
                  statusChips.push({
                    key: 'reconciliation',
                    label: 'Требует проверки',
                    tone: 'danger',
                  })
                }
                const visibleStatusChips = statusChips.slice(0, 3)
                const compactActionLabel = state.nextActionLabel || 'Открыть профиль'
                const compactRiskLabel = !state.hasReconciliationIssues && state.riskTitle ? state.riskTitle : null
                const primaryActionLabel = state.requestedOtherTime ? 'Подобрать время' : 'Предложить время'
                return (
                  <article
                    key={candidate.id}
                    className="glass glass--subtle incoming-row ui-reveal"
                    data-testid="incoming-row"
                    role="listitem"
                  >
                    <div className="incoming-row__head">
                      <div className="incoming-row__identity">
                        <div className="incoming-row__name-line">
                          <div className="incoming-row__name">
                            {candidate.name || 'Без имени'}
                            {isNew && <span className="incoming-card__badge">NEW</span>}
                          </div>
                          <div className="incoming-row__metrics">
                            <span className="incoming-row__waiting">
                              {candidate.waiting_hours != null ? `Ждёт ${candidate.waiting_hours} ч` : 'Без ожидания'}
                            </span>
                            <span className={`incoming-row__score incoming-row__score--${aiTone}`} data-testid="incoming-ai-score">
                              <span className="incoming-row__score-label">AI</span>
                              <strong className="incoming-row__score-value">{formatAiPrimaryScore(candidate)}</strong>
                            </span>
                          </div>
                        </div>
                        <div className="incoming-row__meta">
                          <span>{candidate.city || 'Город не указан'}</span>
                          {isAdmin && candidate.responsible_recruiter_name && (
                            <span>· Ответственный: {candidate.responsible_recruiter_name}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="incoming-row__summary">
                      <div className="incoming-row__status-strip">
                        {visibleStatusChips.map((chip) => (
                          <span key={chip.key} className={`status-pill status-pill--${chip.tone}`}>{chip.label}</span>
                        ))}
                      </div>
                      <div className="incoming-row__action-summary">
                        <span className="incoming-row__action-kicker">Сейчас</span>
                        <strong className="incoming-row__action-text">{compactActionLabel}</strong>
                        {compactRiskLabel && (
                          <span className={`incoming-row__risk-marker incoming-row__risk-marker--${state.riskLevel || 'warning'}`}>
                            {compactRiskLabel}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="incoming-row__footer">
                      <div className="incoming-row__primary">
                        {isAdmin ? (
                          <div className="incoming-row__assign">
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
                        ) : (
                          <button
                            className="ui-btn ui-btn--primary ui-btn--sm"
                            type="button"
                            onClick={() => openIncomingSchedule(candidate)}
                          >
                            {primaryActionLabel}
                          </button>
                        )}
                      </div>
                      <div className="incoming-row__actions">
                        <button
                          className="ui-btn ui-btn--ghost ui-btn--sm"
                          type="button"
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
                          type="button"
                          className="ui-btn ui-btn--ghost ui-btn--sm"
                          onClick={() => toggleCardExpanded(candidate.id)}
                        >
                          {isExpanded ? 'Скрыть детали' : 'Подробнее'}
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
                    {isExpanded && (
                      <div className="incoming-row__details" data-testid={`incoming-row-details-${candidate.id}`}>
                        {state.riskTitle && state.riskMessage && (
                          <div className="incoming-row__detail-card incoming-row__detail-card--risk">
                            <strong>{state.riskTitle}</strong>
                            <span>{state.riskMessage}</span>
                          </div>
                        )}
                        {requestedAnotherTimeLabel && (
                          <div className="incoming-row__detail-card incoming-row__detail-card--requested">
                            <strong>Желаемое время</strong>
                            <span>{requestedAnotherTimeLabel}</span>
                          </div>
                        )}
                        {candidate.requested_another_time_comment && requestedAnotherTimeLabel !== `Пожелание: ${candidate.requested_another_time_comment}` && (
                          <div className="incoming-row__detail-card incoming-row__detail-card--requested">
                            <strong>Комментарий кандидата</strong>
                            <span>{candidate.requested_another_time_comment}</span>
                          </div>
                        )}
                        {candidate.last_message && (
                          <div className="incoming-row__detail-card">
                            <strong>Последнее сообщение</strong>
                            <span>{candidate.last_message}</span>
                            {candidate.last_message_at && (
                              <span className="incoming-row__detail-meta">
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
                        {candidate.availability_note && (
                          <div className="incoming-row__detail-card">
                            <strong>Пожелания по времени</strong>
                            <span>{candidate.availability_note}</span>
                          </div>
                        )}
                        <div className="incoming-row__detail-card incoming-row__detail-card--ai">
                          <div className="incoming-row__detail-head">
                            <strong>AI relevance</strong>
                            <span className={`incoming-row__detail-score incoming-row__detail-score--${aiTone}`}>
                              {formatAiDetailScore(candidate)}
                            </span>
                          </div>
                          <div className="incoming-row__detail-meta">
                            <span>{formatAiDetailStateLabel(candidate.ai_relevance_state)}</span>
                            {formatAiUpdatedAtLabel(candidate.ai_relevance_updated_at) && (
                              <span>· {formatAiUpdatedAtLabel(candidate.ai_relevance_updated_at)}</span>
                            )}
                          </div>
                          {fullAiReasons.length > 0 && (
                            <div className="incoming-row__ai-reasons">
                              {fullAiReasons.map((reason) => (
                                <span
                                  key={`expanded-${candidate.id}-${reason.tone}-${reason.label}`}
                                  className={`incoming-ai__chip incoming-ai__chip--${reason.tone}`}
                                >
                                  {reason.label}
                                </span>
                              ))}
                            </div>
                          )}
                          {!fullAiReasons.length && aiSummary && <span>{aiSummary}</span>}
                          {candidate.ai_risk_hint && <span>{candidate.ai_risk_hint}</span>}
                        </div>
                      </div>
                    )}
                  </article>
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
                {(incomingRequestedPreference || incomingTarget.availability_note) && (
                  <div className="incoming-row__detail-card incoming-row__detail-card--requested">
                    <strong>Что попросил кандидат</strong>
                    {incomingRequestedPreference && <span>{incomingRequestedPreference}</span>}
                    {incomingTarget.availability_note && <span>{incomingTarget.availability_note}</span>}
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
