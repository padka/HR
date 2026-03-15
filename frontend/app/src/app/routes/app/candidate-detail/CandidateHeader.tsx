import type { CandidateDetail } from '@/api/services/candidates'
import { scorecardRecommendationShortLabel } from './candidate-detail.utils'

type CandidateHeaderProps = {
  candidate: CandidateDetail
  candidateId: number
  statusLabel: string
  showStatus: boolean
  headerAiScore: number | null
  headerAiLevel: 'high' | 'medium' | 'low' | 'unknown'
  headerAiRecommendation?: 'od_recommended' | 'clarify_before_od' | 'not_recommended' | null
  isAiFetching: boolean
  onBack: () => void
}

export function CandidateHeader({
  candidate,
  candidateId,
  statusLabel,
  showStatus,
  headerAiScore,
  headerAiLevel,
  headerAiRecommendation,
  isAiFetching,
  onBack,
}: CandidateHeaderProps) {
  const candidateName = candidate.fio || `Кандидат #${candidateId}`
  const recommendationLabel = headerAiRecommendation ? scorecardRecommendationShortLabel(headerAiRecommendation) : null
  const subtitle = [
    showStatus ? statusLabel : null,
    headerAiScore != null ? `${Math.round(headerAiScore)}/100` : isAiFetching ? 'Релевантность...' : null,
  ].filter(Boolean).join(' · ')

  return (
    <>
      <div className="cd-header__back-row">
        <button type="button" className="cd-header__back" onClick={onBack}>
          <span aria-hidden="true">←</span>
          <span>Назад</span>
        </button>
      </div>
      <div className="cd-header__hero">
        <div className="cd-header__avatar">
          {candidateName.charAt(0).toUpperCase()}
        </div>
        <div className="cd-header__main">
          <div className="cd-header__info">
            <div className="cd-header__name-row">
              <h1 className="cd-header__name">{candidateName}</h1>
              {candidate.status_is_terminal && (
                <span className="cd-badge cd-badge--terminal">Финальный этап</span>
              )}
            </div>
            {subtitle && <p className="cd-header__subtitle">{subtitle}</p>}
            <div className="cd-header__meta">
              {candidate.city && <span className="cd-chip">Город: {candidate.city}</span>}
              {candidate.responsible_recruiter?.name && (
                <span className="cd-chip cd-chip--accent">Рекрутер: {candidate.responsible_recruiter.name}</span>
              )}
              {candidate.manual_mode && (
                <span className="cd-chip cd-chip--warning">Ручное назначение</span>
              )}
              <span className={`cd-chip ${candidate.is_active === false ? 'cd-chip--danger' : 'cd-chip--success'}`}>
                {candidate.is_active === false ? 'Неактивен' : 'Активен'}
              </span>
            </div>
          </div>
          {(headerAiScore != null || isAiFetching) && (
            <div
              className={`cd-header-score cd-header-score--${headerAiLevel || 'unknown'}`}
              aria-label={`Релевантность ${headerAiScore != null ? Math.round(headerAiScore) : 'не рассчитана'}`}
            >
              <span className="cd-header-score__label">Релевантность</span>
              <span className="cd-header-score__value">
                {headerAiScore != null ? `${Math.round(headerAiScore)}/100` : '...'}
              </span>
              {recommendationLabel && (
                <span className="cd-header-score__meta">{recommendationLabel}</span>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
