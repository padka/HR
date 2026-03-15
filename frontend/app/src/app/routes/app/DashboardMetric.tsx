import { memo } from 'react'

type DashboardMetricProps = {
  title: string
  value: number | string
}

export const DashboardMetric = memo(function DashboardMetric({ title, value }: DashboardMetricProps) {
  return (
    <article className="dashboard-metric kpi-card">
      <span className="kpi-label">{title}</span>
      <strong className="kpi-value">{value ?? '—'}</strong>
    </article>
  )
})
