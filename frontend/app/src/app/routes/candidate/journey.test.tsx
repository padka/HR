import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateJourneyPage } from './journey'

const useQueryMock = vi.fn()
const useMutationMock = vi.fn()
const useQueryClientMock = vi.fn()
const readyMock = vi.fn()

type QueryOptionsLike = {
  staleTime?: number
  refetchOnWindowFocus?: boolean
  refetchOnReconnect?: boolean
}

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>()
  return {
    ...actual,
    useQuery: (...args: unknown[]) => useQueryMock(...args),
    useMutation: (...args: unknown[]) => useMutationMock(...args),
    useQueryClient: () => useQueryClientMock(),
  }
})

vi.mock('./webapp', () => ({
  markCandidateWebAppReady: () => readyMock(),
}))

describe('CandidateJourneyPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    useQueryClientMock.mockReset()
    readyMock.mockReset()

    useQueryClientMock.mockReturnValue({
      setQueryData: vi.fn(),
      removeQueries: vi.fn(),
    })

    useMutationMock.mockImplementation(() => ({
      mutate: vi.fn(),
      isPending: false,
    }))

    useQueryMock.mockReturnValue({
      data: {
        company: {
          name: 'SMART SERVICE',
          summary: 'Вы проходите отбор в SMART SERVICE по вакансии «Менеджер по работе с клиентами».',
          highlights: [
            'Анкета и прогресс сохраняются автоматически',
            'Статус и следующий шаг видны в одном месте',
            'Запись на собеседование доступна из кабинета',
          ],
        },
        candidate: {
          fio: 'Иванов Иван Иванович',
          phone: '+79991112233',
          city: 'Москва',
          status_label: 'В работе',
          vacancy_label: 'Менеджер по работе с клиентами',
          vacancy_position: 'Менеджер по работе с клиентами',
          vacancy_reference: '12345',
        },
        journey: {
          current_step: 'screening',
          current_step_label: 'Анкета',
          next_action: 'Ответьте на короткую анкету. Прогресс сохранится автоматически.',
          next_step_at: '2026-03-19T10:00:00.000Z',
          next_step_timezone: 'Europe/Moscow',
          entry_channel: 'max',
          steps: [
            { key: 'profile', label: 'Профиль', status: 'completed' },
            { key: 'screening', label: 'Анкета', status: 'in_progress' },
            { key: 'slot_selection', label: 'Собеседование', status: 'pending' },
            { key: 'status', label: 'Статус', status: 'pending' },
          ],
          profile: {
            fio: 'Иванов Иван Иванович',
            phone: '+79991112233',
            city_id: 1,
            city_name: 'Москва',
          },
          screening: {
            questions: [],
            draft_answers: {},
            completed: false,
            completed_at: null,
          },
          slots: {
            available: [],
            active: null,
          },
          messages: [],
          cities: [],
        },
      },
      isLoading: false,
      isError: false,
      error: null,
    })

    window.history.pushState({}, '', '/candidate/journey')
  })

  it('renders company context in the cabinet summary', () => {
    render(<CandidateJourneyPage />)

    expect(readyMock).toHaveBeenCalled()
    expect(screen.getByText('Компания')).toBeInTheDocument()
    expect(screen.getByText('SMART SERVICE')).toBeInTheDocument()
    expect(screen.getByText(/отбор в SMART SERVICE/i)).toBeInTheDocument()
    expect(screen.getByText(/Анкета и прогресс сохраняются автоматически/i)).toBeInTheDocument()
  })

  it('uses a bounded cache policy for the candidate portal journey', () => {
    render(<CandidateJourneyPage />)

    const queryOptions = useQueryMock.mock.calls[0]?.[0] as QueryOptionsLike | undefined
    expect(queryOptions?.staleTime).toBe(60_000)
    expect(queryOptions?.refetchOnWindowFocus).toBe(false)
    expect(queryOptions?.refetchOnReconnect).toBe(false)
  })
})
