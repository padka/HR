import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateJourneyPage } from './journey'

const useQueryMock = vi.fn()
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
  }
})

vi.mock('./webapp', () => ({
  ensureCandidateWebAppBridge: () => Promise.resolve(null),
  markCandidateWebAppReady: () => readyMock(),
}))

describe('CandidateJourneyPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    readyMock.mockReset()
    window.localStorage.clear()
    window.sessionStorage.clear()

    useQueryMock.mockReturnValue({
      data: {
        dashboard: {
          alerts: [
            {
              level: 'info',
              title: 'Рекрутер проверяет результаты',
              body: 'После прохождения Test 1 решение по слоту уйдёт в мессенджер.',
            },
          ],
        },
        company: {
          name: 'SMART SERVICE',
        },
        history: {
          items: [
            {
              kind: 'journey',
              title: 'Открыт кабинет кандидата',
              body: 'Кандидат открыл путь в кабинете.',
              created_at: '2026-04-05T07:40:00.000Z',
              status_label: 'Профиль',
            },
          ],
        },
        candidate: {
          id: 1,
          candidate_id: 'cid',
          fio: 'Иванов Иван Иванович',
          city: 'Москва',
          status_label: 'Ожидает слот',
          vacancy_label: 'Менеджер по работе с клиентами',
          entry_url: 'https://crm.example.test/candidate/start?entry=hh-entry-token',
        },
        journey: {
          session_id: 7,
          journey_key: 'candidate',
          journey_version: 'v1',
          entry_channel: 'max',
          current_step: 'screening',
          current_step_label: 'Тест 1',
          next_action: 'Пройдите Test 1 в MAX. После завершения анкета появится в CRM.',
          next_step_at: '2026-04-05T08:00:00.000Z',
          next_step_timezone: 'Europe/Moscow',
          steps: [
            { key: 'screening', label: 'Тест 1', status: 'in_progress' },
            { key: 'profile', label: 'Профиль в CRM', status: 'pending' },
            { key: 'slot_selection', label: 'Слот', status: 'pending' },
            { key: 'status', label: 'Обратная связь', status: 'pending' },
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
          },
          slots: {
            available: [],
            active: null,
          },
          messages: [],
          cities: [],
          channel_options: {
            web: {
              channel: 'web',
              enabled: true,
              launch_url: 'https://crm.example.test/candidate/start?start=web-token',
              type: 'cabinet',
              requires_bot_start: false,
            },
            max: {
              channel: 'max',
              enabled: true,
              launch_url: 'https://max.example.test/start',
              type: 'external',
              requires_bot_start: false,
            },
            telegram: {
              channel: 'telegram',
              enabled: true,
              launch_url: 'https://t.me/example_bot?start=invite',
              type: 'external',
              requires_bot_start: true,
            },
          },
        },
      },
      isLoading: false,
      isError: false,
      error: null,
    })

    window.history.pushState({}, '', '/candidate/journey')
  })

  it('renders messenger-first live state and removes cabinet copy', () => {
    render(<CandidateJourneyPage />)

    expect(readyMock).toHaveBeenCalled()
    expect(screen.getByText('Путь кандидата в мессенджере')).toBeInTheDocument()
    expect(screen.getByText('Что происходит дальше')).toBeInTheDocument()
    expect(screen.getByText('CRM ↔ Messenger')).toBeInTheDocument()
    expect(screen.getByText('Как это работает с Telegram')).toBeInTheDocument()
    expect(screen.getByText('Резервный вход в браузере')).toBeInTheDocument()
    expect(screen.getByText('История пути')).toBeInTheDocument()
    expect(screen.getByText('Открыт кабинет кандидата')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть MAX' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть Telegram' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть в браузере' })).toHaveAttribute(
      'href',
      'https://crm.example.test/candidate/start?start=web-token',
    )
    expect(screen.queryByText('Кабинет кандидата')).not.toBeInTheDocument()
    expect(screen.queryByText('Тесты и анкеты')).not.toBeInTheDocument()
    expect(screen.queryByText(/Web cabinet/i)).not.toBeInTheDocument()
  })

  it('renders preview messenger scenarios without live queries', () => {
    window.history.pushState({}, '', '/candidate/journey?preview=1')

    render(<CandidateJourneyPage />)

    expect(useQueryMock).not.toHaveBeenCalled()
    expect(screen.getByText('Messenger-first candidate flow')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Test 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Слот назначен' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Обратная связь' })).toBeInTheDocument()
  })

  it('switches preview scenarios and updates the status copy', () => {
    window.history.pushState({}, '', '/candidate/journey?preview=1')

    render(<CandidateJourneyPage />)

    expect(screen.getByText('Ожидаем завершение')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Слот назначен' }))
    expect(screen.getByText('Ждём подтверждение')).toBeInTheDocument()
    expect(screen.getByText(/Кандидат получил сообщение о встрече/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Обратная связь' }))
    expect(screen.getByText('Ожидаем ответ')).toBeInTheDocument()
    expect(screen.getAllByText('Telegram').length).toBeGreaterThan(0)
  })

  it('uses a bounded cache policy for the candidate portal journey', () => {
    render(<CandidateJourneyPage />)

    const queryOptions = useQueryMock.mock.calls[0]?.[0] as QueryOptionsLike | undefined
    expect(queryOptions?.staleTime).toBe(60_000)
    expect(queryOptions?.refetchOnWindowFocus).toBe(false)
    expect(queryOptions?.refetchOnReconnect).toBe(false)
  })

  it('renders a recovery screen for stale candidate portal sessions', () => {
    window.localStorage.setItem('candidate-portal:entry-token', 'hh-entry-token')
    useQueryMock.mockReturnValue({
      data: null,
      isLoading: false,
      isError: true,
      error: Object.assign(new Error('Сессия портала устарела'), {
        status: 401,
        data: {
          detail: {
            code: 'portal_session_version_mismatch',
            state: 'needs_new_link',
            message: 'Сессия портала устарела. Откройте новую ссылку.',
          },
        },
      }),
    })

    render(<CandidateJourneyPage />)

    expect(screen.getByText('Нужно открыть новую ссылку')).toBeInTheDocument()
    expect(screen.getByText(/сессия портала устарела/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Вернуться на старт' })).toHaveAttribute('href', '/candidate/start?entry=hh-entry-token')
  })
})
