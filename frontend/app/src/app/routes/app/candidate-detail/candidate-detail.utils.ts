import type {
  CandidateArchive,
  CandidateDetail,
  CandidateHHSummary,
  CandidateMaxRollout,
  CandidateMaxRolloutAction,
  CandidateMaxRolloutActionKind,
  CandidateMaxRolloutPreview,
  CandidatePendingSlotRequest,
  CandidateSlot,
  TestSection,
} from '@/api/services/candidates'
import { translateSystemMessage } from '@/app/components/CandidatePipeline/pipeline.utils'
import { formatDateTime, formatSlotTime } from '@/shared/utils/formatters'
import type {
  CandidateDrawerTimelineEvent,
  CandidatePipelineStage,
  FunnelStageItem,
  FunnelStageKey,
  IntroDayTemplateContext,
  JourneyEventRecord,
} from './candidate-detail.types'
import {
  DECLINED_STATUS_SLUGS,
  FUNNEL_STAGE_INDEX,
  FUNNEL_STAGE_KEYS,
  FUNNEL_STAGE_META,
  finalOutcomeLabel,
  funnelStageStateLabel,
  funnelToneForState,
  getStatusDisplay,
  journeyActorLabel,
  journeyStageLabel,
  normalizeJourneyCopy,
  resolveFunnelStageKey,
} from './candidate-detail.constants'

const introDayFirstName = (fio: string) => {
  const parts = fio.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return parts[1]
  return parts[0] || 'Кандидат'
}

const formatIntroDayDate = (dateStr: string) => {
  try {
    const [year, month, day] = dateStr.split('-')
    if (year && month && day) return `${day}.${month}`
  } catch {}
  return dateStr
}

export function renderIntroDayTemplate(
  template: string,
  candidateFio: string,
  dateStr: string,
  timeStr: string,
  templateContext?: IntroDayTemplateContext | null,
) {
  if (!template) return ''
  const firstName = introDayFirstName(candidateFio)
  const formattedDate = formatIntroDayDate(dateStr)
  const slotDateTime = [formattedDate, timeStr].filter(Boolean).join(' ').trim()
  const context: Record<string, string> = {
    candidate_name: candidateFio || firstName,
    candidate_fio: candidateFio || firstName,
    candidate_first_name: firstName,
    slot_date_local: formattedDate,
    slot_time_local: timeStr,
    slot_datetime_local: slotDateTime,
    dt_local: slotDateTime,
    interview_date_local: formattedDate,
    interview_time_local: timeStr,
    interview_datetime_local: slotDateTime,
    city_name: templateContext?.city_name || '',
    intro_address: templateContext?.intro_address || templateContext?.address || '',
    address: templateContext?.address || templateContext?.intro_address || '',
    city_address: templateContext?.city_address || templateContext?.intro_address || templateContext?.address || '',
    intro_contact: templateContext?.intro_contact || templateContext?.recruiter_contact || '',
    recruiter_contact: templateContext?.recruiter_contact || templateContext?.intro_contact || '',
    contact_name: templateContext?.contact_name || '',
    contact_phone: templateContext?.contact_phone || '',
  }

  let message = template
  for (const [key, value] of Object.entries(context)) {
    const moustache = new RegExp(`{{\\s*${key}\\s*}}`, 'g')
    const braces = new RegExp(`\\{${key}\\}`, 'g')
    message = message.replace(moustache, value).replace(braces, value)
  }

  return message
    .replace(/\[Имя\]/g, firstName)
    .replace(/\[Дата\]/g, formattedDate)
    .replace(/\[Время\]/g, timeStr)
}

export function buildTestSections(detail?: CandidateDetail | null): TestSection[] {
  const raw = detail?.test_sections ?? []
  if (raw.length > 0) return raw
  const map = detail?.test_results ?? {}
  const entries = Object.entries(map)
  if (entries.length === 0) return []
  return entries.map(([key, value]) => ({
    ...value,
    key,
    title: key === 'test1' ? 'Тест 1' : key === 'test2' ? 'Тест 2' : (value.title || key),
  }))
}

export function getInterviewSlot(slots?: CandidateSlot[] | null): CandidateSlot | null {
  return (slots || []).find((slot) => (slot.purpose || 'interview') !== 'intro_day') || null
}

