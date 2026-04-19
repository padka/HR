import { Link } from '@tanstack/react-router'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { memo, useCallback, useEffect, useMemo, useState, type DragEvent } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { apiFetch } from '@/api/client'
import { EmptyState, PageLoader } from '@/app/components/AppStates'
import {
  CandidateIdentityBlock,
  RecruiterActionBlock,
  RecruiterKanbanColumnHeader,
  RecruiterRiskBanner,
  RecruiterStateContext,
} from '@/app/components/RecruiterState'
import type {
  CandidateAction,
  CandidateActionResponse,
  CandidateBlockingState,
  CandidateListCard,
  CandidateListPayload,
  CandidateStateFilterOption,
} from '@/api/services/candidates'
import { applyCandidateAction } from '@/api/services/candidates'
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

type CandidateChannelFilter = 'all' | 'telegram' | 'max'
type CandidatePreferredChannelFilter = 'all' | 'telegram' | 'max'
type ActiveFilterKey = 'search' | 'state' | 'channel' | 'preferred-channel' | 'pipeline'

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

function candidateScoreTone(score?: number | null, level?: CandidateListCard['ai_relevance_level']) {
  if (typeof score === 'number') {
    if (score >= 70) return 'success'
    if (score >= 40) return 'warning'
    return 'danger'
  }
  if (level === 'high') return 'success'
  if (level === 'medium') return 'warning'
  if (level === 'low') return 'danger'
  return 'neutral'
}

function resolveCandidateRelevanceScore(candidate: Pick<CandidateListCard, 'ai_relevance_score'>) {
  return typeof candidate.ai_relevance_score === 'number' ? candidate.ai_relevance_score : null
}

function resolveCandidateRelevanceLabel(candidate: Pick<CandidateListCard, 'ai_relevance_score' | 'ai_relevance_level'>) {
  const score = resolveCandidateRelevanceScore(candidate)
  if (typeof score === 'number') return `${Math.round(score)}%`
  if (candidate.ai_relevance_level === 'high') return 'Высокая'
  if (candidate.ai_relevance_level === 'medium') return 'Средняя'
  if (candidate.ai_relevance_level === 'low') return 'Низкая'
  return 'Оценивается'
}

function resolveQuickCandidateAction(candidate: CandidateListCard) {
  const recordState = candidate.lifecycle_summary?.record_state
  const archiveStage = candidate.archive?.stage
  return (candidate.candidate_actions || []).find((action) => {
    if (action.key !== 'restart_test1') return false
    return recordState === 'closed' || Boolean(archiveStage)
  }) || null
}

function resolveQuickCandidateActionLabel(candidate: CandidateListCard, action: CandidateAction) {
  if (action.key === 'restart_test1') {
    return candidate.lifecycle_summary?.record_state === 'closed' || candidate.archive?.stage
      ? 'Вернуть в повторный отбор'
      : 'Перезапустить отбор'
  }
  return action.label || 'Выполнить действие'
}

function candidateActionPendingLabel(action: CandidateAction) {
  if (action.key === 'restart_test1') return 'Возврат…'
  return 'Выполнение…'
}

