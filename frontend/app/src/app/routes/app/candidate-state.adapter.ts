import type {
  CandidateBlockingState,
  CandidateContractFinalOutcome,
  CandidateLifecycleStage,
  CandidateLifecycleSummary,
  CandidateNextAction,
  CandidateOperationalSummary,
  CandidateSchedulingSummary,
  CandidateStateReconciliation,
} from '@/api/services/candidates'

export type RecruiterSurfaceTone = 'muted' | 'info' | 'warning' | 'danger' | 'success'
export type RecruiterRiskLevel = 'info' | 'warning' | 'blocker' | 'repair'
export type RecruiterTriageLane = 'action_now' | 'waiting' | 'review'
export type RecruiterKanbanColumnMode = 'interactive' | 'guided' | 'system'

export type RecruiterKanbanColumnSlug =
  | 'incoming'
  | 'slot_pending'
  | 'interview_scheduled'
  | 'interview_confirmed'
  | 'test2_sent'
  | 'test2_completed'
  | 'intro_day_scheduled'
  | 'intro_day_confirmed_preliminary'
  | 'intro_day_confirmed_day_of'

export type RecruiterKanbanColumn = {
  slug: RecruiterKanbanColumnSlug
  label: string
  icon: string
  targetStatus: string
  droppable?: boolean
}

export const RECRUITER_KANBAN_COLUMNS: RecruiterKanbanColumn[] = [
  { slug: 'incoming', label: 'Входящие', icon: '📥', targetStatus: 'waiting_slot', droppable: false },
  { slug: 'slot_pending', label: 'На согласовании', icon: '🕐', targetStatus: 'slot_pending', droppable: false },
  { slug: 'interview_scheduled', label: 'Назначено собеседование', icon: '📅', targetStatus: 'interview_scheduled', droppable: false },
  { slug: 'interview_confirmed', label: 'Подтвердил собеседование', icon: '✅', targetStatus: 'interview_confirmed', droppable: true },
  { slug: 'test2_sent', label: 'Отправлен тест 2', icon: '📨', targetStatus: 'test2_sent', droppable: true },
  { slug: 'test2_completed', label: 'Прошел тест 2', icon: '🧪', targetStatus: 'test2_completed', droppable: true },
  { slug: 'intro_day_scheduled', label: 'Ознакомительный день назначен', icon: '📆', targetStatus: 'intro_day_scheduled', droppable: false },
  { slug: 'intro_day_confirmed_preliminary', label: 'Предварительно подтвердил ОД', icon: '👍', targetStatus: 'intro_day_confirmed_preliminary', droppable: true },
  { slug: 'intro_day_confirmed_day_of', label: 'Подтвердил ОД', icon: '🎯', targetStatus: 'intro_day_confirmed_day_of', droppable: true },
]

const LEGACY_STAGE_LABELS: Record<CandidateLifecycleStage, string> = {
  lead: 'Лид',
  screening: 'Скрининг',
  waiting_interview_slot: 'Ожидает слот на интервью',
  interview: 'Интервью',
  test2: 'Тест 2',
  waiting_intro_day: 'Ожидает ознакомительный день',
  intro_day: 'Ознакомительный день',
  closed: 'Закрыт',
}

const WORKLIST_BUCKET_LABELS: Record<string, string> = {
  incoming: 'Входящие',
  today: 'Сегодня',
  awaiting_candidate: 'Ждем кандидата',
  awaiting_recruiter: 'Ждет рекрутера',
  blocked: 'Требует разбор',
  closed: 'Закрыто',
}

const BLOCKING_STATE_COPY: Record<
  string,
  { level: RecruiterRiskLevel; title: string; message: string }
