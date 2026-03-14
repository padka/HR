import type { CandidateFinalOutcome, AIScorecardMetricItem } from '@/api/services/candidates'
import type { FunnelStageKey, FunnelTone, StatusDisplay } from './candidate-detail.types'

export const FUNNEL_STAGE_META: Record<FunnelStageKey, { label: string; helper: string }> = {
  lead: {
    label: 'Лид',
    helper: 'Кандидат вошёл в воронку и прошёл Тест 1.',
  },
  slot: {
    label: 'Записан на слот',
    helper: 'Выбор и согласование времени собеседования.',
  },
  interview: {
    label: 'Собеседование',
    helper: 'Подтверждение, перенос или отказ по собеседованию.',
  },
  test2: {
    label: 'Тест 2',
    helper: 'Отправка второго теста и ожидание результата.',
  },
  intro_day: {
    label: 'Ознакомительный день',
    helper: 'Назначение и подтверждение ознакомительного дня.',
  },
  outcome: {
    label: 'Итог',
    helper: 'Финальный исход, архивирование и причина решения.',
  },
}

export const FUNNEL_STAGE_KEYS: FunnelStageKey[] = ['lead', 'slot', 'interview', 'test2', 'intro_day', 'outcome']

export const FUNNEL_STAGE_INDEX: Record<FunnelStageKey, number> = {
  lead: 0,
  slot: 1,
  interview: 2,
  test2: 3,
  intro_day: 4,
  outcome: 5,
}

export const FUNNEL_STAGE_ALIASES: Record<string, FunnelStageKey> = {
  lead: 'lead',
  contacted: 'lead',
  invited: 'lead',
  test: 'lead',
  testing: 'lead',
  test1_completed: 'lead',
  waiting_slot: 'slot',
  stalled_waiting_slot: 'slot',
  interview: 'interview',
  slot: 'slot',
  slot_pending: 'slot',
  slot_agreed: 'slot',
  time_proposed_waiting_candidate: 'slot',
  requested_other_slot: 'slot',
  interview_scheduled: 'slot',
  interview_confirmed: 'interview',
  interview_declined: 'interview',
  test2_sent: 'test2',
  test2_sent_waiting: 'test2',
  test2_completed: 'test2',
  test2_failed: 'test2',
  intro_day: 'intro_day',
  intro_day_scheduled: 'intro_day',
  intro_preconfirmed: 'intro_day',
  intro_day_confirmed_preliminary: 'intro_day',
  intro_day_confirmed_day_of: 'intro_day',
  intro_day_declined_invitation: 'intro_day',
  intro_day_declined_day_of: 'intro_day',
  outcome: 'outcome',
  hired: 'outcome',
  not_hired: 'outcome',
  archived_negative: 'outcome',
}

const STATUS_LABELS: Record<string, StatusDisplay> = {
  lead: { label: 'Лид', tone: 'muted' },
  contacted: { label: 'Контакт установлен', tone: 'info' },
  invited: { label: 'Приглашён', tone: 'info' },
  test1_completed: { label: 'Тест 1 пройден', tone: 'success' },
  waiting_slot: { label: 'Ожидает слот', tone: 'warning' },
  stalled_waiting_slot: { label: 'Застрял (ожидание слота)', tone: 'warning' },
  slot_pending: { label: 'На согласовании', tone: 'info' },
  interview_scheduled: { label: 'Собеседование назначено', tone: 'info' },
  interview_confirmed: { label: 'Собеседование подтверждено', tone: 'info' },
  interview_declined: { label: 'Отказ на собеседовании', tone: 'danger' },
  test2_sent: { label: 'Тест 2 отправлен', tone: 'info' },
  test2_completed: { label: 'Тест 2 пройден', tone: 'success' },
  test2_failed: { label: 'Тест 2 не пройден', tone: 'danger' },
  intro_day_scheduled: { label: 'Ознакомительный день назначен', tone: 'info' },
  intro_day_confirmed_preliminary: { label: 'ОД предварительно подтверждён', tone: 'info' },
  intro_day_declined_invitation: { label: 'ОД отклонён (приглашение)', tone: 'danger' },
  intro_day_confirmed_day_of: { label: 'ОД подтверждён (день)', tone: 'success' },
  intro_day_declined_day_of: { label: 'ОД отклонён (день)', tone: 'danger' },
  hired: { label: 'Закреплён на обучение', tone: 'success' },
  not_hired: { label: 'Не закреплён', tone: 'danger' },
}

