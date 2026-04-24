import { formatDateTime } from '@/shared/utils/formatters'
import type { CandidateDetail, TestSection } from '@/api/services/candidates'

import type { AvailableSlot, IncomingCandidate, IncomingPayload } from './incoming.types'

type IncomingSummaryState = {
  page: number
  pageSize: number
}

export type IncomingSummary = {
  queueTotal: number
  filteredTotal: number
  returnedCount: number
  shownStart: number
  shownEnd: number
  page: number
  pageSize: number
  pageCount: number
}

function coerceNonNegativeInt(value: unknown): number | null {
  if (typeof value !== 'number' || Number.isNaN(value)) return null
  const normalized = Math.trunc(value)
  return normalized >= 0 ? normalized : null
}

export function deriveIncomingSummary(
  payload: IncomingPayload | null | undefined,
  fallback: IncomingSummaryState,
): IncomingSummary {
  const items = Array.isArray(payload?.items) ? payload.items : []
  const returnedCount = items.length
  const page = Math.max(1, coerceNonNegativeInt(payload?.page) ?? fallback.page)
  const pageSize = Math.max(1, coerceNonNegativeInt(payload?.page_size) ?? fallback.pageSize)
  const filteredTotal = Math.max(coerceNonNegativeInt(payload?.total) ?? 0, returnedCount)
  const queueTotal = Math.max(coerceNonNegativeInt(payload?.queue_total) ?? 0, filteredTotal, returnedCount)
  if (filteredTotal === 0 || returnedCount === 0) {
    return {
      queueTotal,
      filteredTotal,
      returnedCount,
      shownStart: 0,
      shownEnd: 0,
      page,
      pageSize,
      pageCount: 1,
    }
  }
  const shownStart = ((page - 1) * pageSize) + 1
  const shownEnd = Math.min(filteredTotal, shownStart + returnedCount - 1)
  return {
    queueTotal,
    filteredTotal,
    returnedCount,
    shownStart,
    shownEnd,
    page,
    pageSize,
    pageCount: Math.max(1, Math.ceil(filteredTotal / pageSize)),
  }
}

export function toIsoDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

export function formatSlotOption(slot: AvailableSlot) {
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

export function formatInTz(utcIso: string, tz: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: tz,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(utcIso))
}

export function formatAiRecommendation(value?: IncomingCandidate['ai_recommendation'] | null) {
  if (value === 'od_recommended') return 'ОД'
  if (value === 'clarify_before_od') return 'Уточнить'
  if (value === 'not_recommended') return 'Стоп'
  return null
}

export function formatAiFreshnessLabel(
  state?: IncomingCandidate['ai_relevance_state'] | null,
  updatedAt?: string | null,
) {
  if (state === 'warming') return 'Обновляется'
  if (state === 'unknown') return 'Недостаточно данных'
  if (state === 'stale') return updatedAt ? `Устарело · ${formatDateTime(updatedAt)}` : 'Устарело'
  if (updatedAt) return `AI · ${formatDateTime(updatedAt)}`
  return 'AI'
}

export function formatAiDetailStateLabel(state?: IncomingCandidate['ai_relevance_state'] | null) {
  if (state === 'warming') return 'Обновляется'
  if (state === 'unknown') return 'Нет данных'
  if (state === 'stale') return 'Устарело'
  return 'Актуально'
}

export function formatAiDetailScore(candidate: IncomingCandidate) {
  if (typeof candidate.ai_relevance_score === 'number') return `${Math.round(candidate.ai_relevance_score)}/100`
  return 'Нет оценки'
}

export function formatAiPrimaryScore(candidate: IncomingCandidate) {
  if (typeof candidate.ai_relevance_score === 'number') return `${Math.round(candidate.ai_relevance_score)}`
  return '—'
}

export function formatAiUpdatedAtLabel(updatedAt?: string | null) {
  return updatedAt ? formatDateTime(updatedAt) : null
}

export function formatAiStateLabel(candidate: IncomingCandidate) {
  const state = candidate.ai_relevance_state || 'unknown'
  if (state === 'warming') return 'Обновляется'
  if (state === 'unknown') return 'Unknown'
  if (state === 'stale') return 'Устарело'
  if (typeof candidate.ai_relevance_score === 'number') return `${Math.round(candidate.ai_relevance_score)}`
  if (candidate.ai_relevance_level) return candidate.ai_relevance_level.toUpperCase()
  return 'Unknown'
}

export function resolveAiStateTone(candidate: IncomingCandidate) {
  const state = candidate.ai_relevance_state || 'unknown'
  if (state === 'warming' || state === 'unknown') return 'muted'
  if (state === 'stale') return 'warning'
  return resolveAiScoreTone(candidate.ai_relevance_score, candidate.ai_recommendation)
}

export function resolveAiScoreTone(score?: number | null, recommendation?: IncomingCandidate['ai_recommendation'] | null) {
  if (recommendation === 'not_recommended') return 'danger'
  if (recommendation === 'od_recommended') return 'success'
  if (typeof score === 'number') {
    if (score >= 75) return 'success'
    if (score >= 50) return 'warning'
    return 'danger'
  }
  return 'muted'
}

export function formatRequestedAnotherTime(candidate: IncomingCandidate): string | null {
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
  if (candidate.availability_window) {
    return `Хочет окно: ${candidate.availability_window}`
  }
  return null
}

export function formatDuration(totalSeconds?: number | null) {
  const total = Math.max(0, Math.round(totalSeconds || 0))
  if (total === 0) return '0 мин'
  const minutes = Math.round(total / 60)
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const restMinutes = minutes % 60
  return restMinutes > 0 ? `${hours} ч ${restMinutes} мин` : `${hours} ч`
}

export function resolveTestTone(status?: string | null) {
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

export function TestScoreBar({ correct, total, score }: { correct: number; total: number; score?: number | null }) {
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

export function resolveTest1Section(detail?: CandidateDetail | null): TestSection | null {
  if (!detail) return null
  const fromSections = detail.test_sections?.find((section) => section.key === 'test1')
  if (fromSections) return fromSections
  return detail.test_results?.test1 || null
}
