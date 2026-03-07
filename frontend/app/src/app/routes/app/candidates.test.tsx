import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidatesPage } from './candidates'

const useQueryMock = vi.fn()
const useMutationMock = vi.fn()
const invalidateQueriesMock = vi.fn()
const apiFetchMock = vi.fn()

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

describe('CandidatesPage delete action', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    invalidateQueriesMock.mockReset()
    apiFetchMock.mockReset()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    useQueryMock.mockImplementation((options: any) => {
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
            views: { kanban: { columns: [] }, calendar: { days: [] } },
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

    useMutationMock.mockImplementation((options: any) => ({
      isPending: false,
      mutate: (variables: unknown) => {
        options.onMutate?.(variables)
        Promise.resolve()
          .then(async () => options.mutationFn(variables))
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

  it('moves candidate card in kanban and calls kanban-status api', async () => {
    useQueryMock.mockImplementation((options: any) => {
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
            views: {
              candidates: [
                {
                  id: 101,
                  fio: 'Иванов Иван',
                  city: 'Москва',
                  status: { slug: 'waiting_slot', label: 'Ждет назначения слота', tone: 'warning' },
                  recruiter: { id: -1, name: 'Recruiter' },
                },
              ],
              kanban: { columns: [] },
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
    apiFetchMock.mockResolvedValueOnce({ ok: true, message: 'ok', status: 'slot_pending' })

    render(<CandidatesPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Канбан' }))

    const card = screen.getByText('Иванов Иван').closest('[draggable="true"]')
    const targetColumn = document.querySelector('[data-kanban-column="slot_pending"]')
    const targetDropZone = targetColumn?.querySelector('.kanban__cards')
    expect(card).toBeTruthy()
    expect(targetDropZone).toBeTruthy()

    const dataTransfer = {
      data: {} as Record<string, string>,
      setData(type: string, value: string) {
        this.data[type] = value
      },
      getData(type: string) {
        return this.data[type]
      },
      effectAllowed: 'all',
      dropEffect: 'move',
    }

    fireEvent.dragStart(card as HTMLElement, { dataTransfer })
    fireEvent.dragOver(targetDropZone as HTMLElement, { dataTransfer })
    fireEvent.drop(targetDropZone as HTMLElement, { dataTransfer })

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/candidates/101/kanban-status',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ target_status: 'slot_pending' }),
        }),
      )
    })
  })
})