> = {
  scheduling_conflict: {
    level: 'repair',
    title: 'Нужен ручной разбор расписания',
    message: 'Состояние назначения расходится. Проверьте интервью или ознакомительный день и повторите действие.',
  },
  unsupported_kanban_move: {
    level: 'blocker',
    title: 'Эту колонку нельзя двигать вручную',
    message: 'Колонка обновляется системой или следующим безопасным шагом.',
  },
  missing_interview_scheduling: {
    level: 'blocker',
    title: 'Сначала назначьте интервью',
    message: 'Для этого шага у кандидата должно быть активное интервью.',
  },
  missing_intro_day_scheduling: {
    level: 'blocker',
    title: 'Сначала назначьте ознакомительный день',
    message: 'Для этого шага у кандидата должно быть активное назначение ознакомительного дня.',
  },
  invalid_kanban_transition: {
    level: 'blocker',
    title: 'Переход недоступен',
    message: 'Текущий этап кандидата не позволяет это перемещение.',
  },
  action_not_allowed: {
    level: 'blocker',
    title: 'Действие сейчас недоступно',
    message: 'Сначала завершите обязательный предыдущий шаг или обновите состояние кандидата.',
  },
  invalid_transition: {
    level: 'blocker',
    title: 'Нельзя выполнить этот переход',
    message: 'Текущее состояние кандидата не позволяет выполнить действие напрямую.',
  },
  test2_not_passed: {
    level: 'blocker',
    title: 'Тест 2 еще не подтвержден',
    message: 'Сначала дождитесь проходного результата теста 2, затем двигайте кандидата дальше.',
  },
  partial_transition_requires_repair: {
    level: 'repair',
    title: 'Переход выполнен не полностью',
    message: 'Система сохранила только часть изменений. Проверьте кандидата и завершите разбор вручную.',
  },
}

const LEGACY_KANBAN_COLUMN_BY_STATUS: Record<string, RecruiterKanbanColumnSlug> = {
  lead: 'incoming',
  contacted: 'incoming',
  invited: 'incoming',
  test1_completed: 'incoming',
  waiting_slot: 'incoming',
  stalled_waiting_slot: 'incoming',
  slot_pending: 'slot_pending',
  interview_scheduled: 'interview_scheduled',
  interview_confirmed: 'interview_confirmed',
  test2_sent: 'test2_sent',
  test2_completed: 'test2_completed',
  intro_day_scheduled: 'intro_day_scheduled',
  intro_day_confirmed_preliminary: 'intro_day_confirmed_preliminary',
  intro_day_confirmed_day_of: 'intro_day_confirmed_day_of',
}

type LegacyStatusMeta = {
  slug: string | null
  label: string | null
  tone: RecruiterSurfaceTone
}

export type CandidateStateCarrier = {
  status?: { slug?: string | null; label?: string | null; tone?: string | null } | null
  status_slug?: string | null
  status_display?: string | null
  lifecycle_summary?: CandidateLifecycleSummary | null
  scheduling_summary?: CandidateSchedulingSummary | null
  candidate_next_action?: CandidateNextAction | null
  operational_summary?: CandidateOperationalSummary | null
  state_reconciliation?: CandidateStateReconciliation | null
  blocking_state?: CandidateBlockingState | null
  waiting_hours?: number | null
  requested_another_time?: boolean | null
  incoming_substatus?: string | null
}

export type CandidateSurfaceState = {
  lifecycle: CandidateLifecycleSummary
  scheduling: CandidateSchedulingSummary | null
  nextAction: CandidateNextAction | null
  reconciliation: CandidateStateReconciliation | null
  blockingState: CandidateBlockingState | null
  statusLabel: string
  statusTone: RecruiterSurfaceTone
  schedulingLabel: string | null
  schedulingTone: RecruiterSurfaceTone | null
  nextActionLabel: string | null
  nextActionExplanation: string | null
  nextActionEnabled: boolean
  nextActionTone: RecruiterSurfaceTone
  nextActionUiAction: 'open_schedule_slot_modal' | 'open_schedule_intro_day_modal' | 'open_chat' | 'invoke_candidate_action' | null
  nextActionType: string | null
  nextActionOwnerLabel: string | null
  worklistBucket: string
  worklistBucketLabel: string
  urgency: string
  urgencyLabel: string
  urgencyTone: RecruiterSurfaceTone
  queueState: string | null
  queueStateLabel: string | null
  requestedOtherTime: boolean
  pendingApproval: boolean
  stalled: boolean
  hasSchedulingConflict: boolean
  hasReconciliationIssues: boolean
  reconciliationLabel: string | null
  reconciliationCount: number
  stateContextLine: string | null
  schedulingContextLine: string | null
  riskLevel: RecruiterRiskLevel | null
  riskTitle: string | null
  riskMessage: string | null
  riskRecoveryHint: string | null
  riskIssueCodes: string[]
  riskCount: number
  triageLane: RecruiterTriageLane
  kanbanColumnSlug: RecruiterKanbanColumnSlug
}

