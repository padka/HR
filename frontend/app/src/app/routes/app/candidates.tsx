import { Link } from '@tanstack/react-router'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { memo, useCallback, useEffect, useMemo, useState, type DragEvent } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { apiFetch } from '@/api/client'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { useProfile } from '@/app/hooks/useProfile'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import '@/theme/pages/candidates.css'
import { fadeIn, listItem, stagger } from '@/shared/motion'

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

type Candidate = {
  id: number
  fio?: string | null
  city?: string | null
  status?: { slug?: string; label?: string; tone?: string }
  telegram_id?: string | null
  recruiter_id?: number | null
  recruiter_name?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
  average_score?: number | null
  tests_total?: number | null
  primary_event_at?: string | null
  latest_message?: { created_at?: string | null } | null
  latest_slot?: { start_utc?: string | null } | null
  upcoming_slot?: { start_utc?: string | null } | null
}

type CandidateCard = {
  id: number
  fio?: string | null
  city?: string | null
  telegram_id?: number | string | null
  status?: { slug?: string; label?: string; tone?: string; icon?: string }
  stage?: string | null
  primary_event_at?: string | null
  recruiter?: { id?: number | null; name?: string | null } | null
  average_score?: number | null
  latest_slot?: { start_utc?: string | null } | null
  upcoming_slot?: { start_utc?: string | null } | null
}

type KanbanWorkflowColumn = {
  slug: string
  label: string
  icon: string
  targetStatus: string
  sourceStatuses: string[]
}

type CalendarDay = {
  date: string
  label: string
  events: Array<{
    candidate?: CandidateCard
    slot?: { start_utc?: string | null }
    status?: { slug?: string; label?: string; tone?: string }
  }>
  totals?: Record<string, number>
}

type CandidateListPayload = {
  items: Candidate[]
  total: number
  page: number
  pages_total: number
  filters?: Record<string, unknown>
  pipeline?: string
  pipeline_options?: Array<{ slug: string; label: string }>
  views?: {
    kanban?: { columns: Array<{ slug: string; label: string; candidates: CandidateCard[] }> }
    calendar?: { days: CalendarDay[] }
    candidates?: CandidateCard[]
  }
}

type CandidateKanbanMoveResponse = {
  ok: boolean
  message?: string
  status?: string
  candidate_id?: number
}

type KanbanMoveVariables = {
  candidateId: number
  targetStatus: string
  previousStatus?: string | null
}

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы' },
  { value: 'hired', label: '🎉 Закреплён' },
  { value: 'not_hired', label: '⚠️ Не закреплён' },
  { value: 'waiting_slot', label: '⏳ Ожидает слот' },
  { value: 'slot_pending', label: '⌛ Ожидает подтверждения' },
  { value: 'slot_booked', label: '📅 Согласован слот' },
  { value: 'interview_passed', label: '✅ Интервью пройдено' },
  { value: 'test2_passed', label: '✅ Тест 2 пройден' },
  { value: 'interview_declined', label: '❌ Отказ' },
]

const KANBAN_INCOMING_SOURCE_STATUSES = [
  'new',
  'lead',
  'contacted',
  'invited',
  'test1_completed',
  'waiting_slot',
  'stalled_waiting_slot',
]

const KANBAN_WORKFLOW_COLUMNS: KanbanWorkflowColumn[] = [
  {
    slug: 'incoming',
    label: 'Входящие',
    icon: '📥',
    targetStatus: 'waiting_slot',
    sourceStatuses: KANBAN_INCOMING_SOURCE_STATUSES,
  },
  {
    slug: 'slot_pending',
    label: 'На согласовании',
    icon: '🕐',
    targetStatus: 'slot_pending',
    sourceStatuses: ['slot_pending'],
  },
  {
    slug: 'interview_scheduled',
    label: 'Назначено собеседование',
    icon: '📅',
    targetStatus: 'interview_scheduled',
    sourceStatuses: ['interview_scheduled'],
  },
  {
    slug: 'interview_confirmed',
    label: 'Подтвердил собеседование',
    icon: '✅',
    targetStatus: 'interview_confirmed',
    sourceStatuses: ['interview_confirmed'],
  },
  {
    slug: 'test2_sent',
    label: 'Отправлен тест 2',
    icon: '📨',
    targetStatus: 'test2_sent',
    sourceStatuses: ['test2_sent'],
  },
  {
    slug: 'test2_completed',
    label: 'Прошел тест 2',
    icon: '🧪',
    targetStatus: 'test2_completed',
    sourceStatuses: ['test2_completed'],
  },
  {
    slug: 'intro_day_scheduled',
    label: 'Ознакомительный день назначен',
    icon: '📆',
    targetStatus: 'intro_day_scheduled',
    sourceStatuses: ['intro_day_scheduled'],
  },
  {
    slug: 'intro_day_confirmed_preliminary',
    label: 'Предварительно подтвердил ОД',
    icon: '👍',
    targetStatus: 'intro_day_confirmed_preliminary',
    sourceStatuses: ['intro_day_confirmed_preliminary'],
  },
  {
    slug: 'intro_day_confirmed_day_of',
    label: 'Подтвердил ОД',
    icon: '🎯',
    targetStatus: 'intro_day_confirmed_day_of',
    sourceStatuses: ['intro_day_confirmed_day_of'],
  },
]

