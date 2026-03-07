import { describe, expect, it } from 'vitest'

import {
  resolveIncomingDemoCount,
  withDemoIncomingCandidates,
  type IncomingCandidateLike,
} from './incoming-demo'

describe('incoming demo helper', () => {
  it('fills incoming candidates up to requested count', () => {
    const base: IncomingCandidateLike[] = [
      {
        id: 10,
        name: 'Базовый кандидат',
        city: 'Москва',
        city_id: 10,
      },
    ]

    const simulated = withDemoIncomingCandidates(base, {
      targetCount: 100,
      cityOptions: [
        { id: 10, name: 'Москва' },
        { id: 11, name: 'Ростов' },
      ],
    })

    expect(simulated).toHaveLength(100)
    expect(simulated[0].id).toBe(10)
    expect(simulated[99].id).toBeGreaterThan(900_000)
    expect(new Set(simulated.map((item) => item.status_slug)).size).toBeGreaterThan(1)
    expect(new Set(simulated.map((item) => item.city)).size).toBeGreaterThan(1)
  })

  it('does not modify list when target is lower than current size', () => {
    const base = Array.from({ length: 5 }, (_, idx) => ({ id: idx + 1 }))
    const simulated = withDemoIncomingCandidates(base, { targetCount: 3 })
    expect(simulated).toHaveLength(5)
    expect(simulated).toEqual(base)
  })

  it('resolves demo count from env/query/hostname', () => {
    expect(resolveIncomingDemoCount({ envValue: '120' })).toBe(120)
    expect(resolveIncomingDemoCount({ search: '?incoming_demo_count=88' })).toBe(88)
    expect(resolveIncomingDemoCount({ hostname: 'crm-test.internal' })).toBe(100)
    expect(resolveIncomingDemoCount({ hostname: 'localhost' })).toBe(0)
  })
})