const GUIDED_KANBAN_COLUMNS = new Set<RecruiterKanbanColumnSlug>([
  'incoming',
  'slot_pending',
  'interview_scheduled',
  'intro_day_scheduled',
])

function normalizeTone(value?: string | null): RecruiterSurfaceTone {
  if (value === 'danger' || value === 'warning' || value === 'success' || value === 'info') {
    return value
  }
  return 'muted'
}

function buildLegacyStatusMeta(candidate: CandidateStateCarrier): LegacyStatusMeta {
  const fromObject = candidate.status
  const slug = fromObject?.slug || candidate.status_slug || null
  const label = fromObject?.label || candidate.status_display || slug || null
  const tone = normalizeTone(fromObject?.tone)
  return { slug, label, tone }
}

function buildFallbackLifecycleSummary(candidate: CandidateStateCarrier, legacy: LegacyStatusMeta): CandidateLifecycleSummary {
  const statusSlug = legacy.slug
  let stage: CandidateLifecycleStage = 'lead'
  let recordState: 'active' | 'closed' = 'active'
  let finalOutcome: CandidateContractFinalOutcome | null = null

  if (statusSlug === 'hired') {
    stage = 'closed'
    recordState = 'closed'
    finalOutcome = 'hired'
  } else if (statusSlug === 'not_hired' || statusSlug === 'interview_declined' || statusSlug === 'test2_failed') {
    stage = 'closed'
    recordState = 'closed'
    finalOutcome = 'not_hired'
  } else if (statusSlug === 'intro_day_scheduled' || statusSlug === 'intro_day_confirmed_preliminary' || statusSlug === 'intro_day_confirmed_day_of') {
    stage = 'intro_day'
  } else if (statusSlug === 'test2_sent' || statusSlug === 'test2_completed') {
    stage = statusSlug === 'test2_completed' ? 'waiting_intro_day' : 'test2'
  } else if (statusSlug === 'slot_pending' || statusSlug === 'interview_scheduled' || statusSlug === 'interview_confirmed') {
    stage = 'interview'
  } else if (statusSlug === 'waiting_slot' || statusSlug === 'stalled_waiting_slot') {
    stage = 'waiting_interview_slot'
  } else if (statusSlug === 'contacted' || statusSlug === 'invited' || statusSlug === 'test1_completed') {
    stage = 'screening'
  }

  return {
    stage,
    stage_label: LEGACY_STAGE_LABELS[stage],
    record_state: recordState,
    final_outcome: finalOutcome,
    final_outcome_label:
      finalOutcome === 'hired' ? 'Нанят' : finalOutcome === 'not_hired' ? 'Не нанят' : null,
    archive_reason: null,
    legacy_status_slug: statusSlug,
    updated_at: null,
  }
}

function toneForUrgency(value?: string | null): RecruiterSurfaceTone {
  if (value === 'blocked' || value === 'urgent') return 'danger'
  if (value === 'attention') return 'warning'
  if (value === 'normal') return 'info'
  return 'muted'
}

function labelForUrgency(value?: string | null): string {
  if (value === 'blocked') return 'Заблокировано'
  if (value === 'urgent') return 'Срочно'
  if (value === 'attention') return 'Нужно сейчас'
  if (value === 'normal') return 'В рабочем потоке'
  return 'Без приоритета'
}

function labelForOwnerRole(value?: string | null): string | null {
  if (value === 'candidate') return 'Ждет кандидата'
  if (value === 'recruiter') return 'Зона рекрутера'
  if (value === 'system') return 'Ведет система'
  if (value === 'admin') return 'Нужен админ'
  return null
}

