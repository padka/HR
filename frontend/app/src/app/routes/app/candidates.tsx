import { Link } from '@tanstack/react-router'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { memo, useCallback, useEffect, useMemo, useState, type DragEvent } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { apiFetch } from '@/api/client'
import {
  CandidateIdentityBlock,
  RecruiterActionBlock,
  RecruiterKanbanColumnHeader,
  RecruiterRiskBanner,
  RecruiterStateContext,
} from '@/app/components/RecruiterState'
import type {
  CandidateBlockingState,
  CandidateListCard,
  CandidateListPayload,
  CandidateStateFilterOption,
} from '@/api/services/candidates'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import '@/theme/pages/candidates.css'
import { fadeIn, listItem, stagger } from '@/shared/motion'
import {
  buildCandidateSurfaceState,
  describeKanbanColumnTreatment,
  RECRUITER_KANBAN_COLUMNS,
  type RecruiterKanbanColumn,
} from './candidate-state.adapter'

type CityOption = {
  id: number
  name: string
  tz?: string | null
  active?: boolean
}

type AICityCandidateRecommendation = {
  candidate_id: number
  fit_score?: number | null
  fit_level?: 'high' | 'medium' | 'low' | 'unknown'
  reason: string
  suggested_next_step?: string | null
}

type AICityRecommendationsResponse = {
  ok: boolean
  cached: boolean
  input_hash: string
  criteria_used?: boolean
  recommended: AICityCandidateRecommendation[]
  notes?: string | null
}

type CandidateKanbanMoveResponse = {
  ok: boolean
  message?: string
  status?: string
  candidate_id?: number
  error?: string
  blocking_state?: CandidateBlockingState | null
  intent?: {
    kind?: string
    target_column?: string | null
    intent_key?: string | null
    resolved_status?: string | null
    resolution?: string | null
    compatibility_source?: string | null
  } | null
  candidate_state?: {
    operational_summary?: {
      kanban_column?: string | null
    } | null
  } | null
}

type KanbanMoveVariables = {
  candidateId: number
  targetColumn: RecruiterKanbanColumn['slug']
  previousStatus?: RecruiterKanbanColumn['slug'] | null
}

type CandidateMoveError = Error & {
  data?: CandidateKanbanMoveResponse
}

const DEFAULT_STATE_FILTER_OPTIONS: CandidateStateFilterOption[] = [
  { value: '', label: 'Все кандидаты', kind: 'all' },
  ...RECRUITER_KANBAN_COLUMNS.map((column) => ({
    value: `kanban:${column.slug}`,
    label: `${column.icon} ${column.label}`,
    kind: 'kanban',
    icon: column.icon,
    target_status: column.targetStatus,
  })),
]

const DEFAULT_KANBAN_COLUMNS = RECRUITER_KANBAN_COLUMNS.map((column) => ({
  slug: column.slug,
  label: column.label,
  icon: column.icon,
  tone: 'info',
  target_status: column.targetStatus,
  droppable: column.droppable ?? true,
  total: 0,
  candidates: [] as CandidateListCard[],
}))

function candidateScoreTone(score?: number | null) {
  if (typeof score !== 'number') return 'neutral'
  if (score >= 70) return 'success'
  if (score >= 40) return 'warning'
  return 'danger'
}

function formatCandidateDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

function resolveCandidateDate(candidate: {
  primary_event_at?: string | null
  upcoming_slot?: { start_utc?: string | null } | null
  latest_slot?: { start_utc?: string | null } | null
  latest_message?: { created_at?: string | null } | null
}) {
  return (
    candidate.primary_event_at
    || candidate.upcoming_slot?.start_utc
    || candidate.latest_slot?.start_utc
    || candidate.latest_message?.created_at
    || null
  )
}

function buildSecondaryStatusLabel(state: {
  statusLabel?: string | null
  stateContextLine?: string | null
  schedulingContextLine?: string | null
}) {
  const value = state.statusLabel?.trim()
  if (!value) return null
  if (value === state.stateContextLine?.trim()) return null
  if (value === state.schedulingContextLine?.trim()) return null
  return value
}

type CandidateKanbanCardProps = {
  card: CandidateListCard
  canDelete: boolean
  isDeleting: boolean
  isDragging: boolean
  isMoving: boolean
  shouldAnimate: boolean
  onDeleteCandidate: (candidate: { id: number; fio?: string | null }) => void
  onDragStart: (event: DragEvent<HTMLDivElement>) => void
  onDragEnd: () => void
}

