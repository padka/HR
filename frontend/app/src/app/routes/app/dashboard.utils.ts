import type { IncomingCandidate } from '@/api/services/dashboard'

const AI_LEVEL_LABELS: Record<'high' | 'medium' | 'low' | 'unknown', string> = {
  high: 'Высокая',
  medium: 'Средняя',
  low: 'Низкая',
  unknown: 'Не определена',
}

export function dashboardTrendTone(display?: string | null): 'positive' | 'negative' | 'neutral' {
  if (!display) return 'neutral'
  const normalized = display.trim()
  if (normalized.startsWith('+')) return 'positive'
  if (normalized.startsWith('-')) return 'negative'
  return 'neutral'
}

export function leaderboardRankClass(rank: number) {
  return rank >= 1 && rank <= 3 ? `leaderboard-rank--${rank}` : ''
}

export function formatAiRelevance(candidate: IncomingCandidate): string {
  if (typeof candidate.ai_relevance_score === 'number') {
    const score = Math.min(100, Math.max(0, Math.round(candidate.ai_relevance_score)))
    return `${score}/100`
  }
  if (candidate.ai_relevance_level && AI_LEVEL_LABELS[candidate.ai_relevance_level]) {
    return AI_LEVEL_LABELS[candidate.ai_relevance_level]
  }
  return '—'
}

export function formatAiRecommendation(candidate: IncomingCandidate): string | null {
  if (candidate.ai_recommendation === 'od_recommended') return 'ОД'
  if (candidate.ai_recommendation === 'clarify_before_od') return 'Уточнить'
  if (candidate.ai_recommendation === 'not_recommended') return 'Стоп'
  return null
}

export function toIsoDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

export function getDefaultRange() {
  const today = new Date()
  const from = new Date(today)
  from.setDate(from.getDate() - 6)
  return {
    from: toIsoDate(from),
    to: toIsoDate(today),
  }
}
