type DashboardMetricProps = {
  title: string
  value: number | string
}

export function DashboardMetric({ title, value }: DashboardMetricProps) {
  return (
    <article className="glass stat-card dashboard-metric">
      <span className="stat-label">{title}</span>
      <span className="stat-value">{value ?? '—'}</span>
    </article>
  )
}