export const DECLINED_STATUS_SLUGS = new Set([
  'interview_declined',
  'test2_failed',
  'intro_day_declined_invitation',
  'intro_day_declined_day_of',
  'not_hired',
  'archived_negative',
])

export function getStatusDisplay(slug: string | null | undefined): StatusDisplay {
  if (!slug) return { label: 'Нет статуса', tone: 'muted' }
  return STATUS_LABELS[slug] || { label: slug, tone: 'muted' }
}

export function resolveFunnelStageKey(value?: string | null): FunnelStageKey | null {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return null
  return FUNNEL_STAGE_ALIASES[normalized] || null
}

export function funnelStageStateLabel(value?: string | null): string {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'active') return 'Текущий этап'
  if (normalized === 'passed') return 'Пройден'
  if (normalized === 'declined') return 'Закрыт отказом'
  return 'Ожидает старта'
}

export function funnelToneForState(value?: string | null): FunnelTone {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'active') return 'accent'
  if (normalized === 'passed') return 'success'
  if (normalized === 'declined') return 'danger'
  return 'muted'
}

export function fitLevelLabel(level?: 'high' | 'medium' | 'low' | 'unknown' | null): string {
  if (level === 'high') return 'Высокая'
  if (level === 'medium') return 'Средняя'
  if (level === 'low') return 'Низкая'
  return 'Неизвестно'
}

export function fitLevelFromScore(score?: number | null): 'high' | 'medium' | 'low' | 'unknown' {
  if (typeof score !== 'number' || Number.isNaN(score) || score <= 0) return 'unknown'
  if (score >= 75) return 'high'
  if (score >= 50) return 'medium'
  return 'low'
}

export function scorecardMetricStatusLabel(status?: AIScorecardMetricItem['status']): string {
  if (status === 'met') return 'ОК'
  if (status === 'not_met') return 'Не ок'
  return 'Неясно'
}

export function finalOutcomeLabel(value?: CandidateFinalOutcome | null): string | null {
  if (value === 'attached') return 'Закреплен'
  if (value === 'not_attached') return 'Не закреплен'
  if (value === 'not_counted') return 'Не засчитан'
  return null
}

export function normalizeJourneyCopy(value?: string | null): string | null {
  const normalized = String(value || '').trim()
  if (!normalized) return null
  if (normalized === 'Initial backfill from current candidate status') {
    return 'Статус перенесён из текущей карточки кандидата'
  }
  return normalized
}

export function journeyStageLabel(value?: string | null): string | null {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return null
  if (normalized === 'lead') return 'лид'
  if (normalized === 'testing') return 'тестирование'
  if (normalized === 'interview') return 'собеседование'
  if (normalized === 'intro_day') return 'ознакомительный день'
  if (normalized === 'outcome') return 'итог'
  return normalized.replaceAll('_', ' ')
}

export function journeyActorLabel(value?: string | null): string | null {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return null
  if (normalized === 'candidate') return 'кандидат'
  if (normalized === 'recruiter') return 'рекрутер'
  if (normalized === 'migration') return 'система'
  if (normalized === 'system') return 'система'
  return normalized.replaceAll('_', ' ')
}

export function getHhSyncBadge(status?: string | null) {
  if (status === 'synced') return { label: 'HH синхр.', tone: 'success' as const }
  if (status === 'failed_sync' || status === 'error') return { label: 'HH ошибка', tone: 'danger' as const }
  if (status === 'pending_sync' || status === 'pending') return { label: 'HH ожидание', tone: 'warning' as const }
  if (status === 'conflicted') return { label: 'HH конфликт', tone: 'warning' as const }
  if (status === 'stale') return { label: 'HH устарело', tone: 'warning' as const }
  if (status === 'skipped') return { label: 'HH не найден', tone: 'muted' as const }
  if (!status) return null
  return { label: `HH: ${status}`, tone: 'muted' as const }
}
