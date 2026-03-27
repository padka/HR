import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CandidatePipeline from '@/app/components/CandidatePipeline/CandidatePipeline'
import { CandidateDetailPage } from './candidate-detail'
import {
  useCandidateAi,
  useCandidateChat,
  useCandidateCohort,
  useCandidateDetail,
  useCandidateHh,
  useCitiesOptions,
} from './candidate-detail/candidate-detail.api'
import { DashboardPage } from './dashboard'
import { IncomingPage } from './incoming'
import { MessengerPage } from './messenger'
import { SlotsPage } from './slots'

const useProfileMock = vi.fn()
const useQueryMock = vi.fn()
const useMutationMock = vi.fn()
const apiFetchMock = vi.fn()
const navigateMock = vi.fn()

type QueryOptionsLike = {
  queryKey?: unknown
  staleTime?: number
  refetchInterval?: number | false
  refetchIntervalInBackground?: boolean
  refetchOnWindowFocus?: boolean
  refetchOnReconnect?: boolean
  enabled?: boolean
}

function getQueryOptionsByKey(key: string) {
  return useQueryMock.mock.calls
    .map(([options]) => options as QueryOptionsLike & Record<string, unknown>)
    .filter((options) => Array.isArray(options.queryKey) && options.queryKey[0] === key)
}

