export type SlotApiItem = {
  id: number
  recruiter_id?: number | null
  recruiter_name?: string | null
  start_utc: string
  status?: string | null
  candidate_fio?: string | null
  candidate_tg_id?: string | null
  candidate_id?: number | null
  candidate_channel?: string | null
  candidate_channel_id?: string | number | null
  candidate_identity_label?: string | null
  tz_name?: string | null
  local_time?: string | null
  recruiter_tz?: string | null
  recruiter_local_time?: string | null
  candidate_tz?: string | null
  candidate_local_time?: string | null
  city_name?: string | null
  purpose?: string | null
}

export type SlotUiStatus =
  | 'FREE'
  | 'PENDING'
  | 'BOOKED'
  | 'CONFIRMED_BY_CANDIDATE'
  | 'UNKNOWN'

export type SlotStatusFilter = 'ALL' | 'FREE' | 'PENDING' | 'BOOKED' | 'CONFIRMED_BY_CANDIDATE'

export type SlotStatusCounts = {
  total: number
  free: number
  pending: number
  booked: number
  confirmed: number
  unknown: number
}

export function normalizeSlotStatus(status?: string | null): SlotUiStatus {
  const value = String(status || '')
    .trim()
    .toUpperCase()
  if (value === 'FREE') return 'FREE'
  if (value === 'PENDING') return 'PENDING'
  if (value === 'BOOKED') return 'BOOKED'
  if (value === 'CONFIRMED_BY_CANDIDATE') return 'CONFIRMED_BY_CANDIDATE'
  return 'UNKNOWN'
}

export function statusLabel(status?: string) {
  switch (normalizeSlotStatus(status)) {
    case 'FREE':
      return 'Свободен'
    case 'PENDING':
      return 'Ожидает'
    case 'BOOKED':
      return 'Согласован слот'
    case 'CONFIRMED_BY_CANDIDATE':
      return 'Подтверждён'
    default:
      return status || '—'
  }
}

export function slotPurpose(row: SlotApiItem): string {
  return row.purpose || 'interview'
}

export function slotHasCandidate(row: SlotApiItem): boolean {
  return Boolean(row.candidate_fio || row.candidate_tg_id || row.candidate_id || row.candidate_channel_id)
}

export function slotCandidateIdentityLabel(row: SlotApiItem): string {
  if (row.candidate_identity_label) return row.candidate_identity_label

  const channel = String(row.candidate_channel || '')
    .trim()
    .toLowerCase()
  if (channel === 'max') return 'MAX'
  if (row.candidate_tg_id) return `tg_id: ${row.candidate_tg_id}`
  if (row.candidate_channel_id) {
    return channel ? `${channel}: ${row.candidate_channel_id}` : `id: ${row.candidate_channel_id}`
  }
  return slotHasCandidate(row) ? 'Канал не привязан' : 'Назначьте кандидата'
}

export function slotRecruiterTz(row: SlotApiItem): string {
  return row.recruiter_tz || row.tz_name || 'Europe/Moscow'
}

export function slotRegionTz(row: SlotApiItem): string | null {
  return row.candidate_tz || row.tz_name || null
}

function formatInZone(value: string, tz: string): string {
  try {
    const d = new Date(value)
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz,
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d)
  } catch {
    return value
  }
}

function formatDateOnlyInZone(value: string, tz: string): string {
  try {
    const d = new Date(value)
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(d)
    const pick = (type: string) => parts.find((p) => p.type === type)?.value || ''
    return `${pick('year')}-${pick('month')}-${pick('day')}`
  } catch {
    return ''
  }
}

export function getDateTimeParts(iso: string, tz?: string | null) {
  try {
    const d = new Date(iso)
    const fmt = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz || 'Europe/Moscow',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
    const parts = fmt.formatToParts(d)
    const pick = (type: string) => parts.find((p) => p.type === type)?.value || ''
    const date = `${pick('year')}-${pick('month')}-${pick('day')}`
    const time = `${pick('hour')}:${pick('minute')}`
    return { date, time }
  } catch {
    return { date: '', time: '' }
  }
}

export function slotRecruiterTimeLabel(row: SlotApiItem): string {
  return formatInZone(row.start_utc, slotRecruiterTz(row))
}

export function slotRegionTimeLabel(row: SlotApiItem): string {
  const tz = slotRegionTz(row)
  if (!tz) return '—'
  return formatInZone(row.start_utc, tz)
}

export function slotRecruiterTimestamp(row: SlotApiItem): number {
  const ts = Date.parse(row.start_utc)
  return Number.isNaN(ts) ? 0 : ts
}

export function slotRegionTimestamp(row: SlotApiItem): number {
  const ts = Date.parse(row.start_utc)
  return Number.isNaN(ts) ? 0 : ts
}

export function slotDateForFilter(row: SlotApiItem): string {
  return formatDateOnlyInZone(row.start_utc, slotRecruiterTz(row))
}

export function buildStatusCounts(rows: SlotApiItem[]): SlotStatusCounts {
  const counts: SlotStatusCounts = {
    total: rows.length,
    free: 0,
    pending: 0,
    booked: 0,
    confirmed: 0,
    unknown: 0,
  }
  rows.forEach((row) => {
    const status = normalizeSlotStatus(row.status)
    if (status === 'FREE') counts.free += 1
    else if (status === 'PENDING') counts.pending += 1
    else if (status === 'BOOKED') counts.booked += 1
    else if (status === 'CONFIRMED_BY_CANDIDATE') {
      counts.confirmed += 1
      counts.booked += 1
    } else {
      counts.unknown += 1
    }
  })
  return counts
}

export function matchesStatusFilter(row: SlotApiItem, filter: SlotStatusFilter): boolean {
  if (filter === 'ALL') return true
  const status = normalizeSlotStatus(row.status)
  if (filter === 'BOOKED') {
    return status === 'BOOKED' || status === 'CONFIRMED_BY_CANDIDATE'
  }
  return status === filter
}
