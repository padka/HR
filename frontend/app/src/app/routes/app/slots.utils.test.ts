import { describe, expect, it } from 'vitest'
import {
  buildStatusCounts,
  matchesStatusFilter,
  normalizeSlotStatus,
  slotCandidateIdentityLabel,
  slotDateForFilter,
  slotRecruiterTimeLabel,
  slotRegionTimeLabel,
  type SlotApiItem,
} from './slots.utils'

describe('slots.utils', () => {
  it('formats recruiter and region time using explicit time zones', () => {
    const row: SlotApiItem = {
      id: 1,
      start_utc: '2026-02-24T06:00:00+00:00',
      recruiter_tz: 'Europe/Moscow',
      candidate_tz: 'Asia/Almaty',
      tz_name: 'Asia/Almaty',
    }

    const recruiterTime = slotRecruiterTimeLabel(row)
    const regionTime = slotRegionTimeLabel(row)

    expect(recruiterTime).toContain('09:00')
    expect(regionTime).toContain('11:00')
    expect(slotDateForFilter(row)).toBe('2026-02-24')
  })

  it('aggregates booked summary with confirmed slots', () => {
    const rows: SlotApiItem[] = [
      { id: 1, start_utc: '2026-02-24T06:00:00+00:00', status: 'FREE' },
      { id: 2, start_utc: '2026-02-24T06:20:00+00:00', status: 'PENDING' },
      { id: 3, start_utc: '2026-02-24T06:40:00+00:00', status: 'BOOKED' },
      { id: 4, start_utc: '2026-02-24T07:00:00+00:00', status: 'CONFIRMED_BY_CANDIDATE' },
    ]

    const counts = buildStatusCounts(rows)

    expect(counts.total).toBe(4)
    expect(counts.free).toBe(1)
    expect(counts.pending).toBe(1)
    expect(counts.booked).toBe(2)
    expect(counts.confirmed).toBe(1)
  })

  it('matches booked filter for booked and confirmed statuses', () => {
    const booked: SlotApiItem = { id: 1, start_utc: '2026-02-24T06:00:00+00:00', status: 'BOOKED' }
    const confirmed: SlotApiItem = {
      id: 2,
      start_utc: '2026-02-24T06:20:00+00:00',
      status: 'CONFIRMED_BY_CANDIDATE',
    }
    const pending: SlotApiItem = { id: 3, start_utc: '2026-02-24T06:40:00+00:00', status: 'PENDING' }

    expect(matchesStatusFilter(booked, 'BOOKED')).toBe(true)
    expect(matchesStatusFilter(confirmed, 'BOOKED')).toBe(true)
    expect(matchesStatusFilter(pending, 'BOOKED')).toBe(false)
    expect(normalizeSlotStatus('confirmed_by_candidate')).toBe('CONFIRMED_BY_CANDIDATE')
  })

  it('renders MAX identity without falling back to Telegram-only wording', () => {
    const row: SlotApiItem = {
      id: 10,
      start_utc: '2026-02-24T06:00:00+00:00',
      candidate_fio: 'MAX Candidate',
      candidate_id: 100,
      candidate_tg_id: null,
      candidate_channel: 'max',
      candidate_channel_id: 'max-user-10',
      candidate_identity_label: 'MAX',
    }

    expect(slotCandidateIdentityLabel(row)).toBe('MAX')
  })

  it('keeps Telegram identity label for Telegram-backed slots', () => {
    const row: SlotApiItem = {
      id: 11,
      start_utc: '2026-02-24T06:00:00+00:00',
      candidate_tg_id: '777',
    }

    expect(slotCandidateIdentityLabel(row)).toBe('tg_id: 777')
  })
})