function formatCandidateDate(value?: string | null) {
  if (!value) return 'Нет активности'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Нет активности'
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

function buildCandidateListStatus(candidate: CandidateListCard, state: ReturnType<typeof buildCandidateSurfaceState>) {
  const primary = state.lifecycle.stage_label?.trim()
    || candidate.archive?.stage_label?.trim()
    || state.statusLabel?.trim()
    || 'Без статуса'

  const secondaryCandidate =
    state.lifecycle.record_state === 'closed'
      ? state.lifecycle.final_outcome_label?.trim() || candidate.archive?.label?.trim() || null
      : candidate.archive?.label?.trim() || null

  const reason = candidate.final_outcome_reason?.trim()
    || candidate.archive?.reason?.trim()
    || null

  return {
    primary,
    secondary: secondaryCandidate && secondaryCandidate !== primary ? secondaryCandidate : null,
    reason,
    tone: state.statusTone,
  }
}

function hasTelegramChannel(candidate: Pick<CandidateListCard, 'telegram_id' | 'telegram_username' | 'telegram_linked_at' | 'linked_channels'>) {
  return Boolean(candidate.linked_channels?.telegram || candidate.telegram_id || candidate.telegram_username || candidate.telegram_linked_at)
}

function hasMaxChannel(candidate: Pick<CandidateListCard, 'max' | 'linked_channels'>) {
  return Boolean(candidate.linked_channels?.max || candidate.max?.linked)
}

function matchesChannelFilter(candidate: CandidateListCard, channelFilter: CandidateChannelFilter) {
  if (channelFilter === 'telegram') return hasTelegramChannel(candidate)
  if (channelFilter === 'max') return hasMaxChannel(candidate)
  return true
}

function resolvePreferredChannel(candidate: Pick<CandidateListCard, 'preferred_channel' | 'linked_channels' | 'max' | 'telegram_id' | 'telegram_username' | 'telegram_linked_at'>) {
  const normalized = String(candidate.preferred_channel || '').trim().toLowerCase()
  if (normalized === 'telegram' || normalized === 'max') return normalized
  if (hasMaxChannel(candidate)) return 'max'
  if (hasTelegramChannel(candidate)) return 'telegram'
  return null
}

function matchesPreferredChannelFilter(candidate: CandidateListCard, preferredChannelFilter: CandidatePreferredChannelFilter) {
  if (preferredChannelFilter === 'all') return true
  return resolvePreferredChannel(candidate) === preferredChannelFilter
}

function resolveCompactMaxState(candidate: CandidateListCard): { label: string; tone: 'info' | 'success' | 'danger' } | null {
  const snapshot = candidate.max_rollout
  if (!snapshot) return null
  if (snapshot.invite_state === 'revoked') return { label: 'Отозвано', tone: 'danger' }
  if (snapshot.launch_state === 'launched') return { label: 'Запущено', tone: 'success' }
  if (snapshot.send_state === 'sent') return { label: 'Отправлено', tone: 'success' }
  if (snapshot.invite_state === 'active') return { label: 'Выдано', tone: 'info' }
  return null
}

function renderCandidateChannelBadges(candidate: CandidateListCard) {
  const telegramLinked = hasTelegramChannel(candidate)
  const maxLinked = hasMaxChannel(candidate)
  const maxState = resolveCompactMaxState(candidate)
  const telegramTitle = telegramLinked ? 'Telegram подключён' : 'Telegram не подключён'
  const maxTitle = maxLinked ? 'MAX подключён' : 'MAX не подключён'
  const telegramHref =
    candidate.telegram_username
      ? `https://t.me/${candidate.telegram_username.replace(/^@/, '')}`
      : candidate.telegram_id
        ? `tg://user?id=${candidate.telegram_id}`
        : null

  return (
    <div className="candidate-row__channels" data-testid="candidate-channel-badges">
      {telegramLinked ? (
        telegramHref ? (
          <a href={telegramHref} target="_blank" rel="noopener" className="candidate-row__channel candidate-row__channel--link" title={telegramTitle}>
            TG
          </a>
        ) : (
          <span className="candidate-row__channel candidate-row__channel--link" title={telegramTitle}>TG</span>
        )
      ) : (
        <span className="candidate-row__channel candidate-row__channel--disabled" title={telegramTitle}>TG</span>
      )}
      {maxLinked ? (
        <span className="candidate-row__channel candidate-row__channel--max" title={maxTitle}>MAX</span>
      ) : (
        <span className="candidate-row__channel candidate-row__channel--disabled" title={maxTitle}>MAX</span>
      )}
      {maxState ? (
        <span
          className={`candidate-row__channel candidate-row__channel--state candidate-row__channel--state-${maxState.tone}`}
          title={`Состояние MAX: ${maxState.label}`}
        >
          {maxState.label}
        </span>
      ) : null}
    </div>
  )
}

type CandidateQuickActionsMenuProps = {
  candidate: CandidateListCard
  canDelete: boolean
  isDeleting: boolean
  isActionPending: boolean
  onDeleteCandidate: (candidate: { id: number; fio?: string | null }) => void
  onQuickAction: (candidate: CandidateListCard, action: CandidateAction) => void
  compact?: boolean
}

function CandidateQuickActionsMenu({
  candidate,
  canDelete,
  isDeleting,
  isActionPending,
  onDeleteCandidate,
  onQuickAction,
  compact = false,
}: CandidateQuickActionsMenuProps) {
  const restoreAction = resolveQuickCandidateAction(candidate)

  return (
    <details className={`candidate-action-menu ${compact ? 'candidate-action-menu--compact' : ''}`}>
      <summary
        className="candidate-action-menu__trigger ui-btn ui-btn--ghost ui-btn--sm"
        aria-label={`Действия для ${candidate.fio || `кандидата ${candidate.id}`}`}
      >
        <span aria-hidden="true">⋯</span>
      </summary>
      <div className="candidate-action-menu__content" role="menu">
        <Link
          to="/app/candidates/$candidateId"
          params={{ candidateId: String(candidate.id) }}
          className="ui-btn ui-btn--secondary ui-btn--sm candidate-action-menu__item"
          role="menuitem"
        >
          Открыть профиль
        </Link>
        {restoreAction ? (
          <button
            type="button"
            className="ui-btn ui-btn--ghost ui-btn--sm candidate-action-menu__item"
            onClick={() => onQuickAction(candidate, restoreAction)}
            disabled={isActionPending}
            role="menuitem"
          >
            {isActionPending ? candidateActionPendingLabel(restoreAction) : resolveQuickCandidateActionLabel(candidate, restoreAction)}
          </button>
        ) : null}
        {canDelete ? (
          <button
            type="button"
            className="ui-btn ui-btn--danger ui-btn--sm candidate-action-menu__item"
            onClick={() => onDeleteCandidate(candidate)}
            disabled={isDeleting}
            role="menuitem"
          >
            {isDeleting ? 'Удаление…' : 'Удалить'}
          </button>
        ) : null}
      </div>
    </details>
  )
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
  const relevanceScore = resolveCandidateRelevanceScore(card)
  const scoreTone = candidateScoreTone(relevanceScore, card.ai_relevance_level)
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
          aside={(
            <span className={`candidate-score candidate-score--${scoreTone}`}>{resolveCandidateRelevanceLabel(card)}</span>
          )}
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
  const [channelFilter, setChannelFilter] = useState<CandidateChannelFilter>('all')
  const [preferredChannelFilter, setPreferredChannelFilter] = useState<CandidatePreferredChannelFilter>('all')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [pipeline, setPipeline] = useState(initialFilters.pipeline)
  const [view, setView] = useState<'list' | 'kanban' | 'calendar'>('list')
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)
  const [aiCityId, setAiCityId] = useState('')
  const [deletingCandidateId, setDeletingCandidateId] = useState<number | null>(null)
  const [actionCandidateId, setActionCandidateId] = useState<number | null>(null)
  const [deleteCandidateError, setDeleteCandidateError] = useState<Error | null>(null)
  const [candidateActionError, setCandidateActionError] = useState<Error | null>(null)
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

  const candidateActionMutation = useMutation({
    mutationFn: async ({ candidateId, actionKey }: { candidateId: number; actionKey: string }) =>
      applyCandidateAction(candidateId, actionKey),
    onMutate: ({ candidateId }: { candidateId: number; actionKey: string }) => {
      setCandidateActionError(null)
      setActionCandidateId(candidateId)
    },
    onSuccess: async (_response: CandidateActionResponse) => {
      setCandidateActionError(null)
      await queryClient.invalidateQueries({ queryKey: ['candidates'] })
    },
    onError: (error: Error) => {
      setCandidateActionError(error)
    },
    onSettled: () => {
      setActionCandidateId(null)
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
  const candidateActionMutate = candidateActionMutation.mutate
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
        telegram_username: item.telegram_username,
        telegram_linked_at: item.telegram_linked_at,
        linked_channels: item.linked_channels,
        max: item.max,
        preferred_channel: item.preferred_channel,
        max_rollout: item.max_rollout,
        status: item.status,
        recruiter_id: item.recruiter_id,
        recruiter_name: item.recruiter_name,
        recruiter: item.recruiter,
        average_score: item.average_score,
        ai_relevance_score: item.ai_relevance_score,
        ai_relevance_level: item.ai_relevance_level,
        ai_relevance_updated_at: item.ai_relevance_updated_at,
        primary_event_at: item.primary_event_at,
        latest_slot: item.latest_slot,
        upcoming_slot: item.upcoming_slot,
        candidate_actions: item.candidate_actions,
      }))
    },
    [data?.items, data?.views?.candidates],
  )
  const kanbanCards = useMemo(
    () => listCards,
    [listCards],
  )
  const visibleListCards = useMemo(
    () => listCards.filter(
      (card) => matchesChannelFilter(card, channelFilter)
        && matchesPreferredChannelFilter(card, preferredChannelFilter),
    ),
    [channelFilter, listCards, preferredChannelFilter],
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
  const hasActiveFilters = Boolean(
    search.trim()
    || stateFilter
    || channelFilter !== 'all'
    || preferredChannelFilter !== 'all'
    || (view !== 'kanban' && pipeline !== 'interview')
  )
  const firstRenderAnimation = !hasAnimatedLists && !prefersReducedMotion
  const listAnimationKey = [search, stateFilter, channelFilter, preferredChannelFilter, pipeline, view, page, perPage].join('|')
  const kanbanAnimationKey = [
    search,
    stateFilter,
    pipeline,
    kanbanColumns.map((column) => `${column.slug}:${column.candidates.length}`).join(','),
  ].join('|')
  const activeFilterBadges = [
    search.trim() ? { key: 'search' as const, label: `Поиск: ${search.trim()}` } : null,
    stateFilter
      ? { key: 'state' as const, label: `Этап: ${stateOptions.find((option) => option.value === stateFilter)?.label || stateFilter}` }
      : null,
    channelFilter !== 'all'
      ? { key: 'channel' as const, label: `Связанные каналы: ${channelFilter === 'telegram' ? 'Telegram' : 'MAX'}` }
      : null,
    preferredChannelFilter !== 'all'
      ? {
          key: 'preferred-channel' as const,
          label: `Предпочтительный канал: ${preferredChannelFilter === 'telegram' ? 'Telegram' : 'MAX'}`,
        }
      : null,
    view !== 'kanban' && pipeline !== 'interview'
      ? { key: 'pipeline' as const, label: `Воронка: ${pipelineOptions.find((option) => option.slug === pipeline)?.label || pipeline}` }
      : null,
  ].filter(Boolean) as Array<{ key: ActiveFilterKey; label: string }>
  const advancedFilterCount = Number(channelFilter !== 'all') + Number(preferredChannelFilter !== 'all')

  const resetFilters = () => {
    setSearch('')
    setStateFilter('')
    setChannelFilter('all')
    setPreferredChannelFilter('all')
    setPipeline('interview')
    setPage(1)
    setShowAdvancedFilters(false)
  }

  const clearFilter = useCallback((key: ActiveFilterKey) => {
    switch (key) {
      case 'search':
        setSearch('')
        break
      case 'state':
        setStateFilter('')
        break
      case 'channel':
        setChannelFilter('all')
        break
      case 'preferred-channel':
        setPreferredChannelFilter('all')
        break
      case 'pipeline':
        setPipeline('interview')
        break
    }
    setPage(1)
  }, [])

  useEffect(() => {
    setHasAnimatedLists(true)
  }, [])

  useEffect(() => {
    if (channelFilter !== 'all' || preferredChannelFilter !== 'all') {
      setShowAdvancedFilters(true)
    }
  }, [channelFilter, preferredChannelFilter])

  useEffect(() => {
    setSelectedCandidateIds((prev) => {
      const next = prev.filter((id) => visibleListCards.some((candidate) => candidate.id === id))
      if (next.length === prev.length && next.every((id, index) => id === prev[index])) {
        return prev
      }
      return next
    })
  }, [visibleListCards])

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

  const triggerQuickCandidateAction = useCallback((candidate: CandidateListCard, action: CandidateAction) => {
    const confirmation = action.confirmation?.trim()
    if (confirmation && !window.confirm(confirmation)) return
    setActionCandidateId(candidate.id)
    candidateActionMutate({ candidateId: candidate.id, actionKey: action.key })
  }, [candidateActionMutate])

  const selectedCandidates = useMemo(
    () => listCards.filter((candidate) => selectedCandidateIds.includes(candidate.id)),
    [listCards, selectedCandidateIds],
  )
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
        <section className="glass page-section app-page__section">
          <header className="page-section__header candidates-page__header">
            <h1 className="candidates-page__title">Кандидаты</h1>
          </header>
          <div className="filter-bar ui-filter candidates-filter-bar" data-testid="candidates-filter-bar">
            <input
              aria-label="Поиск кандидата"
              placeholder="Поиск по ФИО, городу, каналу..."
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
            >
              {pipelineOptions.map((opt) => (
                <option key={opt.slug} value={opt.slug}>{opt.label}</option>
              ))}
            </select>
            {view === 'list' && (
              <button
                type="button"
                className={`ui-btn ui-btn--secondary ui-btn--sm candidates-filter-bar__secondary-toggle ${showAdvancedFilters ? 'is-active' : ''}`}
                onClick={() => setShowAdvancedFilters((prev) => !prev)}
                aria-expanded={showAdvancedFilters}
                aria-controls="candidates-advanced-filters"
                data-testid="candidates-advanced-filters-toggle"
              >
                {showAdvancedFilters ? 'Скрыть детали' : 'Доп. фильтры'}
                {advancedFilterCount > 0 ? (
                  <span className="candidates-filter-bar__secondary-count" aria-hidden="true">
                    {advancedFilterCount}
                  </span>
                ) : null}
              </button>
            )}
          </div>

          {view === 'list' && showAdvancedFilters && (
            <div
              id="candidates-advanced-filters"
              className="glass glass--subtle candidates-advanced-panel"
              data-testid="candidates-advanced-filters"
            >
              <div className="candidates-advanced-panel__section">
                <div className="candidates-advanced-panel__heading">Каналы и предпочтения</div>
                <div className="candidates-channel-filter" data-testid="candidates-channel-filter" aria-label="Фильтр по связанным каналам">
                  <span className="candidates-channel-filter__label">Связанные каналы</span>
                  {[
                    { value: 'all' as const, label: 'Все' },
                    { value: 'telegram' as const, label: 'Telegram' },
                    { value: 'max' as const, label: 'MAX' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`candidates-filter-pill ${channelFilter === option.value ? 'candidates-filter-pill--active' : ''}`}
                      aria-pressed={channelFilter === option.value}
                      onClick={() => {
                        setChannelFilter(option.value)
                        setPage(1)
                      }}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <div className="candidates-channel-filter" data-testid="candidates-preferred-channel-filter" aria-label="Фильтр по предпочтительному каналу">
                  <span className="candidates-channel-filter__label">Предпочтительный канал</span>
                  {[
                    { value: 'all' as const, label: 'Все' },
                    { value: 'telegram' as const, label: 'Telegram' },
                    { value: 'max' as const, label: 'MAX' },
                  ].map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`candidates-filter-pill ${preferredChannelFilter === option.value ? 'candidates-filter-pill--active' : ''}`}
                      aria-pressed={preferredChannelFilter === option.value}
                      onClick={() => {
                        setPreferredChannelFilter(option.value)
                        setPage(1)
                      }}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="candidates-advanced-panel__section candidates-advanced-panel__section--assistant">
                <div className="ai-reco">
                  <div className="ai-reco__header">
                    <div>
                      <div className="ai-reco__title">AI рекомендации</div>
                      <div className="subtitle">Подбор кандидатов под критерии города без перегруза основной рабочей сцены.</div>
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
              </div>
            </div>
          )}

          {activeFilterBadges.length > 0 && (
            <div className="candidates-active-filter-strip" aria-label="Активные фильтры" data-testid="candidates-active-filter-strip">
              {activeFilterBadges.map((filter) => (
                <button
                  key={filter.key}
                  type="button"
                  className="candidates-filter-pill candidates-filter-pill--active candidates-filter-pill--dismissible"
                  onClick={() => clearFilter(filter.key)}
                  aria-label={`Убрать фильтр ${filter.label}`}
                >
                  <span>{filter.label}</span>
                  <span aria-hidden="true">×</span>
                </button>
              ))}
              <button type="button" className="candidates-filter-pill candidates-filter-pill--reset" onClick={resetFilters}>
                Сбросить все
              </button>
            </div>
          )}

          {view === 'list' && selectedCandidateIds.length > 0 && (
            <div className="glass candidates-selection-bar" data-testid="candidates-selection-bar">
              <div className="candidates-selection-bar__summary">
                <strong>{selectedCandidateIds.length}</strong>
                <span>выбрано</span>
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

          {isLoading && <PageLoader label="Загружаем кандидатов" description="Собираем список кандидатов и их историю." compact className="candidates-inline-state" />}
          {isError && <ApiErrorBanner error={error} title="Не удалось загрузить кандидатов" />}
          {deleteCandidateError && <ApiErrorBanner error={deleteCandidateError} title="Не удалось удалить кандидата" />}
          {candidateActionError && <ApiErrorBanner error={candidateActionError} title="Не удалось выполнить быстрое действие" />}
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
          {data && visibleListCards.length === 0 && (
            <EmptyState
              title={hasActiveFilters ? 'По текущим фильтрам ничего не найдено' : 'Список кандидатов пока пуст'}
              description={
                hasActiveFilters
                  ? 'Снимите часть ограничений или сбросьте фильтры, чтобы вернуть рабочий срез.'
                  : 'Все кандидаты и их история появятся здесь по мере работы системы.'
              }
              actions={(
                <>
                  {hasActiveFilters && (
                    <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={resetFilters}>
                      Сбросить фильтры
                    </button>
                  )}
                </>
              )}
              className="candidates-inline-state"
              compact
            />
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

          {view === 'list' && data && visibleListCards.length > 0 && (
            <>
              {isMobile && (
                <div className="mobile-card-list" data-testid="candidates-mobile-list">
                  {visibleListCards.map((c) => {
                      const state = buildCandidateSurfaceState(c)
                      const statusSummary = buildCandidateListStatus(c, state)
                      const recruiterName = c.recruiter?.name || c.recruiter_name || '—'
                      const canDelete =
                        isAdmin ||
                        (principalType === 'recruiter' && c.recruiter_id === profile.data?.principal.id)
                      const isDeleting = deletingCandidateId === c.id && deleteCandidateMutation.isPending
                      const isActionPending = actionCandidateId === c.id && candidateActionMutation.isPending
                      const isSelected = selectedCandidateIds.includes(c.id)
                      const candidateDate = formatCandidateDate(resolveCandidateDate(c))
                      const relevanceScore = resolveCandidateRelevanceScore(c)
                      const scoreTone = candidateScoreTone(relevanceScore, c.ai_relevance_level)
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
                            meta={renderCandidateChannelBadges(c)}
                            compact
                            aside={(
                              <div className="candidate-mobile-card__aside">
                                <span className={`candidate-score candidate-score--${scoreTone}`}>
                                  {resolveCandidateRelevanceLabel(c)}
                                </span>
                                <CandidateQuickActionsMenu
                                  candidate={c}
                                  canDelete={canDelete}
                                  isDeleting={isDeleting}
                                  isActionPending={isActionPending}
                                  onDeleteCandidate={deleteCandidate}
                                  onQuickAction={triggerQuickCandidateAction}
                                  compact
                                />
                              </div>
                            )}
                            className="candidate-mobile-card__identity"
                          />
                        </div>
                        <div className="candidate-status-stack">
                          <span className={`candidate-status-pill candidate-status-pill--${statusSummary.tone}`}>
                            {statusSummary.primary}
                          </span>
                          {statusSummary.secondary ? (
                            <span className="candidate-status-note">{statusSummary.secondary}</span>
                          ) : null}
                          {statusSummary.reason ? (
                            <span className="candidate-status-reason">{statusSummary.reason}</span>
                          ) : null}
                        </div>
                        <div className="candidate-mobile-card__meta">
                          <span className="candidate-row__date">{candidateDate}</span>
                          {isAdmin ? <span className="candidate-row__secondary">{recruiterName}</span> : null}
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
                      <th>Статус</th>
                      <th>Релевантность</th>
                      <th>Последняя активность</th>
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
                    {visibleListCards.map((c) => {
                      const state = buildCandidateSurfaceState(c)
                      const statusSummary = buildCandidateListStatus(c, state)
                      const recruiterName = c.recruiter?.name || c.recruiter_name || '—'
                      const canDelete =
                        isAdmin ||
                        (principalType === 'recruiter' && c.recruiter_id === profile.data?.principal.id)
                      const isDeleting = deletingCandidateId === c.id && deleteCandidateMutation.isPending
                      const isActionPending = actionCandidateId === c.id && candidateActionMutation.isPending
                      const relevanceScore = resolveCandidateRelevanceScore(c)
                      const scoreTone = candidateScoreTone(relevanceScore, c.ai_relevance_level)
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
                              meta={renderCandidateChannelBadges(c)}
                              className="candidate-row__identity"
                            />
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--status">
                            <div className="candidate-status-stack">
                              <span className={`candidate-status-pill candidate-status-pill--${statusSummary.tone}`}>
                                {statusSummary.primary}
                              </span>
                              {statusSummary.secondary ? <span className="candidate-status-note">{statusSummary.secondary}</span> : null}
                              {statusSummary.reason ? <span className="candidate-status-reason">{statusSummary.reason}</span> : null}
                            </div>
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--score">
                            <span className={`candidate-score candidate-score--${scoreTone}`}>
                              {resolveCandidateRelevanceLabel(c)}
                            </span>
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--meta">
                            <div className="candidate-row__meta">
                              <span className="candidate-row__date">{candidateDate}</span>
                              {isAdmin ? <span className="candidate-row__secondary">{recruiterName}</span> : null}
                            </div>
                          </td>
                          <td className="candidate-row__cell candidate-row__cell--actions">
                            <div className="candidate-row__actions">
                              <CandidateQuickActionsMenu
                                candidate={c}
                                canDelete={canDelete}
                                isDeleting={isDeleting}
                                isActionPending={isActionPending}
                                onDeleteCandidate={deleteCandidate}
                                onQuickAction={triggerQuickCandidateAction}
                              />
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

          {data && !isLoading && !isError && total > 0 && (
            <div className="pagination app-page__toolbar candidates-pagination">
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
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
