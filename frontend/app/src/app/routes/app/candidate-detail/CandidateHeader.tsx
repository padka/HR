import { CandidateIdentityBlock } from '@/app/components/RecruiterState'
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
  const summaryBadges = [
    showStatus ? { label: statusLabel, tone: 'status' as const } : null,
    candidate.is_active === false ? { label: 'Неактивен', tone: 'inactive' as const } : null,
  ].filter((badge): badge is { label: string; tone: 'status' | 'inactive' } => Boolean(badge))

  return (
    <section className="cd-header" data-testid="candidate-detail-top-scene">
      <div className="cd-header__back-row">
        <button type="button" className="cd-header__back" onClick={onBack}>
          <span aria-hidden="true">←</span>
          <span>Назад</span>
        </button>
      </div>
      <div className="cd-header__surface">
        <CandidateIdentityBlock
          className="cd-header__identity-card"
          title={<h1 className="cd-header__name">{candidateName}</h1>}
          subtitle={summaryBadges.length > 0 ? (
            <div className="cd-header__pill-row">
              {summaryBadges.map((badge) => (
                <span
                  key={`${badge.tone}-${badge.label}`}
                  className={`cd-header__pill cd-header__pill--${badge.tone}`}
                >
                  {badge.label}
                </span>
              ))}
            </div>
          ) : undefined}
          meta={candidate.city ? <div className="cd-header__meta-line">Город: {candidate.city}</div> : undefined}
          aside={(headerAiScore != null || isAiFetching) ? (
            <div
              className={`cd-header-score cd-header-score--${headerAiLevel || 'unknown'}`}
              aria-label={`Релевантность ${headerAiScore != null ? Math.round(headerAiScore) : 'не рассчитана'}`}
            >
              <div className="cd-header-score__copy">
                <span className="cd-header-score__label">AI релевантность</span>
                {recommendationLabel ? (
                  <span className="cd-header-score__meta">{recommendationLabel}</span>
                ) : null}
              </div>
              <span className="cd-header-score__value">
                {headerAiScore != null ? Math.round(headerAiScore) : '…'}
              </span>
            </div>
          ) : undefined}
        />
      </div>
    </section>
  )
}
