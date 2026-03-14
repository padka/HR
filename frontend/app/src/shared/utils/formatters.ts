export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTzOffset(tz: string): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    })
    const parts = formatter.formatToParts(new Date())
    const offsetPart = parts.find((part) => part.type === 'timeZoneName')
    return offsetPart?.value || tz
  } catch {
    return tz
  }
}

export function getTomorrowDate(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

export function formatSlotTime(startUtc: string | null | undefined, tz: string | null | undefined): string {
  if (!startUtc) return '—'
  try {
    const date = new Date(startUtc)
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz || 'Europe/Moscow',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  } catch {
    return startUtc
  }
}

export function formatSecondsToMinutes(value?: number | null): string {
  if (typeof value !== 'number' || value <= 0) return '—'
  return `${Math.max(1, Math.round(value / 60))} мин`
}