export function getIntroDaySlot(slots?: CandidateSlot[] | null): CandidateSlot | null {
  return (slots || []).find((slot) => slot.purpose === 'intro_day') || null
}

function formatTimelineTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function joinTimelineMeta(values: Array<string | null | undefined>): string | undefined {
  const normalized = Array.from(new Set(
    values
      .map((value) => translateSystemMessage(value))
      .map((value) => value.trim())
      .filter(Boolean),
  ))

  return normalized.length > 0 ? normalized.join(' · ') : undefined
}

export function buildCandidateTimeline(
  items: CandidateDetail['timeline'] | undefined,
  hhSummary?: CandidateHHSummary | null,
): CandidateDrawerTimelineEvent[] {
  const events: Array<CandidateDrawerTimelineEvent & { sortValue: number }> = (items || []).map((item, index) => {
    const timestamp = formatTimelineTime(item.dt)
    const sortValue = item.dt ? new Date(item.dt).getTime() : 0
    if (item.kind === 'test') {
      const score = typeof item.score === 'number' ? `${item.score.toFixed(1)}%` : 'без оценки'
      return {
        id: `timeline-test-${index}-${item.dt || ''}`,
        timestamp,
        title: `${translateSystemMessage(item.rating || 'Тест')}: ${score}`,
        meta: 'Автоматически',
        tone: 'test',
        sortValue,
      }
    }
    if (item.kind === 'message') {
      return {
        id: `timeline-message-${index}-${item.dt || ''}`,
        timestamp,
        title: 'Сообщение отправлено',
        meta: item.text ? String(item.text).slice(0, 120) : 'Система',
        tone: 'system',
        sortValue,
      }
    }
    if (item.kind === 'slot') {
      return {
        id: `timeline-slot-${index}-${item.dt || ''}`,
        timestamp,
        title: item.status === 'confirmed' ? 'Собеседование подтверждено' : 'Собеседование назначено',
        meta: joinTimelineMeta([
          item.recruiter ? `Рекрутер: ${item.recruiter}` : 'Система',
          item.city,
        ]),
        tone: 'status',
        sortValue,
      }
    }
    if (item.kind === 'interview_feedback') {
      const scorecard =
        item.scorecard && typeof item.scorecard === 'object'
          ? (item.scorecard as { average_rating?: number | null })
          : null
      const averageRating =
        typeof scorecard?.average_rating === 'number'
          ? `${Number(scorecard.average_rating).toFixed(1)}/5`
          : null
      return {
        id: `timeline-interview-${index}-${item.dt || ''}`,
        timestamp,
        title: translateSystemMessage(item.summary || 'Интервью проведено'),
        meta: joinTimelineMeta([
          averageRating ? `Оценка ${averageRating}` : null,
          item.outcome_reason || 'Система',
        ]),
        tone: 'status',
        sortValue,
      }
    }
    if (item.kind === 'journey') {
      const payload = item.payload && typeof item.payload === 'object' ? item.payload : null
      const payloadReason = payload && typeof payload.reason === 'string' ? payload.reason : null
      return {
        id: `timeline-journey-${index}-${item.dt || ''}`,
        timestamp,
        title: translateSystemMessage(normalizeJourneyCopy(item.summary) || (item.status ? getStatusDisplay(item.status).label : 'Обновление воронки')),
        meta: joinTimelineMeta([
          'Система',
          payloadReason,
          !payloadReason && item.status ? getStatusDisplay(item.status).label : null,
        ]),
        tone: 'status',
        sortValue,
      }
    }
    return {
      id: `timeline-${index}-${item.dt || ''}`,
      timestamp,
      title: translateSystemMessage(item.summary || 'Событие'),
      meta: joinTimelineMeta([item.status ? getStatusDisplay(item.status).label : 'Система']),
      tone: 'system',
      sortValue,
    }
  })

  for (const job of hhSummary?.recent_jobs || []) {
    events.push({
      id: `timeline-hh-job-${job.id}`,
      timestamp: formatTimelineTime(job.finished_at || job.created_at),
      title: translateSystemMessage(job.job_type || 'HH задача'),
      meta: joinTimelineMeta([
        job.status ? `HH · ${job.status}` : 'HH',
        job.last_error || 'Синхронизация обновила данные',
      ]),
      tone: 'system',
      sortValue: new Date(job.finished_at || job.created_at || '').getTime() || 0,
    })
  }

  return events
    .filter((item) => item.timestamp !== '—')
    .sort((left, right) => right.sortValue - left.sortValue)
    .map(({ sortValue: _sortValue, ...event }) => event)
}

