import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RecruitersPage } from './recruiters'

const apiFetchMock = vi.fn()
const useQueryMock = vi.fn()
const useMutationMock = vi.fn()
const invalidateQueriesMock = vi.fn()
const refetchMock = vi.fn()

type MutationOptionsLike = {
  mutationFn?: (variables: unknown) => Promise<unknown> | unknown
  onSuccess?: (data: unknown, variables: unknown) => void
  onError?: (error: unknown, variables: unknown) => void
}

const recruiters = [
  {
    id: 1,
    name: 'Анна Петрова',
    tz: 'Europe/Moscow',
    tg_chat_id: '1001',
    telemost_url: 'https://telemost.example/a',
    active: true,
    is_online: true,
    city_ids: [10, 11],
    cities: [{ name: 'Москва' }, { name: 'Тула' }],
    stats: { total: 8, free: 2, pending: 1, booked: 6 },
    next_free_local: '20 апр, 11:30',
    next_is_future: true,
  },
  {
    id: 2,
    name: 'Борис Смирнов',
    tz: 'Europe/Moscow',
    tg_chat_id: null,
    telemost_url: null,
    active: false,
    is_online: false,
    city_ids: [],
    cities: [],
    stats: { total: 0, free: 0, pending: 0, booked: 0 },
    next_free_local: null,
    next_is_future: false,
  },
]

let currentQueryState: {
  data?: typeof recruiters
  isLoading: boolean
  isError: boolean
  error: unknown
  refetch: () => unknown
}

vi.mock('@/api/client', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('@/app/components/RoleGuard', () => ({
  RoleGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    params: _params,
    ...props
  }: {
    children: ReactNode
    to?: string
    params?: unknown
    [key: string]: unknown
  }) => <a href={to || '#'} {...props}>{children}</a>,
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useMutation: (options: unknown) => useMutationMock(options),
  useQueryClient: () => ({
    invalidateQueries: (...args: unknown[]) => invalidateQueriesMock(...args),
  }),
}))

describe('RecruitersPage', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    apiFetchMock.mockReset()
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    invalidateQueriesMock.mockReset()
    refetchMock.mockReset()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    currentQueryState = {
      data: recruiters,
      isLoading: false,
      isError: false,
      error: null,
      refetch: refetchMock,
    }

    useQueryMock.mockImplementation(() => currentQueryState)
    useMutationMock.mockImplementation((options: MutationOptionsLike) => ({
      isPending: false,
      mutate: (variables: unknown) => {
        if (!options.mutationFn) return
        Promise.resolve()
          .then(async () => options.mutationFn?.(variables))
          .then((data) => options.onSuccess?.(data, variables))
          .catch((error) => options.onError?.(error, variables))
      },
    }))
  })

  it('renders grouped roster with summary cards', () => {
    render(<RecruitersPage />)

    expect(screen.getByTestId('recruiters-summary')).toHaveTextContent('В составе')

    const activeSection = screen.getByTestId('recruiters-active-section')
    const inactiveSection = screen.getByTestId('recruiters-inactive-section')

    expect(within(activeSection).getByText('Анна Петрова')).toBeInTheDocument()
    expect(within(activeSection).getByText('Нужно внимание')).toBeInTheDocument()
    expect(within(inactiveSection).getByText('Борис Смирнов')).toBeInTheDocument()
    expect(within(inactiveSection).getByText('Города пока не назначены')).toBeInTheDocument()
  })

  it('shows stronger empty state with create action', () => {
    currentQueryState = {
      data: [],
      isLoading: false,
      isError: false,
      error: null,
      refetch: refetchMock,
    }

    render(<RecruitersPage />)

    expect(screen.getByText('Реестр рекрутёров пока пуст')).toBeInTheDocument()
    expect(within(screen.getByRole('status')).getByRole('link', { name: '+ Добавить рекрутёра' })).toBeInTheDocument()
  })

  it('shows retry action when recruiters query fails', () => {
    currentQueryState = {
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Сервис недоступен'),
      refetch: refetchMock,
    }

    render(<RecruitersPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Обновить список' }))

    expect(refetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Сервис недоступен')).toBeInTheDocument()
  })

  it('keeps toggle payload unchanged and invalidates recruiters query', async () => {
    apiFetchMock.mockResolvedValueOnce({ ok: true })

    render(<RecruitersPage />)

    const annaRow = screen.getByText('Анна Петрова').closest('[data-testid="recruiter-row"]')
    expect(annaRow).not.toBeNull()

    fireEvent.click(within(annaRow as HTMLElement).getByLabelText('Оставить в составе'))

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/recruiters/1',
        expect.objectContaining({ method: 'PUT' }),
      )
    })

    const [, request] = apiFetchMock.mock.calls[0] as [string, { body?: string }]
    expect(JSON.parse(request.body || '{}')).toEqual({
      name: 'Анна Петрова',
      tz: 'Europe/Moscow',
      tg_chat_id: 1001,
      telemost_url: 'https://telemost.example/a',
      active: false,
      city_ids: [10, 11],
    })
    expect(invalidateQueriesMock).toHaveBeenCalledWith({ queryKey: ['recruiters'] })
  })

  it('preserves delete confirm flow', async () => {
    apiFetchMock.mockResolvedValueOnce({ ok: true })

    render(<RecruitersPage />)

    const annaRow = screen.getByText('Анна Петрова').closest('[data-testid="recruiter-row"]')
    expect(annaRow).not.toBeNull()

    fireEvent.click(within(annaRow as HTMLElement).getByRole('button', { name: 'Удалить' }))

    expect(window.confirm).toHaveBeenCalledWith('Удалить рекрутёра Анна Петрова?')

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/recruiters/1',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
    expect(invalidateQueriesMock).toHaveBeenCalledWith({ queryKey: ['recruiters'] })
  })
})