vi.mock('@/app/components/RoleGuard', () => ({
  RoleGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock('@/app/hooks/useProfile', () => ({
  useProfile: () => useProfileMock(),
}))

vi.mock('@/api/client', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
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
  useNavigate: () => navigateMock,
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useMutation: (options: unknown) => useMutationMock(options),
  useQueryClient: () => ({
    invalidateQueries: vi.fn(),
    setQueryData: vi.fn(),
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
  created_at: '2031-06-30T08:00:00Z',
  fio: 'Тест Кандидат',
  city: 'Москва',
  phone: '8 929 001 8227',
  telegram_id: 79990001122,
  is_active: true,
  workflow_status: 'intro_day_ready',
  workflow_status_label: 'Готов к ознакомительному дню',
  candidate_status_slug: 'lead',
  responsible_recruiter: { id: 7, name: 'Анна Смирнова' },
  status_is_terminal: false,
  candidate_actions: [],
  needs_intro_day: true,
  can_schedule_intro_day: true,
  journey: {
    state: 'intro_preconfirmed',
    state_label: 'Предварительно подтвердился',
    manual_mode: false,
    current_owner: { type: 'recruiter', id: 7, name: 'Анна Смирнова' },
    next_slot_at: '2031-07-03T09:00:00Z',
    events: [
      {
        id: 901,
        event_key: 'test_completed',
        stage: 'testing',
        status_slug: 'test1_completed',
        actor_type: 'candidate',
        summary: 'Тест 1 завершён',
        created_at: '2031-07-01T08:15:00Z',
      },
      {
        id: 902,
        event_key: 'slot_reschedule_requested',
        stage: 'interview',
        status_slug: 'slot_pending',
        actor_type: 'candidate',
        summary: 'Запросил другой слот',
        payload: { reason: 'Может только утром' },
        created_at: '2031-07-02T08:30:00Z',
      },
      {
        id: 903,
        event_key: 'slot_proposed',
        stage: 'interview',
        status_slug: 'slot_pending',
        actor_type: 'recruiter',
        summary: 'Предложено время, ожидаем ответа',
        created_at: '2031-07-02T09:00:00Z',
      },
      {
        id: 904,
        event_key: 'intro_day_confirmed',
        stage: 'intro_day',
        status_slug: 'intro_day_confirmed_preliminary',
        actor_type: 'candidate',
        summary: 'Предварительно подтвердился',
        created_at: '2031-07-03T07:45:00Z',
      },
    ],
  },
  timeline: [
    {
      kind: 'journey',
      dt: '2031-07-03T07:45:00Z',
      event_key: 'intro_day_confirmed',
      status: 'intro_day_confirmed_preliminary',
      summary: 'Предварительно подтвердился',
    },
    {
      kind: 'test',
      dt: '2031-07-01T08:15:00Z',
      rating: 'Тест 1',
      score: 66.7,
      test_key: 'test1',
    },
    {
      kind: 'message',
      dt: '2031-07-02T11:10:00Z',
      text: 'Напоминание о собеседовании отправлено в Telegram',
    },
    {
      kind: 'interview_feedback',
      dt: '2031-07-02T12:30:00Z',
      summary: 'Интервью проведено',
      outcome_reason: 'Рекомендуем двигаться дальше',
      scorecard: {
        average_rating: 4.2,
      },
    },
  ],
  pipeline_stages: [
    { key: 'lead', label: 'Лид', state: 'passed' },
    { key: 'slot', label: 'Записан на слот', state: 'passed' },
    { key: 'interview', label: 'Собеседование', state: 'passed' },
    { key: 'test2', label: 'Тест 2', state: 'passed' },
    { key: 'intro_day', label: 'Ознакомительный день', state: 'active' },
    { key: 'outcome', label: 'Итог', state: 'pending' },
  ],
  allowed_next_statuses: [
    { slug: 'interview_declined', label: 'Отказ', color: 'danger', is_terminal: true },
  ],
  reschedule_request: null,
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
            question_text: 'Готовы к полевому формату работы?',
            user_answer: 'Да, подходит',
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
  intro_day_template: 'Здравствуйте, [Имя]. Приглашаем вас на ознакомительный день [Дата] в [Время] по адресу {intro_address}.',
  intro_day_template_context: {
    city_name: 'Москва',
    intro_address: 'ул. Тестовая, 1',
    recruiter_contact: 'Михаил +7 999 000-00-00',
  },
  stats: {
    tests_total: 1,
    average_score: 66.7,
  },
}

const cohortComparisonData = {
  available: true,
  cohort_label: 'Оператор склада',
  total_candidates: 47,
  rank: 15,
  test1: {
    candidate: 66.7,
    average: 61.2,
  },
  completion_time_sec: {
    candidate: 780,
    average: 840,
  },
  stage_distribution: [
    { key: 'lead', label: 'Лид', count: 10 },
    { key: 'slot', label: 'Записан на слот', count: 8 },
    { key: 'interview', label: 'Собеседование', count: 9 },
    { key: 'test2', label: 'Тест 2', count: 6 },
    { key: 'intro_day', label: 'Ознакомительный день', count: 9 },
    { key: 'outcome', label: 'Итог', count: 5 },
  ],
}

const interviewScriptData = {
  ok: true,
  cached: true,
  input_hash: 'hash-1',
  script: {
    stage_label: 'Первичный скрининг',
    call_goal: 'Понять базовую релевантность кандидата и перевести на следующий этап.',
    conversation_script:
      'Здравствуйте. Рад познакомиться. Коротко объясню, как пройдёт разговор, и если поймём, что подходим друг другу, предложу следующий этап.\n\nПодскажите, пожалуйста, вы успели посмотреть вакансию и что для вас сейчас важно при выборе работы?',
    risk_flags: [{ code: 'SCHEDULE_RISK', severity: 'medium', reason: 'risk', question: 'q', recommended_phrase: 'p' }],
    highlights: ['h1'],
    checks: ['c1'],
    objections: [{ topic: 'obj', candidate_says: 'cand', recruiter_answer: 'ans' }],
    script_blocks: [
      { id: 'greeting_and_frame', title: 'Вступление и рамка', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
      { id: 'vacancy_interest_and_candidate_filters', title: 'Интерес и фильтры', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
      { id: 'company_and_product_pitch', title: 'Компания и продукт', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
      { id: 'role_and_work_format', title: 'Роль и формат', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
      { id: 'resilience_to_rejection', title: 'Устойчивость к отказам', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
      { id: 'onboarding_and_support', title: 'Обучение и поддержка', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
      { id: 'compensation', title: 'Деньги', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
      { id: 'od_closing_and_confirmation', title: 'ОД и подтверждение', goal: 'goal', recruiter_text: 'text', candidate_questions: ['q1'], if_answers: [{ pattern: 'p', hint: 'h' }] },
    ],
    cta_templates: [{ type: 'next', text: 'text' }],
  },
}

const aiSummaryData = {
  ok: true,
  cached: true,
  input_hash: 'summary-1',
  summary: {
    tldr: 'Кандидат релевантен, формат работы подтверждён, можно доводить до собеседования.',
    fit: {
      score: 82,
      level: 'medium',
      rationale: 'Кандидат подтвердил готовность к полевому формату и подходит по базовым критериям.',
      criteria_used: true,
    },
    scorecard: {
      final_score: 82,
      objective_score: 78,
      semantic_score: 88,
      recommendation: 'od_recommended',
      metrics: [
        { key: 'experience_relevance', label: 'Релевантный опыт', score: 25, weight: 25, status: 'met', evidence: 'Есть клиентский опыт.' },
        { key: 'field_format_readiness', label: 'Готовность к полевому формату', score: 20, weight: 20, status: 'met', evidence: 'Кандидат прямо подтвердил готовность к полевому формату.' },
        { key: 'resume_substance', label: 'Содержательность резюме', score: 24, weight: 30, status: 'met', evidence: 'Резюме описывает релевантный опыт.' },
      ],
      blockers: [],
      missing_data: [],
    },
    risks: [],
    next_actions: [
      { key: 'interview', label: 'Довести до интервью', rationale: 'Следующий реальный шаг по воронке уже назначен.' },
    ],
  },
}

const aiCoachData = {
  ok: true,
  cached: true,
  input_hash: 'coach-1',
  coach: {
    relevance_score: 74,
    relevance_level: 'medium',
    rationale: 'Кандидат близок к ОД, но нужны уточнения.',
    criteria_used: true,
    strengths: [{ key: 'exp', label: 'Опыт общения', evidence: 'Есть опыт общения с клиентами.' }],
    risks: [{ key: 'field', severity: 'medium', label: 'Формат работы', explanation: 'Нужно подтвердить готовность к полевому графику.' }],
    interview_questions: ['Готовы ли вы к разъездному формату?'],
    next_best_action: 'Подтвердить формат работы.',
    message_drafts: [{ text: 'Подскажите, комфортен ли вам разъездной формат?', reason: 'Уточнить ключевой критерий.' }],
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
      ai_relevance_score: 74,
      ai_relevance_level: 'medium',
      ai_recommendation: 'clarify_before_od',
      ai_risk_hint: 'Нужно отдельно подтвердить готовность к разъездному формату.',
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
      archived_at: null,
      is_archived: false,
      last_message_preview: 'Можете предложить утро?',
      last_message_kind: 'candidate',
      priority_bucket: 'needs_reply',
      priority_rank: 1,
      requires_reply: true,
      sla_state: 'needs_reply',
      is_terminal: false,
      vacancy_label: 'Оператор склада',
      assignee_label: 'Рекрутер',
      relevance_score: 82,
      relevance_level: 'medium',
      risk_hint: 'Критичных рисков не зафиксировано.',
      last_message: {
        text: 'Можете предложить утро?',
        preview: 'Можете предложить утро?',
        created_at: '2031-07-01T08:35:00Z',
        direction: 'inbound',
        kind: 'candidate',
      },
      unread_count: 1,
    },
  ],
  latest_event_at: '2031-07-01T08:35:00Z',
}

const candidateChatTemplatesData = {
  items: [
    { key: 'reminder', label: 'Напоминание', text: 'Напоминаем о собеседовании.' },
    { key: 'reschedule', label: 'Перенос', text: 'Напишите удобное время, мы подберем слот.' },
  ],
}

const candidateChannelHealthData = {
  candidate_id: 101,
  preferred_channel: 'max',
  portal_entry_ready: true,
  max_entry_ready: false,
  token_valid: false,
  bot_profile_resolved: false,
  bot_profile_name: null,
  max_link_base_resolved: false,
  max_link_base_source: 'missing',
  portal_public_url: 'https://crm.example.test',
  public_link: 'https://max.ru/id312260558067_bot',
  browser_link: 'https://crm.example.test/candidate/start?start=signed-token',
  mini_app_link: 'https://max.ru/id312260558067_bot?startapp=launch-token',
  active_journey_id: 401,
  session_version: 3,
  last_link_issued_at: '2031-07-01T08:45:00Z',
  restart_allowed: true,
  delivery_ready: false,
  delivery_block_reason: 'max_token_invalid',
  config_errors: ['MAX_BOT_TOKEN отклонён провайдером.'],
  telegram_linked: true,
  max_linked: true,
  telegram: {
    linked: true,
    telegram_id: 79990001122,
    telegram_username: 'candidate_max',
  },
  max: {
    linked: true,
    max_user_id: 'max-101',
  },
  active_invite: {
    status: 'active',
    channel: 'max',
    used_by_external_id: 'max-101',
    conflict: false,
  },
  last_inbound_at: '2031-07-01T08:35:00Z',
  last_outbound_delivery: {
    channel: 'max',
    status: 'dead_letter',
    delivery_stage: 'dead_letter',
    error: 'max:invalid_token',
    created_at: '2031-07-01T08:40:00Z',
  },
  last_portal_access_delivery: {
    channel: 'max',
    status: 'failed',
    delivery_stage: 'failed',
    error: "HTTP 404: {'code': 'chat.not.found', 'message': 'Chat 207980776 not found'}",
    created_at: '2031-07-01T08:45:00Z',
  },
}

describe('UI cosmetics smoke', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'scrollTo', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    })
    useProfileMock.mockReset()
    useQueryMock.mockReset()
    useMutationMock.mockReset()
    apiFetchMock.mockReset()

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

    apiFetchMock.mockImplementation((path: string) => {
      if (path.includes('/chat/updates')) {
        const error = new Error('Aborted')
        error.name = 'AbortError'
        return Promise.reject(error)
      }
      if (path.includes('/candidate-chat/threads/updates')) {
        const error = new Error('Aborted')
        error.name = 'AbortError'
        return Promise.reject(error)
      }
      return Promise.resolve({})
    })

    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
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
      if (key === 'cities') {
        return { ...baseQueryResult, data: [{ id: 1, name: 'Москва', tz: 'Europe/Moscow' }] }
      }
      if (key === 'candidate-detail') {
        if (Array.isArray(rawKey) && rawKey[1] === 11) {
          return {
            ...baseQueryResult,
            data: {
              ...candidateDetailData,
              id: 11,
              fio: 'Иван Петров',
              city: 'Москва',
            },
          }
        }
        return { ...baseQueryResult, data: candidateDetailData }
      }
      if (key === 'candidate-chat') {
        return {
          ...baseQueryResult,
          data: {
            messages: [
              {
                id: 301,
                direction: 'inbound',
                kind: 'candidate',
                text: 'Можете предложить утро?',
                created_at: '2031-07-01T08:35:00Z',
                author: 'Иван Петров',
              },
            ],
            has_more: false,
            latest_message_at: '2031-07-01T08:35:00Z',
          },
        }
      }
      if (key === 'candidate-channel-health') {
        return { ...baseQueryResult, data: candidateChannelHealthData }
      }
      if (key === 'candidate-hh-summary') {
        return {
          ...baseQueryResult,
          data: {
            linked: true,
            source: 'hh',
            vacancy: {
              title: 'Оператор склада',
              url: 'https://hh.ru/vacancy/1',
              area_name: 'Москва',
            },
            resume: {
              title: 'Резюме Ивана Петрова',
              url: 'https://hh.ru/resume/1',
            },
          },
        }
      }
      if (key === 'candidate-cohort-comparison') {
        return { ...baseQueryResult, data: cohortComparisonData, isPending: false }
      }
      if (key === 'candidate-chat-threads') {
        if (Array.isArray(rawKey) && rawKey[1] === 'archive') {
          return { ...baseQueryResult, data: { threads: [], latest_event_at: null } }
        }
        return { ...baseQueryResult, data: candidateChatThreadsData }
      }
      if (key === 'ai-summary') {
        return { ...baseQueryResult, data: aiSummaryData }
      }
      if (key === 'ai-coach') {
        return { ...baseQueryResult, data: aiCoachData }
      }
      if (key === 'candidate-chat-templates') {
        return { ...baseQueryResult, data: candidateChatTemplatesData }
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
    expect(screen.getByText(/AI: Нужно отдельно подтвердить готовность к разъездному формату/)).toBeInTheDocument()
  })

  it('renders incoming cards when AI enrichment is missing', () => {
    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const rawKey = options?.queryKey
      const key = Array.isArray(rawKey) ? rawKey[0] : rawKey
      if (key === 'dashboard-incoming') {
        return {
          ...baseQueryResult,
          data: {
            items: [
              {
                ...incomingData.items[0],
                ai_relevance_score: null,
                ai_relevance_level: null,
                ai_recommendation: null,
                ai_risk_hint: null,
              },
            ],
          },
        }
      }
      return { ...baseQueryResult }
    })

    render(<IncomingPage />)

    const card = screen.getByTestId('incoming-card')
    expect(card).toBeInTheDocument()
    expect(within(card).queryByText(/^AI\b/)).not.toBeInTheDocument()
    expect(within(card).queryByText(/AI: /)).not.toBeInTheDocument()
  })

  it('uses conservative polling for incoming queries', () => {
    render(<IncomingPage />)
    render(<DashboardPage />)

    const incomingCalls = getQueryOptionsByKey('dashboard-incoming')

    expect(incomingCalls.length).toBeGreaterThanOrEqual(2)
    for (const options of incomingCalls) {
      expect(options.staleTime).toBe(120_000)
      expect(options.refetchInterval).toBe(120_000)
      expect(options.refetchIntervalInBackground).toBe(false)
      expect(options.refetchOnWindowFocus).toBe(false)
      expect(options.refetchOnReconnect).toBe(false)
    }
  })

  it('uses bounded cache policies for candidate detail and messenger queries', () => {
    const CandidateDetailQueryHarness = () => {
      useCandidateDetail(101)
      useCandidateHh(101, true)
      useCandidateCohort(101, true)
      useCandidateChat(101, true)
      useCandidateAi(101)
      useCitiesOptions()
      return null
    }

    render(<CandidateDetailQueryHarness />)
    render(<MessengerPage />)

    const expectPolicy = (key: string, expected: Pick<QueryOptionsLike, 'staleTime' | 'refetchOnWindowFocus' | 'refetchOnReconnect'>) => {
      const calls = getQueryOptionsByKey(key)
      expect(calls.length).toBeGreaterThan(0)
      for (const options of calls) {
        expect(options.staleTime).toBe(expected.staleTime)
        expect(options.refetchOnWindowFocus).toBe(expected.refetchOnWindowFocus)
        expect(options.refetchOnReconnect).toBe(expected.refetchOnReconnect)
      }
    }

    expectPolicy('candidate-detail', {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('candidate-hh-summary', {
      staleTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('candidate-cohort-comparison', {
      staleTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('candidate-chat', {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('ai-summary', {
      staleTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('candidate-chat-templates', {
      staleTime: 10 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('candidate-chat-threads', {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('cities', {
      staleTime: 10 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
  })

  it('uses bounded cache policies for dashboard summary and leaderboard queries', () => {
    useProfileMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        principal: { type: 'admin', id: 1 },
        profile: {
          city_options: [{ id: 1, name: 'Москва', tz: 'Europe/Moscow' }],
        },
        recruiter: { id: 1, tz: 'Europe/Moscow', cities: [{ id: 1, name: 'Москва' }] },
      },
    })

    render(<DashboardPage />)

    const expectPolicy = (key: string, expected: Pick<QueryOptionsLike, 'staleTime' | 'refetchOnWindowFocus' | 'refetchOnReconnect'>) => {
      const calls = getQueryOptionsByKey(key)
      expect(calls.length).toBeGreaterThan(0)
      for (const options of calls) {
        expect(options.staleTime).toBe(expected.staleTime)
        expect(options.refetchOnWindowFocus).toBe(expected.refetchOnWindowFocus)
        expect(options.refetchOnReconnect).toBe(expected.refetchOnReconnect)
      }
    }

    expectPolicy('dashboard-summary', {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('dashboard-recruiters', {
      staleTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('dashboard-kpis', {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    expectPolicy('dashboard-leaderboard', {
      staleTime: 120_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    })
    const incomingCalls = getQueryOptionsByKey('dashboard-incoming')
    expect(incomingCalls.length).toBeGreaterThan(0)
    for (const options of incomingCalls) {
      expect(options.staleTime).toBe(120_000)
      expect(options.refetchInterval).toBe(120_000)
      expect(options.refetchIntervalInBackground).toBe(false)
      expect(options.refetchOnWindowFocus).toBe(false)
      expect(options.refetchOnReconnect).toBe(false)
    }
  })

  it('opens test preview modal from incoming card actions and removes telegram shortcut', () => {
    render(<IncomingPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Тест' }))

    const modal = screen.getByTestId('incoming-test-preview-modal')
    expect(modal).toBeInTheDocument()
    expect(screen.getByText('Результат Теста 1')).toBeInTheDocument()
    expect(screen.getByText('Анкета заполнена (3 ответа)')).toBeInTheDocument()
    expect(screen.getByText('Опыт в подборе?')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Telegram' })).not.toBeInTheDocument()
    expect(modal.querySelector('.cd-test-preview')).toBeTruthy()
    expect(modal.querySelector('.cd-question-list')).toBeTruthy()

    const questionCards = modal.querySelectorAll('.cd-question-card')
    expect(questionCards).toHaveLength(3)
    expect(questionCards[0]?.querySelector('.cd-question-card__head strong')?.textContent).toContain('Опыт в подборе?')
    expect(questionCards[0]?.querySelectorAll('.cd-question-card__answer')).toHaveLength(2)

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
    expect(screen.getAllByText(/Уточнить/).length).toBeGreaterThan(0)
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

  it('renders candidate header with insights entrypoint and without inline interview script action button', async () => {
    render(<CandidateDetailPage />)
    const header = screen.getByTestId('candidate-header')
    expect(header).toBeInTheDocument()
    expect(screen.getByTestId('candidate-actions')).toBeInTheDocument()
    expect(header).toHaveTextContent('Лид')
    expect(header.querySelector('.status-pill')).toBeNull()
    expect(screen.getByLabelText('Релевантность 82')).toBeInTheDocument()
    expect(within(header).getByText('82')).toBeInTheDocument()
    expect(within(header).getByText(/Рекомендуем|Уточнить|Не рекомендуем/)).toBeInTheDocument()
    expect(screen.queryByText('Слоты и интервью')).not.toBeInTheDocument()
    expect(screen.queryByText('AI-помощник')).not.toBeInTheDocument()
    expect(screen.getByTestId('candidate-insights-trigger')).toBeInTheDocument()
    expect(screen.queryByTestId('candidate-script-trigger')).not.toBeInTheDocument()
    expect(screen.queryByText('Детали')).not.toBeInTheDocument()
    expect(screen.queryByText('Скрипт интервью')).not.toBeInTheDocument()

    expect(screen.getByTestId('candidate-pipeline')).toBeInTheDocument()
    expect(screen.getByTestId('candidate-tests-section')).toBeInTheDocument()
    expect(screen.queryByTestId('candidate-insights-drawer')).not.toBeInTheDocument()
    expect(screen.queryByTestId('interview-script-panel')).not.toBeInTheDocument()
    expect(screen.queryByTestId('interview-script-modal')).not.toBeInTheDocument()
  })

  it('routes candidate chat through MAX when candidate is linked there', async () => {
    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const rawKey = options?.queryKey
      const key = Array.isArray(rawKey) ? rawKey[0] : rawKey
      if (key === 'candidate-detail') {
        return {
          ...baseQueryResult,
          data: {
            ...candidateDetailData,
            telegram_id: null,
            messenger_platform: 'max',
            max_user_id: 'mx-user-1',
          },
        }
      }
      if (key === 'candidate-chat') {
        return {
          ...baseQueryResult,
          data: {
            messages: [],
            has_more: false,
            latest_message_at: null,
          },
        }
      }
      return { ...baseQueryResult }
    })

    render(<CandidateDetailPage />)

    expect(screen.getByText('MAX')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Чат/ }))

    await waitFor(() => {
      expect(screen.getByText('Ответ будет отправлен через MAX')).toBeInTheDocument()
    })
  })

  it('keeps candidate journey inside funnel stages and removes standalone journey block', async () => {
    render(<CandidateDetailPage />)
    const pipeline = screen.getByTestId('candidate-pipeline')
    const stageTitles = Array.from(
      pipeline.querySelectorAll('.candidate-pipeline-stage__label'),
    ).map((node) => node.textContent)

    expect(screen.queryByText('Интерактивный путь кандидата')).not.toBeInTheDocument()
    expect(stageTitles).toEqual([
      'Лид',
      'Записан на слот',
      'Собеседование',
      'Тест 2',
      'Ознакомительный день',
      'Итог',
    ])
    expect(pipeline.querySelector('.candidate-pipeline-stage--current')).toBeTruthy()
    expect(pipeline.querySelector('.candidate-pipeline-stage--upcoming')).toBeTruthy()
  })

  it('translates english pipeline system copy to russian', () => {
    render(
      <CandidatePipeline
        currentStateLabel="Approved"
        stages={[
          {
            id: 'interview',
            title: 'Собеседование',
            subtitle: 'Initial backfill from current candidate status',
            status: 'current',
            helper: 'admin manual status update',
            detail: {
              description: 'Initial backfill from current candidate status',
              meta: ['manual status update', 'system'],
              events: [
                {
                  id: 'evt-1',
                  title: 'admin manual status update',
                  meta: 'system',
                  lines: ['Status update', 'Completed'],
                  timestamp: '14.03.2026, 12:00',
                },
              ],
            },
          },
        ]}
      />,
    )

    expect(screen.getAllByText('Начальный статус при добавлении в воронку').length).toBeGreaterThan(0)
    expect(screen.getByText('Одобрено')).toBeInTheDocument()
    expect(screen.queryByText('Initial backfill from current candidate status')).not.toBeInTheDocument()
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

  it('renders candidate detail channel health card', async () => {
    render(<CandidateDetailPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-channel-health')).toBeInTheDocument()
      expect(screen.getByText(/Primary workspace: web cabinet/)).toBeInTheDocument()
      expect(screen.getByText(/Telegram linked/)).toBeInTheDocument()
      expect(screen.getByText(/MAX linked/)).toBeInTheDocument()
      expect(screen.getByText(/cabinet: ready/)).toBeInTheDocument()
      expect(screen.getByText(/inbox: available/)).toBeInTheDocument()
      expect(screen.getByText(/send: dead_letter/)).toBeInTheDocument()
      expect(screen.getByText(/portal package: failed/)).toBeInTheDocument()
      expect(screen.getByText(/delivery: blocked/)).toBeInTheDocument()
      expect(screen.getByText(/MAX delivery: MAX токен отклонён провайдером/)).toBeInTheDocument()
      expect(screen.getByText(/portal package error: HTTP 404/)).toBeInTheDocument()
      expect(screen.getByText(/journey: #401 · session v3/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть кабинет' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Подготовить browser link' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть MAX launcher' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть browser fallback' })).toBeInTheDocument()
    })
  })

  it('renders messenger as recruiter workspace with compact inbox and sticky composer', async () => {
    render(<MessengerPage />)

    await waitFor(() => {
      expect(screen.getByRole('complementary', { name: 'Чаты кандидатов' })).toBeInTheDocument()
      expect(screen.getAllByText('Иван Петров').length).toBeGreaterThan(0)
      expect(screen.getAllByText(/Можете предложить утро/).length).toBeGreaterThan(0)
      expect(screen.getByLabelText('Поиск по чатам')).toBeInTheDocument()
      expect(screen.getByTestId('messenger-messages')).toBeInTheDocument()
      expect(screen.getByTestId('messenger-composer')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Отправить сообщение' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Детали' })).not.toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Карточка' })).toBeInTheDocument()
      expect(screen.getByText('MAX')).toBeInTheDocument()
      expect(screen.getByText(/send: dead_letter/)).toBeInTheDocument()
      expect(screen.getByText('max:invalid_token')).toBeInTheDocument()
    })
  })

})
