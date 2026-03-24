import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiFetchMock = vi.fn()

vi.mock('./client', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

import { candidateFetch } from './candidate'

describe('candidateFetch', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    window.sessionStorage.clear()
  })

  it('skips csrf preflight for public candidate portal calls', async () => {
    window.sessionStorage.setItem('candidate-portal:access-token', 'stored-portal-token')
    apiFetchMock.mockResolvedValueOnce({ ok: true })

    await candidateFetch('/journey')

    expect(apiFetchMock).toHaveBeenCalledWith(
      '/candidate/journey',
      expect.objectContaining({
        skipCsrf: true,
        headers: expect.any(Headers),
      }),
    )
    const [, init] = apiFetchMock.mock.calls[0]
    expect((init as { headers?: Headers }).headers?.get('x-candidate-portal-token')).toBe(
      'stored-portal-token',
    )
  })
})
