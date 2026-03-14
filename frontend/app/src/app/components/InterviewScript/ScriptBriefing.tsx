type ScriptBriefingProps = {
  candidateName: string
  statusLabel: string
  test1Score?: number | null
  goal: string
  focusAreas: string[]
  flags: string[]
}

export default function ScriptBriefing({
  candidateName,
  statusLabel,
  test1Score,
  goal,
  focusAreas,
  flags,
}: ScriptBriefingProps) {
  return (
    <div className="interview-script__surface">
      <div className="interview-script__briefing-head">
        <div>
          <div className="interview-script__eyebrow">Перед звонком</div>
          <h3 className="interview-script__section-title">Брифинг</h3>
        </div>
        <div className="interview-script__briefing-metrics">
          <span className="interview-script__metric">
            <span className="interview-script__metric-label">Кандидат</span>
            <span className="interview-script__metric-value">{candidateName}</span>
          </span>
          <span className="interview-script__metric">
            <span className="interview-script__metric-label">Этап</span>
            <span className="interview-script__metric-value">{statusLabel}</span>
          </span>
          <span className="interview-script__metric">
            <span className="interview-script__metric-label">Тест 1</span>
            <span className="interview-script__metric-value">{typeof test1Score === 'number' ? `${test1Score.toFixed(1)}%` : '—'}</span>
          </span>
        </div>
      </div>

      <div className="interview-script__callout">
        <div className="interview-script__callout-label">Цель интервью</div>
        <p>{goal}</p>
      </div>

      {focusAreas.length > 0 && (
        <div className="interview-script__stack">
          <div className="interview-script__stack-title">На что обратить внимание</div>
          <ul className="interview-script__bullet-list">
            {focusAreas.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {flags.length > 0 && (
        <div className="interview-script__stack">
          <div className="interview-script__stack-title">Ключевые флаги</div>
          <div className="interview-script__chip-row">
            {flags.map((item) => (
              <span key={item} className="interview-script__chip">
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
