import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateDetailPage } from './candidate-detail'
import { DashboardPage } from './dashboard'
import { IncomingPage } from './incoming'
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
  Link: ({ children, ...rest }: { children: ReactNode }) => <a {...rest}>{children}</a>,
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
  test_sections: [],
  slots: [],
  stats: {
    tests_total: 0,
    average_score: null,
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
      requested_another_time: false,
      responsible_recruiter_id: 7,
      responsible_recruiter_name: 'Рекрутер',
    },
  ],
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

    fireEvent.click(screen.getByRole('button', { name: 'Скрипт интервью' }))
    expect(screen.getByTestId('interview-script-modal')).toBeInTheDocument()
    expect(screen.getByTestId('cd-ai-section-toggle-risks')).toBeInTheDocument()
    expect(screen.getByTestId('cd-ai-section-toggle-objections')).toBeInTheDocument()
    expect(screen.getByTestId('cd-ai-section-toggle-cta')).toBeInTheDocument()
  })
})
