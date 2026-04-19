import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateNewPage } from './candidate-new'

const apiFetchMock = vi.fn()
const useQueryMock = vi.fn()
const useMutationMock = vi.fn()
const navigateMock = vi.fn()

type QueryOptionsLike = {
  queryKey?: unknown
}

type MutationOptionsLike = {
  mutationFn?: () => Promise<unknown> | unknown
  onSuccess?: (data: unknown) => void
  onError?: (error: unknown) => void
}

vi.mock('@/api/client', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('@/app/components/RoleGuard', () => ({
  RoleGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useMutation: (options: unknown) => useMutationMock(options),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: ReactNode; to?: string }) => <a href={to || '#'}>{children}</a>,
  useNavigate: () => navigateMock,
}))

const cities = [{ id: 1, name: 'Москва', tz: 'Europe/Moscow' }]
const recruiters = [{ id: 2, name: 'Рекрутер', tz: 'Europe/Moscow', active: true }]

describe('CandidateNewPage submit flow', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    navigateMock.mockReset()

    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const key = Array.isArray(options?.queryKey) ? options.queryKey[0] : options?.queryKey
      if (key === 'cities') {
        return { data: cities, isLoading: false, isError: false }
      }
      if (key === 'recruiters') {
        return { data: recruiters, isLoading: false, isError: false }
      }
      return { data: undefined, isLoading: false, isError: false }
    })

    useMutationMock.mockImplementation((options: MutationOptionsLike) => ({
      isPending: false,
      mutate: () => {
        if (!options.mutationFn) return
        Promise.resolve()
          .then(async () => options.mutationFn?.())
          .then((data) => options.onSuccess?.(data))
          .catch((err) => options.onError?.(err))
      },
    }))
  })

  it('renders manual creation as default and hides telegram id input', () => {
    render(<CandidateNewPage />)

    expect(screen.queryByLabelText('Telegram ID')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Назначить собеседование сразу')).not.toBeChecked()
  })

  it('creates candidate without immediate scheduling by default', async () => {
    apiFetchMock.mockResolvedValueOnce({ id: 501, fio: 'Тест', city: 'Москва', slot_scheduled: false })

    render(<CandidateNewPage />)

    fireEvent.change(screen.getByPlaceholderText('Иван Иванов'), { target: { value: 'Тест Кандидат' } })
    fireEvent.click(screen.getByRole('button', { name: 'Создать кандидата' }))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({
        to: '/app/candidates/$candidateId',
        params: { candidateId: '501' },
      })
    })

    expect(apiFetchMock).toHaveBeenCalledTimes(1)
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      1,
      '/candidates',
      expect.objectContaining({ method: 'POST' }),
    )

    const [, request] = apiFetchMock.mock.calls[0] as [string, { body?: string }]
    expect(JSON.parse(request.body || '{}')).not.toHaveProperty('telegram_id')
    expect(JSON.parse(request.body || '{}')).not.toHaveProperty('interview_date')
  })

  it('shows warning and keeps candidate when schedule fails with missing telegram', async () => {
    apiFetchMock
      .mockResolvedValueOnce({ id: 502, fio: 'Тест', city: 'Москва', slot_scheduled: false })
      .mockRejectedValueOnce(
        Object.assign(new Error('У кандидата не привязан Telegram.'), {
          data: {
            error: 'candidate_telegram_missing',
            message: 'У кандидата не привязан Telegram.',
          },
        }),
      )

    render(<CandidateNewPage />)

    fireEvent.change(screen.getByPlaceholderText('Иван Иванов'), { target: { value: 'Кандидат Без TG' } })
    fireEvent.click(screen.getByLabelText('Назначить собеседование сразу'))
    fireEvent.click(screen.getByRole('button', { name: 'Создать кандидата' }))

    await waitFor(() => {
      expect(screen.getByText(/Кандидат создан как ручной лид\./)).toBeInTheDocument()
    })

    expect(navigateMock).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Открыть карточку кандидата' })).toBeInTheDocument()
    expect(apiFetchMock).toHaveBeenCalledTimes(2)
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      2,
      '/candidates/502/schedule-slot',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('creates and schedules candidate successfully', async () => {
    apiFetchMock
      .mockResolvedValueOnce({ id: 503, fio: 'Тест', city: 'Москва', slot_scheduled: false })
      .mockResolvedValueOnce({ status: 'pending_offer', message: 'Предложение отправлено кандидату' })

    render(<CandidateNewPage />)

    fireEvent.change(screen.getByPlaceholderText('Иван Иванов'), { target: { value: 'Кандидат С TG' } })
    fireEvent.change(screen.getByPlaceholderText('+7 900 000-00-00'), { target: { value: '+7 999 123-40-99' } })
    fireEvent.click(screen.getByLabelText('Назначить собеседование сразу'))
    fireEvent.click(screen.getByRole('button', { name: 'Создать кандидата' }))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({
        to: '/app/candidates/$candidateId',
        params: { candidateId: '503' },
      })
    })

    expect(apiFetchMock).toHaveBeenCalledTimes(2)
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      2,
      '/candidates/503/schedule-slot',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