export function scorecardRecommendationShortLabel(
  value?: 'od_recommended' | 'clarify_before_od' | 'not_recommended' | null,
): string {
  if (value === 'od_recommended') return 'Рекомендуем'
  if (value === 'clarify_before_od') return 'Уточнить'
  if (value === 'not_recommended') return 'Не рекомендуем'
  return 'Без оценки'
}

const MAX_ROLLOUT_ACTION_LABELS: Record<CandidateMaxRolloutActionKind, string> = {
  preview: 'Предпросмотр',
  send: 'Отправка',
  reissue: 'Перевыпуск',
  revoke: 'Отзыв',
}

export function resolveMaxRolloutPreview(rollout?: CandidateMaxRollout | null): CandidateMaxRolloutPreview | null {
  if (!rollout) return null
  return {
    max_launch_url: rollout.preview?.max_launch_url || rollout.max_launch_url || null,
    max_chat_url: rollout.preview?.max_chat_url || rollout.max_chat_url || null,
    message_preview: rollout.preview?.message_preview || rollout.message_preview || null,
    expires_at: rollout.preview?.expires_at || rollout.expires_at || null,
    dry_run: rollout.preview?.dry_run ?? rollout.dry_run ?? false,
  }
}

export function resolveMaxRolloutAction(
  rollout: CandidateMaxRollout | null | undefined,
  kind: CandidateMaxRolloutActionKind,
): CandidateMaxRolloutAction | null {
  if (!rollout) return null
  const action =
    rollout.actions?.[kind]
    || rollout[`${kind}_action` as const]
    || (rollout[`${kind}_action_key` as const]
      ? {
          key: String(rollout[`${kind}_action_key` as const]),
          label: MAX_ROLLOUT_ACTION_LABELS[kind],
          method: 'POST',
          kind,
        }
      : null)

  if (!action || !action.key) return null
  return {
    ...action,
    label: action.label || MAX_ROLLOUT_ACTION_LABELS[kind],
    method: action.method || 'POST',
    kind,
  }
}

export function journeyEventTitle(event: JourneyEventRecord): string {
  const map: Record<string, string> = {
    status_changed: 'Статус обновлён',
    status_backfill: 'Статус перенесён из истории',
    reminder_sent: 'Отправлено напоминание',
    slot_proposed: 'Предложен слот',
    slot_confirmed: 'Слот подтверждён',
    slot_declined: 'Слот отклонён',
    slot_reschedule_requested: 'Запрос другого слота',
    interview_confirmed: 'Интервью подтверждено',
    interview_declined: 'Отказ от интервью',
    intro_day_confirmed: 'ОД подтверждён',
    intro_day_declined: 'ОД отклонён',
    test_sent: 'Тест отправлен',
    test_completed: 'Тест завершён',
    archived: 'Переведён в архив',
    final_outcome_set: 'Финальный исход обновлён',
  }
  const normalizedSummary = normalizeJourneyCopy(event.summary)
  if (normalizedSummary) return normalizedSummary
  if (event.event_key && map[event.event_key]) return map[event.event_key]
  if (event.status_slug) return getStatusDisplay(event.status_slug).label
  return 'Событие воронки'
}

export function journeyEventMeta(event: JourneyEventRecord): string[] {
  const lines: string[] = []
  if (event.status_slug) {
    lines.push(`Статус: ${getStatusDisplay(event.status_slug).label}`)
  }
  const payload = event.payload || {}
  if (payload && typeof payload === 'object') {
    const fromStatus = typeof payload.from_status === 'string' ? payload.from_status : null
    const toStatus = typeof payload.to_status === 'string' ? payload.to_status : null
    const reason = typeof payload.reason === 'string' ? payload.reason : null
    if (fromStatus || toStatus) {
      lines.push(`Переход: ${getStatusDisplay(fromStatus).label} -> ${getStatusDisplay(toStatus).label}`)
    }
    if (reason) {
      lines.push(`Причина: ${reason}`)
    }
  }
  return lines
}