function recoveryHintForBlockingState(
  blockingState: CandidateBlockingState | null,
  options: {
    hasSchedulingConflict: boolean
    pendingApproval: boolean
    requestedOtherTime: boolean
    stalled: boolean
  },
): string | null {
  if (blockingState?.manual_resolution_required) {
    return 'Откройте карточку кандидата и разберите состояние перед повторной попыткой.'
  }

  if (blockingState?.recoverable) {
    return 'После устранения причины действие можно повторить без смены этапа вручную.'
  }

  if (options.hasSchedulingConflict) {
    return 'Сверьте интервью, ознакомительный день и назначение, затем повторите действие.'
  }

  if (options.pendingApproval) {
    return 'Подтвердите выбранный слот или предложите кандидату новое время.'
  }

  if (options.requestedOtherTime) {
    return 'Подберите новый слот и закройте перенос через следующее действие.'
  }

  if (options.stalled) {
    return 'Верните кандидата в поток через чат или ближайший допустимый шаг.'
  }

  return null
}

export function describeKanbanColumnTreatment(column: {
  slug: string
  droppable?: boolean
}): { mode: RecruiterKanbanColumnMode; helperText: string } {
  if (column.droppable === true) {
    return {
      mode: 'interactive',
      helperText: 'Ручное перемещение доступно только для безопасных переходов.',
    }
  }

  if (GUIDED_KANBAN_COLUMNS.has(column.slug as RecruiterKanbanColumnSlug)) {
    return {
      mode: 'guided',
      helperText: 'Колонка меняется через действие рекрутера или scheduling flow, а не прямым drag-and-drop.',
    }
  }

  return {
    mode: 'system',
    helperText: 'Колонка обновляется системой или ответом кандидата.',
  }
}

function toneForLifecycle(
  lifecycle: CandidateLifecycleSummary,
  scheduling: CandidateSchedulingSummary | null,
  legacy: LegacyStatusMeta,
): RecruiterSurfaceTone {
  if (lifecycle.record_state === 'closed') {
    if (lifecycle.final_outcome === 'hired') return 'success'
    if (lifecycle.final_outcome === 'not_hired') return 'danger'
    return 'muted'
  }
  if (scheduling?.status === 'confirmed') return 'success'
  if (scheduling?.status === 'selected' || scheduling?.status === 'reschedule_requested') return 'warning'
  switch (lifecycle.stage) {
    case 'lead':
    case 'screening':
      return 'info'
    case 'waiting_interview_slot':
      return 'warning'
    case 'interview':
      return 'info'
    case 'test2':
      return 'info'
    case 'waiting_intro_day':
      return 'warning'
    case 'intro_day':
      return 'success'
    case 'closed':
      return lifecycle.final_outcome === 'hired' ? 'success' : 'danger'
    default:
      return legacy.tone
  }
}

function toneForScheduling(status?: string | null): RecruiterSurfaceTone | null {
  if (!status) return null
  if (status === 'confirmed' || status === 'completed') return 'success'
  if (status === 'selected' || status === 'reschedule_requested') return 'warning'
  if (status === 'cancelled' || status === 'no_show') return 'danger'
  return 'info'
}

function issueCodesFromReconciliation(reconciliation?: CandidateStateReconciliation | null): string[] {
  return (reconciliation?.issues || [])
    .map((issue) => issue.code || null)
    .filter((code): code is string => Boolean(code))
}

