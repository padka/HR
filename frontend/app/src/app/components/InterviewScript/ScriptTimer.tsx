type ScriptTimerProps = {
  seconds: number
}

function formatElapsed(seconds: number) {
  const safe = Math.max(0, seconds)
  const mins = Math.floor(safe / 60)
  const secs = safe % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

export default function ScriptTimer({ seconds }: ScriptTimerProps) {
  return (
    <div className="interview-script__timer" aria-label={`Таймер интервью ${formatElapsed(seconds)}`}>
      <span className="interview-script__timer-label">Интервью</span>
      <span className="interview-script__timer-value">{formatElapsed(seconds)}</span>
    </div>
  )
}