type BuildPipelineParams = {
  detail: CandidateDetail
  statusSlug: string | null
  statusLabel: string
  candidateJourney: CandidateDetail['journey']
  archiveInfo: CandidateArchive | null
  pendingSlotRequest: { summary: string; comment?: string | null } | null
  rescheduleRequest: { summary: string; comment?: string | null } | null
  finalOutcomeDisplay: string | null
  finalOutcomeReason: string | null
  test1Section?: TestSection
  test2Section?: TestSection
}

export function buildCandidatePipelineData({
  detail,
  statusSlug,
  statusLabel,
  candidateJourney,
  archiveInfo,
  pendingSlotRequest,
  rescheduleRequest,
  finalOutcomeDisplay,
  finalOutcomeReason,
  test1Section,
  test2Section,
}: BuildPipelineParams): {
  currentStage: FunnelStageKey
  stages: CandidatePipelineStage[]
} {
  const interviewSlot = getInterviewSlot(detail.slots)
  const introDaySlot = getIntroDaySlot(detail.slots)
  const journeyEvents = candidateJourney?.events || []
  const currentFunnelStage =
    resolveFunnelStageKey(candidateJourney?.state)
    || resolveFunnelStageKey(archiveInfo?.stage)
    || resolveFunnelStageKey(statusSlug)
    || 'lead'
  const journeyEventsByStage: Record<FunnelStageKey, JourneyEventRecord[]> = {
    lead: [],
    slot: [],
    interview: [],
    test2: [],
    intro_day: [],
    outcome: [],
  }

  for (const event of journeyEvents) {
    const stageKey = resolveFunnelStageKey(event.stage) || resolveFunnelStageKey(event.status_slug) || currentFunnelStage
    journeyEventsByStage[stageKey].push(event)
  }

  const currentStageIndex = FUNNEL_STAGE_INDEX[currentFunnelStage]
  const isDeclinedFlow = DECLINED_STATUS_SLUGS.has(String(candidateJourney?.state || statusSlug || '').trim().toLowerCase())

  const funnelStageItems: FunnelStageItem[] = FUNNEL_STAGE_KEYS.map((key) => {
    const stageIndex = FUNNEL_STAGE_INDEX[key]
    let state = 'pending'
    if (stageIndex < currentStageIndex) {
      state = 'passed'
    } else if (stageIndex === currentStageIndex) {
      state = isDeclinedFlow ? 'declined' : 'active'
    }
    const events = journeyEventsByStage[key]
    const lastEvent = events[0]
    let summary = ''
    let note: string | null = null

    if (key === 'lead') {
      summary = currentFunnelStage === 'lead'
        ? (candidateJourney?.state_label || statusLabel)
        : test1Section?.status_label
          ? `Тест 1: ${test1Section.status_label}`
          : lastEvent?.summary || (state === 'passed' ? 'Этап завершён' : 'Новый кандидат')
      note = test1Section?.summary || lastEvent?.summary || null
    } else if (key === 'slot') {
      summary = currentFunnelStage === 'slot'
        ? (candidateJourney?.state_label || statusLabel)
        : pendingSlotRequest?.summary
          ? 'Запросил другой слот'
          : interviewSlot?.start_utc
            ? `Слот ${formatSlotTime(interviewSlot.start_utc, interviewSlot.candidate_tz)}`
            : lastEvent?.summary || (state === 'passed' ? 'Слот согласован' : 'Слот ещё не назначен')
      note = pendingSlotRequest?.summary || rescheduleRequest?.summary || lastEvent?.summary || null
    } else if (key === 'interview') {
      summary = currentFunnelStage === 'interview'
        ? (candidateJourney?.state_label || statusLabel)
        : lastEvent?.summary || (state === 'passed' ? 'Собеседование завершено' : 'Собеседование ещё не проведено')
      note = interviewSlot?.start_utc ? formatSlotTime(interviewSlot.start_utc, interviewSlot.candidate_tz) : null
    } else if (key === 'test2') {
      summary = currentFunnelStage === 'test2'
        ? (candidateJourney?.state_label || statusLabel)
        : test2Section?.status_label
          ? `Тест 2: ${test2Section.status_label}`
          : lastEvent?.summary || (state === 'passed' ? 'Тест 2 завершён' : 'Тест 2 ещё не отправлен')
      note = test2Section?.summary || lastEvent?.summary || null
    } else if (key === 'intro_day') {
      summary = currentFunnelStage === 'intro_day'
        ? (candidateJourney?.state_label || statusLabel)
        : introDaySlot?.start_utc
          ? `ОД: ${formatSlotTime(introDaySlot.start_utc, introDaySlot.candidate_tz)}`
          : lastEvent?.summary || (state === 'passed' ? 'Этап завершён' : 'Ещё не назначен')
      note = introDaySlot?.city_name || lastEvent?.summary || null
    } else {
      summary = finalOutcomeDisplay
        || (archiveInfo ? `${archiveInfo.label || 'Архив'}${archiveInfo.stage_label ? ` · ${archiveInfo.stage_label}` : ''}` : null)
        || (currentFunnelStage === 'outcome' ? (candidateJourney?.state_label || statusLabel) : null)
        || (state === 'declined' ? 'Отказ зафиксирован' : 'Решение не зафиксировано')
      note = finalOutcomeReason || archiveInfo?.reason || lastEvent?.summary || null
    }

    return {
      key,
      label: FUNNEL_STAGE_META[key].label,
      state,
      stateLabel: funnelStageStateLabel(state),
      tone: funnelToneForState(state),
      summary,
      note,
      events,
    }
  })

  const stages = funnelStageItems.map((stage) => {
    const status: CandidatePipelineStage['status'] =
      stage.state === 'passed'
        ? 'completed'
        : stage.state === 'active' || stage.state === 'declined'
          ? 'current'
          : 'upcoming'

    const detailMeta = [
      stage.stateLabel,
      stage.note,
      detail.responsible_recruiter?.name ? `Рекрутер: ${detail.responsible_recruiter.name}` : null,
    ].filter(Boolean) as string[]

    if (stage.key === 'slot' && pendingSlotRequest?.summary) {
      detailMeta.unshift(`Запрос кандидата: ${pendingSlotRequest.summary}`)
    } else if (stage.key === 'slot' && interviewSlot?.start_utc) {
      detailMeta.unshift(`Назначено: ${formatSlotTime(interviewSlot.start_utc, interviewSlot.candidate_tz)}`)
    } else if (stage.key === 'intro_day' && introDaySlot?.start_utc) {
      detailMeta.unshift(`Дата ОД: ${formatSlotTime(introDaySlot.start_utc, introDaySlot.candidate_tz)}`)
    } else if (stage.key === 'test2' && test2Section?.status_label) {
      detailMeta.unshift(`Статус теста: ${test2Section.status_label}`)
    } else if (stage.key === 'lead' && test1Section?.status_label) {
      detailMeta.unshift(`Тест 1: ${test1Section.status_label}`)
    }

    return {
      id: stage.key,
      title: stage.label,
      subtitle: stage.summary,
      status,
      badge: status === 'completed' ? 'Пройден' : status === 'current' ? 'Текущий этап' : undefined,
      helper: FUNNEL_STAGE_META[stage.key].helper,
      detail: {
        description: FUNNEL_STAGE_META[stage.key].helper,
        meta: detailMeta,
        notice: stage.key === 'outcome' && (finalOutcomeDisplay || archiveInfo)
          ? {
              title: finalOutcomeDisplay || archiveInfo?.label || 'Итог',
              text: finalOutcomeReason || archiveInfo?.reason || 'Финальное решение уже зафиксировано в профиле кандидата.',
            }
          : null,
        events: stage.events.map((event, index) => ({
          id: String(event.id || `${stage.key}-${index}`),
          title: journeyEventTitle(event),
          meta:
            [journeyStageLabel(event.stage), journeyActorLabel(event.actor_type)].filter(Boolean).join(' · ')
            || 'Системное событие',
          lines: journeyEventMeta(event),
          timestamp: event.created_at ? formatDateTime(event.created_at) : null,
        })),
        emptyText: 'Для этого этапа пока нет событий.',
      },
    }
  })

  return { currentStage: currentFunnelStage, stages }
}

export function resolveFinalOutcomeDisplay(
  candidateJourney: CandidateDetail['journey'],
  finalOutcome: CandidateDetail['final_outcome'],
) {
  return candidateJourney?.final_outcome_label || finalOutcomeLabel(finalOutcome) || null
}

export function resolvePendingSlotRequest(
  detailRequest?: CandidateDetail['pending_slot_request'] | null,
  journeyRequest?: CandidatePendingSlotRequest | null,
) {
  return detailRequest || journeyRequest || null
}