function buildStateContextLine(
  worklistBucketLabel: string,
  queueStateLabel?: string | null,
  lifecycleStageLabel?: string | null,
): string | null {
  const parts = [
    queueStateLabel && queueStateLabel !== worklistBucketLabel ? queueStateLabel : null,
    lifecycleStageLabel,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : null
}

function buildSchedulingContextLine(
  schedulingLabel?: string | null,
  requestedOtherTime?: boolean,
): string | null {
  if (!schedulingLabel && !requestedOtherTime) return null
  if (schedulingLabel && requestedOtherTime) return `${schedulingLabel} · Кандидат просит другое время`
  if (requestedOtherTime) return 'Кандидат просит другое время'
  return schedulingLabel || null
}

function buildRiskState(
  blockingState: CandidateBlockingState | null,
  operational: CandidateOperationalSummary | null,
  reconciliation: CandidateStateReconciliation | null,
  stalled: boolean,
  pendingApproval: boolean,
  requestedOtherTime: boolean,
): {
  level: RecruiterRiskLevel | null
  title: string | null
  message: string | null
  recoveryHint: string | null
  issueCodes: string[]
  count: number
} {
  if (blockingState?.code) {
    const issueCodes = blockingState.issue_codes || issueCodesFromReconciliation(reconciliation)
    const mapped = BLOCKING_STATE_COPY[blockingState.code]
    const hasSchedulingConflict = Boolean(
      operational?.has_scheduling_conflict
      || issueCodes.includes('scheduling_split_brain')
      || issueCodes.includes('scheduling_status_conflict')
    )
    if (mapped) {
      return {
        level: mapped.level,
        title: mapped.title,
        message: mapped.message,
        recoveryHint: recoveryHintForBlockingState(blockingState, {
          hasSchedulingConflict,
          pendingApproval,
          requestedOtherTime,
          stalled,
        }),
        issueCodes,
        count: issueCodes.length || 1,
      }
    }
  }

  const reconciliationIssueCodes = issueCodesFromReconciliation(reconciliation)
  const hasSchedulingConflict = Boolean(
    operational?.has_scheduling_conflict
    || reconciliationIssueCodes.includes('scheduling_split_brain')
    || reconciliationIssueCodes.includes('scheduling_status_conflict')
  )

  if (hasSchedulingConflict) {
    return {
      level: 'repair',
      title: 'Нужен разбор состояния кандидата',
      message: 'Расписание и текущее состояние кандидата расходятся. Проверьте назначение перед следующим действием.',
      recoveryHint: recoveryHintForBlockingState(blockingState, {
        hasSchedulingConflict,
        pendingApproval,
        requestedOtherTime,
        stalled,
      }),
      issueCodes: reconciliationIssueCodes,
      count: reconciliationIssueCodes.length || 1,
    }
  }

  if ((reconciliation?.issues || []).length > 0 || reconciliation?.has_blockers) {
    return {
      level: 'warning',
      title: 'Есть рассинхрон состояния',
      message: reconciliation?.issues?.[0]?.message || 'Проверьте состояние кандидата перед следующим действием.',
      recoveryHint: recoveryHintForBlockingState(blockingState, {
        hasSchedulingConflict,
        pendingApproval,
        requestedOtherTime,
        stalled,
      }),
      issueCodes: reconciliationIssueCodes,
      count: reconciliation?.issues?.length || reconciliationIssueCodes.length || 1,
    }
  }

  if (pendingApproval) {
    return {
      level: 'warning',
      title: 'Ждет решения рекрутера',
      message: 'Кандидат уже выбрал время. Нужна ваша реакция.',
      recoveryHint: recoveryHintForBlockingState(blockingState, {
        hasSchedulingConflict,
        pendingApproval,
        requestedOtherTime,
        stalled,
      }),
      issueCodes: [],
      count: 0,
    }
  }

  if (requestedOtherTime) {
    return {
      level: 'warning',
      title: 'Кандидат просит другое время',
      message: 'Подберите новый слот и закройте перенос без лишней переписки.',
      recoveryHint: recoveryHintForBlockingState(blockingState, {
        hasSchedulingConflict,
        pendingApproval,
        requestedOtherTime,
        stalled,
      }),
      issueCodes: [],
      count: 0,
    }
  }

  if (stalled) {
    return {
      level: 'warning',
      title: 'Кандидат застрял в ожидании',
      message: 'Пора подтолкнуть следующий шаг, чтобы кандидат не выпадал из потока.',
      recoveryHint: recoveryHintForBlockingState(blockingState, {
        hasSchedulingConflict,
        pendingApproval,
        requestedOtherTime,
        stalled,
      }),
      issueCodes: [],
      count: 0,
    }
  }

  return {
    level: null,
    title: null,
    message: null,
    recoveryHint: null,
    issueCodes: [],
    count: 0,
  }
}

function buildTriageLane(input: {
  riskLevel: RecruiterRiskLevel | null
  riskIssueCodes: string[]
  pendingApproval: boolean
  requestedOtherTime: boolean
  stalled: boolean
  nextActionEnabled: boolean
  urgency: string
  worklistBucket: string
  hasSchedulingConflict: boolean
}): RecruiterTriageLane {
  if (
    input.riskLevel === 'repair'
    || input.riskLevel === 'blocker'
    || input.hasSchedulingConflict
    || input.riskIssueCodes.length > 0
    || input.worklistBucket === 'blocked'
  ) {
    return 'review'
  }

  if (input.requestedOtherTime && !input.pendingApproval) {
    return 'waiting'
  }

  if (input.pendingApproval || input.stalled) {
    return 'action_now'
  }

  if (
    input.nextActionEnabled
    && (
      input.urgency === 'urgent'
      || input.urgency === 'attention'
      || input.urgency === 'blocked'
      || input.worklistBucket === 'today'
      || input.worklistBucket === 'awaiting_recruiter'
    )
  ) {
    return 'action_now'
  }

  return 'waiting'
}

function resolveKanbanColumnFromContract(
  lifecycle: CandidateLifecycleSummary,
  scheduling: CandidateSchedulingSummary | null,
  nextAction: CandidateNextAction | null,
  legacy: LegacyStatusMeta,
): RecruiterKanbanColumnSlug {
  const schedulingStatus = scheduling?.status || null
  const primaryActionType = nextAction?.primary_action?.type || null

  switch (lifecycle.stage) {
    case 'lead':
    case 'screening':
    case 'waiting_interview_slot':
      return 'incoming'
    case 'interview':
      if (schedulingStatus === 'selected') return 'slot_pending'
      if (schedulingStatus === 'confirmed') return 'interview_confirmed'
      return 'interview_scheduled'
    case 'test2':
      return primaryActionType === 'schedule_intro_day' ? 'test2_completed' : 'test2_sent'
    case 'waiting_intro_day':
      return 'test2_completed'
    case 'intro_day':
      if (schedulingStatus === 'confirmed') {
        if (primaryActionType === 'finalize_hired' || primaryActionType === 'finalize_not_hired') {
          return 'intro_day_confirmed_day_of'
        }
        return 'intro_day_confirmed_preliminary'
      }
      return 'intro_day_scheduled'
    case 'closed':
      return LEGACY_KANBAN_COLUMN_BY_STATUS[legacy.slug || ''] || 'incoming'
    default:
      return LEGACY_KANBAN_COLUMN_BY_STATUS[legacy.slug || ''] || 'incoming'
  }
}

export function buildCandidateSurfaceState(candidate: CandidateStateCarrier): CandidateSurfaceState {
  const legacy = buildLegacyStatusMeta(candidate)
  const lifecycle = candidate.lifecycle_summary || buildFallbackLifecycleSummary(candidate, legacy)
  const scheduling = candidate.scheduling_summary || null
  const nextAction = candidate.candidate_next_action || null
  const operational = candidate.operational_summary || null
  const reconciliation = candidate.state_reconciliation || null
  const issues = reconciliation?.issues || []
  const hasReconciliationIssues = operational?.has_reconciliation_issues ?? (issues.length > 0 || Boolean(reconciliation?.has_blockers))
  const queueState = operational?.queue_state || candidate.incoming_substatus || null
  const requestedOtherTime = Boolean(
    operational?.requested_reschedule
    || scheduling?.requested_reschedule
    || candidate.requested_another_time
    || queueState === 'requested_other_time'
    || nextAction?.primary_action?.type === 'resolve_reschedule'
  )
  const pendingApproval = Boolean(
    operational?.pending_approval
    || scheduling?.status === 'selected'
    || queueState === 'awaiting_candidate_confirmation'
    || legacy.slug === 'slot_pending'
    || nextAction?.primary_action?.type === 'approve_selected_slot'
  )
  const stalled = Boolean(
    operational?.stalled
    || (
      lifecycle.stage === 'waiting_interview_slot'
      && (
        (candidate.waiting_hours || 0) >= 24
        || legacy.slug === 'stalled_waiting_slot'
        || queueState === 'stalled_waiting_slot'
      )
    )
  )
  const worklistBucket =
    operational?.worklist_bucket
    || nextAction?.worklist_bucket
    || (lifecycle.record_state === 'closed' ? 'closed' : 'incoming')
  const urgency = nextAction?.urgency || (stalled ? 'urgent' : 'normal')
  const statusLabel =
    lifecycle.record_state === 'closed'
      ? lifecycle.final_outcome_label || lifecycle.stage_label || legacy.label || 'Закрыт'
      : lifecycle.stage_label || legacy.label || legacy.slug || '—'
  const reconciliationLabel = issues[0]?.message || (hasReconciliationIssues ? 'Есть рассинхрон состояния' : null)
  const hasSchedulingConflict = Boolean(
    operational?.has_scheduling_conflict
    || issues.some((issue) => issue.code === 'scheduling_split_brain' || issue.code === 'scheduling_status_conflict')
  )
  const blockingState = candidate.blocking_state || null
  const nextActionExplanation = nextAction?.explanation || null
  const nextPrimaryAction = nextAction?.primary_action || null
  const nextActionEnabled = nextPrimaryAction ? nextPrimaryAction.enabled !== false : false
  const stateContextLine = buildStateContextLine(
    operational?.worklist_bucket_label
      || nextAction?.worklist_bucket_label
      || WORKLIST_BUCKET_LABELS[worklistBucket]
      || worklistBucket,
    operational?.queue_state_label || (queueState ? queueState : null),
    lifecycle.stage_label,
  )
  const schedulingContextLine = buildSchedulingContextLine(
    scheduling?.status_label || null,
    requestedOtherTime,
  )
  const risk = buildRiskState(
    blockingState,
    operational,
    reconciliation,
    stalled,
    pendingApproval,
    requestedOtherTime,
  )
  const triageLane = buildTriageLane({
    riskLevel: risk.level,
    riskIssueCodes: risk.issueCodes,
    pendingApproval,
    requestedOtherTime,
    stalled,
    nextActionEnabled,
    urgency,
    worklistBucket,
    hasSchedulingConflict,
  })

  return {
    lifecycle,
    scheduling,
    nextAction,
    reconciliation,
    blockingState,
    statusLabel,
    statusTone: toneForLifecycle(lifecycle, scheduling, legacy),
    schedulingLabel: scheduling?.status_label || null,
    schedulingTone: toneForScheduling(scheduling?.status),
    nextActionLabel: nextAction?.primary_action?.label || nextAction?.explanation || null,
    nextActionExplanation,
    nextActionEnabled,
    nextActionTone: hasReconciliationIssues ? 'danger' : toneForUrgency(urgency),
    nextActionUiAction: nextAction?.primary_action?.ui_action || null,
    nextActionType: nextAction?.primary_action?.type || null,
    nextActionOwnerLabel: labelForOwnerRole(nextAction?.primary_action?.owner_role),
    worklistBucket,
    worklistBucketLabel:
      operational?.worklist_bucket_label
      || nextAction?.worklist_bucket_label
      || WORKLIST_BUCKET_LABELS[worklistBucket]
      || worklistBucket,
    urgency,
    urgencyLabel: labelForUrgency(urgency),
    urgencyTone: toneForUrgency(urgency),
    queueState,
    queueStateLabel: operational?.queue_state_label || (queueState ? queueState : null),
    requestedOtherTime,
    pendingApproval,
    stalled,
    hasSchedulingConflict,
    hasReconciliationIssues,
    reconciliationLabel,
    reconciliationCount: issues.length,
    stateContextLine,
    schedulingContextLine,
    riskLevel: risk.level,
    riskTitle: risk.title,
    riskMessage: risk.message,
    riskRecoveryHint: risk.recoveryHint,
    riskIssueCodes: risk.issueCodes,
    riskCount: risk.count,
    triageLane,
    kanbanColumnSlug:
      (operational?.kanban_column as RecruiterKanbanColumnSlug | null)
      || resolveKanbanColumnFromContract(lifecycle, scheduling, nextAction, legacy),
  }
}

export function matchesIncomingStatusFilter(
  candidate: CandidateStateCarrier,
  filter: 'all' | 'waiting_slot' | 'stalled_waiting_slot' | 'slot_pending' | 'requested_other_time',
): boolean {
  if (filter === 'all') return true
  const state = buildCandidateSurfaceState(candidate)
  if (filter === 'requested_other_time') return state.queueState === 'requested_other_time' || state.requestedOtherTime
  if (filter === 'slot_pending') return state.queueState === 'awaiting_candidate_confirmation' || state.pendingApproval
  if (filter === 'stalled_waiting_slot') return state.queueState === 'stalled_waiting_slot' || state.stalled
  if (filter === 'waiting_slot') return state.queueState === 'waiting_slot' || state.lifecycle.stage === 'waiting_interview_slot'
  return false
}

export function matchesDashboardIncomingFilter(
  candidate: CandidateStateCarrier & { last_message_at?: string | null },
  filter: 'all' | 'new' | 'stalled' | 'pending' | 'requested_other_time',
  nowTs: number = Date.now(),
): boolean {
  if (filter === 'all') return true
  const state = buildCandidateSurfaceState(candidate)
  if (filter === 'requested_other_time') return state.queueState === 'requested_other_time' || state.requestedOtherTime
  if (filter === 'pending') return state.queueState === 'awaiting_candidate_confirmation' || state.pendingApproval
  if (filter === 'stalled') return state.queueState === 'stalled_waiting_slot' || state.stalled
  if (filter === 'new') {
    if (!candidate.last_message_at) return false
    const ageMs = nowTs - new Date(candidate.last_message_at).getTime()
    return Number.isFinite(ageMs) && ageMs <= 24 * 60 * 60 * 1000
  }
  return true
}

export function compareIncomingCandidates(
  left: CandidateStateCarrier & { waiting_hours?: number | null; last_message_at?: string | null; name?: string | null },
  right: CandidateStateCarrier & { waiting_hours?: number | null; last_message_at?: string | null; name?: string | null },
  mode: 'waiting' | 'recent' | 'name' = 'waiting',
): number {
  const leftState = buildCandidateSurfaceState(left)
  const rightState = buildCandidateSurfaceState(right)

  const leftBlockers = leftState.hasReconciliationIssues ? 1 : 0
  const rightBlockers = rightState.hasReconciliationIssues ? 1 : 0
  if (leftBlockers !== rightBlockers) return rightBlockers - leftBlockers

  const leftRequested = leftState.requestedOtherTime ? 1 : 0
  const rightRequested = rightState.requestedOtherTime ? 1 : 0
  if (leftRequested !== rightRequested) return rightRequested - leftRequested

  const leftPending = leftState.pendingApproval ? 1 : 0
  const rightPending = rightState.pendingApproval ? 1 : 0
  if (leftPending !== rightPending) return rightPending - leftPending

  const leftStalled = leftState.stalled ? 1 : 0
  const rightStalled = rightState.stalled ? 1 : 0
  if (leftStalled !== rightStalled) return rightStalled - leftStalled

  if (mode === 'name') {
    return (left.name || '').localeCompare(right.name || '', 'ru')
  }
  if (mode === 'recent') {
    const leftTime = left.last_message_at ? new Date(left.last_message_at).getTime() : 0
    const rightTime = right.last_message_at ? new Date(right.last_message_at).getTime() : 0
    return rightTime - leftTime
  }

  const leftWaiting = left.waiting_hours ?? -1
  const rightWaiting = right.waiting_hours ?? -1
  if (rightWaiting !== leftWaiting) return rightWaiting - leftWaiting

  const leftTime = left.last_message_at ? new Date(left.last_message_at).getTime() : 0
  const rightTime = right.last_message_at ? new Date(right.last_message_at).getTime() : 0
  return rightTime - leftTime
}

export function summarizeIncomingCandidates(
  items: Array<CandidateStateCarrier & { waiting_hours?: number | null; last_message_at?: string | null }>,
): {
  total: number
  pending: number
  requested: number
  stalled: number
  fresh: number
  withIssues: number
} {
  const total = items.length
  let pending = 0
  let requested = 0
  let stalled = 0
  let fresh = 0
  let withIssues = 0
  const now = Date.now()

  for (const item of items) {
    const state = buildCandidateSurfaceState(item)
    if (state.pendingApproval) pending += 1
    if (state.requestedOtherTime) requested += 1
    if (state.stalled) stalled += 1
    if (state.hasReconciliationIssues) withIssues += 1
    if (item.last_message_at) {
      const ageMs = now - new Date(item.last_message_at).getTime()
      if (Number.isFinite(ageMs) && ageMs <= 24 * 60 * 60 * 1000) {
        fresh += 1
      }
    }
  }

  return { total, pending, requested, stalled, fresh, withIssues }
}
