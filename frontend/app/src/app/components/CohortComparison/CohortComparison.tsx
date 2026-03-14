import type { CandidateCohortComparison } from '@/api/services/candidates'

import './cohort-comparison.css'

import CohortBar from './CohortBar'

type CohortComparisonProps = {
  data?: CandidateCohortComparison | null
  isLoading?: boolean
}

function formatMinutes(value: number) {
  return `${Math.round(value / 60)} мин`
}

export default function CohortComparison({ data, isLoading = false }: CohortComparisonProps) {
  if (isLoading) {
    return (
      <section className="glass panel candidate-insights-drawer__section">
        <div className="cd-section-header">
          <div>
            <h2 className="cd-section-title">Сравнение с когортой</h2>
            <p className="subtitle">Собираю метрики по похожим кандидатам…</p>
          </div>
        </div>
      </section>
    )
  }

  if (!data || data.available === false || !data.total_candidates || data.total_candidates < 2) {
    return null
  }

  return (
    <section className="glass panel candidate-insights-drawer__section">
      <div className="cd-section-header">
        <div>
          <h2 className="cd-section-title">Сравнение с когортой</h2>
          <p className="subtitle">{data.cohort_label || 'Похожие кандидаты'} · {data.total_candidates} чел.</p>
        </div>
      </div>

      <div className="cohort-comparison__grid" data-testid="candidate-cohort-comparison">
        <div className="cohort-comparison__tile">
          <div className="cohort-comparison__tile-label">Ранг</div>
          <div className="cohort-comparison__tile-value">{data.rank ? `${data.rank}-й` : '—'}</div>
          <div className="cohort-comparison__tile-meta">из {data.total_candidates}</div>
        </div>
        <div className="cohort-comparison__tile cohort-comparison__tile--wide">
          <CohortBar label="Тест 1" candidateValue={data.test1?.candidate} averageValue={data.test1?.average} formatter={(value) => `${value.toFixed(1)}%`} />
        </div>
        <div className="cohort-comparison__tile cohort-comparison__tile--wide">
          <CohortBar label="Время прохождения" candidateValue={data.completion_time_sec?.candidate} averageValue={data.completion_time_sec?.average} formatter={formatMinutes} />
        </div>
        <div className="cohort-comparison__tile cohort-comparison__tile--span">
          <div className="cohort-comparison__tile-label">Этапы воронки</div>
          <div className="cohort-comparison__funnel">
            {(data.stage_distribution || []).map((item) => (
              <div key={item.key} className="cohort-comparison__funnel-row">
                <span>{item.label}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
