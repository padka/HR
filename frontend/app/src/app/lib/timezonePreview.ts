export type SlotTimePreview = {
  recruiterTz: string
  candidateTz: string
  recruiterLabel: string
  candidateLabel: string
}

function getOffsetMinutes(date: Date, tz: string): number {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  const parts = dtf.formatToParts(date)
  const map = new Map(parts.map((p) => [p.type, p.value]))
  const asUTC = Date.UTC(
    Number(map.get('year')),
    Number(map.get('month')) - 1,
    Number(map.get('day')),
    Number(map.get('hour')),
    Number(map.get('minute')),
    Number(map.get('second')),
  )
  return (asUTC - date.getTime()) / 60000
}

function localToUtc(date: string, time: string, sourceTz: string): Date | null {
  if (!date || !time) return null
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d) || !Number.isFinite(hh) || !Number.isFinite(mm)) {
    return null
  }
  const utcGuess = new Date(Date.UTC(y, m - 1, d, hh, mm, 0, 0))
  const offset = getOffsetMinutes(utcGuess, sourceTz)
  return new Date(utcGuess.getTime() - offset * 60000)
}

function formatInTz(date: Date, tz: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: tz,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Moscow'
}

export function formatTzOffset(tz: string): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    })
    const parts = formatter.formatToParts(new Date())
    const offsetPart = parts.find((p) => p.type === 'timeZoneName')
    return offsetPart?.value || tz
  } catch {
    return tz
  }
}

export function buildSlotTimePreview(
  date: string,
  time: string,
  recruiterTz: string,
  candidateTz: string,
): SlotTimePreview | null {
  const utc = localToUtc(date, time, recruiterTz)
  if (!utc) return null
  return {
    recruiterTz,
    candidateTz,
    recruiterLabel: formatInTz(utc, recruiterTz),
    candidateLabel: formatInTz(utc, candidateTz),
  }
}