const CandidateKanbanCard = memo(function CandidateKanbanCard({
  card,
  canDelete,
  isDeleting,
  isDragging,
  isMoving,
  shouldAnimate,
  onDeleteCandidate,
  onDragStart,
  onDragEnd,
}: CandidateKanbanCardProps) {
  const state = buildCandidateSurfaceState(card)
  const scoreTone = candidateScoreTone(card.average_score)
  const cardDate = formatCandidateDate(resolveCandidateDate(card))

  return (
    <motion.div
      className={`glass glass--interactive kanban__card kanban-card ${isDragging ? 'kanban__card--dragging kanban-card--dragging' : ''} ${isMoving ? 'kanban__card--moving' : ''}`}
      draggable={!isMoving}
      onDragStartCapture={onDragStart}
      onDragEndCapture={onDragEnd}
      data-candidate-id={card.id}
      variants={shouldAnimate ? listItem : undefined}
    >
      <div className="kanban-card__header">
        <CandidateIdentityBlock
          title={card.fio || '—'}
          subtitle={card.city || '—'}
          compact
          aside={typeof card.average_score === 'number' ? (
            <span className={`candidate-score candidate-score--${scoreTone}`}>{Math.round(card.average_score)}%</span>
          ) : null}
        />
      </div>
      <RecruiterActionBlock
        label={state.nextActionLabel || 'Следующий шаг уточняется'}
        explanation={state.nextActionExplanation || 'Откройте профиль, чтобы продолжить работу без потери контекста.'}
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
          recoveryHint={state.riskRecoveryHint}
          count={state.riskCount > 0 ? state.riskCount : undefined}
          compact
        />
      ) : null}
      <div className="kanban-card__footer">
        <span>{card.recruiter?.name || '—'}</span>
        <span>{cardDate}</span>
      </div>
      <div className="kanban__card-footer">
        <div className="toolbar">
          {canDelete && (
            <button
              type="button"
              className="ui-btn ui-btn--danger ui-btn--sm"
              onClick={() => onDeleteCandidate({ id: card.id, fio: card.fio })}
              disabled={isDeleting || isMoving}
            >
              {isDeleting ? 'Удаление…' : 'Удалить'}
            </button>
          )}
          <Link to="/app/candidates/$candidateId" params={{ candidateId: String(card.id) }} className="ui-btn ui-btn--ghost ui-btn--sm">
            Открыть →
          </Link>
        </div>
      </div>
    </motion.div>
  )
})

