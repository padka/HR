export function isValidTimezone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat('ru-RU', { timeZone: tz }).format()
    return true
  } catch {
    return false
  }
}

export function formatTimeInTz(tz: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date())
  } catch {
    return ''
  }
}

export function getNextWeekDate(): string {
  const date = new Date()
  date.setDate(date.getDate() + 7)
  return date.toISOString().slice(0, 10)
}

export function getTodayDate(): string {
  return new Date().toISOString().slice(0, 10)
}
