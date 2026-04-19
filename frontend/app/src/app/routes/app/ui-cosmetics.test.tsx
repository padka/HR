import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CandidatePipeline from '@/app/components/CandidatePipeline/CandidatePipeline'
import { CandidateDetailPage } from './candidate-detail'
import { CandidatesPage } from './candidates'
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
const invalidateQueriesMock = vi.fn()

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
    invalidateQueries: invalidateQueriesMock,
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
  hh_profile_url: 'https://hh.ru/resume/1',
  is_active: true,
  workflow_status: 'intro_day_ready',
  workflow_status_label: 'Готов к ознакомительному дню',
  candidate_status_slug: 'lead',
  responsible_recruiter: { id: 7, name: 'Анна Смирнова' },
  status_is_terminal: false,
  candidate_actions: [],
  needs_intro_day: true,
  can_schedule_intro_day: true,
  lifecycle_summary: {
    stage: 'lead',
    stage_label: 'Лид',
    record_state: 'active',
  },
  candidate_next_action: {
    version: 1,
    lifecycle_stage: 'lead',
    record_state: 'active',
    worklist_bucket: 'incoming',
    urgency: 'attention',
    primary_action: {
      type: 'offer_interview_slot',
      label: 'Предложить время',
      enabled: true,
      owner_role: 'recruiter',
      ui_action: 'open_schedule_slot_modal',
      legacy_action_key: 'schedule_interview',
      blocking_reasons: [],
    },
    explanation: 'Кандидат готов к назначению интервью.',
  },
  state_reconciliation: {
    issues: [],
    has_blockers: false,
  },
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
  max_rollout: {
    status: 'ready',
    status_label: 'Готово к предпросмотру',
    summary: 'Приглашение подготовлено и готово к отправке кандидату.',
    hint: 'Проверьте предпросмотр перед отправкой.',
    issued_at: '2031-07-01T08:45:00Z',
    expires_at: '2031-07-02T08:45:00Z',
    dry_run: true,
    launch_state: 'launched',
    launch_observation: {
      launched: true,
      launched_at: '2031-07-01T09:10:00Z',
      access_session_id: 41,
      provider_bound: true,
    },
    preview: {
      start_param: 'launch-token',
      max_launch_url: 'https://max.ru/id312260558067_bot?startapp=launch-token',
      max_chat_url: 'https://max.ru/id312260558067_bot?start=launch-token',
      message_preview: '[DRY RUN] Откройте мини-приложение MAX, чтобы продолжить путь кандидата.',
      expires_at: '2031-07-02T08:45:00Z',
      dry_run: true,
    },
    actions: {
      send: { key: 'max_pilot_send', label: 'Отправить', method: 'POST' },
      reissue: { key: 'max_pilot_reissue', label: 'Перевыпустить', method: 'POST' },
      revoke: { key: 'max_pilot_revoke', label: 'Отозвать', method: 'POST' },
    },
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
  queue_total: 3,
  total: 1,
  page: 1,
  page_size: 50,
  returned_count: 1,
  has_next: true,
  has_prev: false,
  sort: 'priority',
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
      ai_relevance_state: 'ready',
      ai_recommendation: 'clarify_before_od',
      ai_risk_hint: 'Нужно отдельно подтвердить готовность к разъездному формату.',
      ai_reasons: [
        { tone: 'risk', label: 'Нужно подтвердить готовность к полевому формату' },
        { tone: 'positive', label: 'Хорошо проходит первичный тест' },
      ],
      lifecycle_summary: {
        stage: 'waiting_interview_slot',
        stage_label: 'Ожидает слот на интервью',
        record_state: 'active',
      },
      scheduling_summary: {
        source: 'slot_assignment',
        stage: 'interview',
        status: 'reschedule_requested',
        status_label: 'Запрошен перенос',
        active: true,
        requested_reschedule: true,
      },
      candidate_next_action: {
        version: 1,
        lifecycle_stage: 'interview',
        record_state: 'active',
        worklist_bucket: 'awaiting_recruiter',
        urgency: 'attention',
        primary_action: {
          type: 'resolve_reschedule',
          label: 'Обработать перенос',
          enabled: true,
          owner_role: 'recruiter',
          ui_action: 'open_schedule_slot_modal',
          blocking_reasons: [],
        },
        explanation: 'Кандидат запросил перенос времени. Требуется новый слот.',
      },
      state_reconciliation: {
        issues: [{ code: 'workflow_status_drift', severity: 'warning', message: 'workflow_status расходится.' }],
        has_blockers: true,
      },
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
  telegram_entry_ready: true,
  token_valid: false,
  bot_profile_resolved: false,
  bot_profile_name: null,
  max_link_base_resolved: false,
  max_link_base_source: 'missing',
  portal_public_url: 'https://crm.example.test',
  shared_portal_url: 'https://crm.example.test/candidate/start',
  shared_portal_ready: true,
  shared_portal_block_reason: null,
  last_shared_portal_sent_at: '2031-07-01T08:45:00Z',
  last_otp_delivery_channel: 'hh',
  public_link: 'https://max.ru/id312260558067_bot',
  browser_link: 'https://crm.example.test/candidate/start?start=signed-token',
  mini_app_link: 'https://max.ru/id312260558067_bot?startapp=launch-token',
  telegram_link: 'https://t.me/attila_test_bot?start=telegram-invite',
  active_journey_id: 401,
  session_version: 3,
  last_entry_channel: 'web',
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

const candidateListData = {
  items: [
    {
      id: 201,
      fio: 'Тест Telegram',
      city: 'Москва',
      telegram_id: 79990002211,
      telegram_username: 'telegram_201',
      telegram_linked_at: '2031-07-01T08:10:00Z',
      linked_channels: {
        telegram: true,
        max: false,
      },
      max: {
        linked: false,
      },
      preferred_channel: 'telegram',
      max_rollout: {
        invite_state: 'not_issued',
        send_state: 'not_sent',
        launch_state: 'not_launched',
      },
      recruiter_id: 7,
      recruiter_name: 'Анна Смирнова',
      average_score: 77,
      primary_event_at: '2031-07-02T08:00:00Z',
      status: {
        slug: 'lead',
        label: 'Лид',
        tone: 'info',
      },
      lifecycle_summary: {
        stage: 'lead',
        stage_label: 'Лид',
        record_state: 'active',
      },
      candidate_next_action: {
        label: 'Откройте профиль',
        explanation: 'Следующий шаг появится после открытия профиля кандидата.',
        enabled: true,
      },
      operational_summary: {
        worklist_bucket: 'incoming',
        worklist_bucket_label: 'Входящие',
        urgency: 'attention',
        urgency_label: 'Нужно сейчас',
        next_action_label: 'Откройте профиль',
        queue_state_label: 'В работе',
        state_context_line: 'Лид',
        scheduling_context_line: null,
      },
    },
    {
      id: 202,
      fio: 'Тест MAX',
      city: 'Казань',
      telegram_id: 79990003322,
      telegram_username: 'max_202',
      telegram_linked_at: '2031-07-01T08:15:00Z',
      linked_channels: {
        telegram: true,
        max: true,
      },
      max: {
        linked: true,
        max_user_id: 'max-202',
      },
      preferred_channel: 'max',
      max_rollout: {
        invite_state: 'active',
        send_state: 'sent',
        launch_state: 'not_launched',
      },
      recruiter_id: 7,
      recruiter_name: 'Анна Смирнова',
      average_score: 62,
      primary_event_at: '2031-07-02T09:00:00Z',
      status: {
        slug: 'lead',
        label: 'Лид',
        tone: 'info',
      },
      lifecycle_summary: {
        stage: 'lead',
        stage_label: 'Лид',
        record_state: 'active',
      },
      candidate_next_action: {
        label: 'Откройте профиль',
        explanation: 'Следующий шаг появится после открытия профиля кандидата.',
        enabled: true,
      },
      operational_summary: {
        worklist_bucket: 'incoming',
        worklist_bucket_label: 'Входящие',
        urgency: 'attention',
        urgency_label: 'Нужно сейчас',
        next_action_label: 'Откройте профиль',
        queue_state_label: 'В работе',
        state_context_line: 'Лид',
        scheduling_context_line: null,
      },
    },
  ],
  total: 2,
  page: 1,
  pages_total: 1,
  filters: {
    state_options: [{ value: '', label: 'Все кандидаты', kind: 'all' }],
  },
  pipeline_options: [{ slug: 'interview', label: 'Интервью' }],
  views: {
    candidates: [],
    kanban: { columns: [] },
    calendar: { days: [] },
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
    invalidateQueriesMock.mockReset()

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
      if (key === 'candidates') {
        return { ...baseQueryResult, data: candidateListData }
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
            entry_delivery: {
              ready: false,
              blocked_reason: 'hh_message_action_missing',
              cabinet_url: 'https://crm.example.test/candidate/start?start=signed-token',
              hh_entry_url: 'https://crm.example.test/candidate/start',
              shared_portal_url: 'https://crm.example.test/candidate/start',
              last_status: 'blocked',
              selected_channel: 'web',
              last_otp_delivery_channel: 'hh',
            },
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

    expect(screen.getByTestId('incoming-list')).toBeInTheDocument()
    const rows = screen.getAllByTestId('incoming-row')
    expect(rows.length).toBeGreaterThan(0)
    expect(rows[0]).toHaveClass('incoming-row')
    expect(screen.getByText('Во входящих')).toBeInTheDocument()
    expect(screen.getByTestId('incoming-queue-total')).toHaveTextContent('3')
    expect(screen.getByText('Показано 1–1')).toBeInTheDocument()
    expect(screen.getByText('Страница 1 из 1')).toBeInTheDocument()
    expect(screen.getAllByText('Ожидает слот на интервью').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Обработать перенос').length).toBeGreaterThan(0)
    expect(screen.getByText('Сейчас')).toBeInTheDocument()
    expect(screen.getByText('Требует проверки')).toBeInTheDocument()
    expect(screen.queryByText('Кандидат запросил перенос времени. Требуется новый слот.')).not.toBeInTheDocument()
    expect(within(rows[0]).queryByText('AI relevance')).not.toBeInTheDocument()
    const aiScore = screen.getByTestId('incoming-ai-score')
    expect(within(aiScore).getByText('74')).toBeInTheDocument()

    const advancedToggle = screen.getByTestId('incoming-advanced-filters-toggle')
    fireEvent.click(advancedToggle)
    expect(document.querySelector('.ui-filter-bar__advanced--open')).toBeTruthy()

    const moreToggle = within(rows[0]).getByRole('button', { name: 'Подробнее' })
    fireEvent.click(moreToggle)
    expect(moreToggle).toHaveTextContent('Скрыть детали')
    const details = screen.getByTestId('incoming-row-details-11')
    expect(details).toBeInTheDocument()
    expect(screen.getByText(/workflow_status расходится/)).toBeInTheDocument()
    expect(screen.getByText(/Хочет окно:/)).toBeInTheDocument()
    expect(within(details).getByText('AI relevance')).toBeInTheDocument()
    expect(screen.getByText('74/100')).toBeInTheDocument()
    expect(screen.getByText('Актуально')).toBeInTheDocument()
    expect(screen.getAllByText('Нужно подтвердить готовность к полевому формату').length).toBeGreaterThan(0)
  })

  it('renders incoming cards with quiet missing AI state in collapsed rows', () => {
    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const rawKey = options?.queryKey
      const key = Array.isArray(rawKey) ? rawKey[0] : rawKey
      if (key === 'dashboard-incoming') {
        return {
          ...baseQueryResult,
          data: {
            ...incomingData,
            queue_total: 1,
            total: 1,
            returned_count: 1,
            has_next: false,
            items: [
              {
                ...incomingData.items[0],
                ai_relevance_score: null,
                ai_relevance_level: null,
                ai_relevance_state: 'unknown',
                ai_recommendation: null,
                ai_risk_hint: null,
                ai_reasons: [],
              },
            ],
          },
        }
      }
      return { ...baseQueryResult }
    })

    render(<IncomingPage />)

    const row = screen.getByTestId('incoming-row')
    expect(row).toBeInTheDocument()
    const aiScore = within(row).getByTestId('incoming-ai-score')
    expect(within(aiScore).getByText('—')).toBeInTheDocument()
    expect(within(row).queryByText('Unknown')).not.toBeInTheDocument()
    expect(within(row).queryByText('Недостаточно данных')).not.toBeInTheDocument()
  })

  it('derives truthful queue totals when additive queue_total is missing or zeroed', () => {
    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const rawKey = options?.queryKey
      const key = Array.isArray(rawKey) ? rawKey[0] : rawKey
      if (key === 'dashboard-incoming') {
        return {
          ...baseQueryResult,
          data: {
            ...incomingData,
            queue_total: 0,
            total: 21,
            returned_count: 1,
            has_next: true,
          },
        }
      }
      return { ...baseQueryResult }
    })

    render(<IncomingPage />)

    expect(screen.getByTestId('incoming-queue-total')).toHaveTextContent('21')
    expect(screen.getByTestId('incoming-summary-detail')).toHaveTextContent('Показано 1–1')
  })

  it('keeps only one incoming disclosure open at a time', () => {
    useQueryMock.mockImplementation((options: QueryOptionsLike) => {
      const rawKey = options?.queryKey
      const key = Array.isArray(rawKey) ? rawKey[0] : rawKey
      if (key === 'dashboard-incoming') {
        return {
          ...baseQueryResult,
          data: {
            ...incomingData,
            queue_total: 2,
            total: 2,
            returned_count: 2,
            items: [
              incomingData.items[0],
              {
                ...incomingData.items[0],
                id: 12,
                name: 'Мария Сергеева',
                requested_another_time_comment: 'После обеда',
                state_reconciliation: {
                  issues: [],
                  has_blockers: false,
                },
              },
            ],
          },
        }
      }
      return { ...baseQueryResult }
    })

    render(<IncomingPage />)

    const moreButtons = screen.getAllByRole('button', { name: 'Подробнее' })
    fireEvent.click(moreButtons[0])
    expect(screen.getByTestId('incoming-row-details-11')).toBeInTheDocument()
    fireEvent.click(moreButtons[1])
    expect(screen.queryByTestId('incoming-row-details-11')).not.toBeInTheDocument()
    expect(screen.getByTestId('incoming-row-details-12')).toBeInTheDocument()
  })

  it('uses server-driven incoming query params for paging and sorting', () => {
    render(<IncomingPage />)

    const incomingCalls = getQueryOptionsByKey('dashboard-incoming')
    expect(incomingCalls.length).toBeGreaterThan(0)
    const firstKey = incomingCalls[0]?.queryKey as [string, Record<string, unknown>]
    expect(firstKey[1]).toMatchObject({
      page: 1,
      pageSize: 50,
      statusFilter: 'all',
      ownerFilter: 'all',
      waitingFilter: 'all',
      aiFilter: 'all',
      sortMode: 'priority',
    })

    fireEvent.change(screen.getAllByDisplayValue('По приоритету')[0], { target: { value: 'ai_score_desc' } })
    const afterSortCalls = getQueryOptionsByKey('dashboard-incoming')
    const afterSortKey = (afterSortCalls[afterSortCalls.length - 1]?.queryKey ?? []) as [string, Record<string, unknown>]
    expect(afterSortKey[1]).toMatchObject({ sortMode: 'ai_score_desc', page: 1 })

    fireEvent.click(screen.getByRole('button', { name: 'Дальше' }))
    const afterPageCalls = getQueryOptionsByKey('dashboard-incoming')
    const afterPageKey = (afterPageCalls[afterPageCalls.length - 1]?.queryKey ?? []) as [string, Record<string, unknown>]
    expect(afterPageKey[1]).toMatchObject({ page: 2, sortMode: 'ai_score_desc' })
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

    fireEvent.click(screen.getByRole('button', { name: 'Подобрать время' }))
    expect(screen.getByTestId('incoming-schedule-modal')).toBeInTheDocument()
    expect(screen.getByText('Вы назначаете')).toBeInTheDocument()
    expect(screen.getByText('Кандидат увидит')).toBeInTheDocument()
    expect(screen.getByText('Напоминание за 2 часа отправляется по времени кандидата.')).toBeInTheDocument()
  })

  it('uses expanded incoming workspace as recruiter dashboard default', () => {
    render(<DashboardPage />)
    const incomingFilterBar = screen.getByTestId('incoming-filter-bar')
    expect(incomingFilterBar).toBeInTheDocument()

    const incomingRow = screen.getByTestId('incoming-row')
    expect(incomingRow).toBeInTheDocument()
    expect(screen.getByTestId('incoming-list')).toBeInTheDocument()
    expect(screen.getAllByText(/Обработать перенос/).length).toBeGreaterThan(0)
  })

  it('renders admin dashboard as triage-first control tower with quiet KPI sections', () => {
    useProfileMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        principal: { type: 'admin', id: 1 },
        recruiter: { id: 7, tz: 'Europe/Moscow', cities: [{ id: 1, name: 'Москва' }] },
        profile: {
          city_options: [{ id: 1, name: 'Москва', tz: 'Europe/Moscow' }],
        },
      },
    })

    render(<DashboardPage />)

    expect(screen.getByTestId('dashboard-triage-console')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-triage-summary')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-triage-filter-bar')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-triage-lanes')).toBeInTheDocument()
    expect(screen.getByText('Control Tower')).toBeInTheDocument()
    expect(screen.getByText('Требует действия сейчас')).toBeInTheDocument()
    expect(screen.getByText('Ждет кандидата / внешнего ответа')).toBeInTheDocument()
    expect(screen.getByText('Требует разбора / есть конфликт')).toBeInTheDocument()
    expect(screen.getByText('Общая сводка')).toBeInTheDocument()
    expect(screen.getByText('Лидерборд эффективности')).toBeInTheDocument()
  })

  it('renders slots filter/table test ids', () => {
    render(<SlotsPage />)
    const filterBar = screen.getByTestId('slots-filter-bar')
    expect(filterBar).toBeInTheDocument()
    expect(filterBar).toHaveClass('slots-filters-grid')

    const resultsToolbar = screen.getByTestId('slots-results-toolbar')
    expect(resultsToolbar).toBeInTheDocument()

    const table = screen.getByTestId('slots-table')
    expect(table).toBeInTheDocument()
    expect(table).toHaveClass('data-table')
    expect(document.querySelector('.status-badge')).toBeTruthy()
  })

  it('renders candidate header with insights entrypoint and without inline interview script action button', async () => {
    render(<CandidateDetailPage />)
    const header = screen.getByTestId('candidate-header')
    expect(header).toBeInTheDocument()
    expect(screen.getByTestId('candidate-action-center')).toBeInTheDocument()
    expect(screen.getByTestId('candidate-actions')).toBeInTheDocument()
    expect(header).toHaveTextContent('Лид')
    expect(header.querySelector('.status-pill')).toBeNull()
    expect(screen.getAllByText('Предложить время').length).toBeGreaterThan(0)
    expect(screen.getByText('Кандидат готов к назначению интервью.')).toBeInTheDocument()
    expect(screen.getByTestId('candidate-channels')).toBeInTheDocument()
    expect(screen.getByTestId('candidate-detail-lifecycle')).toBeInTheDocument()
    expect(screen.queryByTestId('candidate-detail-scheduling')).not.toBeInTheDocument()
    expect(screen.queryByTestId('candidate-detail-risks')).not.toBeInTheDocument()
    expect(screen.queryByTestId('candidate-detail-context')).not.toBeInTheDocument()
    expect(screen.getByText('Путь кандидата')).toBeInTheDocument()
    expect(screen.queryByText('Lifecycle')).not.toBeInTheDocument()
    expect(screen.queryByText('Scheduling')).not.toBeInTheDocument()
    expect(screen.queryByText('Risks & blockers')).not.toBeInTheDocument()
    expect(screen.queryByText('Context & history')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Релевантность 82')).toBeInTheDocument()
    expect(within(header).getByText('82')).toBeInTheDocument()
    expect(within(header).getByText(/Рекомендуем|Уточнить|Не рекомендуем/)).toBeInTheDocument()
    expect(screen.queryByText('Слоты и интервью')).not.toBeInTheDocument()
    expect(screen.queryByText('AI-помощник')).not.toBeInTheDocument()
    expect(screen.getByTestId('candidate-insights-trigger')).toBeInTheDocument()
    expect(screen.getByTestId('candidate-tests-trigger')).toBeInTheDocument()
    expect(screen.getByTestId('candidate-hh-trigger')).toBeInTheDocument()
    expect(screen.queryByTestId('candidate-script-trigger')).not.toBeInTheDocument()
    expect(screen.queryByText('Детали')).not.toBeInTheDocument()
    expect(screen.queryByText('Скрипт интервью')).not.toBeInTheDocument()

    expect(screen.getByTestId('candidate-pipeline')).toBeInTheDocument()
    expect(screen.queryByTestId('candidate-tests-section')).not.toBeInTheDocument()
    expect(screen.queryByTestId('candidate-insights-drawer')).not.toBeInTheDocument()
    expect(screen.queryByTestId('interview-script-panel')).not.toBeInTheDocument()
    expect(screen.queryByTestId('interview-script-modal')).not.toBeInTheDocument()
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
      expect(
        screen.getAllByRole('button', { name: 'Тесты' }).some((button) => button.className.includes('ui-btn--primary')),
      ).toBe(true)
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

  it('keeps candidate detail profile free from delivery diagnostics cards', async () => {
    render(<CandidateDetailPage />)

    await waitFor(() => {
      expect(screen.queryByTestId('candidate-channel-health')).not.toBeInTheDocument()
      expect(screen.queryByTestId('candidate-hh-entry-health')).not.toBeInTheDocument()
      expect(screen.queryByText(/Candidate Cabinet/)).not.toBeInTheDocument()
      expect(screen.queryByText(/Entry \/ Delivery/)).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Открыть кабинет' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Отправить shared portal в HH' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Открыть MAX launcher' })).not.toBeInTheDocument()
      expect(screen.queryByText('candidate_max')).not.toBeInTheDocument()
      expect(screen.queryByText('max-101')).not.toBeInTheDocument()
      expect(screen.queryByText('ID 79990001122')).not.toBeInTheDocument()
      expect(screen.getByTestId('candidate-channels')).toBeInTheDocument()
      expect(screen.getByText('Telegram')).toBeInTheDocument()
      expect(screen.getByText('HeadHunter')).toBeInTheDocument()
    })
  })

  it('opens HH profile in modal from candidate detail', async () => {
    render(<CandidateDetailPage />)

    expect(screen.queryByTestId('candidate-detail-max-pilot')).not.toBeInTheDocument()
    fireEvent.click(screen.getByTestId('candidate-hh-trigger'))
    expect(screen.getByText('Резюме HeadHunter')).toBeInTheDocument()
    expect(screen.getByText('Быстрый просмотр профиля кандидата внутри RecruitSmart.')).toBeInTheDocument()
  })

  it('opens insights as notes-first drawer with compact HH block only', async () => {
    render(<CandidateDetailPage />)

    fireEvent.click(screen.getByTestId('candidate-insights-trigger'))

    const drawer = await screen.findByTestId('candidate-insights-drawer')
    expect(drawer).toBeInTheDocument()
    expect(within(drawer).getByText('Заметки по кандидату')).toBeInTheDocument()
    expect(within(drawer).getByTestId('candidate-quick-notes')).toBeInTheDocument()
    expect(within(drawer).getByTestId('candidate-insights-hh')).toBeInTheDocument()
    expect(within(drawer).getByText('HeadHunter')).toBeInTheDocument()
    expect(within(drawer).getByText('Резюме Ивана Петрова')).toBeInTheDocument()
    expect(within(drawer).getByRole('link', { name: 'Открыть в HH' })).toHaveAttribute('href', 'https://hh.ru/resume/1')
    expect(within(drawer).queryByText('Карточка кандидата')).not.toBeInTheDocument()
    expect(within(drawer).queryByText('AI-помощник')).not.toBeInTheDocument()
    expect(within(drawer).queryByText('Подсказки рекрутеру')).not.toBeInTheDocument()
    expect(within(drawer).queryByText('Хронология')).not.toBeInTheDocument()
  })

  it('renders bounded channel badges and compact MAX filter in the candidates list', async () => {
    render(<CandidatesPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidates-advanced-filters-toggle')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('candidates-advanced-filters-toggle'))

    await waitFor(() => {
      expect(screen.getByTestId('candidates-channel-filter')).toBeInTheDocument()
      expect(screen.getByTestId('candidates-preferred-channel-filter')).toBeInTheDocument()
      expect(screen.getAllByTestId('candidate-channel-badges')).toHaveLength(2)
      expect(screen.getByText('Тест Telegram')).toBeInTheDocument()
      expect(screen.getByText('Тест MAX')).toBeInTheDocument()
      expect(within(screen.getAllByTestId('candidate-channel-badges')[0]).getByText('TG')).toBeInTheDocument()
      expect(within(screen.getAllByTestId('candidate-channel-badges')[0]).getByText('MAX')).toBeInTheDocument()
      expect(within(screen.getAllByTestId('candidate-channel-badges')[1]).getByText('MAX')).toBeInTheDocument()
      expect(within(screen.getAllByTestId('candidate-channel-badges')[1]).getByText('Отправлено')).toBeInTheDocument()
    })

    fireEvent.click(within(screen.getByTestId('candidates-channel-filter')).getByRole('button', { name: 'MAX' }))

    await waitFor(() => {
      expect(screen.getByText('Тест MAX')).toBeInTheDocument()
      expect(screen.queryByText('Тест Telegram')).not.toBeInTheDocument()
    })

    fireEvent.click(within(screen.getByTestId('candidates-channel-filter')).getByRole('button', { name: 'Все' }))
    fireEvent.click(within(screen.getByTestId('candidates-preferred-channel-filter')).getByRole('button', { name: 'Telegram' }))

    await waitFor(() => {
      expect(screen.getByText('Тест Telegram')).toBeInTheDocument()
      expect(screen.queryByText('Тест MAX')).not.toBeInTheDocument()
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
