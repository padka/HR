type CohortBarProps = {
  label: string
  candidateValue?: number | null
  averageValue?: number | null
  formatter?: (value: number) => string
}

export default function CohortBar({
  label,
  candidateValue,
  averageValue,
  formatter = (value) => value.toFixed(1),
}: CohortBarProps) {
  const maxValue = Math.max(candidateValue || 0, averageValue || 0, 1)
  return (
    <div className="cohort-comparison__metric">
      <div className="cohort-comparison__metric-head">
        <span>{label}</span>
        <span>
          {candidateValue != null ? formatter(candidateValue) : '—'} / {averageValue != null ? formatter(averageValue) : '—'}
        </span>
      </div>
      <div className="cohort-comparison__bars">
        <div className="cohort-comparison__bar-row">
          <span className="cohort-comparison__bar-label">Кандидат</span>
          <div className="cohort-comparison__bar-track">
            <div className="cohort-comparison__bar cohort-comparison__bar--candidate" style={{ width: `${((candidateValue || 0) / maxValue) * 100}%` }} />
          </div>
        </div>
        <div className="cohort-comparison__bar-row">
          <span className="cohort-comparison__bar-label">Когорта</span>
          <div className="cohort-comparison__bar-track">
            <div className="cohort-comparison__bar cohort-comparison__bar--average" style={{ width: `${((averageValue || 0) / maxValue) * 100}%` }} />
          </div>
        </div>
      </div>
    </div>
  )
}
