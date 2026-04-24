import { describe, expect, it } from 'vitest'

import {
  clearIncomingPersistedFilters,
  loadIncomingPersistedFilters,
  parseIncomingPersistedFilters,
  saveIncomingPersistedFilters,
  type IncomingPersistedFilters,
} from './incoming.filters'

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

describe('incoming.filters', () => {
  it('parses valid payload and sanitizes invalid enums', () => {
    const payload = parseIncomingPersistedFilters(
      JSON.stringify({
        search: 'иванов',
        cityFilter: '10',
        statusFilter: 'requested_other_time',
        channelFilter: 'max',
        ownerFilter: 'mine',
        waitingFilter: '48h',
        aiFilter: 'high',
        sortMode: 'ai_score_desc',
        showAdvancedFilters: true,
      }),
    )
    expect(payload).toEqual({
      search: 'иванов',
      cityFilter: '10',
      statusFilter: 'requested_other_time',
      channelFilter: 'max',
      ownerFilter: 'mine',
      waitingFilter: '48h',
      aiFilter: 'high',
      sortMode: 'ai_score_desc',
      showAdvancedFilters: true,
    })

    const broken = parseIncomingPersistedFilters(
      JSON.stringify({
        statusFilter: 'wrong',
        channelFilter: 'oops',
        ownerFilter: 'oops',
        waitingFilter: 'oops',
        aiFilter: 'oops',
        sortMode: 'oops',
      }),
    )
    expect(broken).toEqual(
      expect.objectContaining({
        statusFilter: 'all',
        channelFilter: 'all',
        ownerFilter: 'all',
        waitingFilter: 'all',
        aiFilter: 'all',
        sortMode: 'priority',
      }),
    )
  })

  it('saves, loads and clears payload', () => {
    const storage = new MemoryStorage()
    const payload: IncomingPersistedFilters = {
      search: 'тест',
      cityFilter: 'all',
      statusFilter: 'waiting_slot',
      channelFilter: 'telegram',
      ownerFilter: 'assigned',
      waitingFilter: '24h',
      aiFilter: 'medium',
      sortMode: 'recent_desc',
      showAdvancedFilters: false,
    }

    saveIncomingPersistedFilters(storage, payload, 'incoming-key')
    expect(loadIncomingPersistedFilters(storage, 'incoming-key')).toEqual(payload)

    clearIncomingPersistedFilters(storage, 'incoming-key')
    expect(loadIncomingPersistedFilters(storage, 'incoming-key')).toEqual({})
  })
})
