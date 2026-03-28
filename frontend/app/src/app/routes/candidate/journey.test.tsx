import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
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

vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, children, ...props }: { to: string; children?: ReactNode }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('./webapp', () => ({
  ensureCandidateWebAppBridge: () => Promise.resolve(null),
  markCandidateWebAppReady: () => readyMock(),
}))

describe('CandidateJourneyPage', () => {
  beforeEach(() => {
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    useQueryClientMock.mockReset()
    readyMock.mockReset()
    window.localStorage.clear()
    window.sessionStorage.clear()

    useQueryClientMock.mockReturnValue({
      setQueryData: vi.fn(),
      removeQueries: vi.fn(),
    })

    useMutationMock.mockImplementation(() => ({
        mutate: vi.fn(),
        mutateAsync: vi.fn(),
        isPending: false,
    }))

    useQueryMock.mockReturnValue({
      data: {
        dashboard: {
          primary_action: {
            key: 'complete_screening',
            label: 'Завершить анкету',
            description: 'Ответьте на короткую анкету. Прогресс сохранится автоматически.',
            target: 'workflow',
          },
          alerts: [
            {
              level: 'info',
              title: 'Есть обновление от рекрутера',
              body: 'Откройте раздел «Сообщения», чтобы продолжить диалог.',
            },
          ],
          upcoming_items: [
            {
              kind: 'interview',
              title: 'Собеседование',
              scheduled_at: '2026-03-19T10:00:00.000Z',
              timezone: 'Europe/Moscow',
              state: 'На подтверждении',
            },
          ],
        },
        company: {
          name: 'SMART SERVICE',
          summary: 'Вы проходите отбор в SMART SERVICE по вакансии «Менеджер по работе с клиентами».',
          highlights: [
            'Анкета и прогресс сохраняются автоматически',
            'Статус и следующий шаг видны в одном месте',
            'Запись на собеседование доступна из кабинета',
          ],
          faq: [
            {
              question: 'Как проходит отбор?',
              answer: 'Профиль, анкета, слот и обратная связь доступны в одном кабинете.',
            },
          ],
        },
        resources: {
          faq: [
            {
              question: 'Как проходит отбор?',
              answer: 'Профиль, анкета, слот и обратная связь доступны в одном кабинете.',
            },
          ],
          documents: [
            {
              key: 'process',
              title: 'Как устроен отбор',
              summary: 'Пошаговый путь кандидата',
            },
          ],
          contacts: [
            {
              label: 'Поддержка',
              value: 'Напишите в раздел «Сообщения».',
            },
          ],
        },
        tests: {
          items: [
            {
              key: 'screening',
              title: 'Короткая анкета',
              status: 'in_progress',
              status_label: 'В процессе',
              summary: 'Можно продолжить с текущего места.',
              question_count: 8,
            },
          ],
        },
        feedback: {
          items: [
            {
              kind: 'message',
              title: 'Сообщение от рекрутера',
              body: 'Проверьте детали собеседования.',
              author_role: 'recruiter',
              created_at: '2026-03-18T12:00:00.000Z',
            },
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
          last_entry_channel: 'max',
          available_channels: ['web', 'max', 'telegram'],
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
              requires_bot_start: true,
            },
            telegram: {
              channel: 'telegram',
              enabled: true,
              launch_url: 'https://t.me/example_bot?start=invite',
              type: 'external',
              requires_bot_start: true,
            },
          },
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
          inbox: {
            conversation_id: 'candidate:1',
            unread_count: null,
            read_tracking_supported: false,
            latest_message: null,
            delivery_state: 'sent',
            available_channels: ['web', 'max'],
          },
          cities: [],
        },
      },
      isLoading: false,
      isError: false,
      error: null,
    })

    window.history.pushState({}, '', '/candidate/journey')
  })

  it('renders web-first cabinet summary and navigation', () => {
    render(<CandidateJourneyPage />)

    expect(readyMock).toHaveBeenCalled()
    expect(screen.getByText('Candidate Cabinet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Главная' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Сообщения' })).toBeInTheDocument()
    expect(screen.getByText('Что нужно сделать сейчас')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Завершить анкету' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Web cabinet' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Открыть в MAX' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Открыть в Telegram' })).toBeInTheDocument()
    expect(screen.getAllByText('Компания').length).toBeGreaterThan(0)
    expect(screen.getAllByText('SMART SERVICE').length).toBeGreaterThan(0)
    expect(screen.getByText(/отбор в SMART SERVICE/i)).toBeInTheDocument()
    expect(screen.getByText(/Magic link \+ resume-cookie/i)).toBeInTheDocument()
    expect(screen.getByText(/web inbox/i)).toBeInTheDocument()
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

    expect(screen.getByText('Продолжим через выбор канала')).toBeInTheDocument()
    expect(screen.getByText(/безопасно вернёмся к выбору Web, MAX или Telegram/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Вернуться к выбору способа входа' })).toHaveAttribute('href', '/candidate/start?entry=hh-entry-token')
  })
})
