import { formatDateTime } from './formatters'

type RescheduleRequestShape = {
  requested_start_utc?: string | null
  requested_end_utc?: string | null
  candidate_comment?: string | null
}

export function scorecardRecommendationLabel(
  value?: 'od_recommended' | 'clarify_before_od' | 'not_recommended' | null,
): string {
  if (value === 'od_recommended') return 'Рекомендуем ОД'
  if (value === 'clarify_before_od') return 'Нужно уточнение'
  if (value === 'not_recommended') return 'Не рекомендуем ОД'
  return 'Решение не определено'
}

export function formatRescheduleRequest(
  request?: RescheduleRequestShape | null,
): { summary: string; comment?: string | null } | null {
  if (!request) return null
  if (request.requested_start_utc && request.requested_end_utc) {
    const start = new Date(request.requested_start_utc)
    const end = new Date(request.requested_end_utc)
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
    return {
      summary: `Окно: ${startLabel}–${endLabel}`,
      comment: request.candidate_comment,
    }
  }
  if (request.requested_start_utc) {
    return {
      summary: `Хочет время: ${formatDateTime(request.requested_start_utc)}`,
      comment: request.candidate_comment,
    }
  }
  if (request.candidate_comment) {
    return {
      summary: `Пожелание: ${request.candidate_comment}`,
      comment: null,
    }
  }
  return null
}
