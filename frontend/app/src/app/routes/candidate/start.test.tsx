import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateStartPage } from './start'

const exchangeCandidatePortalTokenMock = vi.fn()
const fetchCandidatePortalJourneyMock = vi.fn()
const parseCandidatePortalErrorMock = vi.fn()
const navigateMock = vi.fn()
const setQueryDataMock = vi.fn()
const useParamsMock = vi.fn()

vi.mock('@/api/candidate', () => ({
  exchangeCandidatePortalToken: (...args: unknown[]) => exchangeCandidatePortalTokenMock(...args),
  fetchCandidatePortalJourney: (...args: unknown[]) => fetchCandidatePortalJourneyMock(...args),
  parseCandidatePortalError: (...args: unknown[]) => parseCandidatePortalErrorMock(...args),
}))

vi.mock('@/api/client', () => ({
  queryClient: {
    setQueryData: (...args: unknown[]) => setQueryDataMock(...args),
  },
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
  useParams: () => useParamsMock(),
}))

describe('CandidateStartPage', () => {
  beforeEach(() => {
    exchangeCandidatePortalTokenMock.mockReset()
    fetchCandidatePortalJourneyMock.mockReset()
    parseCandidatePortalErrorMock.mockReset()
    navigateMock.mockReset()
    setQueryDataMock.mockReset()
    useParamsMock.mockReturnValue({ token: 'signed-token' })
    window.history.pushState({}, '', '/candidate/start')
    window.sessionStorage.clear()
    ;(window as typeof window & { WebApp?: unknown }).WebApp = undefined
    ;(window as typeof window & { Telegram?: unknown }).Telegram = undefined
  })

  it('exchanges token and redirects into journey', async () => {
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('signed-token')
      expect(setQueryDataMock).toHaveBeenCalledWith(
        ['candidate-portal-journey'],
        expect.objectContaining({
          candidate: expect.objectContaining({ id: 1 }),
        }),
      )
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('shows portal error when exchange fails', async () => {
    exchangeCandidatePortalTokenMock.mockRejectedValue(new Error('Ссылка устарела'))
    parseCandidatePortalErrorMock.mockReturnValue({
      message: 'Ссылка устарела',
      state: 'needs_new_link',
      status: 401,
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(screen.getByText('Нужна новая ссылка')).toBeInTheDocument()
      expect(screen.getByText('Ссылка устарела')).toBeInTheDocument()
    })
  })

  it('falls back to the existing portal session when exchange token is stale', async () => {
    exchangeCandidatePortalTokenMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    fetchCandidatePortalJourneyMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(fetchCandidatePortalJourneyMock).toHaveBeenCalled()
      expect(setQueryDataMock).toHaveBeenCalledWith(
        ['candidate-portal-journey'],
        expect.objectContaining({
          candidate: expect.objectContaining({ id: 1 }),
        }),
      )
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('opens existing portal session when token is missing but cookie session exists', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.clear()
    fetchCandidatePortalJourneyMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(fetchCandidatePortalJourneyMock).toHaveBeenCalled()
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('uses MAX start_param from bridge when direct token is missing', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.clear()
    window.history.pushState({}, '', '/candidate/start')
    const readyMock = vi.fn()
    ;(window as typeof window & { WebApp?: { initDataUnsafe?: { start_param?: string }; ready?: () => void } }).WebApp = {
      initDataUnsafe: { start_param: 'max-invite-token' },
      ready: readyMock,
    }
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(readyMock).toHaveBeenCalled()
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('max-invite-token')
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('supports startapp query parameter fallback', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.clear()
    window.history.pushState({}, '', '/candidate/start?startapp=query-token')
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('query-token')
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('prefers fresh startapp token over stale session storage token', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.setItem('candidate-portal:access-token', 'stale-token')
    window.history.pushState({}, '', '/candidate/start?startapp=fresh-token')
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('fresh-token')
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('does not fall back to stale stored token when a fresh link fails', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.setItem('candidate-portal:access-token', 'stale-token')
    window.history.pushState({}, '', '/candidate/start?startapp=fresh-token')
    exchangeCandidatePortalTokenMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    fetchCandidatePortalJourneyMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    parseCandidatePortalErrorMock.mockImplementation((error: unknown) => ({
      message: error instanceof Error ? error.message : 'Ссылка устарела',
      state: 'needs_new_link',
      status: 401,
    }))

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(fetchCandidatePortalJourneyMock).toHaveBeenCalledWith({ skipStoredPortalToken: true })
      expect(screen.getByText('Нужна новая ссылка')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Запросить новую ссылку у рекрутера' })).toBeInTheDocument()
    })
  })
})
