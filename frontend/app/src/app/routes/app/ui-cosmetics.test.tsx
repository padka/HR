import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateDetailPage } from './candidate-detail'
import { DashboardPage } from './dashboard'
import { IncomingPage } from './incoming'
import { MessengerPage } from './messenger'
import { SlotsPage } from './slots'

const useProfileMock = vi.fn()
const useQueryMock = vi.fn()
const useMutationMock = vi.fn()

vi.mock('@/app/components/RoleGuard', () => ({
  RoleGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock('@/app/hooks/useProfile', () => ({
  useProfile: () => useProfileMock(),
}))

vi.mock('@/api/client', () => ({
  apiFetch: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({
    children,
    to,
    params,
    hash,
    ...rest
  }: {
    children: ReactNode
    to?: string
    params?: Record<string, string>
    hash?: string
  }) => {
    let href = to || '#'
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        href = href.replace(`$${key}`, value)
      })
    }
    if (hash) {
      href = `${href}#${hash.replace(/^#/, '')}`
    }
    return <a href={href} {...rest}>{children}</a>
  },
  useParams: () => ({ candidateId: '101' }),
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useMutation: (options: unknown) => useMutationMock(options),
  useQueryClient: () => ({
    invalidateQueries: vi.fn(),
  }),
}))

const baseQueryResult = {
  data: undefined,
  isLoading: false,
  isFetching: false,
  isError: false,
  error: null,
  refetch: vi.fn(),
}

const candidateDetailData = {
  id: 101,
  fio: 'Тест Кандидат',
  city: 'Москва',
  telegram_id: 79990001122,
  is_active: true,
  workflow_status_label: 'Лид',
  candidate_status_slug: 'lead',
  status_is_terminal: false,
  candidate_actions: [],
  pipeline_stages: [],
  reschedule_request: {
    requested_at: '2031-06-30T09:00:00Z',
    requested_start_utc: '2031-07-02T09:00:00Z',
    requested_end_utc: '2031-07-02T12:00:00Z',
    requested_tz: 'Europe/Moscow',
    candidate_comment: 'Лучше утром',
  },
  test_sections: [
    {
      key: 'test1',
      title: 'Тест 1',
      status: 'passed',
      status_label: 'Пройден',
      summary: 'Анкета заполнена (3 ответа)',
      completed_at: '2031-07-01T08:15:00Z',
      details: {
        stats: {
          total_questions: 3,
          correct_answers: 2,
          raw_score: 2,
          final_score: 66.7,
          total_time: 780,
        },
        questions: [
          {
            question_index: 1,
            question_text: 'Опыт в подборе?',
            user_answer: '3 года',
            correct_answer: '3 года',
            attempts_count: 1,
            time_spent: 120,
            is_correct: true,
            overtime: false,
          },
          {
            question_index: 2,
            question_text: 'Готовы к сменному графику?',
            user_answer: 'Да',
            correct_answer: 'Да',
            attempts_count: 1,
            time_spent: 180,
            is_correct: true,
            overtime: false,
          },
          {
            question_index: 3,
            question_text: 'Какой ваш уровень Excel?',
            user_answer: 'Начальный',
            correct_answer: 'Средний',
            attempts_count: 1,
            time_spent: 240,
            is_correct: false,
            overtime: false,
          },
        ],
      },
    },
  ],
  slots: [],
  stats: {
    tests_total: 1,
    average_score: 66.7,
  },
}

const interviewScriptData = {
  ok: true,
  cached: true,
  input_hash: 'hash-1',
  script: {
    risk_flags: [{ code: 'SCHEDULE_RISK', severity: 'medium', reason: 'risk', question: 'q', recommended_phrase: 'p' }],
    highlights: ['h1'],
    checks: ['c1'],
    objections: [{ topic: 'obj', candidate_says: 'cand', recruiter_answer: 'ans' }],
    script_blocks: [{ id: 'b1', title: 'block', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] }],
    cta_templates: [{ type: 'next', text: 'text' }],
  },
}