const KANBAN_WORKFLOW_COLUMNS_BY_SLUG = new Map(
  KANBAN_WORKFLOW_COLUMNS.map((column) => [column.slug, column]),
)

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

type CandidateKanbanCardProps = {
  card: CandidateCard
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
        <div className="kanban-card__identity">
          <div className="kanban-card__name">{card.fio || '—'}</div>
          <div className="kanban-card__meta">{card.city || '—'}</div>
        </div>
        {typeof card.average_score === 'number' ? (
          <span className={`candidate-score candidate-score--${scoreTone}`}>{Math.round(card.average_score)}%</span>
        ) : null}
      </div>
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
      status: params.get('status') ?? '',
      pipeline: params.get('pipeline') ?? 'interview',
    }
  }, [])

  const [search, setSearch] = useState(initialFilters.search)
  const [status, setStatus] = useState(initialFilters.status)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [pipeline, setPipeline] = useState(initialFilters.pipeline)
  const [view, setView] = useState<'list' | 'kanban' | 'calendar'>('list')
  const [aiCityId, setAiCityId] = useState('')
  const [deletingCandidateId, setDeletingCandidateId] = useState<number | null>(null)
  const [deleteCandidateError, setDeleteCandidateError] = useState<Error | null>(null)
  const [kanbanMoveError, setKanbanMoveError] = useState<Error | null>(null)
  const [kanbanStatusOverrides, setKanbanStatusOverrides] = useState<Record<number, string>>({})
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
  if (status) params.set('status', status)
  if (pipelineForRequest) params.set('pipeline', pipelineForRequest)
  params.set('page', String(page))
  params.set('per_page', String(perPage))
  if (view === 'calendar') {
    params.set('calendar_mode', 'day')
    params.set('date_from', calendarFrom)
    params.set('date_to', calendarTo)
  }

  const { data, isLoading, isError, error } = useQuery<CandidateListPayload>({
    queryKey: ['candidates', { search, status, page, perPage, pipeline: pipelineForRequest, view, calendarFrom, calendarTo }],
    queryFn: () => apiFetch(`/candidates?${params.toString()}`),
  })

  const citiesQuery = useQuery<CityOption[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
    staleTime: 60_000,
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
    mutationFn: async ({ candidateId, targetStatus }: KanbanMoveVariables) =>
      apiFetch<CandidateKanbanMoveResponse>(`/candidates/${candidateId}/kanban-status`, {
        method: 'POST',
        body: JSON.stringify({ target_status: targetStatus }),
      }),
    onMutate: ({ candidateId }: KanbanMoveVariables) => {
      setKanbanMoveError(null)
      setMovingCandidateId(candidateId)
    },
    onSuccess: async (_data, variables) => {
      setKanbanMoveError(null)
      setKanbanStatusOverrides((prev) => {
        const next = { ...prev }
        delete next[variables.candidateId]
        return next
      })
      await queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
    onError: (error: Error, variables) => {
      setKanbanMoveError(error)
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
  const kanbanCards = useMemo(
    () => data?.views?.candidates ?? [],
    [data?.views?.candidates],
  )
  const effectiveStatusById = useMemo(() => {
    const map = new Map<number, string>()
    for (const card of kanbanCards) {
      const statusSlug = kanbanStatusOverrides[card.id] || card.status?.slug || ''
      map.set(card.id, statusSlug)
    }
    return map
  }, [kanbanCards, kanbanStatusOverrides])
  const kanbanColumns = useMemo(
    () =>
      KANBAN_WORKFLOW_COLUMNS.map((column) => {
        const cards = kanbanCards.filter((card) => {
          const currentStatus = effectiveStatusById.get(card.id) || ''
          return column.sourceStatuses.includes(currentStatus)
        })
        return {
          ...column,
          total: cards.length,
          candidates: cards,
        }
      }),
    [kanbanCards, effectiveStatusById],
  )
  const calendarDays = data?.views?.calendar?.days || []
  const pipelineOptions = data?.pipeline_options || [
    { slug: 'main', label: 'Основной канбан' },
    { slug: 'interview', label: 'Интервью' },
    { slug: 'intro_day', label: 'Ознакомительный день' },
  ]
  const hasActiveFilters = Boolean(search.trim() || status || (view !== 'kanban' && pipeline !== 'interview'))
  const firstRenderAnimation = !hasAnimatedLists && !prefersReducedMotion
  const listAnimationKey = [search, status, pipeline, view, page, perPage].join('|')
  const kanbanAnimationKey = [
    search,
    status,
    pipeline,
    kanbanColumns.map((column) => `${column.slug}:${column.candidates.length}`).join(','),
  ].join('|')
  const activeFilterBadges = [
    search.trim() ? `Поиск: ${search.trim()}` : null,
    status ? `Статус: ${STATUS_OPTIONS.find((option) => option.value === status)?.label || status}` : null,
    view !== 'kanban' && pipeline !== 'interview'
      ? `Воронка: ${pipelineOptions.find((option) => option.slug === pipeline)?.label || pipeline}`
      : null,
  ].filter(Boolean) as string[]

  const resetFilters = () => {
    setSearch('')
    setStatus('')
    setPipeline('interview')
    setPage(1)
  }

  useEffect(() => {
    setHasAnimatedLists(true)
  }, [])

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
    const targetSlug = event.currentTarget.dataset.columnSlug || ''
    const targetColumn = KANBAN_WORKFLOW_COLUMNS_BY_SLUG.get(targetSlug)
    const rawCandidateId = event.dataTransfer.getData('text/candidate-id')
    const candidateId = Number(rawCandidateId)
    setDragOverColumn(null)
    setDraggingCardId(null)
    if (!targetColumn || !Number.isFinite(candidateId)) return

    const previousStatus = effectiveStatusById.get(candidateId) || null
    if (!previousStatus) return

    if (
      targetColumn.slug === 'incoming' &&
      KANBAN_INCOMING_SOURCE_STATUSES.includes(previousStatus)
    ) {
      return
    }
    if (targetColumn.targetStatus === previousStatus) {
      return
    }

    setKanbanStatusOverrides((prev) => ({
      ...prev,
      [candidateId]: targetColumn.targetStatus,
    }))
    moveKanbanCandidateMutate({
      candidateId,
      targetStatus: targetColumn.targetStatus,
      previousStatus,
    })
  }, [effectiveStatusById, moveKanbanCandidateMutate])

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
              aria-label="Статус кандидата"
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1) }}
            >
              {STATUS_OPTIONS.map((opt) => (
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
          {kanbanMoveError && <ApiErrorBanner error={kanbanMoveError} title="Не удалось переместить кандидата в канбане" />}
          {data && data.items.length === 0 && (
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
                Перетаскивайте карточки между этапами. Канбан зафиксирован на основном сценарии из 9 статусов.
              </p>
              <div className="kanban">
                {kanbanColumns.map((col) => (
                  <article
                    key={col.slug}
                    className={`glass kanban__column kanban-column ${dragOverColumn === col.slug ? 'kanban-column--drag-over' : ''}`}
                    data-kanban-column={col.slug}
                  >
                    <div className="kanban__header kanban-column-header">
                      <span className="kanban__title">{col.icon} {col.label}</span>
                      <span className="kanban__count kanban-column-count">{col.total ?? col.candidates.length}</span>
                    </div>
                    <motion.div
                      key={`${kanbanAnimationKey}-${col.slug}`}
                      className={`kanban__cards ${dragOverColumn === col.slug ? 'kanban__cards--drag-over' : ''}`}
                      data-column-slug={col.slug}
                      initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
                      animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
                      variants={firstRenderAnimation ? stagger(0.03) : undefined}
                      transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
                      onDragEnter={handleKanbanDragEnter}
                      onDragOver={handleKanbanDragOver}
                      onDragLeave={handleKanbanDragLeave}
                      onDrop={handleKanbanDrop}
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
                ))}
              </div>
            </div>
          )}

          {view === 'list' && data && data.items.length > 0 && (
            <>
              {isMobile && (
                <div className="mobile-card-list" data-testid="candidates-mobile-list">
                  {data.items.map((c) => {
                    const tone = c.status?.tone
                    const recruiterName = c.recruiter?.name || c.recruiter_name || '—'
                    const canDelete =
                      isAdmin ||
                      (principalType === 'recruiter' && c.recruiter_id === profile.data?.principal.id)
                    const isDeleting = deletingCandidateId === c.id && deleteCandidateMutation.isPending
                    return (
                      <article key={`mobile-candidate-${c.id}`} className="candidate-mobile-card glass glass--subtle">
                        <div className="list-item__header">
                          <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} className="candidate-row__name">
                            {c.fio || '—'}
                          </Link>
                          <span className={`status-badge status-badge--${tone || 'muted'}`}>
                            {c.status?.label || c.status?.slug || '—'}
                          </span>
                        </div>
                        <div className="text-muted text-sm">
                          {c.city || '—'}{isAdmin ? ` · ${recruiterName}` : ''}
                        </div>
                        <div className="candidate-mobile-card__meta">
                          <span className={`candidate-score candidate-score--${candidateScoreTone(c.average_score)}`}>
                            {typeof c.average_score === 'number' ? `${Math.round(c.average_score)}%` : '—'}
                          </span>
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
                      <th>Кандидат</th>
                      <th>Статус</th>
                      <th>Score</th>
                      {isAdmin && <th>Рекрутёр</th>}
                      <th>Дата</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <motion.tbody
                    key={listAnimationKey}
                    initial={prefersReducedMotion ? false : firstRenderAnimation ? 'initial' : { opacity: 0 }}
                    animate={prefersReducedMotion ? undefined : firstRenderAnimation ? 'animate' : { opacity: 1 }}
                    variants={firstRenderAnimation ? stagger(0.03) : undefined}
                    transition={prefersReducedMotion || firstRenderAnimation ? undefined : fadeIn.transition}
                  >
                    {data.items.map((c) => {
                      const tone = c.status?.tone
                      const recruiterName = c.recruiter?.name || c.recruiter_name || '—'
                      const canDelete =
                        isAdmin ||
                        (principalType === 'recruiter' && c.recruiter_id === profile.data?.principal.id)
                      const isDeleting = deletingCandidateId === c.id && deleteCandidateMutation.isPending
                      const scoreTone = candidateScoreTone(c.average_score)
                      const candidateDate = formatCandidateDate(resolveCandidateDate(c))
                      return (
                        <motion.tr key={c.id} className="candidate-row" variants={firstRenderAnimation ? listItem : undefined}>
                          <td className="candidate-row__cell candidate-row__cell--identity">
                            <div className="candidate-row__identity">
                              <Link to="/app/candidates/$candidateId" params={{ candidateId: String(c.id) }} className="candidate-row__name">
                                {c.fio || '—'}
                              </Link>
                              <div className="candidate-row__secondary">
                                {c.city || '—'}
                                {c.telegram_id ? (
                                  <>
                                    {' · '}
                                    <a href={`https://t.me/${c.telegram_id}`} target="_blank" rel="noopener" className="candidate-row__link">
                                      @{String(c.telegram_id).replace(/^@/, '')}
                                    </a>
                                  </>
                                ) : null}
                              </div>
                            </div>
                          </td>
                          <td className="candidate-row__cell">
                            <span className={`status-badge status-badge--${tone || 'muted'} candidates-status-pill`}>
                              {c.status?.label || c.status?.slug || '—'}
                            </span>
                          </td>
                          <td className="candidate-row__cell">
                            <span className={`candidate-score candidate-score--${scoreTone}`}>
                              {typeof c.average_score === 'number' ? `${Math.round(c.average_score)}%` : '—'}
                            </span>
                          </td>
                          {isAdmin && <td className="candidate-row__cell candidate-row__secondary">{recruiterName}</td>}
                          <td className="candidate-row__cell candidate-row__date">{candidateDate}</td>
                          <td className="candidate-row__cell">
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
