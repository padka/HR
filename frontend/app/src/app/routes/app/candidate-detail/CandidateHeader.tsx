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

  return (
    <>
      <div className="cd-header__back-row">
        <button type="button" className="cd-header__back" onClick={onBack}>
          <span aria-hidden="true">←</span>
          <span>Назад</span>
        </button>
      </div>
      <div className="cd-header__hero">
        <div className="cd-header__main">
          <div className="cd-header__info">
            <h1 className="cd-header__name">{candidateName}</h1>
            <div className="cd-header__subtitle-row">
              {showStatus && <span className="cd-header__status">{statusLabel}</span>}
              {candidate.city && <span className="cd-header__detail">{candidate.city}</span>}
              {candidate.responsible_recruiter?.name && (
                <span className="cd-header__detail">{candidate.responsible_recruiter.name}</span>
              )}
              {candidate.is_active === false && (
                <span className="cd-header__detail cd-header__detail--inactive">Неактивен</span>
              )}
            </div>
          </div>
          {(headerAiScore != null || isAiFetching) && (
            <div
              className={`cd-header-score cd-header-score--${headerAiLevel || 'unknown'}`}
              aria-label={`Релевантность ${headerAiScore != null ? Math.round(headerAiScore) : 'не рассчитана'}`}
            >
              <span className="cd-header-score__value">
                {headerAiScore != null ? Math.round(headerAiScore) : '…'}
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
