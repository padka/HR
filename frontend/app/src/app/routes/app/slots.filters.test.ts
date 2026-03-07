import { describe, expect, it } from 'vitest'

import {
  clearSlotsPersistedFilters,
  loadSlotsPersistedFilters,
  parseSlotsPersistedFilters,
  saveSlotsPersistedFilters,
  type SlotsPersistedFilters,
} from './slots.filters'

class MemoryStorage {
  private data = new Map<string, string>()

  getItem(key: string): string | null {
    return this.data.get(key) ?? null
  }

  setItem(key: string, value: string): void {
    this.data.set(key, value)
  }

  removeItem(key: string): void {
    this.data.delete(key)
  }
}

describe('slots.filters', () => {
  it('parses valid payload and applies defaults for invalid values', () => {
    const payload = parseSlotsPersistedFilters(
      JSON.stringify({
        statusFilter: 'FREE',
        sortField: 'city',
        sortDir: 'asc',
        page: 5,
        perPage: 50,
        limit: 300,
        candidateFilter: 'with',
        tzRelationFilter: 'same',
        purposeFilter: 'intro_day',
        search: 'иванов',
        cityFilter: 'Москва',
        recruiterFilter: 'Петров',
        dateFrom: '2026-02-01',
        dateTo: '2026-02-20',
      }),
    )

    expect(payload.statusFilter).toBe('FREE')
    expect(payload.sortField).toBe('city')
    expect(payload.sortDir).toBe('asc')
    expect(payload.page).toBe(5)
    expect(payload.perPage).toBe(50)
    expect(payload.limit).toBe(300)
    expect(payload.purposeFilter).toBe('intro_day')
  })

  it('returns safe defaults for malformed json', () => {
    expect(parseSlotsPersistedFilters('{bad_json')).toEqual({})
    expect(parseSlotsPersistedFilters(JSON.stringify({ statusFilter: 'BROKEN', page: -1 }))).toEqual(
      expect.objectContaining({
        statusFilter: 'ALL',
        page: 1,
      }),
    )
  })

  it('saves, loads and clears local payload', () => {
    const storage = new MemoryStorage()
    const payload: SlotsPersistedFilters = {
      statusFilter: 'BOOKED',
      purposeFilter: 'all',
      search: 'tg',
      cityFilter: 'all',
      recruiterFilter: 'all',
      candidateFilter: 'all',
      tzRelationFilter: 'all',
      dateFrom: '',
      dateTo: '',
      sortField: 'recruiter_time',
      sortDir: 'desc',
      limit: 500,
      page: 2,
      perPage: 20,
    }

    saveSlotsPersistedFilters(storage, payload, 'test-key')
    const loaded = loadSlotsPersistedFilters(storage, 'test-key')
    expect(loaded).toEqual(payload)

    clearSlotsPersistedFilters(storage, 'test-key')
    expect(loadSlotsPersistedFilters(storage, 'test-key')).toEqual({})
  })
})
