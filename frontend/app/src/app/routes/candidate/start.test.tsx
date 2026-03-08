import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateStartPage } from './start'

const exchangeCandidatePortalTokenMock = vi.fn()
const navigateMock = vi.fn()
const setQueryDataMock = vi.fn()
const useParamsMock = vi.fn()

vi.mock('@/api/candidate', () => ({
  exchangeCandidatePortalToken: (...args: unknown[]) => exchangeCandidatePortalTokenMock(...args),
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
    navigateMock.mockReset()
    setQueryDataMock.mockReset()
    useParamsMock.mockReturnValue({ token: 'signed-token' })
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

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(screen.getByText('Ссылка устарела')).toBeInTheDocument()
    })
  })
})