export function CandidatesPage() {
  const profile = useProfile()
  const isMobile = useIsMobile()
  const prefersReducedMotion = useReducedMotion()
  const queryClient = useQueryClient()
  const principalType = profile.data?.principal.type
  const isAdmin = principalType === 'admin'

  const initialFilters = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return {
      search: params.get('search') ?? '',
      stateFilter: params.get('state') ?? params.get('status') ?? '',
      pipeline: params.get('pipeline') ?? 'interview',
    }
  }, [])

  const [search, setSearch] = useState(initialFilters.search)
  const [stateFilter, setStateFilter] = useState(initialFilters.stateFilter)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [pipeline, setPipeline] = useState(initialFilters.pipeline)
  const [view, setView] = useState<'list' | 'kanban' | 'calendar'>('list')
  const [aiCityId, setAiCityId] = useState('')
  const [deletingCandidateId, setDeletingCandidateId] = useState<number | null>(null)
  const [deleteCandidateError, setDeleteCandidateError] = useState<Error | null>(null)
  const [kanbanMoveError, setKanbanMoveError] = useState<Error | null>(null)
  const [kanbanMoveBlockingState, setKanbanMoveBlockingState] = useState<CandidateBlockingState | null>(null)
  const [kanbanMoveBlockingMessage, setKanbanMoveBlockingMessage] = useState<string | null>(null)
  const [kanbanStatusOverrides, setKanbanStatusOverrides] = useState<Record<number, RecruiterKanbanColumn['slug']>>({})
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<number[]>([])
  const [draggingCardId, setDraggingCardId] = useState<number | null>(null)
  const [dragOverColumn, setDragOverColumn] = useState<string | null>(null)
  const [movingCandidateId, setMovingCandidateId] = useState<number | null>(null)
  const [hasAnimatedLists, setHasAnimatedLists] = useState(false)
  const [calendarFrom, setCalendarFrom] = useState(() => {
    const d = new Date()
    return d.toISOString().slice(0, 10)
  })
  const [calendarTo, setCalendarTo] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + 6)
    return d.toISOString().slice(0, 10)
  })

  const pipelineForRequest = view === 'kanban' ? 'main' : pipeline
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (stateFilter) params.set('state', stateFilter)
  if (pipelineForRequest) params.set('pipeline', pipelineForRequest)
  params.set('page', String(page))
  params.set('per_page', String(perPage))
  if (view === 'calendar') {
    params.set('calendar_mode', 'day')
    params.set('date_from', calendarFrom)
    params.set('date_to', calendarTo)
  }

  const { data, isLoading, isError, error } = useQuery<CandidateListPayload>({
    queryKey: ['candidates', { search, stateFilter, page, perPage, pipeline: pipelineForRequest, view, calendarFrom, calendarTo }],
    queryFn: () => apiFetch(`/candidates?${params.toString()}`),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const citiesQuery = useQuery<CityOption[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const aiRecoQuery = useQuery<AICityRecommendationsResponse>({
    queryKey: ['ai-city-reco', aiCityId],
    queryFn: () => {
      if (!aiCityId) throw new Error('Выберите город')
      return apiFetch(`/ai/cities/${aiCityId}/candidates/recommendations?limit=30`)
    },
    enabled: false,
    retry: false,
  })

  const deleteCandidateMutation = useMutation({
    mutationFn: async (candidateId: number) =>
      apiFetch<{ ok: boolean; id: number }>(`/candidates/${candidateId}`, {
        method: 'DELETE',
      }),
    onSuccess: async () => {
      setDeleteCandidateError(null)
      await queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
    onError: (error: Error) => {
      setDeleteCandidateError(error)
    },
    onSettled: () => {
      setDeletingCandidateId(null)
    },
  })

  const moveKanbanCandidateMutation = useMutation({
    mutationFn: async ({ candidateId, targetColumn }: KanbanMoveVariables) =>
      apiFetch<CandidateKanbanMoveResponse>(`/candidates/${candidateId}/kanban-status`, {
        method: 'POST',
        body: JSON.stringify({ target_column: targetColumn }),
      }),
    onMutate: ({ candidateId }: KanbanMoveVariables) => {
      setKanbanMoveError(null)
      setKanbanMoveBlockingState(null)
      setKanbanMoveBlockingMessage(null)
      setMovingCandidateId(candidateId)
    },
    onSuccess: async (_data, variables) => {
      setKanbanMoveError(null)
      setKanbanMoveBlockingState(null)
      setKanbanMoveBlockingMessage(null)
      setKanbanStatusOverrides((prev) => {
        const next = { ...prev }
        delete next[variables.candidateId]
        return next
      })
      await queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
    onError: (error: Error, variables) => {
      const response = (error as CandidateMoveError).data
      setKanbanMoveError(response?.blocking_state ? null : error)
      setKanbanMoveBlockingState(response?.blocking_state ?? null)
      setKanbanMoveBlockingMessage(response?.message || error.message)
      setKanbanStatusOverrides((prev) => {
        const next = { ...prev }
        if (variables.previousStatus) {
          next[variables.candidateId] = variables.previousStatus
        } else {
          delete next[variables.candidateId]
        }
        return next
      })
    },
    onSettled: () => {
      setMovingCandidateId(null)
    },
  })
  const deleteCandidateMutate = deleteCandidateMutation.mutate
  const moveKanbanCandidateMutate = moveKanbanCandidateMutation.mutate

  const total = data?.total ?? 0
  const pagesTotal = data?.pages_total ?? 1
  const stateOptions = useMemo(() => {
    const baseOptions = data?.filters?.state_options?.length
      ? data.filters.state_options
      : DEFAULT_STATE_FILTER_OPTIONS
    if (!stateFilter || baseOptions.some((option) => option.value === stateFilter)) {
      return baseOptions
    }
    return [
      ...baseOptions,
      {
        value: stateFilter,
        label: stateFilter,
        kind: 'legacy',
      },
    ]
  }, [data?.filters?.state_options, stateFilter])
  const listCards = useMemo<CandidateListCard[]>(
    () => {
      if (data?.views?.candidates?.length) return data.views.candidates
      return (data?.items || []).map((item) => ({
        id: item.id,
        fio: item.fio,
        city: item.city,
        telegram_id: item.telegram_id,
        status: item.status,
        recruiter_id: item.recruiter_id,
        recruiter_name: item.recruiter_name,
        recruiter: item.recruiter,
        average_score: item.average_score,
        primary_event_at: item.primary_event_at,
        latest_slot: item.latest_slot,
        upcoming_slot: item.upcoming_slot,
      }))
    },
    [data?.items, data?.views?.candidates],
  )
  const kanbanCards = useMemo(
    () => listCards,
    [listCards],
  )
  const backendKanbanColumns = useMemo(
    () => (data?.views?.kanban?.columns?.length ? data.views.kanban.columns : DEFAULT_KANBAN_COLUMNS),
    [data?.views?.kanban?.columns],
  )
  const kanbanColumnsBySlug = useMemo(
    () => new Map(backendKanbanColumns.map((column) => [column.slug, column])),
    [backendKanbanColumns],
  )
  const effectiveColumnById = useMemo(() => {
    const map = new Map<number, RecruiterKanbanColumn['slug']>()
    for (const card of kanbanCards) {
      const columnSlug = kanbanStatusOverrides[card.id] || buildCandidateSurfaceState(card).kanbanColumnSlug
      map.set(card.id, columnSlug)
    }
    return map
  }, [kanbanCards, kanbanStatusOverrides])
  const kanbanColumns = useMemo(
    () =>
      backendKanbanColumns.map((column) => {
        const cards = kanbanCards.filter((card) => {
          const currentColumn = effectiveColumnById.get(card.id) || 'incoming'
          return currentColumn === column.slug
        })
        return {
          ...column,
          total: cards.length,
          candidates: cards,
        }
      }),
    [backendKanbanColumns, kanbanCards, effectiveColumnById],
  )
  const calendarDays = data?.views?.calendar?.days || []
  const pipelineOptions = data?.pipeline_options || [
    { slug: 'main', label: 'Основной канбан' },
    { slug: 'interview', label: 'Интервью' },
    { slug: 'intro_day', label: 'Ознакомительный день' },
  ]
  const hasActiveFilters = Boolean(search.trim() || stateFilter || (view !== 'kanban' && pipeline !== 'interview'))
  const firstRenderAnimation = !hasAnimatedLists && !prefersReducedMotion
  const listAnimationKey = [search, stateFilter, pipeline, view, page, perPage].join('|')
  const kanbanAnimationKey = [
    search,
    stateFilter,
    pipeline,
    kanbanColumns.map((column) => `${column.slug}:${column.candidates.length}`).join(','),
  ].join('|')
  const activeFilterBadges = [
    search.trim() ? `Поиск: ${search.trim()}` : null,
    stateFilter ? `Этап: ${stateOptions.find((option) => option.value === stateFilter)?.label || stateFilter}` : null,
    view !== 'kanban' && pipeline !== 'interview'
      ? `Воронка: ${pipelineOptions.find((option) => option.slug === pipeline)?.label || pipeline}`
      : null,
  ].filter(Boolean) as string[]

  const resetFilters = () => {
    setSearch('')
    setStateFilter('')
    setPipeline('interview')
    setPage(1)
  }

  useEffect(() => {
    setHasAnimatedLists(true)
  }, [])

  useEffect(() => {
    setSelectedCandidateIds((prev) => {
      const next = prev.filter((id) => listCards.some((candidate) => candidate.id === id))
      if (next.length === prev.length && next.every((id, index) => id === prev[index])) {
        return prev
      }
      return next
    })
  }, [listCards])

  useEffect(() => {
    if (!isMobile) return
    if (view === 'calendar') setView('list')
  }, [isMobile, view])

  const deleteCandidate = useCallback((candidate: { id: number; fio?: string | null }) => {
    const name = candidate.fio?.trim() || `#${candidate.id}`
    const confirmed = window.confirm(`Удалить кандидата ${name}? Действие необратимо.`)
    if (!confirmed) return
    setDeletingCandidateId(candidate.id)
    deleteCandidateMutate(candidate.id)
  }, [deleteCandidateMutate])

  const selectedCandidates = useMemo(
    () => listCards.filter((candidate) => selectedCandidateIds.includes(candidate.id)),
    [listCards, selectedCandidateIds],
  )
  const workQueueSummary = useMemo(() => {
    const order = ['incoming', 'today', 'awaiting_recruiter', 'awaiting_candidate', 'blocked', 'closed']
    const queueMap = new Map<string, { label: string; count: number }>()

    for (const candidate of listCards) {
      const state = buildCandidateSurfaceState(candidate)
      const current = queueMap.get(state.worklistBucket)
      if (current) {
        current.count += 1
        continue
      }
      queueMap.set(state.worklistBucket, {
        label: state.worklistBucketLabel,
        count: 1,
      })
    }

    return Array.from(queueMap.entries())
      .sort((left, right) => {
        const leftOrder = order.indexOf(left[0])
        const rightOrder = order.indexOf(right[0])
        if (leftOrder !== rightOrder) return (leftOrder === -1 ? Number.MAX_SAFE_INTEGER : leftOrder) - (rightOrder === -1 ? Number.MAX_SAFE_INTEGER : rightOrder)
        return right[1].count - left[1].count
      })
      .map(([, value]) => value)
  }, [listCards])

  const toggleCandidateSelected = useCallback((candidateId: number) => {
    setSelectedCandidateIds((prev) => (
      prev.includes(candidateId)
        ? prev.filter((id) => id !== candidateId)
        : [...prev, candidateId]
    ))
  }, [])

  const clearSelectedCandidates = useCallback(() => {
    setSelectedCandidateIds([])
  }, [])

  const openSelectedCandidates = useCallback(() => {
    if (typeof window === 'undefined') return
    for (const candidate of selectedCandidates) {
      window.open(`/app/candidates/${candidate.id}`, '_blank', 'noopener,noreferrer')
    }
  }, [selectedCandidates])

  const copySelectedCandidateLinks = useCallback(async () => {
    if (typeof window === 'undefined' || !navigator.clipboard?.writeText) return
    const origin = window.location.origin
    const payload = selectedCandidates
      .map((candidate) => `${candidate.fio || `Кандидат #${candidate.id}`}: ${origin}/app/candidates/${candidate.id}`)
      .join('\n')
    await navigator.clipboard.writeText(payload)
  }, [selectedCandidates])

  const handleKanbanDragStart = useCallback((event: DragEvent<HTMLDivElement>) => {
    const rawCandidateId = event.currentTarget.dataset.candidateId
    const candidateId = Number(rawCandidateId)
    if (!Number.isFinite(candidateId)) return
    event.dataTransfer.setData('text/candidate-id', String(candidateId))
    event.dataTransfer.effectAllowed = 'move'
    setDraggingCardId(candidateId)
    setKanbanMoveError(null)
  }, [])

  const handleKanbanDragEnd = useCallback(() => {
    setDraggingCardId(null)
    setDragOverColumn(null)
  }, [])

  const handleKanbanDragEnter = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    const columnSlug = event.currentTarget.dataset.columnSlug
    if (columnSlug) setDragOverColumn(columnSlug)
  }, [])

  const handleKanbanDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    const columnSlug = event.currentTarget.dataset.columnSlug
    if (columnSlug) setDragOverColumn(columnSlug)
  }, [])

  const handleKanbanDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    const columnSlug = event.currentTarget.dataset.columnSlug
    if (!columnSlug) return
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setDragOverColumn((current) => (current === columnSlug ? null : current))
    }
  }, [])

  const handleKanbanDrop = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    const targetSlug = event.currentTarget.dataset.columnSlug as RecruiterKanbanColumn['slug'] | undefined
    if (!targetSlug) {
      setDragOverColumn(null)
      setDraggingCardId(null)
      return
    }
    const targetColumn = kanbanColumnsBySlug.get(targetSlug)
    const rawCandidateId = event.dataTransfer.getData('text/candidate-id')
    const candidateId = Number(rawCandidateId)
    setDragOverColumn(null)
    setDraggingCardId(null)
    if (!targetColumn || !Number.isFinite(candidateId)) return
    if (targetColumn.droppable === false) return

    const previousStatus = effectiveColumnById.get(candidateId) || null
    if (!previousStatus) return

    if (targetColumn.slug === previousStatus) {
      return
    }

    setKanbanStatusOverrides((prev) => ({
      ...prev,
      [candidateId]: targetColumn.slug as RecruiterKanbanColumn['slug'],
    }))
    moveKanbanCandidateMutate({
      candidateId,
      targetColumn: targetColumn.slug as RecruiterKanbanColumn['slug'],
      previousStatus,
    })
  }, [effectiveColumnById, kanbanColumnsBySlug, moveKanbanCandidateMutate])

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page app-page app-page--ops candidates-page">
        <header className="glass glass--elevated page-header page-header--row app-page__hero">
          <div className="page-header__content">
            <h1 className="title">Кандидаты</h1>
            <p className="subtitle">Операционная база кандидатов с быстрым переходом между списком, канбаном и календарём.</p>
          </div>
          <Link to="/app/candidates/new" className="ui-btn ui-btn--primary" data-testid="candidates-create-btn">+ Новый кандидат</Link>
        </header>

        <section className="glass page-section app-page__section">
          <div className="filter-bar ui-filter candidates-filter-bar" data-testid="candidates-filter-bar">
            <input
              placeholder="Поиск по ФИО, городу, TG..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              className="filter-bar__search candidates-filter-bar__search"
            />
            <select
              aria-label="Этап кандидата"
              value={stateFilter}
              onChange={(e) => { setStateFilter(e.target.value); setPage(1) }}
            >
              {stateOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <select
              aria-label="Воронка"
              value={pipeline}
              onChange={(e) => { setPipeline(e.target.value); setPage(1) }}
              disabled={view === 'kanban'}
            >
              {pipelineOptions.map((opt) => (
                <option key={opt.slug} value={opt.slug}>{opt.label}</option>
              ))}
            </select>
            <div className="view-toggle" data-testid="candidates-view-switcher">
              <button className={`ui-btn ui-btn--sm candidates-view-pill ${view === 'list' ? 'ui-btn--primary is-active' : 'ui-btn--ghost'}`} onClick={() => { setView('list'); setPage(1) }} type="button">
                Список
              </button>
              <button className={`ui-btn ui-btn--sm candidates-view-pill ${view === 'kanban' ? 'ui-btn--primary is-active' : 'ui-btn--ghost'}`} onClick={() => { setView('kanban'); setPipeline('main'); setPage(1) }} type="button">
                Канбан
              </button>
              {!isMobile && (
                <button className={`ui-btn ui-btn--sm candidates-view-pill ${view === 'calendar' ? 'ui-btn--primary is-active' : 'ui-btn--ghost'}`} onClick={() => { setView('calendar'); setPage(1) }} type="button">
                  Календарь
                </button>
              )}
            </div>
          </div>

          {activeFilterBadges.length > 0 && (
            <div className="candidates-filter-pills" aria-label="Активные фильтры">
              {activeFilterBadges.map((label) => (
                <span key={label} className="candidates-filter-pill candidates-filter-pill--active">
                  {label}
                </span>
              ))}
              <button type="button" className="candidates-filter-pill" onClick={resetFilters}>
                Сбросить
              </button>
            </div>
          )}

          <div className="glass ai-reco">
            <div className="ai-reco__header">
              <div>
                <div className="ai-reco__title">AI рекомендации</div>
                <div className="subtitle">Подбор кандидатов под критерии города.</div>
              </div>
              <div className="ai-reco__actions">
                <select
                  aria-label="Город для AI рекомендаций"
                  value={aiCityId}
                  onChange={(e) => setAiCityId(e.target.value)}
                >
                  <option value="">Выберите город…</option>
                  {(citiesQuery.data || []).map((c) => (
                    <option key={c.id} value={String(c.id)}>{c.name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="ui-btn ui-btn--ghost ui-btn--sm"
                  disabled={!aiCityId || aiRecoQuery.isFetching}
                  onClick={() => aiRecoQuery.refetch()}
                >
                  {aiRecoQuery.isFetching ? 'Генерация…' : 'Сгенерировать'}
                </button>
                {aiRecoQuery.data && (
                  <span className={`cd-chip cd-chip--small ${aiRecoQuery.data.cached ? '' : 'cd-chip--accent'}`}>
                    {aiRecoQuery.data.cached ? 'Кэш' : 'Новый'}
                  </span>
                )}
              </div>
            </div>

            {aiRecoQuery.isError && (
              <div className="ai-reco__error">
                AI: {(aiRecoQuery.error as Error).message}
              </div>
            )}

            {aiRecoQuery.data && (
              <div className="ai-reco__body">
                {aiRecoQuery.data.notes && <div className="ai-reco__notes">{aiRecoQuery.data.notes}</div>}
                {aiRecoQuery.data.recommended.length === 0 ? (
                  <div className="subtitle">Нет рекомендаций.</div>
                ) : (
                  <div className="ai-reco__list">
                    {aiRecoQuery.data.recommended.map((r) => (
                      <div key={r.candidate_id} className="ai-reco__item glass glass--interactive">
                        <div className="ai-reco__main">
                          <div className="ai-reco__top">
                            <Link
                              to="/app/candidates/$candidateId"
                              params={{ candidateId: String(r.candidate_id) }}
                              className="font-semibold"
                            >
                              Кандидат #{r.candidate_id}
                            </Link>
                            <span className={`ai-reco__badge ai-reco__badge--${r.fit_level || 'unknown'}`}>
                              {r.fit_score != null ? `${r.fit_score}/100` : '—'}
                            </span>
                          </div>
                          <div className="ai-reco__reason">{r.reason}</div>
                          {r.suggested_next_step && <div className="ai-reco__next">{r.suggested_next_step}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="pagination app-page__toolbar">
            <span className="pagination__info">Всего: {total}</span>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Назад</button>
            <span className="pagination__info">{page} / {pagesTotal}</span>
            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled={page >= pagesTotal} onClick={() => setPage(page + 1)}>Вперёд →</button>
            <select
              aria-label="Кандидатов на странице"
              value={perPage}
              onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1) }}
            >
              {[10, 20, 50, 100].map((v) => <option key={v} value={v}>{v} на стр.</option>)}
            </select>
          </div>

          {isLoading && <p className="text-muted">Загрузка…</p>}
          {isError && <ApiErrorBanner error={error} title="Не удалось загрузить кандидатов" />}
          {deleteCandidateError && <ApiErrorBanner error={deleteCandidateError} title="Не удалось удалить кандидата" />}
          {kanbanMoveBlockingState && (
            <RecruiterRiskBanner
              level={
                kanbanMoveBlockingState.severity === 'warning'
                  ? (kanbanMoveBlockingState.manual_resolution_required ? 'repair' : 'warning')
                  : 'blocker'
              }
              title="Перемещение остановлено"
              message={kanbanMoveBlockingMessage || 'Колонка недоступна для этого кандидата.'}
              count={kanbanMoveBlockingState.issue_codes?.length || undefined}
              className="candidates-kanban-feedback"
            />
          )}
          {kanbanMoveError && <ApiErrorBanner error={kanbanMoveError} title="Не удалось переместить кандидата в канбане" />}
          {view === 'list' && workQueueSummary.length > 0 && (
            <div data-testid="candidates-work-queues" style={{ marginTop: 'var(--space-3)' }}>
              <div className="subtitle">Очереди на странице</div>
              <div className="candidates-filter-pills">
                {workQueueSummary.map((queue) => (
                  <div key={queue.label} className="candidates-filter-pill">
                    <strong>{queue.count}</strong>
                    <span>{queue.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {view === 'list' && selectedCandidateIds.length > 0 && (
            <div className="glass candidates-selection-bar" data-testid="candidates-selection-bar">
              <div className="candidates-selection-bar__summary">
                <strong>{selectedCandidateIds.length}</strong>
                <span>выбрано для безопасного триажа</span>
              </div>
              <div className="candidates-selection-bar__actions">
                <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={openSelectedCandidates}>
                  Открыть профили
                </button>
                <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => { void copySelectedCandidateLinks() }}>
                  Скопировать ссылки
                </button>
                <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={clearSelectedCandidates}>
                  Очистить
                </button>
              </div>
            </div>
          )}
          {data && listCards.length === 0 && (
            <div className="empty-state" data-testid="candidates-empty-state">
              <p className="empty-state__text">
                {hasActiveFilters
                  ? 'Кандидаты не найдены по текущим фильтрам.'
                  : 'Список кандидатов пуст. Добавьте первого кандидата, чтобы начать работу.'}
              </p>
              <div className="toolbar">
                {hasActiveFilters && (
                  <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={resetFilters}>
                    Сбросить фильтры
                  </button>
                )}
                <Link to="/app/candidates/new" className="ui-btn ui-btn--primary ui-btn--sm">
                  + Новый кандидат
                </Link>
              </div>
            </div>
          )}
          {view === 'calendar' && (
            <div className="page-section__content">
              <div className="filter-bar ui-filter">
                <label className="form-group">
                  <span className="form-group__label">От</span>
                  <input type="date" value={calendarFrom} onChange={(e) => setCalendarFrom(e.target.value)} />
                </label>
                <label className="form-group">
                  <span className="form-group__label">До</span>
                  <input type="date" value={calendarTo} onChange={(e) => setCalendarTo(e.target.value)} />
                </label>
              </div>
              {calendarDays.length === 0 && (
                <div className="empty-state">
                  <p className="empty-state__text">Нет событий за выбранный период.</p>
                </div>
              )}
              {calendarDays.length > 0 && (
                <div className="page-section__content">
                  {calendarDays.map((day) => (
                    <article key={day.date} className="glass glass--subtle list-item">
                      <div className="list-item__header">
                        <strong className="list-item__title">{day.label}</strong>
                        <span className="text-muted">Событий: {day.events.length}</span>
                      </div>
                      <div className="page-section__content">
                        {day.events.map((ev, idx) => (
                          <div key={`${day.date}-${idx}`} className="glass glass--interactive list-item list-item--horizontal">
                            <div>
                              <div className="font-semibold">{ev.candidate?.fio || 'Кандидат'}</div>
                              <div className="text-muted text-sm">
                                {ev.candidate?.city || '—'} · {ev.candidate?.recruiter?.name || '—'}
                              </div>
                            </div>
                            {ev.candidate?.id ? (
                              <Link to="/app/candidates/$candidateId" params={{ candidateId: String(ev.candidate.id) }} className="ui-btn ui-btn--ghost ui-btn--sm">
                                Открыть →
                              </Link>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}

          {view === 'kanban' && (
            <div className="page-section__content">
              <p className="subtitle">
                Доска показывает только безопасные ручные переходы. Закрытые колонки обновляются системой или следующим допустимым шагом.
              </p>
              <div className="kanban">
                {kanbanColumns.map((col) => {
                  const treatment = describeKanbanColumnTreatment(col)
                  return (
                    <article
                      key={col.slug}
                      className={`glass kanban__column kanban-column ${dragOverColumn === col.slug ? 'kanban-column--drag-over' : ''} ${col.droppable === false ? 'kanban-column--locked' : ''} kanban-column--${treatment.mode}`}
                      data-kanban-column={col.slug}
                    >
                      <RecruiterKanbanColumnHeader
                        icon={col.icon || '•'}
                        label={col.label}
                        count={col.total ?? col.candidates.length}
                        droppable={col.droppable !== false}
                        mode={treatment.mode}
                        helperText={treatment.helperText}
                      />
                    <motion.div
                      key={`${kanbanAnimationKey}-${col.slug}`}
                      className={`kanban__cards ${dragOverColumn === col.slug ? 'kanban__cards--drag-over' : ''}`}
                      data-column-slug={col.slug}
                      initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
                      animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
                      variants={firstRenderAnimation ? stagger(0.03) : undefined}
                      transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
                      onDragEnter={col.droppable === false ? undefined : handleKanbanDragEnter}
                      onDragOver={col.droppable === false ? undefined : handleKanbanDragOver}
                      onDragLeave={col.droppable === false ? undefined : handleKanbanDragLeave}
                      onDrop={col.droppable === false ? undefined : handleKanbanDrop}
                    >
                      {col.candidates.map((card) => (
                        <CandidateKanbanCard
                          key={card.id}
                          card={card}
                          canDelete={
                            isAdmin ||
                            (principalType === 'recruiter' && card.recruiter?.id === profile.data?.principal.id)
                          }
                          isDeleting={deletingCandidateId === card.id && deleteCandidateMutation.isPending}
                          isDragging={draggingCardId === card.id}
                          isMoving={movingCandidateId === card.id && moveKanbanCandidateMutation.isPending}
                          shouldAnimate={firstRenderAnimation}
                          onDeleteCandidate={deleteCandidate}
                          onDragStart={handleKanbanDragStart}
                          onDragEnd={handleKanbanDragEnd}
                        />
                      ))}
                    </motion.div>
                  </article>
                  )
                })}
              </div>
            </div>
          )}

          {view === 'list' && data && listCards.length > 0 && (
            <>
              {isMobile && (
                <div className="mobile-card-list" data-testid="candidates-mobile-list">
                  {listCards.map((c) => {
                      const state = buildCandidateSurfaceState(c)
                      const secondaryStatusLabel = buildSecondaryStatusLabel(state)
                      const recruiterName = c.recruiter?.name || c.recruiter_name || '—'
                    const canDelete =
                      isAdmin ||
                      (principalType === 'recruiter' && c.recruiter_id === profile.data?.principal.id)
                    const isDeleting = deletingCandidateId === c.id && deleteCandidateMutation.isPending
                    const isSelected = selectedCandidateIds.includes(c.id)
                    return (
                      <article
                        key={`mobile-candidate-${c.id}`}
                        className={`candidate-mobile-card glass glass--subtle ${isSelected ? 'candidate-mobile-card--selected' : ''}`}
                      >
                        <div className="candidate-mobile-card__top">
                          <label className="candidate-select">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleCandidateSelected(c.id)}
                              aria-label={`Выбрать ${c.fio || `кандидата ${c.id}`}`}
                            />
                          </label>
                          <CandidateIdentityBlock
                            title={(
                              <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} className="candidate-row__name">
                                {c.fio || '—'}
                              </Link>
                            )}
                            subtitle={c.city || '—'}
                            compact
                            aside={(
                              <span className={`candidate-score candidate-score--${candidateScoreTone(c.average_score)}`}>
                                {typeof c.average_score === 'number' ? `${Math.round(c.average_score)}%` : '—'}
                              </span>
                            )}
                            className="candidate-mobile-card__identity"
                          />
                        </div>
                        <div className="text-muted text-sm">
                          {isAdmin ? `Ответственный: ${recruiterName}` : 'Рабочая карточка для быстрого разбора'}
                        </div>
                        <RecruiterActionBlock
                          label={state.nextActionLabel || 'Откройте профиль'}
                          explanation={state.nextActionExplanation || 'Следующий шаг появится после открытия профиля кандидата.'}
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
                            recoveryHint={state.riskRecoveryHint}
                            count={state.riskCount > 0 ? state.riskCount : undefined}
                            compact
                          />
                        ) : null}
                        <div className="candidate-mobile-card__meta">
                          {secondaryStatusLabel ? <span className="candidate-row__secondary">{secondaryStatusLabel}</span> : null}
                          <span className="candidate-row__date">{formatCandidateDate(resolveCandidateDate(c))}</span>
                        </div>
                        <div className="toolbar toolbar--compact">
                          <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} className="ui-btn ui-btn--ghost ui-btn--sm">
                            Открыть
                          </Link>
                          {c.telegram_id ? (
                            <a href={`https://t.me/${c.telegram_id}`} target="_blank" rel="noopener" className="ui-btn ui-btn--ghost ui-btn--sm">
                              Telegram
                            </a>
                          ) : (
                            <button className="ui-btn ui-btn--ghost ui-btn--sm" disabled>
                              Telegram
                            </button>
                          )}
                          {canDelete && (
                            <button
                              type="button"
                              className="ui-btn ui-btn--danger ui-btn--sm"
                              onClick={() => deleteCandidate(c)}
                              disabled={isDeleting}
                            >
                              {isDeleting ? 'Удаление…' : 'Удалить'}
                            </button>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
              <div className="data-table-wrapper candidates-table-wrapper">
                <table className="data-table candidates-table" data-testid="candidates-table">
                  <thead className="candidates-thead">
                    <tr>
                      <th aria-label="Выбор кандидата" />
                      <th>Кандидат</th>
                      <th>Следующий шаг</th>
                      <th>Контекст</th>
                      <th>Риски и действия</th>
                    </tr>
                  </thead>
                  <motion.tbody
                    key={listAnimationKey}
                    initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
                    animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
                    variants={firstRenderAnimation ? stagger(0.03) : undefined}
                    transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
                  >
                    {listCards.map((c) => {
                      const state = buildCandidateSurfaceState(c)
                      const secondaryStatusLabel = buildSecondaryStatusLabel(state)
                      const recruiterName = c.recruiter?.name || c.recruiter_name || '—'
                      const canDelete =
                        isAdmin ||
                        (principalType === 'recruiter' && c.recruiter_id === profile.data?.principal.id)
                      const isDeleting = deletingCandidateId === c.id && deleteCandidateMutation.isPending
                      const scoreTone = candidateScoreTone(c.average_score)
                      const candidateDate = formatCandidateDate(resolveCandidateDate(c))
                      const isSelected = selectedCandidateIds.includes(c.id)
                      return (
                        <motion.tr
                          key={c.id}
                          className={`candidate-row ${isSelected ? 'candidate-row--selected' : ''}`}
                          variants={firstRenderAnimation ? listItem : undefined}
                        >
                          <td className="candidate-row__cell candidate-row__cell--select">
                            <label className="candidate-select">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => toggleCandidateSelected(c.id)}
                                aria-label={`Выбрать ${c.fio || `кандидата ${c.id}`}`}
                              />
                            </label>
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--identity">
                            <CandidateIdentityBlock
                              title={(
                                <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} className="candidate-row__name">
                                  {c.fio || '—'}
                                </Link>
                              )}
                              subtitle={c.city || '—'}
                              meta={c.telegram_id ? (
                                <a href={`https://t.me/${c.telegram_id}`} target="_blank" rel="noopener" className="candidate-row__link">
                                  @{String(c.telegram_id).replace(/^@/, '')}
                                </a>
                              ) : null}
                              className="candidate-row__identity"
                            />
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--action">
                            <RecruiterActionBlock
                              label={state.nextActionLabel || 'Откройте профиль'}
                              explanation={state.nextActionExplanation || 'Следующий шаг появится после открытия профиля кандидата.'}
                              tone={state.nextActionTone}
                              enabled={state.nextActionEnabled}
                              compact
                            />
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--context">
                            <RecruiterStateContext
                              bucketLabel={state.worklistBucketLabel}
                              contextLine={state.stateContextLine}
                              schedulingLine={state.schedulingContextLine}
                              compact
                            />
                            <div className="candidate-row__secondary candidate-row__meta-line">
                              {secondaryStatusLabel ? <span>{secondaryStatusLabel}</span> : null}
                              <span>{candidateDate}</span>
                              {isAdmin ? <span>{recruiterName}</span> : null}
                            </div>
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--signals">
                            {state.riskLevel && state.riskTitle && state.riskMessage ? (
                              <RecruiterRiskBanner
                                level={state.riskLevel}
                                title={state.riskTitle}
                                message={state.riskMessage}
                                recoveryHint={state.riskRecoveryHint}
                                count={state.riskCount > 0 ? state.riskCount : undefined}
                                compact
                              />
                            ) : (
                              <div className="candidate-row__secondary candidate-row__healthy">Без блокеров</div>
                            )}
                            <div className="candidate-row__signals-footer">
                              <span className={`candidate-score candidate-score--${scoreTone}`}>
                                {typeof c.average_score === 'number' ? `${Math.round(c.average_score)}%` : '—'}
                              </span>
                              <div className="candidate-row__actions">
                              <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} className="ui-btn ui-btn--ghost ui-btn--sm">
                                Открыть
                              </Link>
                              {canDelete ? (
                                <button
                                  type="button"
                                  className="ui-btn ui-btn--danger ui-btn--sm"
                                  onClick={() => deleteCandidate(c)}
                                  disabled={isDeleting}
                                >
                                  {isDeleting ? 'Удаление…' : 'Удалить'}
                                </button>
                              ) : (
                                <span className="candidate-row__secondary">—</span>
                              )}
                            </div>
                            </div>
                          </td>
                        </motion.tr>
                      )
                    })}
                  </motion.tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
