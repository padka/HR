import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiFetchMock = vi.fn()

vi.mock('./client', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

import { candidateFetch, fetchCandidatePortalJourney } from './candidate'

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

  it('retries journey fetch without stored token when bootstrap needs cookie recovery', async () => {
    window.sessionStorage.setItem('candidate-portal:access-token', 'stored-portal-token')
    const portalError = Object.assign(new Error('Сессия портала истекла'), {
      status: 401,
      data: {
        detail: {
          code: 'portal_session_expired',
          state: 'recoverable',
          message: 'Сессия портала истекла. Попробуйте открыть кабинет заново.',
        },
      },
    })
    apiFetchMock
      .mockRejectedValueOnce(portalError)
      .mockResolvedValueOnce({
        candidate: { id: 1, candidate_id: 'cid' },
        journey: { current_step: 'profile' },
      })

    const payload = await fetchCandidatePortalJourney()

    expect(payload.candidate.id).toBe(1)
    expect(apiFetchMock).toHaveBeenCalledTimes(2)
    const firstCall = apiFetchMock.mock.calls[0]?.[1] as { headers?: Headers } | undefined
    const secondCall = apiFetchMock.mock.calls[1]?.[1] as { headers?: Headers } | undefined
    expect(firstCall?.headers?.get('x-candidate-portal-token')).toBe('stored-portal-token')
    expect(secondCall?.headers?.get('x-candidate-portal-token')).toBeNull()
    expect(window.sessionStorage.getItem('candidate-portal:access-token')).toBeNull()
  })
})