const slotsData = [
  {
    id: 1,
    purpose: 'interview',
    status: 'FREE',
    city_name: 'Москва',
    recruiter_name: 'Рекрутер',
    start_utc: '2031-07-01T10:00:00Z',
    recruiter_tz: 'Europe/Moscow',
    tz_name: 'Europe/Moscow',
    candidate_tg_id: null,
    candidate_fio: null,
    candidate_id: null,
  },
]

const incomingData = {
  items: [
    {
      id: 11,
      name: 'Иван Петров',
      city: 'Москва',
      city_id: 1,
      status_display: 'Ожидает слот',
      status_slug: 'waiting_slot',
      waiting_hours: 3,
      requested_another_time: true,
      requested_another_time_at: '2031-07-01T08:30:00Z',
      requested_another_time_from: '2031-07-02T09:00:00Z',
      requested_another_time_to: '2031-07-02T12:00:00Z',
      requested_another_time_comment: 'Лучше утром',
      responsible_recruiter_id: 7,
      responsible_recruiter_name: 'Рекрутер',
    },
  ],
}

const candidateChatThreadsData = {
  threads: [
    {
      id: 11,
      candidate_id: 11,
      type: 'candidate',
      title: 'Иван Петров',
      city: 'Москва',
      status_label: 'Запросил другое время',
      profile_url: '/app/candidates/11',
      telegram_username: 'ivan_petrov',
      created_at: '2031-07-01T08:00:00Z',
      last_message_at: '2031-07-01T08:35:00Z',
      last_message: {
        text: 'Можете предложить утро?',
        created_at: '2031-07-01T08:35:00Z',
        direction: 'inbound',
      },
      unread_count: 1,
    },
  ],
  latest_event_at: '2031-07-01T08:35:00Z',
}

