import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidatesPage } from './candidates'

const useQueryMock = vi.fn()
const useMutationMock = vi.fn()
const invalidateQueriesMock = vi.fn()
const apiFetchMock = vi.fn()

type MutationOptionsLike = {
  mutationFn?: (variables: unknown) => Promise<unknown> | unknown
  onMutate?: (variables: unknown) => unknown
  onSuccess?: (data: unknown, variables: unknown) => void
  onError?: (error: unknown, variables: unknown) => void
  onSettled?: (data: unknown, error: unknown, variables: unknown, context: unknown) => void
}

type QueryOptionsLike = {
  queryKey?: unknown
  staleTime?: number
  refetchOnWindowFocus?: boolean
  refetchOnReconnect?: boolean
}

vi.mock('@/api/client', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('@/app/components/RoleGuard', () => ({
  RoleGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock('@/app/hooks/useProfile', () => ({
  useProfile: () => ({
    data: {
      principal: { type: 'admin', id: -1 },
    },
  }),
}))

vi.mock('@/app/hooks/useIsMobile', () => ({
  useIsMobile: () => false,
}))

vi.mock('framer-motion', () => ({
  motion: new Proxy({}, {
    get: (_target, tag: string) => ({ children, initial: _initial, animate: _animate, exit: _exit, variants: _variants, transition: _transition, layout: _layout, layoutId: _layoutId, whileInView: _whileInView, viewport: _viewport, ...props }: {
      children?: ReactNode
      initial?: unknown
      animate?: unknown
      exit?: unknown
      variants?: unknown
      transition?: unknown
      layout?: unknown
      layoutId?: unknown
      whileInView?: unknown
      viewport?: unknown
    }) =>
      createElement(tag, props, children),
  }),
  useReducedMotion: () => true,
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to }: { children: ReactNode; to?: string }) => <a href={to || '#'}>{children}</a>,
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useMutation: (options: unknown) => useMutationMock(options),
  useQueryClient: () => ({
    invalidateQueries: (...args: unknown[]) => invalidateQueriesMock(...args),
  }),
}))

describe('CandidatesPage', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    invalidateQueriesMock.mockReset()
    apiFetchMock.mockReset()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(window, 'open').mockImplementation(() => null)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    })

    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const key = Array.isArray(options?.queryKey) ? options.queryKey[0] : options?.queryKey
      if (key === 'candidates') {
        return {
          data: {
            items: [
              {
                id: 101,
                fio: 'Иванов Иван',
                city: 'Москва',
                status: { label: 'Lead', tone: 'info' },
                telegram_id: null,
                recruiter_id: -1,
              },
            ],
            total: 1,
            page: 1,
            pages_total: 1,
            filters: {
              state_options: [
                { value: '', label: 'Все кандидаты', kind: 'all' },
                { value: 'kanban:incoming', label: '📥 Входящие', kind: 'kanban', target_status: 'waiting_slot' },
              ],
            },
            views: {
              candidates: [
                {
                  id: 101,
                  fio: 'Иванов Иван',
                  city: 'Москва',
                  status: { slug: 'waiting_slot', label: 'Lead', tone: 'info' },
                  recruiter: { id: -1, name: 'Recruiter' },
                  lifecycle_summary: {
                    stage: 'waiting_interview_slot',
                    stage_label: 'Ожидает слот на интервью',
                    record_state: 'active',
                  },
                  candidate_next_action: {
                    urgency: 'attention',
                    primary_action: {
                      type: 'offer_interview_slot',
                      label: 'Предложить время',
                      enabled: true,
                    },
                  },
                  state_reconciliation: {
                    issues: [{ code: 'workflow_status_drift', message: 'workflow_status расходится.' }],
                    has_blockers: true,
                  },
                },
              ],
              kanban: {
                columns: [
                  {
                    slug: 'incoming',
                    label: 'Входящие',
                    icon: '📥',
                    target_status: 'waiting_slot',
                    droppable: false,
                    candidates: [],
                  },
                ],
              },
              calendar: { days: [] },
            },
          },
          isLoading: false,
          isError: false,
          error: null,
        }
      }
      if (key === 'cities') {
        return {
          data: [],
          isLoading: false,
          isError: false,
          error: null,
        }
      }
      if (key === 'ai-city-reco') {
        return {
          data: undefined,
          isLoading: false,
          isError: false,
          isFetching: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return {
        data: undefined,
        isLoading: false,
        isError: false,
        error: null,
      }
    })

    useMutationMock.mockImplementation((options: MutationOptionsLike) => ({
      isPending: false,
      mutate: (variables: unknown) => {
        if (!options.mutationFn) return
        options.onMutate?.(variables)
        Promise.resolve()
          .then(async () => options.mutationFn?.(variables))
          .then((data) => options.onSuccess?.(data, variables))
          .catch((error) => options.onError?.(error, variables))
          .finally(() => options.onSettled?.(undefined, undefined, variables, undefined))
      },
    }))
  })

  it('deletes candidate from list and invalidates candidates query', async () => {
    apiFetchMock.mockResolvedValueOnce({ ok: true, id: 101 })

    render(<CandidatesPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Удалить' }))

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/candidates/101',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
    expect(invalidateQueriesMock).toHaveBeenCalledWith({ queryKey: ['candidates'] })
  })

  it('renders contract-driven state cues in list view', () => {
    render(<CandidatesPage />)

    expect(screen.getByTestId('candidates-work-queues')).toBeInTheDocument()
    expect(screen.getByText('Очереди на странице')).toBeInTheDocument()
    expect(screen.getByText('Ожидает слот на интервью')).toBeInTheDocument()
    expect(screen.getByText('Предложить время')).toBeInTheDocument()
    expect(screen.getByText('Есть рассинхрон состояния')).toBeInTheDocument()
    expect(screen.getByText(/workflow_status расходится/)).toBeInTheDocument()
  })

  it('uses a bounded cache policy for candidate list and cities queries', () => {
    render(<CandidatesPage />)

    const candidatesQuery = useQueryMock.mock.calls.find(([options]) => {
      const rawKey = (options as QueryOptionsLike | undefined)?.queryKey
      return Array.isArray(rawKey) && rawKey[0] === 'candidates'
    })?.[0] as QueryOptionsLike | undefined
    expect(candidatesQuery?.staleTime).toBe(60_000)
    expect(candidatesQuery?.refetchOnWindowFocus).toBe(false)
    expect(candidatesQuery?.refetchOnReconnect).toBe(false)

    const citiesQuery = useQueryMock.mock.calls.find(([options]) => {
      const rawKey = (options as QueryOptionsLike | undefined)?.queryKey
      return Array.isArray(rawKey) && rawKey[0] === 'cities'
    })?.[0] as QueryOptionsLike | undefined
    expect(citiesQuery?.staleTime).toBe(60_000)
    expect(citiesQuery?.refetchOnWindowFocus).toBe(false)
    expect(citiesQuery?.refetchOnReconnect).toBe(false)
  })

  it('builds candidate query with canonical state filter parameter', async () => {
    render(<CandidatesPage />)

    fireEvent.change(screen.getByLabelText('Этап кандидата'), {
      target: { value: 'kanban:incoming' },
    })

    const candidatesQuery = [...useQueryMock.mock.calls].reverse().find(([options]) => {
      const rawKey = (options as QueryOptionsLike | undefined)?.queryKey
      return Array.isArray(rawKey) && rawKey[0] === 'candidates'
    })?.[0] as QueryOptionsLike | undefined

    apiFetchMock.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pages_total: 1,
      views: { candidates: [], kanban: { columns: [] }, calendar: { days: [] } },
    })

    await (candidatesQuery as QueryOptionsLike & { queryFn: () => Promise<unknown> }).queryFn()

    expect(apiFetchMock).toHaveBeenCalledWith(expect.stringContaining('state=kanban%3Aincoming'))
    expect(apiFetchMock).not.toHaveBeenCalledWith(expect.stringContaining('status='))
  })

  it('uses canonical target_column in kanban move requests', async () => {
    apiFetchMock.mockResolvedValueOnce({
      ok: true,
      status: 'test2_completed',
      candidate_id: 101,
      intent: { kind: 'kanban_move', target_column: 'test2_completed' },
      candidate_state: { operational_summary: { kanban_column: 'test2_completed' } },
    })

    render(<CandidatesPage />)

    const mutationOptions = useMutationMock.mock.calls[1]?.[0] as MutationOptionsLike | undefined
    expect(mutationOptions?.mutationFn).toBeTypeOf('function')

    await mutationOptions?.mutationFn?.({
      candidateId: 101,
      targetColumn: 'test2_completed',
      previousStatus: 'test2_sent',
    })

    expect(apiFetchMock).toHaveBeenCalledWith(
      '/candidates/101/kanban-status',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ target_column: 'test2_completed' }),
      }),
    )
  })

  it('groups kanban card by backend contract even when legacy status lags behind', () => {
    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const key = Array.isArray(options?.queryKey) ? options.queryKey[0] : options?.queryKey
      if (key === 'candidates') {
        return {
          data: {
            items: [
              {
                id: 101,
                fio: 'Иванов Иван',
                city: 'Москва',
                status: { slug: 'waiting_slot', label: 'Ждет назначения слота', tone: 'warning' },
                telegram_id: '777001',
                recruiter_id: -1,
              },
            ],
            total: 1,
            page: 1,
            pages_total: 1,
            filters: {
              state_options: [
                { value: '', label: 'Все кандидаты', kind: 'all' },
                { value: 'kanban:interview_confirmed', label: '✅ Подтвердил собеседование', kind: 'kanban', target_status: 'interview_confirmed' },
              ],
            },
            views: {
              candidates: [
                {
                  id: 101,
                  fio: 'Иванов Иван',
                  city: 'Москва',
                  status: { slug: 'waiting_slot', label: 'Ждет назначения слота', tone: 'warning' },
                  recruiter: { id: -1, name: 'Recruiter' },
                  lifecycle_summary: {
                    stage: 'interview',
                    stage_label: 'Интервью',
                    record_state: 'active',
                  },
                  scheduling_summary: {
                    status: 'confirmed',
                    status_label: 'Участие подтверждено',
                    active: true,
                  },
                },
              ],
              kanban: {
                columns: [
                  {
                    slug: 'incoming',
                    label: 'Входящие',
                    icon: '📥',
                    target_status: 'waiting_slot',
                    droppable: false,
                    candidates: [],
                  },
                  {
                    slug: 'interview_confirmed',
                    label: 'Подтвердил собеседование',
                    icon: '✅',
                    target_status: 'interview_confirmed',
                    candidates: [],
                  },
                ],
              },
              calendar: { days: [] },
            },
          },
          isLoading: false,
          isError: false,
          error: null,
        }
      }
      if (key === 'cities') {
        return {
          data: [],
          isLoading: false,
          isError: false,
          error: null,
        }
      }
      if (key === 'ai-city-reco') {
        return {
          data: undefined,
          isLoading: false,
          isError: false,
          isFetching: false,
          error: null,
          refetch: vi.fn(),
        }
      }
      return {
        data: undefined,
        isLoading: false,
        isError: false,
        error: null,
      }
    })

    render(<CandidatesPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Канбан' }))

    const sourceColumn = document.querySelector('[data-kanban-column="interview_confirmed"]')
    expect(sourceColumn?.textContent).toContain('Подтвердил собеседование')
    expect(sourceColumn?.textContent).toContain('Иванов Иван')
    expect(screen.getByText('Вести через действие')).toBeInTheDocument()
  })

  it('shows selection-only bulk triage bar without mutating candidates', async () => {
    render(<CandidatesPage />)

    fireEvent.click(screen.getByLabelText('Выбрать Иванов Иван'))

    expect(screen.getByTestId('candidates-selection-bar')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Открыть профили' }))
    expect(window.open).toHaveBeenCalledWith('/app/candidates/101', '_blank', 'noopener,noreferrer')

    fireEvent.click(screen.getByRole('button', { name: 'Скопировать ссылки' }))
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled()
    })

    expect(apiFetchMock).not.toHaveBeenCalledWith(
      expect.stringMatching(/\/actions\/|\/kanban-status|\/status/),
      expect.anything(),
    )
  })
})
