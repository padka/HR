import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
                ai_relevance_score: 81,
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
                  ai_relevance_score: 81,
                  status: { slug: 'waiting_slot', label: 'Lead', tone: 'info' },
                  recruiter: { id: -1, name: 'Recruiter' },
                  lifecycle_summary: {
                    stage: 'waiting_interview_slot',
                    stage_label: 'Ожидает слот на интервью',
                    record_state: 'active',
                  },
                  candidate_actions: [],
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

    fireEvent.click(screen.getByLabelText('Действия для Иванов Иван'))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Удалить' }))

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/candidates/101',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
    expect(invalidateQueriesMock).toHaveBeenCalledWith({ queryKey: ['candidates'] })
  })

  it('renders candidates list as a compact registry view', () => {
    render(<CandidatesPage />)

    expect(screen.queryByTestId('candidates-work-queues')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /\+ Новый кандидат/i })).not.toBeInTheDocument()
    expect(screen.queryByText('Предложить время')).not.toBeInTheDocument()
    expect(screen.queryByText('Есть рассинхрон состояния')).not.toBeInTheDocument()
    expect(screen.queryByText(/workflow_status расходится/)).not.toBeInTheDocument()
    expect(screen.getByText('Кандидат')).toBeInTheDocument()
    expect(screen.getByText('Статус')).toBeInTheDocument()
    expect(screen.getByText('Релевантность')).toBeInTheDocument()
    expect(screen.getByText('Последняя активность')).toBeInTheDocument()
    expect(screen.getByText('Действия')).toBeInTheDocument()
    expect(screen.getByText('Иванов Иван')).toBeInTheDocument()
    expect(screen.getByText('Москва')).toBeInTheDocument()
    expect(screen.getAllByText('Ожидает слот на интервью').length).toBeGreaterThan(0)
    expect(screen.getByText('81%')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Действия для Иванов Иван'))
    expect(screen.getByRole('link', { name: 'Открыть профиль' })).toBeInTheDocument()
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

  it('keeps advanced list filters collapsed until explicitly opened', () => {
    render(<CandidatesPage />)

    expect(screen.queryByTestId('candidates-advanced-filters')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('candidates-advanced-filters-toggle'))

    expect(screen.getByTestId('candidates-advanced-filters')).toBeInTheDocument()
    expect(screen.getByText('Каналы и предпочтения')).toBeInTheDocument()
  })

  it('shows active filter strip for channel filters and allows clearing an individual filter', () => {
    render(<CandidatesPage />)

    fireEvent.click(screen.getByTestId('candidates-advanced-filters-toggle'))
    fireEvent.click(within(screen.getByTestId('candidates-channel-filter')).getByRole('button', { name: 'Telegram' }))

    expect(screen.getByTestId('candidates-active-filter-strip')).toBeInTheDocument()
    const clearChannelFilterButton = screen.getByRole('button', {
      name: 'Убрать фильтр Связанные каналы: Telegram',
    })
    expect(clearChannelFilterButton).toBeInTheDocument()

    fireEvent.click(clearChannelFilterButton)

    expect(screen.queryByRole('button', {
      name: 'Убрать фильтр Связанные каналы: Telegram',
    })).not.toBeInTheDocument()
  })
})