describe('UI cosmetics smoke', () => {
  beforeEach(() => {
    useProfileMock.mockReset()
    useQueryMock.mockReset()
    useMutationMock.mockReset()

    useProfileMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        principal: { type: 'recruiter', id: 7 },
        recruiter: { id: 7, tz: 'Europe/Moscow', cities: [{ id: 1, name: 'Москва' }] },
        profile: {
          city_options: [{ id: 1, name: 'Москва', tz: 'Europe/Moscow' }],
        },
      },
    })

    useMutationMock.mockImplementation(() => ({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
      data: undefined,
    }))

    useQueryMock.mockImplementation((options: any) => {
      const rawKey = options?.queryKey
      const key = Array.isArray(rawKey) ? rawKey[0] : rawKey

      if (key === 'dashboard-incoming') {
        return { ...baseQueryResult, data: incomingData }
      }
      if (key === 'incoming-available-slots') {
        return { ...baseQueryResult, data: { ok: true, items: [] } }
      }
      if (key === 'incoming-recruiters') {
        return { ...baseQueryResult, data: [] }
      }
      if (key === 'slots') {
        return { ...baseQueryResult, data: slotsData }
      }
      if (key === 'candidate-detail') {
        return { ...baseQueryResult, data: candidateDetailData }
      }
      if (key === 'candidate-chat') {
        return { ...baseQueryResult, data: { messages: [], has_more: false } }
      }
      if (key === 'candidate-chat-threads') {
        return { ...baseQueryResult, data: candidateChatThreadsData }
      }
      if (key === 'ai-interview-script') {
        return { ...baseQueryResult, data: interviewScriptData }
      }
      return { ...baseQueryResult }
    })
  })

  it('renders incoming filter bar and cards with stable test ids', () => {
    render(<IncomingPage />)
    const filterBar = screen.getByTestId('incoming-filter-bar')
    expect(filterBar).toBeInTheDocument()
    expect(filterBar).toHaveClass('filter-bar')

    const cards = screen.getAllByTestId('incoming-card')
    expect(cards.length).toBeGreaterThan(0)
    expect(cards[0]).toHaveClass('incoming-card')
    expect(document.querySelector('.status-pill')).toBeTruthy()

    const advancedToggle = screen.getByTestId('incoming-advanced-filters-toggle')
    fireEvent.click(advancedToggle)
    expect(document.querySelector('.ui-filter-bar__advanced--open')).toBeTruthy()

    const moreToggle = screen.getByTestId('incoming-card-more-toggle')
    fireEvent.click(moreToggle)
    expect(moreToggle).toHaveTextContent('Скрыть детали')
    expect(screen.getByText(/Хочет окно:/)).toBeInTheDocument()
  })

  it('opens test preview modal from incoming card actions and removes telegram shortcut', () => {
    render(<IncomingPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Тест' }))

    expect(screen.getByTestId('incoming-test-preview-modal')).toBeInTheDocument()
    expect(screen.getByText('Результат Теста 1')).toBeInTheDocument()
    expect(screen.getByText('Анкета заполнена (3 ответа)')).toBeInTheDocument()
    expect(screen.getByText('Опыт в подборе?')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Telegram' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('incoming-test-preview-schedule'))
    expect(screen.queryByTestId('incoming-test-preview-modal')).not.toBeInTheDocument()
    expect(screen.getByTestId('incoming-schedule-modal')).toBeInTheDocument()
  })

  it('shows timezone preview and reminder hint in incoming schedule modal', () => {
    render(<IncomingPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Предложить время' }))
    expect(screen.getByTestId('incoming-schedule-modal')).toBeInTheDocument()
    expect(screen.getByText('Вы назначаете')).toBeInTheDocument()
    expect(screen.getByText('Кандидат увидит')).toBeInTheDocument()
    expect(screen.getByText('Напоминание за 2 часа отправляется по времени кандидата.')).toBeInTheDocument()
  })

  it('uses expanded incoming workspace as recruiter dashboard default', () => {
    render(<DashboardPage />)
    const incomingFilterBar = screen.getByTestId('incoming-filter-bar')
    expect(incomingFilterBar).toBeInTheDocument()

    const incomingCard = screen.getByTestId('incoming-card')
    expect(incomingCard).toBeInTheDocument()
  })

  it('renders slots filter/table test ids', () => {
    render(<SlotsPage />)
    const filterBar = screen.getByTestId('slots-filter-bar')
    expect(filterBar).toBeInTheDocument()
    expect(filterBar).toHaveClass('slots-filters-grid')

    const table = screen.getByTestId('slots-table')
    expect(table).toBeInTheDocument()
    expect(table).toHaveClass('data-table')
    expect(document.querySelector('.status-badge')).toBeTruthy()
  })

  it('renders candidate header/actions and opens interview script modal', () => {
    render(<CandidateDetailPage />)
    expect(screen.getByTestId('candidate-header')).toBeInTheDocument()
    expect(screen.getByTestId('candidate-actions')).toBeInTheDocument()
    expect(screen.getByTestId('cd-ai-section-toggle-coach')).toBeInTheDocument()
    expect(screen.getByText(/Окно:/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Скрипт интервью' }))
    expect(screen.getByTestId('interview-script-modal')).toBeInTheDocument()
    expect(screen.getByTestId('cd-ai-section-toggle-risks')).toBeInTheDocument()
    expect(screen.getByTestId('cd-ai-section-toggle-objections')).toBeInTheDocument()
    expect(screen.getByTestId('cd-ai-section-toggle-cta')).toBeInTheDocument()
  })

  it('opens candidate tests section from hash on mobile', async () => {
    const previousHash = window.location.hash
    const previousWidth = window.innerWidth

    await act(async () => {
      window.location.hash = '#tests'
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        writable: true,
        value: 375,
      })

      render(<CandidateDetailPage />)
      window.dispatchEvent(new Event('resize'))
    })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Тесты' })).toHaveClass('ui-btn--primary')
    })
    expect(screen.getByTestId('candidate-tests-section')).toBeInTheDocument()

    await act(async () => {
      Object.defineProperty(window, 'innerWidth', {
        configurable: true,
        writable: true,
        value: previousWidth,
      })
      window.location.hash = previousHash
      window.dispatchEvent(new Event('resize'))
    })
  })

  it('renders messenger with candidate threads instead of staff chats', () => {
    render(<MessengerPage />)
    expect(screen.getByText('Чаты с кандидатами')).toBeInTheDocument()
    expect(screen.getAllByText('Иван Петров').length).toBeGreaterThan(0)
    expect(screen.getByText(/Можете предложить утро/)).toBeInTheDocument()
    expect(screen.queryByText('Новый чат')).not.toBeInTheDocument()
  })
})
