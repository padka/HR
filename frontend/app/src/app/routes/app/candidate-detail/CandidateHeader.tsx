import type { CandidateDetail } from '@/api/services/candidates'
import { scorecardRecommendationShortLabel } from './candidate-detail.utils'

type CandidateHeaderProps = {
  candidate: CandidateDetail
  candidateId: number
  statusLabel: string
  statusTone: string
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
  statusTone,
  showStatus,
  headerAiScore,
  headerAiLevel,
  headerAiRecommendation,
  isAiFetching,
  onBack,
}: CandidateHeaderProps) {
  return (
    <div className="cd-header__top">
      <div className="cd-header__avatar">
        {(candidate.fio || '?').charAt(0).toUpperCase()}
      </div>
      <div className="cd-header__info">
        <div className="cd-header__name-row">
          <h1 className="cd-header__name">{candidate.fio || `Кандидат #${candidateId}`}</h1>
          {showStatus && (
            <span className={`status-pill status-pill--${statusTone}`}>
              <span className={`cd-status-dot cd-status-dot--${statusTone}`} />
              {statusLabel}
            </span>
          )}
          {(headerAiScore != null || isAiFetching) && (
            <div
              className={`cd-header-score cd-header-score--${headerAiLevel || 'unknown'}`}
              aria-label={`Релевантность ${headerAiScore != null ? Math.round(headerAiScore) : 'не рассчитана'}`}
            >
              <span className="cd-header-score__label">Релевантность</span>
              <span className="cd-header-score__value">
                {headerAiScore != null ? `${Math.round(headerAiScore)}/100` : '...'}
              </span>
              {headerAiRecommendation && (
                <span className="cd-header-score__meta">{scorecardRecommendationShortLabel(headerAiRecommendation)}</span>
              )}
            </div>
          )}
          {candidate.status_is_terminal && (
            <span className="cd-badge cd-badge--terminal">Финальный</span>
          )}
        </div>
        <div className="cd-header__meta">
          {candidate.city && <span className="cd-chip">{candidate.city}</span>}
          {candidate.responsible_recruiter?.name && (
            <span className="cd-chip cd-chip--accent">{candidate.responsible_recruiter.name}</span>
          )}
          {candidate.manual_mode && (
            <span className="cd-chip cd-chip--warning">Ручное назначение</span>
          )}
          {candidate.is_active === false && (
            <span className="cd-chip cd-chip--danger">Неактивен</span>
          )}
        </div>
      </div>
      <div className="cd-header__actions">
        <button type="button" className="ui-btn ui-btn--ghost" onClick={onBack}>К списку</button>
      </div>
    </div>
  )
}
